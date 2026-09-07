from __future__ import annotations

"""Chapter 8 Phase 8K — direct official-source adapters + manual official URL ingestion.

Purpose
-------
Phase 8J proved that generic search-engine discovery can return zero archive rows even when
exchange-hosted disclosures exist. Phase 8K therefore adds a deterministic ingestion layer for
known official company/exchange/regulator URLs. It does not attempt to guess undocumented
exchange APIs. Instead it:

* validates URLs against an explicit official-source allow-list;
* fetches HTML/PDF source text directly;
* rejects wrong-ticker documents before they can become candidates;
* extracts evidence only for still-open source-locked Chapter 8 dimensions;
* reuses the existing Chapter 8 candidate schema and gap engine;
* keeps every extracted row as ``Candidate — analyst verify``;
* never promotes evidence or writes Analyst Assessment / status / confidence;
* never creates manager identities outside the Chapter 7 manager master;
* never creates a management score, MOS / Research Gate, or BUY/HOLD/SELL output.

The manual URL path is intentional: when an analyst has a direct HOSE/HNX/SSC/company PDF URL,
the app can ingest that source without depending on DuckDuckGo/Bing indexing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse
import re

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from adapters.module2_web_research import HEADERS, KNOWN_COMPANY_DOMAINS
from modules.deep_company_analysis.chapter7_research import fetch_document_text
from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    enhanced_research_gaps,
)
from modules.deep_company_analysis.chapter8_official_deep_retrieval import (
    TARGET_COLUMNS,
    build_official_deep_targets,
    documents_to_gap_candidates,
)
from modules.deep_company_analysis.chapter8_research import (
    ATTEMPT_COLUMNS,
    CANDIDATE_COLUMNS,
    evidence_quality_summary,
    source_grade_from_url,
)


OFFICIAL_DISCLOSURE_HOSTS = (
    "hsx.vn",
    "staticfile.hsx.vn",
    "hose.vn",
    "hnx.vn",
    "cms.hnx.vn",
    "cbtspre.hnx.vn",
    "abspre.hnx.vn",
    "gov.hnx.vn",
    "ssc.gov.vn",
)

# Stable public starting points only. They are seeds/navigation pages, not evidence by themselves.
DIRECT_OFFICIAL_ROOTS = (
    "https://www.hsx.vn/",
    "https://www.hnx.vn/",
    "https://ssc.gov.vn/",
)

# Current direct DGC HOSE disclosure URLs used only by the DGC acceptance harness. Keeping them
# outside the generic default search flow avoids pretending that every ticker has predictable URLs.
DGC_ACCEPTANCE_OFFICIAL_URLS = (
    "https://staticfile.hsx.vn/Uploads/UploadDocuments/2473727/20260625%20-%20DGC%20-%20CBTT%20Bien%20phap%20va%20lo%20trinh%20khac%20phuc%20CK%20bi%20canh%20bao%20do%20y%20kien%20kiem%20toan%20ngoai%20tru.pdf",
    "https://staticfile.hsx.vn/Uploads/UploadDocuments/2461133/20260508%20-%20DGC%20-%20CBTT%20NQ%20HDQT%20so%2015%20thong%20qua%20giao%20dich%20voi%20ben%20lien%20quan.pdf",
    "https://staticfile.hsx.vn/Uploads/UploadDocuments/2449838/20260401%20-%20DGC%20-%20Nhac%20nho%20cham%20nop%20BCTC%20KT%202025.pdf",
)

MANUAL_URL_COLUMNS = [
    "URL",
    "Domain",
    "Official",
    "Ticker Match",
    "Status",
    "Method",
    "Source Grade",
]


@dataclass
class OfficialURLIngestionResult:
    targets: pd.DataFrame
    attempts: pd.DataFrame
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


def _host(url: str) -> str:
    try:
        return urlparse(str(url or "")).netloc.lower().split(":")[0].lstrip("www.")
    except Exception:
        return ""


def _same_or_child(host: str, root: str) -> bool:
    return bool(host and root and (host == root or host.endswith("." + root)))


def company_official_hosts(ticker: str) -> set[str]:
    hosts: set[str] = set()
    for root in KNOWN_COMPANY_DOMAINS.get(_safe(ticker).upper(), []):
        host = _host(root)
        if host:
            hosts.add(host)
    return hosts


def is_official_url(url: str, ticker: str) -> bool:
    host = _host(url)
    if not host:
        return False
    approved = set(OFFICIAL_DISCLOSURE_HOSTS) | company_official_hosts(ticker)
    return any(_same_or_child(host, root) for root in approved)


def normalize_manual_urls(value: str | Iterable[str]) -> list[str]:
    if isinstance(value, str):
        raw = re.split(r"[\n\r,;]+", value)
    else:
        raw = list(value or [])
    urls: list[str] = []
    for item in raw:
        url = _safe(item)
        if not url.startswith(("http://", "https://")):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def _ticker_match(text: str, ticker: str) -> bool:
    symbol = _safe(ticker).upper()
    if not symbol:
        return False
    clean = _safe(text).upper()
    patterns = (
        rf"\b{re.escape(symbol)}\b",
        rf"MÃ\s+CHỨNG\s+KHOÁN\s*[:\-]?\s*{re.escape(symbol)}\b",
        rf"STOCK\s+SYMBOL\s*[:\-]?\s*{re.escape(symbol)}\b",
        rf"SECURITIES\s+SYMBOL\s*[:\-]?\s*{re.escape(symbol)}\b",
    )
    return any(re.search(pattern, clean, flags=re.IGNORECASE) for pattern in patterns)


def _html_text(url: str, timeout_seconds: float) -> tuple[str, str]:
    timeout = httpx.Timeout(timeout_seconds, connect=min(2.5, timeout_seconds))
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        ctype = _safe(response.headers.get("content-type")).lower()
        if "pdf" in ctype:
            return fetch_document_text(url, timeout_seconds=timeout_seconds, max_pages=70, max_chars=240_000)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return _safe(soup.get_text(" ", strip=True))[:240_000], "direct official HTML"


def fetch_official_url_documents(
    ticker: str,
    urls: str | Iterable[str],
    *,
    timeout_seconds: float = 6.0,
    max_urls: int = 20,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Fetch validated direct official URLs; wrong-ticker documents never proceed to extraction."""
    symbol = _safe(ticker).upper()
    normalized = normalize_manual_urls(urls)[: max(1, min(int(max_urls), 40))]
    documents: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for url in normalized:
        host = _host(url)
        official = is_official_url(url, symbol)
        if not official:
            rows.append({
                "URL": url,
                "Domain": host,
                "Official": "No",
                "Ticker Match": "Not checked",
                "Status": "Rejected — domain is outside official allow-list",
                "Method": "Phase 8K direct URL validation",
                "Source Grade": source_grade_from_url(url, symbol),
            })
            continue
        try:
            path = url.lower().split("?")[0]
            if path.endswith(".pdf"):
                text, method = fetch_document_text(
                    url, timeout_seconds=timeout_seconds, max_pages=70, max_chars=240_000
                )
            else:
                text, method = _html_text(url, timeout_seconds)
            matched = bool(text) and _ticker_match(text, symbol)
            status = "Fetched" if text and matched else ("Rejected — ticker mismatch" if text else "Empty/failed")
            rows.append({
                "URL": url,
                "Domain": host,
                "Official": "Yes",
                "Ticker Match": "Yes" if matched else "No",
                "Status": status,
                "Method": f"Phase 8K direct official URL — {method}",
                "Source Grade": source_grade_from_url(url, symbol),
            })
            if text and matched:
                documents.append({
                    "url": url,
                    "title": url.rsplit("/", 1)[-1] or url,
                    "text": text,
                    "method": f"Phase 8K direct official URL — {method}",
                    "depth": 0,
                })
        except Exception as exc:
            rows.append({
                "URL": url,
                "Domain": host,
                "Official": "Yes",
                "Ticker Match": "Unknown",
                "Status": f"Fetch failed: {exc}",
                "Method": "Phase 8K direct official URL",
                "Source Grade": source_grade_from_url(url, symbol),
            })

    return documents, pd.DataFrame(rows, columns=MANUAL_URL_COLUMNS)


