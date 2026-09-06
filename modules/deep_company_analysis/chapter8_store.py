from __future__ import annotations

"""Persistent analyst-owned Chapter 8 workspace and snapshots.

The store deliberately persists only the analyst workspace. Research candidates remain
candidates until the analyst promotes them. Saving never creates a management score,
changes MOS/Research Gate, or emits BUY/HOLD/SELL.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sqlite3

import modules.deep_company_analysis.chapter8 as ch8


APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter8.db"
SCHEMA_VERSION = 1


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chapter8_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                research_status TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter8_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                research_status TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chapter8_snapshots_ticker
            ON chapter8_snapshots(ticker, id DESC);
            """
        )


def _research_status(payload: dict[str, Any]) -> str:
    statuses = payload.get("question_status") or {}
    answered = sum(1 for q in ch8.QUESTION_KEYS if statuses.get(q) == "Answered")
    partial = sum(1 for q in ch8.QUESTION_KEYS if statuses.get(q) == "Partial")
    return f"{answered}/{len(ch8.QUESTION_KEYS)} Answered | {partial} Partial"


def load_record(ticker: str, company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT company_name, payload_json FROM chapter8_current WHERE ticker = ?",
            (safe,),
        ).fetchone()
    if not row:
        return ch8.empty_payload(safe, company_name)
    try:
        stored = json.loads(row["payload_json"] or "{}")
    except Exception:
        stored = {}
    return ch8.normalize_payload(stored, safe, company_name or str(row["company_name"] or ""))


def save_record(ticker: str, payload: dict[str, Any], company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    normalized = ch8.normalize_payload(payload or {}, safe, company_name)
    normalized["ticker"] = safe
    normalized["company_name"] = company_name or str(normalized.get("company_name") or "")
    normalized["schema_version"] = SCHEMA_VERSION
    now = _now()
    init_db()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT created_at FROM chapter8_current WHERE ticker = ?", (safe,)
        ).fetchone()
        created_at = str(existing["created_at"]) if existing else now
        conn.execute(
            """
            INSERT INTO chapter8_current
                (ticker, company_name, payload_json, research_status, schema_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name = excluded.company_name,
                payload_json = excluded.payload_json,
                research_status = excluded.research_status,
                schema_version = excluded.schema_version,
                updated_at = excluded.updated_at
            """,
            (
                safe,
                normalized["company_name"],
                json.dumps(normalized, ensure_ascii=False, default=str),
                _research_status(normalized),
                SCHEMA_VERSION,
                created_at,
                now,
            ),
        )
    return normalized


def create_snapshot(ticker: str, payload: dict[str, Any] | None = None) -> int:
    safe = _safe_ticker(ticker)
    source = payload if isinstance(payload, dict) else load_record(safe)
    record = save_record(safe, source, str(source.get("company_name") or ""))
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chapter8_snapshots
                (ticker, payload_json, research_status, schema_version, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                safe,
                json.dumps(record, ensure_ascii=False, default=str),
                _research_status(record),
                SCHEMA_VERSION,
                _now(),
            ),
        )
        return int(cur.lastrowid)


def list_snapshots(ticker: str, limit: int = 20) -> list[dict[str, Any]]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, ticker, research_status, schema_version, created_at
            FROM chapter8_snapshots
            WHERE ticker = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe, max(1, int(limit))),
        ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "SCHEMA_VERSION",
    "DB_PATH",
    "init_db",
    "load_record",
    "save_record",
    "create_snapshot",
    "list_snapshots",
]
