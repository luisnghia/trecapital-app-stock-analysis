from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5J function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    nearest_year = r'''def _nearest_context_year(name: str, context: str) -> str:
    """Pick the reporting/event year nearest the current manager occurrence."""
    text = _clean_text(context)
    if not text:
        return ""
    needle = _clean_text(name).casefold()
    positions = [m.start() for m in re.finditer(re.escape(needle), text.casefold())] if needle else []
    center = len(text) // 2
    anchor = min(positions, key=lambda p: abs(p - center)) if positions else center
    matches: list[tuple[int, str]] = []
    for m in re.finditer(r"\b(20\d{2})\b", text):
        matches.append((abs(m.start() - anchor), m.group(1)))
    for m in re.finditer(r"\b(20\d{2})[01]\d[0-3]\d\b", text):
        matches.append((abs(m.start() - anchor), m.group(1)))
    if not matches:
        return ""
    matches.sort(key=lambda item: item[0])
    return matches[0][1]'''
    text = replace_function(text, "_nearest_context_year", "_candidate_as_of", nearest_year)

    before_and_event = r'''def _immediate_clause_before_name(name: str, context: str) -> str:
    text = _clean_text(context)
    needle = _clean_text(name).casefold()
    positions = [m.start() for m in re.finditer(re.escape(needle), text.casefold())] if needle else []
    if not positions:
        return ""
    center = len(text) // 2
    pos = min(positions, key=lambda p: abs(p - center))
    before = text[max(0, pos - 180):pos]
    pieces = re.split(r"[.;\n]", before)
    return _clean_text(pieces[-1] if pieces else before).casefold()


def _is_role_change_event(name: str, context: str) -> bool:
    clause = _immediate_clause_before_name(name, context)
    change_cues = ROLE_END_CUES + ("bổ nhiệm", "bo nhiem", "appoint", "appointed", "elected", "giữ chức vụ", "giu chuc vu")
    return bool(clause and any(cue in clause for cue in change_cues))


def _is_role_end_event(name: str, context: str) -> bool:
    clause = _immediate_clause_before_name(name, context)
    return bool(clause and any(cue in clause for cue in ROLE_END_CUES))'''
    text = replace_function(text, "_immediate_clause_before_name", "_is_role_end_event", before_and_event)

    extract_code = r'''def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5, company_name: str = "") -> pd.DataFrame:
    """Extract candidate identities and locally supported roles from official text.

    Roster/table rows use the proven row-local mapper. Personnel-change prose uses occurrence-local
    role resolution so an old dismissed role cannot overwrite a new appointment for the same person.
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
            context = _clean_text(plain[max(0, match.start() - 180):min(len(plain), match.end() + 260)])
            if _is_role_change_event(manager, context):
                role_raw, role_norm, priority = _nearest_role(plain, match.start(), match.end())
                if not role_norm:
                    role_raw, role_norm, priority = line_roles.get(manager, ("", "", 0))
            else:
                role_raw, role_norm, priority = line_roles.get(manager, ("", "", 0))
                if not role_norm:
                    role_raw, role_norm, priority = _nearest_role(plain, match.start(), match.end())
            if not role_norm:
                role_raw, role_norm, priority = "", "Unknown", 1
            if role_norm != "Unknown" and _is_role_end_event(manager, context):
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


def main() -> None:
    patch_discovery()
    print("Chapter 7 V37.1 Round 5J local-event anchoring patch applied")


if __name__ == "__main__":
    main()
