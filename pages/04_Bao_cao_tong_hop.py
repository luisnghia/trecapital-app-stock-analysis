from __future__ import annotations

import pandas as pd
import streamlit as st
from tre_full_width import apply_full_width
from tre_sidebar_nav import render_tre_sidebar_nav

# Import module2_dashboard first: it owns the shared page config, theme CSS and data loaders.
import module2_dashboard as md
from module2_engine import (
    build_module2_valuation_table,
    build_valuation_range,
    build_porter_moat_scorecard,
    build_value_chain_table,
    build_risk_scenario_table,
    build_module2_summary,
    load_assumptions,
)
from report_exporter import build_report_package, render_report_package_as_app_page
from modules.deep_company_analysis.chapter7 import load_record as load_chapter7_record
from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_completion import build_completion_gate, completion_gate_text
from modules.deep_company_analysis.chapter8_integration import build_chapter8_report_frames, build_chapter8_summary
from modules.deep_company_analysis.chapter9_completion import append_completion_log as append_chapter9_log
from modules.deep_company_analysis.chapter9_history import (
    HISTORY_BOUNDARY,
    build_chapter9_report_frames,
    build_chapter9_summary,
    compare_chapter9_payloads,
)
from modules.deep_company_analysis.chapter9_store import (
    list_snapshots as list_chapter9_snapshots,
    load_record as load_chapter9_record,
    load_snapshot as load_chapter9_snapshot,
)
from modules.deep_company_analysis.table_format import render_static_table, static_table_html


APP_VERSION = "secure-ui-current"
SOURCE_DISPLAY_TO_INTERNAL = {
    "Tự động": "Tự động từ dữ liệu tổng quan",
    "Dữ liệu ưu tiên 1": "FireAnt + Vietstock",
    "Dữ liệu ưu tiên 2": "FireAnt",
    "Dữ liệu ưu tiên 3": "Vietstock",
    "Dữ liệu tích hợp": "Financial tích hợp",
    "Dữ liệu mẫu": "CSV mẫu tích hợp",
}
SOURCE_OPTIONS = list(SOURCE_DISPLAY_TO_INTERNAL.keys())


def _default_ticker() -> str:
    for key in ["active_ticker", "module2_ticker", "module1_ticker", "shared_ticker", "last_query_ticker"]:
        value = md._safe_ticker(str(st.session_state.get(key, "")))
        if value:
            return value
    return "DCM"


def _render_ch9_html_table(frame: pd.DataFrame, *, height: int) -> None:
    """Phase 9H read-only report tables follow the app rule: st.html + wrapped table cells."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.caption("Chưa có dữ liệu.")
        return
    table_html = static_table_html(frame, height=height)
    if table_html:
        st.html(table_html)


def _snapshot_label(row: dict) -> str:
    return f"#{int(row.get('id', 0))} | {row.get('created_at', '')} | {row.get('research_status', '')}"


def _render_chapter9_history_delta(ticker: str, current_payload: dict, chapter7_payload: dict) -> None:
    st.markdown("### Phase 9H — Snapshot History & Delta Review")
    st.caption(HISTORY_BOUNDARY)
    with st.expander("📖 Giải thích thuật ngữ Phase 9H", expanded=False):
        st.markdown(
            """
