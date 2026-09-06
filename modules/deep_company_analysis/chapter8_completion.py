from __future__ import annotations

"""Chapter 8 Phase 8F — final source closure and research-completion gate.

The gate measures whether the analyst has closed the research workflow for Q39-Q47.
It deliberately does not judge management quality and cannot change valuation, MOS,
Research Gate, or BUY/HOLD/SELL.
"""

from typing import Any

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_data_bridge import (
    CANONICAL_SOURCE_LABEL,
    MANAGER_SOURCE_LABEL,
)


CLOSED_QUESTION_STATUSES = {"Answered", "N/A"}
CLOSED_GAP_STATUSES = {"closed", "done", "resolved", "completed", "n/a"}
SOURCE_LOCKED_CAPITAL_ALLOCATION_ACTIONS = (
    "Reinvest in business / new projects",
    "Hold cash",
    "Pay dividends",
    "Buy back stock",
    "Make acquisitions",
)


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _table(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    return pd.DataFrame(_rows(value))


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return str(value).strip() not in {"", "Unknown", "None", "nan"}


def _question_from_row(row: dict[str, Any]) -> str:
    question = str(row.get("Question") or "").strip().upper()
    return question if question in ch8.QUESTION_KEYS else ""


def _is_open_gap(row: dict[str, Any]) -> bool:
    return str(row.get("Status") or "").strip().casefold() not in CLOSED_GAP_STATUSES


def _evidence_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = {q: 0 for q in ch8.QUESTION_KEYS}
    for row in _rows(payload.get("evidence")):
        question = _question_from_row(row)
        if question:
            counts[question] += 1
    return counts


def _open_gap_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = {q: 0 for q in ch8.QUESTION_KEYS}
    for row in _rows(payload.get("research_gaps")):
        if not _is_open_gap(row):
            continue
        question = _question_from_row(row)
        if question:
            counts[question] += 1
    return counts


def _q43_dimension_coverage(payload: dict[str, Any]) -> tuple[int, int]:
    expected = {key for key, _ in ch8.EMPLOYEE_RELATION_DIMENSIONS}
    covered: set[str] = set()
    for row in _rows(payload.get("q43_employee_relations")):
        key = str(row.get("Dimension Key") or "").strip()
        if key not in expected:
            continue
        if any(
            _nonempty(row.get(field))
            for field in (
                "Supporting Evidence",
                "Counter-Evidence",
                "Metric / Observation",
                "Source",
            )
        ):
            covered.add(key)
    return len(covered), len(expected)


def _structured_availability(structured_context: dict[str, Any] | None) -> dict[str, bool]:
    ctx = structured_context if isinstance(structured_context, dict) else {}
    return {
        "Q41": not _table(ctx.get("q41_guidance_history")).empty,
        "Q45": not _table(ctx.get("q45_cost_context")).empty,
        "Q46": not _table(ctx.get("q46_capital_allocation_context")).empty,
        "Q47": not _table(ctx.get("q47_buyback_context")).empty,
    }


def _q47_explicit_buyback_available(structured_context: dict[str, Any] | None) -> bool:
    ctx = structured_context if isinstance(structured_context, dict) else {}
    frame = _table(ctx.get("q47_buyback_context"))
    if frame.empty:
        return False
    if "Explicit buyback field available?" in frame.columns:
        return frame["Explicit buyback field available?"].astype(str).str.casefold().eq("yes").any()
    return False


def build_source_closure_table(
    payload: dict[str, Any] | None,
    *,
    structured_context: dict[str, Any] | None = None,
    chapter7_payload: dict[str, Any] | None = None,
) -> pd.DataFrame:
    data = ch8.normalize_payload(payload or {})
    statuses = data.get("question_status") or {}
    assessments = data.get("analyst_assessment") or {}
    confidence = data.get("confidence") or {}
    evidence_counts = _evidence_counts(data)
    gap_counts = _open_gap_counts(data)
    structured = _structured_availability(structured_context)

    manager_profiles = _rows((chapter7_payload or {}).get("management_profiles"))
    manager_linked = any(
        _nonempty(row.get("Manager ID")) or _nonempty(row.get("Manager"))
        for row in manager_profiles
    )

    q43_covered, q43_total = _q43_dimension_coverage(data)
    q46_lock_ok = tuple(ch8.CAPITAL_ALLOCATION_ACTIONS) == SOURCE_LOCKED_CAPITAL_ALLOCATION_ACTIONS
    q47_explicit = _q47_explicit_buyback_available(structured_context)

    rows: list[dict[str, Any]] = []
    for q in ch8.QUESTION_KEYS:
        status = str(statuses.get(q) or "Unknown")
        assessment_present = _nonempty(assessments.get(q))
        evidence_count = int(evidence_counts[q])
        open_gaps = int(gap_counts[q])

        special = ""
        if q in structured:
            special = "Structured context available" if structured[q] else "Structured context missing"
        if q == "Q43":
            special = f"Employee dimensions evidenced: {q43_covered}/{q43_total}"
        elif q == "Q46":
            special = (
                f"Shearn 5-action source lock: {'PASS' if q46_lock_ok else 'FAIL'}; "
                f"structured context: {'available' if structured['Q46'] else 'missing'}"
            )
        elif q == "Q47":
            special = (
                f"Explicit buyback field in canonical context: {'available' if q47_explicit else 'not established'}; "
                "share-count decline alone is not evidence"
            )
        elif q in {"Q39", "Q40", "Q42", "Q43", "Q44"}:
            special = f"Chapter 7 manager identity link: {'available' if manager_linked else 'not supplied'}"

        blockers: list[str] = []
        if status not in CLOSED_QUESTION_STATUSES:
            blockers.append("Question status remains open")
        if status == "Answered" and not assessment_present:
            blockers.append("Answered without analyst assessment")
        if status == "Answered" and evidence_count == 0:
            blockers.append("Answered without promoted/manual evidence")
        if open_gaps > 0:
            blockers.append(f"{open_gaps} open research gap(s)")
        if q == "Q46" and not q46_lock_ok:
            blockers.append("Q46 source lock mismatch")

        rows.append(
            {
                "Question": q,
                "Question Title": ch8.QUESTION_TITLES[q],
                "Research Status": status,
                "Confidence": str(confidence.get(q) or "Unknown"),
                "Analyst Assessment Present": "Yes" if assessment_present else "No",
                "Promoted / Manual Evidence": evidence_count,
                "Open Research Gaps": open_gaps,
                "Source Closure Note": special,
                "Completion State": "Closed" if not blockers else "Open",
                "Blocking Reason": "; ".join(blockers),
            }
        )
    return pd.DataFrame(rows)


def build_completion_gate(
    payload: dict[str, Any] | None,
    *,
    structured_context: dict[str, Any] | None = None,
    chapter7_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    table = build_source_closure_table(
        payload,
        structured_context=structured_context,
        chapter7_payload=chapter7_payload,
    )
    closed = table.loc[table["Completion State"].eq("Closed"), "Question"].astype(str).tolist()
    open_questions = table.loc[table["Completion State"].eq("Open"), "Question"].astype(str).tolist()
    q43_covered, q43_total = _q43_dimension_coverage(ch8.normalize_payload(payload or {}))
    structured = _structured_availability(structured_context)
    q46_lock_ok = tuple(ch8.CAPITAL_ALLOCATION_ACTIONS) == SOURCE_LOCKED_CAPITAL_ALLOCATION_ACTIONS

    manager_profiles = _rows((chapter7_payload or {}).get("management_profiles"))
    manager_reference_rows = sum(
        1
        for row in manager_profiles
        if _nonempty(row.get("Manager ID")) or _nonempty(row.get("Manager"))
    )

    return {
        "gate_name": "Chapter 8 Research Completion Gate",
        "ready_for_chapter_close": len(open_questions) == 0 and q46_lock_ok,
        "closed_questions": closed,
        "open_questions": open_questions,
        "closed_count": len(closed),
        "total_questions": len(ch8.QUESTION_KEYS),
        "q43_dimensions_evidenced": q43_covered,
        "q43_dimensions_total": q43_total,
        "q46_source_lock_ok": q46_lock_ok,
        "q47_explicit_buyback_field_available": _q47_explicit_buyback_available(structured_context),
        "structured_context_available": structured,
        "manager_reference_rows": manager_reference_rows,
        "manager_ssot": MANAGER_SOURCE_LABEL,
        "financial_ssot": CANONICAL_SOURCE_LABEL,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "gate_boundary": (
            "Research completeness only — analyst owns management-quality conclusions; "
            "no MOS/valuation/Research Gate/BUY-HOLD-SELL mutation."
        ),
        "table": table,
    }


def completion_gate_text(gate: dict[str, Any]) -> str:
    if bool(gate.get("ready_for_chapter_close")):
        return "READY — Q39–Q47 research workflow is closed; this is not a management-quality rating."
    open_questions = ", ".join(str(x) for x in gate.get("open_questions") or []) or "Unknown"
    return f"OPEN — research completion still required for: {open_questions}."


__all__ = [
    "CLOSED_QUESTION_STATUSES",
    "CLOSED_GAP_STATUSES",
    "SOURCE_LOCKED_CAPITAL_ALLOCATION_ACTIONS",
    "build_source_closure_table",
    "build_completion_gate",
    "completion_gate_text",
]
