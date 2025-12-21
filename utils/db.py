from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = Path("data") / "market_analyzer.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                platform        TEXT NOT NULL,
                external_id     TEXT NOT NULL,
                keyword         TEXT NOT NULL,
                title           TEXT NOT NULL,
                description     TEXT,
                price           REAL,
                currency        TEXT,
                city            TEXT,
                created_at_api  INTEGER,
                scraped_at      TEXT NOT NULL,
                url             TEXT
            );
            """
        )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_keyword ON products(keyword);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_platform ON products(platform);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_scraped_at ON products(scraped_at);")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_unique_listing ON products(platform, external_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_listing_history ON products(external_id, scraped_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scraped_keyword ON products(keyword, scraped_at);")

        conn.commit()


def save_products(keyword: str, productos: List[Dict[str, Any]]) -> int:
    if not productos:
        return 0

    init_db()
    scraped_at = datetime.utcnow().isoformat()

    rows = []
    for p in productos:
        rows.append(
            (
                p.get("platform") or "wallapop",
                p.get("id"),
                keyword,
                p.get("titulo") or "",
                p.get("descripcion") or "",
                p.get("precio"),
                "EUR",
                p.get("ciudad"),
                p.get("created_at"),
                scraped_at,
                p.get("url"),
            )
        )

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO products (
                platform,
                external_id,
                keyword,
                title,
                description,
                price,
                currency,
                city,
                created_at_api,
                scraped_at,
                url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def delete_run(keyword: str, scraped_at: str) -> int:
    if not DB_PATH.is_file():
        return 0

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM products
            WHERE keyword = ?
              AND scraped_at = ?;
            """,
            (keyword, scraped_at),
        )
        deleted = cur.rowcount or 0
        conn.commit()

    return int(deleted)


def delete_all_for_keyword(keyword: str) -> int:
    if not DB_PATH.is_file():
        return 0

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM products
            WHERE keyword = ?;
            """,
            (keyword,),
        )
        deleted = cur.rowcount or 0
        conn.commit()

    return int(deleted)