- **Snapshot:** bản chụp bất biến của Chapter 9 workspace tại một thời điểm; preview/compare không tự restore current workspace.
- **Delta Review:** so sánh hai trạng thái nghiên cứu để thấy field/evidence/gap/event/closure nào thay đổi; không diễn giải thay đổi là management tốt lên hay xấu đi.
- **Current Workspace:** trạng thái Chapter 9 hiện đang lưu; có thể so với một snapshot lịch sử.
- **Added / Removed / Changed:** thay đổi hồ sơ bằng chứng, không phải tín hiệu tích cực/tiêu cực.
- **Gap Closed / Reopened:** thay đổi trạng thái research gap do analyst quản lý; đóng gap có thể là verified evidence hoặc documented known unknown tùy hồ sơ.
- **Newly closed dimension:** source dimension chuyển sang trạng thái Closed theo Phase 9G; không phải điểm chất lượng quản lý.
            """
        )
        st.caption(
            "Closure delta của snapshot dùng Chapter 7 manager master hiện tại làm SSOT cho cả hai vế so sánh; app không tạo manager history thay thế."
        )

    snapshots = list_chapter9_snapshots(ticker, 50)
    if not snapshots:
        st.info("Chưa có Chapter 9 snapshot để so sánh. Hãy lưu snapshot trong workspace Chapter 9 trước.")
        return

    snapshot_frame = pd.DataFrame(snapshots)
    st.markdown("**Snapshot audit trail**")
    _render_ch9_html_table(snapshot_frame, height=300)

    labels = [_snapshot_label(row) for row in snapshots]
    label_to_id = {label: int(row["id"]) for label, row in zip(labels, snapshots)}
    c1, c2 = st.columns(2)
    with c1:
        baseline_label = st.selectbox(
            "Baseline snapshot",
            labels,
            index=min(1, len(labels) - 1),
            key=f"ch9_report_{ticker}_baseline_snapshot",
        )
    with c2:
        comparison_options = ["Current Workspace"] + labels
        comparison_label = st.selectbox(
            "Comparison state",
            comparison_options,
            index=0,
            key=f"ch9_report_{ticker}_comparison_snapshot",
        )

    baseline = load_chapter9_snapshot(label_to_id[baseline_label])
    if not isinstance(baseline, dict):
        st.warning("Không đọc được baseline snapshot; không thực hiện delta review.")
        return
    if comparison_label == "Current Workspace":
        comparison = current_payload
        comparison_ref = "Current Workspace"
    else:
        comparison = load_chapter9_snapshot(label_to_id[comparison_label])
        comparison_ref = comparison_label
    if not isinstance(comparison, dict):
        st.warning("Không đọc được comparison snapshot; không thực hiện delta review.")
        return

    delta = compare_chapter9_payloads(baseline, comparison, chapter7_payload)
    summary = delta["summary"]
    st.caption(f"Đang so sánh: {baseline_label} → {comparison_ref}")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Question-field changes", summary["question_field_changes"])
    m2.metric("Evidence + / -", f"+{summary['evidence_added']} / -{summary['evidence_removed']}")
    m3.metric("Gap closed / reopened", f"{summary['gaps_closed']} / {summary['gaps_reopened']}")
    m4.metric("Closure changes", summary["closure_status_changes"])
    m5.metric("Dimensions newly closed", summary["dimensions_newly_closed"])
    st.caption(
        f"Research Completion Gate: {summary['before_research_completion_gate']} → {summary['after_research_completion_gate']}"
    )
    st.caption("Các số delta là tally thay đổi hồ sơ nghiên cứu, không phải score, rank hay investment signal.")

    delta_sections = [
        ("Q48–Q52 analyst-field changes", delta["question_delta"], 360),
        ("Evidence delta", delta["evidence_delta"], 420),
        ("Research-gap delta", delta["gap_delta"], 420),
        ("Behavior-event delta", delta["behavior_event_delta"], 380),
        ("Source-dimension closure delta", delta["closure_delta"], 460),
    ]
    any_delta = False
    for title, frame, height in delta_sections:
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            any_delta = True
            st.markdown(f"**{title}**")
            _render_ch9_html_table(frame, height=height)
    if not any_delta:
        st.success("Không có thay đổi được ghi nhận giữa hai trạng thái đã chọn.")

    if st.button(
        "🧾 Ghi log Delta Review Chapter 9",
        use_container_width=True,
        key=f"ch9_report_{ticker}_log_delta",
    ):
        append_chapter9_log(
            ticker,
            "phase9h_delta_review",
            {
                "baseline": baseline_label,
                "comparison": comparison_ref,
                "question_field_changes": summary["question_field_changes"],
                "evidence_added": summary["evidence_added"],
                "evidence_removed": summary["evidence_removed"],
                "gaps_closed": summary["gaps_closed"],
                "gaps_reopened": summary["gaps_reopened"],
                "closure_status_changes": summary["closure_status_changes"],
            },
        )
        st.success("Đã ghi diagnostic log Delta Review vào log Chapter 9.")


def render_consolidated_report_page() -> None:
    md._inject_runtime_ui_css()
    md._render_brand_page_header(
        "📄 Báo cáo tổng hợp toàn bộ nội dung",
        "Render toàn bộ từng tab của Tổng quan doanh nghiệp + Định giá chuyên sâu + So sánh doanh nghiệp trên một trang dài để in/Save as PDF, giữ format giống app nhất có thể.",
    )

    available_tickers = md._available_financial_tickers_cached(str(md.BUNDLED_XLSM)) if md.BUNDLED_XLSM.exists() else []

    with st.sidebar:
        render_tre_sidebar_nav()
        st.header("Thiết lập báo cáo tổng hợp")
        source_display = st.selectbox("Chế độ dữ liệu tài chính", SOURCE_OPTIONS, index=0, key="full_report_source")
        source = SOURCE_DISPLAY_TO_INTERNAL.get(source_display, source_display)
        ticker = st.text_input("Mã cổ phiếu", value=_default_ticker(), max_chars=12, key="full_report_ticker").upper().strip()
        if source == "Financial tích hợp" and available_tickers:
            chosen = st.selectbox("Mã có đủ BCTC trong dữ liệu tích hợp", ["-- Giữ mã đang nhập --"] + available_tickers, index=0, key="full_report_financial_ticker")
            if chosen != "-- Giữ mã đang nhập --":
                ticker = chosen
        target_mos_pct = st.selectbox(
            "Mức MOS yêu cầu (%)",
            md.MOS_OPTIONS_GLOBAL,
            index=md.MOS_OPTIONS_GLOBAL.index(md._normalize_mos_value(st.session_state.get("target_mos_pct", 50))),
            key="full_report_mos",
            help="MOS dùng chung để tính dải định giá và khuyến nghị trong báo cáo.",
        )
        st.session_state["target_mos_pct"] = float(target_mos_pct)
        table_mode = st.radio(
            "Độ dài bảng khi in PDF",
            ["Đầy đủ", "Gọn để in nhanh"],
            index=0,
            help="Đầy đủ giữ toàn bộ dòng; Gọn chỉ hiển thị tối đa 40 dòng mỗi bảng để PDF nhẹ hơn.",
        )
        reload_report = st.button("🔄 Cập nhật dữ liệu báo cáo", use_container_width=True)
        st.caption("PDF đẹp nhất: bấm nút in trong trang báo cáo, chọn A4 ngang và bật Background graphics.")

    if reload_report:
        md._load_overview_cached.clear()
        md._load_timeseries_cached.clear()
        st.toast("Đã làm mới cache đọc dữ liệu báo cáo.")

    ticker = md._safe_ticker(ticker) or _default_ticker()
    st.session_state["module2_ticker"] = ticker
    st.session_state["shared_ticker"] = ticker

    try:
        company, annual_df, quarterly_df, source_label, paths = md._load_data(ticker, source)
    except Exception as exc:
        st.error(f"Không tải được dữ liệu để dựng báo cáo tổng hợp cho {ticker}: {exc}")
        st.stop()

    assumptions = load_assumptions(md.ASSUMPTIONS_PATH)
    valuation_df = build_module2_valuation_table(company, annual_df, assumptions) if annual_df is not None and not annual_df.empty else pd.DataFrame()
    moat_df = build_porter_moat_scorecard(company, annual_df) if annual_df is not None else pd.DataFrame()
    value_chain_df = build_value_chain_table(company, annual_df) if annual_df is not None else pd.DataFrame()
    value_range = build_valuation_range(valuation_df, getattr(company, "current_price", None), float(target_mos_pct)) if not valuation_df.empty else None
    scenario_df = build_risk_scenario_table(company, annual_df, value_range) if value_range is not None and annual_df is not None and not annual_df.empty else pd.DataFrame()
    module2_summary = build_module2_summary(company, annual_df, valuation_df, moat_df) if annual_df is not None and not annual_df.empty else "Chưa đủ dữ liệu để tạo tóm tắt Định giá chuyên sâu."

    peer_df = st.session_state.get("peer_compare_result", pd.DataFrame())
    if not isinstance(peer_df, pd.DataFrame):
        peer_df = pd.DataFrame()
    web_df = st.session_state.get("module2_web_table", pd.DataFrame())
    if not isinstance(web_df, pd.DataFrame):
        web_df = pd.DataFrame()

    package = build_report_package(
        company,
        annual_df,
        quarterly_df,
        valuation_df=valuation_df,
        moat_df=moat_df,
        value_chain_df=value_chain_df,
        scenario_df=scenario_df,
        peer_df=peer_df,
        web_df=web_df,
        assumptions=assumptions,
        source_label="Dữ liệu nội bộ",
        paths=[],
        target_mos_pct=float(target_mos_pct),
        module2_summary=module2_summary,
    )

    max_rows = None if table_mode == "Đầy đủ" else 40
    render_report_package_as_app_page(package, show_export_hint=True, table_height=420, max_rows_per_table=max_rows)

    # Deep Company Analysis Chapter 8 is appended to the printable long report without altering
    # the existing valuation/report package or analyst-owned investment conclusions.
    ch8_company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    ch8_payload = load_chapter8_record(ticker, ch8_company_name)
    ch8_summary = build_chapter8_summary(ch8_payload)
    ch8_frames = build_chapter8_report_frames(ch8_payload)
    ch8_chapter7_payload = load_chapter7_record(ticker)
    ch8_structured = build_phase8b_context(
        ticker,
        annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame(),
        chapter7_payload=ch8_chapter7_payload,
        guidance_rows=ch8_payload.get("q41_guidance_history"),
    )
    ch8_gate = build_completion_gate(
        ch8_payload,
        structured_context=ch8_structured,
        chapter7_payload=ch8_chapter7_payload,
    )

    st.markdown("## 🧭 Deep Company Analysis — Chương 8: Năng lực vận hành Ban điều hành")
    st.caption("Q39–Q47 theo The Investment Checklist. Phần này trình bày trạng thái nghiên cứu và kết luận analyst; không phải Management Quality Score.")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Answered", f"{ch8_summary['answered']}/{ch8_summary['total_questions']}")
    m2.metric("Partial", ch8_summary["partial"])
    m3.metric("Evidence đã promote", ch8_summary["promoted_evidence"])
    m4.metric("Research gaps mở", ch8_summary["research_gaps_open"])
    m5.metric("Kết luận analyst", ch8_summary["analyst_conclusions"])

    st.markdown("### Final Research Completion Gate")
    if ch8_gate["ready_for_chapter_close"]:
        st.success(completion_gate_text(ch8_gate))
    else:
        st.warning(completion_gate_text(ch8_gate))
    render_static_table(ch8_gate["table"], height=470)
    st.caption(ch8_gate["gate_boundary"])

    render_static_table(ch8_frames["status"], height=430)
    if not ch8_frames["evidence"].empty:
        st.markdown("### Evidence Matrix — analyst đã promote / nhập thủ công")
        render_static_table(ch8_frames["evidence"], height=430)
    if not ch8_frames["research_gaps"].empty:
        st.markdown("### Research Gaps")
        render_static_table(ch8_frames["research_gaps"], height=360)
    if not ch8_frames["capital_allocation"].empty:
        st.markdown("### Q46 — Capital Allocation Decision Register")
        render_static_table(ch8_frames["capital_allocation"], height=390)
    if not ch8_frames["buybacks"].empty:
        st.markdown("### Q47 — Explicit Buyback History")
        render_static_table(ch8_frames["buybacks"], height=390)

    st.caption("AI/Data = Research Assistant; Analyst = người kết luận. Chapter 8 không tự thay đổi MOS, Research Gate hoặc BUY/HOLD/SELL.")

    # Chapter 9 Phase 9H: consolidated report + immutable snapshot delta review. This section is
    # descriptive only and does not feed management research into valuation or investment gates.
    ch9_company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    ch9_payload = load_chapter9_record(ticker, ch9_company_name)
    ch9_chapter7_payload = load_chapter7_record(ticker)
    ch9_summary = build_chapter9_summary(ch9_payload, ch9_chapter7_payload)
    ch9_frames = build_chapter9_report_frames(ch9_payload, ch9_chapter7_payload)

    st.markdown("## 🧠 Deep Company Analysis — Chương 9: Phẩm chất tích cực & tiêu cực của Ban điều hành")
    st.caption(
        "Q48–Q52 theo Michael Shearn — The Investment Checklist — Chapter 9. Báo cáo giữ nguyên kết luận analyst và source coverage; không tự chấm Management Quality Score."
    )
    n1, n2, n3, n4, n5 = st.columns(5)
    n1.metric("Answered", f"{ch9_summary['answered']}/{ch9_summary['total_questions']}")
    n2.metric("Evidence rows", ch9_summary["evidence_rows"])
    n3.metric("Open research gaps", ch9_summary["research_gaps_open"])
    n4.metric("Closed dimensions", f"{ch9_summary['closed_dimensions']}/{ch9_summary['source_dimension_count']}")
    n5.metric("Ready questions", f"{ch9_summary['ready_questions']}/{ch9_summary['total_questions']}")

    gate = str(ch9_summary["research_completion_gate"])
    st.markdown("### Phase 9G Research Completion Gate")
    if gate.startswith("Ready"):
        st.success(gate)
    elif gate.startswith("Review"):
        st.warning(gate)
    else:
        st.error(gate)
    st.caption("Research-completion process only — không phải Research Gate đầu tư.")

    st.markdown("### Q48–Q52 Consolidated Analyst Report")
    _render_ch9_html_table(ch9_frames["questions"], height=520)
    with st.expander("26 source-dimension closure records", expanded=False):
        _render_ch9_html_table(ch9_frames["dimension_closure"], height=620)
    if not ch9_frames["evidence"].empty:
        st.markdown("### Chapter 9 Evidence Matrix — analyst đã promote / nhập thủ công")
        _render_ch9_html_table(ch9_frames["evidence"], height=520)
    if not ch9_frames["research_gaps"].empty:
        st.markdown("### Chapter 9 Research Gaps")
        _render_ch9_html_table(ch9_frames["research_gaps"], height=440)
    if not ch9_frames["behavior_events"].empty:
        st.markdown("### Chapter 9 Dated Management / Behavior Events")
        _render_ch9_html_table(ch9_frames["behavior_events"], height=440)
    with st.expander("Q48 — 6 source-locked Passion Research Prompts", expanded=False):
        _render_ch9_html_table(ch9_frames["q48_passion_research"], height=460)

    _render_chapter9_history_delta(ticker, ch9_payload, ch9_chapter7_payload)
    st.caption(
        "AI/Data = Research Assistant; Analyst = người kết luận. Chapter 9 consolidated report/history không tự thay đổi MOS, investment Research Gate hoặc BUY/HOLD/SELL."
    )


render_consolidated_report_page()
apply_full_width()