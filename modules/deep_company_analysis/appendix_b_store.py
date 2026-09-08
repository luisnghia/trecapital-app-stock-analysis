from __future__ import annotations

"""SQLite persistence for Appendix B V94 workspace plus V95 immutable snapshots/re-review.

Only normalized analyst-owned interview state is persisted. DCA references are identifiers only;
no chapter state, financial SSOT, valuation, MOS, Research Gate or investment signal is copied.
"""

from copy import deepcopy
import json
import sqlite3
from pathlib import Path
from typing import Any

from modules.deep_company_analysis.appendix_b_history import normalize_history_payload
from modules.deep_company_analysis.appendix_b_workspace import normalize_research_gap, normalize_session

SNAPSHOT_SCHEMA_VERSION = 1


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def init_store(db_path: str | Path) -> None:
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS appendix_b_sessions (
                ticker TEXT NOT NULL,
                session_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, session_id)
            );
            CREATE TABLE IF NOT EXISTS appendix_b_research_gaps (
                ticker TEXT NOT NULL,
                gap_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (ticker, gap_id)
            );
            CREATE TABLE IF NOT EXISTS appendix_b_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                company_name TEXT NOT NULL DEFAULT '',
                schema_version INTEGER NOT NULL DEFAULT 1,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_appendix_b_snapshots_ticker_created
                ON appendix_b_snapshots(ticker, created_at, snapshot_id);
            CREATE TABLE IF NOT EXISTS appendix_b_re_reviews (
                rereview_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                scope TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_appendix_b_rereviews_ticker_created
                ON appendix_b_re_reviews(ticker, created_at, rereview_id);
            """
        )


def save_session(db_path: str | Path, session: dict[str, Any]) -> dict[str, Any]:
    data = normalize_session(session)
    if not data["ticker"] or not data["session_id"]:
        raise ValueError("ticker and session_id are required")
    init_store(db_path)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO appendix_b_sessions(ticker, session_id, payload_json)
               VALUES (?, ?, ?)
               ON CONFLICT(ticker, session_id) DO UPDATE SET
                 payload_json=excluded.payload_json,
                 updated_at=CURRENT_TIMESTAMP""",
            (data["ticker"], data["session_id"], payload),
        )
    return data


def load_session(db_path: str | Path, ticker: str, session_id: str) -> dict[str, Any] | None:
    init_store(db_path)
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT payload_json FROM appendix_b_sessions WHERE ticker=? AND session_id=?",
            (str(ticker or "").strip().upper(), str(session_id or "").strip()),
        ).fetchone()
    return normalize_session(json.loads(row["payload_json"])) if row else None


def list_sessions(db_path: str | Path, ticker: str) -> list[dict[str, Any]]:
    init_store(db_path)
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT payload_json FROM appendix_b_sessions WHERE ticker=? ORDER BY updated_at DESC, session_id",
            (str(ticker or "").strip().upper(),),
        ).fetchall()
    return [normalize_session(json.loads(row["payload_json"])) for row in rows]


def save_research_gap(db_path: str | Path, gap: dict[str, Any]) -> dict[str, Any]:
    data = normalize_research_gap(gap)
    if not data["ticker"] or not data["gap_id"]:
        raise ValueError("ticker and gap_id are required")
    init_store(db_path)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO appendix_b_research_gaps(ticker, gap_id, payload_json)
               VALUES (?, ?, ?)
               ON CONFLICT(ticker, gap_id) DO UPDATE SET
                 payload_json=excluded.payload_json,
                 updated_at=CURRENT_TIMESTAMP""",
            (data["ticker"], data["gap_id"], payload),
        )
    return data


def list_research_gaps(db_path: str | Path, ticker: str) -> list[dict[str, Any]]:
    init_store(db_path)
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT payload_json FROM appendix_b_research_gaps WHERE ticker=? ORDER BY updated_at DESC, gap_id",
            (str(ticker or "").strip().upper(),),
        ).fetchall()
    return [normalize_research_gap(json.loads(row["payload_json"])) for row in rows]


def _snapshot_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        raw = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        raw = {}
    return {
        "snapshot_id": int(row["snapshot_id"]),
        "ticker": str(row["ticker"] or ""),
        "company_name": str(row["company_name"] or ""),
        "schema_version": int(row["schema_version"]),
        "created_at": str(row["created_at"] or ""),
        "payload": deepcopy(normalize_history_payload(raw)),
    }


def create_snapshot(
    db_path: str | Path,
    ticker: str,
    sessions: list[dict[str, Any]],
    research_gaps: list[dict[str, Any]],
    company_name: str = "",
) -> dict[str, Any]:
    payload = normalize_history_payload({
        "ticker": ticker,
        "company_name": company_name,
        "sessions": sessions,
        "research_gaps": research_gaps,
    })
    if not payload["ticker"]:
        raise ValueError("ticker is required")
    init_store(db_path)
    with _connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO appendix_b_snapshots(ticker, company_name, schema_version, payload_json)
               VALUES (?, ?, ?, ?)""",
            (
                payload["ticker"], payload["company_name"], SNAPSHOT_SCHEMA_VERSION,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        row = con.execute(
            "SELECT snapshot_id,ticker,company_name,schema_version,payload_json,created_at FROM appendix_b_snapshots WHERE snapshot_id=?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _snapshot_row(row)


def load_snapshot(db_path: str | Path, snapshot_id: int) -> dict[str, Any]:
    init_store(db_path)
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT snapshot_id,ticker,company_name,schema_version,payload_json,created_at FROM appendix_b_snapshots WHERE snapshot_id=?",
            (int(snapshot_id),),
        ).fetchone()
    return _snapshot_row(row)


def list_snapshots(db_path: str | Path, ticker: str) -> list[dict[str, Any]]:
    init_store(db_path)
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT snapshot_id,ticker,company_name,schema_version,payload_json,created_at FROM appendix_b_snapshots WHERE ticker=? ORDER BY created_at,snapshot_id",
            (str(ticker or "").strip().upper(),),
        ).fetchall()
    return [_snapshot_row(row) for row in rows]


def record_re_review(db_path: str | Path, ticker: str, scope: str, note: str = "") -> dict[str, Any]:
    key = str(ticker or "").strip().upper()
    scope = str(scope or "").strip()
    note = str(note or "").strip()
    if not key or not scope:
        raise ValueError("ticker and scope are required")
    init_store(db_path)
    with _connect(db_path) as con:
        cur = con.execute(
            "INSERT INTO appendix_b_re_reviews(ticker,scope,note) VALUES(?,?,?)",
            (key, scope, note),
        )
        row = con.execute(
            "SELECT rereview_id,ticker,scope,note,created_at FROM appendix_b_re_reviews WHERE rereview_id=?",
            (int(cur.lastrowid),),
        ).fetchone()
    return dict(row)


def list_re_reviews(db_path: str | Path, ticker: str) -> list[dict[str, Any]]:
    init_store(db_path)
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT rereview_id,ticker,scope,note,created_at FROM appendix_b_re_reviews WHERE ticker=? ORDER BY created_at,rereview_id",
            (str(ticker or "").strip().upper(),),
        ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "SNAPSHOT_SCHEMA_VERSION", "create_snapshot", "init_store", "list_re_reviews", "list_research_gaps",
    "list_sessions", "list_snapshots", "load_session", "load_snapshot", "record_re_review",
    "save_research_gap", "save_session",
]
