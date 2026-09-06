from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5AC marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    old = '''    def add_if_role_document(label: str, final_url: str, text: str, method: str, role: str) -> bool:\n        if final_url in existing or len(_clean_text(text)) < 80:\n            return False\n        if not requested_role_signal(text, role):\n            return False\n        out.append({\n            "title": (_clean_text(label) or f"Official {role} coverage fallback")[:240],\n            "url": final_url,\n            "text": text,\n            "method": f"{method}; role-coverage fallback",\n        })\n        existing.add(final_url)\n        return True\n'''
    new = '''    def add_if_role_document(label: str, final_url: str, text: str, method: str, role: str) -> bool:\n        if final_url in existing or len(_clean_text(text)) < 80:\n            return False\n        candidate_doc = {\n            "title": (_clean_text(label) or f"Official {role} coverage fallback")[:240],\n            "url": final_url,\n            "text": text,\n            "method": f"{method}; role-coverage fallback",\n        }\n        # A broad role term + an unrelated person elsewhere in the page is not enough. The same\n        # production parser that ultimately builds the management candidate table must be able to\n        # extract the requested role from this individual document before it can consume the small\n        # role-document budget. This prevents generic 'bầu Chủ tịch' pages from starving a later\n        # governance/BCTC PDF whose signature or board table actually names the Chairman.\n        parsed = extract_management_candidates_from_documents([candidate_doc], max_targets=12)\n        if parsed.empty or not parsed["Role Normalized"].astype(str).eq(role).any():\n            return False\n        out.append(candidate_doc)\n        existing.add(final_url)\n        return True\n'''
    text = replace_once(text, old, new, "strict parsed-role retention")
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_fallback_budget_is_not_consumed_by_unparsed_role_mentions_v37_1_round5ac"
    if sentinel in text:
        return
    text += r'''


def test_fallback_budget_is_not_consumed_by_unparsed_role_mentions_v37_1_round5ac(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    archive = "https://example.com/category/quan-he-co-dong/bao-cao-quan-tri/"
    false1 = "https://example.com/election-notice-1/"
    false2 = "https://example.com/election-notice-2/"
    valid_pdf = "https://example.com/uploads/governance-2025.pdf"

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return ("search", "HTML text extraction", url, [])
        if url == archive:
            return (
                "Báo cáo quản trị",
                "HTML text extraction",
                url,
                [
                    ("Thông báo bầu Chủ tịch HĐQT 2026", false1),
                    ("Kế hoạch bầu Chủ tịch HĐQT 2026", false2),
                    ("Báo cáo quản trị 2025 PDF", valid_pdf),
                ],
            )
        if url in {false1, false2}:
            return (
                "Đại hội sẽ bầu Chủ tịch HĐQT. Ông Trần Văn Bình là cổ đông tham dự cuộc họp. " * 3,
                "HTML text extraction",
                url,
                [],
            )
        if url == valid_pdf:
            return (
                "T/M. HỘI ĐỒNG QUẢN TRỊ\nCHỦ TỊCH\nNguyễn Văn An\nBáo cáo tình hình quản trị năm 2025.",
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
        max_fetches_per_role=1,
        max_archive_fetches_per_role=10,
        max_documents_per_role=1,
    )
    assert len(docs) == 1
    assert docs[0]["url"] == valid_pdf
    frame = md.extract_management_candidates_from_documents(docs, max_targets=12)
    assert ((frame["Manager"] == "Nguyễn Văn An") & (frame["Role Normalized"] == "Chairman")).any()
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5AC strict parsed-role fallback retention applied")


if __name__ == "__main__":
    main()
