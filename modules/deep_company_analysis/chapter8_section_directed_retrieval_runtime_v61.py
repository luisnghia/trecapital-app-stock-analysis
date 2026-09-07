from __future__ import annotations

"""Runtime hardening for Chapter 8 Phase 8P / V61.

Some issuer WordPress category pages are reachable in browsers/search crawlers but intermittently
return no usable HTML to a CI/app HTTP client. V61 therefore keeps bounded same-domain crawling as
its first path and adds a small, auditable issuer-manifest fallback. Manifest entries are direct
issuer-hosted PDFs already linked by official IR pages; each URL still must pass the same official
allow-list and is re-downloaded/ticker-validated before candidate extraction.
"""

from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from modules.deep_company_analysis.chapter8_official_deep_retrieval import build_official_deep_targets
from modules.deep_company_analysis.chapter8_official_file_ingestion_v60 import OfficialFileIngestionAgentV60
from modules.deep_company_analysis.chapter8_official_source_adapters import is_official_url
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS
from modules.deep_company_analysis.chapter8_section_directed_retrieval_v61 import (
    DISCOVERY_COLUMNS,
    SectionDirectedRetrievalResult,
    build_section_plan,
    discover_section_directed_sources,
    download_section_documents,
    filter_targets_to_keys,
)


# Curated only from issuer-hosted IR pages; these are discovery seeds, never pre-approved evidence.
# They remain subject to URL allow-list, HTTP fetch, PDF validation, ticker match and analyst review.
VERIFIED_ISSUER_DOCUMENT_MANIFEST: dict[str, tuple[dict[str, Any], ...]] = {
    "DGC": (
        {
            "Section": "People / culture / hiring",
            "Title": "DGC Annual Report 2024",
            "Year": 2024,
            "Landing Page": "https://ducgiangchem.vn/cbtt-bao-cao-thuong-nien-2024-annual-report-2024/",
            "Document URL": "https://ducgiangchem.vn/wp-content/uploads/2025/03/20250314-DGC-Bao-cao-thuong-nien-Annual-Report-2024.pdf",
            "Score": 30,
            "Official URL": "Yes",
            "Discovery Method": "Verified issuer IR manifest fallback",
        },
        {
            "Section": "Strategy / operating model",
            "Title": "DGC Annual Report 2023",
            "Year": 2023,
            "Landing Page": "https://ducgiangchem.vn/bao-cao-thuong-nien-nam-2023/",
            "Document URL": "https://ducgiangchem.vn/wp-content/uploads/2024/03/20240319-DGC-Bao-cao-thuong-nien-nam-2023.pdf",
            "Score": 29,
            "Official URL": "Yes",
            "Discovery Method": "Verified issuer IR manifest fallback",
        },
        {
            "Section": "People / culture / hiring",
            "Title": "DGC Corporate Governance Report 2024",
            "Year": 2024,
            "Landing Page": "https://ducgiangchem.vn/cbtt-bao-cao-tinh-hinh-quan-tri-cong-ty-nam-2024/",
            "Document URL": "https://ducgiangchem.vn/wp-content/uploads/2025/01/20250122-DGC-BC-Tinh-hinh-Quan-tri-Cong-ty-nam-2024.pdf",
            "Score": 28,
            "Official URL": "Yes",
            "Discovery Method": "Verified issuer IR manifest fallback",
        },
        {
            "Section": "People / culture / hiring",
            "Title": "DGC Corporate Governance Report 2023",
            "Year": 2023,
            "Landing Page": "https://ducgiangchem.vn/category/quan-he-co-dong/bao-cao-quan-tri/",
            "Document URL": "https://ducgiangchem.vn/wp-content/uploads/2024/01/20240129-DGC-BC-tinh-hinh-quan-tri-Cong-ty-nam-2023.pdf",
            "Score": 27,
            "Official URL": "Yes",
            "Discovery Method": "Verified issuer IR manifest fallback",
        },
        {
            "Section": "Capital allocation / buyback",
            "Title": "DGC Annual Report 2022",
            "Year": 2022,
            "Landing Page": "https://ducgiangchem.vn/cbtt-bao-cao-thuong-nien-nam-2022/",
            "Document URL": "https://ducgiangchem.vn/wp-content/uploads/2023/03/20230317-DGC-BAO-CAO-THUONG-NIEN-nam-2022.pdf",
            "Score": 26,
            "Official URL": "Yes",
            "Discovery Method": "Verified issuer IR manifest fallback",
        },
    ),
}


