from __future__ import annotations

"""Chapter 9 Phase 9E — analyst-owned evidence workspace transforms.

This module mirrors the established Chapter 8 workspace pattern while preserving the
stricter Chapter 9 source/manager boundaries introduced in Phases 9A–9D.

Research Assistant output is *candidate evidence*. Only an explicit analyst selection can
promote a candidate into the persisted Chapter 9 Evidence Matrix. Promotion never changes
Analyst Assessment, Research Status, Confidence, a management score, MOS, Research Gate, or
BUY/HOLD/SELL.
"""

from copy import deepcopy
from hashlib import sha256
from typing import Any

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


RESEARCH_BOUNDARY = (
    "Analyst-owned workspace only — research candidates require explicit promotion; no automatic "
    "management/character conclusion, score/rank, MOS/Research Gate, or BUY/HOLD/SELL."
)

# Kept separate from ch9.EVIDENCE_COLUMNS so the Phase 9A source contract stays unchanged.
# V66 adds provenance/lineage fields needed for reliable promotion and later UI rendering.
WORKSPACE_EVIDENCE_COLUMNS = [
    "Candidate ID",
    "Question",
    "Dimension Key",
    "Dimension",
    "Manager ID",
    "Manager",
    "Current Role",
    "Observation / Claim",
    "Evidence Type",
    "Source Family",
    "Source Grade",
    "Explicitness",
    "Source Title",
    "Source URL / File",
    "Source Date",
    "As-of Date",
    "Evidence Text / Reference",
    "Direction",
    "Research Direction Cue",
    "Source Method",
    "Data Origin",
    "Status",
    "Analyst Note",
]


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _direction(value: Any) -> str:
    text = _safe_text(value).casefold()
    if text.startswith("supporting"):
        return "Supporting"
    if text.startswith("counter"):
        return "Counter"
    if text.startswith("mixed"):
        return "Mixed"
    if text.startswith("neutral") or text.startswith("context"):
        return "Neutral"
    return "Unknown"


def _dimension_map() -> dict[str, contract.SourceDimension]:
    return {item.key: item for item in contract.all_dimensions()}


def _candidate_fallback_id(row: dict[str, Any]) -> str:
    payload = "\x1f".join(
        _safe_text(row.get(key))
        for key in (
            "Question",
            "Dimension Key",
            "Manager ID",
            "Source URL / File",
            "Evidence Text / Reference",
        )
    )
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _evidence_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        _safe_text(row.get("Candidate ID")),
        _safe_text(row.get("Question")),
        _safe_text(row.get("Dimension Key")),
        _safe_text(row.get("Manager ID")),
        _safe_text(row.get("Source URL / File")),
    )


