from __future__ import annotations

"""Chapter 8 V59 research wrapper: V57 official files plus scanned-PDF OCR fallback."""

from typing import Any, Iterable, Mapping

import pandas as pd

from modules.deep_company_analysis.chapter8_official_file_ingestion_v59 import OfficialFileIngestionAgentV59
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchResult
from modules.deep_company_analysis.chapter8_research_v57 import Chapter8ResearchAgent as _V57Chapter8ResearchAgent


class Chapter8ResearchAgent(_V57Chapter8ResearchAgent):
    """V57 research plus explicit OCR fallback for scanned official PDFs."""

    def ingest_official_files(
        self,
        ticker: str,
        files: Iterable[Mapping[str, Any] | Any],
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_files: int = 12,
        enable_ocr: bool = True,
        ocr_languages: str = "vie+eng",
        ocr_dpi: int = 170,
        ocr_max_pages: int = 80,
        ocr_workers: int = 2,
    ):
        return OfficialFileIngestionAgentV59(self.raw_dir / "official_file_v59").ingest(
            ticker,
            files,
            existing_candidates=existing_candidates,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_files=max_files,
            enable_ocr=enable_ocr,
            ocr_languages=ocr_languages,
            ocr_dpi=ocr_dpi,
            ocr_max_pages=ocr_max_pages,
            ocr_workers=ocr_workers,
        )


__all__ = ["Chapter8ResearchAgent", "Chapter8ResearchResult"]
