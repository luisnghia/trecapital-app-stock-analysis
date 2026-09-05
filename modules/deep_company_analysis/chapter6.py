from __future__ import annotations

"""Michael Shearn Chapter 6 — Evaluating the Distribution of Earnings (Cash Flows).

Phase 6A is a source-locked, analyst-owned workspace for Q27–Q32 from
*The Investment Checklist*. It deliberately does not auto-classify accounting quality,
revenue recurrence, cyclicality, operating leverage, working-capital quality, or capex quality.

Canonical financial data remains owned by the Trecapital Data Layer. Quantitative bridges
(DOL, CCC, capex intensity, CFO/NI, etc.) belong to Phase 6B and may not create analyst
conclusions automatically.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import sqlite3

APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter6.db"

QUESTION_KEYS = ("Q27", "Q28", "Q29", "Q30", "Q31", "Q32")
QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
TREND_OPTIONS = ("Unknown", "Improving", "Stable", "Deteriorating", "Mixed")

# Shearn explicitly lists these reserve categories in Q27. They are research prompts,
# not allegations that a company uses or manipulates every reserve.
SHEARN_Q27_RESERVE_AREAS: tuple[tuple[str, str], ...] = (
    ("Bad debts", "Nợ xấu / phải thu khó đòi"),
    ("Sales returns", "Hàng bán bị trả lại"),
    ("Inventory obsolescence", "Giảm giá / lỗi thời hàng tồn kho"),
    ("Warranties", "Bảo hành"),
    ("Product liability", "Trách nhiệm sản phẩm"),
    ("Litigation", "Kiện tụng"),
    ("Environmental contingencies", "Nghĩa vụ môi trường tiềm tàng"),
)

ACCOUNTING_QUALITY_COLUMNS = [
    "Area", "Area (VI)", "Origin", "Policy / Estimate", "Current Treatment",
    "Conservative / Liberal Indicator", "3Y Pattern", "Provision / Estimate",
    "Actual Outcome / Charge-off", "Supporting Evidence", "Counter-Evidence",
    "Analyst Assessment", "Analyst Note",
]

RECURRING_REVENUE_COLUMNS = [
    "Revenue Stream", "Recurring / One-off / Mixed", "Mechanism", "Contract / Reorder Basis",
    "Typical Duration", "Revenue Share", "Renewal / Retention Evidence", "At-Risk Revenue",
    "Customer Dependency", "Supporting Evidence", "Counter-Evidence", "Analyst Assessment",
]

CYCLE_COLUMNS = [
    "Demand / Cycle Driver", "Exposure Mechanism", "Cyclical / Countercyclical / Resistant / Mixed",
    "Customer Purchase Deferrability", "Customer Budget Importance", "Customer Cycle Exposure",
    "Supply / Demand Context", "Past Downturn Evidence", "Peak / Trough Behavior",
    "Supporting Evidence", "Counter-Evidence", "Analyst Assessment",
]

COST_STRUCTURE_COLUMNS = [
    "Cost Item", "Fixed / Variable / Semi-variable", "Economic Driver", "Adjustment Lag",
    "Capacity / Utilization Link", "Management Flexibility", "Downturn Behavior",
    "Supporting Evidence", "Counter-Evidence", "Analyst Assessment",
]

WORKING_CAPITAL_COLUMNS = [
    "Component / Mechanism", "Cash Absorbed / Released", "Business Driver",
    "Sustainable / Temporary / Unknown", "Customer / Supplier Consequence",
    "Normalization Needed?", "Supporting Evidence", "Counter-Evidence", "Analyst Assessment",
]

CAPEX_COLUMNS = [
    "Capex Category / Asset", "Maintenance / Growth / Regulatory / Unclear", "Amount",
    "Period", "Recurring?", "Capacity / Cash-flow Effect", "Discretionary?",
    "Management Disclosure", "Supporting Evidence", "Counter-Evidence", "Analyst Assessment",
]

EVIDENCE_COLUMNS = [
    "Question", "Claim", "Evidence Type", "Source Title", "Source URL / File",
    "Source Date", "Period", "Evidence Text", "Direction", "Status", "Data Origin", "Analyst Note",
]

RESEARCH_GAP_COLUMNS = [
    "Question", "Research Gap", "Materiality", "Next Action", "Status", "Analyst Note",
]

CHILD_TABLES: dict[str, str] = {
    "q27_accounting_quality": "chapter6_accounting_quality",
    "q28_revenue_streams": "chapter6_revenue_streams",
    "q29_cycle_drivers": "chapter6_cycle_drivers",
    "q30_cost_structure": "chapter6_cost_structure",
    "q31_working_capital": "chapter6_working_capital",
    "q32_capex_register": "chapter6_capex_register",
    "evidence_matrix": "chapter6_evidence",
    "research_gaps_table": "chapter6_research_gaps",
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
            CREATE TABLE IF NOT EXISTS chapter6_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{{}}',
                understanding_status TEXT NOT NULL DEFAULT 'not_understood',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter6_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                understanding_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chapter6_snapshots_ticker ON chapter6_snapshots(ticker);
            {child_sql}
            """
        )


