from __future__ import annotations

"""Chapter 8 V61 research wrapper: V60 plus section-directed official document expansion."""

from pathlib import Path
from typing import Iterable

import pandas as pd

from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import Chapter8ResearchResult
from modules.deep_company_analysis.chapter8_research_v60 import Chapter8ResearchAgent as _V60Chapter8ResearchAgent
from modules.deep_company_analysis.chapter8_section_directed_retrieval_v61 import SectionDirectedRetrievalAgentV61


class Chapter8ResearchAgent(_V60Chapter8ResearchAgent):
    """V60 research plus bounded archive/document expansion targeted by open management gaps."""

    def retrieve_section_directed_official_documents(
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
    ):
        agent = SectionDirectedRetrievalAgentV61(self.raw_dir / "section_retrieval_v61")
        result = agent.run(
            ticker,
            existing_candidates=existing_candidates,
            manager_reference=manager_reference,
            target_keys=target_keys,
            seed_urls=seed_urls,
            max_targets=max_targets,
            max_documents=max_documents,
            max_files=max_files,
            max_scanned_ocr_docs=max_scanned_ocr_docs,
            year_floor=year_floor,
        )
        self.last_section_retrieval_plan = result.section_plan
        self.last_section_discovery = result.discovery
        self.last_section_downloads = result.downloads
        self.last_section_ocr_diagnostics = getattr(agent, "last_ocr_diagnostics", pd.DataFrame())
        return result


__all__ = ["Chapter8ResearchAgent", "Chapter8ResearchResult"]
