from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5c patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '("Vice Chairman", ("phó chủ tịch", "vice chairman"), 94),',
        '("Vice Chairman", ("phó chủ tịch hđqt", "phó chủ tịch hội đồng quản trị", "phó chủ tịch", "vice chairman"), 94),',
        "vice chairman compound aliases",
    )

    old_primary = '''def _line_role_candidates(raw_text: str) -> dict[str, tuple[str, str, int]]:
    """Use preserved HTML/PDF line layout for common `person | role` and two-line patterns."""
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    mapping: dict[str, tuple[str, str, int]] = {}
    for idx, line in enumerate(lines):
        for match in PERSON_NAME_PATTERN.finditer(line):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            candidates = [line[match.end():]]
            for j in range(idx + 1, min(len(lines), idx + 3)):
                if re.search(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\\.?|Ms\\.?)\\s+", lines[j], flags=re.I):
                    break
                candidates.append(lines[j])
            role = _role_from_context(" ".join(candidates))
            if role[1] and role[2] > mapping.get(manager, ("", "", 0))[2]:
                mapping[manager] = role
    return mapping
'''
    new_primary = '''def _line_role_candidates(raw_text: str) -> dict[str, tuple[str, str, int]]:
    """Use preserved HTML/PDF layout without leaking a following person's role into the current row."""
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    mapping: dict[str, tuple[str, str, int]] = {}
    for idx, line in enumerate(lines):
        for match in PERSON_NAME_PATTERN.finditer(line):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            # Same-line role is authoritative for this extraction pass.
            role = _role_from_context(line[match.end():])
            if not role[1]:
                # Two-line layout fallback: inspect following lines only until another person row begins.
                for j in range(idx + 1, min(len(lines), idx + 3)):
                    next_line = lines[j]
                    if re.search(r"(?<![A-Za-zÀ-ỹĐđ])(?:Ông|Bà|Mr\\.?|Ms\\.?)\\s+", next_line, flags=re.I):
                        break
                    bare_people = [
                        _candidate_name(m.group(1))
                        for m in BARE_NAME_PATTERN.finditer(next_line)
                        if _candidate_name(m.group(1))
                    ]
                    next_role = _role_from_context(next_line)
                    if bare_people and next_role[1]:
                        break
                    if next_role[1]:
                        role = next_role
                        break
            if role[1] and role[2] > mapping.get(manager, ("", "", 0))[2]:
                mapping[manager] = role
    return mapping
'''
    text = replace_once(text, old_primary, new_primary, "primary line-local role isolation")

    old_bare = '''def _bare_line_role_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract role-supported names from preserved table-like lines without requiring Ông/Bà.

    The fallback is intentionally narrow: a candidate must share a line or immediate following
    layout line with a recognized senior-management/board role. This avoids treating headings,
    company names or ordinary prose as people.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []
    for idx, line in enumerate(lines):
        context_lines = [line]
        if idx + 1 < len(lines):
            context_lines.append(lines[idx + 1])
        context = " ".join(context_lines)
        role = _role_from_context(context)
        if not role[1]:
            continue
        for match in BARE_NAME_PATTERN.finditer(line):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            # Honorific rows are handled by the primary parser; keep this fallback for genuinely bare cells.
            prefix = line[max(0, match.start() - 5):match.start()].casefold()
            if any(prefix.rstrip().endswith(x) for x in ("ông", "bà", "mr", "ms")):
                continue
            out.append((manager, role, _clean_text(context)[:900]))
    deduped: list[tuple[str, tuple[str, str, int], str]] = []
    seen: set[tuple[str, str]] = set()
    for manager, role, context in out:
        key = (manager.casefold(), role[1])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((manager, role, context))
    return deduped
'''
    new_bare = '''def _bare_line_role_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract role-supported bare names while keeping each role local to its own table row."""
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []
    for idx, line in enumerate(lines):
        matches = []
        for match in BARE_NAME_PATTERN.finditer(line):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            prefix = line[max(0, match.start() - 5):match.start()].casefold()
            if any(prefix.rstrip().endswith(x) for x in ("ông", "bà", "mr", "ms")):
                continue
            matches.append((match, manager))
        if not matches:
            continue

        for match, manager in matches:
            # Prefer a role after the person's name on the same row.
            role = _role_from_context(line[match.end():])
            context = line
            if not role[1] and idx + 1 < len(lines):
                next_line = lines[idx + 1]
                next_role = _role_from_context(next_line)
                next_people = [
                    _candidate_name(m.group(1))
                    for m in BARE_NAME_PATTERN.finditer(next_line)
                    if _candidate_name(m.group(1))
                ]
                # Only treat the next line as a role continuation when it is not another person's row.
                if next_role[1] and not next_people:
                    role = next_role
                    context = f"{line} {next_line}"
            if role[1]:
                out.append((manager, role, _clean_text(context)[:900]))

    deduped: list[tuple[str, tuple[str, str, int], str]] = []
    seen: set[tuple[str, str]] = set()
    for manager, role, context in out:
        key = (manager.casefold(), role[1])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((manager, role, context))
    return deduped
'''
    text = replace_once(text, old_bare, new_bare, "bare row-local role isolation")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_adjacent_table_rows_do_not_leak_roles_v37_1_round5c():"
    if sentinel in text:
        return
    text += '''


def test_adjacent_table_rows_do_not_leak_roles_v37_1_round5c():
    docs = [{
        "title": "Official roster 2025",
        "url": "https://example.com/roster.pdf",
        "text": (
            "Đào Hữu Huyền    Chủ tịch HĐQT\\n"
            "Phạm Văn Hùng    Phó Tổng Giám đốc\\n"
            "Nguyễn Thị Thu Hà    Thành viên HĐQT độc lập"
        ),
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
    assert ("Nguyễn Thị Thu Hà", "Independent Director") in found


def test_vice_chairman_compound_title_is_not_chairman_v37_1_round5c():
    docs = [{
        "title": "Official board roster 2025",
        "url": "https://example.com/board.pdf",
        "text": "Đào Hữu Duy Anh    Phó Chủ tịch HĐQT",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Duy Anh", "Vice Chairman") in found
    assert ("Đào Hữu Duy Anh", "Chairman") not in found
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5c row-local role isolation patch applied")


if __name__ == "__main__":
    main()
