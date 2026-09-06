from __future__ import annotations

"""Chapter 8 Phase 8H — gap-directed research engine.

This module takes the dimension/subtopic gaps produced by Phase 8G and turns them into
bounded, target-specific web research. It is intentionally a research assistant only:
- it never promotes evidence automatically;
- it never writes analyst conclusions/status/confidence;
- it never creates manager identities outside the Chapter 7 manager master;
- it never creates a management score or investment signal.

The target planner only schedules source-locked dimensions that remain open. Q46's
hurdle/discipline row stays context-only and is never counted as a sixth Shearn action.
Q47 still requires explicit buyback evidence; share-count decline is not proof.
"""

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Any, Iterable

import pandas as pd

from adapters.module2_web_research import KNOWN_COMPANY_DOMAINS, WebEvidenceAgent
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_gap_engine import (
    BOUNDARY,
    MANAGER_SCOPED_QUESTIONS,
    QUESTION_DIMENSIONS,
    build_dimension_coverage,
    enhanced_research_gaps,
)
from modules.deep_company_analysis.chapter8_research import (
    CANDIDATE_COLUMNS,
    direction_cue,
    evidence_quality_summary,
    source_grade_from_url,
)


TARGET_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Gap Type",
    "Manager Scope Required",
    "Manager Scope Mode",
    "Query Terms",
    "Next Action",
    "Boundary",
]

QUERY_LOG_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Queries",
    "Manager Scope Mode",
    "Candidates Found",
    "Raw Path",
    "Status",
]


@dataclass
class GapDirectedResearchResult:
    targets: pd.DataFrame
    query_log: pd.DataFrame
    new_candidates: pd.DataFrame
    merged_candidates: pd.DataFrame
    before_coverage: pd.DataFrame
    after_coverage: pd.DataFrame
    remaining_gaps: pd.DataFrame
    raw_paths: list[str]
    note: str


