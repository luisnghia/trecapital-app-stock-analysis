from __future__ import annotations

"""Shearn Chapter 4 — Business & Industry Strength (approved Phase 4A core).

Source-locked analyst workspace for Q15–Q20 from *The Investment Checklist*.
Phase 4A intentionally contains no automatic moat/pricing/industry conclusions.
AI/Data bridges arrive in later phases and may only suggest evidence/data, never
overwrite analyst assessment, trend, confidence or conclusion.
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
DB_PATH = APP_DIR / "data_cache" / "deep_company_analysis_chapter4.db"

STATUS_LABELS = {
    "understood": "🟢 Understood",
    "partial": "🟡 Partially Understood",
    "not_understood": "🔴 Not Yet Understood",
}
QUESTION_KEYS = ("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")

# Q15 — the six common sources presented by Shearn + one explicit analyst-defined extension.
Q15_SOURCES = (
    ("Network Economics", "Shearn"),
    ("Brand Loyalty", "Shearn"),
    ("Patents", "Shearn"),
    ("Regulatory Licenses", "Shearn"),
    ("Switching Costs", "Shearn"),
    ("Cost Advantages — Scale / Location / Unique Asset", "Shearn"),
    ("Other Source — Analyst-defined", "Analyst-defined"),
)

ADVANTAGE_COLUMNS = [
    "Specific Advantage",
    "Economic Mechanism",
    "Supporting Evidence",
    "Counter-Evidence",
    "Competitor Comparison",
    "Copyability",
    "Time to Copy/Replace",
    "Structural Character",
    "Current Strength",
    "Trend",
    "Why Trend?",
    "Primary Erosion Threat",
    "Reinvestment Inside Advantage",
    "Confidence",
    "Conclusion",
]
PRICING_EVENT_COLUMNS = [
    "Period", "Product / Segment", "Price Increase %", "Volume Change %",
    "Retention / Churn Change", "Cost Inflation %", "Gross Margin %",
    "EBIT Margin %", "Competitor Price Change", "Nature",
    "Evidence", "Analyst Interpretation",
]
PRICING_SEGMENT_COLUMNS = [
    "Segment / Product", "Revenue Relevance", "Profit Relevance",
    "Pricing Power", "Trend", "Evidence",
]
INDUSTRY_PEER_COLUMNS = [
    "Company", "ROIC Latest", "ROIC 5Y Median", "ROIC 10Y Median",
    "ROIC Min", "ROIC Max", "EBIT Margin", "CCC", "Comment",
]
INDUSTRY_FACTOR_COLUMNS = [
    "Factor", "Origin", "Current Assessment", "Supporting Evidence",
    "Counter-Evidence", "Trend", "Structural / Temporary", "Analyst Conclusion",
]
INDUSTRY_EVENT_COLUMNS = [
    "Period", "Event / Force", "Category", "Origin", "Industry Before",
    "What Changed", "Industry After", "Impact on Demand", "Impact on Supply",
    "Impact on Pricing", "Impact on Margin", "Impact on ROIC",
    "Impact on Competition", "Winners", "Losers", "Structural / Temporary",
    "Evidence", "Analyst Interpretation",
]
COMPETITOR_COLUMNS = [
    "Competitor", "Type", "Segment", "Geography", "Market Share",
    "Customer Overlap", "Key Strength", "Key Weakness", "Status", "Trend", "Evidence",
]
COMPETITION_MODE_COLUMNS = [
    "Competition Mode", "Origin", "Current Importance", "Target Position",
    "Best Competitor", "Supporting Evidence", "Counter-Evidence", "Trend",
    "What Could Change It?", "Analyst Conclusion",
]
SUBSTITUTE_COLUMNS = [
    "Substitute", "Function Replaced", "Price Advantage", "Performance Advantage",
    "Convenience Advantage", "Adoption Level", "Adoption Trend",
    "Time to Meaningful Threat", "Target Response", "Threat", "Evidence",
]
IDEAL_BUSINESS_COLUMNS = [
    "Ideal Characteristic", "Ideal Source", "Target", "Gap", "Analyst Interpretation",
]
FAILURE_COLUMNS = [
    "Competitor", "Failure Period", "What Happened", "Root Cause",
    "Early Warning Signs", "Strategy Error", "Operating Error",
    "Financial Consequences", "Target Exposed?", "What Changed Since?", "Analyst Lesson",
]
SUPPLIER_COLUMNS = [
    "Supplier / Group", "Input", "% Supply if Disclosed", "Criticality",
    "Alternative", "Switching Time", "Geography", "Reliability",
    "Relationship", "Trend", "Capacity Risk", "Financial Health",
    "Disruption History", "Evidence",
]
COMMODITY_COLUMNS = [
    "Commodity", "Business Use", "% COGS if Disclosed", "Historical Volatility",
    "Current Price Trend", "Pass-through Ability", "Lag to Pass Through",
    "Hedge", "Hedge Duration", "Alternatives", "Earnings Sensitivity",
    "Analyst Assessment", "Evidence",
]
EVIDENCE_COLUMNS = [
    "Question", "Claim", "Evidence Type", "Source Title", "Source URL / File",
    "Source Date", "Period", "Evidence Text", "Direction",
    "Status", "Data Origin", "Analyst Note",
]
RESEARCH_GAP_COLUMNS = [
    "Question", "Research Gap", "Materiality", "Next Action", "Status", "Analyst Note",
]

CHILD_TABLES: dict[str, str] = {
    "q15_advantages": "chapter4_advantages",
    "q15_advantage_history": "chapter4_advantage_history",
    "q16_pricing_events": "chapter4_pricing_events",
    "q16_pricing_segments": "chapter4_pricing_segments",
    "q17_industry_peers": "chapter4_industry_peers",
    "q17_industry_factors": "chapter4_industry_factors",
    "q18_industry_events": "chapter4_industry_events",
    "q19_competitors": "chapter4_competitors",
    "q19_competition_modes": "chapter4_competition_modes",
    "q19_substitutes": "chapter4_substitutes",
    "q19_ideal_business": "chapter4_ideal_business",
    "q19_competitor_failures": "chapter4_competitor_failures",
    "q20_suppliers": "chapter4_suppliers",
    "q20_commodity_exposure": "chapter4_commodity_exposure",
    "evidence_matrix": "chapter4_evidence",
    "research_gaps_table": "chapter4_research_gaps",
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
            CREATE TABLE IF NOT EXISTS chapter4_current (
                ticker TEXT PRIMARY KEY,
                company_name TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{{}}',
                understanding_status TEXT NOT NULL DEFAULT 'not_understood',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chapter4_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                understanding_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chapter4_snapshots_ticker
                ON chapter4_snapshots(ticker);
            {child_sql}
            """
        )


