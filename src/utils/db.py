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
