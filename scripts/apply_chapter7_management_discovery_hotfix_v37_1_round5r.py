from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"V37.1 Round 5R patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")

    marker = "def discover_management_candidates(\n"
    helper = r'''def _role_coverage_fallback_documents(
    client: httpx.Client,
    seeds: list[str],
    existing_documents: list[dict[str, Any]],
    missing_roles: list[str],
    *,
    max_fetches_per_role: int = 18,
    max_documents_per_role: int = 6,
) -> list[dict[str, Any]]:
    """Give each missing high-priority role a small isolated official-site crawl budget.

    The main breadth crawl intentionally has a global fetch/document budget. On large IR sites that
    budget can be consumed by valid personnel/accounting disclosures before a Chairman or CEO page is
    reached. This fallback does not invent an identity or role: it only fetches additional same-domain
    official pages from role-specific WordPress searches and feeds their original text through the
    existing candidate parser. The analyst still has to verify any discovered candidate.
    """
    query_map: dict[str, tuple[str, ...]] = {
        "Chairman": ("chủ tịch HĐQT", "chủ tịch hội đồng quản trị", "chairman"),
        "CEO": ("tổng giám đốc", "chief executive officer", "CEO"),
        "Vice Chairman": ("phó chủ tịch HĐQT", "phó chủ tịch hội đồng quản trị", "vice chairman"),
    }
    roots: list[tuple[str, str]] = []
    for seed in seeds:
        parsed = urlparse(seed)
        if parsed.scheme and parsed.netloc:
            root = f"{parsed.scheme}://{parsed.netloc}/"
            domain = _domain(root)
            if (root, domain) not in roots:
                roots.append((root, domain))

    existing = {_clean_text(d.get("url")) for d in existing_documents if isinstance(d, dict)}
    out: list[dict[str, Any]] = []
    for role in missing_roles:
        queries = query_map.get(role, ())
        if not queries:
            continue
        role_fetches = 0
        role_docs = 0
        seen_children: set[str] = set()
        for root, domain in roots:
            if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                break
            for term in queries:
                if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                    break
                search_url = root + "?s=" + quote_plus(term)
                try:
                    _, _, final_search_url, links = _fetch_text(client, search_url)
                except Exception:
                    continue
                ranked: list[tuple[int, str, str]] = []
                for label, href in links:
                    if href in existing or href in seen_children or not _same_domain(href, domain):
                        continue
                    score = _targeted_search_child_score(final_search_url, label, href, _link_score(label, href))
                    if score <= 0:
                        continue
                    ranked.append((score, label, href))
                ranked.sort(key=lambda x: x[0], reverse=True)

                for _, label, href in ranked[:10]:
                    if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                        break
                    seen_children.add(href)
                    role_fetches += 1
                    try:
                        text, method, final_url, _ = _fetch_text(client, href)
                    except Exception:
                        continue
                    if final_url in existing or len(_clean_text(text)) < 80:
                        continue
                    if not _document_has_management_signal(text):
                        continue
                    out.append({
                        "title": _source_label(label, final_url, f"Official {role} coverage fallback"),
                        "url": final_url,
                        "text": text,
                        "method": f"{method}; role-coverage fallback",
                    })
                    existing.add(final_url)
                    role_docs += 1
    return out


''' + marker
    text = replace_once(text, marker, helper, "role-coverage fallback helper")

    old = '''                    queue.append((child_score, depth + 1, child_label, child_href, root_domain))
                    queued.add(child_href)

    managers = extract_management_candidates_from_documents(documents, max_targets=max_targets, company_name=company_name)
'''
    new = '''                    queue.append((child_score, depth + 1, child_label, child_href, root_domain))
                    queued.add(child_href)

        # Coverage fallback is intentionally isolated from the breadth-crawl budget. It is invoked
        # only for missing priority roles and only adds original same-domain official documents.
        preliminary = extract_management_candidates_from_documents(
            documents, max_targets=max_targets, company_name=company_name
        )
        observed_roles = set(preliminary.get("Role Normalized", pd.Series(dtype="object")).astype(str)) if not preliminary.empty else set()
        missing_priority_roles = [role for role in ("Chairman", "CEO") if role not in observed_roles]
        if missing_priority_roles:
            documents.extend(
                _role_coverage_fallback_documents(
                    client,
                    seeds,
                    documents,
                    missing_priority_roles,
                )
            )

    managers = extract_management_candidates_from_documents(documents, max_targets=max_targets, company_name=company_name)
'''
    text = replace_once(text, old, new, "invoke isolated role-coverage fallback")
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_role_coverage_fallback_fetches_same_domain_chairman_result_v37_1_round5r(monkeypatch):"
    if sentinel in text:
        return
    text += r'''


def test_role_coverage_fallback_fetches_same_domain_chairman_result_v37_1_round5r(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return (
                "search",
                "HTML text extraction",
                url,
                [("Đại hội cổ đông thường niên", "https://example.com/agm-2025/")],
            )
        if url == "https://example.com/agm-2025/":
            return (
                "Phát biểu tại đại hội, Ông Nguyễn Văn An, Chủ tịch HĐQT, trình bày chiến lược dài hạn của công ty.",
                "HTML text extraction",
                url,
                [],
            )
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/investor-relations/"],
        [],
        ["Chairman"],
        max_fetches_per_role=4,
        max_documents_per_role=2,
    )
    assert docs
    assert docs[0]["url"] == "https://example.com/agm-2025/"
    assert "Chủ tịch HĐQT" in docs[0]["text"]


def test_role_coverage_fallback_never_crosses_official_domain_v37_1_round5r(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return (
                "search",
                "HTML text extraction",
                url,
                [("Chairman profile", "https://unrelated.example.org/chairman/")],
            )
        raise AssertionError("Off-domain result must never be fetched")

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/investor-relations/"],
        [],
        ["Chairman"],
    )
    assert docs == []
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5R isolated role-coverage fallback crawl applied")


if __name__ == "__main__":
    main()
