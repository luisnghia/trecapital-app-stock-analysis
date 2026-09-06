from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5U patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    old1 = '''                for label, href in links:\n                    if href in existing or href in seen or not _same_domain(href, domain):\n                        continue\n'''
    new1 = '''                for label, href in links:\n                    # Existing HTML/article parents are still useful as attachment indexes. Re-fetch them\n                    # to discover linked official PDFs; add_if_role_document() prevents duplicate retention.\n                    # Existing PDFs stay skipped because they were already parsed as evidence documents.\n                    if href in seen or not _same_domain(href, domain):\n                        continue\n                    if href in existing and href.lower().split("?")[0].endswith(".pdf"):\n                        continue\n'''
    text = replace_once(text, old1, new1, "search path existing-parent traversal")

    old2 = '''                    for label, href in archive_links:\n                        if href in existing or href in seen or not _same_domain(href, domain):\n                            continue\n'''
    new2 = '''                    for label, href in archive_links:\n                        # Do not discard already-retained article pages: they can contain attachment links\n                        # that were not followed during the broad crawl. Existing PDFs remain skipped.\n                        if href in seen or not _same_domain(href, domain):\n                            continue\n                        if href in existing and href.lower().split("?")[0].endswith(".pdf"):\n                            continue\n'''
    text = replace_once(text, old2, new2, "archive path existing-parent traversal")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_existing_parent_article_is_refetched_for_new_pdf_attachment_v37_1_round5u(monkeypatch):"
    if sentinel in text:
        return

    text += r'''


def test_existing_parent_article_is_refetched_for_new_pdf_attachment_v37_1_round5u(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    parent = "https://example.com/personnel-change/"
    pdf = "https://example.com/uploads/personnel-change.pdf"

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return (
                "search",
                "HTML text extraction",
                url,
                [("Personnel change disclosure", parent)],
            )
        if url == parent:
            return (
                "Company personnel change disclosure already retained earlier",
                "HTML text extraction",
                url,
                [("Official attached resolution", pdf)],
            )
        if url == pdf:
            return (
                "Hội đồng quản trị\nÔng Nguyễn Văn An\nChủ tịch HĐQT\nNghị quyết có hiệu lực kể từ ngày ký.",
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
        [{"url": parent, "title": "Existing retained disclosure", "text": "existing"}],
        ["Chairman"],
        max_fetches_per_role=6,
        max_archive_fetches_per_role=4,
        max_documents_per_role=2,
    )
    assert any(doc["url"] == pdf for doc in docs)
    assert any("Chủ tịch HĐQT" in doc["text"] for doc in docs)


def test_existing_pdf_is_not_refetched_v37_1_round5u(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    pdf = "https://example.com/uploads/already-parsed.pdf"

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return ("search", "HTML text extraction", url, [("Old PDF", pdf)])
        if url == pdf:
            raise AssertionError("Existing PDF must not be refetched")
        if "/category/quan-he-co-dong/" in url:
            return ("archive", "HTML text extraction", url, [])
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/quan-he-co-dong/"],
        [{"url": pdf, "title": "Already parsed", "text": "Chủ tịch HĐQT Ông Nguyễn Văn An"}],
        ["Chairman"],
        max_fetches_per_role=4,
        max_archive_fetches_per_role=2,
        max_documents_per_role=2,
    )
    assert docs == []
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5U existing-parent attachment traversal applied")


if __name__ == "__main__":
    main()
