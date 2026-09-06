from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5X patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    marker = "def _role_then_name_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:\n"
    helper = r'''def _board_signature_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract Chairman evidence from a tightly local Board-of-Directors signature block.

    Vietnamese official resolutions often end with `T/M. HỘI ĐỒNG QUẢN TRỊ`, then `CHỦ TỊCH`,
    then the signatory name. `CHỦ TỊCH` is not made a global role alias: it is accepted only when
    board context is within the preceding two lines and a person name is on the same or next two
    lines. `PHÓ CHỦ TỊCH` is explicitly excluded. The output remains a research candidate.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []

    def is_board_context(value: str) -> bool:
        low = _clean_text(value).casefold()
        return any(token in low for token in ("hội đồng quản trị", "hoi dong quan tri", "hđqt", "hdqt"))

    def chairman_title_span(value: str) -> tuple[bool, str]:
        clean = _clean_text(value)
        low = clean.casefold()
        if "phó chủ tịch" in low or "pho chu tich" in low or "vice chairman" in low:
            return False, ""
        match = re.search(
            r"(?i)(?:^|[^A-Za-zÀ-ỹĐđ])(?:chủ\s+tịch|chu\s+tich|chairman)"
            r"(?:\s+(?:hđqt|hdqt|hội\s+đồng\s+quản\s+trị|hoi\s+dong\s+quan\s+tri))?"
            r"(?:$|[^A-Za-zÀ-ỹĐđ])",
            clean,
        )
        suffix = clean[match.end():].strip(" -–—,:;()[]") if match else ""
        return bool(match), suffix

    for idx, line in enumerate(lines):
        is_title, suffix = chairman_title_span(line)
        if not is_title:
            continue
        if not any(is_board_context(lines[j]) for j in range(max(0, idx - 2), idx + 1)):
            continue

        candidate_lines: list[str] = []
        if suffix:
            candidate_lines.append(suffix)
        for j in range(idx + 1, min(len(lines), idx + 3)):
            next_line = _clean_text(lines[j])
            next_role, _, _ = _role_span_in_line(next_line)
            if next_role[1] and next_role[1] != "Chairman":
                break
            candidate_lines.append(next_line)

        for candidate_text in candidate_lines:
            manager = ""
            honorific = PERSON_NAME_PATTERN.search(candidate_text)
            if honorific:
                manager = _candidate_name(honorific.group(1))
            if not manager:
                for bare in BARE_NAME_PATTERN.finditer(candidate_text):
                    manager = _candidate_name(bare.group(1))
                    if manager:
                        break
            if not manager:
                continue
            start = max(0, idx - 2)
            end = min(len(lines), idx + 3)
            context = _clean_text(" ".join(lines[start:end]))[:900]
            out.append((manager, ("chủ tịch", "Chairman", 100), context))
            break

    deduped: list[tuple[str, tuple[str, str, int], str]] = []
    seen: set[tuple[str, str]] = set()
    for manager, role, context in out:
        key = (manager.casefold(), role[1])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((manager, role, context))
    return deduped


''' + marker
    text = replace_once(text, marker, helper, "board signature helper")

    old_signal = '''    role_then_name_hit = bool(_role_then_name_candidates(text))\n    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))\n    return (role_hit and (person_hit or bare_role_hit or role_then_name_hit)) or compensation_hit\n'''
    new_signal = '''    role_then_name_hit = bool(_role_then_name_candidates(text))\n    board_signature_hit = bool(_board_signature_candidates(text))\n    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))\n    return (role_hit and (person_hit or bare_role_hit or role_then_name_hit)) or board_signature_hit or compensation_hit\n'''
    text = replace_once(text, old_signal, new_signal, "global management signal")

    old_requested = '''        role_hit = any(term.strip().casefold() in low for term in terms if term.strip())\n        person_hit = bool(PERSON_NAME_PATTERN.search(clean)) or bool(_bare_line_role_candidates(text)) or bool(_role_then_name_candidates(text))\n        return role_hit and person_hit\n'''
    new_requested = '''        role_hit = any(term.strip().casefold() in low for term in terms if term.strip())\n        board_signature_hit = bool(_board_signature_candidates(text))\n        if role == "Chairman" and board_signature_hit:\n            role_hit = True\n        person_hit = (\n            bool(PERSON_NAME_PATTERN.search(clean))\n            or bool(_bare_line_role_candidates(text))\n            or bool(_role_then_name_candidates(text))\n            or board_signature_hit\n        )\n        return role_hit and person_hit\n'''
    text = replace_once(text, old_requested, new_requested, "requested role signal")

    rows_marker = '''    if not rows:\n        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)\n'''
    signature_rows = '''        for manager, (role_raw, role_norm, priority), context in _board_signature_candidates(raw_text):\n            rows.append({\n                "Select": False,\n                "Manager": manager,\n                "Role Raw": role_raw,\n                "Role Normalized": role_norm,\n                "As-of Date": as_of,\n                "Source Title": source_title[:240],\n                "Source URL / File": source_url,\n                "Source Grade": "A — Company/Official disclosure",\n                "Evidence Text / Reference": context[:900],\n                "Status": "Discovered candidate — analyst verify",\n                "_priority": priority,\n            })\n    if not rows:\n        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)\n'''
    text = replace_once(text, rows_marker, signature_rows, "extract signature rows before empty check")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_board_signature_block_extracts_chairman_v37_1_round5x():"
    if sentinel in text:
        return
    text += r'''


def test_board_signature_block_extracts_chairman_v37_1_round5x():
    import modules.deep_company_analysis.chapter7_management_discovery as md

    raw = (
        "Nghị quyết Hội đồng quản trị số 04/2025/NQ-HĐQT\n"
        "T/M. HỘI ĐỒNG QUẢN TRỊ\n"
        "CHỦ TỊCH\n"
        "Đào Hữu Huyền\n"
    )
    found = md._board_signature_candidates(raw)
    assert any(name == "Đào Hữu Huyền" and role[1] == "Chairman" for name, role, _ in found)

    frame = md.extract_management_candidates_from_documents([{
        "title": "Nghị quyết HĐQT 04/2025",
        "url": "https://example.com/uploads/nq-04-2025.pdf",
        "text": raw,
        "method": "PDF text extraction (no OCR)",
    }], company_name="Tập đoàn Hóa chất Đức Giang")
    assert ((frame["Manager"] == "Đào Hữu Huyền") & (frame["Role Normalized"] == "Chairman")).any()


def test_board_signature_does_not_promote_vice_chairman_to_chairman_v37_1_round5x():
    import modules.deep_company_analysis.chapter7_management_discovery as md
    raw = "T/M. HỘI ĐỒNG QUẢN TRỊ\nPHÓ CHỦ TỊCH\nNguyễn Văn An\n"
    assert md._board_signature_candidates(raw) == []
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5X board-signature Chairman parser applied")


if __name__ == "__main__":
    main()
