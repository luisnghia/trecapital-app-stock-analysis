from __future__ import annotations

"""Chapter 9 Phase 9G — research-completion and source-coverage closure checks.

This module answers one process question only: is the Chapter 9 research record sufficiently
closed for the analyst to finish Q48-Q52? It does not evaluate whether management is good or bad.
It never writes Analyst Assessment, Confidence, Research Status, a management score, MOS,
Research Gate, or BUY/HOLD/SELL.

Source and app-design boundaries
--------------------------------
- The 26 Phase 9B source dimensions remain the complete Chapter 9 coverage contract.
- Chapter 7 remains the manager identity/role SSOT; Q48/Q52 still require an explicit CEO scope.
- Research Assistant output is not enough by itself: evidence must be analyst-promoted/verified,
  or a gap must be explicitly closed by the analyst as a documented known-unknown.
- Missing evidence remains missing. This module never fabricates a source or silently marks a gap
  complete because a search returned nothing.
- All outputs are coverage/readiness metadata, never management-quality or investment signals.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


APP_DIR = Path(__file__).resolve().parents[2]
LOG_PATH = APP_DIR / "data_cache" / "logs" / "deep_company_analysis_chapter9.log"

RESEARCH_COMPLETION_BOUNDARY = (
    "Research-completion gate only — measures source coverage and analyst closure; "
    "not a management-quality score, character classification, investment signal, MOS change, "
    "Research Gate, or BUY/HOLD/SELL."
)

DIMENSION_CLOSURE_COLUMNS = [
    "Question",
    "Dimension Key",
    "Dimension",
    "Manager Scope",
    "Evidence Rows",
    "Verified Evidence",
    "Source-Lineage Rows",
    "Open Gaps",
    "Closed Gaps",
    "Closure Status",
    "Closure Reason",
    "Next Action",
]

QUESTION_COMPLETION_COLUMNS = [
    "Question",
    "Question Title",
    "Source Dimensions",
    "Closed Dimensions",
    "Review Dimensions",
    "Open / Blocked Dimensions",
    "Research Status",
    "Analyst Confidence",
    "Analyst Assessment Present",
    "Completion Status",
    "Next Action",
]

CLOSED_GAP_STATUSES = {
    "closed",
    "done",
    "resolved",
    "completed",
    "n/a",
    "na",
    "closed — known unknown",
    "closed - known unknown",
    "closed — analyst accepted known unknown",
    "closed - analyst accepted known unknown",
}

VERIFIED_EVIDENCE_STATUS_PREFIXES = (
    "promoted",
    "verified",
    "confirmed",
    "accepted",
    "closed",
)


def _safe_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _status_key(value: Any) -> str:
    return _safe_text(value).casefold()


def _is_closed_gap(row: dict[str, Any]) -> bool:
    status = _status_key(row.get("Status"))
    return status in CLOSED_GAP_STATUSES or status.startswith("closed") or status.startswith("resolved")


def _is_verified_evidence(row: dict[str, Any]) -> bool:
    status = _status_key(row.get("Status"))
    return any(status.startswith(prefix) for prefix in VERIFIED_EVIDENCE_STATUS_PREFIXES)


def _has_source_lineage(row: dict[str, Any]) -> bool:
    source = _safe_text(row.get("Source URL / File") or row.get("Source"))
    reference = _safe_text(
        row.get("Evidence Text / Reference")
        or row.get("Observation / Claim")
        or row.get("Source Title")
    )
    return bool(source and reference)


def _manager_scope_status(question: str, context: bridge.Chapter9ContextResult) -> str:
    scope = context.dimension_scope
    if not isinstance(scope, pd.DataFrame) or scope.empty:
        return "Blocked — manager identity unavailable"
    sub = scope[scope["Question"].eq(question)]
    if sub.empty:
        return "Blocked — manager identity unavailable"
    if question in bridge.CEO_QUESTIONS:
        manager_ids = sub.get("Manager ID", pd.Series(dtype="object")).astype(str)
        if not manager_ids.str.len().gt(0).any():
            return "Blocked — explicit Chapter 7 CEO required"
    return "Scoped — Chapter 7 manager master"


def build_dimension_closure(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Build one coverage/closure row for every source-locked Chapter 9 dimension.

    A dimension is closed only by either analyst-verified evidence with usable source lineage,
    or an explicitly closed research gap. An empty search result is never treated as closure.
    """
    data = ch9.normalize_payload(payload or {})
    evidence = _rows(data.get("evidence"))
    gaps = _rows(data.get("research_gaps"))
    context = bridge.build_context(chapter7_payload)

    rows: list[dict[str, Any]] = []
    for dim in contract.all_dimensions():
        scope_status = _manager_scope_status(dim.question, context)
        dim_evidence = [
            row for row in evidence
            if _safe_text(row.get("Question")) == dim.question
            and _safe_text(row.get("Dimension Key")) == dim.key
        ]
        dim_gaps = [
            row for row in gaps
            if _safe_text(row.get("Question")) == dim.question
            and _safe_text(row.get("Dimension Key")) == dim.key
        ]
        verified = [row for row in dim_evidence if _is_verified_evidence(row)]
        lineage = [row for row in dim_evidence if _has_source_lineage(row)]
        verified_with_lineage = [
            row for row in dim_evidence if _is_verified_evidence(row) and _has_source_lineage(row)
        ]
        closed_gaps = [row for row in dim_gaps if _is_closed_gap(row)]
        open_gaps = [row for row in dim_gaps if not _is_closed_gap(row)]

        if scope_status.startswith("Blocked"):
            closure_status = "Blocked — manager scope"
            reason = scope_status
            next_action = "Confirm manager identity/role in Chapter 7 first; do not create a replacement Manager ID in Chapter 9."
        elif verified_with_lineage:
            closure_status = "Closed — verified evidence"
            reason = "At least one analyst-verified evidence row preserves both source and evidence/reference lineage."
            next_action = "No automatic action. Analyst may add counter-evidence or stronger corroboration if material."
        elif verified and not verified_with_lineage:
            closure_status = "Review — source lineage incomplete"
            reason = "Evidence is marked verified/promoted, but source URL/file or evidence/reference lineage is incomplete."
            next_action = "Complete the source and evidence/reference fields before treating the dimension as closed."
        elif dim_evidence:
            closure_status = "Review — evidence verification"
            reason = "Evidence exists, but no row is explicitly analyst-verified/promoted with usable lineage."
            next_action = "Open the source, verify context, and mark the evidence row as verified/promoted only after analyst review."
        elif open_gaps:
            closure_status = "Open — research gap"
            reason = "At least one research gap for this dimension remains open."
            next_action = "Follow the recorded Next Action, or explicitly close the gap as a documented known-unknown after analyst review."
        elif closed_gaps:
            closure_status = "Closed — analyst accepted known unknown"
            reason = "The analyst explicitly closed the documented research gap; no evidence is fabricated to fill it."
            next_action = "Retain the closed gap in the audit trail and reopen it if new material information appears."
        else:
            closure_status = "Open — no coverage"
            reason = "No dimension-linked verified evidence and no explicitly closed research gap is recorded."
            next_action = "Research this source dimension or record a specific research gap; do not infer an answer from missing evidence."

        rows.append(
            {
                "Question": dim.question,
                "Dimension Key": dim.key,
                "Dimension": dim.label,
                "Manager Scope": scope_status,
                "Evidence Rows": len(dim_evidence),
                "Verified Evidence": len(verified),
                "Source-Lineage Rows": len(lineage),
                "Open Gaps": len(open_gaps),
                "Closed Gaps": len(closed_gaps),
                "Closure Status": closure_status,
                "Closure Reason": reason,
                "Next Action": next_action,
            }
        )

    return pd.DataFrame(rows, columns=DIMENSION_CLOSURE_COLUMNS)


