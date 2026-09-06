from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "chapter7_management_discovery.py"
TEST_DISCOVERY = ROOT / "modules" / "deep_company_analysis" / "test_chapter7_management_discovery.py"


def replace_function(text: str, name: str, next_name: str, new_code: str) -> str:
    start = text.find(f"def {name}(")
    end = text.find(f"def {next_name}(", start + 1)
    if start < 0 or end < 0:
        raise RuntimeError(f"V37.1 Round 5S function marker not found: {name} -> {next_name}")
    return text[:start] + new_code.rstrip() + "\n\n\n" + text[end:]


def patch_discovery() -> None:
    text = DISCOVERY.read_text(encoding="utf-8")
    code = r'''def _role_coverage_fallback_documents(
    client: httpx.Client,
    seeds: list[str],
    existing_documents: list[dict[str, Any]],
    missing_roles: list[str],
    *,
    max_fetches_per_role: int = 28,
    max_documents_per_role: int = 8,
) -> list[dict[str, Any]]:
    """Isolated same-domain coverage crawl for missing Chairman/CEO evidence.

    The first path uses role-specific site search. The second path walks a small set of common IR
    report archives (governance, financial statements, annual reports), then follows one article page
    and its linked PDFs. This solves a common IR-site shape where the archive/search result contains
    no manager name and the actual board roster lives only inside a linked PDF.

    Every retained document is original same-domain source text. This function does not invent a
    person, infer an office from a URL/title, or confirm a manager; the existing evidence parser and
    analyst-verification boundary remain authoritative.
    """
    query_map: dict[str, tuple[str, ...]] = {
        "Chairman": ("chủ tịch HĐQT", "chủ tịch hội đồng quản trị", "chairman"),
        "CEO": ("tổng giám đốc", "chief executive officer", "CEO"),
        "Vice Chairman": ("phó chủ tịch HĐQT", "phó chủ tịch hội đồng quản trị", "vice chairman"),
    }
    report_archives = (
        "category/quan-he-co-dong/bao-cao-quan-tri/",
        "category/quan-he-co-dong/bao-cao-tai-chinh/",
        "category/quan-he-co-dong/bao-cao-thuong-nien/",
        "category/quan-he-co-dong/",
    )

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

    def requested_role_signal(text: str, role: str) -> bool:
        clean = _clean_text(text)
        low = clean.casefold()
        terms: tuple[str, ...] = ()
        for normalized, role_terms, _ in ROLE_RULES:
            if normalized == role:
                terms = role_terms
                break
        role_hit = any(term.strip().casefold() in low for term in terms if term.strip())
        person_hit = bool(PERSON_NAME_PATTERN.search(clean)) or bool(_bare_line_role_candidates(text)) or bool(_role_then_name_candidates(text))
        return role_hit and person_hit

    def add_if_role_document(label: str, final_url: str, text: str, method: str, role: str) -> bool:
        if final_url in existing or len(_clean_text(text)) < 80:
            return False
        if not requested_role_signal(text, role):
            return False
        out.append({
            "title": (_clean_text(label) or f"Official {role} coverage fallback")[:240],
            "url": final_url,
            "text": text,
            "method": f"{method}; role-coverage fallback",
        })
        existing.add(final_url)
        return True

    for role in missing_roles:
        queries = query_map.get(role, ())
        if not queries:
            continue
        role_fetches = 0
        role_docs = 0
        seen: set[str] = set()

        # Path 1 — role-specific WordPress/site search result pages.
        for root, domain in roots:
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
                    if href in existing or href in seen or not _same_domain(href, domain):
                        continue
                    score = _targeted_search_child_score(final_search_url, label, href, _link_score(label, href))
                    if score > 0:
                        ranked.append((score, label, href))
                ranked.sort(key=lambda x: x[0], reverse=True)
                for _, label, href in ranked[:8]:
                    if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                        break
                    seen.add(href)
                    role_fetches += 1
                    try:
                        page_text, method, final_url, page_links = _fetch_text(client, href)
                    except Exception:
                        continue
                    if add_if_role_document(label, final_url, page_text, method, role):
                        role_docs += 1
                    # Search-result articles often contain only download labels; follow their PDFs.
                    pdf_links = [
                        (a_label, a_href) for a_label, a_href in page_links
                        if _same_domain(a_href, domain) and a_href.lower().split("?")[0].endswith(".pdf")
                    ]
                    pdf_links.sort(key=lambda item: _link_score(item[0], item[1]), reverse=True)
                    for pdf_label, pdf_href in pdf_links[:4]:
                        if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                            break
                        if pdf_href in existing or pdf_href in seen:
                            continue
                        seen.add(pdf_href)
                        role_fetches += 1
                        try:
                            pdf_text, pdf_method, pdf_final, _ = _fetch_text(client, pdf_href)
                        except Exception:
                            continue
                        if add_if_role_document(pdf_label or label, pdf_final, pdf_text, pdf_method, role):
                            role_docs += 1

            if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                break

        # Path 2 — independent small budget for common IR report archives. This is intentionally
        # separate from the broad crawler because a large site can exhaust the global queue first.
        if role_docs < max_documents_per_role:
            for root, domain in roots:
                for archive in report_archives:
                    if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                        break
                    archive_url = urljoin(root, archive)
                    try:
                        _, _, final_archive_url, archive_links = _fetch_text(client, archive_url)
                    except Exception:
                        continue
                    ranked_articles: list[tuple[int, str, str]] = []
                    for label, href in archive_links:
                        if href in existing or href in seen or not _same_domain(href, domain):
                            continue
                        path = urlparse(href).path.casefold()
                        if "/category/" in path or "/tag/" in path or "/author/" in path or "/feed/" in path:
                            continue
                        score = _link_score(label, href)
                        year = _year(f"{label} {href}")
                        if year:
                            score += max(0, int(year) - 2020) * 12
                        if href.lower().split("?")[0].endswith(".pdf"):
                            score += 120
                        else:
                            score += 40
                        ranked_articles.append((score, label, href))
                    ranked_articles.sort(key=lambda x: x[0], reverse=True)

                    for _, label, href in ranked_articles[:8]:
                        if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                            break
                        if href in seen:
                            continue
                        seen.add(href)
                        role_fetches += 1
                        try:
                            page_text, method, final_url, page_links = _fetch_text(client, href)
                        except Exception:
                            continue
                        if add_if_role_document(label, final_url, page_text, method, role):
                            role_docs += 1

                        # Crucial second hop: archive -> disclosure article -> attached official PDF.
                        attached = [
                            (a_label, a_href) for a_label, a_href in page_links
                            if _same_domain(a_href, domain) and a_href.lower().split("?")[0].endswith(".pdf")
                        ]
                        attached.sort(key=lambda item: _link_score(item[0], item[1]), reverse=True)
                        for pdf_label, pdf_href in attached[:5]:
                            if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                                break
                            if pdf_href in existing or pdf_href in seen:
                                continue
                            seen.add(pdf_href)
                            role_fetches += 1
                            try:
                                pdf_text, pdf_method, pdf_final, _ = _fetch_text(client, pdf_href)
                            except Exception:
                                continue
                            if add_if_role_document(pdf_label or label, pdf_final, pdf_text, pdf_method, role):
                                role_docs += 1
                if role_fetches >= max_fetches_per_role or role_docs >= max_documents_per_role:
                    break
    return out'''
    text = replace_function(text, "_role_coverage_fallback_documents", "discover_management_candidates", code)
    DISCOVERY.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_DISCOVERY.read_text(encoding="utf-8")
    sentinel = "def test_role_coverage_fallback_two_hop_archive_article_pdf_v37_1_round5s(monkeypatch):"
    if sentinel in text:
        return
    text += r'''


def test_role_coverage_fallback_two_hop_archive_article_pdf_v37_1_round5s(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return ("search", "HTML text extraction", url, [])
        if url.endswith("category/quan-he-co-dong/bao-cao-quan-tri/"):
            return (
                "Báo cáo quản trị",
                "HTML text extraction",
                url,
                [("Báo cáo quản trị năm 2025", "https://example.com/governance-2025/")],
            )
        if url == "https://example.com/governance-2025/":
            return (
                "Tải báo cáo quản trị",
                "HTML text extraction",
                url,
                [("2025 governance PDF", "https://example.com/uploads/governance-2025.pdf")],
            )
        if url == "https://example.com/uploads/governance-2025.pdf":
            return (
                "Hội đồng quản trị\nÔng Nguyễn Văn An\nChủ tịch HĐQT\nÔng Trần Văn Bình\nThành viên HĐQT",
                "PDF text extraction (no OCR)",
                url,
                [],
            )
        if "/category/quan-he-co-dong/" in url:
            return ("archive", "HTML text extraction", url, [])
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(),
        ["https://example.com/quan-he-co-dong/"],
        [],
        ["Chairman"],
        max_fetches_per_role=12,
        max_documents_per_role=3,
    )
    assert any(doc["url"].endswith("governance-2025.pdf") for doc in docs)
    assert any("Chủ tịch HĐQT" in doc["text"] for doc in docs)


def test_role_coverage_fallback_retains_only_requested_role_signal_v37_1_round5s(monkeypatch):
    import modules.deep_company_analysis.chapter7_management_discovery as md

    def fake_fetch_text(client, url, *args, **kwargs):
        if "?s=" in url:
            return ("search", "HTML text extraction", url, [])
        if url.endswith("category/quan-he-co-dong/bao-cao-quan-tri/"):
            return (
                "Báo cáo quản trị",
                "HTML text extraction",
                url,
                [("Report", "https://example.com/report/")],
            )
        if url == "https://example.com/report/":
            return (
                "Ông Nguyễn Văn An - Tổng Giám đốc",
                "HTML text extraction",
                url,
                [],
            )
        if "/category/quan-he-co-dong/" in url:
            return ("archive", "HTML text extraction", url, [])
        raise AssertionError(url)

    monkeypatch.setattr(md, "_fetch_text", fake_fetch_text)
    docs = md._role_coverage_fallback_documents(
        object(), ["https://example.com/quan-he-co-dong/"], [], ["Chairman"],
        max_fetches_per_role=8, max_documents_per_role=2,
    )
    assert docs == []
'''
    TEST_DISCOVERY.write_text(text, encoding="utf-8")


def main() -> None:
    patch_discovery()
    patch_tests()
    print("Chapter 7 V37.1 Round 5S two-hop official-report coverage fallback applied")


if __name__ == "__main__":
    main()
