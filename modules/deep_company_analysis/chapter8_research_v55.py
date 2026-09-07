from __future__ import annotations

"""Chapter 8 V55 wrapper: V54 deep retrieval plus official archive/history pass.

The production page continues to use the same compatibility import and one analyst workspace.
V55 only expands evidence retrieval. It never promotes candidates, writes analyst conclusions,
creates manager identities, or emits management/investment scores or BUY/HOLD/SELL.
"""

from typing import Any

import pandas as pd

from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    build_question_coverage_summary,
)
from modules.deep_company_analysis.chapter8_official_archive_retrieval import OfficialArchiveRetrievalAgent
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import (
    ATTEMPT_COLUMNS,
    CANDIDATE_COLUMNS,
    Chapter8ResearchResult,
)
from modules.deep_company_analysis.chapter8_research_v54 import Chapter8ResearchAgent as _V54Chapter8ResearchAgent


class Chapter8ResearchAgent(_V54Chapter8ResearchAgent):
    """Run V54 research, then search historical company/exchange/regulator archives."""

    def search(
        self,
        ticker: str,
        company_name: str = "",
        *,
        chapter7_payload: dict[str, Any] | None = None,
        max_results_per_query: int = 2,
        max_official_documents: int = 18,
        max_gap_targets: int = 12,
        max_gap_results_per_query: int = 1,
        max_deep_targets: int = 48,
        max_deep_index_pages: int = 12,
        max_deep_documents: int = 24,
        max_deep_depth: int = 2,
        max_archive_targets: int = 48,
        max_archive_queries: int = 18,
        max_archive_results_per_query: int = 2,
        max_archive_documents: int = 14,
    ) -> Chapter8ResearchResult:
        result = super().search(
            ticker,
            company_name,
            chapter7_payload=chapter7_payload,
            max_results_per_query=max_results_per_query,
            max_official_documents=max_official_documents,
            max_gap_targets=max_gap_targets,
            max_gap_results_per_query=max_gap_results_per_query,
            max_deep_targets=max_deep_targets,
            max_deep_index_pages=max_deep_index_pages,
            max_deep_documents=max_deep_documents,
            max_deep_depth=max_deep_depth,
        )

        before_summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_before = int(before_summary["Dimensions Open"].sum()) if not before_summary.empty else 0

        archive = OfficialArchiveRetrievalAgent(self.raw_dir / "official_archive_v55").search(
            ticker,
            company_name,
            existing_candidates=result.candidates,
            manager_reference=result.manager_reference,
            max_targets=max_archive_targets,
            max_queries=max_archive_queries,
            max_results_per_query=max_archive_results_per_query,
            max_documents=max_archive_documents,
        )
        result.candidates = archive.merged_candidates
        result.quality = archive.quality
        result.gaps = archive.remaining_gaps

        base_attempts = (
            result.source_attempts
            if isinstance(result.source_attempts, pd.DataFrame)
            else pd.DataFrame(columns=ATTEMPT_COLUMNS)
        )
        archive_attempts = (
            archive.source_attempts
            if isinstance(archive.source_attempts, pd.DataFrame)
            else pd.DataFrame(columns=ATTEMPT_COLUMNS)
        )
        result.source_attempts = pd.concat([base_attempts, archive_attempts], ignore_index=True)
        if not result.source_attempts.empty:
            subset = [column for column in ("URL", "Method", "Status") if column in result.source_attempts.columns]
            if subset:
                result.source_attempts = result.source_attempts.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)

        after_summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_after = int(after_summary["Dimensions Open"].sum()) if not after_summary.empty else 0
        suffix = (
            f"Phase 8J official archive pass: source-locked open dimensions {open_before} -> {open_after}. "
            f"{archive.note}"
        )
        result.note = f"{result.note} | {suffix}" if result.note else suffix

        # Diagnostics for CI acceptance and offline artifacts; production UI may ignore them.
        result.official_archive_targets = archive.targets  # type: ignore[attr-defined]
        result.official_archive_query_plan = archive.query_plan  # type: ignore[attr-defined]
        result.official_archive_search_results = archive.search_results  # type: ignore[attr-defined]
        result.official_archive_source_attempts = archive.source_attempts  # type: ignore[attr-defined]
        result.official_archive_documents = archive.documents  # type: ignore[attr-defined]
        result.official_archive_new_candidates = archive.new_candidates  # type: ignore[attr-defined]
        result.official_archive_before_coverage = archive.before_coverage  # type: ignore[attr-defined]
        result.official_archive_after_coverage = archive.after_coverage  # type: ignore[attr-defined]
        return result


def dimension_coverage_for_result(result: Chapter8ResearchResult):
    return build_dimension_coverage(result.candidates)


def question_coverage_for_result(result: Chapter8ResearchResult):
    return build_question_coverage_summary(result.candidates, result.manager_reference)


__all__ = [
    "CANDIDATE_COLUMNS",
    "Chapter8ResearchAgent",
    "Chapter8ResearchResult",
    "dimension_coverage_for_result",
    "question_coverage_for_result",
]
