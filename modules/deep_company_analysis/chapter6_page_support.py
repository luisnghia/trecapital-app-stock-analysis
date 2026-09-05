from __future__ import annotations

"""Streamlit UI for Deep Company Analysis — Chapter 6 approved Phase 6A.

The UI is analyst-owned. Data/AI may support evidence collection in later phases but must
never silently convert a signal into an analyst conclusion, a Research Gate, or BUY/HOLD/SELL.
"""

from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter6 import (
    ACCOUNTING_QUALITY_COLUMNS,
    CAPEX_COLUMNS,
    COST_STRUCTURE_COLUMNS,
    CYCLE_COLUMNS,
    DISTRIBUTION_MATRIX_COLUMNS,
    DISTRIBUTION_WIDTH_OPTIONS,
    EVIDENCE_COLUMNS,
    MAINTENANCE_CAPEX_METHOD_OPTIONS,
    QUESTION_STATUS_OPTIONS,
    RECURRING_REVENUE_COLUMNS,
    RESERVE_ROLLFORWARD_COLUMNS,
    RESEARCH_GAP_COLUMNS,
    TREND_OPTIONS,
    WORKING_CAPITAL_COLUMNS,
    create_snapshot,
    list_snapshots,
    load_record,
    research_gap_warnings,
    save_record,
)
from modules.deep_company_analysis.chapter6_format import (
    financial_table_html,
    has_financial_numeric_columns,
    infer_numeric_kind,
)

APP_DIR = Path(__file__).resolve().parents[2]
FORMULA_DOC = APP_DIR / "docs" / "formulas" / "DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md"
SOURCE_LOCK_DOC = APP_DIR / "docs" / "CHAPTER6_PHASE6A_SOURCE_LOCK.md"


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _df(rows: Any, columns: list[str]) -> pd.DataFrame:
    incoming = [dict(row) for row in rows] if isinstance(rows, list) else []
    if not incoming:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame(incoming)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        clean = value.where(pd.notna(value), None)
        return clean.to_dict(orient="records")
    return []


def _question_controls(payload: dict[str, Any], q: str, key_prefix: str) -> None:
    c1, c2 = st.columns(2)
    status_current = str((payload.get("question_status") or {}).get(q) or "Unknown")
    trend_current = str((payload.get("question_trend") or {}).get(q) or "Unknown")
    with c1:
        payload["question_status"][q] = st.selectbox(
            "Research status",
            QUESTION_STATUS_OPTIONS,
            index=QUESTION_STATUS_OPTIONS.index(status_current) if status_current in QUESTION_STATUS_OPTIONS else 0,
            key=f"{key_prefix}_{q}_status",
        )
    with c2:
        payload["question_trend"][q] = st.selectbox(
            "Trend",
            TREND_OPTIONS,
            index=TREND_OPTIONS.index(trend_current) if trend_current in TREND_OPTIONS else 0,
            key=f"{key_prefix}_{q}_trend",
        )


def _select(label: str, current: Any, options: tuple[str, ...], key: str) -> str:
    value = str(current or options[0])
    return st.selectbox(
        label,
        options,
        index=options.index(value) if value in options else 0,
        key=key,
    )


