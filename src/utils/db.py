import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
import psycopg2.extras


def _conn() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
        sslmode="require",
    )


def _ensure_table() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS extracted_data (
                    id         SERIAL PRIMARY KEY,
                    name       TEXT        NOT NULL DEFAULT '',
                    emails     TEXT[]      NOT NULL DEFAULT '{}',
                    phones     TEXT[]      NOT NULL DEFAULT '{}',
                    urls       TEXT[]      NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        conn.commit()


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _ensure_url_tables() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS validated_urls (
                    id            SERIAL PRIMARY KEY,
                    url           TEXT        NOT NULL,
                    status_code   INT,
                    response_time FLOAT,
                    content_type  TEXT        DEFAULT '',
                    server        TEXT        DEFAULT '',
                    redirect_url  TEXT        DEFAULT '',
                    checked_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS not_validated_urls (
                    id            SERIAL PRIMARY KEY,
                    url           TEXT        NOT NULL,
                    error_message TEXT        DEFAULT '',
                    status_code   INT,
                    checked_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)
        conn.commit()


def push_validated_urls(results: list) -> int:
    working = [r for r in results if r.is_working]
    if not working:
        return 0

    _ensure_url_tables()

    records = [
        (
            r.url,
            r.status_code,
            r.response_time,
            r.content_type or "",
            r.server or "",
            r.redirect_url or "",
        )
        for r in working
    ]

    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO validated_urls (url, status_code, response_time, content_type, server, redirect_url) VALUES %s",
                records,
            )
        conn.commit()

    return len(records)


def push_not_validated_urls(results: list) -> int:
    failed = [r for r in results if not r.is_working]
    if not failed:
        return 0

    _ensure_url_tables()

    records = [
        (
            r.url,
            r.error_message or "",
            r.status_code,
        )
        for r in failed
    ]

    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO not_validated_urls (url, error_message, status_code) VALUES %s",
                records,
            )
        conn.commit()

    return len(records)


def push_entity_map(rows: list[dict]) -> int:
    if not rows:
        return 0

    _ensure_table()

    records = [
        (
            r.get("Name", ""),
            _split(r.get("Emails", "")),
            _split(r.get("Phones", "")),
            _split(r.get("URLs", "")),
        )
        for r in rows
    ]

    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO extracted_data (name, emails, phones, urls) VALUES %s",
                records,
            )
        conn.commit()

    return len(records)
