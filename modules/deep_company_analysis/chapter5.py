from __future__ import annotations

"""Shearn Chapter 5 — Measuring the Operating and Financial Health of the Business.

Phase 5A is a source-locked analyst workspace for Q21–Q26 from *The Investment Checklist*.
It intentionally contains no automatic fundamental/risk/inflation/balance-sheet/ROIC conclusion.

User-approved amendments:
- Chapter 5 has NO confidence field anywhere.
- Q23 is pre-populated with the operational risks explicitly listed by Michael Shearn;
  the analyst may add additional risks, which are marked Analyst-defined.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import sqlite3

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parents[2]
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter5.db"

QUESTION_KEYS = ("Q21", "Q22", "Q23", "Q24", "Q25", "Q26")
QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
TREND_OPTIONS = ("Unknown", "Improving", "Stable", "Deteriorating", "Mixed")

# Q23 — Shearn's explicit operational-risk examples, preserved as the default risk universe.
SHEARN_Q23_RISKS: tuple[tuple[str, str], ...] = (
    ("Overcapacity", "Dư thừa công suất"),
    ("Commoditization", "Hàng hóa hóa / mất khác biệt"),
    ("Deregulation", "Bãi bỏ hoặc giảm điều tiết"),
    ("Increased power among suppliers", "Quyền lực của nhà cung cấp gia tăng"),
    ("Shifts in technology", "Dịch chuyển công nghệ"),
    ("Changes in laws and regulations", "Thay đổi luật và quy định"),
    ("Product obsolescence", "Sản phẩm lỗi thời"),
    ("Patent expirations", "Bằng sáng chế hết hạn"),
    ("Development of new product lines where the business has limited expertise", "Phát triển dòng sản phẩm mới ở lĩnh vực doanh nghiệp ít kinh nghiệm"),
    ("The emergence of competitors", "Sự xuất hiện của đối thủ mới"),
    ("Brand erosion", "Suy yếu thương hiệu"),
    ("Overreliance on too few customers", "Phụ thuộc quá mức vào quá ít khách hàng"),
    ("Limited geographic distribution", "Phân phối địa lý hạn chế"),
    ("Research and development failure", "Thất bại nghiên cứu và phát triển"),
    ("Business-development failure", "Thất bại phát triển kinh doanh"),
    ("Merger or acquisition failure", "Thất bại sáp nhập hoặc mua lại"),
    ("A weak product pipeline", "Danh mục sản phẩm mới yếu"),
)

FUNDAMENTAL_COLUMNS = [
    "Fundamental Driver", "Why It Creates Value", "Economic Linkage", "Measure / KPI",
    "Current Assessment", "Trend", "Leading / Lagging", "Supporting Evidence",
    "Counter-Evidence", "Deterioration Test", "Analyst Conclusion",
]

METRIC_COLUMNS = [
    "Metric", "Definition", "Unit", "Linked Fundamental", "Source", "Current Value",
    "Current Period", "3-5Y Trend", "Temporary / Structural", "Why It Changed",
    "Comparable with Peers?", "Analyst Conclusion",
]

METRIC_HISTORY_COLUMNS = [
    "Metric", "Period", "Value", "Change", "Why?", "Evidence",
    "Temporary / Structural", "Analyst Interpretation",
]

RISK_COLUMNS = [
    "Risk", "Risk (VI)", "Origin", "Applicability", "Exposure Mechanism", "Frequency",
    "Severity", "Historical Company Evidence", "Peer / Historical Case", "Financial Consequence",
    "Mitigation", "Mitigation Evidence", "Early Warning Indicator", "Review Trigger",
    "Counter-Evidence", "Trend", "Analyst Assessment", "Evidence",
]

INFLATION_COLUMNS = [
    "Input / Exposure", "Channel", "Exposure", "Observed Cost Change", "Pass-through Ability",
    "Lag to Pass Through", "Volume / Customer Impact", "Cost Offset", "Capital Replacement Burden",
    "Debt / Interest Exposure", "Real Cash Flow Impact", "Evidence", "Analyst Assessment",
]

DEBT_COLUMNS = [
    "Debt / Facility", "Purpose", "Amount", "Currency", "Fixed / Floating", "Rate",
    "Maturity", "Secured?", "Recourse", "Lender / Funding Source", "Evidence", "Analyst Note",
]

OFF_BS_COLUMNS = [
    "Obligation", "Amount", "Period", "On / Off Balance Sheet", "Cash Commitment",
    "Included in Adjusted Debt?", "Evidence", "Analyst Note",
]

COVENANT_COLUMNS = [
    "Covenant", "Actual", "Limit", "Headroom", "Status", "Test Date", "Evidence", "Analyst Note",
]

ROIC_VARIANT_COLUMNS = [
    "ROIC Variant", "Origin", "Numerator Definition", "Denominator Definition", "Value",
    "Period", "Purpose", "Distortion Addressed", "Analyst Interpretation",
]

ROIC_ADJUSTMENT_COLUMNS = [
    "Adjustment", "Numerator / Denominator", "Amount", "Rationale", "Evidence",
    "Included?", "Analyst Note",
]

REINVESTMENT_COLUMNS = [
    "Period / Project", "Reinvestment Amount", "Organic / M&A", "Incremental Earnings",
    "Incremental ROIC", "Runway", "Moat Support", "Capacity Constraint", "Evidence",
    "Analyst Assessment",
]

EVIDENCE_COLUMNS = [
    "Question", "Claim", "Evidence Type", "Source Title", "Source URL / File",
    "Source Date", "Period", "Evidence Text", "Direction", "Status", "Data Origin", "Analyst Note",
]

RESEARCH_GAP_COLUMNS = [
    "Question", "Research Gap", "Materiality", "Next Action", "Status", "Analyst Note",
]

CHILD_TABLES: dict[str, str] = {
    "q21_fundamentals": "chapter5_fundamentals",
    "q22_metrics": "chapter5_metric_registry",
    "q22_metric_history": "chapter5_metric_history",
    "q23_risks": "chapter5_risks",
    "q24_inflation_exposures": "chapter5_inflation_exposures",
    "q25_debt_instruments": "chapter5_debt_instruments",
    "q25_off_balance_obligations": "chapter5_off_balance_obligations",
    "q25_covenants": "chapter5_covenants",
    "q26_roic_variants": "chapter5_roic_variants",
    "q26_roic_adjustments": "chapter5_roic_adjustments",
    "q26_reinvestment": "chapter5_reinvestment",
    "evidence_matrix": "chapter5_evidence",
    "research_gaps_table": "chapter5_research_gaps",
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
            CREATE TABLE IF NOT EXISTS chapter5_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{{}}',
                understanding_status TEXT NOT NULL DEFAULT 'not_understood',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter5_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                understanding_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chapter5_snapshots_ticker ON chapter5_snapshots(ticker);
            {child_sql}
            """
        )


