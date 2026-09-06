from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "modules" / "deep_company_analysis" / "chapter7_research.py"
TEST_RESEARCH = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_phase7c.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5AA marker not found: {label}")
    return text.replace(old, new, 1)


def patch_research() -> None:
    text = RESEARCH.read_text(encoding="utf-8")

    marker = "def _official_market_manager_fallback(\n"
    helper = r'''class _OfficialCompanyRoleAgent(WebEvidenceAgent):
    """Search a known official company domain for one still-missing senior role.

    This fallback is deliberately identity-agnostic: queries contain ticker/company/role only, never
    an expected person's name. A result becomes a management candidate only after original company
    HTML/PDF text is fetched and the existing local person+role parser finds both fields.
    """

    def __init__(self, raw_dir: str | Path, role: str, site_domain: str):
        super().__init__(raw_dir)
        self.role = role
        self.site_domain = site_domain

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:
        clean = self._clean_company_name(company_name)
        name = clean or company_name or ticker
        vi, en = OFFICIAL_ROLE_SEARCH_TERMS.get(self.role, (self.role, self.role))
        return [
            f'site:{self.site_domain} "{ticker}" "{vi}" "{name}"',
            f'site:{self.site_domain} "{ticker}" "{vi}" "Họ và tên"',
            f'site:{self.site_domain} "{ticker}" "{en}" management',
        ]


def _is_known_company_domain(domain: str, ticker: str) -> bool:
    clean = _safe_text(domain).lower().replace("www.", "")
    return any(clean == root or clean.endswith("." + root) for root in _known_company_domains(ticker))


def _official_company_manager_fallback(
    ticker: str,
    company_name: str,
    missing_roles: list[str],
    raw_dir: str | Path,
    *,
    max_results_per_query: int = 8,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[str], str]:
    """Find role candidates from text-extractable documents on the company's own known domain."""
    domains = sorted(_known_company_domains(ticker))
    if not domains:
        return (
            pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS),
            [],
            [],
            "Official company role fallback: no configured official company domain.",
        )

    frames: list[pd.DataFrame] = []
    documents: list[dict[str, Any]] = []
    raw_paths: list[str] = []
    notes: list[str] = []
    seen_urls: set[str] = set()

    for role in [r for r in missing_roles if r in OFFICIAL_ROLE_SEARCH_TERMS]:
        role_found = False
        for site_domain in domains:
            agent = _OfficialCompanyRoleAgent(raw_dir, role, site_domain)
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
                if not _is_known_company_domain(domain, ticker):
                    continue
                if not source_grade(source, ticker).startswith("A —"):
                    continue
                url = _safe_text(source.get("Nguồn/URL"))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                source_text, method = fetch_document_text(url, timeout_seconds=10.0, max_pages=100)
                if len(_safe_text(source_text)) < 60:
                    continue
                title = _safe_text(source.get("Tiêu đề")) or url
                document = {
                    "title": title,
                    "url": url,
                    "text": source_text,
                    "method": f"Official company role fallback — {method}",
                }
                parsed = extract_management_candidates_from_documents(
                    [document], max_targets=12, company_name=company_name
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
                notes.append(f"{role}: official company-domain identity candidate found via {site_domain}.")
                break
        if not role_found:
            notes.append(f"{role}: no text-extractable identity candidate found on configured company domain.")

    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=MANAGER_CANDIDATE_COLUMNS)
    if not frame.empty:
        frame = frame.drop_duplicates(
            subset=["Manager", "Role Normalized", "As-of Date", "Source URL / File"], keep="first"
        ).reset_index(drop=True)
    return frame, documents, raw_paths, "Official company role fallback: " + " | ".join(notes)


''' + marker
    text = replace_once(text, marker, helper, "company-domain role fallback helper")

    old = '''                missing_priority_roles = [role for role in ("Chairman", "CEO") if role not in observed_roles]\n                if missing_priority_roles:\n                    market_managers, market_documents, market_raw_paths, market_note = _official_market_manager_fallback(\n                        ticker, company_name, missing_priority_roles, self.raw_dir\n                    )\n                    manager_candidates = _merge_manager_candidate_frames(manager_candidates, market_managers)\n                    all_official_documents.extend(market_documents)\n                    raw_paths.extend(market_raw_paths)\n                    notes.append(market_note)\n                manager_names = choose_research_targets(manager_candidates, max_targets=5, company_name=company_name)\n'''
    new = '''                missing_priority_roles = [role for role in ("Chairman", "CEO") if role not in observed_roles]\n                if missing_priority_roles:\n                    company_managers, company_documents, company_raw_paths, company_note = _official_company_manager_fallback(\n                        ticker, company_name, missing_priority_roles, self.raw_dir\n                    )\n                    manager_candidates = _merge_manager_candidate_frames(manager_candidates, company_managers)\n                    all_official_documents.extend(company_documents)\n                    raw_paths.extend(company_raw_paths)\n                    notes.append(company_note)\n                    observed_roles = set(\n                        manager_candidates.get("Role Normalized", pd.Series(dtype="object")).astype(str)\n                    ) if not manager_candidates.empty else set()\n                    missing_priority_roles = [role for role in ("Chairman", "CEO") if role not in observed_roles]\n                if missing_priority_roles:\n                    market_managers, market_documents, market_raw_paths, market_note = _official_market_manager_fallback(\n                        ticker, company_name, missing_priority_roles, self.raw_dir\n                    )\n                    manager_candidates = _merge_manager_candidate_frames(manager_candidates, market_managers)\n                    all_official_documents.extend(market_documents)\n                    raw_paths.extend(market_raw_paths)\n                    notes.append(market_note)\n                manager_names = choose_research_targets(manager_candidates, max_targets=5, company_name=company_name)\n'''
    text = replace_once(text, old, new, "company fallback before exchange fallback")
    RESEARCH.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_RESEARCH.read_text(encoding="utf-8")
    sentinel = "def test_company_domain_role_fallback_rejects_off_domain_rows_v37_1_round5aa"
    if sentinel in text:
        return
    text += r'''


def test_company_domain_role_fallback_rejects_off_domain_rows_v37_1_round5aa(monkeypatch, tmp_path):
    import pandas as pd
    import modules.deep_company_analysis.chapter7_research as research

    class FakeAgent:
        def __init__(self, *args, **kwargs):
            pass
        def search(self, ticker, company_name, max_results_per_query=8):
            class Result:
                raw_path = None
                table = pd.DataFrame([{
                    "Trạng thái": "Tìm thấy",
                    "Tên miền": "example-news.com",
                    "Nguồn/URL": "https://example-news.com/chairman",
                    "Tiêu đề": "Chairman",
                    "Nhóm thông tin": "Tin tham khảo",
                }])
            return Result()

    monkeypatch.setattr(research, "_OfficialCompanyRoleAgent", FakeAgent)
    monkeypatch.setattr(research, "_known_company_domains", lambda ticker: {"official.example.com"})
    frame, docs, paths, note = research._official_company_manager_fallback(
        "ABC", "ABC Company", ["Chairman"], tmp_path
    )
    assert frame.empty
    assert docs == []
    assert "no text-extractable" in note
'''
    TEST_RESEARCH.write_text(text, encoding="utf-8")


def main() -> None:
    patch_research()
    patch_tests()
    print("Chapter 7 V37.1 Round 5AA official company-domain role fallback applied")


if __name__ == "__main__":
    main()
