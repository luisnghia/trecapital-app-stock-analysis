from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"
CH4 = ROOT / "modules" / "deep_company_analysis" / "chapter4.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Patch anchor not found in {path}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        PAGE,
        "from modules.deep_company_analysis.chapter4 import render_chapter4\n",
        "from modules.deep_company_analysis.chapter4_page_support import render_chapter4_tab\n",
    )
    replace_once(
        PAGE,
        "    render_chapter4(default_ticker=chapter4_ticker)\n",
        "    render_chapter4_tab(chapter4_ticker)\n",
    )
    replace_once(
        CH4,
        "**Phase 4A:** đây là Source-Locked Core. Chưa có Research Assistant tự kết luận. Phase 4B/4C sau này mới nối canonical data và evidence nhưng không được ghi đè analyst work.",
        "**Phase 4B:** Source-Locked Core vẫn là nơi Analyst kết luận; phía trên workspace có Quantitative Bridge đọc canonical Trecapital data cho margins/ROIC/CCC/peer context. Phase 4C mới bổ sung research-evidence candidates. Không lớp nào được ghi đè analyst work.",
    )
    print("Applied Chapter 4 Phase 4B quantitative bridge integration patch.")


if __name__ == "__main__":
    main()
