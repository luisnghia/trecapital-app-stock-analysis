from __future__ import annotations

"""Runtime hardening for Chapter 8 Phase 8P / V61.

Some issuer WordPress category pages and media URLs behave differently for a bare HTTP request than
for the issuer's own landing-page flow. V58-V60 already proved a reliable, evidence-conservative
retrieval path: prime the official landing page, resolve its PDF hrefs, then fetch only genuine PDF
bytes. V61 reuses that proven transport for section-directed historical documents.

A small auditable issuer manifest remains a discovery fallback only. Every document still must pass
the existing official URL allow-list, real network download, PDF signature validation, ticker gate,
and analyst-verification boundary.
"""

from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from modules.deep_company_analysis.chapter8_official_deep_retrieval import build_official_deep_targets
from modules.deep_company_analysis.chapter8_official_file_ingestion_v60 import OfficialFileIngestionAgentV60
from modules.deep_company_analysis.chapter8_official_source_adapters import is_official_url
from modules.deep_company_analysis.chapter8_real_official_sources import RealOfficialSource, download_real_official_files
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS
from modules.deep_company_analysis.chapter8_section_directed_retrieval_v61 import (
    DISCOVERY_COLUMNS,
    DOWNLOAD_COLUMNS,
    SectionDirectedRetrievalResult,
    _pdf_text_chars,
    build_section_plan,
    discover_section_directed_sources,
    filter_targets_to_keys,
)


# Curated only from issuer-hosted IR pages; these are discovery seeds, never pre-approved evidence.
# They remain subject to URL allow-list, network fetch, PDF/ticker validation and analyst review.
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


def _document_type(section: str, title: str) -> str:
    low = f"{section} {title}".casefold()
    if "governance" in low or "quản trị" in low or "quan tri" in low:
        return "Corporate Governance Report"
    if "agm" in low or "đại hội" in low or "dai hoi" in low or "resolution" in low:
        return "AGM / Resolution"
    return "Annual Report / Official Disclosure"


def download_section_documents_resilient(
    ticker: str,
    discovery: pd.DataFrame,
    *,
    max_files: int = 8,
    max_scanned_ocr_docs: int = 2,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Fetch V61 documents through the V58-V60 proven landing-page-aware downloader.

    Native-text PDFs are preferred. A bounded number of scanned PDFs may continue into V60 OCR.
    The returned status table uses V61's stable schema so QA/UI can compare attempts consistently.
    """
    symbol = str(ticker or "").strip().upper()
    if not isinstance(discovery, pd.DataFrame) or discovery.empty:
        return [], pd.DataFrame(columns=DOWNLOAD_COLUMNS)

    sources: list[RealOfficialSource] = []
    meta_by_key: dict[str, dict[str, Any]] = {}
    for seq, (_, row) in enumerate(discovery.iterrows(), start=1):
        url = str(row.get("Document URL") or "").strip()
        landing = str(row.get("Landing Page") or "").strip()
        if not url or not is_official_url(url, symbol):
            continue
        year = int(pd.to_numeric(pd.Series([row.get("Year")]), errors="coerce").fillna(0).iloc[0])
        key = f"v61_{symbol.lower()}_{year or 'undated'}_{seq}"
        title = str(row.get("Title") or url.rsplit("/", 1)[-1]).strip()
        source = RealOfficialSource(
            key=key,
            ticker=symbol,
            document_type=_document_type(str(row.get("Section") or ""), title),
            title=title,
            published_date=f"{year}-01-01" if year else "",
            landing_page=landing or url,
            document_url=url,
        )
        sources.append(source)
        meta_by_key[key] = {
            "Section": str(row.get("Section") or ""),
            "Title": title,
            "Year": year,
            "Document URL": url,
        }

    raw_files, raw_attempts = download_real_official_files(symbol, sources, timeout_seconds=35.0)
    file_by_source_url = {str(item.get("source_url") or ""): item for item in raw_files}
    file_by_key = {str(item.get("manifest_key") or ""): item for item in raw_files}
    rows: list[dict[str, Any]] = []
    fetched_items: list[tuple[dict[str, Any], int, str]] = []

    for _, attempt in raw_attempts.iterrows():
        key = str(attempt.get("Key") or "")
        meta = meta_by_key.get(key, {})
        status = str(attempt.get("Status") or "")
        resolved = str(attempt.get("Resolved Document URL") or attempt.get("Document URL") or "")
        item = file_by_key.get(key) or file_by_source_url.get(resolved)
        text_chars = _pdf_text_chars(item.get("bytes", b"")) if item else 0
        row = {
            "Section": meta.get("Section", ""),
            "Title": meta.get("Title", str(attempt.get("Title") or "")),
            "Year": meta.get("Year", 0),
            "Document URL": resolved or meta.get("Document URL", ""),
            "Status": status,
            "Bytes": int(attempt.get("Bytes") or 0),
            "Text Layer chars": int(text_chars),
            "OCR Candidate": "Yes" if item and text_chars == 0 else "No",
        }
        rows.append(row)
        if item and status == "Fetched":
            # Preserve V61 section/year metadata for downstream diagnostics.
            item = dict(item)
            item["section"] = meta.get("Section", "")
            item["year"] = meta.get("Year", 0)
            fetched_items.append((item, int(text_chars), key))

    # Prefer native text. Only bounded scanned PDFs enter OCR; diversify scans in discovery order.
    text_items = [item for item, chars, _ in fetched_items if chars > 0]
    scan_items = [item for item, chars, _ in fetched_items if chars <= 0][: max(0, min(int(max_scanned_ocr_docs), 4))]
    selected = (text_items + scan_items)[: max(1, min(int(max_files), 20))]
    selected_urls = {str(item.get("source_url") or "") for item in selected}
    for row in rows:
        if row["Status"] == "Fetched" and row["Document URL"] not in selected_urls:
            row["Status"] = "Fetched — deferred by V61 runtime budget"
    return selected, pd.DataFrame(rows, columns=DOWNLOAD_COLUMNS)


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
        files, downloads = download_section_documents_resilient(
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
            f"fetched {fetched} via landing-page-aware issuer transport, sent {len(files)} into local extraction/OCR; "
            f"new evidence candidates={len(ingestion.new_candidates)}. Manifest entries are discovery fallbacks only; "
            "every document is fetched, PDF-validated, ticker-gated and analyst-verified."
        )
        return SectionDirectedRetrievalResult(targets, plan, discovery, downloads, ingestion, note)


__all__ = [
    "SectionDirectedRetrievalAgentV61Runtime",
    "VERIFIED_ISSUER_DOCUMENT_MANIFEST",
    "discover_section_sources_resilient",
    "download_section_documents_resilient",
    "verified_manifest_discovery",
]
