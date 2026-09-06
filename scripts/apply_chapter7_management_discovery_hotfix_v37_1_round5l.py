from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5L function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    # Prevent date/section words from extending a bare-person candidate, e.g. `Đào Hữu Duy Anh Ngày`.
    old_noise = '"ông", "bà", "mr", "ms", "ủy", "uỷ", "ban", "kiểm", "soát", "giữ", "chức", "vụ", "được", "đảm", "sinh",'
    new_noise = '"ông", "bà", "mr", "ms", "ủy", "uỷ", "ban", "kiểm", "soát", "giữ", "chức", "vụ", "được", "đảm", "sinh", "ngày",'
    if new_noise not in text:
        if old_noise not in text:
            raise RuntimeError("V37.1 Round 5L noise marker not found")
        text = text.replace(old_noise, new_noise, 1)

    ended_code = r'''def _row_is_ended_role_candidate(manager: str, normalized_role: str, evidence: str) -> bool:
    """Suppress only the exact role ended for this manager in the same local clause.

    A mixed disclosure may say `dismiss CEO A. appoint A Vice Chairman.` The Vice-Chairman row must
    survive even though the same evidence window also contains the earlier CEO dismissal. Therefore
    end-event matching is performed sentence/clause by sentence/clause, never across punctuation.
    """
    name = _clean_text(manager)
    role = _clean_text(normalized_role)
    text = _clean_text(evidence).casefold()
    if not name or not role or role == "Unknown" or not text:
        return False
    aliases = sorted(_role_aliases(role), key=len, reverse=True)
    if not aliases:
        return False
    name_low = name.casefold()
    # Split on strong disclosure boundaries while keeping each event compact. `Nghị quyết`/`Ngày`
    # are also common event starters when HTML extraction loses paragraph boundaries.
    clauses = re.split(
        r"[.;\n]+|(?=\bnghị\s+quyết\b)|(?=\bnghi\s+quyet\b)|(?=\bngày\s+\d{1,2}[/-])|(?=\bngay\s+\d{1,2}[/-])",
        text,
        flags=re.I,
    )
    for clause in clauses:
        local = _clean_text(clause).casefold()
        if not local or name_low not in local:
            continue
        if not any(cue.casefold() in local for cue in ROLE_END_CUES):
            continue
        if any(alias and alias in local for alias in aliases):
            return True
    return False'''
    text = replace_function(text, "_row_is_ended_role_candidate", "extract_management_candidates_from_documents", ended_code)

    # Bare-name and role-before-name fallbacks are only for genuinely bare table/signature layouts.
    # If the local context already contains Ông/Bà/Mr/Ms, the primary honorific parser owns it.
    old_bare = '''        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):\n            if _is_role_end_event(manager, context):\n                continue\n'''
    new_bare = '''        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):\n            if re.search(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\\.?|Ms\\.?)\\s+", context, flags=re.I):\n                continue\n            if _is_role_end_event(manager, context):\n                continue\n'''
    if new_bare not in text:
        if old_bare not in text:
            raise RuntimeError("V37.1 Round 5L bare fallback marker not found")
        text = text.replace(old_bare, new_bare, 1)

    old_role_before = '''        for manager, (role_raw, role_norm, priority), context in _role_then_name_candidates(raw_text):\n            if _is_role_end_event(manager, context):\n                continue\n'''
    new_role_before = '''        for manager, (role_raw, role_norm, priority), context in _role_then_name_candidates(raw_text):\n            if re.search(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\\.?|Ms\\.?)\\s+", context, flags=re.I):\n                continue\n            if _is_role_end_event(manager, context):\n                continue\n'''
    if new_role_before not in text:
        if old_role_before not in text:
            raise RuntimeError("V37.1 Round 5L role-before-name fallback marker not found")
        text = text.replace(old_role_before, new_role_before, 1)

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_honorific_personnel_prose_does_not_leak_into_bare_fallback_v37_1_round5l():"
    if sentinel in text:
        return
    text += r'''


def test_honorific_personnel_prose_does_not_leak_into_bare_fallback_v37_1_round5l():
    docs = [{
        "title": "Personnel change 2025",
        "url": "https://example.com/personnel-2025.html",
        "text": (
            "Ngày 03/03/2025 miễn nhiệm chức danh Tổng giám đốc đối với ông Đào Hữu Duy Anh. "
            "Ngày 03/03/2025 bổ nhiệm ông Đào Hữu Duy Anh giữ chức vụ Phó chủ tịch HĐQT. "
            "Ngày 03/03/2025 bổ nhiệm ông Lưu Bách Đạt giữ chức vụ Tổng giám đốc."
        ),
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs, company_name="Tập đoàn Hóa chất Đức Giang")
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert found == {("Đào Hữu Duy Anh", "Vice Chairman"), ("Lưu Bách Đạt", "CEO")}
    assert not any(str(name).casefold().endswith(" ngày") for name in frame["Manager"])
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5L clause-local event cleanup applied")


if __name__ == "__main__":
    main()
