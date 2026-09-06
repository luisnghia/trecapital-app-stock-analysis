from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5O function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    code = r'''def _link_score(label: str, url: str) -> int:
    # Normalize separators because Vietnamese IR sites frequently put the only semantic signal in
    # slugs such as `bao-cao-thuong-nien-2024` or `thay-doi-nhan-su` while the anchor says `Xem thêm`.
    raw = f"{label} {url}".casefold()
    normalized = re.sub(r"[-_/\\.?=&%+:]+", " ", raw)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    def norm_term(term: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[-_/\\.?=&%+:]+", " ", term.casefold())).strip()

    link_hits = [term for term in LINK_TERMS if norm_term(term) and norm_term(term) in normalized]
    management_hits = [term for term in MANAGEMENT_PRIORITY_TERMS if norm_term(term) and norm_term(term) in normalized]
    report_hits = [term for term in REPORT_PRIORITY_TERMS if norm_term(term) and norm_term(term) in normalized]

    score = 3 * len(link_hits) + 30 * len(management_hits) + 18 * len(report_hits)
    year = _year(raw)
    if year:
        score += max(0, min(int(year), 2026) - 2020) * 2

    path = urlparse(url).path.casefold()
    is_search = "?s=" in url.casefold()
    is_category = "/category/" in path
    is_direct_content = bool(path.strip("/")) and not is_category and not is_search

    # A direct article/report reached from an IR index should outrank broad archive/search pages.
    # Without this depth preference, hundreds of category/navigation URLs can consume the fetch
    # budget before the crawler opens the article that contains the actual manager roster.
    if is_direct_content and management_hits:
        score += 100
    if is_direct_content and report_hits:
        score += 85

    if url.lower().split("?")[0].endswith(".pdf"):
        score += 65
        if management_hits:
            score += 120
        if report_hits:
            score += 60

    # Mild preference for a concrete article path even when only a general IR term matched.
    if is_direct_content and len(path.strip("/").split("/")) >= 1:
        score += 5
    return score'''
    text = replace_function(text, "_link_score", "_index_like", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_direct_report_article_outranks_archive_navigation_v37_1_round5o():"
    if sentinel in text:
        return
    text += r'''


def test_direct_report_article_outranks_archive_navigation_v37_1_round5o():
    article = _link_score(
        "Báo cáo thường niên 2024",
        "https://example.com/bao-cao-thuong-nien-2024/",
    )
    archive = _link_score(
        "Báo cáo thường niên",
        "https://example.com/category/quan-he-co-dong/bao-cao-thuong-nien/",
    )
    assert article >= 100
    assert article > archive


def test_direct_management_article_gets_priority_v37_1_round5o():
    score = _link_score(
        "Xem thêm",
        "https://example.com/cbtt-thong-bao-thay-doi-nhan-su-chu-tich-hdqt/",
    )
    assert score >= 100
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5O direct-content crawl priority patch applied")


if __name__ == "__main__":
    main()