def _editor_column_config(columns: list[str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for column in columns:
        kind = infer_numeric_kind(column)
        if kind == "amount_bil":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.0f",
                help="Đơn vị: tỷ đồng; hiển thị 0 số lẻ.",
            )
        elif kind == "percent":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.1f%%",
                help="Đơn vị: %; hiển thị 1 số lẻ.",
            )
        elif kind == "ratio":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.1f",
                help="Hệ số; hiển thị 1 số lẻ.",
            )
        elif kind == "days":
            config[column] = st.column_config.NumberColumn(
                column,
                format="%.1f",
                help="Số ngày; hiển thị 1 số lẻ.",
            )

    if "Revenue Type" in columns:
        config["Revenue Type"] = st.column_config.SelectboxColumn(
            "Revenue Type",
            options=[
                "Unknown",
                "Contractual recurring",
                "Behavioral recurring",
                "Repeat purchase",
                "One-off",
                "Mixed",
            ],
        )
    if "Contractual?" in columns:
        config["Contractual?"] = st.column_config.SelectboxColumn(
            "Contractual?",
            options=["Unknown", "Yes", "No", "Mixed"],
        )
    if "Effect on Distribution" in columns:
        config["Effect on Distribution"] = st.column_config.SelectboxColumn(
            "Effect on Distribution",
            options=["Unknown", "Narrower", "Wider", "Neutral", "Mixed"],
        )
    if "Question" in columns:
        config["Question"] = st.column_config.TextColumn("Question", disabled=True)
    if "Driver" in columns and columns == DISTRIBUTION_MATRIX_COLUMNS:
        config["Driver"] = st.column_config.TextColumn("Driver", disabled=True)
    return config


def _editor(
    label: str,
    rows: Any,
    columns: list[str],
    key: str,
    *,
    height: int = 300,
) -> list[dict[str, Any]]:
    st.markdown(f"**{label}**")
    edited = st.data_editor(
        _df(rows, columns),
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        height=height,
        column_config=_editor_column_config(columns),
        key=key,
    )
    if has_financial_numeric_columns(columns) and isinstance(edited, pd.DataFrame) and not edited.empty:
        with st.expander(f"🔎 Preview format số liệu — {label}", expanded=False):
            st.caption(
                "Quy chuẩn: tỷ đồng 0 số lẻ; % và hệ số 1 số lẻ; số âm đỏ, số dương xanh ngọc; "
                "cường độ màu tăng theo độ lớn tuyệt đối."
            )
            st.html(financial_table_html(edited, columns))
    return _rows(edited)


