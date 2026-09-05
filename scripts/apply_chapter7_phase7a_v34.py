from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase7A integration marker not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from modules.deep_company_analysis.chapter6_page_support import render_chapter6_tab\n",
        "from modules.deep_company_analysis.chapter6_page_support import render_chapter6_tab\n"
        "from modules.deep_company_analysis.chapter7_page_support import render_chapter7_tab\n",
        "chapter7 import",
    )
    text = replace_once(
        text,
        '        or st.session_state.get("dca_ch6_ticker")\n        or st.session_state.get("dca_ch5_ticker")\n',
        '        or st.session_state.get("dca_ch7_ticker")\n        or st.session_state.get("dca_ch6_ticker")\n        or st.session_state.get("dca_ch5_ticker")\n',
        "default ticker",
    )
    text = replace_once(
        text,
        "chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab, chapter6_tab = st.tabs([\n"
        '    "📗 Chương 1 — Cơ hội đầu tư",\n'
        '    "📘 Chương 2 — Hiểu doanh nghiệp",\n'
        '    "📙 Chương 3 — Góc nhìn khách hàng",\n'
        '    "📕 Chương 4 — Lợi thế & ngành",\n'
        '    "📒 Chương 5 — Hoạt động & tài chính",\n'
        '    "📓 Chương 6 — Earnings & dòng tiền",\n'
        "])\n",
        "chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab, chapter6_tab, chapter7_tab = st.tabs([\n"
        '    "📗 Chương 1 — Cơ hội đầu tư",\n'
        '    "📘 Chương 2 — Hiểu doanh nghiệp",\n'
        '    "📙 Chương 3 — Góc nhìn khách hàng",\n'
        '    "📕 Chương 4 — Lợi thế & ngành",\n'
        '    "📒 Chương 5 — Hoạt động & tài chính",\n'
        '    "📓 Chương 6 — Earnings & dòng tiền",\n'
        '    "👥 Chương 7 — Ban điều hành",\n'
        "])\n",
        "tabs",
    )
    text = replace_once(
        text,
        "    render_chapter6_tab(chapter6_ticker)\n\napply_full_width()",
        "    render_chapter6_tab(chapter6_ticker)\n\n"
        "with chapter7_tab:\n"
        "    chapter7_ticker = _safe_ticker(\n"
        "        str(\n"
        '            st.session_state.get("dca_ch7_ticker")\n'
        '            or st.session_state.get("dca_ch6_ticker")\n'
        '            or st.session_state.get("dca_ch5_ticker")\n'
        '            or st.session_state.get("dca_ch4_ticker")\n'
        '            or st.session_state.get("dca_ch3_ticker")\n'
        '            or st.session_state.get("dca_ch2_ticker")\n'
        '            or st.session_state.get("dca_ch1_ticker")\n'
        '            or st.session_state.get("active_ticker")\n'
        "            or default_ticker\n"
        "        )\n"
        "    ) or default_ticker\n"
        "    render_chapter7_tab(chapter7_ticker)\n\n"
        "apply_full_width()",
        "chapter7 render",
    )
    PAGE.write_text(text, encoding="utf-8")
    print("Chapter 7 Phase 7A unified-page integration applied")


if __name__ == "__main__":
    main()