def build_question_completion(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Aggregate dimension closure to Q48-Q52 without scoring management quality."""
    data = ch9.normalize_payload(payload or {})
    closure = build_dimension_closure(data, chapter7_payload)
    rows: list[dict[str, Any]] = []

    for question in ch9.QUESTION_KEYS:
        sub = closure[closure["Question"].eq(question)]
        statuses = sub["Closure Status"].astype(str) if not sub.empty else pd.Series(dtype="object")
        closed = int(statuses.str.startswith("Closed").sum())
        review = int(statuses.str.startswith("Review").sum())
        open_or_blocked = int((statuses.str.startswith("Open") | statuses.str.startswith("Blocked")).sum())
        research_status = _safe_text((data.get("question_status") or {}).get(question)) or "Unknown"
        confidence = _safe_text((data.get("confidence") or {}).get(question)) or "Unknown"
        assessment = _safe_text((data.get("analyst_assessment") or {}).get(question))
        assessment_present = bool(assessment and assessment != "Unknown")

        if open_or_blocked:
            completion_status = "Blocked — research incomplete"
            next_action = "Close the open/blocked source dimensions first; missing evidence remains Unknown."
        elif review:
            completion_status = "Review — evidence/source verification required"
            next_action = "Resolve the remaining verification/source-lineage rows before closing the question."
        elif research_status not in {"Answered", "N/A"}:
            completion_status = "Review — analyst research status not closed"
            next_action = "Analyst decides whether the question is Answered or N/A; the app does not change Research Status automatically."
        elif confidence == "Unknown":
            completion_status = "Review — analyst confidence missing"
            next_action = "Analyst records confidence; the app does not infer confidence from evidence counts."
        elif not assessment_present:
            completion_status = "Review — analyst assessment missing"
            next_action = "Analyst writes the conclusion in Analyst Assessment; Research Assistant cannot write it."
        else:
            completion_status = "Ready — research closure complete"
            next_action = "No automatic action. Preserve snapshot/audit trail and reopen if new material evidence appears."

        rows.append(
            {
                "Question": question,
                "Question Title": ch9.QUESTION_TITLES[question],
                "Source Dimensions": len(sub),
                "Closed Dimensions": closed,
                "Review Dimensions": review,
                "Open / Blocked Dimensions": open_or_blocked,
                "Research Status": research_status,
                "Analyst Confidence": confidence,
                "Analyst Assessment Present": "Yes" if assessment_present else "No",
                "Completion Status": completion_status,
                "Next Action": next_action,
            }
        )

    return pd.DataFrame(rows, columns=QUESTION_COMPLETION_COLUMNS)


def completion_snapshot(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic research-readiness snapshot, explicitly not a quality score."""
    dimensions = build_dimension_closure(payload, chapter7_payload)
    questions = build_question_completion(payload, chapter7_payload)
    dim_status = dimensions["Closure Status"].astype(str)
    q_status = questions["Completion Status"].astype(str)

    if q_status.str.startswith("Blocked").any():
        gate = "Blocked — research incomplete"
    elif q_status.str.startswith("Review").any():
        gate = "Review — analyst closure required"
    else:
        gate = "Ready — research closure complete"

    return {
        "chapter": ch9.CHAPTER_NUMBER,
        "source_lock": ch9.SOURCE_LOCK,
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "source_dimension_count": len(dimensions),
        "closed_dimensions": int(dim_status.str.startswith("Closed").sum()),
        "review_dimensions": int(dim_status.str.startswith("Review").sum()),
        "open_dimensions": int(dim_status.str.startswith("Open").sum()),
        "blocked_dimensions": int(dim_status.str.startswith("Blocked").sum()),
        "ready_questions": int(q_status.str.startswith("Ready").sum()),
        "review_questions": int(q_status.str.startswith("Review").sum()),
        "blocked_questions": int(q_status.str.startswith("Blocked").sum()),
        "research_completion_gate": gate,
        "automatic_question_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_assessment": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
    }


def append_completion_log(ticker: str, event: str, details: dict[str, Any] | None = None) -> None:
    """Append a compact JSONL diagnostic log for Phase 9G runtime troubleshooting."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "module": "deep_company_analysis.chapter9_completion",
            "ticker": _safe_text(ticker).upper(),
            "event": _safe_text(event),
            "details": details or {},
        }
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        # Logging must never break the analyst workspace.
        pass


__all__ = [
    "CLOSED_GAP_STATUSES",
    "DIMENSION_CLOSURE_COLUMNS",
    "LOG_PATH",
    "QUESTION_COMPLETION_COLUMNS",
    "RESEARCH_COMPLETION_BOUNDARY",
    "VERIFIED_EVIDENCE_STATUS_PREFIXES",
    "append_completion_log",
    "build_dimension_closure",
    "build_question_completion",
    "completion_snapshot",
]
