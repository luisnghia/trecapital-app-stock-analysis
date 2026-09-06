from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5E function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    code = '''def _line_role_candidates(raw_text: str) -> dict[str, tuple[str, str, int]]:
    """Map honorific person segments to roles without crossing into the next person.

    Official HTML often flattens several management rows into one long text line. Therefore a
    physical line is not a safe role boundary. Each Ông/Bà/Mr/Ms marker defines its own segment;
    the role is resolved only inside that segment, with a narrow two-line continuation fallback.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    mapping: dict[str, tuple[str, str, int]] = {}
    honorific_marker = re.compile(r"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\\.?|Ms\\.?)\\s+")

    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        markers = list(honorific_marker.finditer(clean_line))
        for pos, marker in enumerate(markers):
            seg_end = markers[pos + 1].start() if pos + 1 < len(markers) else len(clean_line)
            segment = clean_line[marker.start():seg_end]
            role, role_start, _ = _role_span_in_line(segment)
            prefix = segment[:role_start] if role_start >= 0 else segment
            person_match = PERSON_NAME_PATTERN.search(prefix)
            if not person_match:
                continue
            manager = _candidate_name(person_match.group(1))
            if not manager:
                continue

            local_role = role
            if not local_role[1] and pos + 1 == len(markers):
                # Only the final person segment on a physical line can continue to the next line.
                for j in range(idx + 1, min(len(lines), idx + 3)):
                    next_line = _clean_text(lines[j])
                    next_role, next_role_start, _ = _role_span_in_line(next_line)
                    next_prefix = next_line[:next_role_start] if next_role_start >= 0 else next_line
                    if honorific_marker.search(next_prefix):
                        break
                    next_bare = any(
                        _candidate_name(m.group(1))
                        for m in BARE_NAME_PATTERN.finditer(next_prefix)
                    )
                    if next_bare:
                        break
                    if next_role[1]:
                        local_role = next_role
                        break

            if local_role[1] and local_role[2] > mapping.get(manager, ("", "", 0))[2]:
                mapping[manager] = local_role
    return mapping'''
    text = replace_function(text, "_line_role_candidates", "_bare_line_role_candidates", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_flattened_multiple_honorific_people_keep_segment_local_roles_v37_1_round5e():"
    if sentinel in text:
        return
    text += '''


def test_flattened_multiple_honorific_people_keep_segment_local_roles_v37_1_round5e():
    docs = [{
        "title": "Official flattened roster 2025",
        "url": "https://example.com/flattened.html",
        "text": (
            "Ông Đào Hữu Huyền Chủ tịch HĐQT. "
            "Ông Lưu Bách Đạt Tổng Giám đốc. "
            "Ông Đào Hữu Duy Anh Phó Chủ tịch HĐQT. "
            "Ông Phạm Văn Hùng Phó Tổng Giám đốc."
        ),
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    assert ("Lưu Bách Đạt", "CEO") in found
    assert ("Đào Hữu Duy Anh", "Vice Chairman") in found
    assert ("Phạm Văn Hùng", "Deputy CEO") in found
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5E honorific-segment role isolation patch applied")


if __name__ == "__main__":
    main()
