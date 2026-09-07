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

import httpx
import pandas as pd

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
                "Official URL": "Yes" if official else "No",
                "Status": "",
                "Bytes": 0,
            }
            if not official:
                attempts.append({**row, "Status": "Rejected: URL not on official allow-list"})
                continue
            try:
                with client.stream("GET", source.document_url) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError(f"document exceeds max_bytes={max_bytes}")
                        chunks.append(chunk)
                data = b"".join(chunks)
                content_type = str(response.headers.get("content-type") or "").lower()
                if not data:
                    attempts.append({**row, "Status": "Fetch failed: empty body"})
                    continue
                if "pdf" not in content_type and not source.document_url.lower().split("?")[0].endswith(".pdf"):
                    attempts.append({**row, "Status": f"Fetch failed: unexpected content-type {content_type}"})
                    continue
                filename = source.document_url.rsplit("/", 1)[-1].split("?", 1)[0] or f"{source.key}.pdf"
                files.append({
                    "name": filename,
                    "bytes": data,
                    "issuer": source.issuer,
                    "source_url": source.document_url,
                    "official_confirmed": True,
                    "title": source.title,
                    "manifest_key": source.key,
                })
                attempts.append({**row, "Status": "Fetched", "Bytes": len(data)})
            except Exception as exc:
                attempts.append({**row, "Status": f"Fetch failed: {exc}"})
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
