from __future__ import annotations

"""Idempotently integrate approved Chapter 4 Phase 4A into the unified app and CI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
CH4 = ROOT / "modules" / "deep_company_analysis" / "chapter4.py"
WORKFLOW = ROOT / ".github" / "workflows" / "deep-company-analysis.yml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Patch target not found: {label}")
    return text.replace(old, new, 1)


def patch_page() -> None:
    text = PAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from modules.deep_company_analysis.chapter3_page_support import render_chapter3_tab\n",
        "from modules.deep_company_analysis.chapter3_page_support import render_chapter3_tab\nfrom modules.deep_company_analysis.chapter4 import render_chapter4\n",
        "page chapter4 import",
    )
    text = replace_once(
        text,
        '        or st.session_state.get("dca_ch3_ticker")\n        or st.session_state.get("active_ticker")',
        '        or st.session_state.get("dca_ch3_ticker")\n        or st.session_state.get("dca_ch4_ticker")\n        or st.session_state.get("active_ticker")',
        "page default ticker ch4 state",
    )
    text = replace_once(
        text,
        'chapter1_tab, chapter2_tab, chapter3_tab = st.tabs([\n    "📗 Chương 1 — Cơ hội đầu tư",\n    "📘 Chương 2 — Hiểu doanh nghiệp",\n    "📙 Chương 3 — Góc nhìn khách hàng",\n])',
        'chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab = st.tabs([\n    "📗 Chương 1 — Cơ hội đầu tư",\n    "📘 Chương 2 — Hiểu doanh nghiệp",\n    "📙 Chương 3 — Góc nhìn khách hàng",\n    "📕 Chương 4 — Lợi thế & ngành",\n])',
        "page chapter tabs",
    )
    old_tail = '''with chapter3_tab:\n    chapter3_ticker = _safe_ticker(\n        str(\n            st.session_state.get("dca_ch3_ticker")\n            or st.session_state.get("dca_ch2_ticker")\n            or st.session_state.get("dca_ch1_ticker")\n            or st.session_state.get("active_ticker")\n            or default_ticker\n        )\n    ) or default_ticker\n    render_chapter3_tab(chapter3_ticker)\n\napply_full_width()'''
    new_tail = '''with chapter3_tab:\n    chapter3_ticker = _safe_ticker(\n        str(\n            st.session_state.get("dca_ch3_ticker")\n            or st.session_state.get("dca_ch2_ticker")\n            or st.session_state.get("dca_ch1_ticker")\n            or st.session_state.get("active_ticker")\n            or default_ticker\n        )\n    ) or default_ticker\n    render_chapter3_tab(chapter3_ticker)\n\nwith chapter4_tab:\n    chapter4_ticker = _safe_ticker(\n        str(\n            st.session_state.get("dca_ch4_ticker")\n            or st.session_state.get("dca_ch3_ticker")\n            or st.session_state.get("dca_ch2_ticker")\n            or st.session_state.get("dca_ch1_ticker")\n            or st.session_state.get("active_ticker")\n            or default_ticker\n        )\n    ) or default_ticker\n    render_chapter4(default_ticker=chapter4_ticker)\n\napply_full_width()'''
    text = replace_once(text, old_tail, new_tail, "page chapter4 tab body")
    PAGE.write_text(text, encoding="utf-8")


def patch_chapter4_nested_expanders() -> None:
    text = CH4.read_text(encoding="utf-8")
    old = '''    with st.expander("Q15 — Sustainable Competitive Advantage", expanded=True):\n        _render_q15(record, ticker)\n    with st.expander("Q16 — Pricing Power", expanded=False):\n        _render_q16(record, ticker)\n    with st.expander("Q17 — Good or Bad Industry", expanded=False):\n        _render_q17(record, ticker)\n    with st.expander("Q18 — Industry Evolution", expanded=False):\n        _render_q18(record, ticker)\n    with st.expander("Q19 — Competitive Landscape", expanded=False):\n        _render_q19(record, ticker)\n    with st.expander("Q20 — Supplier Relationships", expanded=False):\n        _render_q20(record, ticker)\n\n    _render_synthesis(record, ticker)'''
    new = '''    q15_tab, q16_tab, q17_tab, q18_tab, q19_tab, q20_tab = st.tabs([\n        "Q15 — Lợi thế cạnh tranh",\n        "Q16 — Pricing Power",\n        "Q17 — Chất lượng ngành",\n        "Q18 — Tiến hóa ngành",\n        "Q19 — Cạnh tranh",\n        "Q20 — Nhà cung cấp",\n    ])\n    with q15_tab:\n        _render_q15(record, ticker)\n    with q16_tab:\n        _render_q16(record, ticker)\n    with q17_tab:\n        _render_q17(record, ticker)\n    with q18_tab:\n        _render_q18(record, ticker)\n    with q19_tab:\n        _render_q19(record, ticker)\n    with q20_tab:\n        _render_q20(record, ticker)\n\n    _render_synthesis(record, ticker)'''
    text = replace_once(text, old, new, "chapter4 nested expander layout")
    CH4.write_text(text, encoding="utf-8")


def patch_workflow() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    text = text.replace("Compile deep-analysis Chapters 1-3", "Compile deep-analysis Chapters 1-4")
    text = replace_once(
        text,
        "      - name: Run live DGC Chapter 2 end-to-end diagnostic\n",
        "      - name: Run Chapter 4 approved Phase 4A source-locked acceptance explicitly\n        run: |\n          python -m pytest -q modules/deep_company_analysis/test_chapter4.py\n      - name: Run live DGC Chapter 2 end-to-end diagnostic\n",
        "workflow ch4 test",
    )
    text = text.replace("Build lightweight Windows offline package V15", "Build lightweight Windows offline package V16")
    text = text.replace('PKG_NAME="Trecapital_Deep_Analysis_Offline_V15"', 'PKG_NAME="Trecapital_Deep_Analysis_Offline_V16"')
    text = replace_once(
        text,
        '          test -f "dist/${PKG_NAME}/modules/deep_company_analysis/chapter3.py"\n',
        '          test -f "dist/${PKG_NAME}/modules/deep_company_analysis/chapter3.py"\n          test -f "dist/${PKG_NAME}/modules/deep_company_analysis/chapter4.py"\n',
        "workflow package chapter4",
    )
    text = replace_once(
        text,
        '          test -f "dist/${PKG_NAME}/docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER3.md"\n',
        '          test -f "dist/${PKG_NAME}/docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER3.md"\n          test -f "dist/${PKG_NAME}/docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER4.md"\n',
        "workflow package ch4 context",
    )
    text = text.replace("Upload offline package V15", "Upload offline package V16")
    text = text.replace("Trecapital_Deep_Analysis_Offline_V15", "Trecapital_Deep_Analysis_Offline_V16")
    # Ensure future CI reacts to Chapter 4 context changes.
    needle = "      - 'docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER3.md'\n"
    addition = needle + "      - 'docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER4.md'\n"
    if "docs/CONTEXT_DEEP_COMPANY_ANALYSIS_CHAPTER4.md" not in text.split("permissions:", 1)[0]:
        text = text.replace(needle, addition)
    WORKFLOW.write_text(text, encoding="utf-8")


def main() -> None:
    patch_page()
    patch_chapter4_nested_expanders()
    patch_workflow()
    print("Applied Chapter 4 Phase 4A integration patch.")


if __name__ == "__main__":
    main()
