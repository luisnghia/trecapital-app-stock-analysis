from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5 patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '("Chairman", ("chủ tịch hđqt", "chủ tịch hội đồng quản trị", "chairman"), 100),',
        '("Chairman", ("chủ tịch hđqt", "chủ tịch hội đồng quản trị", "ct hđqt", "ct hdqt", "chairman"), 100),',
        "chairman abbreviation aliases",
    )
    text = replace_once(
        text,
        '("CEO", ("tổng giám đốc", "chief executive officer", " ceo "), 98),',
        '("CEO", ("tổng giám đốc", "tgđ", "tgd", "chief executive officer", " ceo "), 98),',
        "CEO abbreviation aliases",
    )
    text = replace_once(
        text,
        '("Deputy CEO", ("phó tổng giám đốc", "deputy general director", "deputy ceo"), 86),',
        '("Deputy CEO", ("phó tổng giám đốc", "p. tgđ", "p tgđ", "ptgđ", "deputy general director", "deputy ceo"), 86),',
        "deputy CEO abbreviation aliases",
    )
    text = replace_once(
        text,
        '("Independent Director", ("thành viên hđqt độc lập", "thành viên hội đồng quản trị độc lập", "independent director"), 78),',
        '("Independent Director", ("thành viên hđqt độc lập", "thành viên hội đồng quản trị độc lập", "tv hđqt độc lập", "tv hdqt doc lap", "independent director"), 78),',
        "independent-director abbreviation aliases",
    )
    text = replace_once(
        text,
        '("Board Director", ("thành viên hđqt", "ủy viên hđqt", "thành viên hội đồng quản trị", "board member", "director"), 72),',
        '("Board Director", ("thành viên hđqt", "ủy viên hđqt", "thành viên hội đồng quản trị", "tv hđqt", "tv hdqt", "board member", "director"), 72),',
        "board-director abbreviation aliases",
    )

    person_block = '''PERSON_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\\.?|Ms\\.?)\\s+"
    r"([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+"
    r"(?:\\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+){1,5})"
)'''
    person_plus_bare = person_block + '''

# Official governance/financial PDFs often render table cells without an honorific, e.g.
# `Đào Hữu Huyền    Chủ tịch HĐQT`. Bare names are therefore considered only when a
# role is present in the same/adjacent preserved-layout line; they are never accepted globally.
BARE_NAME_PATTERN = re.compile(
    r"(?<![A-Za-zÀ-ỹĐđ])([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+"
    r"(?:\\s+[A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠ-Ỹ][A-Za-zÀ-ỹĐđ'\\.-]+){1,5})"
)
'''
    text = replace_once(text, person_block, person_plus_bare, "bare-name pattern")

    marker = '''def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5) -> pd.DataFrame:
'''
    helper = '''def _bare_line_role_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
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


''' + marker
    text = replace_once(text, marker, helper, "bare role-supported name helper")

    old_loop_end = '''            rows.append({
                "Select": False,
                "Manager": manager,
                "Role Raw": role_raw,
                "Role Normalized": role_norm,
                "As-of Date": as_of,
                "Source Title": source_title[:240],
                "Source URL / File": source_url,
                "Source Grade": "A — Company/Official disclosure",
                "Evidence Text / Reference": context[:900],
                "Status": "Discovered candidate — analyst verify",
                "_priority": priority,
            })
    if not rows:
'''
    new_loop_end = '''            rows.append({
                "Select": False,
                "Manager": manager,
                "Role Raw": role_raw,
                "Role Normalized": role_norm,
                "As-of Date": as_of,
                "Source Title": source_title[:240],
                "Source URL / File": source_url,
                "Source Grade": "A — Company/Official disclosure",
                "Evidence Text / Reference": context[:900],
                "Status": "Discovered candidate — analyst verify",
                "_priority": priority,
            })
        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):
            rows.append({
                "Select": False,
                "Manager": manager,
                "Role Raw": role_raw,
                "Role Normalized": role_norm,
                "As-of Date": as_of,
                "Source Title": source_title[:240],
                "Source URL / File": source_url,
                "Source Grade": "A — Company/Official disclosure",
                "Evidence Text / Reference": context[:900],
                "Status": "Discovered candidate — analyst verify",
                "_priority": priority,
            })
    if not rows:
'''
    text = replace_once(text, old_loop_end, new_loop_end, "append bare role-supported rows")

    old_signal = '''def _document_has_management_signal(text: str) -> bool:
    low = _clean_text(text).casefold()
    role_hit = any(term.strip().casefold() in low for _, terms, _ in ROLE_RULES for term in terms if term.strip())
    person_hit = bool(PERSON_NAME_PATTERN.search(_clean_text(text)))
    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))
    return (role_hit and person_hit) or compensation_hit
'''
    new_signal = '''def _document_has_management_signal(text: str) -> bool:
    low = _clean_text(text).casefold()
    role_hit = any(term.strip().casefold() in low for _, terms, _ in ROLE_RULES for term in terms if term.strip())
    person_hit = bool(PERSON_NAME_PATTERN.search(_clean_text(text)))
    bare_role_hit = bool(_bare_line_role_candidates(text))
    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))
    return (role_hit and (person_hit or bare_role_hit)) or compensation_hit
'''
    text = replace_once(text, old_signal, new_signal, "management-signal bare-table fallback")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_bare_official_table_rows_require_local_role_v37_1_round5():"
    if sentinel in text:
        return
    text += '''


def test_bare_official_table_rows_require_local_role_v37_1_round5():
    docs = [{
        "title": "Official Q4 financial statement 2025",
        "url": "https://example.com/q4-2025.pdf",
        "text": "Hội đồng Quản trị\\nĐào Hữu Huyền    Chủ tịch HĐQT\\nPhạm Văn Hùng    Phó Tổng Giám đốc\\nNguyễn Thị Thu Hà    Thành viên HĐQT độc lập",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
    assert ("Nguyễn Thị Thu Hà", "Independent Director") in found


def test_bare_names_without_local_role_are_not_discovered_v37_1_round5():
    docs = [{
        "title": "Generic company prose",
        "url": "https://example.com/news",
        "text": "Đào Hữu Huyền tham dự sự kiện. Nguyễn Văn An phát biểu tại hội nghị.",
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs)
    assert frame.empty
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 management discovery Round 5 bare-table fallback applied")


if __name__ == "__main__":
    main()
