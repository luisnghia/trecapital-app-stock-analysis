from __future__ import annotations

"""Chapter 8 V56 research wrapper: V55 archive pass plus optional direct official URL ingestion.

The normal automated Research Assistant behavior remains V55-compatible. Phase 8K direct URL
sources are ingested only when the analyst explicitly supplies URLs, so production research does
not depend on undocumented exchange APIs and does not silently crawl arbitrary sites.
"""

from typing import Any, Iterable

import pandas as pd

from modules.deep_company_analysis.chapter8_official_source_adapters import OfficialURLIngestionAgent
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchResult
from modules.deep_company_analysis.chapter8_research_v55 import Chapter8ResearchAgent as _V55Chapter8ResearchAgent


class Chapter8ResearchAgent(_V55Chapter8ResearchAgent):
    """V55 automated research plus an explicit official-URL ingestion entry point."""

    def ingest_official_urls(
        self,
        ticker: str,
        urls: str | Iterable[str],
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 48,
        max_urls: int = 20,
    ):
        return OfficialURLIngestionAgent(self.raw_dir / "official_url_v56").ingest(
            ticker,
            urls,
            existing_candidates=existing_candidates,
            manager_reference=manager_reference,
            max_targets=max_targets,
            max_urls=max_urls,
        )


__all__ = ["Chapter8ResearchAgent", "Chapter8ResearchResult"]