def _merge_candidates(existing: pd.DataFrame, new: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    left = existing.copy() if isinstance(existing, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    right = new.copy() if isinstance(new, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    for frame in (left, right):
        for column in CANDIDATE_COLUMNS:
            if column not in frame.columns:
                frame[column] = None
    before = set(left.get("Candidate ID", pd.Series(dtype="object")).fillna("").astype(str))
    merged = pd.concat([left[CANDIDATE_COLUMNS], right[CANDIDATE_COLUMNS]], ignore_index=True)
    if not merged.empty:
        merged = merged.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
    after = set(merged.get("Candidate ID", pd.Series(dtype="object")).fillna("").astype(str))
    return merged, len(after - before)


def _open_count(frame: pd.DataFrame) -> int:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return 0
    return int((frame["Source Locked"].eq("Yes") & ~frame["Coverage Status"].eq("Candidate coverage — analyst verify")).sum())


class OfficialURLIngestionAgent:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def ingest(
        self,
        ticker: str,
        urls: str | Iterable[str],
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_urls: int = 20,
    ) -> OfficialURLIngestionResult:
        before = build_dimension_coverage(existing_candidates)
        targets = build_official_deep_targets(existing_candidates, max_targets=max_targets)
        documents, attempts = fetch_official_url_documents(ticker, urls, max_urls=max_urls)
        new_candidates = documents_to_gap_candidates(documents, ticker, targets, manager_reference)
        merged, added = _merge_candidates(existing_candidates, new_candidates)
        after = build_dimension_coverage(merged)
        gaps = enhanced_research_gaps(merged, manager_reference)
        quality = evidence_quality_summary(merged)
        document_table = pd.DataFrame([
            {
                "URL": _safe(doc.get("url")),
                "Title": _safe(doc.get("title")),
                "Method": _safe(doc.get("method")),
                "Text chars": len(_safe(doc.get("text"))),
            }
            for doc in documents
        ])
        note = (
            f"Phase 8K direct official URL ingestion: received {len(normalize_manual_urls(urls))} URL(s), "
            f"accepted {len(documents)} ticker-matched official document(s), added {added} unique candidate(s); "
            f"source-locked open dimensions {_open_count(before)} -> {_open_count(after)}. "
            "All rows remain Candidate — analyst verify; no auto-promotion, management score or investment signal."
        )
        return OfficialURLIngestionResult(
            targets=targets,
            attempts=attempts,
            documents=document_table,
            new_candidates=new_candidates,
            merged_candidates=merged,
            before_coverage=before,
            after_coverage=after,
            remaining_gaps=gaps,
            quality=quality,
            note=note,
        )


__all__ = [
    "DGC_ACCEPTANCE_OFFICIAL_URLS",
    "DIRECT_OFFICIAL_ROOTS",
    "MANUAL_URL_COLUMNS",
    "OFFICIAL_DISCLOSURE_HOSTS",
    "OfficialURLIngestionAgent",
    "OfficialURLIngestionResult",
    "company_official_hosts",
    "fetch_official_url_documents",
    "is_official_url",
    "normalize_manual_urls",
]