def _default_accounting_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for area, area_vi in SHEARN_Q27_RESERVE_AREAS:
        rows.append(
            {
                "Area": area,
                "Area (VI)": area_vi,
                "Origin": "Shearn",
                "Policy / Estimate": "",
                "Current Treatment": "",
                "Conservative / Liberal Indicator": "Unknown",
                "3Y Pattern": "",
                "Provision / Estimate": None,
                "Actual Outcome / Charge-off": None,
                "Supporting Evidence": "",
                "Counter-Evidence": "",
                "Analyst Assessment": "Unknown",
                "Analyst Note": "",
            }
        )
    return rows


def empty_payload(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": _safe_ticker(ticker),
        "company_name": company_name or "",
        "question_status": {q: "Unknown" for q in QUESTION_KEYS},
        "question_trend": {q: "Unknown" for q in QUESTION_KEYS},
        "q27": {
            "true_operating_earnings_note": "",
            "tax_book_difference": "Unknown",
            "cfo_vs_net_income": "Unknown",
            "revenue_recognition": "Unknown",
            "expense_vs_capitalize": "Unknown",
            "discretionary_costs": "Unknown",
            "depreciation_assumptions": "Unknown",
            "restructuring_charges": "Unknown",
            "reserve_quality": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q27_accounting_quality": _default_accounting_rows(),
        "q28": {
            "recurring_revenue_share": "",
            "starting_revenue_base": "Unknown",
            "dependence_on_new_sales": "Unknown",
            "expense_budget_visibility": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q28_revenue_streams": [],
        "q29": {
            "cycle_classification": "Unknown",
            "purchase_deferrability": "Unknown",
            "recurring_revenue_protection": "Unknown",
            "customer_budget_importance": "Unknown",
            "customer_cycle_exposure": "Unknown",
            "supply_demand_distortion": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q29_cycle_drivers": [],
        "q30": {
            "operating_leverage": "Unknown",
            "fixed_cost_intensity": "Unknown",
            "cost_flexibility": "Unknown",
            "forecast_difficulty": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q30_cost_structure": [],
        "q31": {
            "working_capital_model": "",
            "ccc_direction": "Unknown",
            "ccc_change_quality": "Unknown",
            "negative_working_capital": "Unknown",
            "liquidity_dependency": "Unknown",
            "normalization_needed": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q31_working_capital": [],
        "q32": {
            "capital_intensity": "Unknown",
            "maintenance_capex_visibility": "Unknown",
            "maintenance_vs_growth_split": "Unknown",
            "regulatory_capex_burden": "Unknown",
            "deferred_maintenance_risk": "Unknown",
            "asset_age_replacement_risk": "Unknown",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q32_capex_register": [],
        "evidence_matrix": [],
        "research_gaps_table": [],
        "earnings_distribution_summary": "",
        "narrowing_factors": "",
        "widening_factors": "",
        "critical_unknowns": "",
        "analyst_summary": "",
    }


def _merge_dict(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in (incoming or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _understanding_status(payload: dict[str, Any]) -> str:
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
            if isinstance(value, dict):
                out.append(value)
        except Exception:
            continue
    return out


def _replace_child_rows(
    conn: sqlite3.Connection,
    table_name: str,
    ticker: str,
    rows: Any,
    timestamp: str,
) -> None:
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
        current = conn.execute(
            "SELECT company_name, payload_json FROM chapter6_current WHERE ticker = ?", (safe,)
        ).fetchone()
        if current is None:
            return empty_payload(safe)
        try:
            stored = json.loads(current["payload_json"] or "{}")
        except Exception:
            stored = {}
        payload = _merge_dict(empty_payload(safe, str(current["company_name"] or "")), stored)
        # Existing records own their child tables. Empty means intentionally empty; do not re-seed defaults.
        for payload_key, table_name in CHILD_TABLES.items():
            payload[payload_key] = _read_child_rows(conn, table_name, safe)
        return payload


def save_record(ticker: str, payload: dict[str, Any], company_name: str = "") -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    init_db()
    now = _now()
    normalized = _merge_dict(empty_payload(safe, company_name), payload or {})
    normalized["ticker"] = safe
    normalized["company_name"] = company_name or str(normalized.get("company_name") or "")
    for q in QUESTION_KEYS:
        status = str((normalized.get("question_status") or {}).get(q) or "Unknown")
        trend = str((normalized.get("question_trend") or {}).get(q) or "Unknown")
        normalized["question_status"][q] = status if status in QUESTION_STATUS_OPTIONS else "Unknown"
        normalized["question_trend"][q] = trend if trend in TREND_OPTIONS else "Unknown"

    # Keep child rows outside payload_json to avoid two independent sources of truth.
    body = deepcopy(normalized)
    for payload_key in CHILD_TABLES:
        body.pop(payload_key, None)
    understanding = _understanding_status(normalized)

    with _connect() as conn:
        existing = conn.execute("SELECT created_at FROM chapter6_current WHERE ticker = ?", (safe,)).fetchone()
        created_at = str(existing["created_at"]) if existing else now
        conn.execute(
            """
            INSERT INTO chapter6_current (ticker, company_name, payload_json, understanding_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name = excluded.company_name,
                payload_json = excluded.payload_json,
                understanding_status = excluded.understanding_status,
                updated_at = excluded.updated_at
            """,
            (
                safe,
                normalized["company_name"],
                json.dumps(body, ensure_ascii=False, default=str),
                understanding,
                created_at,
                now,
            ),
        )
        for payload_key, table_name in CHILD_TABLES.items():
            _replace_child_rows(conn, table_name, safe, normalized.get(payload_key), now)
    return normalized


def create_snapshot(ticker: str, payload: dict[str, Any] | None = None) -> int:
    safe = _safe_ticker(ticker)
    record = save_record(safe, payload or load_record(safe), str((payload or {}).get("company_name") or ""))
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO chapter6_snapshots (ticker, payload_json, understanding_status, created_at) VALUES (?, ?, ?, ?)",
            (
                safe,
                json.dumps(record, ensure_ascii=False, default=str),
                _understanding_status(record),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def list_snapshots(ticker: str, limit: int = 20) -> list[dict[str, Any]]:
    safe = _safe_ticker(ticker)
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, understanding_status, created_at FROM chapter6_snapshots WHERE ticker = ? ORDER BY id DESC LIMIT ?",
            (safe, max(1, int(limit))),
        ).fetchall()
        return [dict(row) for row in rows]


def research_gap_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if str((payload.get("q27") or {}).get("overall_assessment") or "Unknown") not in {"Unknown", "N/A"} and not payload.get("q27_accounting_quality"):
        warnings.append("Q27 đã có kết luận nhưng chưa có register chính sách/ước tính kế toán hoặc reserve evidence.")
    if str((payload.get("q28") or {}).get("overall_assessment") or "Unknown") not in {"Unknown", "N/A"} and not payload.get("q28_revenue_streams"):
        warnings.append("Q28 đã có kết luận nhưng chưa phân rã các dòng doanh thu recurring / one-off.")
    if str((payload.get("q29") or {}).get("cycle_classification") or "Unknown") not in {"Unknown", "N/A"} and not payload.get("q29_cycle_drivers"):
        warnings.append("Q29 đã phân loại chu kỳ nhưng chưa lưu bằng chứng theo cycle driver / downturn.")
    if str((payload.get("q30") or {}).get("operating_leverage") or "Unknown") not in {"Unknown", "N/A"} and not payload.get("q30_cost_structure"):
        warnings.append("Q30 đã đánh giá operating leverage nhưng chưa có cost-structure evidence.")
    if str((payload.get("q31") or {}).get("ccc_change_quality") or "Unknown") not in {"Unknown", "N/A"} and not payload.get("q31_working_capital"):
        warnings.append("Q31 đã đánh giá chất lượng thay đổi working capital nhưng chưa có mechanism/evidence register.")
    if str((payload.get("q32") or {}).get("maintenance_vs_growth_split") or "Unknown") not in {"Unknown", "N/A"} and not payload.get("q32_capex_register"):
        warnings.append("Q32 đã đánh giá maintenance/growth capex nhưng chưa có capex register/evidence.")
    return warnings


__all__ = [
    "ACCOUNTING_QUALITY_COLUMNS", "CAPEX_COLUMNS", "COST_STRUCTURE_COLUMNS", "CYCLE_COLUMNS",
    "EVIDENCE_COLUMNS", "QUESTION_KEYS", "QUESTION_STATUS_OPTIONS", "RECURRING_REVENUE_COLUMNS",
    "RESEARCH_GAP_COLUMNS", "SHEARN_Q27_RESERVE_AREAS", "TREND_OPTIONS", "WORKING_CAPITAL_COLUMNS",
    "create_snapshot", "empty_payload", "init_db", "list_snapshots", "load_record",
    "research_gap_warnings", "save_record",
]
