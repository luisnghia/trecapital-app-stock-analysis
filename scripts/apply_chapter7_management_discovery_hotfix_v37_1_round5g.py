from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"
QA = ROOT / "scripts" / "qa_chapter7_v37_1_dgc.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5G marker not found: {label}")
    return text.replace(old, new, 1)


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5G function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    marker = "def _nearest_role(raw_text: str, start: int, end: int) -> tuple[str, str, int]:\n"
    helper = '''COMMON_VN_SURNAMES = {
    "nguyễn", "trần", "lê", "phạm", "hoàng", "huỳnh", "phan", "vũ", "võ", "đặng", "bùi", "đỗ", "hồ", "ngô",
    "dương", "lý", "đào", "đinh", "lưu", "mai", "trịnh", "cao", "lâm", "tạ", "tô", "tăng", "thái", "quách",
    "châu", "chu", "hà", "kiều", "la", "mạc", "ninh", "tôn", "trương", "vương", "lại", "doãn", "thân", "thạch",
}

NON_PERSON_NAME_TOKENS = {
    "dgc", "ctcp", "tnhh", "cp", "jsc", "group", "joint", "stock", "company", "corporation", "chemical", "chemicals",
    "phòng", "ban", "stt", "họ", "cbtt", "report", "annual", "board", "management", "directors", "director",
    "mua", "bán", "cổ", "phiếu", "giấy", "đề", "cử", "biên", "bản", "nghị", "quyết", "tiếng", "english",
    "thời", "gian", "còn", "lại", "ứng", "viên", "thông", "tin", "công", "bố", "hoá", "hóa", "chất",
}

NON_PERSON_NAME_PHRASES = {
    "board of management", "board of directors", "duc giang chemicals", "dgc cho thời gian", "mua cổ phiếu của",
    "giấy đề cử", "biên bản", "nghị quyết", "công bố thông tin", "hóa chất đức giang", "hoá chất đức giang",
    "việt nam", "viöt nam", "bình dương", "lào cai", "đà nẵng", "miền nam", "phòng phòng phòng",
}

RELATED_PERSON_CUES = (
    "mẹ", "cha", "bố", "vợ", "chồng", "con", "anh", "chị", "em", "người liên quan", "related person",
)


def _has_honorific_reference(name: str, evidence: str) -> bool:
    safe = re.escape(_clean_text(name)).replace(r"\\ ", r"\\s+")
    return bool(re.search(rf"(?<![A-Za-zÀ-ỹĐđ])(?i:Ông|Bà|Mr\\.?|Ms\\.?)\\s+{safe}(?![A-Za-zÀ-ỹĐđ])", str(evidence or "")))


def _relation_cue_after_name(name: str, evidence: str) -> bool:
    low = _clean_text(evidence).casefold()
    needle = _clean_text(name).casefold()
    pos = low.find(needle)
    if pos < 0:
        return False
    tail = low[pos + len(needle): pos + len(needle) + 90]
    return any(re.search(rf"(?<!\\w){re.escape(cue.casefold())}(?!\\w)", tail) for cue in RELATED_PERSON_CUES)


def _plausible_manager_candidate(name: str, evidence: str = "", company_name: str = "") -> bool:
    """Conservative identity filter for candidate research targets, never a manager conclusion.

    A Vietnamese-domain bare name must look like a person (typically a common surname) unless the
    source explicitly uses an honorific. Organization/navigation/place fragments are rejected.
    """
    clean = _clean_text(name)
    tokens = [t.casefold().strip(".,;:()[]{}") for t in clean.split() if t.strip(".,;:()[]{}")]
    if not (2 <= len(tokens) <= 5):
        return False
    low = " ".join(tokens)
    if any(token in NON_PERSON_NAME_TOKENS for token in tokens):
        return False
    if any(phrase in low for phrase in NON_PERSON_NAME_PHRASES):
        return False
    if _relation_cue_after_name(clean, evidence):
        return False

    honorific = _has_honorific_reference(clean, evidence)
    if honorific:
        return True

    company_low = _clean_text(company_name).casefold()
    if company_low and low in company_low:
        return False

    return tokens[0] in COMMON_VN_SURNAMES


''' + marker
    text = replace_once(text, marker, helper, "plausible-person helper")

    text = replace_once(
        text,
        "def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5) -> pd.DataFrame:",
        "def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5, company_name: str = \"\") -> pd.DataFrame:",
        "company-aware extract signature",
    )

    old_tail = '''    frame = pd.DataFrame(rows)
    frame["_year_num"] = pd.to_numeric(frame["As-of Date"], errors="coerce").fillna(0)
    frame = frame.sort_values(["_year_num", "_priority"], ascending=[False, False])
    frame = frame.drop_duplicates(subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first")
    return frame[MANAGER_CANDIDATE_COLUMNS].reset_index(drop=True)
'''
    new_tail = '''    frame = pd.DataFrame(rows)
    plausible = frame.apply(
        lambda row: _plausible_manager_candidate(
            row.get("Manager", ""), row.get("Evidence Text / Reference", ""), company_name
        ),
        axis=1,
    )
    frame = frame[plausible].copy()
    if frame.empty:
        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)

    # If the same source/role contains both a full name and a shorter suffix fragment, retain the
    # longest candidate. This handles table extraction such as `TRẦN THỊ XUÂN` plus `THỊ XUÂN`.
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
    return frame[MANAGER_CANDIDATE_COLUMNS].reset_index(drop=True)
'''
    text = replace_once(text, old_tail, new_tail, "filter extracted manager candidates")

    choose_code = '''def choose_research_targets(managers: pd.DataFrame, max_targets: int = 5, company_name: str = "") -> list[str]:
    if not isinstance(managers, pd.DataFrame) or managers.empty:
        return []
    ranked = managers.copy()
    ranked = ranked[
        ranked.apply(
            lambda row: _plausible_manager_candidate(
                row.get("Manager", ""), row.get("Evidence Text / Reference", ""), company_name
            ),
            axis=1,
        )
    ].copy()
    if ranked.empty:
        return []

    priority_map = {normalized: priority for normalized, _, priority in ROLE_RULES}
    ranked["_priority"] = ranked["Role Normalized"].map(priority_map).fillna(1)
    ranked["_year"] = pd.to_numeric(ranked["As-of Date"], errors="coerce").fillna(0)
    current_year = pd.Timestamp.utcnow().year
    ranked["_year"] = ranked["_year"].clip(upper=current_year)
    ranked["_source_count"] = ranked.groupby("Manager")["Source URL / File"].transform("nunique")
    ranked = ranked.sort_values(["_year", "_priority", "_source_count"], ascending=[False, False, False])

    names: list[str] = []
    # Always seed the research queue with the strongest Chairman and CEO candidates when available;
    # this is target coverage, not confirmation of office or management quality.
    for required_role in ("Chairman", "CEO"):
        role_rows = ranked[ranked["Role Normalized"].eq(required_role)]
        for value in role_rows["Manager"].astype(str):
            name = _clean_text(value)
            if name and name not in names:
                names.append(name)
                break
        if len(names) >= max_targets:
            return names[:max_targets]

    for value in ranked["Manager"].astype(str):
        name = _clean_text(value)
        if name and name not in names:
            names.append(name)
        if len(names) >= max_targets:
            break
    return names[:max_targets]'''
    text = replace_function(text, "choose_research_targets", "_fetch_text", choose_code)

    text = replace_once(
        text,
        "managers = extract_management_candidates_from_documents(documents, max_targets=max_targets)",
        "managers = extract_management_candidates_from_documents(documents, max_targets=max_targets, company_name=company_name)",
        "company-aware extraction call",
    )
    text = replace_once(
        text,
        "targets = choose_research_targets(managers, max_targets=max_targets)",
        "targets = choose_research_targets(managers, max_targets=max_targets, company_name=company_name)",
        "company-aware target selection",
    )

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_candidate_filter_rejects_org_navigation_places_and_related_person_v37_1_round5g():"
    if sentinel in text:
        return
    text += '''


def test_candidate_filter_rejects_org_navigation_places_and_related_person_v37_1_round5g():
    from modules.deep_company_analysis.chapter7_management_discovery import _plausible_manager_candidate

    assert _plausible_manager_candidate("Đào Hữu Huyền", "CHỦ TỊCH HĐQT Đào Hữu Huyền", "Tập đoàn Hóa chất Đức Giang")
    assert _plausible_manager_candidate("Lưu Bách Đạt", "Ông Lưu Bách Đạt Tổng Giám đốc", "Tập đoàn Hóa chất Đức Giang")
    for bad in [
        "BOARD OF MANAGEMENT", "DGC CHO THỜI GIAN CÒN", "DUC GIANG CHEMICALS GROUP JOINT",
        "MUA CỔ PHIẾU CỦA", "Phòng Kinh", "STT Họ", "Việt Nam", "Bình Dương", "Lào Cai", "Đức Giang",
    ]:
        assert not _plausible_manager_candidate(bad, f"{bad} Chủ tịch HĐQT", "Tập đoàn Hóa chất Đức Giang")
    assert not _plausible_manager_candidate(
        "Trần Thị Xuân", "Bà Trần Thị Xuân - mẹ TV HĐQT độc lập", "Tập đoàn Hóa chất Đức Giang"
    )


def test_research_targets_cover_chairman_ceo_and_exclude_noise_v37_1_round5g():
    frame = extract_management_candidates_from_documents(_docs(), company_name="Tập đoàn Hóa chất Đức Giang")
    targets = choose_research_targets(frame, max_targets=5, company_name="Tập đoàn Hóa chất Đức Giang")
    assert "Đào Hữu Huyền" in targets
    assert "Lưu Bách Đạt" in targets
    assert not any("BOARD" in name.upper() or "DGC CHO" in name.upper() for name in targets)
'''
    # Ensure choose_research_targets is imported in the test module already; it is in the existing import block.
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def patch_qa() -> None:
    text = QA.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "research_targets = choose_research_targets(managers, max_targets=5)",
        "research_targets = choose_research_targets(managers, max_targets=5, company_name=company_name)",
        "QA company-aware target selection",
    )

    old_noise = '''    noisy = {
        "báo", "thay", "đổi", "nhân", "sự", "qua", "bầu", "nghị",
        "quyết", "thông", "tin", "công", "bố", "xem", "thêm", "giữ",
        "chức", "vụ", "được", "đảm",
    }
    for name in unique_names:
        if any(token.casefold() in noisy for token in str(name).split()):
            critical.append(
                f"Noise/action heading was misidentified as a manager: {name}"
            )
'''
    new_noise = '''    noisy = {
        "báo", "thay", "đổi", "nhân", "sự", "qua", "bầu", "nghị", "quyết", "thông", "tin", "công", "bố",
        "xem", "thêm", "giữ", "chức", "vụ", "được", "đảm", "dgc", "group", "joint", "chemical", "chemicals",
        "phòng", "stt", "tnhh", "cp", "mua", "cổ", "phiếu", "thời", "gian", "còn", "tiếng", "board", "management",
        "giấy", "đề", "cử",
    }
    for name in unique_names:
        if any(token.casefold().strip(".,;:()") in noisy for token in str(name).split()):
            critical.append(f"Noise/org/navigation fragment was misidentified as a manager: {name}")

    target_rows = managers[managers["Manager"].astype(str).isin(research_targets)] if not managers.empty else pd.DataFrame()
    if target_rows.empty or "Chairman" not in set(target_rows.get("Role Normalized", pd.Series(dtype="object")).astype(str)):
        critical.append("Research target queue does not include a Chairman candidate.")
    if target_rows.empty or "CEO" not in set(target_rows.get("Role Normalized", pd.Series(dtype="object")).astype(str)):
        critical.append("Research target queue does not include a CEO candidate.")
'''
    text = replace_once(text, old_noise, new_noise, "stricter QA noise and target-role gates")
    QA.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    patch_qa()
    print("Chapter 7 V37.1 Round 5G candidate-quality and target-coverage patch applied")


if __name__ == "__main__":
    main()
