import streamlit as st
import pymysql
import pymysql.cursors


def _conn() -> pymysql.connections.Connection:
    cfg = st.secrets["mysql"]
    return pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port", 3306)),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


def _ensure_table(cur: pymysql.cursors.DictCursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS extracted_contacts (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(255)  DEFAULT '',
            email      VARCHAR(320)  DEFAULT '',
            phone      VARCHAR(50)   DEFAULT '',
            url        VARCHAR(2048) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)


def push_entity_map(rows: list[dict]) -> int:
    """Insert entity-map rows into extracted_contacts. Returns number of rows inserted."""
    if not rows:
        return 0

    records = [
        (
            r.get("Name", ""),
            r.get("Emails", ""),
            r.get("Phones", ""),
            r.get("URLs", ""),
        )
        for r in rows
    ]

    with _conn() as conn:
        with conn.cursor() as cur:
            _ensure_table(cur)
            cur.executemany(
                "INSERT INTO extracted_contacts (name, email, phone, url) VALUES (%s, %s, %s, %s)",
                records,
            )
        conn.commit()

    return len(records)
