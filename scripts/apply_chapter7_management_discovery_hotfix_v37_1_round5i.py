from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"
QA_DGC = ROOT / "scripts" / "qa_chapter7_v37_1_dgc.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5I function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    helper_sentinel = "GENERIC_SOURCE_TITLES = {"
    if helper_sentinel not in text:
        marker = "def _role_from_context(context: str) -> tuple[str, str, int]:\n"
        if marker not in text:
            raise RuntimeError("V37.1 Round 5I role helper marker not found")
        helper = r'''GENERIC_SOURCE_TITLES = {
    "tiếng việt", "tieng viet", "english", "trang chủ", "trang chu", "home", "home page",
}

ROLE_END_CUES = (
    "miễn nhiệm", "mien nhiem", "thôi giữ", "thoi giu", "chấm dứt", "cham dut",
    "resign", "resigned", "dismiss", "dismissed", "terminate", "terminated", "relieved",
)


def _useful_source_title(source_title: str, source_url: str) -> str:
    title = _clean_text(source_title)
    if title and title.casefold() not in GENERIC_SOURCE_TITLES:
        return title
    try:
        slug = urlparse(source_url).path.rstrip("/").split("/")[-1]
    except Exception:
        slug = ""
    slug = re.sub(r"[-_]+", " ", slug).strip()
    if slug:
        return f"Official disclosure — {slug}"
    domain = _domain(source_url)
    return f"Official disclosure — {domain}" if domain else (title or source_url)


def _nearest_context_year(name: str, context: str) -> str:
    """Pick the reporting/event year nearest the manager name, not an unrelated later page year."""
    text = _clean_text(context)
    if not text:
        return ""
    needle = _clean_text(name)
    anchor = text.casefold().find(needle.casefold()) if needle else -1
    if anchor < 0:
        anchor = len(text) // 2
    matches: list[tuple[int, str]] = []
    for m in re.finditer(r"\b(20\d{2})\b", text):
        matches.append((abs(m.start() - anchor), m.group(1)))
    for m in re.finditer(r"\b(20\d{2})[01]\d[0-3]\d\b", text):
        matches.append((abs(m.start() - anchor), m.group(1)))
    if not matches:
        return ""
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def _candidate_as_of(name: str, context: str, source_title: str, source_url: str) -> str:
    local = _nearest_context_year(name, context)
    if local:
        return local
    return _year(f"{source_title} {source_url}")


def _immediate_clause_before_name(name: str, context: str) -> str:
    text = _clean_text(context)
    needle = _clean_text(name)
    pos = text.casefold().find(needle.casefold()) if needle else -1
    if pos < 0:
        return ""
    before = text[max(0, pos - 180):pos]
    pieces = re.split(r"[.;\n]", before)
    return _clean_text(pieces[-1] if pieces else before).casefold()


def _is_role_end_event(name: str, context: str) -> bool:
    clause = _immediate_clause_before_name(name, context)
    return bool(clause and any(cue in clause for cue in ROLE_END_CUES))


'''
        text = text.replace(marker, helper + marker, 1)

    extract_code = r'''def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5, company_name: str = "") -> pd.DataFrame:
    """Extract candidate identities and locally supported roles from official text.

    This is a research-target dataset, not a confirmed current-management roster. Pure dismissal/
    termination mentions are not promoted as current-role candidates; appointment/roster evidence
    remains candidate-only and still requires analyst verification.
    """
    rows: list[dict[str, Any]] = []
    for document in documents:
        raw_text = _preserve_lines(document.get("text"))
        plain = _clean_text(raw_text)
        if not plain:
            continue
        source_url = _clean_text(document.get("url"))
        raw_source_title = _clean_text(document.get("title")) or source_url
        source_title = _useful_source_title(raw_source_title, source_url)
        line_roles = _line_role_candidates(raw_text)

        for match in PERSON_NAME_PATTERN.finditer(plain):
            manager = _candidate_name(match.group(1))
            if not manager:
                continue
            # Occurrence-local role beats a document-wide row map. This is essential for personnel
            # disclosures that both dismiss an old role and appoint a new role for the same person.
            role_raw, role_norm, priority = _nearest_role(plain, match.start(), match.end())
            if not role_norm:
                role_raw, role_norm, priority = line_roles.get(manager, ("", "", 0))
            if not role_norm:
                role_raw, role_norm, priority = "", "Unknown", 1
            context = _clean_text(plain[max(0, match.start() - 180):min(len(plain), match.end() + 260)])
            if role_norm != "Unknown" and _is_role_end_event(manager, context):
                # The ended role belongs in the historical/event trail, not the current research-target
                # role queue. A separate appointment occurrence in the same source is still captured.
                continue
            as_of = _candidate_as_of(manager, context, raw_source_title, source_url)
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

        for manager, (role_raw, role_norm, priority), context in _bare_line_role_candidates(raw_text):
            if _is_role_end_event(manager, context):
                continue
            as_of = _candidate_as_of(manager, context, raw_source_title, source_url)
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
            if _is_role_end_event(manager, context):
                continue
            as_of = _candidate_as_of(manager, context, raw_source_title, source_url)
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
        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)
    frame = pd.DataFrame(rows)
    plausible = frame.apply(
        lambda row: _plausible_manager_candidate(
            row.get("Manager", ""), row.get("Evidence Text / Reference", ""), company_name
        ),
        axis=1,
    )
    frame = frame[plausible].copy()
    if frame.empty:
        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)

    drop_idx: set[int] = set()
    for _, group in frame.groupby(["Source URL / File", "Role Normalized", "As-of Date"], dropna=False):
        entries = [(idx, _clean_text(row["Manager"]).casefold()) for idx, row in group.iterrows()]
        for idx, short in entries:
            for other_idx, long_name in entries:
                if idx == other_idx:
                    continue
                if len(long_name.split()) > len(short.split()) and (long_name.endswith(" " + short) or long_name.startswith(short + " ")):
                    drop_idx.add(idx)
                    break
    if drop_idx:
        frame = frame.drop(index=list(drop_idx))

    frame["_year_num"] = pd.to_numeric(frame["As-of Date"], errors="coerce").fillna(0)
    current_year = pd.Timestamp.utcnow().year
    frame["_year_num"] = frame["_year_num"].clip(upper=current_year)
    frame = frame.sort_values(["_year_num", "_priority"], ascending=[False, False])
    frame = frame.drop_duplicates(subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first")
    return frame[MANAGER_CANDIDATE_COLUMNS].reset_index(drop=True)'''
    text = replace_function(text, "extract_management_candidates_from_documents", "choose_research_targets", extract_code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_personnel_change_uses_local_event_role_and_date_v37_1_round5i():"
    if sentinel in text:
        return
    text += r'''


def test_personnel_change_uses_local_event_role_and_date_v37_1_round5i():
    docs = [{
        "title": "Tiếng Việt",
        "url": "https://ducgiangchem.vn/cbtt-nghi-quyet-hdqt-so-03-04-05-2025-nq-hdqt-thong-qua-thay-doi-nhan-su/",
        "text": (
            "Nghị quyết Hội đồng quản trị số 03/2025/NQ-HĐQT ngày 03/03/2025 thông qua miễn nhiệm "
            "chức danh Tổng giám đốc đối với ông Đào Hữu Duy Anh. "
            "Nghị quyết Hội đồng quản trị số 04/2025/NQ-HĐQT ngày 03/03/2025 thông qua bổ nhiệm "
            "ông Đào Hữu Duy Anh giữ chức vụ Phó chủ tịch thường trực Hội đồng quản trị. "
            "Nghị quyết số 05/2025/NQ-HĐQT ngày 03/03/2025 thông qua bổ nhiệm ông Lưu Bách Đạt "
            "giữ chức vụ Tổng giám đốc. Cùng chuyên mục: tạm ứng cổ tức năm 2026."
        ),
        "method": "HTML text extraction",
    }]
    frame = extract_management_candidates_from_documents(docs, company_name="Tập đoàn Hóa chất Đức Giang")
    found = {(r["Manager"], r["Role Normalized"], str(r["As-of Date"])) for _, r in frame.iterrows()}
    assert ("Đào Hữu Duy Anh", "Vice Chairman", "2025") in found
    assert ("Lưu Bách Đạt", "CEO", "2025") in found
    assert ("Đào Hữu Duy Anh", "CEO", "2025") not in found
    assert set(frame["As-of Date"].astype(str)) == {"2025"}
    assert "Tiếng Việt" not in set(frame["Source Title"].astype(str))


def test_annual_report_date_falls_back_to_source_title_v37_1_round5i():
    docs = [{
        "title": "Annual Report 2024",
        "url": "https://example.com/annual-report.pdf",
        "text": "Ông Nguyễn Văn An Tổng Giám đốc.",
        "method": "PDF text extraction (no OCR)",
    }]
    frame = extract_management_candidates_from_documents(docs)
    assert set(frame["As-of Date"].astype(str)) == {"2024"}
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def patch_qa() -> None:
    text = QA_DGC.read_text(encoding="utf-8")
    sentinel = "Round 5I: personnel-event semantics"
    if sentinel in text:
        return
    marker = "    if len(extracted) < 3:\n"
    if marker not in text:
        raise RuntimeError("V37.1 Round 5I DGC QA marker not found")
    block = r'''    # Round 5I: personnel-event semantics and provenance quality.
    current_year = pd.Timestamp.utcnow().year
    as_of_num = pd.to_numeric(managers.get("As-of Date", pd.Series(dtype="object")), errors="coerce")
    if bool((as_of_num > current_year).fillna(False).any()):
        critical.append("Manager candidate As-of Date contains an unrelated future year.")

    generic_titles = {"tiếng việt", "tieng viet", "english", "trang chủ", "trang chu", "home", "home page"}
    recent_rows = managers[as_of_num.fillna(0) >= 2025] if not managers.empty else pd.DataFrame()
    if not recent_rows.empty and recent_rows["Source Title"].astype(str).str.casefold().isin(generic_titles).any():
        critical.append("Recent management candidate still uses a generic navigation label as Source Title.")

    current_ceo = managers[
        managers["Manager"].astype(str).eq("Lưu Bách Đạt")
        & managers["Role Normalized"].astype(str).eq("CEO")
        & (pd.to_numeric(managers["As-of Date"], errors="coerce").fillna(0) >= 2025)
    ] if not managers.empty else pd.DataFrame()
    if current_ceo.empty:
        critical.append("DGC current CEO appointment candidate Lưu Bách Đạt (2025+) was not resolved.")

    duy_current = managers[
        managers["Manager"].astype(str).eq("Đào Hữu Duy Anh")
        & (pd.to_numeric(managers["As-of Date"], errors="coerce").fillna(0) >= 2025)
    ] if not managers.empty else pd.DataFrame()
    if duy_current.empty or "Vice Chairman" not in set(duy_current["Role Normalized"].astype(str)):
        critical.append("DGC Đào Hữu Duy Anh 2025+ Vice Chairman appointment candidate was not resolved.")
    if not duy_current.empty:
        dismissed_ceo = duy_current[
            duy_current["Role Normalized"].astype(str).eq("CEO")
            & duy_current["Evidence Text / Reference"].astype(str).str.casefold().str.contains("miễn nhiệm", na=False)
        ]
        if not dismissed_ceo.empty:
            critical.append("Dismissed DGC CEO role was incorrectly retained as a current 2025+ candidate.")

'''
    text = text.replace(marker, block + marker, 1)
    QA_DGC.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    patch_qa()
    print("Chapter 7 V37.1 Round 5I event/date/provenance patch applied")


if __name__ == "__main__":
    main()
