from __future__ import annotations

"""Pure Chapter 8 workspace transforms used by the Streamlit UI and tests."""

from copy import deepcopy
from typing import Any

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8


def _direction(value: Any) -> str:
    text = str(value or "").strip().casefold()
    if text.startswith("supporting"):
        return "Supporting"
    if text.startswith("counter"):
        return "Counter"
    if text.startswith("mixed"):
        return "Mixed"
    if text.startswith("neutral"):
        return "Neutral"
    return "Unknown"


def _candidate_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("Question") or "").strip(),
        str(row.get("Manager ID") or "").strip(),
        str(row.get("Source URL / File") or "").strip(),
        str(row.get("Evidence Text / Reference") or "").strip(),
    )


def candidate_to_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """Map a manually promoted Phase 8C candidate into the Chapter 8 evidence matrix."""
    return {
        "Question": str(row.get("Question") or "").strip(),
        "Manager ID": str(row.get("Manager ID") or "").strip(),
        "Manager": str(row.get("Manager") or "").strip(),
        "Claim": str(row.get("Subtopic") or row.get("Source Title") or "").strip(),
        "Evidence Type": "Phase 8C research candidate promoted by analyst",
        "Source Grade": str(row.get("Source Grade") or "").strip(),
        "Source Title": str(row.get("Source Title") or "").strip(),
        "Source URL / File": str(row.get("Source URL / File") or "").strip(),
        "Source Date": str(row.get("Source Date") or "").strip(),
        "As-of Date": str(row.get("As-of Date") or "").strip(),
        "Evidence Text / Reference": str(row.get("Evidence Text / Reference") or "").strip(),
        "Direction": _direction(row.get("Direction")),
        "Status": "Promoted — analyst verified",
        "Data Origin": str(row.get("Data Origin") or "External research candidate").strip(),
        "Analyst Note": "",
    }


def promote_selected_candidates(
    payload: dict[str, Any], candidates: pd.DataFrame | list[dict[str, Any]]
) -> tuple[dict[str, Any], int]:
    """Promote selected rows without touching analyst assessments/status/confidence."""
    out = ch8.normalize_payload(deepcopy(payload or {}))
    if isinstance(candidates, pd.DataFrame):
        rows = candidates.to_dict("records")
    elif isinstance(candidates, list):
        rows = [dict(x) for x in candidates if isinstance(x, dict)]
    else:
        rows = []

    existing = [dict(x) for x in out.get("evidence", []) if isinstance(x, dict)]
    keys = {_candidate_key(x) for x in existing}
    added = 0
    for row in rows:
        if not bool(row.get("Select")):
            continue
        mapped = candidate_to_evidence(row)
        key = _candidate_key(mapped)
        if key in keys:
            continue
        existing.append(mapped)
        keys.add(key)
        added += 1
    out["evidence"] = existing
    return out, added


def _gap_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("Question") or "").strip(),
        str(row.get("Manager ID") or "").strip(),
        str(row.get("Research Gap") or "").strip(),
        str(row.get("Status") or "").strip(),
    )


def merge_research_gaps(
    payload: dict[str, Any], gaps: pd.DataFrame | list[dict[str, Any]]
) -> tuple[dict[str, Any], int]:
    """Merge machine-found gaps while preserving any analyst-edited existing row."""
    out = ch8.normalize_payload(deepcopy(payload or {}))
    if isinstance(gaps, pd.DataFrame):
        incoming = gaps.to_dict("records")
    elif isinstance(gaps, list):
        incoming = [dict(x) for x in gaps if isinstance(x, dict)]
    else:
        incoming = []

    existing = [dict(x) for x in out.get("research_gaps", []) if isinstance(x, dict)]
    keys = {_gap_key(x) for x in existing}
    added = 0
    for row in incoming:
        normalized = {column: row.get(column, "") for column in ch8.RESEARCH_GAP_COLUMNS}
        key = _gap_key(normalized)
        if key in keys:
            continue
        existing.append(normalized)
        keys.add(key)
        added += 1
    out["research_gaps"] = existing
    return out, added


__all__ = [
    "candidate_to_evidence",
    "promote_selected_candidates",
    "merge_research_gaps",
]
