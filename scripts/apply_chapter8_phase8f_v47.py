from __future__ import annotations

"""Apply the small Phase 8F UI/report integration patch.

Kept as an idempotent script so GitHub Actions can compile/test the exact integrated source
and commit the resulting two file edits back to the V47 branch.
"""

from pathlib import Path


PAGE_SUPPORT = Path("modules/deep_company_analysis/chapter8_page_support.py")
REPORT_PAGE = Path("pages/04_Bao_cao_tong_hop.py")


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase 8F patch anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_page_support() -> None:
    text = PAGE_SUPPORT.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        "from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context\n",
        "from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context\n"
        "from modules.deep_company_analysis.chapter8_completion import build_completion_gate, completion_gate_text\n",
        label="page support completion import",
    )
    text = text.replace(
        "Management Competence: How Management Operates the Business | Phase 8A + 8B + 8C + 8D UI",
        "Management Competence: How Management Operates the Business | Phase 8A–8F | final research-completion gate",
    )

    anchor = '''    with st.container(border=True):\n        _render_evidence_gap_events(ticker, payload)\n\n    warnings = ch8.research_gap_warnings(payload)\n'''
    insert = '''    with st.container(border=True):\n        _render_evidence_gap_events(ticker, payload)\n\n    completion_context = build_phase8b_context(\n        ticker,\n        annual,\n        chapter7_payload=chapter7_payload,\n        guidance_rows=payload.get("q41_guidance_history"),\n    )\n    completion_gate = build_completion_gate(\n        payload,\n        structured_context=completion_context,\n        chapter7_payload=chapter7_payload,\n    )\n    with st.container(border=True):\n        st.markdown("### ✅ Final Research Completion Gate — Q39–Q47")\n        gate_text = completion_gate_text(completion_gate)\n        if completion_gate["ready_for_chapter_close"]:\n            st.success(gate_text)\n        else:\n            st.warning(gate_text)\n        g1, g2, g3, g4 = st.columns(4)\n        g1.metric("Closed questions", f"{completion_gate['closed_count']}/{completion_gate['total_questions']}")\n        g2.metric("Open questions", len(completion_gate["open_questions"]))\n        g3.metric("Q43 dimensions evidenced", f"{completion_gate['q43_dimensions_evidenced']}/{completion_gate['q43_dimensions_total']}")\n        g4.metric("Q46 source lock", "PASS" if completion_gate["q46_source_lock_ok"] else "FAIL")\n        render_static_table(completion_gate["table"], height=470, sort_key=f"dca8_{ticker}_completion_gate")\n        st.caption(completion_gate["gate_boundary"])\n\n    warnings = ch8.research_gap_warnings(payload)\n'''
    text = _replace_once(text, anchor, insert, label="page support completion container")
    PAGE_SUPPORT.write_text(text, encoding="utf-8")


def patch_report_page() -> None:
    text = REPORT_PAGE.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        "from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record\n",
        "from modules.deep_company_analysis.chapter7 import load_record as load_chapter7_record\n"
        "from modules.deep_company_analysis.chapter8_store import load_record as load_chapter8_record\n"
        "from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context\n"
        "from modules.deep_company_analysis.chapter8_completion import build_completion_gate, completion_gate_text\n",
        label="report completion imports",
    )

    anchor = '''    ch8_summary = build_chapter8_summary(ch8_payload)\n    ch8_frames = build_chapter8_report_frames(ch8_payload)\n\n    st.markdown("## 🧭 Deep Company Analysis — Chương 8: Năng lực vận hành Ban điều hành")\n'''
    insert = '''    ch8_summary = build_chapter8_summary(ch8_payload)\n    ch8_frames = build_chapter8_report_frames(ch8_payload)\n    ch8_chapter7_payload = load_chapter7_record(ticker)\n    ch8_structured = build_phase8b_context(\n        ticker,\n        annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame(),\n        chapter7_payload=ch8_chapter7_payload,\n        guidance_rows=ch8_payload.get("q41_guidance_history"),\n    )\n    ch8_gate = build_completion_gate(\n        ch8_payload,\n        structured_context=ch8_structured,\n        chapter7_payload=ch8_chapter7_payload,\n    )\n\n    st.markdown("## 🧭 Deep Company Analysis — Chương 8: Năng lực vận hành Ban điều hành")\n'''
    text = _replace_once(text, anchor, insert, label="report gate build")

    anchor2 = '''    m5.metric("Kết luận analyst", ch8_summary["analyst_conclusions"])\n\n    render_static_table(ch8_frames["status"], height=430)\n'''
    insert2 = '''    m5.metric("Kết luận analyst", ch8_summary["analyst_conclusions"])\n\n    st.markdown("### Final Research Completion Gate")\n    if ch8_gate["ready_for_chapter_close"]:\n        st.success(completion_gate_text(ch8_gate))\n    else:\n        st.warning(completion_gate_text(ch8_gate))\n    render_static_table(ch8_gate["table"], height=470)\n    st.caption(ch8_gate["gate_boundary"])\n\n    render_static_table(ch8_frames["status"], height=430)\n'''
    text = _replace_once(text, anchor2, insert2, label="report gate render")
    REPORT_PAGE.write_text(text, encoding="utf-8")


def main() -> int:
    patch_page_support()
    patch_report_page()
    print(f"Phase 8F patched: {PAGE_SUPPORT}, {REPORT_PAGE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
