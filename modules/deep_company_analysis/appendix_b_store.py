from __future__ import annotations

"""SQLite persistence for Appendix B V94 management interview workspace.

Only normalized analyst-owned interview state is persisted. DCA references are identifiers only;
no chapter state, financial SSOT, valuation, MOS, Research Gate or investment signal is copied.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from modules.deep_company_analysis.appendix_b_workspace import normalize_research_gap, normalize_session


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


__all__ = ["init_store", "list_research_gaps", "list_sessions", "load_session", "save_research_gap", "save_session"]
