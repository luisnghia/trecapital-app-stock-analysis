from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FMT = ROOT / "modules" / "deep_company_analysis" / "table_format.py"
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"


def main() -> None:
    fmt = FMT.read_text(encoding="utf-8")
    fmt = fmt.replace(
        "add/delete + widget-generation + ``st.rerun()`` race.",
        "add/delete + widget-generation + forced-rerun race.",
    )
    FMT.write_text(fmt, encoding="utf-8")

    page = PAGE.read_text(encoding="utf-8")
    page = page.replace(
        "Khung phân tích doanh nghiệp theo The Investment Checklist — mỗi chương là một tab trong cùng workspace, dùng chung dữ liệu Trecapital.",
        "Khung phân tích doanh nghiệp theo The Investment Checklist — chọn một chương để làm việc trong cùng workspace, dùng chung dữ liệu Trecapital.",
    )
    PAGE.write_text(page, encoding="utf-8")
    print("V50 follow-up cleanup applied.")


if __name__ == "__main__":
    main()
