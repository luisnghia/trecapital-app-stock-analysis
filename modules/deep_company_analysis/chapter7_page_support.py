from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter7 import (
    CAREER_TIMELINE_COLUMNS,
    COMPENSATION_DESIGN_COLUMNS,
    COMPENSATION_HISTORY_COLUMNS,
    CONFIDENCE_OPTIONS,
    EVIDENCE_COLUMNS,
    EVENT_COLUMNS,
    INSIDER_TRANSACTION_COLUMNS,
    LION_HYENA_COLUMNS,
    LION_HYENA_DIMENSIONS,
    LION_HYENA_OPTIONS,
    MANAGEMENT_PROFILE_COLUMNS,
    MANAGER_CLASSIFICATION_DEFINITIONS,
    MANAGER_CLASSIFICATION_OPTIONS,
    OUTSIDE_TRANSITION_COLUMNS,
    OWNERSHIP_HISTORY_COLUMNS,
    QUESTION_KEYS,
    QUESTION_STATUS_OPTIONS,
    RESEARCH_GAP_COLUMNS,
    build_management_overview,
    create_snapshot,
    list_snapshots,
    load_record,
    research_gap_warnings,
    save_record,
)
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor
from modules.deep_company_analysis.chapter7_data_bridge_ui import render_structured_management_bridge


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _select(label: str, value: Any, options: tuple[str, ...] | list[str], key: str) -> str:
    choices = list(options)
    current = str(value or choices[0])
    index = choices.index(current) if current in choices else 0
    return str(st.selectbox(label, choices, index=index, key=key))


def _editor(
    label: str,
    rows: Any,
    columns: list[str],
    key: str,
    *,
    height: int = 300,
    disabled: list[str] | None = None,
    column_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows if isinstance(rows, list) else [])
    for col in columns:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[columns]
    st.markdown(f"**{label}**")
    edited = sortable_data_editor(
        frame,
        key=key,
        hide_index=True,
        use_container_width=True,
        height=height,
        num_rows="dynamic",
        disabled=disabled or [],
        column_config=column_config or {},
    )
    return edited.to_dict("records") if isinstance(edited, pd.DataFrame) else frame.to_dict("records")


def _classification_config() -> dict[str, Any]:
    return {
        "Suggested Classification": st.column_config.SelectboxColumn(
            "Suggested Classification",
            options=list(MANAGER_CLASSIFICATION_OPTIONS),
            help="Phase 7A để Unknown; Phase 7C AI chỉ được gợi ý, không được ghi đè Analyst Classification.",
        ),
        "Analyst Classification": st.column_config.SelectboxColumn(
            "Analyst Classification", options=list(MANAGER_CLASSIFICATION_OPTIONS)
        ),
        "Confidence": st.column_config.SelectboxColumn("Confidence", options=list(CONFIDENCE_OPTIONS)),
        "Actual Ownership (%)": st.column_config.NumberColumn("Actual Ownership (%)", format="%.1f%%"),
    }


def _render_source_lock() -> None:
    with st.expander("🔒 Source-lock Chương 7 — Who Are They?", expanded=True):
        st.markdown(
            """
**Q33–Q38 là workspace nghiên cứu nền tảng và phân loại ban điều hành, không phải Management Quality Score.**

- Q33 dùng continuum **OO1 / OO2 / OO3 / LT1 / LT2 / HH1 / HH2**. Founder không tự động = OO1; outsider không tự động = xấu.
- Q35 giữ đúng **7 dimensions của Table 7.1 Lion/Hyena** và tuyệt đối không quy đổi thành điểm số.
- Q36 dựng career chronology; khoảng trống nghề nghiệp không được suy đoán nguyên nhân khi nguồn không nói rõ.
- Q37 tách **Actual Shares / Options / RSU / ESOP / Unvested Awards**; không cộng thành một ownership number mơ hồ.
- Q38 insider buy/sell là evidence cần review, không phải Buy/Sell Signal. Heuristic trong sách không phải universal threshold của Trecapital.
- Dữ liệu chương này chủ yếu là **event/as-of data**. Không tạo TTM giả cho career, ownership, classification hoặc insider event.
- **AI/Data = Research Assistant; Analyst = người kết luận.** Phase 7B chỉ tự động hóa structured disclosure bridge; research assistant web/PDF sâu vẫn để Phase 7C.
            """
        )
        taxonomy = pd.DataFrame(
            [{"Class": key, "Source-Locked Meaning": value} for key, value in MANAGER_CLASSIFICATION_DEFINITIONS.items()]
        )
        render_static_table(taxonomy, height=330, sort_key="ch7_taxonomy")


