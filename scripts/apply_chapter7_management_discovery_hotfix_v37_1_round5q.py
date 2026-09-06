from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5Q function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    old_import = "from urllib.parse import urljoin, urlparse, quote_plus, urldefrag"
    new_import = "from urllib.parse import urljoin, urlparse, quote_plus, urldefrag, unquote_plus"
    if new_import not in text:
        if old_import not in text:
            raise RuntimeError("V37.1 Round 5Q urllib import marker not found")
        text = text.replace(old_import, new_import, 1)

    code = r'''def _targeted_search_child_score(parent_url: str, label: str, child_url: str, base_score: int) -> int:
    """Prioritize concrete official pages according to the role/report intent of the parent search.

    WordPress result titles can be generic (for example an AGM page) even when the parent query is
    highly specific (for example `chủ tịch HĐQT`). A uniform result bonus can therefore still leave
    Chairman/CEO evidence behind large archive queues. This helper carries only the *search intent*
    into crawl scheduling. It does not infer any person's role and never confirms a manager identity.
    """
    parent = str(parent_url or "")
    if "?s=" not in parent.casefold():
        return int(base_score)

    child = str(child_url or "")
    path = urlparse(child).path.casefold()
    if not path.strip("/"):
        return int(base_score)
    excluded = (
        "/category/", "/tag/", "/author/", "/feed/", "/wp-json/",
        "/gioi-thieu", "/lien-he", "/tuyen-dung", "/san-pham", "/products/",
    )
    if any(token in path for token in excluded):
        return int(base_score)
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js")):
        return int(base_score)

    # Decode the WordPress query because quote_plus percent-encodes Vietnamese role terms.
    query = unquote_plus(urlparse(parent).query).casefold()
    score = max(int(base_score), 145)

    intent_groups = (
        (330, ("chủ tịch hđqt", "chủ tịch hội đồng quản trị", "chairman")),
        (320, ("tổng giám đốc", "chief executive officer", " ceo ")),
        (300, ("hội đồng quản trị", "board of directors", "board director")),
        (285, ("thông tin về doanh nghiệp", "company information", "ban tổng giám đốc", "management")),
        (275, ("báo cáo quản trị", "tình hình quản trị", "corporate governance")),
        (265, ("báo cáo thường niên", "annual report")),
        (255, ("báo cáo tài chính quý 4", "financial statement", "financial report")),
    )
    for priority, terms in intent_groups:
        if any(term.strip() and term.strip() in query for term in terms):
            score = max(score, priority)
            break
    return score'''
    text = replace_function(text, "_targeted_search_child_score", "discover_management_candidates", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_chairman_search_intent_outranks_generic_targeted_results_v37_1_round5q():"
    if sentinel in text:
        return
    text += r'''


def test_chairman_search_intent_outranks_generic_targeted_results_v37_1_round5q():
    from modules.deep_company_analysis.chapter7_management_discovery import _targeted_search_child_score
    score = _targeted_search_child_score(
        "https://example.com/?s=ch%E1%BB%A7+t%E1%BB%8Bch+H%C4%90QT",
        "ĐẠI HỘI CỔ ĐÔNG THƯỜNG NIÊN NĂM 2025",
        "https://example.com/9329-2/",
        5,
    )
    assert score >= 330


def test_company_information_search_gets_secondary_role_discovery_priority_v37_1_round5q():
    from modules.deep_company_analysis.chapter7_management_discovery import _targeted_search_child_score
    score = _targeted_search_child_score(
        "https://example.com/?s=th%C3%B4ng+tin+v%E1%BB%81+doanh+nghi%E1%BB%87p",
        "Báo cáo tài chính quý I",
        "https://example.com/bao-cao-tai-chinh-quy-i-2025/",
        18,
    )
    assert score >= 285


def test_role_intent_priority_still_excludes_archive_navigation_v37_1_round5q():
    from modules.deep_company_analysis.chapter7_management_discovery import _targeted_search_child_score
    score = _targeted_search_child_score(
        "https://example.com/?s=ch%E1%BB%A7+t%E1%BB%8Bch+H%C4%90QT",
        "Quan hệ cổ đông",
        "https://example.com/category/quan-he-co-dong/",
        7,
    )
    assert score == 7
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5Q role-intent crawl priority applied")


if __name__ == "__main__":
    main()
