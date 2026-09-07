from __future__ import annotations

"""Phase 9K — explicit re-review workflow for analyst-owned management synthesis.

This module translates the Phase 9J source fingerprint into a report/workflow state. It never
rewrites the analyst's text or status automatically. Accepting a new source baseline is an explicit
analyst action after reviewing the changed source sections. Source freshness is not a Management
Quality Score, character classification, investment signal, MOS change, investment Research Gate,
portfolio-sizing input, or BUY/HOLD/SELL recommendation.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    SOURCE_SECTION_KEYS,
    SYNTHESIS_WORKSPACE_BOUNDARY,
    capture_source_baseline,
    normalize_synthesis_workspace,
    source_drift_status,
)


SOURCE_REVIEW_CURRENT = "Current — analyst-reviewed baseline matches current Q33–Q52"
SOURCE_REVIEW_NEEDS_REREVIEW = "Needs Re-review — Q33–Q52 source research changed"
SOURCE_REVIEW_NO_BASELINE = "No Baseline — analyst review baseline not captured"

SECTION_LABELS = {
    "question_ledger": "Q33–Q52 Question Ledger",
    "manager_roster": "Chapter 7 Manager Roster",
    "evidence_ledger": "Cross-Chapter Evidence Ledger",
    "research_gap_ledger": "Research Gap Ledger",
    "chapter_readiness": "Chapter Research / Closure Readiness",
    "lineage_warning_table": "Manager Lineage Warnings",
}

RE_REVIEW_CHECKLIST_COLUMNS = [
    "Source Section",
    "Review State",
    "Saved Fingerprint",
    "Current Fingerprint",
    "Required Analyst Action",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def build_source_review_state(
    workspace: dict[str, Any] | None,
    current_handoff: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return report-safe source freshness without mutating analyst-owned fields."""
    data = normalize_synthesis_workspace(workspace or {})
    drift = source_drift_status(data, current_handoff or {})
    has_baseline = bool(_text(data.get("source_fingerprint")))
    if not has_baseline:
        state = SOURCE_REVIEW_NO_BASELINE
        report_label = "No baseline"
        needs_re_review = False
    elif drift["changed"]:
        state = SOURCE_REVIEW_NEEDS_REREVIEW
        report_label = "Needs Re-review"
        needs_re_review = True
    else:
        state = SOURCE_REVIEW_CURRENT
        report_label = "Current"
        needs_re_review = False
    return {
        "state": state,
        "report_label": report_label,
        "has_baseline": has_baseline,
        "needs_re_review": needs_re_review,
        "changed_sections": list(drift.get("changed_sections") or []),
        "saved_fingerprint": drift.get("saved_fingerprint") or "",
        "current_fingerprint": drift.get("current_fingerprint") or "",
        "last_re_review_at": _text(data.get("last_re_review_at")),
        "last_re_review_note": _text(data.get("last_re_review_note")),
        "last_re_review_sections": list(data.get("last_re_review_sections") or []),
        "automatic_workspace_status_change": False,
        "automatic_analyst_text_change": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "boundary": SYNTHESIS_WORKSPACE_BOUNDARY,
    }


def build_re_review_checklist(
    workspace: dict[str, Any] | None,
    current_handoff: dict[str, Any] | None,
) -> pd.DataFrame:
    data = normalize_synthesis_workspace(workspace or {})
    drift = source_drift_status(data, current_handoff or {})
    saved = data.get("source_section_fingerprints") if isinstance(data.get("source_section_fingerprints"), dict) else {}
    current = drift.get("current_signature", {}).get("section_fingerprints", {})
    changed = set(drift.get("changed_sections") or [])
    rows: list[dict[str, Any]] = []
    for key in SOURCE_SECTION_KEYS:
        is_changed = key in changed
        rows.append(
            {
                "Source Section": SECTION_LABELS.get(key, key),
                "Review State": "Changed — review required" if is_changed else "Unchanged",
                "Saved Fingerprint": _text(saved.get(key))[:16],
                "Current Fingerprint": _text(current.get(key))[:16],
                "Required Analyst Action": (
                    "Review the underlying saved Chapter 7–9 records before accepting a new baseline."
                    if is_changed
                    else "No additional action required for this source section."
                ),
            }
        )
    return pd.DataFrame(rows, columns=RE_REVIEW_CHECKLIST_COLUMNS)


def accept_current_source_after_re_review(
    workspace: dict[str, Any] | None,
    current_handoff: dict[str, Any] | None,
    *,
    analyst_review_note: str = "",
) -> dict[str, Any]:
    """Explicitly accept the current Q33–Q52 source package as the new reviewed baseline.

    The function returns a new workspace. It preserves all analyst synthesis text, status and
    confidence. Persistence remains the caller's responsibility.
    """
    before = normalize_synthesis_workspace(workspace or {})
    drift = source_drift_status(before, current_handoff or {})
    out = capture_source_baseline(deepcopy(before), current_handoff or {}, mark_reviewed=True)
    out["last_re_review_at"] = _now()
    out["last_re_review_note"] = _text(analyst_review_note)
    out["last_re_review_sections"] = list(drift.get("changed_sections") or [])
    return out


__all__ = [
    "RE_REVIEW_CHECKLIST_COLUMNS",
    "SECTION_LABELS",
    "SOURCE_REVIEW_CURRENT",
    "SOURCE_REVIEW_NEEDS_REREVIEW",
    "SOURCE_REVIEW_NO_BASELINE",
    "accept_current_source_after_re_review",
    "build_re_review_checklist",
    "build_source_review_state",
]