def _candidate_rows(candidates: pd.DataFrame | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(candidates, pd.DataFrame):
        return candidates.to_dict("records")
    if isinstance(candidates, list):
        return [dict(item) for item in candidates if isinstance(item, dict)]
    return []


def validate_candidate_for_promotion(
    row: dict[str, Any],
    chapter7_payload: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Validate source-dimension and manager identity lineage before analyst promotion.

    Blank manager IDs remain permissible for management-wide Q49–Q51 evidence. Q48/Q52 are
    CEO-specific and therefore require an explicit Chapter 7 CEO match before promotion.
    A nonblank Manager ID is never accepted unless it exists in the Chapter 7 manager master.
    """
    question = _safe_text(row.get("Question"))
    dimension_key = _safe_text(row.get("Dimension Key"))
    manager_id = _safe_text(row.get("Manager ID"))
    dim = _dimension_map().get(dimension_key)

    if question not in ch9.QUESTION_KEYS:
        return False, "Question is outside source-locked Q48-Q52."
    if dim is None or dim.question != question:
        return False, "Dimension Key does not belong to the source-locked question."
    if _safe_text(row.get("Status")) and not _safe_text(row.get("Status")).startswith("Candidate"):
        return False, "Only research candidates can use candidate promotion."

    context = bridge.build_context(chapter7_payload)
    managers = context.manager_reference
    known_ids = set(managers.get("Manager ID", pd.Series(dtype="object")).astype(str)) if not managers.empty else set()
    if manager_id and manager_id not in known_ids:
        return False, "Manager ID is not present in the Chapter 7 manager master."

    if question in bridge.CEO_QUESTIONS:
        scoped = context.dimension_scope
        ceo_ids = set(
            scoped.loc[
                scoped["Question"].eq(question) & scoped["Manager ID"].astype(str).str.len().gt(0),
                "Manager ID",
            ].astype(str)
        ) if not scoped.empty else set()
        if not manager_id:
            return False, "CEO-specific candidate has no exact Chapter 7 CEO link."
        if manager_id not in ceo_ids:
            return False, "CEO-specific candidate is not linked to an explicitly scoped Chapter 7 CEO."

    return True, "PASS"


def candidate_to_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """Map one analyst-selected Phase 9D candidate into a provenance-preserving evidence row."""
    candidate_id = _safe_text(row.get("Candidate ID")) or _candidate_fallback_id(row)
    cue = _safe_text(row.get("Direction"))
    return {
        "Candidate ID": candidate_id,
        "Question": _safe_text(row.get("Question")),
        "Dimension Key": _safe_text(row.get("Dimension Key")),
        "Dimension": _safe_text(row.get("Dimension")),
        "Manager ID": _safe_text(row.get("Manager ID")),
        "Manager": _safe_text(row.get("Manager")),
        "Current Role": _safe_text(row.get("Current Role")),
        "Observation / Claim": _safe_text(row.get("Dimension") or row.get("Source Title")),
        "Evidence Type": "Phase 9D research candidate promoted by analyst",
        "Source Family": _safe_text(row.get("Source Family")),
        "Source Grade": _safe_text(row.get("Source Grade")),
        "Explicitness": _safe_text(row.get("Explicitness")),
        "Source Title": _safe_text(row.get("Source Title")),
        "Source URL / File": _safe_text(row.get("Source URL / File")),
        "Source Date": _safe_text(row.get("Source Date")),
        "As-of Date": _safe_text(row.get("As-of Date")),
        "Evidence Text / Reference": _safe_text(row.get("Evidence Text / Reference")),
        "Direction": _direction(cue),
        "Research Direction Cue": cue,
        "Source Method": _safe_text(row.get("Source Method")),
        "Data Origin": _safe_text(row.get("Data Origin")) or "External research candidate",
        "Status": "Promoted — analyst verified",
        "Analyst Note": "",
    }


def promote_selected_candidates(
    payload: dict[str, Any],
    candidates: pd.DataFrame | list[dict[str, Any]],
    *,
    chapter7_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    """Promote selected, valid candidates without mutating candidates or analyst conclusions."""
    out = ch9.normalize_payload(deepcopy(payload or {}))
    existing = [dict(item) for item in out.get("evidence", []) if isinstance(item, dict)]
    keys = {_evidence_key(item) for item in existing}
    added = 0

    for row in _candidate_rows(candidates):
        if not bool(row.get("Select")):
            continue
        valid, _ = validate_candidate_for_promotion(row, chapter7_payload)
        if not valid:
            continue
        mapped = candidate_to_evidence(row)
        key = _evidence_key(mapped)
        if key in keys:
            continue
        existing.append(mapped)
        keys.add(key)
        added += 1

    out["evidence"] = existing
    return out, added


def _gap_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _safe_text(row.get("Question")),
        _safe_text(row.get("Dimension Key")),
        _safe_text(row.get("Research Gap")),
        _safe_text(row.get("Status")),
    )


def merge_research_gaps(
    payload: dict[str, Any],
    gaps: pd.DataFrame | list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    """Merge assistant-found gaps while preserving analyst-edited existing rows."""
    out = ch9.normalize_payload(deepcopy(payload or {}))
    incoming = gaps.to_dict("records") if isinstance(gaps, pd.DataFrame) else (
        [dict(item) for item in gaps if isinstance(item, dict)] if isinstance(gaps, list) else []
    )
    existing = [dict(item) for item in out.get("research_gaps", []) if isinstance(item, dict)]
    keys = {_gap_key(item) for item in existing}
    added = 0
    for row in incoming:
        normalized = {
            "Question": _safe_text(row.get("Question")),
            "Dimension Key": _safe_text(row.get("Dimension Key")),
            "Manager ID": _safe_text(row.get("Manager ID")),
            "Manager": _safe_text(row.get("Manager")),
            "Research Gap": _safe_text(row.get("Research Gap")),
            "Materiality": _safe_text(row.get("Materiality")),
            "Next Action": _safe_text(row.get("Next Action")),
            "Status": _safe_text(row.get("Status")),
            "Analyst Note": _safe_text(row.get("Analyst Note")),
        }
        key = _gap_key(normalized)
        if key in keys:
            continue
        existing.append(normalized)
        keys.add(key)
        added += 1
    out["research_gaps"] = existing
    return out, added


def workspace_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Return research-completeness metadata only; never a quality or investment score."""
    data = ch9.normalize_payload(deepcopy(payload or {}))
    statuses = data.get("question_status") or {}
    evidence = [item for item in data.get("evidence", []) if isinstance(item, dict)]
    gaps = [item for item in data.get("research_gaps", []) if isinstance(item, dict)]
    return {
        "question_count": len(ch9.QUESTION_KEYS),
        "answered": sum(1 for q in ch9.QUESTION_KEYS if statuses.get(q) == "Answered"),
        "partial": sum(1 for q in ch9.QUESTION_KEYS if statuses.get(q) == "Partial"),
        "unknown": sum(1 for q in ch9.QUESTION_KEYS if statuses.get(q) == "Unknown"),
        "promoted_evidence": sum(1 for item in evidence if _safe_text(item.get("Status")).startswith("Promoted")),
        "open_research_gaps": sum(1 for item in gaps if _safe_text(item.get("Status")).startswith("Open")),
        "source_dimension_count": len(contract.all_dimensions()),
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
    }


__all__ = [
    "RESEARCH_BOUNDARY",
    "WORKSPACE_EVIDENCE_COLUMNS",
    "candidate_to_evidence",
    "merge_research_gaps",
    "promote_selected_candidates",
    "validate_candidate_for_promotion",
    "workspace_snapshot",
]
