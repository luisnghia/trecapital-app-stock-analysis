from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
RESEARCH = ROOT / "modules" / "deep_company_analysis" / "chapter7_research.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5F function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5F marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    candidate_code = '''def _candidate_name(raw_name: str) -> str:
    tokens = [t.strip(" ,.;:()-") for t in _clean_text(raw_name).split() if t.strip(" ,.;:()-")]
    forbidden = {
        "cbtt", "biên", "bản", "giấy", "đề", "cử", "tiếng", "english",
        "board", "management", "directors", "director", "report", "annual",
    }
    kept: list[str] = []
    for token in tokens:
        folded = token.casefold().rstrip(".")
        if folded in NOISE_NAME_TOKENS or folded in forbidden:
            break
        if not re.fullmatch(r"[A-Za-zÀ-ỹĐđ'\\.-]+", token):
            break
        kept.append(token)
        if len(kept) >= 5:
            break
    if not (2 <= len(kept) <= 5):
        return ""
    name = " ".join(kept)
    low = name.casefold()
    if any(phrase in low for phrase in (
        "board of management", "board of directors", "tiếng việt", "cbtt ",
        "giấy đề cử", "biên bản", "nghị quyết", "công bố thông tin",
    )):
        return ""
    if all(t.isupper() for t in kept) and any(t.casefold() in NOISE_NAME_TOKENS for t in kept):
        return ""
    return name'''
    text = replace_function(text, "_candidate_name", "_nearest_role", candidate_code)

    marker = "def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5) -> pd.DataFrame:\n"
    if marker not in text:
        raise RuntimeError("V37.1 Round 5F extract marker not found")
    role_then_name = '''def _role_then_name_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract signature/table layouts where a recognized role precedes the person's name.

    Examples from official filings include `CHỦ TỊCH HĐQT` on one line and the signatory name on
    the next line. The fallback is deliberately local: same line after the role, or exactly one
    following line when that line has no competing role.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []
    for idx, line in enumerate(lines):
        clean_line = _clean_text(line)
        role, role_start, role_end = _role_span_in_line(clean_line)
        if not role[1] or role_start < 0:
            continue

        candidates: list[tuple[str, str]] = []
        suffix = clean_line[role_end:].strip()
        for match in BARE_NAME_PATTERN.finditer(suffix):
            manager = _candidate_name(match.group(1))
            if manager:
                candidates.append((manager, clean_line))
                break

        if not candidates and idx + 1 < len(lines):
            next_line = _clean_text(lines[idx + 1])
            next_role, _, _ = _role_span_in_line(next_line)
            if not next_role[1]:
                for match in BARE_NAME_PATTERN.finditer(next_line):
                    manager = _candidate_name(match.group(1))
                    if manager:
                        candidates.append((manager, f"{clean_line} {next_line}"))
                        break

        for manager, context in candidates:
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
    if "def _role_then_name_candidates(" not in text:
        text = text.replace(marker, role_then_name + marker, 1)

    old_append = '''        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):
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
    new_append = '''        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):
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
        for manager, (role_raw, role_norm, priority), context in _role_then_name_candidates(raw_text):
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
    text = replace_once(text, old_append, new_append, "append role-before-name candidates")

    old_signal = '''    bare_role_hit = bool(_bare_line_role_candidates(text))
    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))
    return (role_hit and (person_hit or bare_role_hit)) or compensation_hit
'''
    new_signal = '''    bare_role_hit = bool(_bare_line_role_candidates(text))
    role_then_name_hit = bool(_role_then_name_candidates(text))
    compensation_hit = any(x in low for x in ("thù lao", "remuneration", "esop", "cổ phần nắm giữ", "ownership", "người nội bộ", "giao dịch"))
    return (role_hit and (person_hit or bare_role_hit or role_then_name_hit)) or compensation_hit
'''
    text = replace_once(text, old_signal, new_signal, "role-before-name management signal")

    old_pdf_score = '''    if url.lower().split("?")[0].endswith(".pdf"):
        score += 15
'''
    new_pdf_score = '''    if url.lower().split("?")[0].endswith(".pdf"):
        score += 65
        # Personnel resolutions, governance reports and signed appointment PDFs should outrank
        # generic IR category pages because they carry the actual named management evidence.
        if any(token in text for token in (
            "hdqt", "tgd", "nhan-su", "nhân sự", "bo-nhiem", "bổ nhiệm",
            "mien-nhiem", "miễn nhiệm", "chu-tich", "chủ tịch", "tong-giam-doc",
            "báo cáo quản trị", "bao-cao-quan-tri",
        )):
            score += 120
'''
    text = replace_once(text, old_pdf_score, new_pdf_score, "management PDF priority")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_research() -> None:
    text = RESEARCH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "discover_management_candidates(ticker, company_name, max_documents=24, max_targets=5)",
        "discover_management_candidates(ticker, company_name, max_documents=36, max_targets=5)",
        "increase official management document budget",
    )
    RESEARCH.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_role_before_name_signature_and_heading_noise_filter_v37_1_round5f():"
    if sentinel in text:
        return
    text += '''


def test_role_before_name_signature_and_heading_noise_filter_v37_1_round5f():
    docs = [{
        "title": "Official personnel resolution 2025",
        "url": "https://example.com/personnel.pdf",
        "text": (
            "CHỦ TỊCH HĐQT\\nĐào Hữu Huyền\\n"
            "CBTT BIÊN BẢN HỌP NHÓM VÀ GIẤY ĐỀ CỬ THÀNH VIÊN HĐQT"
        ),
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    found = {(r["Manager"], r["Role Normalized"]) for _, r in frame.iterrows()}
    assert ("Đào Hữu Huyền", "Chairman") in found
    names = set(frame["Manager"].astype(str))
    assert "CBTT BIÊN BẢN" not in names
    assert "GIẤY ĐỀ CỬ" not in names
    assert "BOARD OF MANAGEMENT" not in names
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_research()
    patch_tests()
    print("Chapter 7 V37.1 Round 5F signature/noise/PDF-priority patch applied")


if __name__ == "__main__":
    main()
