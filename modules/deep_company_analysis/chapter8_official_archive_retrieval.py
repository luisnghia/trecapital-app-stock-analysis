from __future__ import annotations

"""Chapter 8 Phase 8J — official archive / historical disclosure retrieval.

Phase 8I follows the company's own IR site. Phase 8J adds a second, bounded route for the
remaining source-locked dimensions: site-restricted search of the company's historical IR
archive and the exchange/regulator disclosure domains already classified as official by
Trecapital.

Research boundary:
- Chapter 7 remains the manager identity/background SSOT.
- Trecapital canonical data remains the financial SSOT.
- only still-open source-locked Chapter 8 dimensions are targeted;
- only company/IR or exchange/regulator archive domains are retained;
- candidates remain ``Candidate — analyst verify`` and are never auto-promoted;
- no analyst assessment/status/confidence is written;
- no management score, MOS/Research Gate, or BUY/HOLD/SELL is produced;
- Q46 remains exactly the five source-locked Shearn capital-allocation actions;
- Q47 still requires explicit repurchase/buyback language; share-count decline is not proof.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from adapters.module2_web_research import (
    HEADERS,
    KNOWN_COMPANY_DOMAINS,
    PRIORITY_DOMAINS,
    WebEvidenceAgent,
)
from modules.deep_company_analysis.chapter7_research import fetch_document_text
from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    enhanced_research_gaps,
)
from modules.deep_company_analysis.chapter8_official_deep_retrieval import (
    build_official_deep_targets,
    documents_to_gap_candidates,
)
from modules.deep_company_analysis.chapter8_research import (
    ATTEMPT_COLUMNS,
    CANDIDATE_COLUMNS,
    evidence_quality_summary,
    source_grade_from_url,
)


OFFICIAL_ARCHIVE_DOMAINS = tuple(
    domain
    for domain, group in PRIORITY_DOMAINS.items()
    if group == "Nguồn công bố chính thức"
)

QUERY_PLAN_COLUMNS = [
    "Question",
    "Open Dimensions",
    "Route",
    "Domain",
    "Query",
    "Boundary",
]

SEARCH_RESULT_COLUMNS = [
    "Question",
    "Route",
    "Domain",
    "Title",
    "URL",
    "Snippet",
    "Query",
    "Source Grade",
]

BOUNDARY = (
    "Historical official-source candidate only — analyst verification/promotion required; "
    "no management score or investment signal."
)

HISTORICAL_MARKERS = ("2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019")
Q47_EXPLICIT_QUERY_TERMS = (
    "buyback",
    "share repurchase",
    "treasury shares",
    "mua lại cổ phiếu",
    "cổ phiếu quỹ",
)
ARCHIVE_CONTEXT_TERMS = (
    "công bố thông tin",
    "báo cáo thường niên",
    "báo cáo quản trị",
    "nghị quyết",
    "ĐHĐCĐ",
)


@dataclass
class OfficialArchiveRetrievalResult:
    targets: pd.DataFrame
    query_plan: pd.DataFrame
    search_results: pd.DataFrame
    source_attempts: pd.DataFrame
    documents: pd.DataFrame
    new_candidates: pd.DataFrame
    merged_candidates: pd.DataFrame
    before_coverage: pd.DataFrame
    after_coverage: pd.DataFrame
    remaining_gaps: pd.DataFrame
    quality: pd.DataFrame
    note: str


def _safe(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _domain(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _domain_matches(domain: str, allowed: Iterable[str]) -> bool:
    domain = _safe(domain).lower().replace("www.", "")
    return any(
        domain == item or domain.endswith("." + item) or item.endswith("." + domain)
        for item in allowed
        if item
    )


def _company_domains(ticker: str) -> tuple[str, ...]:
    domains: list[str] = []
    for root in KNOWN_COMPANY_DOMAINS.get(_safe(ticker).upper(), []):
        domain = _domain(root)
        if domain and domain not in domains:
            domains.append(domain)
    return tuple(domains)


def allowed_archive_domains(ticker: str) -> tuple[str, ...]:
    """Return only domains already classified by Trecapital as company/official disclosure."""
    ordered: list[str] = []
    for domain in (*_company_domains(ticker), *OFFICIAL_ARCHIVE_DOMAINS):
        if domain and domain not in ordered:
            ordered.append(domain)
    return tuple(ordered)


def _terms_from_targets(frame: pd.DataFrame, *, limit: int = 6) -> list[str]:
    terms: list[str] = []
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return terms
    for raw in frame.get("Query Terms", pd.Series(dtype="object")).fillna("").astype(str):
        for term in raw.split("|"):
            clean = _safe(term)
            if len(clean) < 3:
                continue
            if clean.casefold() not in {x.casefold() for x in terms}:
                terms.append(clean)
            if len(terms) >= limit:
                return terms
    return terms


def _quoted_terms(terms: Iterable[str], *, limit: int = 4) -> str:
    out: list[str] = []
    for term in terms:
        clean = _safe(term)
        if not clean:
            continue
        if " " in clean:
            out.append(f'"{clean}"')
        else:
            out.append(clean)
        if len(out) >= limit:
            break
    return " ".join(out)


def build_archive_query_plan(
    ticker: str,
    company_name: str,
    targets: pd.DataFrame,
    *,
    max_queries: int = 18,
) -> pd.DataFrame:
    """Build at most two site-restricted historical queries per open Chapter 8 question."""
    max_queries = max(0, min(int(max_queries), 24))
    if max_queries <= 0 or not isinstance(targets, pd.DataFrame) or targets.empty:
        return pd.DataFrame(columns=QUERY_PLAN_COLUMNS)

    symbol = _safe(ticker).upper()
    company = _safe(company_name)
    company_domains = _company_domains(symbol)
    archive_domains = tuple(OFFICIAL_ARCHIVE_DOMAINS)
    rows: list[dict[str, Any]] = []
    question_order = list(dict.fromkeys(targets["Question"].fillna("").astype(str)))

    for index, question in enumerate(question_order):
        qrows = targets[targets["Question"].astype(str).eq(question)]
        terms = Q47_EXPLICIT_QUERY_TERMS if question == "Q47" else tuple(_terms_from_targets(qrows, limit=6))
        if not terms:
            continue
        dimension_count = int(len(qrows))
        subject = f'"{symbol}"'
        if company:
            words = [part for part in company.split() if len(part) >= 4][:3]
            if words:
                subject += " " + " ".join(f'"{word}"' for word in words)
        term_clause = _quoted_terms(terms, limit=4)
        years = " ".join(HISTORICAL_MARKERS[:6])

        routes: list[tuple[str, str]] = []
        if company_domains:
            routes.append(("Company historical IR", company_domains[0]))
        if archive_domains:
            routes.append(("Exchange/regulator archive", archive_domains[index % len(archive_domains)]))

        for route, domain in routes:
            if len(rows) >= max_queries:
                break
            context = _quoted_terms(ARCHIVE_CONTEXT_TERMS[:2], limit=2)
            query = _safe(f"site:{domain} {subject} {term_clause} {context} {years}")
            rows.append(
                {
                    "Question": question,
                    "Open Dimensions": dimension_count,
                    "Route": route,
                    "Domain": domain,
                    "Query": query,
                    "Boundary": BOUNDARY,
                }
            )
        if len(rows) >= max_queries:
            break

    return pd.DataFrame(rows, columns=QUERY_PLAN_COLUMNS)


def search_official_archives(
    ticker: str,
    query_plan: pd.DataFrame,
    raw_dir: str | Path,
    *,
    max_results_per_query: int = 2,
    timeout_seconds: float = 2.5,
) -> pd.DataFrame:
    """Run site-restricted search and retain only company/exchange/regulator archive URLs."""
    if not isinstance(query_plan, pd.DataFrame) or query_plan.empty:
        return pd.DataFrame(columns=SEARCH_RESULT_COLUMNS)
    max_results_per_query = max(1, min(int(max_results_per_query), 4))
    allowed = allowed_archive_domains(ticker)
    agent = WebEvidenceAgent(raw_dir)
    rows: list[dict[str, Any]] = []
    timeout = httpx.Timeout(timeout_seconds, connect=min(1.2, timeout_seconds))

    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        for _, plan in query_plan.iterrows():
            query = _safe(plan.get("Query"))
            if not query:
                continue
            found, _ = agent._search_duckduckgo(client, query, max_results_per_query)
            if not found:
                found, _ = agent._search_bing(client, query, max_results_per_query)
            for item in found:
                url = _safe(item.get("Nguồn/URL"))
                domain = _domain(url)
                if not url or not _domain_matches(domain, allowed):
                    continue
                rows.append(
                    {
                        "Question": _safe(plan.get("Question")),
                        "Route": _safe(plan.get("Route")),
                        "Domain": domain,
                        "Title": _safe(item.get("Tiêu đề"))[:240],
                        "URL": url,
                        "Snippet": _safe(item.get("Trích yếu"))[:900],
                        "Query": query,
                        "Source Grade": source_grade_from_url(url, ticker),
                    }
                )
    frame = pd.DataFrame(rows, columns=SEARCH_RESULT_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["URL"], keep="first").reset_index(drop=True)


def _fetch_archive_text(url: str, *, timeout_seconds: float = 5.0) -> tuple[str, str]:
    """Use the shared document extractor first, then a bounded HTML fallback."""
    try:
        text, method = fetch_document_text(
            url,
            timeout_seconds=timeout_seconds,
            max_pages=80,
            max_chars=260_000,
        )
        if _safe(text):
            return _safe(text), method
    except Exception:
        pass

    timeout = httpx.Timeout(timeout_seconds, connect=min(2.5, timeout_seconds))
    try:
        with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg"]):
                tag.decompose()
            text = _safe(soup.get_text(" ", strip=True))[:260_000]
            return text, "Phase 8J bounded HTML fallback" if text else "HTML empty"
    except Exception as exc:
        return "", f"fetch failed: {exc}"


def fetch_archive_documents(
    ticker: str,
    search_results: pd.DataFrame,
    *,
    max_documents: int = 14,
    timeout_seconds: float = 5.0,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Open the bounded official archive result set and retain extracted source text."""
    max_documents = max(0, min(int(max_documents), 24))
    if max_documents <= 0 or not isinstance(search_results, pd.DataFrame) or search_results.empty:
        return [], pd.DataFrame(columns=ATTEMPT_COLUMNS)

    allowed = allowed_archive_domains(ticker)
    documents: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for _, row in search_results.head(max_documents).iterrows():
        url = _safe(row.get("URL"))
        domain = _domain(url)
        if not url or not _domain_matches(domain, allowed):
            continue
        text, method = _fetch_archive_text(url, timeout_seconds=timeout_seconds)
        attempts.append(
            {
                "URL": url,
                "Domain": domain,
                "Status": "Fetched" if text else "Empty/failed",
                "Method": f"Phase 8J official archive — {method}",
                "Source Grade": source_grade_from_url(url, ticker),
            }
        )
        if len(text) < 160:
            continue
        documents.append(
            {
                "url": url,
                "title": _safe(row.get("Title")) or url,
                "text": text,
                "method": f"Phase 8J official archive — {method}",
                "depth": "archive-search",
            }
        )
    return documents, pd.DataFrame(attempts, columns=ATTEMPT_COLUMNS)