def _default_risk_rows() -> list[dict[str, Any]]:
    return [
        {
            "Risk": risk,
            "Risk (VI)": vi,
            "Origin": "Shearn",
            "Applicability": "Review",
            "Exposure Mechanism": "",
            "Frequency": "Unknown",
            "Severity": "Unknown",
            "Historical Company Evidence": "",
            "Peer / Historical Case": "",
            "Financial Consequence": "",
            "Mitigation": "",
            "Mitigation Evidence": "",
            "Early Warning Indicator": "",
            "Review Trigger": "",
            "Counter-Evidence": "",
            "Trend": "Unknown",
            "Analyst Assessment": "Unknown",
            "Evidence": "",
        }
        for risk, vi in SHEARN_Q23_RISKS
    ]


def empty_payload(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": _safe_ticker(ticker),
        "company_name": company_name or "",
        "question_status": {q: "Unknown" for q in QUESTION_KEYS},
        "question_trend": {q: "Unknown" for q in QUESTION_KEYS},
        "q21": {
            "fundamentals_summary": "",
            "most_important_driver": "",
            "deteriorating_driver": "",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q21_fundamentals": [],
        "q22": {
            "critical_metrics_summary": "",
            "definition_compatibility_note": "",
            "temporary_vs_structural_summary": "",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q22_metrics": [],
        "q22_metric_history": [],
        "q23": {
            "risk_framework_note": "Frequency + Severity; use historical evidence, not media attention.",
            "most_material_risk": "",
            "largest_unknown_risk": "",
            "downside_scenario_link": "",
            "overall_assessment": "Unknown",
            "conclusion": "",
        },
        "q23_risks": _default_risk_rows(),
        "q24": {
            "pricing_pass_through": "Unknown",
            "cost_flexibility": "Unknown",
            "capital_replacement_burden": "Unknown",
            "debt_interest_exposure": "Unknown",
            "inflation_resilience": "Unknown",
            "main_vulnerability": "",
            "main_protection": "",
            "conclusion": "",
        },
        "q24_inflation_exposures": [],
        "q25": {
            "debt_motivation": "",
            "cash_flow_stability": "Unknown",
            "liquidity": "Unknown",
            "refinancing_risk": "Unknown",
            "covenant_risk": "Unknown",
            "financial_flexibility": "Unknown",
            "balance_sheet_assessment": "Unknown",
            "main_strength": "",
            "main_weakness": "",
            "conclusion": "",
        },
        "q25_debt_instruments": [],
        "q25_off_balance_obligations": [],
        "q25_covenants": [],
        "q26": {
            "canonical_roic_note": "Canonical ROIC remains owned by the Trecapital Data Layer.",
            "selected_analytical_method": "Unknown",
            "current_roic_quality": "Unknown",
            "distortion_summary": "",
            "incremental_roic_assessment": "Unknown",
            "reinvestment_runway": "Unknown",
            "sustainability": "Unknown",
            "conclusion": "",
        },
        "q26_roic_variants": [
            {"ROIC Variant": name, "Origin": origin, "Numerator Definition": "", "Denominator Definition": "", "Value": None, "Period": "", "Purpose": purpose, "Distortion Addressed": distortion, "Analyst Interpretation": ""}
            for name, origin, purpose, distortion in (
                ("Trecapital Canonical ROIC", "Trecapital canonical", "Single Source of Truth reference", "None — canonical reference"),
                ("ROIC with cash", "Shearn analytical", "Total capital view", "Cash may dilute core economics"),
                ("ROIC ex excess cash", "Shearn analytical", "Core operating return", "Excess cash distortion"),
                ("ROIC including goodwill", "Shearn analytical", "Include acquisition capital", "Acquisition overpayment"),
                ("ROIC ex goodwill", "Shearn analytical", "Tangible operating return", "Goodwill distortion"),
                ("ROIC gross-asset adjusted", "Shearn analytical", "Check aging/depreciation distortion", "Depreciation / aging asset"),
                ("ROIC off-BS adjusted", "Shearn analytical", "Include material off-BS obligations", "Lease / pension / other obligations"),
            )
        ],
        "q26_roic_adjustments": [],
        "q26_reinvestment": [],
        "evidence_matrix": [],
        "research_gaps_table": [],
        "top_operating_strengths": "",
        "top_operating_weaknesses": "",
        "deterioration_watch": "",
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


def _risk_key(row: dict[str, Any]) -> str:
    return str(row.get("Risk") or "").strip().casefold()


def ensure_shearn_risks(rows: Any) -> list[dict[str, Any]]:
    """Keep all Shearn defaults and preserve analyst-added risks.

    Analyst-added rows with blank Origin are normalized to Analyst-defined.  Shearn rows cannot be
    silently relabelled as Analyst-defined.
    """
    incoming = [dict(x) for x in rows] if isinstance(rows, list) else []
    incoming_by_key = {_risk_key(row): row for row in incoming if _risk_key(row)}
    result: list[dict[str, Any]] = []

    for default in _default_risk_rows():
        key = _risk_key(default)
        merged = {**default, **incoming_by_key.pop(key, {})}
        merged["Risk"] = default["Risk"]
        merged["Risk (VI)"] = default["Risk (VI)"]
        merged["Origin"] = "Shearn"
        result.append(merged)

    for row in incoming:
        key = _risk_key(row)
        if not key or key not in incoming_by_key:
            continue
        normalized = {col: row.get(col, "") for col in RISK_COLUMNS}
        normalized["Origin"] = str(normalized.get("Origin") or "Analyst-defined")
        if normalized["Origin"] == "Shearn":
            normalized["Origin"] = "Analyst-defined"
        result.append(normalized)
        incoming_by_key.pop(key, None)
    return result


def _strip_confidence_fields(value: Any) -> Any:
    """Chapter-5 policy: confidence fields are intentionally removed from all payload levels."""
    if isinstance(value, dict):
        return {k: _strip_confidence_fields(v) for k, v in value.items() if "confidence" not in str(k).casefold()}
    if isinstance(value, list):
        return [_strip_confidence_fields(x) for x in value]
    return value


def _sync_child_tables(conn: sqlite3.Connection, record: dict[str, Any], now: str) -> None:
    ticker = _safe_ticker(record.get("ticker", ""))
    for key, table in CHILD_TABLES.items():
        conn.execute(f"DELETE FROM {table} WHERE ticker = ?", (ticker,))
        rows = record.get(key, [])
        if not isinstance(rows, list):
            continue
        for position, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            conn.execute(
                f"INSERT INTO {table}(ticker, position, row_json, created_at, updated_at) VALUES(?,?,?,?,?)",
                (ticker, position, json.dumps(row, ensure_ascii=False, default=str), now, now),
            )


def load_record(ticker: str, company_name: str = "") -> dict[str, Any]:
    init_db()
    ticker = _safe_ticker(ticker)
    base = empty_payload(ticker, company_name)
    if not ticker:
        return base
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chapter5_current WHERE ticker = ?", (ticker,)).fetchone()
    if not row:
        return base
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    record = _merge_dict(base, payload)
    record["ticker"] = ticker
    record["company_name"] = company_name or record.get("company_name", "")
    record["q23_risks"] = ensure_shearn_risks(record.get("q23_risks"))
    return _strip_confidence_fields(record)


def save_record(record: dict[str, Any], create_snapshot: bool = False) -> dict[str, Any]:
    init_db()
    clean = _strip_confidence_fields(deepcopy(record))
    ticker = _safe_ticker(clean.get("ticker", ""))
    if not ticker:
        raise ValueError("Ticker is required")
    clean["ticker"] = ticker
    clean["q23_risks"] = ensure_shearn_risks(clean.get("q23_risks"))
    now = _now()
    understanding = _understanding_status(clean)
    payload_json = json.dumps(clean, ensure_ascii=False, default=str)
    with _connect() as conn:
        exists = conn.execute("SELECT 1 FROM chapter5_current WHERE ticker = ?", (ticker,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE chapter5_current SET company_name=?, payload_json=?, understanding_status=?, updated_at=? WHERE ticker=?",
                (clean.get("company_name", ""), payload_json, understanding, now, ticker),
            )
        else:
            conn.execute(
                "INSERT INTO chapter5_current(ticker, company_name, payload_json, understanding_status, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (ticker, clean.get("company_name", ""), payload_json, understanding, now, now),
            )
        _sync_child_tables(conn, clean, now)
        if create_snapshot:
            conn.execute(
                "INSERT INTO chapter5_snapshots(ticker, payload_json, understanding_status, created_at) VALUES(?,?,?,?)",
                (ticker, payload_json, understanding, now),
            )
    return clean


def save_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    return save_record(record, create_snapshot=True)


def load_snapshots(ticker: str, limit: int = 20) -> pd.DataFrame:
    init_db()
    safe = _safe_ticker(ticker)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, ticker, understanding_status, created_at FROM chapter5_snapshots WHERE ticker=? ORDER BY id DESC LIMIT ?",
            (safe, int(limit)),
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def _understanding_status(record: dict[str, Any]) -> str:
    statuses = record.get("question_status", {}) if isinstance(record, dict) else {}
    values = [str(statuses.get(q, "Unknown")) for q in QUESTION_KEYS]
    answered = sum(v == "Answered" for v in values)
    partial = sum(v == "Partial" for v in values)
    if answered == len(QUESTION_KEYS):
        return "understood"
    if answered + partial > 0:
        return "partial"
    return "not_understood"


def research_coverage(record: dict[str, Any]) -> tuple[int, int]:
    statuses = record.get("question_status", {}) if isinstance(record, dict) else {}
    complete = sum(str(statuses.get(q, "Unknown")) in {"Answered", "N/A"} for q in QUESTION_KEYS)
    return complete, len(QUESTION_KEYS)


def cross_question_checks(record: dict[str, Any], chapter4_record: dict[str, Any] | None = None) -> list[str]:
    checks: list[str] = []
    q23 = record.get("q23", {}) if isinstance(record, dict) else {}
    risks = record.get("q23_risks", []) if isinstance(record, dict) else []
    for row in risks if isinstance(risks, list) else []:
        if not isinstance(row, dict):
            continue
        if str(row.get("Severity")) == "Catastrophic" and str(row.get("Frequency")) == "Unknown":
            checks.append(f"Q23 — {row.get('Risk')}: Severity = Catastrophic nhưng Frequency còn Unknown → Critical Research Gap.")
        if str(row.get("Severity")) in {"High", "Catastrophic"} and not str(row.get("Historical Company Evidence") or row.get("Peer / Historical Case") or "").strip():
            checks.append(f"Q23 — {row.get('Risk')}: rủi ro nghiêm trọng nhưng chưa có historical evidence/case để ước lượng hậu quả.")

    if chapter4_record:
        q16 = chapter4_record.get("q16", {}) if isinstance(chapter4_record, dict) else {}
        q15 = chapter4_record.get("q15", {}) if isinstance(chapter4_record, dict) else {}
        pricing = str(q16.get("pricing_power", "Unknown"))
        inflation = str(record.get("q24", {}).get("inflation_resilience", "Unknown"))
        if inflation == "Resilient" and pricing in {"Weak", "None", "Unknown"}:
            checks.append("Q24 ↔ Ch4/Q16 — Inflation Resilience đang là Resilient nhưng Pricing Power chưa mạnh; cần chứng minh cost flexibility/capex/debt channel thay thế.")
        runway = str(record.get("q26", {}).get("reinvestment_runway", "Unknown"))
        moat_trend = str(q15.get("overall_moat_trend", "Unknown"))
        if runway == "Long" and moat_trend == "Deteriorating":
            checks.append("Q26 ↔ Ch4/Q15 — Reinvestment Runway = Long nhưng moat đang Deteriorating; cần review sustainability of incremental returns.")

    q26 = record.get("q26", {}) if isinstance(record, dict) else {}
    if str(q26.get("current_roic_quality")) == "High" and str(q26.get("reinvestment_runway")) in {"None", "Short"}:
        checks.append("Q26 — Current ROIC cao nhưng reinvestment runway ngắn/không có; không được tự coi là long-run compounder.")
    return checks


def guardrails() -> dict[str, bool]:
    return {
        "auto_fundamental_conclusion": False,
        "auto_metric_criticality": False,
        "auto_risk_rating": False,
        "media_attention_is_risk_level": False,
        "missing_risk_data_is_low_risk": False,
        "auto_inflation_resilience": False,
        "auto_balance_sheet_conclusion": False,
        "debt_ratio_threshold_is_final_judgement": False,
        "auto_roic_quality_conclusion": False,
        "roic_above_threshold_is_final_quality": False,
        "auto_reinvestment_conclusion": False,
        "auto_research_gate_change": False,
        "auto_buy_hold_sell": False,
    }


def _to_records(df: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame):
        return []
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = ""
    out = out[columns].where(pd.notna(out), None)
    rows = out.to_dict("records")
    return [row for row in rows if any(str(v or "").strip() for v in row.values())]


def _editor(label: str, rows: list[dict[str, Any]], columns: list[str], key: str, height: int = 320) -> pd.DataFrame:
    df = pd.DataFrame(rows or [], columns=columns)
    st.caption(label)
    return st.data_editor(
        df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        height=height,
        key=key,
    )


def _question_header(record: dict[str, Any], q: str, title: str, key_prefix: str) -> tuple[str, str]:
    st.markdown(f"### {q} — {title}")
    c1, c2 = st.columns(2)
    with c1:
        status = st.selectbox(
            "Research status",
            QUESTION_STATUS_OPTIONS,
            index=QUESTION_STATUS_OPTIONS.index(str(record.get("question_status", {}).get(q, "Unknown"))) if str(record.get("question_status", {}).get(q, "Unknown")) in QUESTION_STATUS_OPTIONS else 0,
            key=f"{key_prefix}_{q}_status",
        )
    with c2:
        trend = st.selectbox(
            "Trend",
            TREND_OPTIONS,
            index=TREND_OPTIONS.index(str(record.get("question_trend", {}).get(q, "Unknown"))) if str(record.get("question_trend", {}).get(q, "Unknown")) in TREND_OPTIONS else 0,
            key=f"{key_prefix}_{q}_trend",
        )
    return status, trend


def render_chapter5(default_ticker: str = "DGC", company_name: str = "") -> None:
    safe = _safe_ticker(st.text_input("Mã cổ phiếu — Chương 5", value=_safe_ticker(default_ticker) or "DGC", key="dca_ch5_ticker")) or "DGC"
    record = load_record(safe, company_name)
    prefix = f"ch5_{safe}"

    st.info(
        "Chương 5 bám Q21–Q26 của Michael Shearn. Phase 5A là analyst workspace: chưa tự kết luận fundamentals, risk, inflation, balance sheet hay ROIC. "
        "Theo yêu cầu đã duyệt, Chương 5 không có Confidence field."
    )

    complete, total = research_coverage(record)
    cols = st.columns(6)
    labels = {
        "Q21": "Fundamentals", "Q22": "Operating Metrics", "Q23": "Key Risks",
        "Q24": "Inflation", "Q25": "Balance Sheet", "Q26": "ROIC",
    }
    for i, q in enumerate(QUESTION_KEYS):
        cols[i].metric(labels[q], str(record.get("question_status", {}).get(q, "Unknown")))
    st.caption(f"Research completion: {complete}/{total} câu Answered/N/A. Đây là coverage nghiên cứu, không phải investment-quality score.")

    with st.expander("Q21 — What are the fundamentals of the business?", expanded=True):
        q21_status, q21_trend = _question_header(record, "Q21", "Các fundamentals thực sự của doanh nghiệp là gì?", prefix)
        st.caption("Fundamental không đồng nghĩa với revenue/EPS. Hãy xác định những yếu tố hoạt động mà nếu suy yếu thì giá trị kinh tế của doanh nghiệp cũng suy yếu.")
        q21_df = _editor("Fundamental Driver Map", record.get("q21_fundamentals", []), FUNDAMENTAL_COLUMNS, f"{prefix}_q21_fundamentals", 340)
        q21_summary = st.text_area("Tóm tắt fundamentals", value=str(record.get("q21", {}).get("fundamentals_summary", "")), key=f"{prefix}_q21_summary")
        q21_key = st.text_input("Fundamental quan trọng nhất", value=str(record.get("q21", {}).get("most_important_driver", "")), key=f"{prefix}_q21_key")
        q21_det = st.text_input("Fundamental đang suy yếu đáng chú ý", value=str(record.get("q21", {}).get("deteriorating_driver", "")), key=f"{prefix}_q21_det")
        q21_ass = st.selectbox("Q21 Analyst Assessment", ("Unknown", "Strong", "Stable", "Deteriorating", "Broken", "Mixed"), index=("Unknown", "Strong", "Stable", "Deteriorating", "Broken", "Mixed").index(str(record.get("q21", {}).get("overall_assessment", "Unknown"))) if str(record.get("q21", {}).get("overall_assessment", "Unknown")) in ("Unknown", "Strong", "Stable", "Deteriorating", "Broken", "Mixed") else 0, key=f"{prefix}_q21_ass")
        q21_conclusion = st.text_area("Q21 Analyst Conclusion", value=str(record.get("q21", {}).get("conclusion", "")), key=f"{prefix}_q21_conclusion")

    with st.expander("Q22 — What are the operating metrics of the business that you need to monitor?", expanded=False):
        q22_status, q22_trend = _question_header(record, "Q22", "Các operating metrics cần theo dõi là gì?", prefix)
        st.caption("Ghi nguyên nhân biến động ít nhất 3–5 năm; phân biệt Temporary vs Structural; chỉ so peer khi định nghĩa/kỳ/accounting method tương thích.")
        q22_df = _editor("Operating Metric Registry", record.get("q22_metrics", []), METRIC_COLUMNS, f"{prefix}_q22_metrics", 330)
        q22_hist_df = _editor("Metric Driver History", record.get("q22_metric_history", []), METRIC_HISTORY_COLUMNS, f"{prefix}_q22_hist", 280)
        q22_summary = st.text_area("Critical metrics summary", value=str(record.get("q22", {}).get("critical_metrics_summary", "")), key=f"{prefix}_q22_summary")
        q22_compat = st.text_area("Metric Definition Compatibility note", value=str(record.get("q22", {}).get("definition_compatibility_note", "")), key=f"{prefix}_q22_compat")
        q22_temp = st.text_area("Temporary vs Structural summary", value=str(record.get("q22", {}).get("temporary_vs_structural_summary", "")), key=f"{prefix}_q22_temp")
        q22_ass = st.selectbox("Q22 Analyst Assessment", ("Unknown", "Healthy", "Mixed", "Deteriorating"), index=("Unknown", "Healthy", "Mixed", "Deteriorating").index(str(record.get("q22", {}).get("overall_assessment", "Unknown"))) if str(record.get("q22", {}).get("overall_assessment", "Unknown")) in ("Unknown", "Healthy", "Mixed", "Deteriorating") else 0, key=f"{prefix}_q22_ass")
        q22_conclusion = st.text_area("Q22 Analyst Conclusion", value=str(record.get("q22", {}).get("conclusion", "")), key=f"{prefix}_q22_conclusion")

    with st.expander("Q23 — What are the key risks the business faces?", expanded=True):
        q23_status, q23_trend = _question_header(record, "Q23", "Những rủi ro trọng yếu mà doanh nghiệp đối mặt là gì?", prefix)
        st.warning("Shearn: đánh giá risk theo Frequency + Severity và historical evidence. Mức độ báo chí nhắc đến không phải thước đo rủi ro. Không có dữ liệu không đồng nghĩa Low Risk.")
        st.markdown("**17 rủi ro mặc định dưới đây là các operational-risk examples Shearn nêu trực tiếp trong Chương 5. Người phân tích có thể thêm dòng mới; dòng mới sẽ được lưu là `Analyst-defined`.**")
        risk_df = _editor("Risk Underwriter Register — Shearn defaults + Analyst-defined risks", record.get("q23_risks", []), RISK_COLUMNS, f"{prefix}_q23_risks", 520)
        q23_material = st.text_input("Rủi ro trọng yếu nhất", value=str(record.get("q23", {}).get("most_material_risk", "")), key=f"{prefix}_q23_material")
        q23_unknown = st.text_input("Rủi ro lớn nhất còn chưa hiểu", value=str(record.get("q23", {}).get("largest_unknown_risk", "")), key=f"{prefix}_q23_unknown")
        q23_downside = st.text_area("Downside scenario / valuation linkage", value=str(record.get("q23", {}).get("downside_scenario_link", "")), key=f"{prefix}_q23_downside")
        q23_ass = st.selectbox("Q23 Analyst Assessment", ("Unknown", "Manageable", "Material", "High", "Critical", "Mixed"), index=("Unknown", "Manageable", "Material", "High", "Critical", "Mixed").index(str(record.get("q23", {}).get("overall_assessment", "Unknown"))) if str(record.get("q23", {}).get("overall_assessment", "Unknown")) in ("Unknown", "Manageable", "Material", "High", "Critical", "Mixed") else 0, key=f"{prefix}_q23_ass")
        q23_conclusion = st.text_area("Q23 Analyst Conclusion", value=str(record.get("q23", {}).get("conclusion", "")), key=f"{prefix}_q23_conclusion")

    with st.expander("Q24 — How does inflation affect the business?", expanded=False):
        q24_status, q24_trend = _question_header(record, "Q24", "Lạm phát ảnh hưởng doanh nghiệp như thế nào?", prefix)
        st.caption("Theo Shearn, protection có thể đến từ pricing power, cost reduction, low capex requirements và long-term debt maturities. Phase 5A chỉ ghi cơ chế/evidence; chưa tự kết luận.")
        q24_df = _editor("Inflation Resilience Map", record.get("q24_inflation_exposures", []), INFLATION_COLUMNS, f"{prefix}_q24_exposures", 330)
        q24_pricing = st.selectbox("Pricing pass-through", ("Unknown", "Strong", "Partial", "Weak", "None"), index=("Unknown", "Strong", "Partial", "Weak", "None").index(str(record.get("q24", {}).get("pricing_pass_through", "Unknown"))) if str(record.get("q24", {}).get("pricing_pass_through", "Unknown")) in ("Unknown", "Strong", "Partial", "Weak", "None") else 0, key=f"{prefix}_q24_pricing")
        q24_cost = st.selectbox("Cost flexibility", ("Unknown", "Strong", "Partial", "Weak"), index=("Unknown", "Strong", "Partial", "Weak").index(str(record.get("q24", {}).get("cost_flexibility", "Unknown"))) if str(record.get("q24", {}).get("cost_flexibility", "Unknown")) in ("Unknown", "Strong", "Partial", "Weak") else 0, key=f"{prefix}_q24_cost")
        q24_capex = st.selectbox("Capital replacement burden", ("Unknown", "Low", "Moderate", "High"), index=("Unknown", "Low", "Moderate", "High").index(str(record.get("q24", {}).get("capital_replacement_burden", "Unknown"))) if str(record.get("q24", {}).get("capital_replacement_burden", "Unknown")) in ("Unknown", "Low", "Moderate", "High") else 0, key=f"{prefix}_q24_capex")
        q24_debt = st.selectbox("Debt / interest exposure", ("Unknown", "Low", "Moderate", "High"), index=("Unknown", "Low", "Moderate", "High").index(str(record.get("q24", {}).get("debt_interest_exposure", "Unknown"))) if str(record.get("q24", {}).get("debt_interest_exposure", "Unknown")) in ("Unknown", "Low", "Moderate", "High") else 0, key=f"{prefix}_q24_debt")
        q24_res = st.selectbox("Inflation Resilience — Analyst", ("Unknown", "Resilient", "Partially Resilient", "Vulnerable", "Mixed"), index=("Unknown", "Resilient", "Partially Resilient", "Vulnerable", "Mixed").index(str(record.get("q24", {}).get("inflation_resilience", "Unknown"))) if str(record.get("q24", {}).get("inflation_resilience", "Unknown")) in ("Unknown", "Resilient", "Partially Resilient", "Vulnerable", "Mixed") else 0, key=f"{prefix}_q24_res")
        q24_vuln = st.text_input("Main vulnerability", value=str(record.get("q24", {}).get("main_vulnerability", "")), key=f"{prefix}_q24_vuln")
        q24_prot = st.text_input("Main protection", value=str(record.get("q24", {}).get("main_protection", "")), key=f"{prefix}_q24_prot")
        q24_conclusion = st.text_area("Q24 Analyst Conclusion", value=str(record.get("q24", {}).get("conclusion", "")), key=f"{prefix}_q24_conclusion")

    with st.expander("Q25 — Is the business's balance sheet strong or weak?", expanded=False):
        q25_status, q25_trend = _question_header(record, "Q25", "Bảng cân đối mạnh hay yếu?", prefix)
        st.caption("Phase 5A dựng analyst workspace về debt purpose, maturity, fixed/floating, recourse, off-BS obligations và covenants. Phase 5B mới nối canonical ratios/stress test.")
        q25_debt_df = _editor("Debt / Facility Register", record.get("q25_debt_instruments", []), DEBT_COLUMNS, f"{prefix}_q25_debt", 330)
        q25_off_df = _editor("Hidden / Contractual Obligations", record.get("q25_off_balance_obligations", []), OFF_BS_COLUMNS, f"{prefix}_q25_off", 260)
        q25_cov_df = _editor("Covenant Monitor", record.get("q25_covenants", []), COVENANT_COLUMNS, f"{prefix}_q25_cov", 250)
        q25_mot = st.text_area("Debt motivation / why did the business borrow?", value=str(record.get("q25", {}).get("debt_motivation", "")), key=f"{prefix}_q25_mot")
        q25_cfs = st.selectbox("Cash-flow stability", ("Unknown", "High", "Moderate", "Low", "Cyclical"), index=("Unknown", "High", "Moderate", "Low", "Cyclical").index(str(record.get("q25", {}).get("cash_flow_stability", "Unknown"))) if str(record.get("q25", {}).get("cash_flow_stability", "Unknown")) in ("Unknown", "High", "Moderate", "Low", "Cyclical") else 0, key=f"{prefix}_q25_cfs")
        q25_liq = st.selectbox("Liquidity", ("Unknown", "Strong", "Adequate", "Weak"), index=("Unknown", "Strong", "Adequate", "Weak").index(str(record.get("q25", {}).get("liquidity", "Unknown"))) if str(record.get("q25", {}).get("liquidity", "Unknown")) in ("Unknown", "Strong", "Adequate", "Weak") else 0, key=f"{prefix}_q25_liq")
        q25_refi = st.selectbox("Refinancing risk", ("Unknown", "Low", "Moderate", "High"), index=("Unknown", "Low", "Moderate", "High").index(str(record.get("q25", {}).get("refinancing_risk", "Unknown"))) if str(record.get("q25", {}).get("refinancing_risk", "Unknown")) in ("Unknown", "Low", "Moderate", "High") else 0, key=f"{prefix}_q25_refi")
        q25_cov = st.selectbox("Covenant risk", ("Unknown", "Low", "Moderate", "High"), index=("Unknown", "Low", "Moderate", "High").index(str(record.get("q25", {}).get("covenant_risk", "Unknown"))) if str(record.get("q25", {}).get("covenant_risk", "Unknown")) in ("Unknown", "Low", "Moderate", "High") else 0, key=f"{prefix}_q25_covrisk")
        q25_flex = st.selectbox("Financial flexibility", ("Unknown", "Strong", "Adequate", "Weak"), index=("Unknown", "Strong", "Adequate", "Weak").index(str(record.get("q25", {}).get("financial_flexibility", "Unknown"))) if str(record.get("q25", {}).get("financial_flexibility", "Unknown")) in ("Unknown", "Strong", "Adequate", "Weak") else 0, key=f"{prefix}_q25_flex")
        q25_ass = st.selectbox("Balance Sheet — Analyst Assessment", ("Unknown", "Strong", "Adequate", "Weak", "Stressed"), index=("Unknown", "Strong", "Adequate", "Weak", "Stressed").index(str(record.get("q25", {}).get("balance_sheet_assessment", "Unknown"))) if str(record.get("q25", {}).get("balance_sheet_assessment", "Unknown")) in ("Unknown", "Strong", "Adequate", "Weak", "Stressed") else 0, key=f"{prefix}_q25_ass")
        q25_strength = st.text_input("Main balance-sheet strength", value=str(record.get("q25", {}).get("main_strength", "")), key=f"{prefix}_q25_strength")
        q25_weak = st.text_input("Main balance-sheet weakness", value=str(record.get("q25", {}).get("main_weakness", "")), key=f"{prefix}_q25_weak")
        q25_conclusion = st.text_area("Q25 Analyst Conclusion", value=str(record.get("q25", {}).get("conclusion", "")), key=f"{prefix}_q25_conclusion")

    with st.expander("Q26 — What is the return on invested capital for the business?", expanded=True):
        q26_status, q26_trend = _question_header(record, "Q26", "ROIC thực sự của doanh nghiệp là gì và có tái đầu tư được không?", prefix)
        st.warning("Canonical ROIC vẫn thuộc Trecapital Data Layer. Phase 5A chỉ tạo methodology/adjustment/reinvestment workspace; không tự chọn phương pháp ROIC cuối cùng hay tự gọi doanh nghiệp là high quality.")
        q26_var_df = _editor("ROIC Methodology / Variant Registry", record.get("q26_roic_variants", []), ROIC_VARIANT_COLUMNS, f"{prefix}_q26_variants", 360)
        q26_adj_df = _editor("ROIC Adjustments / Distortion Register", record.get("q26_roic_adjustments", []), ROIC_ADJUSTMENT_COLUMNS, f"{prefix}_q26_adj", 260)
        q26_reinv_df = _editor("Reinvestment Analyzer", record.get("q26_reinvestment", []), REINVESTMENT_COLUMNS, f"{prefix}_q26_reinv", 300)
        q26_method = st.selectbox("Selected analytical methodology — Analyst", ("Unknown", "Canonical only", "Ex excess cash", "Including goodwill", "Ex goodwill", "Gross asset adjusted", "Off-BS adjusted", "Multiple views"), index=("Unknown", "Canonical only", "Ex excess cash", "Including goodwill", "Ex goodwill", "Gross asset adjusted", "Off-BS adjusted", "Multiple views").index(str(record.get("q26", {}).get("selected_analytical_method", "Unknown"))) if str(record.get("q26", {}).get("selected_analytical_method", "Unknown")) in ("Unknown", "Canonical only", "Ex excess cash", "Including goodwill", "Ex goodwill", "Gross asset adjusted", "Off-BS adjusted", "Multiple views") else 0, key=f"{prefix}_q26_method")
        q26_quality = st.selectbox("Current ROIC Quality — Analyst", ("Unknown", "High", "Moderate", "Low", "Distorted", "Mixed"), index=("Unknown", "High", "Moderate", "Low", "Distorted", "Mixed").index(str(record.get("q26", {}).get("current_roic_quality", "Unknown"))) if str(record.get("q26", {}).get("current_roic_quality", "Unknown")) in ("Unknown", "High", "Moderate", "Low", "Distorted", "Mixed") else 0, key=f"{prefix}_q26_quality")
        q26_dist = st.text_area("ROIC distortion summary", value=str(record.get("q26", {}).get("distortion_summary", "")), key=f"{prefix}_q26_dist")
        q26_inc = st.selectbox("Incremental ROIC — Analyst", ("Unknown", "High", "Moderate", "Low", "Negative", "Mixed"), index=("Unknown", "High", "Moderate", "Low", "Negative", "Mixed").index(str(record.get("q26", {}).get("incremental_roic_assessment", "Unknown"))) if str(record.get("q26", {}).get("incremental_roic_assessment", "Unknown")) in ("Unknown", "High", "Moderate", "Low", "Negative", "Mixed") else 0, key=f"{prefix}_q26_inc")
        q26_runway = st.selectbox("Reinvestment Runway — Analyst", ("Unknown", "Long", "Medium", "Short", "None"), index=("Unknown", "Long", "Medium", "Short", "None").index(str(record.get("q26", {}).get("reinvestment_runway", "Unknown"))) if str(record.get("q26", {}).get("reinvestment_runway", "Unknown")) in ("Unknown", "Long", "Medium", "Short", "None") else 0, key=f"{prefix}_q26_runway")
        q26_sus = st.selectbox("Sustainability — Analyst", ("Unknown", "Durable", "Questionable", "Deteriorating", "Mixed"), index=("Unknown", "Durable", "Questionable", "Deteriorating", "Mixed").index(str(record.get("q26", {}).get("sustainability", "Unknown"))) if str(record.get("q26", {}).get("sustainability", "Unknown")) in ("Unknown", "Durable", "Questionable", "Deteriorating", "Mixed") else 0, key=f"{prefix}_q26_sus")
        q26_conclusion = st.text_area("Q26 Analyst Conclusion", value=str(record.get("q26", {}).get("conclusion", "")), key=f"{prefix}_q26_conclusion")

    with st.expander("🔎 Evidence Matrix + Research Gaps", expanded=False):
        evidence_df = _editor("Evidence Matrix", record.get("evidence_matrix", []), EVIDENCE_COLUMNS, f"{prefix}_evidence", 300)
        gaps_df = _editor("Research Gaps", record.get("research_gaps_table", []), RESEARCH_GAP_COLUMNS, f"{prefix}_gaps", 260)

    # Cross-chapter consistency uses Chapter 4 if available. It is advisory only.
    chapter4_record = None
    try:
        from modules.deep_company_analysis.chapter4 import load_record as load_chapter4_record
        chapter4_record = load_chapter4_record(safe, company_name)
    except Exception:
        chapter4_record = None
    checks = cross_question_checks(record, chapter4_record)
    with st.expander(f"🧭 Cross-Question Consistency Check ({len(checks)})", expanded=bool(checks)):
        if checks:
            for item in checks:
                st.warning(item)
        else:
            st.caption("Chưa phát hiện contradiction theo các rule Phase 5A. Đây không phải xác nhận rằng phân tích đã hoàn chỉnh.")

    st.markdown("### Chapter 5 Synthesis")
    top_strengths = st.text_area("Top operating/financial strengths", value=str(record.get("top_operating_strengths", "")), key=f"{prefix}_top_strengths")
    top_weaknesses = st.text_area("Top operating/financial weaknesses", value=str(record.get("top_operating_weaknesses", "")), key=f"{prefix}_top_weaknesses")
    deterioration = st.text_area("Deterioration Watch", value=str(record.get("deterioration_watch", "")), key=f"{prefix}_deterioration")
    critical_unknowns = st.text_area("Critical Unknowns", value=str(record.get("critical_unknowns", "")), key=f"{prefix}_unknowns")
    analyst_summary = st.text_area("Analyst Summary — Chapter 5", value=str(record.get("analyst_summary", "")), key=f"{prefix}_summary")

    c1, c2 = st.columns(2)
    save_clicked = c1.button("💾 Lưu Chương 5", use_container_width=True, key=f"{prefix}_save")
    snapshot_clicked = c2.button("📸 Lưu Snapshot Chương 5", use_container_width=True, key=f"{prefix}_snapshot")

    if save_clicked or snapshot_clicked:
        new_record = deepcopy(record)
        new_record["ticker"] = safe
        new_record["company_name"] = company_name or new_record.get("company_name", "")
        new_record["question_status"] = {"Q21": q21_status, "Q22": q22_status, "Q23": q23_status, "Q24": q24_status, "Q25": q25_status, "Q26": q26_status}
        new_record["question_trend"] = {"Q21": q21_trend, "Q22": q22_trend, "Q23": q23_trend, "Q24": q24_trend, "Q25": q25_trend, "Q26": q26_trend}
        new_record["q21_fundamentals"] = _to_records(q21_df, FUNDAMENTAL_COLUMNS)
        new_record["q21"].update({"fundamentals_summary": q21_summary, "most_important_driver": q21_key, "deteriorating_driver": q21_det, "overall_assessment": q21_ass, "conclusion": q21_conclusion})
        new_record["q22_metrics"] = _to_records(q22_df, METRIC_COLUMNS)
        new_record["q22_metric_history"] = _to_records(q22_hist_df, METRIC_HISTORY_COLUMNS)
        new_record["q22"].update({"critical_metrics_summary": q22_summary, "definition_compatibility_note": q22_compat, "temporary_vs_structural_summary": q22_temp, "overall_assessment": q22_ass, "conclusion": q22_conclusion})
        new_record["q23_risks"] = ensure_shearn_risks(_to_records(risk_df, RISK_COLUMNS))
        new_record["q23"].update({"most_material_risk": q23_material, "largest_unknown_risk": q23_unknown, "downside_scenario_link": q23_downside, "overall_assessment": q23_ass, "conclusion": q23_conclusion})
        new_record["q24_inflation_exposures"] = _to_records(q24_df, INFLATION_COLUMNS)
        new_record["q24"].update({"pricing_pass_through": q24_pricing, "cost_flexibility": q24_cost, "capital_replacement_burden": q24_capex, "debt_interest_exposure": q24_debt, "inflation_resilience": q24_res, "main_vulnerability": q24_vuln, "main_protection": q24_prot, "conclusion": q24_conclusion})
        new_record["q25_debt_instruments"] = _to_records(q25_debt_df, DEBT_COLUMNS)
        new_record["q25_off_balance_obligations"] = _to_records(q25_off_df, OFF_BS_COLUMNS)
        new_record["q25_covenants"] = _to_records(q25_cov_df, COVENANT_COLUMNS)
        new_record["q25"].update({"debt_motivation": q25_mot, "cash_flow_stability": q25_cfs, "liquidity": q25_liq, "refinancing_risk": q25_refi, "covenant_risk": q25_cov, "financial_flexibility": q25_flex, "balance_sheet_assessment": q25_ass, "main_strength": q25_strength, "main_weakness": q25_weak, "conclusion": q25_conclusion})
        new_record["q26_roic_variants"] = _to_records(q26_var_df, ROIC_VARIANT_COLUMNS)
        new_record["q26_roic_adjustments"] = _to_records(q26_adj_df, ROIC_ADJUSTMENT_COLUMNS)
        new_record["q26_reinvestment"] = _to_records(q26_reinv_df, REINVESTMENT_COLUMNS)
        new_record["q26"].update({"selected_analytical_method": q26_method, "current_roic_quality": q26_quality, "distortion_summary": q26_dist, "incremental_roic_assessment": q26_inc, "reinvestment_runway": q26_runway, "sustainability": q26_sus, "conclusion": q26_conclusion})
        new_record["evidence_matrix"] = _to_records(evidence_df, EVIDENCE_COLUMNS)
        new_record["research_gaps_table"] = _to_records(gaps_df, RESEARCH_GAP_COLUMNS)
        new_record["top_operating_strengths"] = top_strengths
        new_record["top_operating_weaknesses"] = top_weaknesses
        new_record["deterioration_watch"] = deterioration
        new_record["critical_unknowns"] = critical_unknowns
        new_record["analyst_summary"] = analyst_summary
        save_record(new_record, create_snapshot=snapshot_clicked)
        st.success("Đã lưu Chương 5" + (" + snapshot." if snapshot_clicked else "."))

    with st.expander("🕘 Version History", expanded=False):
        history = load_snapshots(safe)
        if history.empty:
            st.caption("Chưa có snapshot Chương 5.")
        else:
            st.dataframe(history, use_container_width=True, hide_index=True)

    st.caption("Phase 5A guardrails: " + " | ".join(f"{k}={v}" for k, v in guardrails().items()))
