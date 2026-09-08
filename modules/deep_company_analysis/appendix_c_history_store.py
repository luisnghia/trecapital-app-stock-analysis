from __future__ import annotations

"""Persistence for Appendix C V98 referential snapshots and explicit analyst re-reviews only."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from modules.deep_company_analysis import appendix_c_history as hist

DEFAULT_DB = Path("data_cache/deep_company_analysis_appendix_c_history.sqlite")


def _connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS appendix_c_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        company_name TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        payload_json TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS appendix_c_re_reviews (
        re_review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        company_name TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        scope TEXT NOT NULL,
        analyst_note TEXT NOT NULL DEFAULT ''
    )""")
    conn.commit()
    return conn


def create_snapshot(ticker: str, company_name: str, payload: Mapping[str, Any], db_path: str | Path = DEFAULT_DB) -> int:
    clean = dict(payload)
    errors = hist.validate_snapshot_payload(clean)
    if errors:
        raise ValueError("; ".join(errors))
    created_at = datetime.now(timezone.utc).isoformat()
    fingerprint = hist.snapshot_fingerprint(clean)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO appendix_c_snapshots(ticker, company_name, created_at, fingerprint, payload_json) VALUES(?,?,?,?,?)",
            (str(ticker or '').strip().upper(), str(company_name or '').strip(), created_at, fingerprint,
             json.dumps(clean, ensure_ascii=False, sort_keys=True)),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_snapshots(ticker: str, company_name: str = "", db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT snapshot_id, ticker, company_name, created_at, fingerprint, payload_json FROM appendix_c_snapshots WHERE ticker=? AND company_name=? ORDER BY snapshot_id",
            (str(ticker or '').strip().upper(), str(company_name or '').strip()),
        ).fetchall()
    return [{**dict(row), "payload": json.loads(row["payload_json"])} for row in rows]


def add_re_review(ticker: str, company_name: str = "", note: str = "", scope: str = "Q01-Q59", db_path: str | Path = DEFAULT_DB) -> int:
    record = hist.build_re_review_record(note=note, scope=scope)
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO appendix_c_re_reviews(ticker, company_name, created_at, scope, analyst_note) VALUES(?,?,?,?,?)",
            (str(ticker or '').strip().upper(), str(company_name or '').strip(), created_at, record["scope"], record["analyst_note"]),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_re_reviews(ticker: str, company_name: str = "", db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT re_review_id, ticker, company_name, created_at, scope, analyst_note FROM appendix_c_re_reviews WHERE ticker=? AND company_name=? ORDER BY re_review_id",
            (str(ticker or '').strip().upper(), str(company_name or '').strip()),
        ).fetchall()
    return [dict(row) for row in rows]


__all__ = ["DEFAULT_DB", "add_re_review", "create_snapshot", "list_re_reviews", "list_snapshots"]