def verified_manifest_discovery(ticker: str, *, year_floor: int | None = None) -> pd.DataFrame:
    symbol = str(ticker or "").strip().upper()
    rows: list[dict[str, Any]] = []
    for item in VERIFIED_ISSUER_DOCUMENT_MANIFEST.get(symbol, ()):
        year = int(item.get("Year") or 0)
        if year_floor is not None and year and year < int(year_floor):
            continue
        url = str(item.get("Document URL") or "").strip()
        if not url or not is_official_url(url, symbol):
            continue
        rows.append(dict(item))
    frame = pd.DataFrame(rows, columns=DISCOVERY_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(["Score", "Year", "Document URL"], ascending=[False, False, True], kind="stable").reset_index(drop=True)


def discover_section_sources_resilient(
    ticker: str,
    targets: pd.DataFrame,
    *,
    seed_urls: Iterable[str] | None = None,
    max_documents: int = 12,
    year_floor: int | None = None,
) -> pd.DataFrame:
    crawled = discover_section_directed_sources(
        ticker,
        targets,
        seed_urls=seed_urls,
        max_index_pages=18,
        max_landing_pages=24,
        max_documents=max_documents,
        year_floor=year_floor,
    )
    fallback = verified_manifest_discovery(ticker, year_floor=year_floor)
    if crawled.empty:
        return fallback.head(max_documents).reset_index(drop=True)
    if fallback.empty:
        return crawled.head(max_documents).reset_index(drop=True)
    merged = pd.concat([crawled, fallback], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Document URL"], keep="first")
    merged["Score"] = pd.to_numeric(merged["Score"], errors="coerce").fillna(0).astype(int)
    merged["Year"] = pd.to_numeric(merged["Year"], errors="coerce").fillna(0).astype(int)
    return merged.sort_values(["Score", "Year", "Document URL"], ascending=[False, False, True], kind="stable").head(max_documents).reset_index(drop=True)


class SectionDirectedRetrievalAgentV61Runtime:
    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.last_ocr_diagnostics = pd.DataFrame()

    def run(
        self,
        ticker: str,
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        target_keys: set[tuple[str, str]] | None = None,
        seed_urls: Iterable[str] | None = None,
        max_targets: int = 48,
        max_documents: int = 12,
        max_files: int = 8,
        max_scanned_ocr_docs: int = 2,
        year_floor: int | None = None,
    ) -> SectionDirectedRetrievalResult:
        base = existing_candidates if isinstance(existing_candidates, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
        targets = build_official_deep_targets(base, max_targets=max_targets)
        targets = filter_targets_to_keys(targets, target_keys)
        plan = build_section_plan(targets)
        discovery = discover_section_sources_resilient(
            ticker,
            targets,
            seed_urls=seed_urls,
            max_documents=max_documents,
            year_floor=year_floor,
        )
        files, downloads = download_section_documents(
            ticker,
            discovery,
            max_files=max_files,
            max_scanned_ocr_docs=max_scanned_ocr_docs,
        )
        ingestion_agent = OfficialFileIngestionAgentV60(self.raw_dir / "official_files")
        ingestion = ingestion_agent.ingest(
            ticker,
            files,
            existing_candidates=base,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_files=max_files,
            enable_ocr=max_scanned_ocr_docs > 0,
            ocr_languages="vie+eng",
            coarse_dpi=110,
            coarse_max_pages=30,
            coarse_workers=4,
            high_res_dpi=220,
            high_res_max_pages=8,
            neighbor_radius=1,
        )
        self.last_ocr_diagnostics = ingestion_agent.last_diagnostics
        fetched = int(downloads["Status"].astype(str).str.startswith("Fetched").sum()) if not downloads.empty else 0
        manifest_rows = int(discovery["Discovery Method"].astype(str).str.contains("manifest fallback", case=False, regex=False).sum()) if not discovery.empty else 0
        note = (
            f"Phase 8P section-directed retrieval: {len(targets)} open target(s) mapped to {len(plan)} section(s); "
            f"discovered {len(discovery)} official document candidate(s) (verified-manifest rows={manifest_rows}), "
            f"fetched {fetched}, sent {len(files)} into local extraction/OCR; new evidence candidates={len(ingestion.new_candidates)}. "
            "Manifest entries are discovery fallbacks only; every document is still fetched, ticker-validated and analyst-verified."
        )
        return SectionDirectedRetrievalResult(targets, plan, discovery, downloads, ingestion, note)


__all__ = [
    "SectionDirectedRetrievalAgentV61Runtime",
    "VERIFIED_ISSUER_DOCUMENT_MANIFEST",
    "discover_section_sources_resilient",
    "verified_manifest_discovery",
]
