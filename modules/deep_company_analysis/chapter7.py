from __future__ import annotations

"""Michael Shearn Chapter 7 — Management Background & Classification (Who Are They?).

Phase 7A is a source-locked analyst workspace for Q33-Q38 from *The Investment Checklist*.
It organizes management background, classification, compensation/ownership and insider evidence.
It never creates a management quality score, never auto-classifies Lion/Hyena, never turns insider
activity into BUY/SELL, and never fabricates TTM for event/as-of management data.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import sqlite3

import pandas as pd


APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter7.db"
SCHEMA_VERSION = 3

QUESTION_KEYS = ("Q33", "Q34", "Q35", "Q36", "Q37", "Q38")
QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
MANAGER_CLASSIFICATION_OPTIONS = ("Unknown", "OO1", "OO2", "OO3", "LT1", "LT2", "HH1", "HH2", "Mixed")
LION_HYENA_OPTIONS = ("Unknown", "Lion", "Mixed", "Hyena")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")

# Source-locked continuum from Shearn. These are research categories, not automatic quality labels.
MANAGER_CLASSIFICATION_DEFINITIONS: dict[str, str] = {
    "OO1": "Owner-operator type 1 — founder/owner with evidence of long-term stewardship and stakeholder orientation.",
    "OO2": "Owner-operator type 2 — owner-operator with mixed stakeholder and personal-interest evidence.",
    "OO3": "Owner-operator type 3 — owner-operator with evidence the business may be run materially for personal benefit.",
    "LT1": "Long-tenured type 1 — rose from inside the company.",
    "LT2": "Long-tenured type 2 — joined from outside but has meaningful same-industry / same-customer experience.",
    "HH1": "Hired hand type 1 — outside manager from a related industry.",
    "HH2": "Hired hand type 2 — outside manager from an unrelated industry / limited customer-base experience.",
}

# Exact seven conceptual dimensions in Table 7.1, represented as evidence prompts rather than a score.
LION_HYENA_DIMENSIONS: tuple[tuple[str, str, str], ...] = (
    ("Ethics", "Committed to ethical and moral values", "Little interest in ethics and morals"),
    ("Time horizon", "Long-term focus", "Short-term focus"),
    ("Shortcuts", "Does not take shortcuts", "Wants to win the game / outcome over process"),
    ("Learning", "Thirsty for knowledge", "Little interest in learning"),
    ("Partnership", "Supports partners and alliances", "Opportunistic / mostly goes alone"),
    ("Employees", "Treats employees as partners", "Treats employees mainly as expenses"),
    ("Persistence", "Admires perseverance", "Admires tactics/resourcefulness/guile"),
)

MANAGEMENT_PROFILE_COLUMNS = [
    "Manager ID",
    "Manager",
    "Current Role",
    "Founder?",
    "Family-controlled relationship",
    "Joined Company",
    "Started Current Role",
    "Prior Company",
    "Prior Industry",
    "Same Industry",
    "Same Customer Base",
    "Prior Functional Background",
    "Actual Ownership (%)",
    "Suggested Classification",
    "Analyst Classification",
    "Supporting Evidence",
    "Counter-Evidence",
    "Analyst Rationale",
    "Confidence",
]

OUTSIDE_TRANSITION_COLUMNS = [
    "Manager ID",
    "Manager",
    "Entry Date",
    "Role Start Date",
    "Internal / External",
    "Previous Company",
    "Previous Industry",
    "Industry Overlap",
    "Customer Overlap",
    "Organization-specific Knowledge",
    "Support-network Transferability",
    "First Major Action",
    "Days to First Major Action",
    "Employee Consultation Evidence",
    "Customer-learning Evidence",
    "Culture-learning Evidence",
    "Cost-cutting Actions",
    "Growth-building Actions",
    "Key Executive Departures",
    "Strategy Changes",
    "Early Operating Outcomes",
    "Supporting Evidence",
    "Counter-Evidence",
    "Analyst Conclusion",
]

LION_HYENA_COLUMNS = [
    "Manager ID",
    "Manager",
    "Dimension",
    "Lion Definition",
    "Hyena Definition",
    "Lion Evidence",
    "Hyena Evidence",
    "Source",
    "Evidence Date",
    "Evidence Direction",
    "Analyst Note",
]

CAREER_TIMELINE_COLUMNS = [
    "Manager ID",
    "Manager",
    "From",
    "To",
    "Date Precision",
    "Company",
    "Role",
    "Industry",
    "Functional Area",
    "Customer-facing",
    "Operating Exposure",
    "Employee Exposure",
    "Corporate-suite Exposure",
    "Promotion Type",
    "Previous Company Culture",
    "Major Responsibility",
    "Observed Result",
    "Source",
    "Career Gap?",
    "Gap Explanation",
]

COMPENSATION_HISTORY_COLUMNS = [
    "Year",
    "Manager ID",
    "Manager",
    "Role",
    "Compensation Scope",
    "Salary (tỷ)",
    "Cash Bonus (tỷ)",
    "Stock Awards (tỷ)",
    "Options Granted",
    "RSU / Restricted Stock",
    "ESOP Benefit",
    "Pension / Other (tỷ)",
    "Severance (tỷ)",
    "Total Compensation (tỷ)",
    "Performance Metric",
    "Measurement Horizon",
    "Target",
    "Actual",
    "Target Met",
    "Payout Despite Missing Target",
    "Guaranteed Component",
    "Compensation Consultant",
    "Source",
    "Data Quality Flags",
    "Analyst Note",
]

OWNERSHIP_HISTORY_COLUMNS = [
    "As-of Date",
    "Manager ID",
    "Manager",
    "Actual Shares",
    "Ownership (%)",
    "Options",
    "RSU / Restricted",
    "Unvested Awards",
    "Ownership Origin",
    "Shares Added",
    "Shares Reduced",
    "Ownership Requirement",
    "Requirement Met",
    "Source",
    "Analyst Note",
]

COMPENSATION_DESIGN_COLUMNS = [
    "Manager ID",
    "Manager",
    "Component",
    "Metric Rewarded",
    "Horizon",
    "Manager Controllability",
    "Downside / Penalty",
    "Clawback",
    "Alignment Evidence",
    "Counter-Evidence",
    "Source",
    "Analyst Assessment",
]

INSIDER_TRANSACTION_COLUMNS = [
    "Transaction Date",
    "Transaction Date From",
    "Transaction Date To",
    "Disclosure Date",
    "Manager ID",
    "Insider",
    "Role",
    "Transaction",
    "Transaction Type",
    "Registered Shares",
    "Executed Shares",
    "Shares",
    "Price",
    "Transaction Value (tỷ)",
    "Ownership Before",
    "Ownership After",
    "Change in Ownership (%)",
    "% of Existing Ownership",
    "Funding Source",
    "Stated Reason",
    "Discretionary Transaction",
    "Source",
    "Analyst Materiality",
    "Analyst Interpretation",
]

EVIDENCE_COLUMNS = [
    "Question",
    "Manager ID",
    "Manager",
    "Claim",
    "Evidence Type",
    "Source Grade",
    "Source Title",
    "Source URL / File",
    "Source Date",
    "As-of Date",
    "Evidence Text / Reference",
    "Direction",
    "Status",
    "Data Origin",
    "Analyst Note",
]

RESEARCH_GAP_COLUMNS = [
    "Question",
    "Manager ID",
    "Manager",
    "Research Gap",
    "Materiality",
    "Next Action",
    "Status",
    "Analyst Note",
]

EVENT_COLUMNS = [
    "Event Date",
    "Publication Date",
    "Effective Date",
    "As-of Date",
    "Manager ID",
    "Manager",
    "Event Type",
    "Event",
    "Questions to Review",
    "Source",
    "Review Status",
    "Analyst Note",
]

CHILD_TABLES: dict[str, str] = {
    "management_profiles": "chapter7_management_profiles",
    "outside_transitions": "chapter7_outside_transitions",
    "lion_hyena_matrix": "chapter7_lion_hyena_matrix",
    "career_timeline": "chapter7_career_timeline",
    "compensation_history": "chapter7_compensation_history",
    "ownership_history": "chapter7_ownership_history",
    "compensation_design": "chapter7_compensation_design",
    "insider_transactions": "chapter7_insider_transactions",
    "evidence_matrix": "chapter7_evidence",
    "research_gaps_table": "chapter7_research_gaps",
    "management_events": "chapter7_events",
    "chapter7_final_checklist": "chapter7_final_checklist",
    "chapter7_residual_unknowns": "chapter7_residual_unknowns",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    child_sql = "\n".join(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            row_json TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_{table_name}_ticker ON {table_name}(ticker);
        """
        for table_name in CHILD_TABLES.values()
    )
    with _connect() as conn:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS chapter7_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{{}}',
                research_status TEXT NOT NULL DEFAULT 'not_understood',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chapter7_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                research_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chapter7_snapshots_ticker ON chapter7_snapshots(ticker);
            {child_sql}
            """
        )


def default_lion_hyena_rows() -> list[dict[str, Any]]:
    return [
        {
            "Manager ID": "",
            "Manager": "",
            "Dimension": dimension,
            "Lion Definition": lion,
            "Hyena Definition": hyena,
            "Lion Evidence": "",
            "Hyena Evidence": "",
            "Source": "",
            "Evidence Date": "",
            "Evidence Direction": "Unknown",
            "Analyst Note": "",
        }
        for dimension, lion, hyena in LION_HYENA_DIMENSIONS
    ]


def empty_payload(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": _safe_ticker(ticker),
        "company_name": company_name or "",
        "question_status": {q: "Unknown" for q in QUESTION_KEYS},
        "q33": {
            "primary_manager": "",
            "analyst_classification": "Unknown",
            "execution_uncertainty": "Unknown",
            "management_business_fit": "Unknown",
            "conclusion": "",
        },
        "q34": {
            "applicable": "Unknown",
            "learn_before_change": "Unknown",
            "organization_specific_knowledge": "Unknown",
            "culture_fit": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q35": {
            "overall_classification": "Unknown",
            "conclusion": "",
        },
        "q36": {
            "top5_reviewed": "Unknown",
            "career_pattern_summary": "",
            "critical_gaps": "",
            "conclusion": "",
        },
        "q37": {
            "compensation_alignment": "Unknown",
            "ownership_alignment": "Unknown",
            "actual_vs_potential_ownership_reviewed": "Unknown",
            "conclusion": "",
        },
        "q38": {
            "insider_behavior": "Unknown",
            "material_transactions_reviewed": "Unknown",
            "conclusion": "",
        },
        "management_profiles": [],
        "outside_transitions": [],
        "lion_hyena_matrix": default_lion_hyena_rows(),
        "career_timeline": [],
        "compensation_history": [],
        "ownership_history": [],
        "compensation_design": [],
        "insider_transactions": [],
        "evidence_matrix": [],
        "research_gaps_table": [],
        "management_events": [],
        "final_management_classification": "Unknown",
        "execution_uncertainty": "Unknown",
        "management_business_fit": "Unknown",
        "ownership_alignment": "Unknown",
        "compensation_alignment": "Unknown",
        "insider_behavior": "Unknown",
        "critical_strengths": "",
        "critical_concerns": "",
        "critical_unknowns": "",
        "evidence_that_would_change_view": "",
        "analyst_summary": "",
        "phase7a_source_lock_note": "Event/as-of management data; no fabricated TTM. AI/Data is evidence support only; analyst owns classifications and conclusions.",
        "phase7b_bridge_note": "Structured official disclosure bridge uses Raw → Candidate → Analyst Apply; registered != executed; actual shares != options/RSU/ESOP; no auto management conclusion.",
        "phase7c_research_note": "Web/PDF/HTML Research Assistant produces candidate evidence and research gaps only; analyst must explicitly Promote; no auto classification, Management Quality conclusion or insider trading signal.",
        "phase7d_closure_note": "Final source closure verifies Q33-Q38 research completeness only; no Management Quality score, MOS, investment Research Gate or BUY/HOLD/SELL.",
        "chapter7_final_checklist": [],
        "chapter7_residual_unknowns": [],
        "chapter7_complete_confirmed": False,
        "chapter7_completion_note": "",
        "chapter7_completion_as_of": "",
        "chapter7_completion_version": 0,
        "chapter7_last_management_review_at": "",
        "chapter7_last_management_review_result": "",
        "chapter7_closure_source_snapshot": [],
        "chapter7_closure_conflict_snapshot": [],
        "chapter7_closure_review_snapshot": [],
    }


def _merge_dict(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _research_status(payload: dict[str, Any]) -> str:
    statuses = list((payload.get("question_status") or {}).values())
    answered = sum(1 for value in statuses if value in {"Answered", "N/A"})
    partial = sum(1 for value in statuses if value == "Partial")
    if answered == len(QUESTION_KEYS):
        return "understood"
    if answered or partial:
        return "partial"
    return "not_understood"


def _read_child_rows(conn: sqlite3.Connection, table_name: str, ticker: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT row_json FROM {table_name} WHERE ticker = ? ORDER BY position, id", (ticker,)
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            value = json.loads(row["row_json"] or "{}")
        except Exception:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def _replace_child_rows(conn: sqlite3.Connection, table_name: str, ticker: str, rows: Any, timestamp: str) -> None:
    conn.execute(f"DELETE FROM {table_name} WHERE ticker = ?", (ticker,))
    for position, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        conn.execute(
            f"INSERT INTO {table_name} (ticker, position, row_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (ticker, position, json.dumps(row, ensure_ascii=False, default=str), timestamp, timestamp),
        )


def load_record(ticker: str) -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT company_name, payload_json FROM chapter7_current WHERE ticker = ?", (safe,)
        ).fetchone()
        if row is None:
            return empty_payload(safe)
        try:
            stored = json.loads(row["payload_json"] or "{}")
        except Exception:
            stored = {}
        payload = _merge_dict(empty_payload(safe, str(row["company_name"] or "")), stored)
        for payload_key, table_name in CHILD_TABLES.items():
            rows = _read_child_rows(conn, table_name, safe)
            if payload_key == "lion_hyena_matrix" and not rows:
                rows = default_lion_hyena_rows()
            payload[payload_key] = rows
        payload["schema_version"] = SCHEMA_VERSION
        return payload


def save_record(ticker: str, payload: dict[str, Any], company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    init_db()
    now = _now()
    normalized = _merge_dict(empty_payload(safe, company_name), payload or {})
    normalized["ticker"] = safe
    normalized["company_name"] = company_name or str(normalized.get("company_name") or "")
    normalized["schema_version"] = SCHEMA_VERSION
    for q in QUESTION_KEYS:
        status = str((normalized.get("question_status") or {}).get(q) or "Unknown")
        normalized["question_status"][q] = status if status in QUESTION_STATUS_OPTIONS else "Unknown"
    for key in ("final_management_classification",):
        value = str(normalized.get(key) or "Unknown")
        normalized[key] = value if value in MANAGER_CLASSIFICATION_OPTIONS else "Unknown"
    body = deepcopy(normalized)
    for payload_key in CHILD_TABLES:
        body.pop(payload_key, None)
    status = _research_status(normalized)
    with _connect() as conn:
        existing = conn.execute("SELECT created_at FROM chapter7_current WHERE ticker = ?", (safe,)).fetchone()
        created_at = str(existing["created_at"]) if existing else now
        conn.execute(
            """
            INSERT INTO chapter7_current
                (ticker, company_name, payload_json, research_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name = excluded.company_name,
                payload_json = excluded.payload_json,
                research_status = excluded.research_status,
                updated_at = excluded.updated_at
            """,
            (safe, normalized["company_name"], json.dumps(body, ensure_ascii=False, default=str), status, created_at, now),
        )
        for payload_key, table_name in CHILD_TABLES.items():
            _replace_child_rows(conn, table_name, safe, normalized.get(payload_key), now)
    return normalized


def create_snapshot(ticker: str, payload: dict[str, Any] | None = None) -> int:
    safe = _safe_ticker(ticker)
    source = payload or load_record(safe)
    record = save_record(safe, source, str(source.get("company_name") or ""))
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO chapter7_snapshots (ticker, payload_json, research_status, created_at) VALUES (?, ?, ?, ?)",
            (safe, json.dumps(record, ensure_ascii=False, default=str), _research_status(record), _now()),
        )
        return int(cur.lastrowid)


def list_snapshots(ticker: str, limit: int = 20) -> list[dict[str, Any]]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, ticker, research_status, created_at FROM chapter7_snapshots WHERE ticker = ? ORDER BY id DESC LIMIT ?",
            (safe, max(1, int(limit))),
        ).fetchall()
        return [dict(row) for row in rows]


def _parse_date(value: Any) -> pd.Timestamp | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        out = pd.to_datetime(value, errors="coerce", dayfirst=True)
        if pd.isna(out):
            return None
        return pd.Timestamp(out)
    except Exception:
        return None


def years_between(start: Any, end: Any | None = None) -> float | None:
    start_ts = _parse_date(start)
    end_ts = _parse_date(end) if end not in {None, ""} else pd.Timestamp.today().normalize()
    if start_ts is None or end_ts is None or end_ts < start_ts:
        return None
    return round((end_ts - start_ts).days / 365.25, 1)


def build_management_overview(rows: Any, as_of_date: Any | None = None) -> pd.DataFrame:
    """Derived tenure summary only; it never classifies a manager."""
    if isinstance(rows, pd.DataFrame):
        source = rows.to_dict("records")
    elif isinstance(rows, list):
        source = [dict(r) for r in rows if isinstance(r, dict)]
    else:
        source = []
    out: list[dict[str, Any]] = []
    for row in source:
        out.append(
            {
                "Manager ID": row.get("Manager ID"),
                "Manager": row.get("Manager"),
                "Current Role": row.get("Current Role"),
                "Company Tenure (years)": years_between(row.get("Joined Company"), as_of_date),
                "Current Role Tenure (years)": years_between(row.get("Started Current Role"), as_of_date),
                "Actual Ownership (%)": row.get("Actual Ownership (%)"),
                "Suggested Classification": row.get("Suggested Classification") or "Unknown",
                "Analyst Classification": row.get("Analyst Classification") or "Unknown",
                "Confidence": row.get("Confidence") or "Unknown",
            }
        )
    return pd.DataFrame(out)


def research_gap_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    statuses = payload.get("question_status") or {}
    if str(statuses.get("Q33") or "Unknown") == "Answered" and not payload.get("management_profiles"):
        warnings.append("Q33 đã Answered nhưng chưa có Management Profile / classification evidence.")
    if str(statuses.get("Q34") or "Unknown") == "Answered" and not payload.get("outside_transitions"):
        warnings.append("Q34 đã Answered nhưng chưa có Outside Management Transition evidence.")
    if str(statuses.get("Q35") or "Unknown") == "Answered":
        matrix = payload.get("lion_hyena_matrix") or []
        dimensions = {str(row.get("Dimension") or "") for row in matrix if isinstance(row, dict)}
        expected = {d for d, _, _ in LION_HYENA_DIMENSIONS}
        if dimensions != expected:
            warnings.append("Q35 phải review đủ đúng 7 dimensions của Table 7.1; không dùng numerical score.")
    if str(statuses.get("Q36") or "Unknown") == "Answered" and not payload.get("career_timeline"):
        warnings.append("Q36 đã Answered nhưng Career Timeline còn trống.")
    if str(statuses.get("Q37") or "Unknown") == "Answered":
        if not payload.get("compensation_history") or not payload.get("ownership_history"):
            warnings.append("Q37 cần review cả Compensation History và Ownership History; actual shares phải tách khỏi options/RSU/ESOP.")
    if str(statuses.get("Q38") or "Unknown") == "Answered" and not payload.get("insider_transactions"):
        warnings.append("Q38 đã Answered nhưng Insider Transaction Register còn trống; nếu không có dữ liệu nên dùng N/A có lý do.")
    for row in payload.get("management_profiles") or []:
        if not isinstance(row, dict):
            continue
        suggested = str(row.get("Suggested Classification") or "Unknown")
        analyst = str(row.get("Analyst Classification") or "Unknown")
        if suggested not in MANAGER_CLASSIFICATION_OPTIONS:
            warnings.append("Suggested Classification có giá trị ngoài taxonomy source-lock OO1-OO3/LT1-LT2/HH1-HH2.")
        if analyst not in MANAGER_CLASSIFICATION_OPTIONS:
            warnings.append("Analyst Classification có giá trị ngoài taxonomy source-lock OO1-OO3/LT1-LT2/HH1-HH2.")
    return warnings


__all__ = [
    "SCHEMA_VERSION",
    "QUESTION_KEYS",
    "QUESTION_STATUS_OPTIONS",
    "CONFIDENCE_OPTIONS",
    "MANAGER_CLASSIFICATION_OPTIONS",
    "LION_HYENA_OPTIONS",
    "MANAGER_CLASSIFICATION_DEFINITIONS",
    "LION_HYENA_DIMENSIONS",
    "MANAGEMENT_PROFILE_COLUMNS",
    "OUTSIDE_TRANSITION_COLUMNS",
    "LION_HYENA_COLUMNS",
    "CAREER_TIMELINE_COLUMNS",
    "COMPENSATION_HISTORY_COLUMNS",
    "OWNERSHIP_HISTORY_COLUMNS",
    "COMPENSATION_DESIGN_COLUMNS",
    "INSIDER_TRANSACTION_COLUMNS",
    "EVIDENCE_COLUMNS",
    "RESEARCH_GAP_COLUMNS",
    "EVENT_COLUMNS",
    "default_lion_hyena_rows",
    "empty_payload",
    "init_db",
    "load_record",
    "save_record",
    "create_snapshot",
    "list_snapshots",
    "years_between",
    "build_management_overview",
    "research_gap_warnings",
]
