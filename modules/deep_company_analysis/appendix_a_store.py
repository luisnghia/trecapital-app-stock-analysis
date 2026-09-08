from __future__ import annotations

"""SQLite persistence for Appendix A analyst-owned human-intelligence records and V92 snapshots."""

from copy import deepcopy
import json
import sqlite3
from pathlib import Path
from typing import Any

from .appendix_a_workspace import normalize_workspace

DEFAULT_DB_PATH = Path("data_cache/deep_company_analysis.sqlite3")
TABLE_NAME = "dca_appendix_a_workspaces"
SNAPSHOT_TABLE_NAME = "dca_appendix_a_snapshots"
SNAPSHOT_SCHEMA_VERSION = 1


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
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SNAPSHOT_TABLE_NAME} (
            snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            company_name TEXT NOT NULL DEFAULT '',
            schema_version INTEGER NOT NULL DEFAULT 1,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{SNAPSHOT_TABLE_NAME}_ticker_created ON {SNAPSHOT_TABLE_NAME} (ticker, created_at, snapshot_id)"
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


def create_appendix_a_snapshot(
    payload: dict[str, Any],
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Persist an immutable normalized workspace version without changing current state."""
    normalized = normalize_workspace(payload)
    ticker = normalized["ticker"]
    if not ticker:
        raise ValueError("ticker is required")
    with _connect(db_path) as conn:
        cursor = conn.execute(
            f"""
            INSERT INTO {SNAPSHOT_TABLE_NAME} (ticker, company_name, schema_version, payload_json, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                ticker,
                normalized["company_name"],
                SNAPSHOT_SCHEMA_VERSION,
                json.dumps(normalized, ensure_ascii=False, sort_keys=True),
            ),
        )
        snapshot_id = int(cursor.lastrowid)
        row = conn.execute(
            f"SELECT snapshot_id, ticker, company_name, schema_version, payload_json, created_at FROM {SNAPSHOT_TABLE_NAME} WHERE snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()
    return _snapshot_row(row)


def _snapshot_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        raw = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        raw = {}
    payload = normalize_workspace(raw, ticker=row["ticker"], company_name=row["company_name"])
    return {
        "snapshot_id": int(row["snapshot_id"]),
        "ticker": str(row["ticker"]),
        "company_name": str(row["company_name"] or ""),
        "schema_version": int(row["schema_version"]),
        "created_at": str(row["created_at"] or ""),
        "payload": deepcopy(payload),
    }


def load_appendix_a_snapshot(snapshot_id: int, *, db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, Any]:
    with _connect(db_path) as conn:
        row = conn.execute(
            f"SELECT snapshot_id, ticker, company_name, schema_version, payload_json, created_at FROM {SNAPSHOT_TABLE_NAME} WHERE snapshot_id = ?",
            (int(snapshot_id),),
        ).fetchone()
    return _snapshot_row(row)


def list_appendix_a_snapshots(ticker: str, *, db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    key = str(ticker or "").strip().upper()
    if not key:
        return []
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT snapshot_id, ticker, company_name, schema_version, payload_json, created_at FROM {SNAPSHOT_TABLE_NAME} WHERE ticker = ? ORDER BY created_at, snapshot_id",
            (key,),
        ).fetchall()
    return [_snapshot_row(row) for row in rows]


__all__ = [
    "DEFAULT_DB_PATH", "SNAPSHOT_SCHEMA_VERSION", "SNAPSHOT_TABLE_NAME", "TABLE_NAME",
    "create_appendix_a_snapshot", "delete_appendix_a_workspace", "list_appendix_a_snapshots",
    "load_appendix_a_snapshot", "load_appendix_a_workspace", "save_appendix_a_workspace",
]
