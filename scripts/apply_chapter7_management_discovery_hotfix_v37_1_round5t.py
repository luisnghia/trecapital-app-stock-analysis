from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5T patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    old_sig = '''    max_fetches_per_role: int = 28,\n    max_documents_per_role: int = 8,\n) -> list[dict[str, Any]]:\n'''
    new_sig = '''    max_fetches_per_role: int = 28,\n    max_documents_per_role: int = 8,\n    max_archive_fetches_per_role: int = 28,\n) -> list[dict[str, Any]]:\n'''
    text = replace_once(text, old_sig, new_sig, "separate archive budget signature")

    old_init = '''        role_fetches = 0\n        role_docs = 0\n        seen: set[str] = set()\n\n        # Path 1 — role-specific WordPress/site search result pages.\n'''
    new_init = '''        search_fetches = 0\n        archive_fetches = 0\n        role_docs = 0\n        seen: set[str] = set()\n\n        # Path 1 — role-specific WordPress/site search result pages.\n        # IMPORTANT: this path has its own budget. Exhausting role-search results must never starve\n        # the archive→article→PDF fallback below.\n'''
    text = replace_once(text, old_init, new_init, "separate search/archive counters")

    # Restrict replacements to the search-path portion by replacing the exact repeated fragments in order.
    text = replace_once(
        text,
        '''                if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                    break\n''',
        '''                if search_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                    break\n''',
        "search outer budget check",
    )
    text = replace_once(
        text,
        '''                    if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                        break\n''',
        '''                    if search_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                        break\n''',
        "search child budget check",
    )
    text = replace_once(text, '''                    role_fetches += 1\n''', '''                    search_fetches += 1\n''', "search page increment")
    text = replace_once(
        text,
        '''                        if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                            break\n''',
        '''                        if search_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                            break\n''',
        "search pdf budget check",
    )
    text = replace_once(text, '''                        role_fetches += 1\n''', '''                        search_fetches += 1\n''', "search pdf increment")
    text = replace_once(
        text,
        '''            if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                break\n\n        # Path 2 — independent small budget for common IR report archives. This is intentionally\n''',
        '''            if search_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                break\n\n        # Path 2 — independent small budget for common IR report archives. This is intentionally\n''',
        "search path terminal budget check",
    )

    # Archive path gets an independent fetch budget. role_docs remains shared so we still cap retained
    # evidence volume and do not flood the analyst workspace.
    text = replace_once(
        text,
        '''                    if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                        break\n                    archive_url = urljoin(root, archive)\n''',
        '''                    if archive_fetches >= max_archive_fetches_per_role or role_docs >= max_documents_per_role:\n                        break\n                    archive_url = urljoin(root, archive)\n                    archive_fetches += 1\n''',
        "archive list budget check and increment",
    )
    text = replace_once(
        text,
        '''                        if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                            break\n''',
        '''                        if archive_fetches >= max_archive_fetches_per_role or role_docs >= max_documents_per_role:\n                            break\n''',
        "archive article budget check",
    )
    text = replace_once(text, '''                        role_fetches += 1\n''', '''                        archive_fetches += 1\n''', "archive article increment")
    text = replace_once(
        text,
        '''                            if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                                break\n''',
        '''                            if archive_fetches >= max_archive_fetches_per_role or role_docs >= max_documents_per_role:\n                                break\n''',
        "archive pdf budget check",
    )
    text = replace_once(text, '''                            role_fetches += 1\n''', '''                            archive_fetches += 1\n''', "archive pdf increment")
    text = replace_once(
        text,
        '''                if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:\n                    break\n''',
        '''                if archive_fetches >= max_archive_fetches_per_role or role_docs >= max_documents_per_role:\n                    break\n''',
        "archive terminal budget check",
    )

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_archive_fallback_budget_survives_exhausted_role_search_v37_1_round5t(monkeypatch):"
    if sentinel in text:
        return

    text += r'''


def test_archive_fallback_budget_survives_exhausted_role_search_v37_1_round5t(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    search_children = [(f"Generic result {i}", f"https://example.com/search-result-{i}/") for i in range(8)]

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return ("search", "HTML text extraction", url, search_children)
        if "search-result-" in url:
            # Search results consume the entire search-path budget but contain no Chairman evidence.
            return ("generic company disclosure text with sufficient length but no board chair role " * 3,
                    "HTML text extraction", url, [])
        if url.endswith("category/quan-he-co-dong/bao-cao-quan-tri/"):
            return (
                "Báo cáo quản trị",
                "HTML text extraction",
                url,
                [("Báo cáo quản trị 2025", "https://example.com/governance-2025/")],
            )
        if url == "https://example.com/governance-2025/":
            return (
                "Tải báo cáo quản trị chính thức",
                "HTML text extraction",
                url,
                [("Governance PDF", "https://example.com/uploads/governance-2025.pdf")],
            )
        if url == "https://example.com/uploads/governance-2025.pdf":
            return (
                "Hội đồng quản trị\nÔng Nguyễn Văn An\nChủ tịch HĐQT\nThông tin quản trị công ty năm 2025.",
                "PDF text extraction (no OCR)",
                url,
                [],
            )
        if "/category/quan-he-co-dong/" in url:
            return ("archive", "HTML text extraction", url, [])
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/quan-he-co-dong/"],
        [],
        ["Chairman"],
        max_fetches_per_role=2,              # deliberately exhausted by search path
        max_archive_fetches_per_role=8,      # independent archive budget must still run
        max_documents_per_role=2,
    )
    assert any(doc["url"].endswith("governance-2025.pdf") for doc in docs)
    assert any("Chủ tịch HĐQT" in doc["text"] for doc in docs)
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5T independent archive fallback budget applied")


if __name__ == "__main__":
    main()
