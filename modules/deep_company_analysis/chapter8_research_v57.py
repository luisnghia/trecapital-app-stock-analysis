from __future__ import annotations

"""Chapter 8 V57 research wrapper: V56 direct URLs plus analyst-supplied official files."""

from typing import Any, Iterable, Mapping

import pandas as pd

from modules.deep_company_analysis.chapter8_official_file_ingestion import OfficialFileIngestionAgent
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchResult
from modules.deep_company_analysis.chapter8_research_v56 import Chapter8ResearchAgent as _V56Chapter8ResearchAgent


class Chapter8ResearchAgent(_V56Chapter8ResearchAgent):
    """V56 research plus explicit official-file/PDF ingestion."""

    def ingest_official_files(
        self,
        ticker: str,
        files: Iterable[Mapping[str, Any] | Any],
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_files: int = 12,
    ):
        return OfficialFileIngestionAgent(self.raw_dir / "official_file_v57").ingest(
            ticker,
            files,
            existing_candidates=existing_candidates,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_files=max_files,
        )


__all__ = ["Chapter8ResearchAgent", "Chapter8ResearchResult"]
