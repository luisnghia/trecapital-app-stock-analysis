from __future__ import annotations

from pathlib import Path

PAGE = Path("pages/07_Phan_tich_chuyen_sau_doanh_nghiep.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Patch anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PAGE.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "from modules.deep_company_analysis.chapter4_page_support import render_chapter4_tab\n",
        "from modules.deep_company_analysis.chapter4_page_support import render_chapter4_tab\nfrom modules.deep_company_analysis.chapter5 import render_chapter5\n",
        "chapter5 import",
    )

    text = replace_once(
        text,
        '        or st.session_state.get("dca_ch4_ticker")\n        or st.session_state.get("active_ticker")',
        '        or st.session_state.get("dca_ch4_ticker")\n        or st.session_state.get("dca_ch5_ticker")\n        or st.session_state.get("active_ticker")',
        "default ticker",
    )

    text = replace_once(
        text,
        'chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab = st.tabs([\n    "📗 Chương 1 — Cơ hội đầu tư",\n    "📘 Chương 2 — Hiểu doanh nghiệp",\n    "📙 Chương 3 — Góc nhìn khách hàng",\n    "📕 Chương 4 — Lợi thế & ngành",\n])',
        'chapter1_tab, chapter2_tab, chapter3_tab, chapter4_tab, chapter5_tab = st.tabs([\n    "📗 Chương 1 — Cơ hội đầu tư",\n    "📘 Chương 2 — Hiểu doanh nghiệp",\n    "📙 Chương 3 — Góc nhìn khách hàng",\n    "📕 Chương 4 — Lợi thế & ngành",\n    "📒 Chương 5 — Hoạt động & tài chính",\n])',
        "chapter tabs",
    )

    chapter5_block = '''\nwith chapter5_tab:\n    chapter5_ticker = _safe_ticker(\n        str(\n            st.session_state.get("dca_ch5_ticker")\n            or st.session_state.get("dca_ch4_ticker")\n            or st.session_state.get("dca_ch3_ticker")\n            or st.session_state.get("dca_ch2_ticker")\n            or st.session_state.get("dca_ch1_ticker")\n            or st.session_state.get("active_ticker")\n            or default_ticker\n        )\n    ) or default_ticker\n    render_chapter5(default_ticker=chapter5_ticker)\n\n'''
    if "with chapter5_tab:" not in text:
        marker = "\napply_full_width()"
        if marker not in text:
            raise RuntimeError("Patch anchor not found: apply_full_width")
        text = text.replace(marker, chapter5_block + "apply_full_width()", 1)

    PAGE.write_text(text, encoding="utf-8")
    print("Chapter 5 Phase 5A UI patch applied")


if __name__ == "__main__":
    main()
