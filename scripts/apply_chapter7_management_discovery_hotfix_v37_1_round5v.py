from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5V patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    old_sig = '''    max_documents_per_role: int = 8,\n    max_archive_fetches_per_role: int = 28,\n) -> list[dict[str, Any]]:\n'''
    new_sig = '''    max_documents_per_role: int = 8,\n    max_archive_fetches_per_role: int = 28,\n    max_existing_parent_fetches_per_role: int = 18,\n) -> list[dict[str, Any]]:\n'''
    text = replace_once(text, old_sig, new_sig, "existing-parent budget signature")

    marker = '''        # Path 1 — role-specific WordPress/site search result pages.\n        # IMPORTANT: this path has its own budget. Exhausting role-search results must never starve\n        # the archive→article→PDF fallback below.\n'''
    insertion = '''        # Path 0 — revisit already-retained official HTML management pages and inspect attachments.\n        # This is the highest-value fallback because the broad crawler may retain a disclosure article\n        # from its visible text but not retain a linked signed PDF whose signature/table contains the\n        # missing Chairman/CEO evidence. Re-fetching the parent does not duplicate it in `out`; it is\n        # used only as an attachment index.\n        existing_parent_fetches = 0\n        parent_candidates: list[tuple[int, str, str, str]] = []\n        for doc in existing_documents:\n            if not isinstance(doc, dict):\n                continue\n            parent_url = _clean_text(doc.get("url"))\n            if not parent_url or parent_url.lower().split("?")[0].endswith(".pdf"):\n                continue\n            parent_domain = _domain(parent_url)\n            if not any(_same_domain(parent_url, root_domain) for _root, root_domain in roots):\n                continue\n            parent_title = _clean_text(doc.get("title"))\n            parent_text = _clean_text(doc.get("text"))\n            score = _link_score(parent_title, parent_url)\n            # Personnel/governance pages already retained by the main crawler are especially likely\n            # to expose signed resolutions or governance PDFs as attachments.\n            low = f"{parent_title} {parent_url} {parent_text[:800]}".casefold()\n            if any(term.casefold() in low for term in MANAGEMENT_PRIORITY_TERMS):\n                score += 220\n            if any(term.casefold() in low for term in REPORT_PRIORITY_TERMS):\n                score += 140\n            year = _year(low)\n            if year:\n                score += max(0, int(year) - 2020) * 20\n            parent_candidates.append((score, parent_title, parent_url, parent_domain))\n        parent_candidates.sort(key=lambda x: x[0], reverse=True)\n\n        for _score, parent_title, parent_url, parent_domain in parent_candidates[:18]:\n            if existing_parent_fetches >= max_existing_parent_fetches_per_role or role_docs >= max_documents_per_role:\n                break\n            if parent_url in seen:\n                continue\n            seen.add(parent_url)\n            existing_parent_fetches += 1\n            try:\n                _parent_text, _parent_method, _parent_final, parent_links = _fetch_text(client, parent_url)\n            except Exception:\n                continue\n            attached = [\n                (a_label, a_href) for a_label, a_href in parent_links\n                if _same_domain(a_href, parent_domain) and a_href.lower().split("?")[0].endswith(".pdf")\n            ]\n            attached.sort(key=lambda item: _link_score(item[0], item[1]), reverse=True)\n            for pdf_label, pdf_href in attached[:6]:\n                if existing_parent_fetches >= max_existing_parent_fetches_per_role or role_docs >= max_documents_per_role:\n                    break\n                if pdf_href in existing or pdf_href in seen:\n                    continue\n                seen.add(pdf_href)\n                existing_parent_fetches += 1\n                try:\n                    pdf_text, pdf_method, pdf_final, _ = _fetch_text(client, pdf_href)\n                except Exception:\n                    continue\n                if add_if_role_document(pdf_label or parent_title, pdf_final, pdf_text, pdf_method, role):\n                    role_docs += 1\n\n''' + marker
    text = replace_once(text, marker, insertion, "path0 retained-parent attachment traversal")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_retained_management_parent_is_traversed_even_when_search_and_archive_miss_v37_1_round5v(monkeypatch):"
    if sentinel in text:
        return

    text += r'''


def test_retained_management_parent_is_traversed_even_when_search_and_archive_miss_v37_1_round5v(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    parent = "https://example.com/cbtt-personnel-change/"
    pdf = "https://example.com/uploads/board-resolution.pdf"

    def fake_fetch_text(client, url, *args, **kwargs):
        if url == parent:
            return (
                "Visible page appoints a CEO and Vice Chairman but not the Chairman name.",
                "HTML text extraction",
                url,
                [("Signed board resolution", pdf)],
            )
        if url == pdf:
            return (
                "T/M. HỘI ĐỒNG QUẢN TRỊ\nCHỦ TỊCH\nNguyễn Văn An\nNghị quyết có hiệu lực kể từ ngày ký.",
                "PDF text extraction (no OCR)",
                url,
                [],
            )
        if "?s=" in url or "/category/quan-he-co-dong/" in url:
            return ("no useful links", "HTML text extraction", url, [])
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/quan-he-co-dong/"],
        [{
            "url": parent,
            "title": "CBTT Nghị quyết HĐQT thay đổi nhân sự 2025",
            "text": "Bổ nhiệm Tổng giám đốc và Phó Chủ tịch HĐQT",
            "method": "HTML text extraction",
        }],
        ["Chairman"],
        max_fetches_per_role=2,
        max_archive_fetches_per_role=2,
        max_existing_parent_fetches_per_role=4,
        max_documents_per_role=2,
    )
    assert any(doc["url"] == pdf for doc in docs)
    frame = md.extract_management_candidates_from_documents(docs, company_name="Example Company")
    assert ((frame["Manager"] == "Nguyễn Văn An") & (frame["Role Normalized"] == "Chairman")).any()


def test_retained_parent_path_keeps_existing_pdf_dedup_v37_1_round5v(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    parent = "https://example.com/cbtt/"
    pdf = "https://example.com/uploads/already-retained.pdf"
    fetched = []

    def fake_fetch_text(client, url, *args, **kwargs):
        fetched.append(url)
        if url == parent:
            return ("disclosure", "HTML text extraction", url, [("PDF", pdf)])
        if url == pdf:
            raise AssertionError("Existing retained PDF must not be fetched again")
        if "?s=" in url or "/category/quan-he-co-dong/" in url:
            return ("no links", "HTML text extraction", url, [])
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/quan-he-co-dong/"],
        [
            {"url": parent, "title": "Personnel disclosure", "text": "Bổ nhiệm nhân sự", "method": "HTML text extraction"},
            {"url": pdf, "title": "Signed PDF", "text": "Chủ tịch HĐQT Nguyễn Văn An", "method": "PDF text extraction (no OCR)"},
        ],
        ["Chairman"],
        max_fetches_per_role=1,
        max_archive_fetches_per_role=1,
        max_existing_parent_fetches_per_role=3,
        max_documents_per_role=2,
    )
    assert pdf not in fetched
    assert docs == []
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5V retained-parent attachment traversal applied")


if __name__ == "__main__":
    main()
