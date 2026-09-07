from __future__ import annotations

"""Persistence for the Phase 9J analyst-owned management synthesis workspace.

The store is intentionally separate from Chapters 7, 8 and 9 source stores. It saves only the
analyst's cross-chapter synthesis plus source fingerprints/counts. It never edits source research,
manager identity, question status, confidence, valuation, MOS, investment Research Gate, or signals.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import sqlite3

from modules.deep_company_analysis.chapter9_synthesis_workspace import normalize_synthesis_workspace


APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_management_synthesis.db"
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
            CREATE TABLE IF NOT EXISTS management_synthesis_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                workspace_status TEXT NOT NULL DEFAULT 'Draft',
                source_fingerprint TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS management_synthesis_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                workspace_status TEXT NOT NULL DEFAULT 'Draft',
                source_fingerprint TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_management_synthesis_snapshots_ticker
            ON management_synthesis_snapshots(ticker, id DESC);
            """
        )


def load_workspace(ticker: str, company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT company_name, payload_json FROM management_synthesis_current WHERE ticker = ?",
            (safe,),
        ).fetchone()
    if not row:
        return normalize_synthesis_workspace({}, safe, company_name)
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    return normalize_synthesis_workspace(payload, safe, company_name or str(row["company_name"] or ""))


def save_workspace(ticker: str, workspace: dict[str, Any], company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    normalized = normalize_synthesis_workspace(workspace or {}, safe, company_name)
    normalized["ticker"] = safe
    normalized["company_name"] = company_name or str(normalized.get("company_name") or "")
    normalized["schema_version"] = SCHEMA_VERSION
    now = _now()
    init_db()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT created_at FROM management_synthesis_current WHERE ticker = ?",
            (safe,),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing else now
        conn.execute(
            """
            INSERT INTO management_synthesis_current
                (ticker, company_name, workspace_status, source_fingerprint, payload_json,
                 schema_version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name = excluded.company_name,
                workspace_status = excluded.workspace_status,
                source_fingerprint = excluded.source_fingerprint,
                payload_json = excluded.payload_json,
                schema_version = excluded.schema_version,
                updated_at = excluded.updated_at
            """,
            (
                safe,
                normalized["company_name"],
                normalized["workspace_status"],
                str(normalized.get("source_fingerprint") or ""),
                json.dumps(normalized, ensure_ascii=False, default=str),
                SCHEMA_VERSION,
                created_at,
                now,
            ),
        )
    return normalized


def create_snapshot(ticker: str, workspace: dict[str, Any] | None = None) -> int:
    safe = _safe_ticker(ticker)
    source = workspace if isinstance(workspace, dict) else load_workspace(safe)
    normalized = save_workspace(safe, source, str(source.get("company_name") or ""))
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO management_synthesis_snapshots
                (ticker, workspace_status, source_fingerprint, payload_json, schema_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                safe,
                normalized["workspace_status"],
                str(normalized.get("source_fingerprint") or ""),
                json.dumps(normalized, ensure_ascii=False, default=str),
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
            SELECT id, ticker, workspace_status, source_fingerprint, schema_version, created_at
            FROM management_synthesis_snapshots
            WHERE ticker = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe, max(1, int(limit))),
        ).fetchall()
    return [dict(row) for row in rows]


def load_snapshot(snapshot_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT ticker, payload_json FROM management_synthesis_snapshots WHERE id = ?",
            (int(snapshot_id),),
        ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    return normalize_synthesis_workspace(payload, str(row["ticker"] or ""))


__all__ = [
    "DB_PATH",
    "SCHEMA_VERSION",
    "create_snapshot",
    "init_db",
    "list_snapshots",
    "load_snapshot",
    "load_workspace",
    "save_workspace",
]
