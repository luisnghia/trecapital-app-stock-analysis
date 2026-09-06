from __future__ import annotations

"""Apply the Phase 8E Chapter 8 integration to the unified DCA and consolidated report pages.

The patch is deliberately idempotent and fails loudly if an expected V45 anchor disappears.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DCA_PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
REPORT_PAGE = ROOT / "pages" / "04_Bao_cao_tong_hop.py"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 8E anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_dca_page(text: str) -> str:
    # V50 replaced eager st.tabs with lazy chapter selection. If Chapter 8 is already
    # integrated in that architecture, Phase 8E is complete and this legacy migrator
    # must be a no-op rather than trying to recreate the obsolete tab anchors.
    if (
        "CHAPTER_OPTIONS = (" in text
        and "active_chapter = st.radio(" in text
        and "render_chapter8_tab(chapter8_ticker)" in text
        and "from modules.deep_company_analysis.chapter8_page_support import render_chapter8_tab" in text
        and "from modules.deep_company_analysis.chapter8_integration import build_chapter8_summary" in text
        and "from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record" in text
    ):
        return text
    text = _replace_once(
        text,
        "from modules.deep_company_analysis.chapter7_page_support import render_chapter7_tab\n",
        "from modules.deep_company_analysis.chapter7_page_support import render_chapter7_tab\n"
        "from modules.deep_company_analysis.chapter8_page_support import render_chapter8_tab\n"
        "from modules.deep_company_analysis.chapter8_integration import build_chapter8_summary\n"
        "from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record\n",
        "Chapter 8 integration imports",
    )
    text = _replace_once(
        text,
        "        or st.session_state.get(\"dca_ch7_ticker\")\n        or st.session_state.get(\"dca_ch6_ticker\")\n",
        "        or st.session_state.get(\"dca_ch7_ticker\")\n"
        "        or st.session_state.get(\"dca_ch8_ticker\")\n"
        "        or st.session_state.get(\"dca_ch6_ticker\")\n",
        "Chapter 8 ticker fallback",
    )
    old_tabs = '''chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab, chapter6_tab, chapter7_tab = st.tabs([\n    "📗 Chương 1 — Cơ hội đầu tư",\n    "📘 Chương 2 — Hiểu doanh nghiệp",\n    "📙 Chương 3 — Góc nhìn khách hàng",\n    "📕 Chương 4 — Lợi thế & ngành",\n    "📒 Chương 5 — Hoạt động & tài chính",\n    "📓 Chương 6 — Earnings & dòng tiền",\n    "👥 Chương 7 — Ban điều hành",\n])\n'''
    new_tabs = '''chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab, chapter6_tab, chapter7_tab, chapter8_tab = st.tabs([\n    "📗 Chương 1 — Cơ hội đầu tư",\n    "📘 Chương 2 — Hiểu doanh nghiệp",\n    "📙 Chương 3 — Góc nhìn khách hàng",\n    "📕 Chương 4 — Lợi thế & ngành",\n    "📒 Chương 5 — Hoạt động & tài chính",\n    "📓 Chương 6 — Earnings & dòng tiền",\n    "👥 Chương 7 — Ban điều hành",\n    "🧭 Chương 8 — Năng lực vận hành",\n])\n'''
    text = _replace_once(text, old_tabs, new_tabs, "Chapter 8 unified tab")

    old_summary_anchor = ''') or "DGC"\n\nchapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab, chapter6_tab, chapter7_tab, chapter8_tab = st.tabs([\n'''
    new_summary_anchor = ''') or "DGC"\n\n# Phase 8E summary is descriptive only. It never computes a management score or changes the investment gate.\n_ch8_summary_payload = load_chapter8_record(default_ticker)\n_ch8_summary = build_chapter8_summary(_ch8_summary_payload)\nwith st.expander("🧭 Trạng thái nghiên cứu Chương 8 — Q39 đến Q47", expanded=False):\n    c1, c2, c3, c4, c5 = st.columns(5)\n    c1.metric("Answered", f"{_ch8_summary['answered']}/{_ch8_summary['total_questions']}")\n    c2.metric("Partial", _ch8_summary["partial"])\n    c3.metric("Promoted evidence", _ch8_summary["promoted_evidence"])\n    c4.metric("Open research gaps", _ch8_summary["research_gaps_open"])\n    c5.metric("Analyst conclusions", _ch8_summary["analyst_conclusions"])\n    st.caption("Đây là research-completeness summary, không phải Management Quality Score và không tạo BUY/HOLD/SELL.")\n\nchapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab, chapter6_tab, chapter7_tab, chapter8_tab = st.tabs([\n'''
    text = _replace_once(text, old_summary_anchor, new_summary_anchor, "Chapter 8 status summary")

    old_tail = '''    render_chapter7_tab(chapter7_ticker)\n\napply_full_width()\n'''
    new_tail = '''    render_chapter7_tab(chapter7_ticker)\n\nwith chapter8_tab:\n    chapter8_ticker = _safe_ticker(\n        str(\n            st.session_state.get("dca_ch8_ticker")\n            or st.session_state.get("dca_ch7_ticker")\n            or st.session_state.get("dca_ch6_ticker")\n            or st.session_state.get("dca_ch5_ticker")\n            or st.session_state.get("dca_ch4_ticker")\n            or st.session_state.get("dca_ch3_ticker")\n            or st.session_state.get("dca_ch2_ticker")\n            or st.session_state.get("dca_ch1_ticker")\n            or st.session_state.get("active_ticker")\n            or default_ticker\n        )\n    ) or default_ticker\n    render_chapter8_tab(chapter8_ticker)\n\napply_full_width()\n'''
    return _replace_once(text, old_tail, new_tail, "Chapter 8 tab renderer")


def patch_report_page(text: str) -> str:
    text = _replace_once(
        text,
        "from report_exporter import build_report_package, render_report_package_as_app_page\n",
        "from report_exporter import build_report_package, render_report_package_as_app_page\n"
        "from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record\n"
        "from modules.deep_company_analysis.chapter8_integration import build_chapter8_report_frames, build_chapter8_summary\n"
        "from modules.deep_company_analysis.table_format import render_static_table\n",
        "Chapter 8 consolidated report imports",
    )
    old = '''    max_rows = None if table_mode == "Đầy đủ" else 40\n    render_report_package_as_app_page(package, show_export_hint=True, table_height=420, max_rows_per_table=max_rows)\n'''
    new = '''    max_rows = None if table_mode == "Đầy đủ" else 40\n    render_report_package_as_app_page(package, show_export_hint=True, table_height=420, max_rows_per_table=max_rows)\n\n    # Deep Company Analysis Chapter 8 is appended to the printable long report without altering\n    # the existing valuation/report package or analyst-owned investment conclusions.\n    ch8_company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")\n    ch8_payload = load_chapter8_record(ticker, ch8_company_name)\n    ch8_summary = build_chapter8_summary(ch8_payload)\n    ch8_frames = build_chapter8_report_frames(ch8_payload)\n\n    st.markdown("## 🧭 Deep Company Analysis — Chương 8: Năng lực vận hành Ban điều hành")\n    st.caption("Q39–Q47 theo The Investment Checklist. Phần này trình bày trạng thái nghiên cứu và kết luận analyst; không phải Management Quality Score.")\n    m1, m2, m3, m4, m5 = st.columns(5)\n    m1.metric("Answered", f"{ch8_summary['answered']}/{ch8_summary['total_questions']}")\n    m2.metric("Partial", ch8_summary["partial"])\n    m3.metric("Evidence đã promote", ch8_summary["promoted_evidence"])\n    m4.metric("Research gaps mở", ch8_summary["research_gaps_open"])\n    m5.metric("Kết luận analyst", ch8_summary["analyst_conclusions"])\n\n    render_static_table(ch8_frames["status"], height=430)\n    if not ch8_frames["evidence"].empty:\n        st.markdown("### Evidence Matrix — analyst đã promote / nhập thủ công")\n        render_static_table(ch8_frames["evidence"], height=430)\n    if not ch8_frames["research_gaps"].empty:\n        st.markdown("### Research Gaps")\n        render_static_table(ch8_frames["research_gaps"], height=360)\n    if not ch8_frames["capital_allocation"].empty:\n        st.markdown("### Q46 — Capital Allocation Decision Register")\n        render_static_table(ch8_frames["capital_allocation"], height=390)\n    if not ch8_frames["buybacks"].empty:\n        st.markdown("### Q47 — Explicit Buyback History")\n        render_static_table(ch8_frames["buybacks"], height=390)\n\n    st.caption("AI/Data = Research Assistant; Analyst = người kết luận. Chapter 8 không tự thay đổi MOS, Research Gate hoặc BUY/HOLD/SELL.")\n'''
    return _replace_once(text, old, new, "Chapter 8 consolidated report section")


def main() -> None:
    dca_before = DCA_PAGE.read_text(encoding="utf-8")
    report_before = REPORT_PAGE.read_text(encoding="utf-8")
    dca_after = patch_dca_page(dca_before)
    report_after = patch_report_page(report_before)
    DCA_PAGE.write_text(dca_after, encoding="utf-8")
    REPORT_PAGE.write_text(report_after, encoding="utf-8")
    print(f"Phase 8E patched: {DCA_PAGE.relative_to(ROOT)}, {REPORT_PAGE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
