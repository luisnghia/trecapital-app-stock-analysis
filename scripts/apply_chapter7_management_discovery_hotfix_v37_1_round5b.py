from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5b patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    old = '''def _role_from_context(context: str) -> tuple[str, str, int]:
    low = f" {_clean_text(context).casefold()} "
    best = ("", "", 0)
    for normalized, terms, priority in ROLE_RULES:
        for term in terms:
            needle = term.casefold().strip()
            if needle and needle in low and priority > best[2]:
                best = (term.strip(), normalized, priority)
    return best
'''
    new = '''def _role_from_context(context: str) -> tuple[str, str, int]:
    low = f" {_clean_text(context).casefold()} "
    # Match specificity must outrank seniority priority so compound titles do not collapse:
    # "Phó Tổng Giám đốc" -> Deputy CEO, not CEO; "Phó Chủ tịch HĐQT" -> Vice Chairman,
    # not Chairman; "Thành viên HĐQT độc lập" -> Independent Director, not Board Director.
    best = ("", "", 0)
    best_key = (0, 0)
    for normalized, terms, priority in ROLE_RULES:
        for term in terms:
            needle = term.casefold().strip()
            if not needle or needle not in low:
                continue
            key = (len(needle), priority)
            if key > best_key:
                best = (term.strip(), normalized, priority)
                best_key = key
    return best
'''
    text = replace_once(text, old, new, "specific role matching")
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_compound_titles_beat_embedded_generic_titles_v37_1_round5b():"
    if sentinel in text:
        return
    text += '''


def test_compound_titles_beat_embedded_generic_titles_v37_1_round5b():
    docs = [{
        "title": "Official management roster 2025",
        "url": "https://example.com/management-2025.pdf",
        "text": (
            "Phạm Văn Hùng    Phó Tổng Giám đốc\\n"
            "Đào Hữu Duy Anh    Phó Chủ tịch HĐQT\\n"
            "Nguyễn Thị Thu Hà    Thành viên HĐQT độc lập"
        ),
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
    assert ("Đào Hữu Duy Anh", "Vice Chairman") in found
    assert ("Nguyễn Thị Thu Hà", "Independent Director") in found
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5b compound-role specificity patch applied")


if __name__ == "__main__":
    main()