def _render_status_panel(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("### Research Status — Q33 đến Q38")
    cols = st.columns(3)
    for idx, question in enumerate(QUESTION_KEYS):
        with cols[idx % 3]:
            payload["question_status"][question] = _select(
                question,
                (payload.get("question_status") or {}).get(question),
                QUESTION_STATUS_OPTIONS,
                f"dca7_{ticker}_{question}_status",
            )


def _render_q33(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Q33 — What type of manager is leading the company?")
    st.caption("Phân loại là continuum source-lock, không phải quality score. Suggested Classification không được coi là kết luận analyst.")
    payload["management_profiles"] = _editor(
        "Manager Classification Map",
        payload.get("management_profiles"),
        MANAGEMENT_PROFILE_COLUMNS,
        f"dca7_{ticker}_profiles",
        height=420,
        disabled=["Suggested Classification"],
        column_config=_classification_config(),
    )
    overview = build_management_overview(payload.get("management_profiles"))
    if not overview.empty:
        st.markdown("**Derived tenure overview — chỉ mô tả, không auto-classify**")
        render_static_table(overview, height=300, sort_key=f"dca7_{ticker}_overview")

    q33 = payload["q33"]
    c1, c2, c3 = st.columns(3)
    with c1:
        q33["analyst_classification"] = _select(
            "Primary analyst classification", q33.get("analyst_classification"), MANAGER_CLASSIFICATION_OPTIONS, f"dca7_{ticker}_q33_class"
        )
    with c2:
        q33["execution_uncertainty"] = _select(
            "Execution uncertainty", q33.get("execution_uncertainty"), ("Unknown", "Low", "Medium", "High"), f"dca7_{ticker}_q33_uncertainty"
        )
    with c3:
        q33["management_business_fit"] = _select(
            "Management-business fit", q33.get("management_business_fit"), ("Unknown", "Strong", "Adequate", "Weak", "Mixed"), f"dca7_{ticker}_q33_fit"
        )
    q33["conclusion"] = st.text_area("Q33 analyst conclusion", value=str(q33.get("conclusion") or ""), key=f"dca7_{ticker}_q33_conclusion")


def _render_q34(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Q34 — Effects of bringing in outside management")
    st.caption("Theo dõi learn-first/change-later, organization-specific knowledge và network transferability; outsider không tự động bị đánh giá tiêu cực.")
    payload["outside_transitions"] = _editor(
        "Outside Management Transition Analyzer",
        payload.get("outside_transitions"),
        OUTSIDE_TRANSITION_COLUMNS,
        f"dca7_{ticker}_outside",
        height=440,
    )
    q34 = payload["q34"]
    c1, c2, c3 = st.columns(3)
    with c1:
        q34["applicable"] = _select("Applicable?", q34.get("applicable"), ("Unknown", "Yes", "No", "N/A"), f"dca7_{ticker}_q34_app")
    with c2:
        q34["learn_before_change"] = _select("Learn before change", q34.get("learn_before_change"), ("Unknown", "Strong evidence", "Mixed", "Weak evidence", "N/A"), f"dca7_{ticker}_q34_learn")
    with c3:
        q34["culture_fit"] = _select("Culture fit", q34.get("culture_fit"), ("Unknown", "Strong", "Adequate", "Weak", "Mixed", "N/A"), f"dca7_{ticker}_q34_culture")
    q34["conclusion"] = st.text_area("Q34 analyst conclusion", value=str(q34.get("conclusion") or ""), key=f"dca7_{ticker}_q34_conclusion")


def _render_q35(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Q35 — Is the manager a lion or a hyena?")
    st.caption("Table 7.1 là evidence matrix. Không có Lion score, Management score hoặc weighted score.")
    payload["lion_hyena_matrix"] = _editor(
        "Lion–Hyena Evidence Matrix — Table 7.1",
        payload.get("lion_hyena_matrix"),
        LION_HYENA_COLUMNS,
        f"dca7_{ticker}_lion_hyena",
        height=440,
        disabled=["Dimension", "Lion Definition", "Hyena Definition"],
        column_config={
            "Evidence Direction": st.column_config.SelectboxColumn(
                "Evidence Direction", options=["Unknown", "Lion", "Hyena", "Mixed"]
            )
        },
    )
    expected = pd.DataFrame(
        [{"Dimension": d, "Lion": lion, "Hyena": hyena} for d, lion, hyena in LION_HYENA_DIMENSIONS]
    )
    with st.expander("7 source-locked dimensions của Table 7.1", expanded=False):
        render_static_table(expected, height=330, sort_key=f"dca7_{ticker}_lion_definitions")
    payload["q35"]["overall_classification"] = _select(
        "Overall analyst classification", payload["q35"].get("overall_classification"), LION_HYENA_OPTIONS, f"dca7_{ticker}_q35_overall"
    )
    payload["q35"]["conclusion"] = st.text_area("Q35 analyst conclusion", value=str(payload["q35"].get("conclusion") or ""), key=f"dca7_{ticker}_q35_conclusion")


def _render_q36(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Q36 — How did the manager rise to lead the business?")
    st.caption("Ưu tiên top-5 senior managers và chronology 5–10 năm khi nguồn cho phép. Career gap chưa rõ nguyên nhân phải giữ Unknown.")
    payload["career_timeline"] = _editor(
        "Top-5 Management Career Timeline",
        payload.get("career_timeline"),
        CAREER_TIMELINE_COLUMNS,
        f"dca7_{ticker}_career",
        height=460,
    )
    q36 = payload["q36"]
    q36["top5_reviewed"] = _select("Top-5 managers reviewed?", q36.get("top5_reviewed"), ("Unknown", "Yes", "Partial", "N/A"), f"dca7_{ticker}_q36_top5")
    q36["career_pattern_summary"] = st.text_area("Career pattern summary", value=str(q36.get("career_pattern_summary") or ""), key=f"dca7_{ticker}_q36_pattern")
    q36["critical_gaps"] = st.text_area("Known career/research gaps", value=str(q36.get("critical_gaps") or ""), key=f"dca7_{ticker}_q36_gaps")
    q36["conclusion"] = st.text_area("Q36 analyst conclusion", value=str(q36.get("conclusion") or ""), key=f"dca7_{ticker}_q36_conclusion")


def _render_q37(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Q37 — Compensation & ownership alignment")
    st.caption("Actual Shares phải tách khỏi Options/RSU/ESOP. Không cộng quyền tiềm năng thành ownership thực tế.")
    payload["compensation_history"] = _editor(
        "Executive Compensation History — 5–10Y khi có disclosure",
        payload.get("compensation_history"),
        COMPENSATION_HISTORY_COLUMNS,
        f"dca7_{ticker}_comp_history",
        height=450,
    )
    payload["ownership_history"] = _editor(
        "Ownership History — actual economic ownership vs potential awards",
        payload.get("ownership_history"),
        OWNERSHIP_HISTORY_COLUMNS,
        f"dca7_{ticker}_ownership",
        height=410,
    )
    payload["compensation_design"] = _editor(
        "Compensation Design Map",
        payload.get("compensation_design"),
        COMPENSATION_DESIGN_COLUMNS,
        f"dca7_{ticker}_comp_design",
        height=370,
    )
    q37 = payload["q37"]
    c1, c2 = st.columns(2)
    with c1:
        q37["compensation_alignment"] = _select("Compensation alignment", q37.get("compensation_alignment"), ("Unknown", "Strong", "Mixed", "Weak"), f"dca7_{ticker}_q37_comp")
    with c2:
        q37["ownership_alignment"] = _select("Ownership alignment", q37.get("ownership_alignment"), ("Unknown", "Strong", "Mixed", "Weak"), f"dca7_{ticker}_q37_owner")
    q37["actual_vs_potential_ownership_reviewed"] = _select(
        "Actual vs potential ownership reviewed?", q37.get("actual_vs_potential_ownership_reviewed"), ("Unknown", "Yes", "Partial", "N/A"), f"dca7_{ticker}_q37_split"
    )
    q37["conclusion"] = st.text_area("Q37 analyst conclusion", value=str(q37.get("conclusion") or ""), key=f"dca7_{ticker}_q37_conclusion")


def _render_q38(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Q38 — Have managers been buying or selling the stock?")
    st.caption("Phân biệt open-market buy/sell với grant, option exercise, vesting, ESOP, tax withholding, gift... Insider activity chỉ là research evidence.")
    payload["insider_transactions"] = _editor(
        "Insider Transaction Register",
        payload.get("insider_transactions"),
        INSIDER_TRANSACTION_COLUMNS,
        f"dca7_{ticker}_insider",
        height=450,
        column_config={
            "Transaction": st.column_config.SelectboxColumn("Transaction", options=["", "Buy", "Sell", "Other"]),
            "Transaction Type": st.column_config.SelectboxColumn(
                "Transaction Type",
                options=["", "Open market", "Option exercise", "Grant", "Vesting", "ESOP", "Tax withholding", "Gift", "Other", "Unknown"],
            ),
        },
    )
    q38 = payload["q38"]
    q38["insider_behavior"] = _select("Analyst insider behavior", q38.get("insider_behavior"), ("Unknown", "Supportive", "Neutral", "Concerning", "Mixed"), f"dca7_{ticker}_q38_behavior")
    q38["material_transactions_reviewed"] = _select("Material transactions reviewed?", q38.get("material_transactions_reviewed"), ("Unknown", "Yes", "Partial", "N/A"), f"dca7_{ticker}_q38_reviewed")
    q38["conclusion"] = st.text_area("Q38 analyst conclusion", value=str(q38.get("conclusion") or ""), key=f"dca7_{ticker}_q38_conclusion")


def _render_evidence_and_events(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Evidence, Research Gaps & Management Events")
    payload["evidence_matrix"] = _editor(
        "Evidence Matrix",
        payload.get("evidence_matrix"),
        EVIDENCE_COLUMNS,
        f"dca7_{ticker}_evidence",
        height=390,
    )
    payload["research_gaps_table"] = _editor(
        "Research Gaps",
        payload.get("research_gaps_table"),
        RESEARCH_GAP_COLUMNS,
        f"dca7_{ticker}_gaps",
        height=330,
    )
    payload["management_events"] = _editor(
        "Management Event Register — Phase 7A manual capture",
        payload.get("management_events"),
        EVENT_COLUMNS,
        f"dca7_{ticker}_events",
        height=330,
    )
    st.caption("Phase 7B phát hiện event từ structured disclosures và đưa vào Review Queue; Phase 7C mới research/extract sâu từ nguồn unstructured/web.")


def _render_final_conclusion(ticker: str, payload: dict[str, Any]) -> None:
    st.markdown("## Analyst Final Management Background Conclusion")
    c1, c2, c3 = st.columns(3)
    with c1:
        payload["final_management_classification"] = _select(
            "Management Classification", payload.get("final_management_classification"), MANAGER_CLASSIFICATION_OPTIONS, f"dca7_{ticker}_final_class"
        )
        payload["execution_uncertainty"] = _select("Execution uncertainty", payload.get("execution_uncertainty"), ("Unknown", "Low", "Medium", "High"), f"dca7_{ticker}_final_exec")
    with c2:
        payload["management_business_fit"] = _select("Management-business fit", payload.get("management_business_fit"), ("Unknown", "Strong", "Adequate", "Weak", "Mixed"), f"dca7_{ticker}_final_fit")
        payload["ownership_alignment"] = _select("Ownership alignment", payload.get("ownership_alignment"), ("Unknown", "Strong", "Mixed", "Weak"), f"dca7_{ticker}_final_owner")
    with c3:
        payload["compensation_alignment"] = _select("Compensation alignment", payload.get("compensation_alignment"), ("Unknown", "Strong", "Mixed", "Weak"), f"dca7_{ticker}_final_comp")
        payload["insider_behavior"] = _select("Insider behavior", payload.get("insider_behavior"), ("Unknown", "Supportive", "Neutral", "Concerning", "Mixed"), f"dca7_{ticker}_final_insider")
    payload["critical_strengths"] = st.text_area("Critical strengths", value=str(payload.get("critical_strengths") or ""), key=f"dca7_{ticker}_strengths")
    payload["critical_concerns"] = st.text_area("Critical concerns", value=str(payload.get("critical_concerns") or ""), key=f"dca7_{ticker}_concerns")
    payload["critical_unknowns"] = st.text_area("Critical unknowns", value=str(payload.get("critical_unknowns") or ""), key=f"dca7_{ticker}_unknowns")
    payload["evidence_that_would_change_view"] = st.text_area("Evidence that would change my view", value=str(payload.get("evidence_that_would_change_view") or ""), key=f"dca7_{ticker}_change_view")
    payload["analyst_summary"] = st.text_area("Kết luận Chương 7 của analyst", value=str(payload.get("analyst_summary") or ""), key=f"dca7_{ticker}_summary")
    st.caption("Phase 7A chưa có Chapter 7 Completion Gate chính thức; gate source-closure sẽ được khóa ở Phase 7D sau khi 7B/7C hoàn tất. Phase 7B cũng không tạo Completion Gate; final source-closure vẫn thuộc Phase 7D.")


def render_chapter7_tab(default_ticker: str = "") -> None:
    ticker = _safe_ticker(
        st.text_input("Mã cổ phiếu", value=_safe_ticker(default_ticker) or "DGC", key="dca_ch7_ticker")
    ) or "DGC"
    payload = load_record(ticker)
    payload["ticker"] = ticker
    payload["company_name"] = st.text_input(
        "Tên doanh nghiệp", value=str(payload.get("company_name") or ""), key=f"dca7_{ticker}_company_name"
    )

    st.title("👥 Chương 7 — Ban điều hành: Nền tảng & Phân loại")
    st.caption("Assessing the Quality of Management — Background and Classification: Who Are They? | Phase 7A + 7B structured data bridge")
    _render_source_lock()
    _render_status_panel(ticker, payload)

    with st.container(border=True):
        payload = render_structured_management_bridge(ticker, payload)

    with st.container(border=True):
        _render_q33(ticker, payload)
    with st.container(border=True):
        _render_q34(ticker, payload)
    with st.container(border=True):
        _render_q35(ticker, payload)
    with st.container(border=True):
        _render_q36(ticker, payload)
    with st.container(border=True):
        _render_q37(ticker, payload)
    with st.container(border=True):
        _render_q38(ticker, payload)
    with st.container(border=True):
        _render_evidence_and_events(ticker, payload)
    with st.container(border=True):
        _render_final_conclusion(ticker, payload)

    warnings = research_gap_warnings(payload)
    if warnings:
        st.warning("Consistency / Research Gap:\n\n- " + "\n- ".join(warnings))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("💾 Lưu Chapter 7 — Phase 7A+7B", use_container_width=True, key=f"dca7_{ticker}_save"):
            save_record(ticker, payload, str(payload.get("company_name") or ""))
            st.success("Đã lưu Phase 7A+7B. Structured bridge không ghi đè classification/conclusion của analyst.")
    with c2:
        if st.button("📸 Lưu snapshot Chapter 7", use_container_width=True, key=f"dca7_{ticker}_snapshot"):
            snapshot_id = create_snapshot(ticker, payload)
            st.success(f"Đã lưu snapshot #{snapshot_id}.")

    snapshots = pd.DataFrame(list_snapshots(ticker, 20))
    if not snapshots.empty:
        st.markdown("### Snapshot History")
        render_static_table(snapshots, height=300, sort_key=f"dca7_{ticker}_snapshots")


__all__ = ["render_chapter7_tab"]