def archive_documents_to_gap_candidates(
    documents: list[dict[str, Any]],
    ticker: str,
    targets: pd.DataFrame,
    manager_reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Reuse the source-locked dimension matcher while relabeling provenance as Phase 8J."""
    frame = documents_to_gap_candidates(documents, ticker, targets, manager_reference)
    if frame.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    frame = frame.copy()
    frame["Explicitness"] = "Historical official disclosure text — analyst verify"
    frame["Source Method"] = frame["Source Method"].fillna("").astype(str).str.replace(
        "Phase 8I official deep retrieval",
        "Phase 8J official archive/historical retrieval",
        regex=False,
    )
    frame["Data Origin"] = "Official company/exchange/regulator archive — analyst verification required"
    frame["Status"] = "Candidate — analyst verify"
    frame["Select"] = False
    return frame[CANDIDATE_COLUMNS].reset_index(drop=True)


def _merge_candidates(existing: pd.DataFrame, new_candidates: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    left = existing.copy() if isinstance(existing, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    right = new_candidates.copy() if isinstance(new_candidates, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    for frame in (left, right):
        for column in CANDIDATE_COLUMNS:
            if column not in frame.columns:
                frame[column] = None
    before = set(left["Candidate ID"].fillna("").astype(str)) if "Candidate ID" in left else set()
    merged = pd.concat([left[CANDIDATE_COLUMNS], right[CANDIDATE_COLUMNS]], ignore_index=True)
    if not merged.empty:
        merged = merged.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
    after = set(merged["Candidate ID"].fillna("").astype(str)) if "Candidate ID" in merged else set()
    return merged, len(after - before)


def _open_count(coverage: pd.DataFrame) -> int:
    if not isinstance(coverage, pd.DataFrame) or coverage.empty:
        return 0
    return int(
        (
            coverage["Source Locked"].eq("Yes")
            & ~coverage["Coverage Status"].eq("Candidate coverage — analyst verify")
        ).sum()
    )


class OfficialArchiveRetrievalAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def search(
        self,
        ticker: str,
        company_name: str,
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_queries: int = 18,
        max_results_per_query: int = 2,
        max_documents: int = 14,
    ) -> OfficialArchiveRetrievalResult:
        before = build_dimension_coverage(existing_candidates)
        targets = build_official_deep_targets(existing_candidates, max_targets=max_targets)
        query_plan = build_archive_query_plan(
            ticker,
            company_name,
            targets,
            max_queries=max_queries,
        )
        search_results = search_official_archives(
            ticker,
            query_plan,
            self.raw_dir / "search",
            max_results_per_query=max_results_per_query,
        )
        documents, attempts = fetch_archive_documents(
            ticker,
            search_results,
            max_documents=max_documents,
        )
        new_candidates = archive_documents_to_gap_candidates(
            documents,
            ticker,
            targets,
            manager_reference,
        )
        merged, added = _merge_candidates(existing_candidates, new_candidates)
        after = build_dimension_coverage(merged)
        remaining = enhanced_research_gaps(merged, manager_reference)
        quality = evidence_quality_summary(merged)
        document_table = pd.DataFrame(
            [
                {
                    "URL": _safe(doc.get("url")),
                    "Title": _safe(doc.get("title")),
                    "Method": _safe(doc.get("method")),
                    "Text chars": len(_safe(doc.get("text"))),
                    "Source Grade": source_grade_from_url(_safe(doc.get("url")), ticker),
                }
                for doc in documents
            ]
        )
        note = (
            f"Phase 8J official archive/historical retrieval: planned {len(query_plan)} site-restricted query(ies), "
            f"retained {len(search_results)} official archive result(s), fetched {len(documents)} text document(s), "
            f"added {added} unique candidate(s); source-locked open dimensions "
            f"{_open_count(before)} -> {_open_count(after)}. Candidates still require analyst verification/promotion; "
            "no management score or investment signal is produced."
        )
        return OfficialArchiveRetrievalResult(
            targets=targets,
            query_plan=query_plan,
            search_results=search_results,
            source_attempts=attempts,
            documents=document_table,
            new_candidates=new_candidates,
            merged_candidates=merged,
            before_coverage=before,
            after_coverage=after,
            remaining_gaps=remaining,
            quality=quality,
            note=note,
        )


__all__ = [
    "OFFICIAL_ARCHIVE_DOMAINS",
    "OfficialArchiveRetrievalAgent",
    "OfficialArchiveRetrievalResult",
    "allowed_archive_domains",
    "archive_documents_to_gap_candidates",
    "build_archive_query_plan",
    "fetch_archive_documents",
    "search_official_archives",
]
