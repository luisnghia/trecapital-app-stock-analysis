from __future__ import annotations

"""Persistent analyst-owned Chapter 11 M&A workspace and immutable snapshot history.

Only Chapter 11 analyst state, explicitly promoted evidence, analyst-authored M&A synthesis and
immutable analyst snapshots are persisted. Canonical financial/market data remain read-only in
their existing SSOT and are never copied into this database.
"""

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json
import sqlite3

import modules.deep_company_analysis.chapter11 as ch11

APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter11.db"
SCHEMA_VERSION = 3


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chapter11_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                research_status TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                UNIQUE(ticker, id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ch11_snapshots_ticker_created ON chapter11_snapshots(ticker, created_at)")


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


def create_snapshot(ticker: str, payload: dict[str, Any] | None = None, company_name: str = "", reason: str = "") -> dict[str, Any]:
    """Append an immutable Chapter 11 snapshot; existing snapshots are never updated in place."""
    safe = _safe_ticker(ticker)
    p = load_record(safe, company_name) if payload is None else save_record(safe, payload, company_name)
    now = _now()
    init_db()
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO chapter11_snapshots(ticker,company_name,payload_json,research_status,schema_version,created_at,reason)
            VALUES(?,?,?,?,?,?,?)
        """, (
            safe,
            str(p.get("company_name") or company_name or ""),
            json.dumps(p, ensure_ascii=False, default=str),
            research_status(p),
            SCHEMA_VERSION,
            now,
            str(reason or "").strip(),
        ))
        sid = int(cur.lastrowid)
    return {
        "snapshot_id": sid, "ticker": safe, "created_at": now, "schema_version": SCHEMA_VERSION,
        "research_status": research_status(p), "reason": str(reason or "").strip(), "payload": p,
    }


def list_snapshots(ticker: str) -> list[dict[str, Any]]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id,company_name,payload_json,research_status,schema_version,created_at,reason "
            "FROM chapter11_snapshots WHERE ticker=? ORDER BY created_at,id",
            (safe,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            stored = json.loads(row["payload_json"] or "{}")
        except Exception:
            stored = {}
        out.append({
            "snapshot_id": int(row["id"]), "ticker": safe,
            "company_name": str(row["company_name"] or ""), "created_at": str(row["created_at"] or ""),
            "schema_version": int(row["schema_version"] or 0), "research_status": str(row["research_status"] or ""),
            "reason": str(row["reason"] or ""),
            "payload": _normalize_stored(stored, safe, str(row["company_name"] or "")),
        })
    return out


def load_snapshot(ticker: str, snapshot_id: int) -> dict[str, Any] | None:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id,company_name,payload_json,research_status,schema_version,created_at,reason "
            "FROM chapter11_snapshots WHERE ticker=? AND id=?",
            (safe, int(snapshot_id)),
        ).fetchone()
    if not row:
        return None
    try:
        stored = json.loads(row["payload_json"] or "{}")
    except Exception:
        stored = {}
    return {
        "snapshot_id": int(row["id"]), "ticker": safe,
        "company_name": str(row["company_name"] or ""), "created_at": str(row["created_at"] or ""),
        "schema_version": int(row["schema_version"] or 0), "research_status": str(row["research_status"] or ""),
        "reason": str(row["reason"] or ""),
        "payload": _normalize_stored(stored, safe, str(row["company_name"] or "")),
    }


def mark_explicit_re_review(ticker: str, sections: list[str] | tuple[str, ...], note: str = "", company_name: str = "") -> dict[str, Any]:
    """Record analyst re-review metadata without changing conclusions/status/confidence automatically."""
    p = load_record(ticker, company_name)
    syn = dict(p.get("ma_synthesis") or {})
    syn["last_re_review_at"] = _now()
    syn["last_re_review_note"] = str(note or "").strip()
    syn["last_re_review_sections"] = [str(x).strip() for x in sections if str(x).strip()]
    p["ma_synthesis"] = syn
    return save_record(ticker, p, company_name)


def promoted_candidate_ids(payload: dict[str, Any] | None) -> set[str]:
    p = ch11.normalize_payload(payload or {})
    return {
        str(row.get("Candidate ID"))
        for row in p.get("evidence", [])
        if isinstance(row, dict) and row.get("Candidate ID")
    }


__all__ = [
    "DB_PATH", "SCHEMA_VERSION", "init_db", "load_record", "save_record", "research_status",
    "promoted_candidate_ids", "create_snapshot", "list_snapshots", "load_snapshot", "mark_explicit_re_review",
]
