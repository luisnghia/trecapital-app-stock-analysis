from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5P patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    marker = '''def discover_management_candidates(
'''
    helper = '''def _targeted_search_child_score(parent_url: str, label: str, child_url: str, base_score: int) -> int:
    """Promote concrete same-site result pages reached from a targeted WordPress search.

    Search-result titles are frequently generic (e.g. AGM 2025) even when the query is specific
    (`chủ tịch HĐQT`). Without a parent-search bonus, relevant result pages sit behind hundreds of
    archive/navigation URLs and the crawler can exhaust its fetch budget first. The bonus only
    applies to concrete content paths, never to category/tag/navigation/static-asset links.
    """
    if "?s=" not in str(parent_url or "").casefold():
        return base_score
    path = urlparse(str(child_url or "")).path.casefold()
    if not path.strip("/"):
        return base_score
    excluded = (
        "/category/", "/tag/", "/author/", "/feed/", "/wp-json/",
        "/gioi-thieu", "/lien-he", "/tuyen-dung", "/san-pham", "/products/",
    )
    if any(token in path for token in excluded):
        return base_score
    if path.endswith((".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js")):
        return base_score
    return max(int(base_score), 145)


''' + marker
    text = replace_once(text, marker, helper, "targeted-search child helper")

    old_loop = '''                    child_score = _link_score(child_label, child_href)
                    if child_score <= 0:
                        continue
                    queue.append((child_score, depth + 1, child_label, child_href, root_domain))
'''
    new_loop = '''                    child_score = _targeted_search_child_score(
                        final_url,
                        child_label,
                        child_href,
                        _link_score(child_label, child_href),
                    )
                    if child_score <= 0:
                        continue
                    queue.append((child_score, depth + 1, child_label, child_href, root_domain))
'''
    text = replace_once(text, old_loop, new_loop, "search-child queue boost")
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_targeted_search_promotes_concrete_result_page_v37_1_round5p():"
    if sentinel in text:
        return
    text += r'''


def test_targeted_search_promotes_concrete_result_page_v37_1_round5p():
    from modules.deep_company_analysis.chapter7_management_discovery import _targeted_search_child_score
    score = _targeted_search_child_score(
        "https://example.com/?s=chu+tich+hdqt",
        "ĐẠI HỘI CỔ ĐÔNG THƯỜNG NIÊN NĂM 2025",
        "https://example.com/9329-2/",
        5,
    )
    assert score >= 145


def test_targeted_search_does_not_promote_navigation_v37_1_round5p():
    from modules.deep_company_analysis.chapter7_management_discovery import _targeted_search_child_score
    score = _targeted_search_child_score(
        "https://example.com/?s=chu+tich+hdqt",
        "Quan hệ cổ đông",
        "https://example.com/category/quan-he-co-dong/",
        3,
    )
    assert score == 3
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5P targeted-search result prioritization applied")


if __name__ == "__main__":
    main()