def _empty_source_state() -> dict[str, Any]:
    return {
        "current_assessment": "Unknown",
        "trend": "Unknown",
        "source_summary": "",
        "advantages": [],
    }


def empty_payload(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": _safe_ticker(ticker),
        "company_name": company_name or "",
        "q15": {
            "sources": {name: _empty_source_state() for name, _ in Q15_SOURCES},
            "sustainable_advantage": "Unknown",
            "primary_sources": "",
            "strongest_advantage": "",
            "advantage_expanding_most": "",
            "advantage_deteriorating_most": "",
            "overall_moat_trend": "Unknown",
            "copy_replace_threat": "",
            "technology_threat": "",
            "regulatory_threat": "",
            "right_place_right_time_risk": "",
            "strongest_counter_evidence": "",
            "reinvestment_runway": "Unknown",
            "confidence": "Unknown",
            "conclusion": "",
        },
        "q15_advantages": [],
        "q15_advantage_history": [],
        "q16": {
            "retention": {"evidence": "", "trend": "Unknown", "analyst_interpretation": ""},
            "price_sensitivity": {"evidence": "", "trend": "Unknown", "analyst_interpretation": ""},
            "customer_economics": {"evidence": "", "trend": "Unknown", "analyst_interpretation": ""},
            "quality_vs_price": {"evidence": "", "trend": "Unknown", "analyst_interpretation": ""},
            "price_transparency": {"evidence": "", "trend": "Unknown", "analyst_interpretation": ""},
            "pricing_power": "Unknown",
            "nature": "Unknown",
            "scope": "Unknown",
            "trend": "Unknown",
            "best_evidence": "",
            "strongest_counter_evidence": "",
            "main_erosion_threat": "",
            "confidence": "Unknown",
            "conclusion": "",
        },
        "q16_pricing_events": [],
        "q16_pricing_segments": [],
        "q17": {
            "industry_economics": "Unknown",
            "ease_of_making_money": "Unknown",
            "roic_structure": "",
            "demand_quality": "",
            "pricing_environment": "",
            "barriers": "",
            "capital_intensity": "",
            "cyclicality": "Unknown",
            "trend": "Unknown",
            "structural_vs_temporary": "",
            "main_positive": "",
            "main_negative": "",
            "target_vs_industry_reason": "",
            "confidence": "Unknown",
            "conclusion": "",
        },
        "q17_industry_peers": [],
        "q17_industry_factors": [
            {"Factor": label, "Origin": "Shearn", "Current Assessment": "", "Supporting Evidence": "", "Counter-Evidence": "", "Trend": "Unknown", "Structural / Temporary": "Unknown", "Analyst Conclusion": ""}
            for label in (
                "What drives the industry?",
                "How do people compete within the industry?",
                "What is the larger macro picture?",
                "What are the industry trends?",
                "Average Cash Conversion Cycle",
                "Exposure to cyclical markets",
                "Ability to pass on price increases",
                "Volatility of customer demand",
            )
        ],
        "q18": {
            "industry_then": "",
            "industry_now": "",
            "current_regime": "",
            "regime_start": "",
            "force_created_regime": "",
            "previous_regime": "",
            "what_broke_previous_economics": "",
            "next_inflection": "",
            "early_change_evidence": "",
            "trend": "Unknown",
            "confidence": "Unknown",
            "conclusion": "",
            "management_claims_vs_history": [],
        },
        "q18_industry_events": [],
        "q19": {
            "limited_competition_note": "",
            "industry_change_frequency": "Unknown",
            "industry_change_note": "",
            "fierceness": "Unknown",
            "fierceness_note": "",
            "foreign_low_cost_threat": "Unknown",
            "foreign_threat_trend": "Unknown",
            "foreign_threat_note": "",
            "competition_intensity": "Unknown",
            "trend": "Unknown",
            "dominant_competition_mode": "",
            "industry_leader": "",
            "target_vs_ideal": "",
            "biggest_direct_threat": "",
            "biggest_substitute_threat": "",
            "irrational_competition_risk": "",
            "most_important_failure_lesson": "",
            "confidence": "Unknown",
            "conclusion": "",
        },
        "q19_competitors": [],
        "q19_competition_modes": [
            {"Competition Mode": label, "Origin": origin, "Current Importance": "", "Target Position": "", "Best Competitor": "", "Supporting Evidence": "", "Counter-Evidence": "", "Trend": "Unknown", "What Could Change It?": "", "Analyst Conclusion": ""}
            for label, origin in (
                ("Capital", "Shearn"),
                ("Service", "Shearn"),
                ("Price", "Shearn"),
                ("Copying", "Shearn"),
                ("Other", "Analyst-defined"),
            )
        ],
        "q19_substitutes": [],
        "q19_ideal_business": [],
        "q19_competitor_failures": [],
        "q20": {
            "supplier_relationship": "Unknown",
            "supply_reliability": "Unknown",
            "supplier_concentration": "Unknown",
            "commodity_dependence": "Unknown",
            "supply_chain_efficiency": "",
            "supplier_innovation": "",
            "trend": "Unknown",
            "biggest_supply_risk": "",
            "biggest_supplier_strength": "",
            "confidence": "Unknown",
            "conclusion": "",
        },
        "q20_suppliers": [],
        "q20_commodity_exposure": [],
        "supplier_innovation_records": [],
        "evidence_matrix": [],
        "research_gaps_table": [],
        "top_business_strengths": "",
        "top_business_weaknesses": "",
        "deterioration_watch": "",
        "improvement_watch": "",
        "critical_unknowns": "",
        "analyst_summary": "",
    }


