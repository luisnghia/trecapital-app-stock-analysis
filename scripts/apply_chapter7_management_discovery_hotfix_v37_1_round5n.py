from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5N function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    code = r'''def _link_score(label: str, url: str) -> int:
    # IR sites often expose generic anchor text such as `Xem thêm`; the semantic signal then lives
    # only in a hyphenated/underscored slug (e.g. `thong-bao-thay-doi-nhan-su`). Normalize URL
    # separators before term matching so relevant article/PDF links can enter the crawl queue.
    raw = f"{label} {url}".casefold()
    text = re.sub(r"[-_/\\.?=&%+:]+", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    score = sum(3 for term in LINK_TERMS if re.sub(r"[-_/\\.?=&%+:]+", " ", term.casefold()).strip() in text)
    score += sum(30 for term in MANAGEMENT_PRIORITY_TERMS if re.sub(r"[-_/\\.?=&%+:]+", " ", term.casefold()).strip() in text)
    score += sum(18 for term in REPORT_PRIORITY_TERMS if re.sub(r"[-_/\\.?=&%+:]+", " ", term.casefold()).strip() in text)
    year = _year(raw)
    if year:
        score += max(0, int(year) - 2020) * 2
    if url.lower().split("?")[0].endswith(".pdf"):
        score += 65
        # Personnel resolutions, governance reports and signed appointment PDFs should outrank
        # generic IR category pages because they carry the actual named management evidence.
        if any(re.sub(r"[-_/\\.?=&%+:]+", " ", token.casefold()).strip() in text for token in (
            "hdqt", "tgd", "nhan-su", "nhân sự", "bo-nhiem", "bổ nhiệm",
            "mien-nhiem", "miễn nhiệm", "chu-tich", "chủ tịch", "tong-giam-doc",
            "báo cáo quản trị", "bao-cao-quan-tri",
        )):
            score += 120
    if "/category/" not in url.lower() and len(urlparse(url).path.strip("/").split("/")) >= 2:
        score += 5
    return score'''
    text = replace_function(text, "_link_score", "_index_like", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_hyphenated_ir_slug_enters_management_crawl_queue_v37_1_round5n():"
    if sentinel in text:
        return

    # Add the private-helper import after the future import. Python requires __future__ imports to
    # remain the first executable statement in the module.
    marker = "from modules.deep_company_analysis.chapter7_management_discovery import ("
    if marker not in text:
        raise RuntimeError("V37.1 Round 5N test import marker not found")
    import_line = "from modules.deep_company_analysis.chapter7_management_discovery import _link_score\n"
    if import_line not in text:
        future_line = "from __future__ import annotations\n"
        if future_line in text:
            text = text.replace(future_line, future_line + "\n" + import_line, 1)
        else:
            text = import_line + text

    text += r'''


def test_hyphenated_ir_slug_enters_management_crawl_queue_v37_1_round5n():
    score = _link_score(
        "Xem thêm",
        "https://example.com/cbtt-thong-bao-thay-doi-nhan-su-tong-giam-doc/",
    )
    assert score >= 30


def test_hyphenated_annual_report_pdf_gets_high_priority_v37_1_round5n():
    score = _link_score(
        "Tải xuống",
        "https://example.com/wp-content/uploads/2026/03/bao-cao-thuong-nien-2025.pdf",
    )
    assert score >= 65
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5N URL-token link discovery patch applied")


if __name__ == "__main__":
    main()
