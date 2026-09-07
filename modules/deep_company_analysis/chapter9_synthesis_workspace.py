from __future__ import annotations

"""Chapter 9 Phase 9J–9K — analyst-owned Chapters 7–9 management synthesis workspace.

This layer stores the analyst's own cross-chapter synthesis after the Phase 9I read-only handoff.
It deliberately does not generate management-quality scores, character classifications, investment
signals, MOS changes, investment Research Gates, portfolio sizing, or BUY/HOLD/SELL conclusions.

The only derived automation in this module is source fingerprinting. A fingerprint tells the analyst
whether the saved Q33–Q52 synthesis was based on the same underlying research package as the current
one. Source drift never rewrites, invalidates, downgrades, or re-classifies the analyst's conclusion.
Phase 9K adds audit fields for an explicit analyst re-review action; it never auto-accepts source drift.
"""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import json

import pandas as pd


SYNTHESIS_WORKSPACE_BOUNDARY = (
    "Analyst-owned management synthesis only — source fingerprints detect research changes; "
    "they do not create a Management Quality Score, character classification, investment signal, "
    "MOS change, investment Research Gate, portfolio sizing, or BUY/HOLD/SELL."
)

WORKSPACE_STATUS_OPTIONS = ("Draft", "Reviewed", "Finalized")
ANALYST_CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
SOURCE_SECTION_KEYS = (
    "question_ledger",
    "manager_roster",
    "evidence_ledger",
    "research_gap_ledger",
    "chapter_readiness",
    "lineage_warning_table",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_ticker(value: Any) -> str:
    return "".join(ch for ch in _text(value).upper() if ch.isalnum() or ch in {".", "-"})[:20]


def _jsonable(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        records = [_jsonable(row) for row in value.where(pd.notna(value), None).to_dict("records")]
        return sorted(records, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))
    if isinstance(value, dict):
        return {str(key): _jsonable(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        items = [_jsonable(item) for item in value]
        if all(isinstance(item, dict) for item in items):
            return sorted(items, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))
        return items
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _digest(value: Any) -> str:
    payload = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(payload.encode("utf-8")).hexdigest()


def empty_synthesis_workspace(ticker: str = "", company_name: str = "") -> dict[str, Any]:
    return {
        "schema_version": 2,
        "ticker": _safe_ticker(ticker),
        "company_name": _text(company_name),
        "workspace_status": "Draft",
        "analyst_confidence": "Unknown",
        "chapter7_background_takeaway": "",
        "chapter8_operating_takeaway": "",
        "chapter9_traits_takeaway": "",
        "management_strengths": "",
        "management_concerns": "",
        "management_unknowns": "",
        "evidence_that_would_change_view": "",
        "final_management_synthesis": "",
        "analyst_note": "",
        "source_fingerprint": "",
        "source_section_fingerprints": {},
        "source_counts": {},
        "source_handoff_state": "",
        "source_captured_at": "",
        "analyst_reviewed_at": "",
        "last_re_review_at": "",
        "last_re_review_note": "",
        "last_re_review_sections": [],
        "boundary": SYNTHESIS_WORKSPACE_BOUNDARY,
    }


def normalize_synthesis_workspace(
    workspace: dict[str, Any] | None,
    ticker: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    base = empty_synthesis_workspace(ticker or str((workspace or {}).get("ticker") or ""), company_name)
    if isinstance(workspace, dict):
        for key in base:
            if key in workspace:
                base[key] = deepcopy(workspace[key])
    base["schema_version"] = 2
    base["ticker"] = _safe_ticker(ticker or base.get("ticker"))
    if company_name:
        base["company_name"] = _text(company_name)
    else:
        base["company_name"] = _text(base.get("company_name"))
    if base.get("workspace_status") not in WORKSPACE_STATUS_OPTIONS:
        base["workspace_status"] = "Draft"
    if base.get("analyst_confidence") not in ANALYST_CONFIDENCE_OPTIONS:
        base["analyst_confidence"] = "Unknown"
    if not isinstance(base.get("source_section_fingerprints"), dict):
        base["source_section_fingerprints"] = {}
    if not isinstance(base.get("source_counts"), dict):
        base["source_counts"] = {}
    if not isinstance(base.get("last_re_review_sections"), list):
        base["last_re_review_sections"] = []
    base["boundary"] = SYNTHESIS_WORKSPACE_BOUNDARY
    return base


def build_source_signature(handoff: dict[str, Any] | None) -> dict[str, Any]:
    """Create stable fingerprints for the Phase 9I handoff without changing source payloads."""
    data = handoff if isinstance(handoff, dict) else {}
    section_fingerprints = {key: _digest(data.get(key)) for key in SOURCE_SECTION_KEYS}
    counts = {
        "total_questions": int(data.get("total_questions") or 0),
        "manager_count": int(data.get("manager_count") or 0),
        "evidence_rows": int(data.get("evidence_rows") or 0),
        "research_gaps_total": int(data.get("research_gaps_total") or 0),
        "research_gaps_open": int(data.get("research_gaps_open") or 0),
        "lineage_warnings": int(data.get("lineage_warnings") or 0),
    }
    overall_payload = {
        "source_question_range": _text(data.get("source_question_range")),
        "manager_identity_ssot": _text(data.get("manager_identity_ssot")),
        "handoff_state": _text(data.get("handoff_state")),
        "ready_for_analyst_synthesis": bool(data.get("ready_for_analyst_synthesis")),
        "section_fingerprints": section_fingerprints,
        "counts": counts,
    }
    return {
        "fingerprint": _digest(overall_payload),
        "section_fingerprints": section_fingerprints,
        "counts": counts,
        "handoff_state": _text(data.get("handoff_state")),
        "ready_for_analyst_synthesis": bool(data.get("ready_for_analyst_synthesis")),
        "manager_identity_ssot": _text(data.get("manager_identity_ssot")),
        "source_question_range": _text(data.get("source_question_range")),
    }


def source_drift_status(
    saved_workspace: dict[str, Any] | None,
    current_handoff: dict[str, Any] | None,
) -> dict[str, Any]:
    saved = normalize_synthesis_workspace(saved_workspace or {})
    current = build_source_signature(current_handoff)
    saved_fingerprint = _text(saved.get("source_fingerprint"))
    saved_sections = saved.get("source_section_fingerprints") if isinstance(saved.get("source_section_fingerprints"), dict) else {}

    if not saved_fingerprint:
        status = "No baseline — save synthesis to capture Q33–Q52 source state"
        changed_sections = list(SOURCE_SECTION_KEYS)
        changed = False
    else:
        changed_sections = [
            key for key in SOURCE_SECTION_KEYS
            if _text(saved_sections.get(key)) != _text(current["section_fingerprints"].get(key))
        ]
        changed = saved_fingerprint != current["fingerprint"]
        status = "Changed — analyst review required" if changed else "Unchanged — synthesis source baseline current"

    return {
        "status": status,
        "changed": changed,
        "changed_sections": changed_sections,
        "saved_fingerprint": saved_fingerprint,
        "current_fingerprint": current["fingerprint"],
        "current_signature": current,
        "automatic_workspace_status_change": False,
        "automatic_analyst_text_change": False,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "boundary": SYNTHESIS_WORKSPACE_BOUNDARY,
    }


def capture_source_baseline(
    workspace: dict[str, Any] | None,
    handoff: dict[str, Any] | None,
    *,
    mark_reviewed: bool = False,
) -> dict[str, Any]:
    """Copy only source fingerprints/counts into the analyst workspace; never rewrite conclusions."""
    out = normalize_synthesis_workspace(workspace or {})
    signature = build_source_signature(handoff)
    out["source_fingerprint"] = signature["fingerprint"]
    out["source_section_fingerprints"] = deepcopy(signature["section_fingerprints"])
    out["source_counts"] = deepcopy(signature["counts"])
    out["source_handoff_state"] = signature["handoff_state"]
    out["source_captured_at"] = _now()
    if mark_reviewed:
        out["analyst_reviewed_at"] = _now()
    return out


def synthesis_workspace_summary(
    workspace: dict[str, Any] | None,
    current_handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = normalize_synthesis_workspace(workspace or {})
    drift = source_drift_status(data, current_handoff or {}) if current_handoff is not None else None
    text_fields = (
        "chapter7_background_takeaway",
        "chapter8_operating_takeaway",
        "chapter9_traits_takeaway",
        "management_strengths",
        "management_concerns",
        "management_unknowns",
        "evidence_that_would_change_view",
        "final_management_synthesis",
    )
    completed = sum(1 for key in text_fields if _text(data.get(key)))
    return {
        "workspace_status": data["workspace_status"],
        "analyst_confidence": data["analyst_confidence"],
        "completed_text_sections": completed,
        "total_text_sections": len(text_fields),
        "source_baseline_captured": bool(_text(data.get("source_fingerprint"))),
        "source_drift_status": drift["status"] if drift else "Not checked",
        "source_changed": bool(drift and drift["changed"]),
        "changed_sections": list(drift["changed_sections"]) if drift else [],
        "last_re_review_at": _text(data.get("last_re_review_at")),
        "last_re_review_note": _text(data.get("last_re_review_note")),
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
    }


def build_synthesis_report_frame(
    workspace: dict[str, Any] | None,
    current_handoff: dict[str, Any] | None = None,
) -> pd.DataFrame:
    data = normalize_synthesis_workspace(workspace or {})
    summary = synthesis_workspace_summary(data, current_handoff)
    return pd.DataFrame([
        {
            "Workspace Status": data["workspace_status"],
            "Analyst Confidence": data["analyst_confidence"],
            "Source Freshness": summary["source_drift_status"],
            "Chapter 7 Background Takeaway": data["chapter7_background_takeaway"],
            "Chapter 8 Operating Takeaway": data["chapter8_operating_takeaway"],
            "Chapter 9 Traits Takeaway": data["chapter9_traits_takeaway"],
            "Management Strengths": data["management_strengths"],
            "Management Concerns": data["management_concerns"],
            "Management Unknowns": data["management_unknowns"],
            "Evidence That Would Change View": data["evidence_that_would_change_view"],
            "Final Analyst Management Synthesis": data["final_management_synthesis"],
            "Analyst Note": data["analyst_note"],
            "Source Captured At": data["source_captured_at"],
            "Analyst Reviewed At": data["analyst_reviewed_at"],
            "Last Re-review At": data["last_re_review_at"],
            "Last Re-review Note": data["last_re_review_note"],
            "Boundary": SYNTHESIS_WORKSPACE_BOUNDARY,
        }
    ])


__all__ = [
    "ANALYST_CONFIDENCE_OPTIONS",
    "SOURCE_SECTION_KEYS",
    "SYNTHESIS_WORKSPACE_BOUNDARY",
    "WORKSPACE_STATUS_OPTIONS",
    "build_source_signature",
    "build_synthesis_report_frame",
    "capture_source_baseline",
    "empty_synthesis_workspace",
    "normalize_synthesis_workspace",
    "source_drift_status",
    "synthesis_workspace_summary",
]
