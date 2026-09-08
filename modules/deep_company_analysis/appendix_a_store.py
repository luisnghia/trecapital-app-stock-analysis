from __future__ import annotations

"""SQLite persistence for Appendix A V91 analyst-owned human intelligence records."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from .appendix_a_workspace import normalize_workspace

DEFAULT_DB_PATH = Path("data_cache/deep_company_analysis.sqlite3")
TABLE_NAME = "dca_appendix_a_workspaces"


def _connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            ticker TEXT PRIMARY KEY,
            company_name TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return conn


def save_appendix_a_workspace(
    payload: dict[str, Any],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    normalized = normalize_workspace(payload)
    ticker = normalized["ticker"]
    if not ticker:
        raise ValueError("ticker is required")
    with _connect(db_path) as conn:
        conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (ticker, company_name, payload_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name=excluded.company_name,
                payload_json=excluded.payload_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (ticker, normalized["company_name"], json.dumps(normalized, ensure_ascii=False, sort_keys=True)),
        )
    return normalized


def load_appendix_a_workspace(
    ticker: str,
    *,
    company_name: str = "",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    key = str(ticker or "").strip().upper()
    if not key:
        return normalize_workspace({}, ticker="", company_name=company_name)
    with _connect(db_path) as conn:
        row = conn.execute(f"SELECT payload_json FROM {TABLE_NAME} WHERE ticker = ?", (key,)).fetchone()
    if row is None:
        return normalize_workspace({}, ticker=key, company_name=company_name)
    try:
        raw = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        raw = {}
    return normalize_workspace(raw, ticker=key, company_name=company_name or raw.get("company_name", ""))


def delete_appendix_a_workspace(ticker: str, *, db_path: str | Path = DEFAULT_DB_PATH) -> bool:
    key = str(ticker or "").strip().upper()
    if not key:
        return False
    with _connect(db_path) as conn:
        cursor = conn.execute(f"DELETE FROM {TABLE_NAME} WHERE ticker = ?", (key,))
    return bool(cursor.rowcount)


__all__ = ["DEFAULT_DB_PATH", "TABLE_NAME", "delete_appendix_a_workspace", "load_appendix_a_workspace", "save_appendix_a_workspace"]