def _merge_dict(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def load_record(ticker: str, company_name: str = "") -> dict[str, Any]:
    init_db()
    ticker = _safe_ticker(ticker)
    base = empty_payload(ticker, company_name)
    if not ticker:
        return base
    with _connect() as conn:
        row = conn.execute("SELECT * FROM chapter4_current WHERE ticker = ?", (ticker,)).fetchone()
    if not row:
        return base
    try:
        payload = json.loads(row["payload_json"] or "{}")
    except Exception:
        payload = {}
    merged = _merge_dict(base, payload if isinstance(payload, dict) else {})
    merged["ticker"] = ticker
    merged["company_name"] = row["company_name"] or merged.get("company_name", "")
    merged["_exists"] = True
    return merged


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _nonempty_rows(rows: Any) -> bool:
    if not isinstance(rows, list):
        return False
    return any(isinstance(row, dict) and any(_has_text(v) for v in row.values()) for row in rows)


def question_statuses(payload: dict[str, Any]) -> dict[str, str]:
    def status(primary: bool, conclusion: bool, supporting: bool = False) -> str:
        if primary and conclusion:
            return "Answered"
        if primary or conclusion or supporting:
            return "Partial"
        return "Unknown"

    q15, q16, q17, q18, q19, q20 = (payload.get(k, {}) for k in ("q15", "q16", "q17", "q18", "q19", "q20"))
    return {
        "Q15": status(str(q15.get("sustainable_advantage") or "Unknown") != "Unknown", _has_text(q15.get("conclusion")), _nonempty_rows(payload.get("q15_advantages"))),
        "Q16": status(str(q16.get("pricing_power") or "Unknown") != "Unknown", _has_text(q16.get("conclusion")), _nonempty_rows(payload.get("q16_pricing_events")) or _nonempty_rows(payload.get("q16_pricing_segments"))),
        "Q17": status(str(q17.get("industry_economics") or "Unknown") != "Unknown", _has_text(q17.get("conclusion")), _nonempty_rows(payload.get("q17_industry_peers"))),
        "Q18": status(str(q18.get("trend") or "Unknown") != "Unknown", _has_text(q18.get("conclusion")), _nonempty_rows(payload.get("q18_industry_events"))),
        "Q19": status(str(q19.get("competition_intensity") or "Unknown") != "Unknown", _has_text(q19.get("conclusion")), _nonempty_rows(payload.get("q19_competitors"))),
        "Q20": status(str(q20.get("supplier_relationship") or "Unknown") != "Unknown", _has_text(q20.get("conclusion")), _nonempty_rows(payload.get("q20_suppliers")) or _nonempty_rows(payload.get("q20_commodity_exposure"))),
    }


def understanding_status(payload: dict[str, Any]) -> str:
    statuses = question_statuses(payload)
    answered = sum(1 for value in statuses.values() if value == "Answered")
    if answered == len(QUESTION_KEYS):
        return "understood"
    if any(value != "Unknown" for value in statuses.values()):
        return "partial"
    return "not_understood"


def _replace_child_rows(conn: sqlite3.Connection, ticker: str, table: str, rows: Any, now: str) -> None:
    conn.execute(f"DELETE FROM {table} WHERE ticker = ?", (ticker,))
    if not isinstance(rows, list):
        return
    clean_rows = [row for row in rows if isinstance(row, dict) and any(_has_text(v) for v in row.values())]
    for pos, row in enumerate(clean_rows):
        conn.execute(
            f"INSERT INTO {table} (ticker, position, row_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (ticker, pos, json.dumps(row, ensure_ascii=False), now, now),
        )


def save_record(payload: dict[str, Any]) -> str:
    init_db()
    ticker = _safe_ticker(payload.get("ticker", ""))
    if not ticker:
        raise ValueError("Ticker is required")
    payload = deepcopy(payload)
    payload.pop("_exists", None)
    payload["ticker"] = ticker
    company_name = str(payload.get("company_name") or "")
    status = understanding_status(payload)
    now = _now()
    serialized = json.dumps(payload, ensure_ascii=False)
    with _connect() as conn:
        old = conn.execute("SELECT created_at FROM chapter4_current WHERE ticker = ?", (ticker,)).fetchone()
        created_at = old["created_at"] if old else now
        conn.execute(
            """
            INSERT INTO chapter4_current (ticker, company_name, payload_json, understanding_status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                company_name=excluded.company_name,
                payload_json=excluded.payload_json,
                understanding_status=excluded.understanding_status,
                updated_at=excluded.updated_at
            """,
            (ticker, company_name, serialized, status, created_at, now),
        )
        for payload_key, table in CHILD_TABLES.items():
            _replace_child_rows(conn, ticker, table, payload.get(payload_key, []), now)
        conn.execute(
            "INSERT INTO chapter4_snapshots (ticker, payload_json, understanding_status, created_at) VALUES (?, ?, ?, ?)",
            (ticker, serialized, status, now),
        )
    return status


def load_history(ticker: str) -> pd.DataFrame:
    init_db()
    ticker = _safe_ticker(ticker)
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, understanding_status, created_at FROM chapter4_snapshots WHERE ticker = ? ORDER BY id DESC",
            (ticker,),
        ).fetchall()
    return pd.DataFrame([
        {
            "Snapshot": row["id"],
            "Understanding": STATUS_LABELS.get(row["understanding_status"], row["understanding_status"]),
            "Thời điểm": row["created_at"],
        }
        for row in rows
    ])


def _rows_to_df(rows: Any, columns: list[str]) -> pd.DataFrame:
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns].fillna("")


