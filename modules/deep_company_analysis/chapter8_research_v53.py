from __future__ import annotations

"""Chapter 8 V53 research wrapper: dimension-gap audit plus gap-directed second pass.

V53 preserves the Phase 8C candidate workflow and Phase 8G source-locks, then uses only
open source-locked dimensions to run a bounded second research pass. Nothing is promoted
or concluded automatically; the analyst remains the decision owner.
"""

from typing import Any

import pandas as pd

from modules.deep_company_analysis.chapter8_gap_directed_research import (
    GapDirectedResearchAgent,
    quality_after_gap_directed,
)
from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    build_question_coverage_summary,
    enhanced_research_gaps,
)
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import (
    CANDIDATE_COLUMNS,
    Chapter8ResearchAgent as _BaseChapter8ResearchAgent,
    Chapter8ResearchResult,
)


class Chapter8ResearchAgent(_BaseChapter8ResearchAgent):
    """Base research plus V52 gap audit plus V53 gap-directed research."""

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
    ) -> Chapter8ResearchResult:
        result = super().search(
            ticker,
            company_name,
            chapter7_payload=chapter7_payload,
            max_results_per_query=max_results_per_query,
            max_official_documents=max_official_documents,
        )

        # Phase 8G baseline gap audit before the targeted pass.
        result.gaps = enhanced_research_gaps(result.candidates, result.manager_reference)
        baseline_summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_before = int(baseline_summary["Dimensions Open"].sum()) if not baseline_summary.empty else 0

        directed = GapDirectedResearchAgent(str(self.raw_dir / "gap_directed_v53")).search(
            ticker,
            company_name,
            existing_candidates=result.candidates,
            manager_reference=result.manager_reference,
            max_targets=max_gap_targets,
            max_results_per_query=max_gap_results_per_query,
        )
        result.candidates = directed.merged_candidates
        result.quality = quality_after_gap_directed(directed)
        result.gaps = directed.remaining_gaps
        result.raw_paths = list(dict.fromkeys([*result.raw_paths, *directed.raw_paths]))

        after_summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_after = int(after_summary["Dimensions Open"].sum()) if not after_summary.empty else 0
        manager_gap_count = int(
            result.gaps.get("Status", pd.Series(dtype="object")).astype(str).str.contains("manager", case=False).sum()
        ) if isinstance(result.gaps, pd.DataFrame) and not result.gaps.empty else 0
        suffix = (
            f"Phase 8H targeted pass: source-locked open dimensions {open_before} -> {open_after}; "
            f"manager identity/scope gaps remaining={manager_gap_count}. {directed.note}"
        )
        result.note = f"{result.note} | {suffix}" if result.note else suffix

        # Extra diagnostics are attached for QA/artifact export; the existing UI can ignore them safely.
        result.gap_directed_targets = directed.targets  # type: ignore[attr-defined]
        result.gap_directed_query_log = directed.query_log  # type: ignore[attr-defined]
        result.gap_directed_new_candidates = directed.new_candidates  # type: ignore[attr-defined]
        result.gap_directed_before_coverage = directed.before_coverage  # type: ignore[attr-defined]
        result.gap_directed_after_coverage = directed.after_coverage  # type: ignore[attr-defined]
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