def render_chapter6_tab(default_ticker: str = "") -> None:
    st.subheader("Chương 6 — Đánh giá phân phối lợi nhuận & dòng tiền")
    st.caption(
        "Michael Shearn Q27–Q32 | Approved Phase 6A: source-locked analyst workspace. "
        "Mục tiêu là hiểu độ rộng/predictability của earnings & cash-flow distribution."
    )

    with st.expander("📘 Source lock, ranh giới phân tích & format", expanded=True):
        st.markdown(
            """
**Mục tiêu:** không cố dự báo một con số lợi nhuận tương lai duy nhất. Chương 6 đánh giá **độ rộng của phân phối earnings/cash flow** và những yếu tố có thể khiến kết quả thực tế lệch khỏi kỳ vọng.

- **Q27:** tìm true operating earnings; kiểm tra tax/book, CFO/NI, revenue recognition, capitalization, discretionary costs, depreciation/estimate changes, restructuring và reserves.
- **Q28:** phân biệt **Contractual recurring / Behavioral recurring / Repeat purchase / One-off**; không tự suy ra recurring share nếu thiếu disclosure/evidence.
- **Q29:** cyclical / countercyclical / recession-resistant phải dựa trên company economics, customer cycle, supply/demand và downturn evidence.
- **Q30:** Phase 6A phân rã fixed / variable / semi-variable; historical DOL thuộc Phase 6B.
- **Q31:** không dùng quy tắc máy móc `CCC thấp = tốt` hay `negative WC = tốt`.
- **Q32:** maintenance capex theo thứ tự **company disclosure → analyst estimate có evidence → depreciation rough proxy gắn nhãn rõ → Unknown**. Total capex không được mặc định là maintenance capex.

**Không weighted score 0–100. Không tự đổi MOS. Không BUY/HOLD/SELL.**
            """
        )
        st.success(
            "Format lock: tỷ đồng = 0 số lẻ; % = 1 số lẻ; hệ số = 1 số lẻ; "
            "bảng số read-only dùng st.html(), fixed layout + wrap; âm đỏ, dương xanh ngọc theo heat intensity."
        )
        st.caption(
            f"Approved source lock: `{SOURCE_LOCK_DOC.relative_to(APP_DIR)}` | "
            f"Formula boundary: `{FORMULA_DOC.relative_to(APP_DIR)}`"
        )

    safe_default = _safe_ticker(default_ticker) or "DGC"
    ticker = _safe_ticker(
        st.text_input("Mã cổ phiếu", value=safe_default, key="dca_ch6_ticker_input")
    ) or safe_default
    st.session_state["dca_ch6_ticker"] = ticker

    payload = load_record(ticker)
    payload["ticker"] = ticker
    payload["company_name"] = st.text_input(
        "Tên doanh nghiệp (analyst, optional)",
        value=str(payload.get("company_name") or ""),
        key=f"dca_ch6_company_{ticker}",
    )

    with st.expander("Q27 — Accounting standards: Conservative hay Liberal?", expanded=True):
        st.caption(
            "Mục tiêu theo Shearn là tiến gần true operating earnings, không phải gắn nhãn gian lận từ một ratio riêng lẻ."
        )
        _question_controls(payload, "Q27", f"dca6_{ticker}")
        q = payload["q27"]
        q["tax_book_difference"] = _select(
            "27A — Tax vs Book Earnings",
            q.get("tax_book_difference"),
            ("Unknown", "Small / conservative", "Material", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_tax",
        )
        q["cfo_vs_net_income"] = _select(
            "27B — CFO vs Net Income",
            q.get("cfo_vs_net_income"),
            ("Unknown", "Closely approximates", "Persistent gap", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_cfo",
        )
        q["revenue_recognition"] = _select(
            "27C — Revenue recognition",
            q.get("revenue_recognition"),
            ("Unknown", "When earned", "Potentially front-loaded", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_rev",
        )
        q["expense_vs_capitalize"] = _select(
            "27D — Expense vs capitalize",
            q.get("expense_vs_capitalize"),
            ("Unknown", "Expenses quickly", "Potential capitalization concern", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_cap",
        )
        q["discretionary_costs"] = _select(
            "27E — Discretionary costs",
            q.get("discretionary_costs"),
            ("Unknown", "No smoothing evidence", "Potential smoothing", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_disc",
        )
        q["depreciation_assumptions"] = _select(
            "27F — Depreciation / estimate assumptions",
            q.get("depreciation_assumptions"),
            ("Unknown", "Conservative / stable", "Potentially liberal", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_dep",
        )
        q["restructuring_charges"] = _select(
            "27G — Restructuring / one-offs",
            q.get("restructuring_charges"),
            ("Unknown", "No concern found", "Potential concern", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_restruct",
        )
        q["reserve_quality"] = _select(
            "Reserve quality",
            q.get("reserve_quality"),
            ("Unknown", "Well matched to outcomes", "Over/under-reserving concern", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_reserve",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Conservative", "Balanced", "Liberal", "Mixed", "N/A"),
            f"dca6_{ticker}_q27_overall",
        )
        q["true_operating_earnings_note"] = st.text_area(
            "True operating earnings / adjustments cần xem xét",
            value=str(q.get("true_operating_earnings_note") or ""),
            key=f"dca6_{ticker}_q27_true",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q27",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q27_conclusion",
        )
        payload["q27_accounting_quality"] = _editor(
            "Accounting Quality Investigation Register",
            payload.get("q27_accounting_quality"),
            ACCOUNTING_QUALITY_COLUMNS,
            f"dca6_{ticker}_q27_table",
            height=340,
        )
        payload["q27_reserve_rollforward"] = _editor(
            "Reserve / Provision Roll-forward — Tables 6.1–6.2",
            payload.get("q27_reserve_rollforward"),
            RESERVE_ROLLFORWARD_COLUMNS,
            f"dca6_{ticker}_q27_reserve_rollforward",
            height=320,
        )
        st.info(
            "Không tính Beneish lần thứ hai tại đây. Phase 6C chỉ nhận read-only evidence/cảnh báo "
            "từ Module Manipulation; analyst vẫn quyết định Conservative / Mixed / Liberal."
        )

    with st.expander("Q28 — Revenue Durability: recurring hay one-off?", expanded=False):
        st.caption(
            "Contractual recurring khác Behavioral recurring; Repeat purchase cũng không được relabel thành contracted revenue."
        )
        _question_controls(payload, "Q28", f"dca6_{ticker}")
        q = payload["q28"]
        q["recurring_revenue_share"] = st.text_input(
            "Recurring revenue share (chỉ nhập khi có nguồn hoặc analyst estimate rõ)",
            value=str(q.get("recurring_revenue_share") or ""),
            key=f"dca6_{ticker}_q28_share",
        )
        q["recurring_revenue_share_source"] = _select(
            "Nguồn recurring revenue share",
            q.get("recurring_revenue_share_source"),
            ("Unknown", "Company disclosed", "Analyst estimate with evidence", "N/A"),
            f"dca6_{ticker}_q28_share_source",
        )
        q["starting_revenue_base"] = _select(
            "Starting revenue base",
            q.get("starting_revenue_base"),
            ("Unknown", "High recurring base", "Mixed", "Mostly resets", "N/A"),
            f"dca6_{ticker}_q28_base",
        )
        q["dependence_on_new_sales"] = _select(
            "Dependence on new sales/products",
            q.get("dependence_on_new_sales"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q28_new",
        )
        q["expense_budget_visibility"] = _select(
            "Expense budget visibility",
            q.get("expense_budget_visibility"),
            ("Unknown", "High", "Medium", "Low", "N/A"),
            f"dca6_{ticker}_q28_budget",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Predominantly recurring", "Mixed", "Predominantly one-off", "N/A"),
            f"dca6_{ticker}_q28_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q28",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q28_conclusion",
        )
        payload["q28_revenue_streams"] = _editor(
            "Revenue Durability Map",
            payload.get("q28_revenue_streams"),
            RECURRING_REVENUE_COLUMNS,
            f"dca6_{ticker}_q28_table",
            height=330,
        )

    with st.expander("Q29 — Cycle Exposure Map", expanded=False):
        st.caption(
            "Không gắn nhãn recession-resistant chỉ vì một downturn trước đó tốt; phải kiểm tra company economics và supply/demand context."
        )
        _question_controls(payload, "Q29", f"dca6_{ticker}")
        q = payload["q29"]
        q["cycle_classification"] = _select(
            "Analyst cycle classification",
            q.get("cycle_classification"),
            ("Unknown", "Cyclical", "Countercyclical", "Recession-resistant", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_class",
        )
        q["purchase_deferrability"] = _select(
            "Customer purchase deferrability",
            q.get("purchase_deferrability"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q29_defer",
        )
        q["recurring_revenue_protection"] = _select(
            "Recurring-revenue protection",
            q.get("recurring_revenue_protection"),
            ("Unknown", "Strong", "Moderate", "Weak", "N/A"),
            f"dca6_{ticker}_q29_rec",
        )
        q["customer_budget_importance"] = _select(
            "Share of customer budget / necessity",
            q.get("customer_budget_importance"),
            ("Unknown", "Low / easy to keep", "Moderate", "High / cuttable", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_budget",
        )
        q["customer_cycle_exposure"] = _select(
            "Customer exposure to economic cycle",
            q.get("customer_cycle_exposure"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_customer",
        )
        q["supply_demand_distortion"] = _select(
            "Past supply/demand distortion?",
            q.get("supply_demand_distortion"),
            ("Unknown", "No evidence", "Possible", "Material", "N/A"),
            f"dca6_{ticker}_q29_supply",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Narrow earnings distribution", "Moderate", "Wide earnings distribution", "Mixed", "N/A"),
            f"dca6_{ticker}_q29_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q29",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q29_conclusion",
        )
        payload["q29_cycle_drivers"] = _editor(
            "Cycle Driver / Downturn Evidence Map",
            payload.get("q29_cycle_drivers"),
            CYCLE_COLUMNS,
            f"dca6_{ticker}_q29_table",
            height=330,
        )

    with st.expander("Q30 — Operating leverage tác động earnings thế nào?", expanded=False):
        st.caption(
            "Phase 6A phân rã cost structure. DOL lịch sử, downside/upside sensitivity và stress test thuộc Phase 6B."
        )
        _question_controls(payload, "Q30", f"dca6_{ticker}")
        q = payload["q30"]
        q["operating_leverage"] = _select(
            "Operating leverage",
            q.get("operating_leverage"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_dol",
        )
        q["fixed_cost_intensity"] = _select(
            "Fixed-cost intensity",
            q.get("fixed_cost_intensity"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_fixed",
        )
        q["cost_flexibility"] = _select(
            "Cost flexibility",
            q.get("cost_flexibility"),
            ("Unknown", "High", "Medium", "Low", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_flex",
        )
        q["forecast_difficulty"] = _select(
            "Earnings forecast difficulty",
            q.get("forecast_difficulty"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q30_forecast",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Favorable / low amplification", "Neutral", "Risky / high amplification", "Mixed", "N/A"),
            f"dca6_{ticker}_q30_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q30",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q30_conclusion",
        )
        payload["q30_cost_structure"] = _editor(
            "Cost Structure Matrix — Tables 6.3–6.5 logic",
            payload.get("q30_cost_structure"),
            COST_STRUCTURE_COLUMNS,
            f"dca6_{ticker}_q30_table",
            height=320,
        )

    with st.expander("Q31 — Working capital tác động cash flow thế nào?", expanded=False):
        st.caption(
            "Theo Shearn cần xem nhiều năm DSO/DIO/DPO/CCC và giải thích nguyên nhân. Phase 6A lưu cơ chế; Phase 6B mới tính canonical history."
        )
        _question_controls(payload, "Q31", f"dca6_{ticker}")
        q = payload["q31"]
        q["working_capital_model"] = st.text_area(
            "Working-capital mechanism của doanh nghiệp",
            value=str(q.get("working_capital_model") or ""),
            key=f"dca6_{ticker}_q31_model",
        )
        q["ccc_direction"] = _select(
            "CCC direction",
            q.get("ccc_direction"),
            ("Unknown", "Improving", "Stable", "Deteriorating", "Volatile", "N/A"),
            f"dca6_{ticker}_q31_ccc",
        )
        q["ccc_change_quality"] = _select(
            "Quality of CCC change",
            q.get("ccc_change_quality"),
            ("Unknown", "Sustainable", "Partly sustainable", "Temporary", "Adverse", "N/A"),
            f"dca6_{ticker}_q31_quality",
        )
        q["negative_working_capital"] = _select(
            "Negative working capital model",
            q.get("negative_working_capital"),
            ("Unknown", "No", "Yes — structurally favorable", "Yes — liquidity-sensitive", "Mixed", "N/A"),
            f"dca6_{ticker}_q31_negative",
        )
        q["liquidity_dependency"] = _select(
            "Liquidity dependency",
            q.get("liquidity_dependency"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q31_liq",
        )
        q["normalization_needed"] = _select(
            "Normalize temporary WC benefit?",
            q.get("normalization_needed"),
            ("Unknown", "No", "Possibly", "Yes", "N/A"),
            f"dca6_{ticker}_q31_norm",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Cash-generative", "Neutral", "Cash-absorbing", "Mixed", "N/A"),
            f"dca6_{ticker}_q31_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q31",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q31_conclusion",
        )
        payload["q31_working_capital"] = _editor(
            "Working Capital Mechanism Register — Table 6.6 logic",
            payload.get("q31_working_capital"),
            WORKING_CAPITAL_COLUMNS,
            f"dca6_{ticker}_q31_table",
            height=310,
        )

    with st.expander("Q32 — Capital-expenditure requirements cao hay thấp?", expanded=False):
        st.caption(
            "Maintenance capex hierarchy: disclosure → analyst estimate có evidence → depreciation rough proxy gắn nhãn rõ → Unknown."
        )
        _question_controls(payload, "Q32", f"dca6_{ticker}")
        q = payload["q32"]
        q["capital_intensity"] = _select(
            "Capital intensity",
            q.get("capital_intensity"),
            ("Unknown", "Low", "Medium", "High", "Mixed", "N/A"),
            f"dca6_{ticker}_q32_intensity",
        )
        q["maintenance_capex_visibility"] = _select(
            "Maintenance capex visibility",
            q.get("maintenance_capex_visibility"),
            ("Unknown", "Disclosed / supportable", "Partial", "Not separately disclosed", "N/A"),
            f"dca6_{ticker}_q32_maintvis",
        )
        q["maintenance_vs_growth_split"] = _select(
            "Maintenance vs growth split",
            q.get("maintenance_vs_growth_split"),
            ("Unknown", "Supportable", "Partly supportable", "Not supportable", "N/A"),
            f"dca6_{ticker}_q32_split",
        )
        q["maintenance_capex_method"] = _select(
            "Maintenance capex method",
            q.get("maintenance_capex_method"),
            MAINTENANCE_CAPEX_METHOD_OPTIONS,
            f"dca6_{ticker}_q32_method",
        )
        if q["maintenance_capex_method"] == "Depreciation rough proxy — clearly labelled":
            st.warning(
                "Depreciation chỉ là rough proxy theo Shearn trong trường hợp phù hợp. Ghi rõ vì sao hợp lý, "
                "asset age/growth context và giới hạn; không relabel thành company-disclosed maintenance capex."
            )
            q["depreciation_proxy_note"] = st.text_area(
                "Lý do / giới hạn khi dùng depreciation proxy",
                value=str(q.get("depreciation_proxy_note") or ""),
                key=f"dca6_{ticker}_q32_dep_proxy_note",
            )
        q["regulatory_capex_burden"] = _select(
            "Regulatory / mandatory capex burden",
            q.get("regulatory_capex_burden"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q32_reg",
        )
        q["deferred_maintenance_risk"] = _select(
            "Deferred maintenance risk",
            q.get("deferred_maintenance_risk"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q32_defer",
        )
        q["asset_age_replacement_risk"] = _select(
            "Asset-age / replacement risk",
            q.get("asset_age_replacement_risk"),
            ("Unknown", "Low", "Medium", "High", "N/A"),
            f"dca6_{ticker}_q32_age",
        )
        q["overall_assessment"] = _select(
            "Analyst overall assessment",
            q.get("overall_assessment"),
            ("Unknown", "Low capex burden", "Moderate", "High capex burden", "Mixed", "N/A"),
            f"dca6_{ticker}_q32_overall",
        )
        q["conclusion"] = st.text_area(
            "Kết luận analyst Q32",
            value=str(q.get("conclusion") or ""),
            key=f"dca6_{ticker}_q32_conclusion",
        )
        payload["q32_capex_register"] = _editor(
            "Capex Register",
            payload.get("q32_capex_register"),
            CAPEX_COLUMNS,
            f"dca6_{ticker}_q32_table",
            height=320,
        )

    with st.expander("Evidence, Counter-evidence & Research Gaps", expanded=False):
        payload["evidence_matrix"] = _editor(
            "Evidence Matrix",
            payload.get("evidence_matrix"),
            EVIDENCE_COLUMNS,
            f"dca6_{ticker}_evidence",
            height=320,
        )
        payload["research_gaps_table"] = _editor(
            "Research Gaps",
            payload.get("research_gaps_table"),
            RESEARCH_GAP_COLUMNS,
            f"dca6_{ticker}_gaps",
            height=260,
        )

    st.markdown("### Chapter 6 — Earnings & Cash-flow Predictability Matrix")
    payload["earnings_distribution_width"] = _select(
        "Earnings/Cash-flow Distribution",
        payload.get("earnings_distribution_width"),
        DISTRIBUTION_WIDTH_OPTIONS,
        f"dca6_{ticker}_distribution_width",
    )
    payload["earnings_distribution_matrix"] = _editor(
        "Predictability Matrix — không weighted score",
        payload.get("earnings_distribution_matrix"),
        DISTRIBUTION_MATRIX_COLUMNS,
        f"dca6_{ticker}_distribution_matrix",
        height=285,
    )
    st.caption(
        "Không tính điểm 0–100 và không tự điều chỉnh MOS. Distribution là kết luận của analyst từ Q27–Q32."
    )
    if payload["earnings_distribution_width"] in {"Moderately Wide", "Wide"}:
        st.info(
            "Distribution rộng: ở phase định giá sau này app có thể gợi ý Bear/Base/Bull, normalized earnings/FCF và wider MOS review, "
            "nhưng không tự thay assumptions."
        )
    elif payload["earnings_distribution_width"] in {"Narrow", "Moderately Narrow"}:
        st.info(
            "Distribution hẹp: single-point valuation có thể hữu ích hơn, nhưng đây vẫn không phải Buy Signal."
        )

    payload["earnings_distribution_summary"] = st.text_area(
        "Phân phối earnings/cash flow: hẹp hay rộng, vì sao?",
        value=str(payload.get("earnings_distribution_summary") or ""),
        key=f"dca6_{ticker}_dist",
    )
    payload["narrowing_factors"] = st.text_area(
        "Các yếu tố làm hẹp distribution",
        value=str(payload.get("narrowing_factors") or ""),
        key=f"dca6_{ticker}_narrow",
    )
    payload["widening_factors"] = st.text_area(
        "Các yếu tố làm rộng distribution",
        value=str(payload.get("widening_factors") or ""),
        key=f"dca6_{ticker}_wide",
    )
    payload["critical_unknowns"] = st.text_area(
        "Critical unknowns",
        value=str(payload.get("critical_unknowns") or ""),
        key=f"dca6_{ticker}_unknowns",
    )
    payload["analyst_summary"] = st.text_area(
        "Kết luận Chapter 6 của analyst",
        value=str(payload.get("analyst_summary") or ""),
        key=f"dca6_{ticker}_summary",
    )

    warnings = research_gap_warnings(payload)
    if warnings:
        st.warning("Consistency / Research Gap:\n\n- " + "\n- ".join(warnings))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Lưu Chapter 6", use_container_width=True, key=f"dca6_{ticker}_save"):
            save_record(ticker, payload, str(payload.get("company_name") or ""))
            st.success("Đã lưu Chapter 6. Không có analyst conclusion nào bị AI/Data ghi đè.")
    with c2:
        if st.button("📸 Lưu snapshot Chapter 6", use_container_width=True, key=f"dca6_{ticker}_snapshot"):
            snapshot_id = create_snapshot(ticker, payload)
            st.success(f"Đã lưu snapshot #{snapshot_id}.")

    snapshots = list_snapshots(ticker, limit=8)
    if snapshots:
        with st.expander("🕘 Snapshot gần nhất", expanded=False):
            rows_html = "".join(
                "<tr>"
                f"<td>{int(item['id'])}</td>"
                f"<td>{escape(str(item['created_at']))}</td>"
                f"<td>{escape(str(item['understanding_status']))}</td>"
                "</tr>"
                for item in snapshots
            )
            st.html(
                "<div style='overflow-x:auto;width:100%'>"
                "<table style='width:100%;table-layout:fixed;border-collapse:collapse;white-space:normal;overflow-wrap:anywhere'>"
                "<thead><tr><th>Snapshot</th><th>Created</th><th>Research completion</th></tr></thead>"
                f"<tbody>{rows_html}</tbody></table></div>"
            )


__all__ = ["render_chapter6_tab"]
