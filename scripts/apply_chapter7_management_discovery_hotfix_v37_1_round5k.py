from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    sentinel = "def _row_is_ended_role_candidate("
    if sentinel not in text:
        marker = "def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5, company_name: str = \"\") -> pd.DataFrame:\n"
        if marker not in text:
            raise RuntimeError("V37.1 Round 5K extract marker not found")
        helper = r'''def _role_aliases(normalized_role: str) -> tuple[str, ...]:
    for normalized, terms, _priority in ROLE_RULES:
        if normalized == normalized_role:
            return tuple(term.casefold().strip() for term in terms if term.strip())
    return ()


def _row_is_ended_role_candidate(manager: str, normalized_role: str, evidence: str) -> bool:
    """Return True only when this row's specific role is explicitly ended for this manager.

    The check is role-specific and source-row-local. It does not remove a historical CEO row from a
    different annual report merely because another document later dismisses that CEO. It is designed
    for mixed personnel disclosures that contain both `miễn nhiệm <old role> ... ông NAME` and a new
    appointment for the same person in the same source.
    """
    name = _clean_text(manager)
    role = _clean_text(normalized_role)
    text = _clean_text(evidence).casefold()
    if not name or not role or role == "Unknown" or not text:
        return False

    name_pat = re.escape(name.casefold()).replace(r"\ ", r"\s+")
    aliases = sorted(_role_aliases(role), key=len, reverse=True)
    if not aliases:
        return False

    end_terms = tuple(dict.fromkeys(cue.casefold() for cue in ROLE_END_CUES))
    # Vietnamese/English disclosure pattern: END-CUE ... ROLE ... [đối với] [ông/bà] NAME.
    for end_cue in end_terms:
        for alias in aliases:
            alias_pat = re.escape(alias).replace(r"\ ", r"\s+")
            pattern_before = (
                rf"{re.escape(end_cue)}.{{0,120}}{alias_pat}.{{0,120}}"
                rf"(?:(?:đối\s+với|doi\s+voi)\s+)?(?:(?:ông|bà|mr\.?|ms\.?)\s+)?{name_pat}"
            )
            if re.search(pattern_before, text, flags=re.I):
                return True

            # Less common pattern: END-CUE ... NAME ... ROLE, still within one compact clause.
            pattern_after = (
                rf"{re.escape(end_cue)}.{{0,120}}(?:(?:ông|bà|mr\.?|ms\.?)\s+)?{name_pat}"
                rf".{{0,120}}{alias_pat}"
            )
            if re.search(pattern_after, text, flags=re.I):
                return True
    return False


'''
        text = text.replace(marker, helper + marker, 1)

    old = '''    frame = pd.DataFrame(rows)\n    plausible = frame.apply(\n'''
    new = '''    frame = pd.DataFrame(rows)\n    # Final role-specific event cleanup: fallback parsers may legitimately rediscover a name/role\n    # pair from the same mixed personnel disclosure. Suppress only rows where that exact role is\n    # explicitly ended for that manager in the row evidence; preserve historical rows from other sources.\n    ended_mask = frame.apply(\n        lambda row: _row_is_ended_role_candidate(\n            row.get("Manager", ""),\n            row.get("Role Normalized", ""),\n            row.get("Evidence Text / Reference", ""),\n        ),\n        axis=1,\n    )\n    frame = frame[~ended_mask].copy()\n    if frame.empty:\n        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)\n\n    plausible = frame.apply(\n'''
    if new not in text:
        if old not in text:
            raise RuntimeError("V37.1 Round 5K final-frame filter marker not found")
        text = text.replace(old, new, 1)

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_ended_role_suppression_is_source_local_and_preserves_history_v37_1_round5k():"
    if sentinel in text:
        return
    text += r'''


def test_ended_role_suppression_is_source_local_and_preserves_history_v37_1_round5k():
    docs = [
        {
            "title": "Annual Report 2024",
            "url": "https://example.com/ar-2024.pdf",
            "text": "Ông Đào Hữu Duy Anh Tổng Giám đốc.",
            "method": "PDF text extraction (no OCR)",
        },
        {
            "title": "Personnel change 2025",
            "url": "https://example.com/personnel-2025.html",
            "text": (
                "Ngày 03/03/2025 thông qua miễn nhiệm chức danh Tổng giám đốc đối với ông Đào Hữu Duy Anh. "
                "Ngày 03/03/2025 thông qua bổ nhiệm ông Đào Hữu Duy Anh giữ chức vụ Phó chủ tịch HĐQT. "
                "Ngày 03/03/2025 thông qua bổ nhiệm ông Lưu Bách Đạt giữ chức vụ Tổng giám đốc."
            ),
            "method": "HTML text extraction",
        },
    ]
    frame = extract_management_candidates_from_documents(docs, company_name="Tập đoàn Hóa chất Đức Giang")
    found = {(r["Manager"], r["Role Normalized"], str(r["As-of Date"]), r["Source URL / File"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Duy Anh", "CEO", "2024", "https://example.com/ar-2024.pdf") in found
    assert ("Đào Hữu Duy Anh", "Vice Chairman", "2025", "https://example.com/personnel-2025.html") in found
    assert ("Đào Hữu Duy Anh", "CEO", "2025", "https://example.com/personnel-2025.html") not in found
    assert ("Lưu Bách Đạt", "CEO", "2025", "https://example.com/personnel-2025.html") in found
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5K ended-role suppression patch applied")


if __name__ == "__main__":
    main()
