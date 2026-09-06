from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5H function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    code = '''def _relation_cue_after_name(name: str, evidence: str) -> bool:
    """Reject a related-person row only when the relationship label immediately follows the name.

    Do not scan an arbitrary trailing window: the next manager may legitimately contain words such
    as `Anh` in their own name, which must not be mistaken for a relationship cue.
    """
    low = _clean_text(evidence).casefold()
    needle = _clean_text(name).casefold()
    pos = low.find(needle)
    if pos < 0:
        return False
    tail = low[pos + len(needle):].lstrip(" -–—,:;()[]")
    tail = re.sub(r"^(?:là|la)\\s+", "", tail)
    for cue in RELATED_PERSON_CUES:
        if re.match(rf"^{re.escape(cue.casefold())}(?:\\s|[-–—,:;()])", tail):
            return True
    return False'''
    text = replace_function(text, "_relation_cue_after_name", "_plausible_manager_candidate", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_relation_filter_is_immediate_and_does_not_reject_next_manager_named_anh_v37_1_round5h():"
    if sentinel in text:
        return
    text += '''


def test_relation_filter_is_immediate_and_does_not_reject_next_manager_named_anh_v37_1_round5h():
    from modules.deep_company_analysis.chapter7_management_discovery import _plausible_manager_candidate

    evidence = "Ông Lưu Bách Đạt Tổng Giám đốc. Ông Đào Hữu Duy Anh Phó Chủ tịch HĐQT."
    assert _plausible_manager_candidate("Lưu Bách Đạt", evidence, "Tập đoàn Hóa chất Đức Giang")
    assert _plausible_manager_candidate("Đào Hữu Duy Anh", evidence, "Tập đoàn Hóa chất Đức Giang")
    assert not _plausible_manager_candidate(
        "Trần Thị Xuân", "Bà Trần Thị Xuân - mẹ TV HĐQT độc lập", "Tập đoàn Hóa chất Đức Giang"
    )
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5H immediate relation-cue fix applied")


if __name__ == "__main__":
    main()
