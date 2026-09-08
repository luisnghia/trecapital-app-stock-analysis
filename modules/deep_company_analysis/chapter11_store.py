from __future__ import annotations

"""Persistent analyst-owned Chapter 11 M&A workspace.

Only Chapter 11 analyst state, explicitly promoted evidence, and analyst-authored M&A synthesis
are persisted. Canonical financial/market data remain read-only in their existing SSOT and are
never copied into this database.
"""

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import sqlite3

import modules.deep_company_analysis.chapter11 as ch11

APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter11.db"
SCHEMA_VERSION = 2


def _safe_ticker(value: str) -> str:
    return "".join(c for c in str(value).upper().strip() if c.isalnum() or c in {".", "-"})[:20]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _preserve_analyst_extensions(normalized: dict[str, Any], source: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(source, dict) and isinstance(source.get("ma_synthesis"), dict):
        normalized["ma_synthesis"] = json.loads(json.dumps(source["ma_synthesis"], ensure_ascii=False, default=str))
    return normalized


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chapter11_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                research_status TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


def research_status(payload: dict[str, Any]) -> str:
    p = ch11.normalize_payload(payload or {})
    statuses = p.get("question_status", {})
    answered = sum(statuses.get(q) == "Answered" for q in ch11.QUESTION_KEYS)
    partial = sum(statuses.get(q) == "Partial" for q in ch11.QUESTION_KEYS)
    unknown = sum(statuses.get(q) == "Unknown" for q in ch11.QUESTION_KEYS)
    na = sum(statuses.get(q) == "N/A" for q in ch11.QUESTION_KEYS)
    return f"{answered}/{len(ch11.QUESTION_KEYS)} Answered | {partial} Partial | {unknown} Unknown | {na} N/A"


def _normalize_stored(stored: dict[str, Any], ticker: str, company_name: str = "") -> dict[str, Any]:
    p = ch11.normalize_payload(stored, ticker, company_name)
    return _preserve_analyst_extensions(p, stored)


def load_record(ticker: str, company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT company_name, payload_json FROM chapter11_current WHERE ticker=?",
            (safe,),
        ).fetchone()
    if not row:
        return ch11.empty_payload(safe, company_name)
    try:
        stored = json.loads(row["payload_json"] or "{}")
    except Exception:
        stored = {}
    return _normalize_stored(stored, safe, company_name or str(row["company_name"] or ""))


def save_record(ticker: str, payload: dict[str, Any], company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    p = ch11.normalize_payload(payload or {}, safe, company_name)
    p = _preserve_analyst_extensions(p, payload)
    p["ticker"] = safe
    p["company_name"] = company_name or str(p.get("company_name") or "")
    now = _now()
    init_db()
    with _connect() as conn:
        old = conn.execute("SELECT created_at FROM chapter11_current WHERE ticker=?", (safe,)).fetchone()
        created = str(old["created_at"]) if old else now
        conn.execute("""
            INSERT INTO chapter11_current(
                ticker, company_name, payload_json, research_status, schema_version, created_at, updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name=excluded.company_name,
                payload_json=excluded.payload_json,
                research_status=excluded.research_status,
                schema_version=excluded.schema_version,
                updated_at=excluded.updated_at
        """, (
            safe,
            p["company_name"],
            json.dumps(p, ensure_ascii=False, default=str),
            research_status(p),
            SCHEMA_VERSION,
            created,
            now,
        ))
    return p


def promoted_candidate_ids(payload: dict[str, Any] | None) -> set[str]:
    p = ch11.normalize_payload(payload or {})
    return {
        str(row.get("Candidate ID"))
        for row in p.get("evidence", [])
        if isinstance(row, dict) and row.get("Candidate ID")
    }


__all__ = [
    "DB_PATH", "SCHEMA_VERSION", "init_db", "load_record", "save_record",
    "research_status", "promoted_candidate_ids",
]
