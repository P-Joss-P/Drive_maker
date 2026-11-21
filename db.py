# SPDX-FileCopyrightText: 2026 P-Joss-P
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Base SQLite : correspondance article -> produit choisi, par enseigne."""
import sqlite3
from dataclasses import dataclass

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS mapping (
    article_key   TEXT NOT NULL,          -- nom normalisé de l'article Tandoor
    site          TEXT NOT NULL,          -- 'carrefour' | 'leclerc'
    product_name  TEXT,
    product_url   TEXT,
    qty_default   INTEGER NOT NULL DEFAULT 1,  -- nombre d'unités à acheter
    ignored       INTEGER NOT NULL DEFAULT 0,  -- 1 = ne jamais acheter via le drive
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (article_key, site)
);
"""


@dataclass
class Mapping:
    article_key: str
    site: str
    product_name: str | None
    product_url: str | None
    qty_default: int
    ignored: bool


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_mapping(conn, article_key: str, site: str) -> Mapping | None:
    row = conn.execute(
        "SELECT * FROM mapping WHERE article_key = ? AND site = ?",
        (article_key, site),
    ).fetchone()
    if row is None:
        return None
    return Mapping(
        row["article_key"], row["site"], row["product_name"],
        row["product_url"], row["qty_default"], bool(row["ignored"]),
    )


def save_mapping(conn, article_key, site, product_name, product_url, qty=1, ignored=False):
    conn.execute(
        """INSERT INTO mapping (article_key, site, product_name, product_url, qty_default, ignored)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(article_key, site) DO UPDATE SET
             product_name = excluded.product_name,
             product_url  = excluded.product_url,
             qty_default  = excluded.qty_default,
             ignored      = excluded.ignored,
             updated_at   = CURRENT_TIMESTAMP""",
        (article_key, site, product_name, product_url, qty, int(ignored)),
    )
    conn.commit()


def list_mappings(conn, site: str):
    return conn.execute(
        "SELECT * FROM mapping WHERE site = ? ORDER BY article_key", (site,)
    ).fetchall()
