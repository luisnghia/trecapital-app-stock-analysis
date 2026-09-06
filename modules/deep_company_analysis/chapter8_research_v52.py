from __future__ import annotations

"""Chapter 8 V52 research wrapper with dimension/subtopic gap coverage.

The underlying search/candidate extraction remains Phase 8C. V52 only upgrades the research-gap
and coverage audit. It does not auto-promote candidates and does not write analyst conclusions.
"""

from typing import Any

from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import (
    Chapter8ResearchAgent as _BaseChapter8ResearchAgent,
    Chapter8ResearchResult,
)
from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    build_question_coverage_summary,
    enhanced_research_gaps,
)


class Chapter8ResearchAgent(_BaseChapter8ResearchAgent):
    """Phase 8C search plus V52 dimension-level coverage/gap analysis."""

    def search(
        self,
        ticker: str,
        company_name: str = "",
        *,
        chapter7_payload: dict[str, Any] | None = None,
        max_results_per_query: int = 2,
        max_official_documents: int = 18,
    ) -> Chapter8ResearchResult:
        result = super().search(
            ticker,
            company_name,
            chapter7_payload=chapter7_payload,
            max_results_per_query=max_results_per_query,
            max_official_documents=max_official_documents,
        )
        result.gaps = enhanced_research_gaps(result.candidates, result.manager_reference)
        summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_dimensions = int(summary["Dimensions Open"].sum()) if not summary.empty else 0
        if not result.gaps.empty and "Status" in result.gaps.columns:
            manager_open = int(
                result.gaps["Status"]
                .fillna("")
                .astype(str)
                .str.contains("manager", case=False)
                .groupby(result.gaps["Question"].astype(str))
                .any()
                .sum()
            )
        else:
            manager_open = 0
        suffix = (
            f"V52 coverage audit: {open_dimensions} source-locked dimensions remain open; "
            f"{manager_open} question(s) still have manager identity/scope gaps. "
            "Counts are research coverage only, not a management score."
        )
        result.note = f"{result.note} | {suffix}" if result.note else suffix
        return result


def dimension_coverage_for_result(result: Chapter8ResearchResult):
    return build_dimension_coverage(result.candidates)


def question_coverage_for_result(result: Chapter8ResearchResult):
    return build_question_coverage_summary(result.candidates, result.manager_reference)


__all__ = [
    "Chapter8ResearchAgent",
    "Chapter8ResearchResult",
    "dimension_coverage_for_result",
    "question_coverage_for_result",
]
