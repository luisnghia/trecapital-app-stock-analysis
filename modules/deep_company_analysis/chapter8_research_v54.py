from __future__ import annotations

"""Chapter 8 V54 research wrapper: V53 gap-directed pass plus official deep retrieval.

The existing production UI continues to import the compatibility module and therefore keeps
one analyst workspace/state store. V54 only expands evidence retrieval. It does not promote
candidates, write analyst conclusions, create manager identities, or emit investment signals.
"""

from typing import Any

import pandas as pd

from modules.deep_company_analysis.chapter8_gap_engine import (
    build_dimension_coverage,
    build_question_coverage_summary,
)
from modules.deep_company_analysis.chapter8_official_deep_retrieval import OfficialDeepRetrievalAgent
from modules.deep_company_analysis.chapter8_research import *  # noqa: F401,F403
from modules.deep_company_analysis.chapter8_research import (
    ATTEMPT_COLUMNS,
    CANDIDATE_COLUMNS,
    Chapter8ResearchResult,
)
from modules.deep_company_analysis.chapter8_research_v53 import Chapter8ResearchAgent as _V53Chapter8ResearchAgent


class Chapter8ResearchAgent(_V53Chapter8ResearchAgent):
    """Run V53 research, then mine official reports/disclosures for remaining dimensions."""

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
    ) -> Chapter8ResearchResult:
        result = super().search(
            ticker,
            company_name,
            chapter7_payload=chapter7_payload,
            max_results_per_query=max_results_per_query,
            max_official_documents=max_official_documents,
            max_gap_targets=max_gap_targets,
            max_gap_results_per_query=max_gap_results_per_query,
        )

        before_summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_before = int(before_summary["Dimensions Open"].sum()) if not before_summary.empty else 0

        deep = OfficialDeepRetrievalAgent(self.raw_dir / "official_deep_v54").search(
            ticker,
            existing_candidates=result.candidates,
            manager_reference=result.manager_reference,
            max_targets=max_deep_targets,
            max_index_pages=max_deep_index_pages,
            max_documents=max_deep_documents,
            max_depth=max_deep_depth,
        )
        result.candidates = deep.merged_candidates
        result.quality = deep.quality
        result.gaps = deep.remaining_gaps

        base_attempts = result.source_attempts if isinstance(result.source_attempts, pd.DataFrame) else pd.DataFrame(columns=ATTEMPT_COLUMNS)
        deep_attempts = deep.source_attempts if isinstance(deep.source_attempts, pd.DataFrame) else pd.DataFrame(columns=ATTEMPT_COLUMNS)
        result.source_attempts = pd.concat([base_attempts, deep_attempts], ignore_index=True)
        if not result.source_attempts.empty:
            result.source_attempts = result.source_attempts.drop_duplicates(
                subset=[column for column in ("URL", "Method", "Status") if column in result.source_attempts.columns],
                keep="first",
            ).reset_index(drop=True)

        after_summary = build_question_coverage_summary(result.candidates, result.manager_reference)
        open_after = int(after_summary["Dimensions Open"].sum()) if not after_summary.empty else 0
        suffix = (
            f"Phase 8I official deep retrieval: source-locked open dimensions {open_before} -> {open_after}. "
            f"{deep.note}"
        )
        result.note = f"{result.note} | {suffix}" if result.note else suffix

        # Diagnostics for acceptance/artifact export. The UI can ignore them safely.
        result.official_deep_targets = deep.targets  # type: ignore[attr-defined]
        result.official_deep_source_attempts = deep.source_attempts  # type: ignore[attr-defined]
        result.official_deep_documents = deep.documents  # type: ignore[attr-defined]
        result.official_deep_new_candidates = deep.new_candidates  # type: ignore[attr-defined]
        result.official_deep_before_coverage = deep.before_coverage  # type: ignore[attr-defined]
        result.official_deep_after_coverage = deep.after_coverage  # type: ignore[attr-defined]
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
