from __future__ import annotations

"""Chapter 9 Phase 9C — research-completion gate, never a management-quality rating."""

from typing import Any

import pandas as pd

from modules.deep_company_analysis import chapter9 as ch9
from modules.deep_company_analysis import chapter9_source_contract_v63 as v63
from modules.deep_company_analysis.chapter9_workspace_v64 import (
    CLOSED_DIMENSION_STATUSES,
    normalize_workspace_payload,
    validate_manager_scope,
)


CLOSED_QUESTION_STATUSES = {"Answered", "N/A"}
CLOSED_GAP_STATUSES = {"closed", "done", "resolved", "completed", "n/a"}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip() not in {"", "Unknown", "None", "nan"}


def _is_open_gap(row: dict[str, Any]) -> bool:
    return str(row.get("Status") or "").strip().casefold() not in CLOSED_GAP_STATUSES


def _dimension_has_evidence(row: dict[str, Any]) -> bool:
    return any(
        _nonempty(row.get(field))
        for field in ("Supporting Evidence", "Counter-Evidence", "Source")
    )


def _question_gap_counts(data: dict[str, Any]) -> dict[str, int]:
    counts = {q: 0 for q in ch9.QUESTION_KEYS}
    for row in _rows(data.get("research_gaps")):
        question = str(row.get("Question") or "").strip().upper()
        if question in counts and _is_open_gap(row):
            counts[question] += 1
    return counts


def build_source_closure_table(
    payload: dict[str, Any] | None,
    *,
    chapter7_payload: dict[str, Any] | None = None,
) -> pd.DataFrame:
    data = normalize_workspace_payload(payload)
    statuses = data.get("question_status") or {}
    assessments = data.get("analyst_assessment") or {}
    confidence = data.get("confidence") or {}
    gaps = _question_gap_counts(data)
    manager_issues = validate_manager_scope(data, chapter7_payload) if chapter7_payload is not None else []
    manager_issue_counts = {q: 0 for q in ch9.QUESTION_KEYS}
    for issue in manager_issues:
        q = str(issue.get("Question") or "")
        if q in manager_issue_counts:
            manager_issue_counts[q] += 1

    dimensions = data["dimension_evidence"]
    rows: list[dict[str, Any]] = []
    for q in ch9.QUESTION_KEYS:
        qdims = [row for row in dimensions if str(row.get("Question") or "") == q]
        closed_dims = [
            row
            for row in qdims
            if str(row.get("Evidence Status") or "").strip().casefold() in CLOSED_DIMENSION_STATUSES
        ]
        evidence_dims = [row for row in closed_dims if _dimension_has_evidence(row)]
        status = str(statuses.get(q) or "Unknown")
        assessment_present = _nonempty(assessments.get(q))
        open_dimensions = len(qdims) - len(closed_dims)
        blockers: list[str] = []

        if status not in CLOSED_QUESTION_STATUSES:
            blockers.append("Question status remains open")
        if status == "Answered" and not assessment_present:
            blockers.append("Answered without analyst assessment")
        if open_dimensions > 0:
            blockers.append(f"{open_dimensions} source-locked dimension(s) remain open")
        if status == "Answered" and len(evidence_dims) == 0:
            blockers.append("Answered without analyst-verified dimension evidence")
        if gaps[q] > 0:
            blockers.append(f"{gaps[q]} open research gap(s)")
        if manager_issue_counts[q] > 0:
            blockers.append(f"{manager_issue_counts[q]} Chapter 7 manager-link issue(s)")

        rows.append(
            {
                "Question": q,
                "Question Title": ch9.QUESTION_TITLES[q],
                "Research Status": status,
                "Confidence": str(confidence.get(q) or "Unknown"),
                "Analyst Assessment Present": "Yes" if assessment_present else "No",
                "Source-Locked Dimensions": len(qdims),
                "Closed Dimensions": len(closed_dims),
                "Dimensions With Evidence": len(evidence_dims),
                "Open Dimensions": open_dimensions,
                "Open Research Gaps": gaps[q],
                "Manager-Link Issues": manager_issue_counts[q],
                "Completion State": "Closed" if not blockers else "Open",
                "Blocking Reason": "; ".join(blockers),
            }
        )
    return pd.DataFrame(rows)


def build_completion_gate(
    payload: dict[str, Any] | None,
    *,
    chapter7_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = normalize_workspace_payload(payload)
    table = build_source_closure_table(data, chapter7_payload=chapter7_payload)
    closed = table.loc[table["Completion State"].eq("Closed"), "Question"].astype(str).tolist()
    open_questions = table.loc[table["Completion State"].eq("Open"), "Question"].astype(str).tolist()
    total_dimensions = len(data["dimension_evidence"])
    expected_dimensions = len(v63.all_dimensions())
    manager_issues = validate_manager_scope(data, chapter7_payload) if chapter7_payload is not None else []
    contract_ok = total_dimensions == expected_dimensions == 26

    return {
        "gate_name": "Chapter 9 Research Completion Gate",
        "ready_for_chapter_close": len(open_questions) == 0 and contract_ok and not manager_issues,
        "closed_questions": closed,
        "open_questions": open_questions,
        "closed_count": len(closed),
        "total_questions": len(ch9.QUESTION_KEYS),
        "source_locked_dimensions": total_dimensions,
        "expected_source_locked_dimensions": expected_dimensions,
        "source_contract_ok": contract_ok,
        "manager_link_issues": manager_issues,
        "manager_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "gate_boundary": (
            "Research completeness only — analyst owns all positive/negative trait conclusions; "
            "no valuation, MOS, Research Gate, or BUY/HOLD/SELL mutation."
        ),
        "table": table,
    }


def completion_gate_text(gate: dict[str, Any]) -> str:
    if bool(gate.get("ready_for_chapter_close")):
        return "READY — Q48–Q52 research workflow is closed; this is not a management-quality rating."
    open_questions = ", ".join(str(x) for x in gate.get("open_questions") or []) or "Unknown"
    return f"OPEN — Chapter 9 research completion still required for: {open_questions}."


__all__ = [
    "CLOSED_GAP_STATUSES",
    "CLOSED_QUESTION_STATUSES",
    "build_completion_gate",
    "build_source_closure_table",
    "completion_gate_text",
]
