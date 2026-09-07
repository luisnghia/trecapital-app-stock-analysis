from __future__ import annotations

"""Chapter 8 V60 research wrapper: V59 plus gap-directed high-resolution OCR."""

from typing import Any, Iterable, Mapping

import pandas as pd

from modules.deep_company_analysis.chapter8_official_file_ingestion_v60 import OfficialFileIngestionAgentV60
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchResult
from modules.deep_company_analysis.chapter8_research_v59 import Chapter8ResearchAgent as _V59Chapter8ResearchAgent


class Chapter8ResearchAgent(_V59Chapter8ResearchAgent):
    """V59 research plus gap-directed high-resolution OCR for scanned official PDFs."""

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
        coarse_dpi: int = 110,
        coarse_max_pages: int = 36,
        coarse_workers: int = 4,
        high_res_dpi: int = 220,
        high_res_max_pages: int = 10,
        neighbor_radius: int = 1,
    ):
        agent = OfficialFileIngestionAgentV60(self.raw_dir / "official_file_v60")
        result = agent.ingest(
            ticker,
            files,
            existing_candidates=existing_candidates,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_files=max_files,
            enable_ocr=enable_ocr,
            ocr_languages=ocr_languages,
            coarse_dpi=coarse_dpi,
            coarse_max_pages=coarse_max_pages,
            coarse_workers=coarse_workers,
            high_res_dpi=high_res_dpi,
            high_res_max_pages=high_res_max_pages,
            neighbor_radius=neighbor_radius,
        )
        self.last_gap_directed_ocr_diagnostics = agent.last_diagnostics
        return result


__all__ = ["Chapter8ResearchAgent", "Chapter8ResearchResult"]
