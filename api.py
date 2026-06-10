import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
import psycopg2.extras
from datetime import date
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="Extractor API")


def _conn():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
        sslmode="require",
    )


@app.get("/extracted", response_class=JSONResponse)
def get_extracted(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    from_date: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    offset = (page - 1) * page_size
    direction = "DESC" if order == "desc" else "ASC"

    filters = []
    params: list = []
    if from_date:
        filters.append("created_at >= %s")
        params.append(from_date)
    if to_date:
        filters.append("created_at < %s + INTERVAL '1 day'")
        params.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM extracted_data {where}", params)
            total = cur.fetchone()["total"]

            cur.execute(
                f"""
                SELECT id, name, emails, phones, urls, created_at
                FROM extracted_data {where}
                ORDER BY created_at {direction}
                LIMIT %s OFFSET %s
                """,
                params + [page_size, offset],
            )
            rows = cur.fetchall()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "order": order,
        "data": [
            {
                "id": r["id"],
                "name": r["name"],
                "emails": r["emails"],
                "phones": r["phones"],
                "urls": r["urls"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }
