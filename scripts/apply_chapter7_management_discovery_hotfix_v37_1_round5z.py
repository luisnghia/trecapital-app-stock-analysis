from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
RESEARCH = ROOT / "modules" / "deep_company_analysis" / "chapter7_research.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"
TEST_RESEARCH = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_phase7c.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5Z patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    marker = "def extract_management_candidates_from_documents(documents: list[dict[str, Any]], max_targets: int = 5, company_name: str = \"\") -> pd.DataFrame:\n"
    helper = r'''def _official_form_role_candidates(raw_text: str) -> list[tuple[str, tuple[str, str, int], str]]:
    """Extract a person + role from explicit official disclosure form fields.

    Exchange/regulator disclosures commonly render fields on adjacent lines, for example::

        Họ và tên / Full name: Đào Hữu Kha
        Chức vụ hiện nay tại tổ chức niêm yết / Current position ...: Chủ tịch HĐQT

    The extractor is deliberately local and field-labelled. It does not infer identity from a URL,
    title, family relationship, or company name. Results remain research candidates requiring analyst
    verification, exactly like other management-discovery candidates.
    """
    lines = [line for line in _preserve_lines(raw_text).split("\n") if line]
    out: list[tuple[str, tuple[str, str, int], str]] = []

    def name_from_field(line: str) -> str:
        clean = _clean_text(line)
        low = clean.casefold()
        labels = (
            "họ và tên", "ho va ten", "full name", "fullname",
        )
        positions = [low.find(label) for label in labels if low.find(label) >= 0]
        if not positions:
            return ""
        # Prefer the text after the final ':' because bilingual forms may contain both labels first.
        suffix = clean.rsplit(":", 1)[-1].strip() if ":" in clean else clean[max(positions) :]
        suffix = re.sub(r"(?i)^(?:họ\s+và\s+tên|ho\s+va\s+ten|full\s*name)\s*[/|-]?\s*", "", suffix).strip(" -–—,:;")
        honorific = PERSON_NAME_PATTERN.search(suffix)
        if honorific:
            return _candidate_name(honorific.group(1))
        candidates = []
        for match in BARE_NAME_PATTERN.finditer(suffix):
            candidate = _candidate_name(match.group(1))
            if candidate:
                candidates.append(candidate)
        return max(candidates, key=lambda x: (len(x.split()), len(x)), default="")

    for idx, line in enumerate(lines):
        manager = name_from_field(line)
        if not manager:
            continue
        role = ("", "", 0)
        role_context = ""
        # Official forms usually place current position on the same or next few lines.
        for j in range(idx, min(len(lines), idx + 5)):
            candidate_line = _clean_text(lines[j])
            low = candidate_line.casefold()
            if j > idx and any(label in low for label in ("họ và tên", "ho va ten", "full name", "fullname")):
                break
            local_role, _, _ = _role_span_in_line(candidate_line)
            if local_role[1]:
                role = local_role
                role_context = candidate_line
                break
        if not role[1]:
            continue
        start = max(0, idx - 1)
        end = min(len(lines), idx + 5)
        context = _clean_text(" ".join(lines[start:end]))[:900]
        out.append((manager, role, context or _clean_text(f"{line} {role_context}")[:900]))

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
    text = replace_once(text, marker, helper, "official form-role helper")

    # Include form-layout candidates in final manager extraction, after signature-layout candidates.
    rows_marker = '''    if not rows:\n        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)\n'''
    form_rows = '''        for manager, (role_raw, role_norm, priority), context in _official_form_role_candidates(raw_text):\n            as_of = _candidate_as_of(manager, context, raw_source_title, source_url)\n            rows.append({\n                "Select": False,\n                "Manager": manager,\n                "Role Raw": role_raw,\n                "Role Normalized": role_norm,\n                "As-of Date": as_of,\n                "Source Title": source_title[:240],\n                "Source URL / File": source_url,\n                "Source Grade": "A — Company/Official disclosure",\n                "Evidence Text / Reference": context[:900],\n                "Status": "Discovered candidate — analyst verify",\n                "_priority": priority,\n            })\n    if not rows:\n        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)\n'''
    text = replace_once(text, rows_marker, form_rows, "append official form candidates")

    DISCOVERY.write_text(text, encoding="utf-8")


def patch_research() -> None:
    text = RESEARCH.read_text(encoding="utf-8")

    old_import = '''from modules.deep_company_analysis.chapter7_management_discovery import (\n    MANAGER_CANDIDATE_COLUMNS,\n    discover_management_candidates,\n)\n'''
    new_import = '''from modules.deep_company_analysis.chapter7_management_discovery import (\n    MANAGER_CANDIDATE_COLUMNS,\n    choose_research_targets,\n    discover_management_candidates,\n    extract_management_candidates_from_documents,\n)\n'''
    text = replace_once(text, old_import, new_import, "research discovery imports")

    marker = "class Chapter7ResearchAgent:\n"
    helper = r'''OFFICIAL_MANAGEMENT_DISCLOSURE_DOMAINS = (
    "staticfile.hsx.vn",
    "hsx.vn",
    "hnx.vn",
    "ssc.gov.vn",
    "upcom.vn",
)

OFFICIAL_ROLE_SEARCH_TERMS: dict[str, tuple[str, str]] = {
    "Chairman": ("Chủ tịch HĐQT", "Chairman of the Board"),
    "CEO": ("Tổng Giám đốc", "Chief Executive Officer"),
    "Vice Chairman": ("Phó Chủ tịch HĐQT", "Vice Chairman"),
}


class _OfficialRoleDisclosureAgent(WebEvidenceAgent):
    """Focused search over exchange/regulator disclosures for one missing senior role."""

    def __init__(self, raw_dir: str | Path, role: str, site_domain: str):
        super().__init__(raw_dir)
        self.role = role
        self.site_domain = site_domain

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:
        clean = self._clean_company_name(company_name)
        name = clean or company_name or ticker
        vi, en = OFFICIAL_ROLE_SEARCH_TERMS.get(self.role, (self.role, self.role))
        return [
            f'site:{self.site_domain} "{ticker}" "{vi}" "thay đổi nhân sự"',
            f'site:{self.site_domain} "{ticker}" "{name}" "{en}"',
        ]


def _is_official_management_domain(domain: str) -> bool:
    clean = _safe_text(domain).lower().replace("www.", "")
    return any(clean == root or clean.endswith("." + root) for root in ("hsx.vn", "hnx.vn", "ssc.gov.vn", "upcom.vn"))


def _merge_manager_candidate_frames(primary: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in (primary, extra) if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    for col in MANAGER_CANDIDATE_COLUMNS:
        if col not in combined.columns:
            combined[col] = False if col == "Select" else ""
    combined["_year"] = pd.to_numeric(combined["As-of Date"], errors="coerce").fillna(0)
    combined = combined.sort_values("_year", ascending=False)
    combined = combined.drop_duplicates(
        subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first"
    )
    return combined[MANAGER_CANDIDATE_COLUMNS].reset_index(drop=True)


def _official_market_manager_fallback(
    ticker: str,
    company_name: str,
    missing_roles: list[str],
    raw_dir: str | Path,
    *,
    max_results_per_query: int = 8,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[str], str]:
    """Find *candidate* management identities from Tier-A exchange/regulator disclosures.

    This fallback is invoked only for senior roles still missing after company/IR discovery. Search
    results from financial media or secondary sites are never fetched into canonical management
    discovery. Every accepted identity must come from extracted text of an A-grade HSX/HNX/SSC/UPCoM
    source and is still labelled `Discovered candidate — analyst verify`. No OCR is introduced here.
    """
    frames: list[pd.DataFrame] = []
    documents: list[dict[str, Any]] = []
    raw_paths: list[str] = []
    notes: list[str] = []
    seen_urls: set[str] = set()

    for role in [r for r in missing_roles if r in OFFICIAL_ROLE_SEARCH_TERMS]:
        role_found = False
        for site_domain in OFFICIAL_MANAGEMENT_DISCLOSURE_DOMAINS:
            agent = _OfficialRoleDisclosureAgent(raw_dir, role, site_domain)
            try:
                result = agent.search(ticker, company_name, max_results_per_query=max_results_per_query)
            except Exception as exc:
                notes.append(f"{role}@{site_domain}: search failed safely: {exc}")
                continue
            if result.raw_path:
                raw_paths.append(str(result.raw_path))
            table = result.table if isinstance(result.table, pd.DataFrame) else pd.DataFrame()
            if table.empty:
                continue

            accepted_for_role = 0
            for _, row in table.iterrows():
                source = row.to_dict()
                if _safe_text(source.get("Trạng thái")) != "Tìm thấy":
                    continue
                domain = _safe_text(source.get("Tên miền")) or WebEvidenceAgent._domain(_safe_text(source.get("Nguồn/URL")))
                if not _is_official_management_domain(domain):
                    continue
                if not source_grade(source, ticker).startswith("A —"):
                    continue
                url = _safe_text(source.get("Nguồn/URL"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                source_text, method = fetch_document_text(url, timeout_seconds=8.0, max_pages=80)
                if len(_safe_text(source_text)) < 60:
                    continue
                title = _safe_text(source.get("Tiêu đề")) or url
                document = {
                    "title": title,
                    "url": url,
                    "text": source_text,
                    "method": f"Official exchange/regulator fallback — {method}",
                }
                parsed = extract_management_candidates_from_documents(
                    [document], max_targets=10, company_name=company_name
                )
                if parsed.empty:
                    continue
                role_rows = parsed[parsed["Role Normalized"].astype(str).eq(role)].copy()
                if role_rows.empty:
                    continue
                frames.append(role_rows)
                documents.append(document)
                accepted_for_role += len(role_rows)
                role_found = True
                if accepted_for_role >= 3:
                    break
            if role_found:
                notes.append(f"{role}: Tier-A official market disclosure candidate found via {site_domain}.")
                break
        if not role_found:
            notes.append(f"{role}: no text-extractable Tier-A exchange/regulator identity candidate found.")

    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)
    if not frame.empty:
        frame = frame.drop_duplicates(
            subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first"
        ).reset_index(drop=True)
    return frame, documents, raw_paths, "Official market management fallback: " + " | ".join(notes)


''' + marker
    text = replace_once(text, marker, helper, "official market fallback helper")

    old_block = '''                discovery = discover_management_candidates(ticker, company_name, max_documents=36, max_targets=5)\n                manager_candidates = discovery.managers.copy()\n                manager_names = list(discovery.target_names)\n                direct_candidates = official_documents_to_candidates(discovery.documents, ticker, manager_names)\n                if not direct_candidates.empty:\n                    pieces.append(direct_candidates)\n                notes.append("Management target discovery: " + discovery.note)\n'''
    new_block = '''                discovery = discover_management_candidates(ticker, company_name, max_documents=36, max_targets=5)\n                manager_candidates = discovery.managers.copy()\n                all_official_documents = list(discovery.documents)\n                observed_roles = set(\n                    manager_candidates.get("Role Normalized", pd.Series(dtype="object")).astype(str)\n                ) if not manager_candidates.empty else set()\n                missing_priority_roles = [role for role in ("Chairman", "CEO") if role not in observed_roles]\n                if missing_priority_roles:\n                    market_managers, market_documents, market_raw_paths, market_note = _official_market_manager_fallback(\n                        ticker, company_name, missing_priority_roles, self.raw_dir\n                    )\n                    manager_candidates = _merge_manager_candidate_frames(manager_candidates, market_managers)\n                    all_official_documents.extend(market_documents)\n                    raw_paths.extend(market_raw_paths)\n                    notes.append(market_note)\n                manager_names = choose_research_targets(manager_candidates, max_targets=5, company_name=company_name)\n                direct_candidates = official_documents_to_candidates(all_official_documents, ticker, manager_names)\n                if not direct_candidates.empty:\n                    pieces.append(direct_candidates)\n                notes.append("Management target discovery: " + discovery.note)\n'''
    text = replace_once(text, old_block, new_block, "research search fallback integration")

    RESEARCH.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    discovery_tests = TEST_DISCOVERY.read_text(encoding="utf-8")
    discovery_sentinel = "def test_official_exchange_form_fields_extract_chairman_v37_1_round5z():"
    if discovery_sentinel not in discovery_tests:
        discovery_tests += r'''


def test_official_exchange_form_fields_extract_chairman_v37_1_round5z():
    import modules.deep_company_analysis.chapter7_management_discovery as md

    raw = (
        "THÔNG BÁO THAY ĐỔI NHÂN SỰ\n"
        "Họ và tên / Full name: Đào Hữu Kha\n"
        "Chức vụ hiện nay tại tổ chức niêm yết / Current position in the listed organization: Chủ tịch HĐQT\n"
        "Số lượng cổ phiếu nắm giữ: 22.667.148 cổ phiếu\n"
        "Ngày 08/05/2026\n"
    )
    found = md._official_form_role_candidates(raw)
    assert any(name == "Đào Hữu Kha" and role[1] == "Chairman" for name, role, _ in found)

    frame = md.extract_management_candidates_from_documents([{
        "title": "DGC - Thông báo thay đổi nhân sự HĐQT 08/05/2026",
        "url": "https://staticfile.hsx.vn/Uploads/UploadDocuments/example.pdf",
        "text": raw,
        "method": "PDF text extraction (no OCR)",
    }], company_name="Tập đoàn Hóa chất Đức Giang")
    row = frame[(frame["Manager"] == "Đào Hữu Kha") & (frame["Role Normalized"] == "Chairman")]
    assert len(row) == 1
    assert row.iloc[0]["As-of Date"] == "2026"
    assert row.iloc[0]["Status"] == "Discovered candidate — analyst verify"
'''
        TEST_DISCOVERY.write_text(discovery_tests, encoding="utf-8")

    research_tests = TEST_RESEARCH.read_text(encoding="utf-8")
    research_sentinel = "def test_official_market_fallback_accepts_hsx_and_rejects_secondary_v37_1_round5z(monkeypatch):"
    if research_sentinel not in research_tests:
        research_tests += r'''


def test_official_market_fallback_accepts_hsx_and_rejects_secondary_v37_1_round5z(monkeypatch):
    from types import SimpleNamespace
    import modules.deep_company_analysis.chapter7_research as research

    hsx_url = "https://staticfile.hsx.vn/Uploads/UploadDocuments/2461127/management.pdf"
    media_url = "https://cafef.vn/dgc-chairman.chn"

    def fake_search(self, ticker, company_name="", max_results_per_query=5):
        return SimpleNamespace(
            table=pd.DataFrame([
                {
                    "Nhóm thông tin": "Nguồn công bố chính thức",
                    "Tiêu đề": "DGC - Thông báo thay đổi nhân sự HĐQT",
                    "Nguồn/URL": hsx_url,
                    "Tên miền": "staticfile.hsx.vn",
                    "Trích yếu": "Chủ tịch HĐQT DGC",
                    "Trạng thái": "Tìm thấy",
                },
                {
                    "Nhóm thông tin": "Dữ liệu/tin tài chính",
                    "Tiêu đề": "DGC có Chủ tịch mới",
                    "Nguồn/URL": media_url,
                    "Tên miền": "cafef.vn",
                    "Trích yếu": "Tin thứ cấp",
                    "Trạng thái": "Tìm thấy",
                },
            ]),
            raw_path=None,
            note="fake",
        )

    def fake_fetch(url, *args, **kwargs):
        assert url == hsx_url, "Secondary media must never be fetched into official manager discovery"
        return (
            "THÔNG BÁO THAY ĐỔI NHÂN SỰ\n"
            "Họ và tên / Full name: Đào Hữu Kha\n"
            "Chức vụ hiện nay tại tổ chức niêm yết: Chủ tịch HĐQT\n"
            "Ngày 08/05/2026",
            "PDF text extraction (no OCR)",
        )

    monkeypatch.setattr(research._OfficialRoleDisclosureAgent, "search", fake_search)
    monkeypatch.setattr(research, "fetch_document_text", fake_fetch)
    frame, docs, raw_paths, note = research._official_market_manager_fallback(
        "DGC", "Tập đoàn Hóa chất Đức Giang", ["Chairman"], "."
    )
    assert not frame.empty
    assert ((frame["Manager"] == "Đào Hữu Kha") & (frame["Role Normalized"] == "Chairman")).any()
    assert len(docs) == 1
    assert docs[0]["url"] == hsx_url
    assert media_url not in {doc["url"] for doc in docs}
    assert raw_paths == []
    assert "Tier-A official market disclosure candidate found" in note


def test_merge_manager_candidates_preserves_company_and_exchange_evidence_v37_1_round5z():
    import modules.deep_company_analysis.chapter7_research as research

    base = pd.DataFrame([{
        "Select": False,
        "Manager": "Lưu Bách Đạt",
        "Role Raw": "tổng giám đốc",
        "Role Normalized": "CEO",
        "As-of Date": "2026",
        "Source Title": "Company disclosure",
        "Source URL / File": "https://example.com/company",
        "Source Grade": "A — Company/Official disclosure",
        "Evidence Text / Reference": "Lưu Bách Đạt - Tổng Giám đốc",
        "Status": "Discovered candidate — analyst verify",
    }])
    extra = pd.DataFrame([{
        "Select": False,
        "Manager": "Đào Hữu Kha",
        "Role Raw": "chủ tịch hđqt",
        "Role Normalized": "Chairman",
        "As-of Date": "2026",
        "Source Title": "HSX disclosure",
        "Source URL / File": "https://staticfile.hsx.vn/x.pdf",
        "Source Grade": "A — Company/Official disclosure",
        "Evidence Text / Reference": "Đào Hữu Kha - Chủ tịch HĐQT",
        "Status": "Discovered candidate — analyst verify",
    }])
    merged = research._merge_manager_candidate_frames(base, extra)
    assert set(merged["Manager"]) == {"Lưu Bách Đạt", "Đào Hữu Kha"}
    assert set(merged["Role Normalized"]) == {"CEO", "Chairman"}
'''
        TEST_RESEARCH.write_text(research_tests, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_research()
    patch_tests()
    print("Chapter 7 V37.1 Round 5Z Tier-A exchange/regulator management fallback applied")


if __name__ == "__main__":
    main()