def _df_to_rows(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    rows = []
    for row in df.fillna("").to_dict(orient="records"):
        if any(_has_text(v) for v in row.values()):
            rows.append(row)
    return rows


def _select(label: str, value: str, options: list[str], key: str, help: str | None = None) -> str:
    current = value if value in options else options[0]
    return st.selectbox(label, options, index=options.index(current), key=key, help=help)


def _editor(label: str, rows: Any, columns: list[str], key: str, height: int = 260) -> list[dict[str, Any]]:
    st.markdown(f"**{label}**")
    edited = st.data_editor(
        _rows_to_df(rows, columns),
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        height=height,
        key=key,
    )
    return _df_to_rows(edited)


def _render_intro() -> None:
    with st.expander("📕 Hướng dẫn sử dụng Chương 4 — Lợi thế doanh nghiệp & Cấu trúc ngành", expanded=True):
        st.markdown(
            """
**Mục tiêu:** hiểu liệu economics của doanh nghiệp có được bảo vệ bởi lợi thế cạnh tranh, pricing power, economics ngành, cấu trúc cạnh tranh và quan hệ nhà cung cấp hay không.

**Nguyên tắc:** Chương 4 không tạo *Moat Score* hay *Chapter Score*. Mỗi câu Q15–Q20 được phân rã theo logic của Michael Shearn; Trecapital chỉ quản lý evidence, counter-evidence, trend, history và các analytical records. **Current Assessment, Trend, Confidence và Conclusion là quyết định của Analyst.**

**Phase 4A:** đây là Source-Locked Core. Chưa có Research Assistant tự kết luận. Phase 4B/4C sau này mới nối canonical data và evidence nhưng không được ghi đè analyst work.
"""
        )


def _render_dashboard(payload: dict[str, Any]) -> None:
    statuses = question_statuses(payload)
    answered = sum(v == "Answered" for v in statuses.values())
    partial = sum(v == "Partial" for v in statuses.values())
    unknown = sum(v == "Unknown" for v in statuses.values())
    evidence_rows = payload.get("evidence_matrix", []) or []
    counter = sum(
        1 for row in evidence_rows
        if isinstance(row, dict) and str(row.get("Direction") or "").lower().startswith(("contr", "phản", "phan"))
    )
    cols = st.columns(5)
    cols[0].metric("Q Answered", f"{answered}/6")
    cols[1].metric("Partial", partial)
    cols[2].metric("Critical Unknowns", unknown)
    cols[3].metric("Evidence records", len(evidence_rows))
    cols[4].metric("Counter-evidence", counter)
    st.caption("Các chỉ số trên đo research completeness/evidence management, không phải chất lượng khoản đầu tư.")


def _render_q15(payload: dict[str, Any], ticker: str) -> None:
    q = payload["q15"]
    st.markdown("## Q15 — Doanh nghiệp có lợi thế cạnh tranh bền vững không và nguồn gốc là gì?")
    st.caption("Đi từ từng nguồn lợi thế → từng lợi thế cụ thể → copy/replace test → xu hướng mở rộng/suy yếu → counter-evidence → analyst conclusion.")

    for idx, (source, origin) in enumerate(Q15_SOURCES, start=1):
        source_state = q["sources"].setdefault(source, _empty_source_state())
        with st.expander(f"Nguồn {idx}: {source} · {origin}", expanded=False):
            if source == "Network Economics":
                st.caption("Kiểm tra: utility có tăng theo số/chất lượng participants? critical mass? multi-homing? network đang tự củng cố hay suy yếu?")
            elif source == "Brand Loyalty":
                st.caption("Kiểm tra: brand đại diện điều gì, loyalty thật hay awareness, premium price, repeat purchase, discount dependence và brand erosion.")
            elif source == "Patents":
                st.caption("Kiểm tra commercial value, expiry, technology bypass/obsolescence, revenue/profit relevance nếu disclosure có.")
            elif source == "Regulatory Licenses":
                st.caption("Kiểm tra regulator, số lượng license, time/cost to obtain, price/capacity controls và legislative threats.")
            elif source == "Switching Costs":
                st.caption("Kiểm tra tiền mặt, retraining, migration/integration, operational risk, embeddedness, time-to-switch và retention evidence.")
            elif source.startswith("Cost Advantages"):
                st.caption("Kiểm tra Scale / Industry Consolidation / Location / Unique Asset Access và cost gap thực tế; không suy moat chỉ từ gross margin cao.")
            else:
                st.caption("Analyst-defined: phải giải thích vì sao không phù hợp 6 nguồn Shearn và vẫn đi qua cùng copyability/durability tests.")

            c1, c2 = st.columns(2)
            source_state["current_assessment"] = _select(
                "Đánh giá nguồn", source_state.get("current_assessment", "Unknown"),
                ["Unknown", "Không có", "Strength only", "Potential Advantage", "Sustainable Advantage"],
                f"ch4_q15_src_assess_{ticker}_{idx}",
            )
            source_state["trend"] = _select(
                "Trend", source_state.get("trend", "Unknown"),
                ["Unknown", "Expanding", "Stable", "Deteriorating", "Mixed"],
                f"ch4_q15_src_trend_{ticker}_{idx}",
            )
            source_state["source_summary"] = st.text_area(
                "Tóm tắt analyst cho nguồn này", value=str(source_state.get("source_summary") or ""),
                key=f"ch4_q15_src_summary_{ticker}_{idx}", height=90,
            )

    payload["q15_advantages"] = _editor(
        "Moat Copyability Analyzer — từng lợi thế cụ thể (Table 4.1 implementation)",
        payload.get("q15_advantages"), ADVANTAGE_COLUMNS,
        f"ch4_q15_adv_{ticker}", height=330,
    )
    payload["q15_advantage_history"] = _editor(
        "Advantage Trend History", payload.get("q15_advantage_history"),
        ["Review Period", "Specific Advantage", "Source", "Current Strength", "Trend", "Evidence New", "What Changed?"],
        f"ch4_q15_hist_{ticker}", height=220,
    )

    c1, c2, c3 = st.columns(3)
    q["sustainable_advantage"] = _select("Sustainable Competitive Advantage Exists", q.get("sustainable_advantage", "Unknown"), ["Unknown", "Yes", "Partial", "No"], f"ch4_q15_overall_{ticker}")
    q["overall_moat_trend"] = _select("Overall Moat Trend", q.get("overall_moat_trend", "Unknown"), ["Unknown", "Expanding", "Stable", "Deteriorating", "Mixed"], f"ch4_q15_overall_trend_{ticker}")
    q["reinvestment_runway"] = _select("Reinvestment Runway Inside the Moat", q.get("reinvestment_runway", "Unknown"), ["Unknown", "Long", "Medium", "Short", "None"], f"ch4_q15_runway_{ticker}")
    q["primary_sources"] = st.text_area("Primary Source(s) of Advantage", value=str(q.get("primary_sources") or ""), key=f"ch4_q15_primary_{ticker}", height=70)
    q["strongest_advantage"] = st.text_area("Lợi thế quan trọng nhất", value=str(q.get("strongest_advantage") or ""), key=f"ch4_q15_strongest_{ticker}", height=70)
    q["advantage_expanding_most"] = st.text_area("Lợi thế đang mở rộng mạnh nhất", value=str(q.get("advantage_expanding_most") or ""), key=f"ch4_q15_expand_{ticker}", height=70)
    q["advantage_deteriorating_most"] = st.text_area("Lợi thế đang suy yếu", value=str(q.get("advantage_deteriorating_most") or ""), key=f"ch4_q15_deteriorate_{ticker}", height=70)
    q["copy_replace_threat"] = st.text_area("Khả năng bị copy/replace tổng thể", value=str(q.get("copy_replace_threat") or ""), key=f"ch4_q15_copythreat_{ticker}", height=70)
    q["technology_threat"] = st.text_area("Technology Disruption Risk", value=str(q.get("technology_threat") or ""), key=f"ch4_q15_tech_{ticker}", height=70)
    q["regulatory_threat"] = st.text_area("Regulatory Threat", value=str(q.get("regulatory_threat") or ""), key=f"ch4_q15_reg_{ticker}", height=70)
    q["right_place_right_time_risk"] = st.text_area("Right Place / Right Time Risk", value=str(q.get("right_place_right_time_risk") or ""), key=f"ch4_q15_luck_{ticker}", height=70)
    q["strongest_counter_evidence"] = st.text_area("Most Important Counter-Evidence", value=str(q.get("strongest_counter_evidence") or ""), key=f"ch4_q15_counter_{ticker}", height=80)
    q["confidence"] = _select("Analyst Confidence", q.get("confidence", "Unknown"), ["Unknown", "Low", "Medium", "High"], f"ch4_q15_conf_{ticker}")
    q["conclusion"] = st.text_area("Q15 Analyst Conclusion", value=str(q.get("conclusion") or ""), key=f"ch4_q15_conclusion_{ticker}", height=130)


def _render_q16(payload: dict[str, Any], ticker: str) -> None:
    q = payload["q16"]
    st.markdown("## Q16 — Doanh nghiệp có thể tăng giá mà không mất khách hàng không?")
    st.caption("Phân biệt True Pricing Power với Cost Pass-through và Commodity/Shortage Pricing; đánh giá theo actual pricing events và phạm vi segment.")
    for key, label, note in (
        ("retention", "1. High Customer Retention", "Link evidence từ Chương 3 Q10; retention cao chỉ là evidence, không tự kết luận pricing power."),
        ("price_sensitivity", "2. Low Price Sensitivity", "Xem product cost trong customer budget, tender/price comparison, phản ứng volume và alternatives."),
        ("customer_economics", "3. Profitable Customer Business Models", "Đặc biệt với B2B: customer profitability, procurement pressure và health of customer industry."),
        ("quality_vs_price", "4. Quality More Important Than Price", "Xem hậu quả của failure, qualification/specification, premium willingness và peer quality gap."),
        ("price_transparency", "5. Technology / Price Transparency Threat", "Marketplace, procurement digitization, search cost, price dispersion và switching ease."),
    ):
        with st.expander(label, expanded=False):
            st.caption(note)
            block = q.setdefault(key, {"evidence": "", "trend": "Unknown", "analyst_interpretation": ""})
            block["evidence"] = st.text_area("Evidence / data", value=str(block.get("evidence") or ""), key=f"ch4_q16_{key}_ev_{ticker}", height=90)
            block["trend"] = _select("Trend", block.get("trend", "Unknown"), ["Unknown", "Improving", "Stable", "Deteriorating", "Mixed"], f"ch4_q16_{key}_trend_{ticker}")
            block["analyst_interpretation"] = st.text_area("Analyst interpretation", value=str(block.get("analyst_interpretation") or ""), key=f"ch4_q16_{key}_note_{ticker}", height=80)

    payload["q16_pricing_events"] = _editor("Pricing Event Timeline — mỗi lần tăng giá là một record", payload.get("q16_pricing_events"), PRICING_EVENT_COLUMNS, f"ch4_q16_events_{ticker}", height=320)
    payload["q16_pricing_segments"] = _editor("Scope of Pricing Power — theo segment/product", payload.get("q16_pricing_segments"), PRICING_SEGMENT_COLUMNS, f"ch4_q16_segments_{ticker}", height=220)

    q["pricing_power"] = _select("Pricing Power", q.get("pricing_power", "Unknown"), ["Unknown", "Strong", "Moderate", "Weak", "None"], f"ch4_q16_power_{ticker}")
    q["nature"] = _select("Nature", q.get("nature", "Unknown"), ["Unknown", "Structural", "Temporary", "Cost-pass-through", "Commodity / Shortage", "Mixed"], f"ch4_q16_nature_{ticker}")
    q["scope"] = _select("Scope", q.get("scope", "Unknown"), ["Unknown", "Company-wide", "Segment-specific"], f"ch4_q16_scope_{ticker}")
    q["trend"] = _select("Trend", q.get("trend", "Unknown"), ["Unknown", "Expanding", "Stable", "Deteriorating", "Mixed"], f"ch4_q16_trend_{ticker}")
    q["best_evidence"] = st.text_area("Best Evidence", value=str(q.get("best_evidence") or ""), key=f"ch4_q16_best_{ticker}", height=80)
    q["strongest_counter_evidence"] = st.text_area("Strongest Counter-Evidence", value=str(q.get("strongest_counter_evidence") or ""), key=f"ch4_q16_counter_{ticker}", height=80)
    q["main_erosion_threat"] = st.text_area("Main Erosion Threat", value=str(q.get("main_erosion_threat") or ""), key=f"ch4_q16_threat_{ticker}", height=70)
    q["confidence"] = _select("Analyst Confidence", q.get("confidence", "Unknown"), ["Unknown", "Low", "Medium", "High"], f"ch4_q16_conf_{ticker}")
    q["conclusion"] = st.text_area("Q16 Analyst Conclusion", value=str(q.get("conclusion") or ""), key=f"ch4_q16_conclusion_{ticker}", height=130)


def _render_q17(payload: dict[str, Any], ticker: str) -> None:
    q = payload["q17"]
    st.markdown("## Q17 — Doanh nghiệp hoạt động trong ngành tốt hay xấu?")
    st.caption("Câu hỏi trung tâm: trong ngành này kiếm tiền có dễ không? Không dùng ROIC của một doanh nghiệp để đại diện cả ngành.")
    payload["q17_industry_peers"] = _editor("Industry ROIC Distribution / Peer Economics", payload.get("q17_industry_peers"), INDUSTRY_PEER_COLUMNS, f"ch4_q17_peers_{ticker}", height=280)
    payload["q17_industry_factors"] = _editor("Industry Economics Factors — các nhóm Shearn/Lister + Analyst-defined nếu cần", payload.get("q17_industry_factors"), INDUSTRY_FACTOR_COLUMNS, f"ch4_q17_factors_{ticker}", height=300)
    st.caption("Khi phân tích Best vs Worst, hãy trả lời: vì sao Best kiếm tiền tốt còn Worst không, và khác biệt đến từ company-specific advantage hay economics ngành?")

    q["industry_economics"] = _select("Industry Economics", q.get("industry_economics", "Unknown"), ["Unknown", "Good", "Mixed", "Bad"], f"ch4_q17_econ_{ticker}")
    q["ease_of_making_money"] = _select("Ease of Making Money", q.get("ease_of_making_money", "Unknown"), ["Unknown", "Easy", "Moderate", "Difficult"], f"ch4_q17_easy_{ticker}")
    q["trend"] = _select("Industry Trend", q.get("trend", "Unknown"), ["Unknown", "Improving", "Stable", "Deteriorating", "Mixed"], f"ch4_q17_trend_{ticker}")
    q["cyclicality"] = _select("Cyclicality", q.get("cyclicality", "Unknown"), ["Unknown", "Low", "Moderate", "High"], f"ch4_q17_cycle_{ticker}")
    for key, label in (
        ("roic_structure", "ROIC Structure"), ("demand_quality", "Demand Quality"),
        ("pricing_environment", "Pricing Environment"), ("barriers", "Barriers"),
        ("capital_intensity", "Capital Intensity"), ("structural_vs_temporary", "Structural vs Temporary Drivers"),
        ("main_positive", "Main Positive"), ("main_negative", "Main Negative"),
        ("target_vs_industry_reason", "Target tốt vì ngành tốt hay vì doanh nghiệp tốt hơn một ngành khó?"),
    ):
        q[key] = st.text_area(label, value=str(q.get(key) or ""), key=f"ch4_q17_{key}_{ticker}", height=70)
    q["confidence"] = _select("Analyst Confidence", q.get("confidence", "Unknown"), ["Unknown", "Low", "Medium", "High"], f"ch4_q17_conf_{ticker}")
    q["conclusion"] = st.text_area("Q17 Analyst Conclusion", value=str(q.get("conclusion") or ""), key=f"ch4_q17_conclusion_{ticker}", height=130)


def _render_q18(payload: dict[str, Any], ticker: str) -> None:
    q = payload["q18"]
    st.markdown("## Q18 — Ngành đã tiến hóa như thế nào?")
    st.caption("Nghiên cứu >10 năm; tách Industry Then vs Now, regime change và kiểm tra management claims bằng lịch sử ngành.")
    payload["q18_industry_events"] = _editor(
        ">10-Year Industry Evolution Timeline", payload.get("q18_industry_events"), INDUSTRY_EVENT_COLUMNS,
        f"ch4_q18_events_{ticker}", height=360,
    )
    q["industry_then"] = st.text_area("Industry Then", value=str(q.get("industry_then") or ""), key=f"ch4_q18_then_{ticker}", height=100)
    q["industry_now"] = st.text_area("Industry Now", value=str(q.get("industry_now") or ""), key=f"ch4_q18_now_{ticker}", height=100)
    claims = q.get("management_claims_vs_history", [])
    q["management_claims_vs_history"] = _editor(
        "Management Claim vs Industry History", claims,
        ["Management Claim", "Historical Evidence", "Supports?", "Analyst Note"],
        f"ch4_q18_claims_{ticker}", height=220,
    )
    for key, label in (
        ("current_regime", "Current Industry Regime"), ("regime_start", "Regime started when?"),
        ("force_created_regime", "Force that created current regime"), ("previous_regime", "Previous regime"),
        ("what_broke_previous_economics", "What broke previous economics?"),
        ("next_inflection", "Next potential inflection point"), ("early_change_evidence", "Early evidence regime is changing"),
    ):
        q[key] = st.text_area(label, value=str(q.get(key) or ""), key=f"ch4_q18_{key}_{ticker}", height=70)
    q["trend"] = _select("Industry Evolution Assessment", q.get("trend", "Unknown"), ["Unknown", "Improving", "Stable", "Deteriorating", "Structural Transition"], f"ch4_q18_trend_{ticker}")
    q["confidence"] = _select("Analyst Confidence", q.get("confidence", "Unknown"), ["Unknown", "Low", "Medium", "High"], f"ch4_q18_conf_{ticker}")
    q["conclusion"] = st.text_area("Q18 Analyst Conclusion", value=str(q.get("conclusion") or ""), key=f"ch4_q18_conclusion_{ticker}", height=130)


def _render_q19(payload: dict[str, Any], ticker: str) -> None:
    q = payload["q19"]
    st.markdown("## Q19 — Bức tranh cạnh tranh và mức độ cạnh tranh")
    st.caption("Giữ nguyên 8 hướng nghiên cứu của Shearn: limited competition; industry change; competition mode; fierceness; substitutes; low-cost countries; industry standard; failed competitors.")

    with st.expander("Q19.1 — Does the business have limited competition?", expanded=False):
        payload["q19_competitors"] = _editor("Competitor Master Table", payload.get("q19_competitors"), COMPETITOR_COLUMNS, f"ch4_q19_competitors_{ticker}", height=280)
        q["limited_competition_note"] = st.text_area("Analyst note", value=str(q.get("limited_competition_note") or ""), key=f"ch4_q19_limited_{ticker}", height=90)

    with st.expander("Q19.2 — Does the industry change often?", expanded=False):
        q["industry_change_frequency"] = _select("Change frequency", q.get("industry_change_frequency", "Unknown"), ["Unknown", "Low", "Moderate", "High"], f"ch4_q19_changefreq_{ticker}")
        q["industry_change_note"] = st.text_area("Technology/product lifecycle/new entrant/business-model/customer preference evidence", value=str(q.get("industry_change_note") or ""), key=f"ch4_q19_changenote_{ticker}", height=100)

    with st.expander("Q19.3 — How do competitors compete, and how could that change?", expanded=False):
        payload["q19_competition_modes"] = _editor("Competition Modes — Capital / Service / Price / Copying + Analyst-defined", payload.get("q19_competition_modes"), COMPETITION_MODE_COLUMNS, f"ch4_q19_modes_{ticker}", height=300)

    with st.expander("Q19.4 — How fiercely do businesses compete?", expanded=False):
        q["fierceness"] = _select("Fierceness", q.get("fierceness", "Unknown"), ["Unknown", "Easing", "Stable", "Intensifying", "Irrational"], f"ch4_q19_fierce_{ticker}")
        q["fierceness_note"] = st.text_area("Evidence: number/size of competitors, maturity, capacity, price war, below-economic pricing, acquisition/retention costs...", value=str(q.get("fierceness_note") or ""), key=f"ch4_q19_fiercenote_{ticker}", height=100)

    with st.expander("Q19.5 — Substitute products", expanded=False):
        payload["q19_substitutes"] = _editor("Substitute Map", payload.get("q19_substitutes"), SUBSTITUTE_COLUMNS, f"ch4_q19_subs_{ticker}", height=280)

    with st.expander("Q19.6 — Low-cost country competition", expanded=False):
        q["foreign_low_cost_threat"] = _select("Foreign Low-cost Threat", q.get("foreign_low_cost_threat", "Unknown"), ["Unknown", "Low", "Moderate", "High", "Structural"], f"ch4_q19_foreign_{ticker}")
        q["foreign_threat_trend"] = _select("Threat Trend", q.get("foreign_threat_trend", "Unknown"), ["Unknown", "Increasing", "Stable", "Decreasing"], f"ch4_q19_foreigntrend_{ticker}")
        q["foreign_threat_note"] = st.text_area("Compare labor/input/energy/freight/tariff/quality/lead time/delivered cost", value=str(q.get("foreign_threat_note") or ""), key=f"ch4_q19_foreignnote_{ticker}", height=110)

    with st.expander("Q19.7 — Which competitor sets the industry standard? / Ideal Business (Table 4.2)", expanded=False):
        payload["q19_ideal_business"] = _editor("Peer & Ideal Company Analyzer", payload.get("q19_ideal_business"), IDEAL_BUSINESS_COLUMNS, f"ch4_q19_ideal_{ticker}", height=260)

    with st.expander("Q19.8 — Why have competitors failed?", expanded=False):
        payload["q19_competitor_failures"] = _editor("Competitor Failure Analysis", payload.get("q19_competitor_failures"), FAILURE_COLUMNS, f"ch4_q19_fail_{ticker}", height=300)

    q["competition_intensity"] = _select("Competition Intensity", q.get("competition_intensity", "Unknown"), ["Unknown", "Limited", "Moderate", "Intense", "Extreme"], f"ch4_q19_intensity_{ticker}")
    q["trend"] = _select("Overall Competition Trend", q.get("trend", "Unknown"), ["Unknown", "Easing", "Stable", "Intensifying", "Mixed"], f"ch4_q19_trend_{ticker}")
    for key, label in (
        ("dominant_competition_mode", "Dominant Competition Mode"), ("industry_leader", "Industry Leader"),
        ("target_vs_ideal", "Target vs Ideal Business"), ("biggest_direct_threat", "Biggest Direct Threat"),
        ("biggest_substitute_threat", "Biggest Substitute Threat"), ("irrational_competition_risk", "Irrational Competition Risk"),
        ("most_important_failure_lesson", "Most Important Failure Lesson"),
    ):
        q[key] = st.text_area(label, value=str(q.get(key) or ""), key=f"ch4_q19_{key}_{ticker}", height=70)
    q["confidence"] = _select("Analyst Confidence", q.get("confidence", "Unknown"), ["Unknown", "Low", "Medium", "High"], f"ch4_q19_conf_{ticker}")
    q["conclusion"] = st.text_area("Q19 Analyst Conclusion", value=str(q.get("conclusion") or ""), key=f"ch4_q19_conclusion_{ticker}", height=130)


def _render_q20(payload: dict[str, Any], ticker: str) -> None:
    q = payload["q20"]
    st.markdown("## Q20 — Doanh nghiệp có quan hệ như thế nào với nhà cung cấp?")
    st.caption("Không mặc định ép supplier giá thấp là tốt. Đánh giá reliability, innovation, concentration, commodity dependence và economics dài hạn của quan hệ.")

    with st.expander("Q20.1 — Does the business have reliable sources of supply?", expanded=False):
        payload["q20_suppliers"] = _editor("Supplier Map", payload.get("q20_suppliers"), SUPPLIER_COLUMNS, f"ch4_q20_suppliers_{ticker}", height=320)
        st.caption("% Supply chỉ điền khi disclosure có. Không disclosure ≠ diversified supplier base.")

    with st.expander("Supply Chain Management", expanded=False):
        st.caption("Phase 4B sẽ nối Inventory Turnover = COGS / Average Inventory và peer/trend comparison. Ratio không tự kết luận supplier quality.")
        q["supply_chain_efficiency"] = st.text_area("Supply-chain efficiency / inventory / returns / distribution / responsiveness", value=str(q.get("supply_chain_efficiency") or ""), key=f"ch4_q20_chain_{ticker}", height=100)

    with st.expander("Q20.2 — Does the business help suppliers innovate?", expanded=False):
        payload["supplier_innovation_records"] = _editor("Supplier Innovation Records", payload.get("supplier_innovation_records"), ["Supplier", "Joint Initiative", "Customer Feedback Shared", "Result", "Competitive Benefit", "Trend", "Evidence"], f"ch4_q20_innovation_{ticker}", height=240)
        q["supplier_innovation"] = st.text_area("Analyst interpretation", value=str(q.get("supplier_innovation") or ""), key=f"ch4_q20_innovation_note_{ticker}", height=90)

    with st.expander("Q20.3 — Is the business dependent on only a few suppliers?", expanded=False):
        st.caption("Dùng Supplier Map phía trên để ghi từng material supplier, alternatives, qualification/switching time, capacity risk và disruption history.")

    with st.expander("Q20.4 — Commodity resource dependence", expanded=False):
        payload["q20_commodity_exposure"] = _editor("Commodity Exposure Map", payload.get("q20_commodity_exposure"), COMMODITY_COLUMNS, f"ch4_q20_commodity_{ticker}", height=300)
        st.caption("Phase 4B/4C sẽ cross-check commodity exposure với Q16 pass-through/pricing power; hedging chỉ ghi khi disclosure có.")

    q["supplier_relationship"] = _select("Supplier Relationship", q.get("supplier_relationship", "Unknown"), ["Unknown", "Collaborative", "Balanced", "Transactional", "Adversarial"], f"ch4_q20_relationship_{ticker}")
    q["supply_reliability"] = _select("Supply Reliability", q.get("supply_reliability", "Unknown"), ["Unknown", "Strong", "Moderate", "Weak"], f"ch4_q20_reliability_{ticker}")
    q["supplier_concentration"] = _select("Supplier Concentration", q.get("supplier_concentration", "Unknown"), ["Unknown", "Low", "Moderate", "High"], f"ch4_q20_concentration_{ticker}")
    q["commodity_dependence"] = _select("Commodity Dependence", q.get("commodity_dependence", "Unknown"), ["Unknown", "Low", "Moderate", "High"], f"ch4_q20_commoditydep_{ticker}")
    q["trend"] = _select("Overall Supplier/Supply Trend", q.get("trend", "Unknown"), ["Unknown", "Improving", "Stable", "Deteriorating", "Mixed"], f"ch4_q20_trend_{ticker}")
    q["biggest_supply_risk"] = st.text_area("Biggest Supply Risk", value=str(q.get("biggest_supply_risk") or ""), key=f"ch4_q20_risk_{ticker}", height=80)
    q["biggest_supplier_strength"] = st.text_area("Biggest Supplier Strength", value=str(q.get("biggest_supplier_strength") or ""), key=f"ch4_q20_strength_{ticker}", height=80)
    q["confidence"] = _select("Analyst Confidence", q.get("confidence", "Unknown"), ["Unknown", "Low", "Medium", "High"], f"ch4_q20_conf_{ticker}")
    q["conclusion"] = st.text_area("Q20 Analyst Conclusion", value=str(q.get("conclusion") or ""), key=f"ch4_q20_conclusion_{ticker}", height=130)


def consistency_warnings(payload: dict[str, Any]) -> list[str]:
    """Deterministic contradiction prompts only; never changes analyst conclusions."""
    q15, q16, q17, q18, q19, q20 = (payload.get(k, {}) for k in ("q15", "q16", "q17", "q18", "q19", "q20"))
    warnings: list[str] = []
    if str(q15.get("sustainable_advantage")) == "Yes" and str(q16.get("pricing_power")) in {"Weak", "None"}:
        warnings.append("Q15 có sustainable advantage nhưng Q16 pricing power yếu/không có. Điều này có thể hợp lý với cost moat/commodity business, nhưng analyst cần giải thích cơ chế lợi thế.")
    if str(q16.get("pricing_power")) in {"Strong", "Moderate"} and str(q16.get("nature")) in {"Cost-pass-through", "Commodity / Shortage"}:
        warnings.append("Q16 đang đánh pricing power cao nhưng Nature là pass-through/commodity shortage. Hãy kiểm tra lại True Pricing Power vs temporary pricing.")
    if str(q17.get("industry_economics")) == "Good" and str(q18.get("trend")) in {"Deteriorating", "Structural Transition"}:
        warnings.append("Q17 đánh ngành Good nhưng Q18 cho thấy economics đang deteriorating/structural transition. Cần review tính còn hiệu lực của Q17.")
    if str(q15.get("overall_moat_trend")) == "Stable" and _has_text(q15.get("advantage_deteriorating_most")):
        warnings.append("Q15 Overall Moat Trend = Stable nhưng analyst đã ghi lợi thế đang suy yếu. Hãy xác nhận đây là yếu tố nhỏ hay trend tổng thể cần đổi.")
    if str(q20.get("commodity_dependence")) == "High" and str(q16.get("pricing_power")) in {"Weak", "None"}:
        warnings.append("Q20 commodity dependence cao + Q16 pricing power yếu/không có → margin vulnerability cần analyst đánh giá.")
    if str(q20.get("supply_reliability")) == "Strong" and str(q20.get("supplier_concentration")) == "High":
        warnings.append("Q20 supply reliability Strong nhưng supplier concentration High. Reliability hiện tại không loại bỏ single-source/concentration risk.")
    if str(q19.get("competition_intensity")) == "Limited" and _nonempty_rows(payload.get("q19_substitutes")):
        warnings.append("Q19 direct competition Limited nhưng có substitute records. Hãy kiểm tra competitive set rộng hơn direct peers.")
    return warnings


def _render_synthesis(payload: dict[str, Any], ticker: str) -> None:
    st.markdown("## Cross-Question Consistency Check")
    warnings = consistency_warnings(payload)
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("Chưa phát hiện contradiction rule nào từ các analyst assessments hiện tại. Đây không phải xác nhận rằng thesis đúng.")

    st.markdown("## Chapter 4 Synthesis")
    summary_rows = [
        {"Dimension": "Q15 Sustainable Advantage", "Assessment": payload["q15"].get("sustainable_advantage"), "Trend": payload["q15"].get("overall_moat_trend"), "Confidence": payload["q15"].get("confidence"), "Main Threat": payload["q15"].get("copy_replace_threat")},
        {"Dimension": "Q16 Pricing Power", "Assessment": payload["q16"].get("pricing_power"), "Trend": payload["q16"].get("trend"), "Confidence": payload["q16"].get("confidence"), "Main Threat": payload["q16"].get("main_erosion_threat")},
        {"Dimension": "Q17 Industry Economics", "Assessment": payload["q17"].get("industry_economics"), "Trend": payload["q17"].get("trend"), "Confidence": payload["q17"].get("confidence"), "Main Threat": payload["q17"].get("main_negative")},
        {"Dimension": "Q18 Industry Evolution", "Assessment": payload["q18"].get("trend"), "Trend": payload["q18"].get("trend"), "Confidence": payload["q18"].get("confidence"), "Main Threat": payload["q18"].get("next_inflection")},
        {"Dimension": "Q19 Competition", "Assessment": payload["q19"].get("competition_intensity"), "Trend": payload["q19"].get("trend"), "Confidence": payload["q19"].get("confidence"), "Main Threat": payload["q19"].get("biggest_direct_threat")},
        {"Dimension": "Q20 Suppliers", "Assessment": payload["q20"].get("supplier_relationship"), "Trend": payload["q20"].get("trend"), "Confidence": payload["q20"].get("confidence"), "Main Threat": payload["q20"].get("biggest_supply_risk")},
    ]
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

    payload["top_business_strengths"] = st.text_area("Top Business Strengths", value=str(payload.get("top_business_strengths") or ""), key=f"ch4_strengths_{ticker}", height=100)
    payload["top_business_weaknesses"] = st.text_area("Top Business Weaknesses", value=str(payload.get("top_business_weaknesses") or ""), key=f"ch4_weaknesses_{ticker}", height=100)
    payload["deterioration_watch"] = st.text_area("Deterioration Watch", value=str(payload.get("deterioration_watch") or ""), key=f"ch4_deterioration_{ticker}", height=90)
    payload["improvement_watch"] = st.text_area("Improvement Watch", value=str(payload.get("improvement_watch") or ""), key=f"ch4_improvement_{ticker}", height=90)
    payload["critical_unknowns"] = st.text_area("Critical Unknowns", value=str(payload.get("critical_unknowns") or ""), key=f"ch4_unknowns_{ticker}", height=100)
    payload["analyst_summary"] = st.text_area("Chapter 4 Analyst Summary", value=str(payload.get("analyst_summary") or ""), key=f"ch4_summary_{ticker}", height=140)

    payload["evidence_matrix"] = _editor("Evidence / Counter-Evidence Matrix", payload.get("evidence_matrix"), EVIDENCE_COLUMNS, f"ch4_evidence_{ticker}", height=300)
    payload["research_gaps_table"] = _editor("Research Gaps", payload.get("research_gaps_table"), RESEARCH_GAP_COLUMNS, f"ch4_gaps_{ticker}", height=240)


def render_chapter4(default_ticker: str = "DGC", company_name: str = "") -> None:
    init_db()
    _render_intro()
    safe_default = _safe_ticker(default_ticker) or "DGC"
    ticker = _safe_ticker(st.text_input("Mã cổ phiếu — Chương 4", value=safe_default, key="dca_ch4_ticker")) or safe_default
    record = load_record(ticker, company_name)
    record["ticker"] = ticker
    if company_name and not str(record.get("company_name") or "").strip():
        record["company_name"] = company_name
    record["company_name"] = st.text_input("Doanh nghiệp", value=str(record.get("company_name") or ""), key=f"ch4_company_{ticker}")

    _render_dashboard(record)
    status = understanding_status(record)
    st.info(f"Research Understanding: **{STATUS_LABELS[status]}** — đây là mức độ hoàn tất nghiên cứu, không phải investment rating.")

    q15_tab, q16_tab, q17_tab, q18_tab, q19_tab, q20_tab = st.tabs([
        "Q15 — Lợi thế cạnh tranh",
        "Q16 — Pricing Power",
        "Q17 — Chất lượng ngành",
        "Q18 — Tiến hóa ngành",
        "Q19 — Cạnh tranh",
        "Q20 — Nhà cung cấp",
    ])
    with q15_tab:
        _render_q15(record, ticker)
    with q16_tab:
        _render_q16(record, ticker)
    with q17_tab:
        _render_q17(record, ticker)
    with q18_tab:
        _render_q18(record, ticker)
    with q19_tab:
        _render_q19(record, ticker)
    with q20_tab:
        _render_q20(record, ticker)

    _render_synthesis(record, ticker)

    if st.button("💾 Lưu Chương 4", type="primary", use_container_width=True, key=f"ch4_save_{ticker}"):
        saved_status = save_record(record)
        st.success(f"Đã lưu Chương 4 cho {ticker}. Research Understanding: {STATUS_LABELS[saved_status]}. Snapshot mới đã được tạo.")

    history = load_history(ticker)
    if not history.empty:
        with st.expander(f"Version History — {ticker}", expanded=False):
            st.dataframe(history, use_container_width=True, hide_index=True)