def _safe(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _year_candidate(text: str) -> str:
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", str(text or ""))
    return years[-1] if years else ""


def _candidate_id(*parts: Any) -> str:
    payload = "\x1f".join(_safe(x) for x in parts)
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _manager_reference_rows(manager_reference: pd.DataFrame | None) -> list[tuple[str, str]]:
    if not isinstance(manager_reference, pd.DataFrame) or manager_reference.empty:
        return []
    rows: list[tuple[str, str]] = []
    for _, row in manager_reference.iterrows():
        manager_id = _safe(row.get("Manager ID"))
        manager = _safe(row.get("Manager"))
        if manager:
            rows.append((manager_id, manager))
    return rows


def _manager_match(text: str, manager_reference: pd.DataFrame | None) -> tuple[str, str]:
    low = _safe(text).casefold()
    for manager_id, manager in sorted(_manager_reference_rows(manager_reference), key=lambda x: len(x[1]), reverse=True):
        if manager.casefold() in low:
            return manager_id, manager
    return "", ""


def _dimension_lookup(question: str, dimension_key: str):
    for dimension in QUESTION_DIMENSIONS.get(str(question), ()):  # pragma: no branch - tiny bounded tuple
        if dimension.key == dimension_key:
            return dimension
    return None


def _open_source_locked_rows(candidates: pd.DataFrame) -> pd.DataFrame:
    coverage = build_dimension_coverage(candidates)
    if coverage.empty:
        return coverage
    return coverage[
        coverage["Source Locked"].eq("Yes")
        & ~coverage["Coverage Status"].eq("Candidate coverage — analyst verify")
    ].copy()


def _round_robin_targets(open_rows: pd.DataFrame, max_targets: int) -> pd.DataFrame:
    if open_rows.empty or max_targets <= 0:
        return open_rows.iloc[0:0].copy()
    buckets: dict[str, list[dict[str, Any]]] = {}
    for question in ch8.QUESTION_KEYS:
        qrows = open_rows[open_rows["Question"].astype(str).eq(question)].copy()
        qrows = qrows.sort_values(["Candidates", "Dimension Key"], ascending=[True, True])
        buckets[question] = qrows.to_dict("records")

    selected: list[dict[str, Any]] = []
    while len(selected) < max_targets and any(buckets.values()):
        for question in ch8.QUESTION_KEYS:
            if len(selected) >= max_targets:
                break
            if buckets.get(question):
                selected.append(buckets[question].pop(0))
    return pd.DataFrame(selected)


def build_gap_targets(
    candidates: pd.DataFrame,
    manager_reference: pd.DataFrame | None = None,
    *,
    max_targets: int = 12,
) -> pd.DataFrame:
    """Plan a bounded set of open source-locked dimensions, spread across Q39-Q47."""
    max_targets = max(0, min(int(max_targets), 36))
    open_rows = _open_source_locked_rows(candidates)
    planned = _round_robin_targets(open_rows, max_targets)
    if planned.empty:
        return pd.DataFrame(columns=TARGET_COLUMNS)

    manager_rows = _manager_reference_rows(manager_reference)
    rows: list[dict[str, Any]] = []
    for _, row in planned.iterrows():
        question = _safe(row.get("Question"))
        key = _safe(row.get("Dimension Key"))
        dimension = _dimension_lookup(question, key)
        if dimension is None or not dimension.source_locked:
            continue
        manager_required = question in MANAGER_SCOPED_QUESTIONS
        if not manager_required:
            manager_mode = "Not required"
        elif manager_rows:
            manager_mode = "Confirmed Chapter 7 managers included"
        else:
            manager_mode = "General target only — Chapter 7 manager identity unresolved"
        gap_type = "Evidence gap" if int(row.get("Candidates") or 0) == 0 else "Source-quality gap"
        rows.append({
            "Question": question,
            "Dimension Key": key,
            "Dimension": dimension.label,
            "Gap Type": gap_type,
            "Manager Scope Required": manager_required,
            "Manager Scope Mode": manager_mode,
            "Query Terms": " | ".join(dimension.terms[:6]),
            "Next Action": dimension.next_action,
            "Boundary": BOUNDARY,
        })
    return pd.DataFrame(rows, columns=TARGET_COLUMNS)


def _query_terms(terms: Iterable[str], *, limit: int = 4) -> str:
    chosen: list[str] = []
    for term in terms:
        clean = _safe(term)
        if clean and clean.casefold() not in {x.casefold() for x in chosen}:
            chosen.append(clean)
        if len(chosen) >= limit:
            break
    return " ".join(f'"{term}"' if " " in term else term for term in chosen)


def build_target_queries(
    ticker: str,
    company_name: str,
    target: dict[str, Any] | pd.Series,
    manager_reference: pd.DataFrame | None = None,
) -> list[str]:
    """Build at most two focused queries for one open dimension."""
    symbol = _safe(ticker).upper()
    question = _safe(target.get("Question"))
    key = _safe(target.get("Dimension Key"))
    dimension = _dimension_lookup(question, key)
    if not symbol or dimension is None or not dimension.source_locked:
        return []

    clean_company = WebEvidenceAgent._clean_company_name(company_name)
    name = clean_company or _safe(company_name) or symbol
    term_clause = _query_terms(dimension.terms)
    manager_names = [name for _, name in _manager_reference_rows(manager_reference)]
    manager_clause = ""
    if question in MANAGER_SCOPED_QUESTIONS and manager_names:
        manager_clause = " " + " ".join(f'"{x}"' for x in manager_names[:2])

    domains: list[str] = []
    for root in KNOWN_COMPANY_DOMAINS.get(symbol, []):
        domain = WebEvidenceAgent._domain(root)
        if domain and domain not in domains:
            domains.append(domain)

    queries: list[str] = []
    if domains:
        queries.append(f'site:{domains[0]} "{symbol}" {term_clause}')
    queries.append(f'"{symbol}" "{name}"{manager_clause} {term_clause}')
    return list(dict.fromkeys(q for q in queries if q.strip()))[:2]


class _GapTargetAgent(WebEvidenceAgent):
    def __init__(self, raw_dir: str, queries: list[str]):
        super().__init__(raw_dir)
        self._queries = list(queries)

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # noqa: ARG002
        return self._queries


def target_rows_to_candidates(
    raw: pd.DataFrame,
    ticker: str,
    target: dict[str, Any] | pd.Series,
    manager_reference: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Convert only rows that explicitly match the planned dimension into candidates."""
    question = _safe(target.get("Question"))
    key = _safe(target.get("Dimension Key"))
    dimension = _dimension_lookup(question, key)
    if dimension is None or not dimension.source_locked or not isinstance(raw, pd.DataFrame) or raw.empty:
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)

    rows: list[dict[str, Any]] = []
    for _, item in raw.iterrows():
        status = _safe(item.get("Trạng thái"))
        if status != "Tìm thấy":
            continue
        title = _safe(item.get("Tiêu đề"))
        snippet = _safe(item.get("Trích yếu"))
        url = _safe(item.get("Nguồn/URL"))
        text = _safe(f"{title} {snippet}")
        low = text.casefold()
        if not text or not any(term.casefold() in low for term in dimension.terms):
            continue
        manager_id, manager = _manager_match(text, manager_reference)
        rows.append({
            "Select": False,
            "Candidate ID": _candidate_id(question, key, manager_id, url, title, snippet),
            "Question": question,
            "Manager ID": manager_id,
            "Manager": manager,
            "Subtopic": dimension.label,
            "Direction": direction_cue(text),
            "Source Grade": source_grade_from_url(url, ticker),
            "Explicitness": "Gap-directed title/snippet candidate — analyst verify",
            "Source Title": title[:240],
            "Source URL / File": url,
            "Source Date": "",
            "As-of Date": _year_candidate(text),
            "Evidence Text / Reference": snippet[:900],
            "Source Method": f"Phase 8H gap-directed research — {key}",
            "Data Origin": "Gap-directed external research candidate — analyst verification required",
            "Status": "Candidate — analyst verify",
        })
    frame = pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
    if frame.empty:
        return frame
    return frame.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)


def _merge_candidates(existing: pd.DataFrame, new_candidates: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    left = existing.copy() if isinstance(existing, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    right = new_candidates.copy() if isinstance(new_candidates, pd.DataFrame) else pd.DataFrame(columns=CANDIDATE_COLUMNS)
    for frame in (left, right):
        for column in CANDIDATE_COLUMNS:
            if column not in frame.columns:
                frame[column] = None
    before = set(left.get("Candidate ID", pd.Series(dtype="object")).fillna("").astype(str))
    merged = pd.concat([left[CANDIDATE_COLUMNS], right[CANDIDATE_COLUMNS]], ignore_index=True)
    if not merged.empty:
        merged = merged.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
    after = set(merged.get("Candidate ID", pd.Series(dtype="object")).fillna("").astype(str))
    return merged, len(after - before)


def _open_count(coverage: pd.DataFrame) -> int:
    if not isinstance(coverage, pd.DataFrame) or coverage.empty:
        return 0
    mask = coverage["Source Locked"].eq("Yes") & ~coverage["Coverage Status"].eq("Candidate coverage — analyst verify")
    return int(mask.sum())


class GapDirectedResearchAgent:
    def __init__(self, raw_dir: str):
        self.raw_dir = str(raw_dir)

    def search(
        self,
        ticker: str,
        company_name: str,
        *,
        existing_candidates: pd.DataFrame,
        manager_reference: pd.DataFrame | None = None,
        max_targets: int = 12,
        max_results_per_query: int = 1,
    ) -> GapDirectedResearchResult:
        before = build_dimension_coverage(existing_candidates)
        targets = build_gap_targets(existing_candidates, manager_reference, max_targets=max_targets)
        pieces: list[pd.DataFrame] = []
        logs: list[dict[str, Any]] = []
        raw_paths: list[str] = []

        for _, target in targets.iterrows():
            queries = build_target_queries(ticker, company_name, target, manager_reference)
            if not queries:
                logs.append({
                    "Question": target["Question"],
                    "Dimension Key": target["Dimension Key"],
                    "Dimension": target["Dimension"],
                    "Queries": "",
                    "Manager Scope Mode": target["Manager Scope Mode"],
                    "Candidates Found": 0,
                    "Raw Path": "",
                    "Status": "Skipped — no valid targeted query",
                })
                continue
            try:
                agent = _GapTargetAgent(self.raw_dir, queries)
                result = agent.search(ticker, company_name, max_results_per_query=max(1, int(max_results_per_query)))
                candidates = target_rows_to_candidates(result.table, ticker, target, manager_reference)
                if not candidates.empty:
                    pieces.append(candidates)
                raw_path = str(result.raw_path) if result.raw_path else ""
                if raw_path:
                    raw_paths.append(raw_path)
                logs.append({
                    "Question": target["Question"],
                    "Dimension Key": target["Dimension Key"],
                    "Dimension": target["Dimension"],
                    "Queries": " || ".join(queries),
                    "Manager Scope Mode": target["Manager Scope Mode"],
                    "Candidates Found": int(len(candidates)),
                    "Raw Path": raw_path,
                    "Status": "Attempted — analyst verify results",
                })
            except Exception as exc:
                logs.append({
                    "Question": target["Question"],
                    "Dimension Key": target["Dimension Key"],
                    "Dimension": target["Dimension"],
                    "Queries": " || ".join(queries),
                    "Manager Scope Mode": target["Manager Scope Mode"],
                    "Candidates Found": 0,
                    "Raw Path": "",
                    "Status": f"Failed safely: {exc}",
                })

        new_candidates = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=CANDIDATE_COLUMNS)
        if not new_candidates.empty:
            new_candidates = new_candidates.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
        merged, added = _merge_candidates(existing_candidates, new_candidates)
        after = build_dimension_coverage(merged)
        remaining = enhanced_research_gaps(merged, manager_reference)
        before_open = _open_count(before)
        after_open = _open_count(after)
        query_log = pd.DataFrame(logs, columns=QUERY_LOG_COLUMNS)
        note = (
            f"Phase 8H gap-directed research: planned {len(targets)} open source-locked dimensions; "
            f"attempted {int(query_log['Status'].astype(str).str.startswith('Attempted').sum()) if not query_log.empty else 0}; "
            f"added {added} unique candidate(s); open dimensions {before_open} -> {after_open}. "
            "Candidates still require analyst verification/promotion; no management score or investment signal is produced."
        )
        return GapDirectedResearchResult(
            targets=targets,
            query_log=query_log,
            new_candidates=new_candidates,
            merged_candidates=merged,
            before_coverage=before,
            after_coverage=after,
            remaining_gaps=remaining,
            raw_paths=raw_paths,
            note=note,
        )


def quality_after_gap_directed(result: GapDirectedResearchResult) -> pd.DataFrame:
    return evidence_quality_summary(result.merged_candidates)


__all__ = [
    "GapDirectedResearchAgent",
    "GapDirectedResearchResult",
    "QUERY_LOG_COLUMNS",
    "TARGET_COLUMNS",
    "build_gap_targets",
    "build_target_queries",
    "quality_after_gap_directed",
    "target_rows_to_candidates",
]
