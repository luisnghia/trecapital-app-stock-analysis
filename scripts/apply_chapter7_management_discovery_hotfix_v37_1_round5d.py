from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start_marker = f"def {name}("
    next_marker = f"def {next_name}("
    start = text.find(start_marker)
    end = text.find(next_marker, start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5d function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    # The earlier bare-name fallback intentionally used the layout text, but the shared
    # line-preserver collapses repeated spaces. A greedy person regex could therefore consume
    # the first capitalized word of a title (e.g. "Chủ"), leaving no complete role phrase.
    # Round 5D makes the recognized role span the delimiter: parse the role first, then only
    # inspect the text *before* that span for a person. This is deterministic and row-local.
    role_span_code = '''def _role_span_in_line(line: str) -> tuple[tuple[str, str, int], int, int]:
    clean = _clean_text(line)
    low = clean.casefold()
    best_role = ("", "", 0)
    best_span = (-1, -1)
    best_key = (0, 0)
    for normalized, terms, priority in ROLE_RULES:
        for term in terms:
            needle = term.casefold().strip()
            if not needle:
                continue
            pos = low.find(needle)
            if pos < 0:
                continue
            key = (len(needle), priority)
            if key > best_key:
                best_role = (term.strip(), normalized, priority)
                best_span = (pos, pos + len(needle))
                best_key = key
    return best_role, best_span[0], best_span[1]


def _line_role_candidates(raw_text: str) -> dict[str, tuple[str, str, int]]:
    """Map honorific person rows to roles using the role phrase itself as a hard delimiter."""
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    mapping: dict[str, tuple[str, str, int]] = {}
    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        role, role_start, _ = _role_span_in_line(clean_line)
        prefix = clean_line[:role_start] if role_start >= 0 else clean_line
        person_matches = list(PERSON_NAME_PATTERN.finditer(prefix))
        for match in person_matches:
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            local_role = role
            if not local_role[1]:
                for j in range(idx + 1, min(len(lines), idx + 3)):
                    next_line = _clean_text(lines[j])
                    next_role, next_role_start, _ = _role_span_in_line(next_line)
                    next_prefix = next_line[:next_role_start] if next_role_start >= 0 else next_line
                    next_honorific = bool(PERSON_NAME_PATTERN.search(next_prefix))
                    next_bare = any(
                        _candidate_name(m.group(1))
                        for m in BARE_NAME_PATTERN.finditer(next_prefix)
                    )
                    if next_honorific or next_bare:
                        break
                    if next_role[1]:
                        local_role = next_role
                        break
            if local_role[1] and local_role[2] > mapping.get(manager, ("", "", 0))[2]:
                mapping[manager] = local_role
    return mapping'''
    text = replace_function(text, "_line_role_candidates", "_bare_line_role_candidates", role_span_code)

    bare_code = '''def _bare_line_role_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract bare names only from the portion of a row preceding a locally recognized role."""
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []
    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        role, role_start, _ = _role_span_in_line(clean_line)
        prefix = clean_line[:role_start] if role_start >= 0 else clean_line

        bare_people: list[str] = []
        for match in BARE_NAME_PATTERN.finditer(prefix):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            before = prefix[max(0, match.start() - 8):match.start()].casefold().rstrip()
            if any(before.endswith(x) for x in ("ông", "bà", "mr", "mr.", "ms", "ms.")):
                continue
            bare_people.append(manager)

        if not bare_people:
            continue

        local_role = role
        context = clean_line
        if not local_role[1] and idx + 1 < len(lines):
            next_line = _clean_text(lines[idx + 1])
            next_role, next_role_start, _ = _role_span_in_line(next_line)
            next_prefix = next_line[:next_role_start] if next_role_start >= 0 else next_line
            next_honorific = bool(PERSON_NAME_PATTERN.search(next_prefix))
            next_bare = any(
                _candidate_name(m.group(1))
                for m in BARE_NAME_PATTERN.finditer(next_prefix)
            )
            if next_role[1] and not next_honorific and not next_bare:
                local_role = next_role
                context = f"{clean_line} {next_line}"

        if not local_role[1]:
            continue
        for manager in bare_people:
            out.append((manager, local_role, _clean_text(context)[:900]))

    deduped: list[tuple[str, tuple[str, str, int], str]] = []
    seen: set[tuple[str, str]] = set()
    for manager, role, context in out:
        key = (manager.casefold(), role[1])
        if key in seen:
            continue
        seen.add(key)
        deduped.append((manager, role, context))
    return deduped'''
    text = replace_function(text, "_bare_line_role_candidates", "extract_management_candidates_from_documents", bare_code)

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_role_phrase_delimits_bare_name_when_layout_spaces_collapse_v37_1_round5d():"
    if sentinel in text:
        return
    text += '''


def test_role_phrase_delimits_bare_name_when_layout_spaces_collapse_v37_1_round5d():
    docs = [{
        "title": "Official roster 2025",
        "url": "https://example.com/roster.pdf",
        "text": "Đào Hữu Huyền Chủ tịch HĐQT\\nLưu Bách Đạt Tổng Giám đốc",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Lưu Bách Đạt", "CEO") in found
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5D role-delimiter parsing patch applied")


if __name__ == "__main__":
    main()
