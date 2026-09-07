from __future__ import annotations

"""Chapter 8 Phase 8M — real official-document acceptance support.

This module contains a small, auditable manifest of *real* DGC documents published on the
issuer's official website. It exists to validate the V57 local-file ingestion path against real
issuer documents rather than synthetic fixtures.

Important boundaries
--------------------
* manifest entries are official-source retrieval targets, not pre-approved investment evidence;
* downloaded bytes are still ticker-gated by Phase 8L before candidate extraction;
* every extracted row remains ``Candidate — analyst verify``;
* the V54 historical coverage snapshot is used only to measure how many of the 40 then-open
  source-locked dimensions receive candidate coverage from these real documents;
* no candidate is auto-promoted and no analyst assessment/status/confidence is written here;
* no management score, MOS/Research Gate, or BUY/HOLD/SELL output is created.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from adapters.module2_web_research import HEADERS
from modules.deep_company_analysis.chapter8_official_source_adapters import is_official_url


V54_DGC_COVERAGE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "CH8_DGC_DIMENSION_COVERAGE_AFTER_V54.csv"


@dataclass(frozen=True)
class RealOfficialSource:
    key: str
    ticker: str
    document_type: str
    title: str
    published_date: str
    landing_page: str
    document_url: str
    issuer: str = "Company/IR"


DGC_REAL_OFFICIAL_SOURCES: tuple[RealOfficialSource, ...] = (
    RealOfficialSource(
        key="dgc_annual_report_2025",
        ticker="DGC",
        document_type="Annual Report",
        title="BÁO CÁO THƯỜNG NIÊN NĂM 2025",
        published_date="2026-04-07",
        landing_page="https://ducgiangchem.vn/bao-cao-thuong-nien-nam-2025/",
        document_url="https://ducgiangchem.vn/wp-content/uploads/2026/04/20260407-DGC-CBTT-Bao-cao-thuong-nien-2025.pdf",
    ),
    RealOfficialSource(
        key="dgc_governance_report_2025",
        ticker="DGC",
        document_type="Corporate Governance Report",
        title="CBTT BÁO CÁO TÌNH HÌNH QUẢN TRỊ CÔNG TY NĂM 2025",
        published_date="2026-01-30",
        landing_page="https://ducgiangchem.vn/cbtt-bao-cao-tinh-hinh-quan-tri-cong-ty-nam-2025/",
        document_url="https://ducgiangchem.vn/wp-content/uploads/2026/01/20260130-DGC-BC-tinh-hinh-quan-tri-Cong-ty-2025-1.pdf",
    ),
    RealOfficialSource(
        key="dgc_agm_minutes_2025",
        ticker="DGC",
        document_type="AGM Minutes/Resolution",
        title="CBTT NGHỊ QUYẾT, BIÊN BẢN ĐHĐCĐ THƯỜNG NIÊN 2025",
        published_date="2025-04-01",
        landing_page="https://ducgiangchem.vn/cbtt-nghi-quyet-bien-ban-dhdcd-thuong-nien-2025-resolution-minutes-of-2025-agm/",
        document_url="https://ducgiangchem.vn/wp-content/uploads/2025/04/20253103-DGC-Nghi-quyet-Bien-ban-hop-DHDCD-thuong-nien-2025-Resolution.Minutes-of-2025-AGM-1.pdf",
    ),
    RealOfficialSource(
        key="dgc_board_nomination_2026",
        ticker="DGC",
        document_type="Governance / Board Nomination",
        title="CBTT BIÊN BẢN HỌP NHÓM VÀ ĐỀ CỬ ỨNG VIÊN THAM GIA BẦU BỔ SUNG 02 THÀNH VIÊN HĐQT",
        published_date="2026-08-05",
        landing_page="https://ducgiangchem.vn/cbtt-bien-ban-hop-nhom-va-de-cu-ung-vien-tham-gia-bau-bo-sung-02-thanh-vien-hdqt/",
        document_url="https://ducgiangchem.vn/wp-content/uploads/2026/08/20260805-DGC-CBTT-BB-hop-nhom-va-De-cu-ung-vien-tham-gia-bau-bo-sung-02-TV-HDQT.pdf",
    ),
)

DOWNLOAD_COLUMNS = [
    "Key",
    "Document Type",
    "Title",
    "Published Date",
    "Landing Page",
    "Document URL",
    "Resolved Document URL",
    "Official URL",
    "Status",
    "Bytes",
]


def manifest_frame(sources: Iterable[RealOfficialSource] = DGC_REAL_OFFICIAL_SOURCES) -> pd.DataFrame:
    return pd.DataFrame([asdict(source) for source in sources])


def load_v54_dgc_coverage() -> pd.DataFrame:
    return pd.read_csv(V54_DGC_COVERAGE_FIXTURE, encoding="utf-8-sig")


def v54_historical_open_keys() -> set[tuple[str, str]]:
    frame = load_v54_dgc_coverage()
    mask = frame["Source Locked"].eq("Yes") & ~frame["Coverage Status"].eq("Candidate coverage — analyst verify")
    return set(zip(frame.loc[mask, "Question"].astype(str), frame.loc[mask, "Dimension Key"].astype(str)))


def _is_pdf_bytes(data: bytes) -> bool:
    return bool(data and data.lstrip()[:5] == b"%PDF-")


def _landing_pdf_candidates(client: httpx.Client, source: RealOfficialSource) -> list[str]:
    """Prime issuer cookies and resolve PDF hrefs from the official landing page."""
    candidates: list[str] = [source.document_url]
    try:
        response = client.get(source.landing_page, headers={**HEADERS, "Referer": "https://ducgiangchem.vn/"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        preferred_name = source.document_url.rsplit("/", 1)[-1].split("?", 1)[0].casefold()
        discovered: list[tuple[int, str]] = []
        for anchor in soup.find_all("a", href=True):
            href = urljoin(str(response.url), str(anchor.get("href") or ""))
            if ".pdf" not in href.lower().split("?", 1)[0]:
                continue
            label = str(anchor.get_text(" ", strip=True) or "").casefold()
            href_low = href.casefold()
            score = 0
            if preferred_name and preferred_name in href_low:
                score += 100
            if "dgc" in href_low:
                score += 20
            for token in source.title.casefold().split():
                if len(token) >= 5 and token in label:
                    score += 1
            discovered.append((score, href))
        for _, href in sorted(discovered, key=lambda x: (-x[0], x[1])):
            if href not in candidates:
                candidates.append(href)
    except Exception:
        pass
    return candidates


def _fetch_pdf_bytes(
    client: httpx.Client,
    source: RealOfficialSource,
    *,
    max_bytes: int,
) -> tuple[bytes, str, str]:
    """Try manifest URL and landing-page-resolved hrefs; only return genuine PDF bytes."""
    last_error = "no candidate URL"
    for url in _landing_pdf_candidates(client, source):
        try:
            headers = {
                **HEADERS,
                "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
                "Referer": source.landing_page,
                "Cache-Control": "no-cache",
            }
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"document exceeds max_bytes={max_bytes}")
                    chunks.append(chunk)
            data = b"".join(chunks)
            if _is_pdf_bytes(data):
                return data, url, "Fetched PDF bytes"
            content_type = str(response.headers.get("content-type") or "").lower()
            prefix = data[:80].decode("latin-1", errors="ignore").replace("\n", " ").replace("\r", " ")
            last_error = f"non-PDF response content-type={content_type}; prefix={prefix!r}"
        except Exception as exc:
            last_error = str(exc)
    return b"", source.document_url, last_error


def download_real_official_files(
    ticker: str,
    sources: Iterable[RealOfficialSource] = DGC_REAL_OFFICIAL_SOURCES,
    *,
    timeout_seconds: float = 35.0,
    max_bytes: int = 30 * 1024 * 1024,
) -> tuple[list[dict], pd.DataFrame]:
    """Download real issuer PDFs for the Phase 8L file-ingestion path.

    Retrieval failure is recorded explicitly. It never becomes evidence and is never silently
    replaced with synthetic text.
    """
    symbol = str(ticker or "").upper().strip()
    files: list[dict] = []
    attempts: list[dict] = []
    timeout = httpx.Timeout(timeout_seconds, connect=min(8.0, timeout_seconds))
    with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
        for source in sources:
            if source.ticker != symbol:
                continue
            official = is_official_url(source.document_url, symbol)
            row = {
                "Key": source.key,
                "Document Type": source.document_type,
                "Title": source.title,
                "Published Date": source.published_date,
                "Landing Page": source.landing_page,
                "Document URL": source.document_url,
                "Resolved Document URL": source.document_url,
                "Official URL": "Yes" if official else "No",
                "Status": "",
                "Bytes": 0,
            }
            if not official:
                attempts.append({**row, "Status": "Rejected: URL not on official allow-list"})
                continue
            data, resolved_url, status = _fetch_pdf_bytes(client, source, max_bytes=max_bytes)
            if not data:
                attempts.append({**row, "Resolved Document URL": resolved_url, "Status": f"Fetch failed: {status}"})
                continue
            if not is_official_url(resolved_url, symbol):
                attempts.append({**row, "Resolved Document URL": resolved_url, "Status": "Rejected: resolved URL not official"})
                continue
            filename = resolved_url.rsplit("/", 1)[-1].split("?", 1)[0] or f"{source.key}.pdf"
            files.append({
                "name": filename,
                "bytes": data,
                "issuer": source.issuer,
                "source_url": resolved_url,
                "official_confirmed": True,
                "title": source.title,
                "manifest_key": source.key,
            })
            attempts.append({
                **row,
                "Resolved Document URL": resolved_url,
                "Status": "Fetched",
                "Bytes": len(data),
            })
    return files, pd.DataFrame(attempts, columns=DOWNLOAD_COLUMNS)


__all__ = [
    "DGC_REAL_OFFICIAL_SOURCES",
    "DOWNLOAD_COLUMNS",
    "RealOfficialSource",
    "V54_DGC_COVERAGE_FIXTURE",
    "download_real_official_files",
    "load_v54_dgc_coverage",
    "manifest_frame",
    "v54_historical_open_keys",
]
