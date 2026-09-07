from __future__ import annotations

"""Chapter 9 Phase 9I — cross-chapter management synthesis handoff for Chapters 7–9.

The handoff is deliberately descriptive. It assembles analyst-owned Chapter 7 background,
Chapter 8 operating-competence research, and Chapter 9 management-trait research into one
traceable package for review/reporting. It does not generate a management-quality score,
character classification, investment signal, MOS change, investment Research Gate, or
BUY/HOLD/SELL recommendation.

Boundaries
----------
- Chapter 7 manager master is the only manager identity/role source of truth.
- Chapter-specific Research Status, Confidence and Analyst Assessment/Conclusion are copied;
  this module never rewrites them.
- Evidence and research gaps preserve source-chapter lineage.
- Cross-chapter readiness means research handoff completeness only, never management quality.
- Unknown is a valid research state and is never interpreted as a negative trait.
"""

from copy import deepcopy
from typing import Any

import pandas as pd

import modules.deep_company_analysis.chapter7 as ch7
from modules.deep_company_analysis.chapter7_closure import chapter7_completion_status
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_completion import build_completion_gate as build_ch8_completion_gate
import modules.deep_company_analysis.chapter9 as ch9
from modules.deep_company_analysis.chapter9_completion import completion_snapshot as build_ch9_completion_snapshot


MANAGER_IDENTITY_SSOT = "Chapter 7 manager master"
SYNTHESIS_BOUNDARY = (
    "Cross-chapter management research handoff only — Chapters 7–9 remain analyst-owned; "
    "not a Management Quality Score, character classification, investment signal, MOS change, "
    "investment Research Gate, portfolio-sizing input, or BUY/HOLD/SELL."
)

CHAPTER7_QUESTION_TITLES: dict[str, str] = {
    "Q33": "What type of manager is leading the company?",
    "Q34": "Effects of bringing in outside management",
    "Q35": "Is the manager a lion or a hyena?",
    "Q36": "How did the manager rise to lead the business?",
    "Q37": "Compensation & ownership alignment",
    "Q38": "Have managers been buying or selling the stock?",
}

CHAPTER_READINESS_COLUMNS = [
    "Chapter",
    "Question Range",
    "Questions",
    "Research / Closure State",
    "Handoff State",
    "Open / Blocking Items",
    "Manager Identity Basis",
    "Boundary",
]

QUESTION_LEDGER_COLUMNS = [
    "Chapter",
    "Question",
    "Question Title",
    "Research Status",
    "Analyst Confidence",
    "Analyst Assessment / Conclusion",
    "Manager Scope",
]

MANAGER_ROSTER_COLUMNS = [
    "Manager ID",
    "Manager",
    "Current Role",
    "Founder?",
    "Joined Company",
    "Started Current Role",
    "Analyst Classification",
    "Confidence",
    "Identity Source",
]

EVIDENCE_LEDGER_COLUMNS = [
    "Chapter",
    "Question",
    "Manager ID",
    "Manager",
    "Claim / Observation",
    "Direction",
    "Status",
    "Source Grade",
    "Source Title",
    "Source URL / File",
    "Evidence Text / Reference",
    "Data Origin",
]

GAP_LEDGER_COLUMNS = [
    "Chapter",
    "Question",
    "Manager ID",
    "Manager",
    "Research Gap",
    "Materiality",
    "Next Action",
    "Status",
    "Analyst Note",
]

LINEAGE_WARNING_COLUMNS = [
    "Chapter",
    "Record Type",
    "Question",
    "Manager ID",
    "Manager",
    "Warning",
    "Required Action",
]


_CLOSED_GAP_PREFIXES = ("closed", "resolved", "done", "completed", "accepted", "n/a", "na")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def _is_open_gap(row: dict[str, Any]) -> bool:
    status = _text(row.get("Status")).casefold()
    if not status:
        return True
    return not any(status.startswith(prefix) for prefix in _CLOSED_GAP_PREFIXES)


def build_manager_roster(chapter7_payload: dict[str, Any] | None) -> pd.DataFrame:
    """Return the cross-chapter manager roster using Chapter 7 only.

    Chapter 8/9 evidence can reference this roster, but can never create or modify a manager.
    """
    rows: list[dict[str, Any]] = []
    for row in _rows((chapter7_payload or {}).get("management_profiles")):
        manager_id = _text(row.get("Manager ID"))
        manager = _text(row.get("Manager"))
        if not manager_id and not manager:
            continue
        rows.append(
            {
                "Manager ID": manager_id,
                "Manager": manager,
                "Current Role": _text(row.get("Current Role")),
                "Founder?": _text(row.get("Founder?")),
                "Joined Company": _text(row.get("Joined Company")),
                "Started Current Role": _text(row.get("Started Current Role")),
                "Analyst Classification": _text(row.get("Analyst Classification")) or "Unknown",
                "Confidence": _text(row.get("Confidence")) or "Unknown",
                "Identity Source": MANAGER_IDENTITY_SSOT,
            }
        )
    return _frame(rows, MANAGER_ROSTER_COLUMNS)


def _chapter7_question_ledger(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = payload if isinstance(payload, dict) else ch7.empty_payload()
    statuses = data.get("question_status") or {}
    rows: list[dict[str, Any]] = []
    for question in ch7.QUESTION_KEYS:
        qdata = data.get(question.casefold()) or {}
        conclusion = _text(qdata.get("conclusion")) or "Unknown"
        rows.append(
            {
                "Chapter": "Chapter 7",
                "Question": question,
                "Question Title": CHAPTER7_QUESTION_TITLES[question],
                "Research Status": _text(statuses.get(question)) or "Unknown",
                "Analyst Confidence": "Not recorded at question level",
                "Analyst Assessment / Conclusion": conclusion,
                "Manager Scope": MANAGER_IDENTITY_SSOT,
            }
        )
    return rows


def _chapter8_question_ledger(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = ch8.normalize_payload(payload or {})
    statuses = data.get("question_status") or {}
    confidence = data.get("confidence") or {}
    assessments = data.get("analyst_assessment") or {}
    return [
        {
            "Chapter": "Chapter 8",
            "Question": question,
            "Question Title": ch8.QUESTION_TITLES[question],
            "Research Status": _text(statuses.get(question)) or "Unknown",
            "Analyst Confidence": _text(confidence.get(question)) or "Unknown",
            "Analyst Assessment / Conclusion": _text(assessments.get(question)) or "Unknown",
            "Manager Scope": MANAGER_IDENTITY_SSOT,
        }
        for question in ch8.QUESTION_KEYS
    ]


def _chapter9_question_ledger(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = ch9.normalize_payload(payload or {})
    statuses = data.get("question_status") or {}
    confidence = data.get("confidence") or {}
    assessments = data.get("analyst_assessment") or {}
    return [
        {
            "Chapter": "Chapter 9",
            "Question": question,
            "Question Title": ch9.QUESTION_TITLES[question],
            "Research Status": _text(statuses.get(question)) or "Unknown",
            "Analyst Confidence": _text(confidence.get(question)) or "Unknown",
            "Analyst Assessment / Conclusion": _text(assessments.get(question)) or "Unknown",
            "Manager Scope": MANAGER_IDENTITY_SSOT,
        }
        for question in ch9.QUESTION_KEYS
    ]


def build_question_ledger(
    chapter7_payload: dict[str, Any] | None,
    chapter8_payload: dict[str, Any] | None,
    chapter9_payload: dict[str, Any] | None,
) -> pd.DataFrame:
    """Return all Q33-Q52 analyst-owned question states in source order."""
    rows = (
        _chapter7_question_ledger(chapter7_payload)
        + _chapter8_question_ledger(chapter8_payload)
        + _chapter9_question_ledger(chapter9_payload)
    )
    return pd.DataFrame(rows, columns=QUESTION_LEDGER_COLUMNS)


def _normalize_evidence_rows(chapter: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        question = _text(row.get("Question")).upper()
        if not question:
            continue
        normalized.append(
            {
                "Chapter": chapter,
                "Question": question,
                "Manager ID": _text(row.get("Manager ID")),
                "Manager": _text(row.get("Manager")),
                "Claim / Observation": _text(row.get("Claim") or row.get("Observation / Claim")),
                "Direction": _text(row.get("Direction")) or "Unknown",
                "Status": _text(row.get("Status")) or "Unknown",
                "Source Grade": _text(row.get("Source Grade")),
                "Source Title": _text(row.get("Source Title")),
                "Source URL / File": _text(row.get("Source URL / File") or row.get("Source")),
                "Evidence Text / Reference": _text(row.get("Evidence Text / Reference")),
                "Data Origin": _text(row.get("Data Origin")),
            }
        )
    return normalized


def build_evidence_ledger(
    chapter7_payload: dict[str, Any] | None,
    chapter8_payload: dict[str, Any] | None,
    chapter9_payload: dict[str, Any] | None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows += _normalize_evidence_rows("Chapter 7", _rows((chapter7_payload or {}).get("evidence_matrix")))
    rows += _normalize_evidence_rows("Chapter 8", _rows((chapter8_payload or {}).get("evidence")))
    rows += _normalize_evidence_rows("Chapter 9", _rows((chapter9_payload or {}).get("evidence")))
    return _frame(rows, EVIDENCE_LEDGER_COLUMNS)


def _normalize_gap_rows(chapter: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        question = _text(row.get("Question")).upper()
        if not question:
            continue
        normalized.append(
            {
                "Chapter": chapter,
                "Question": question,
                "Manager ID": _text(row.get("Manager ID")),
                "Manager": _text(row.get("Manager")),
                "Research Gap": _text(row.get("Research Gap")),
                "Materiality": _text(row.get("Materiality")),
                "Next Action": _text(row.get("Next Action")),
                "Status": _text(row.get("Status")) or "Open",
                "Analyst Note": _text(row.get("Analyst Note")),
            }
        )
    return normalized


def build_gap_ledger(
    chapter7_payload: dict[str, Any] | None,
    chapter8_payload: dict[str, Any] | None,
    chapter9_payload: dict[str, Any] | None,
    *,
    open_only: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows += _normalize_gap_rows("Chapter 7", _rows((chapter7_payload or {}).get("research_gaps_table")))
    rows += _normalize_gap_rows("Chapter 8", _rows((chapter8_payload or {}).get("research_gaps")))
    rows += _normalize_gap_rows("Chapter 9", _rows((chapter9_payload or {}).get("research_gaps")))
    if open_only:
        rows = [row for row in rows if _is_open_gap(row)]
    return _frame(rows, GAP_LEDGER_COLUMNS)


def build_lineage_warnings(
    chapter7_payload: dict[str, Any] | None,
    chapter8_payload: dict[str, Any] | None,
    chapter9_payload: dict[str, Any] | None,
) -> pd.DataFrame:
    """Flag manager references not present in Chapter 7 without creating replacement identities."""
    roster = build_manager_roster(chapter7_payload)
    valid_ids = {
        _text(value)
        for value in (roster["Manager ID"].tolist() if not roster.empty else [])
        if _text(value)
    }
    warnings: list[dict[str, Any]] = []
    evidence = build_evidence_ledger(chapter7_payload, chapter8_payload, chapter9_payload)
    gaps = build_gap_ledger(chapter7_payload, chapter8_payload, chapter9_payload)
    for record_type, frame in (("Evidence", evidence), ("Research Gap", gaps)):
        for row in frame.to_dict("records"):
            manager_id = _text(row.get("Manager ID"))
            if not manager_id or manager_id in valid_ids:
                continue
            warnings.append(
                {
                    "Chapter": _text(row.get("Chapter")),
                    "Record Type": record_type,
                    "Question": _text(row.get("Question")),
                    "Manager ID": manager_id,
                    "Manager": _text(row.get("Manager")),
                    "Warning": "Manager ID is not present in the Chapter 7 manager master.",
                    "Required Action": "Correct/link the manager in Chapter 7 first; do not create a replacement manager in Chapter 8/9.",
                }
            )
    return _frame(warnings, LINEAGE_WARNING_COLUMNS)


def _chapter7_readiness(payload: dict[str, Any] | None) -> tuple[str, str, int]:
    data = payload if isinstance(payload, dict) else ch7.empty_payload()
    result = chapter7_completion_status(
        data,
        open_conflicts=_rows(data.get("chapter7_closure_conflict_snapshot")),
        open_review_items=_rows(data.get("chapter7_closure_review_snapshot")),
    )
    blockers = list(result.get("blockers") or [])
    if bool(result.get("ready")) and bool(result.get("confirmed")):
        handoff = "Ready — analyst-confirmed research closure"
    elif bool(result.get("ready")):
        handoff = "Review — analyst confirmation required"
    else:
        handoff = "Open — Chapter 7 research incomplete"
    return str(result.get("status") or "Not Started"), handoff, len(blockers)


def _chapter8_readiness(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None,
    structured_context: dict[str, Any] | None,
) -> tuple[str, str, int]:
    gate = build_ch8_completion_gate(
        payload or {},
        structured_context=structured_context,
        chapter7_payload=chapter7_payload,
    )
    open_questions = list(gate.get("open_questions") or [])
    ready = bool(gate.get("ready_for_chapter_close"))
    return (
        "Ready — research closure complete" if ready else "Open — research closure incomplete",
        "Ready — research handoff complete" if ready else "Open — Chapter 8 research incomplete",
        len(open_questions),
    )


def _chapter9_readiness(
    payload: dict[str, Any] | None,
    chapter7_payload: dict[str, Any] | None,
) -> tuple[str, str, int]:
    snap = build_ch9_completion_snapshot(payload or {}, chapter7_payload)
    gate = _text(snap.get("research_completion_gate"))
    open_count = int(snap.get("review_questions", 0)) + int(snap.get("blocked_questions", 0))
    ready = gate.startswith("Ready")
    return gate, "Ready — research handoff complete" if ready else "Open — Chapter 9 research incomplete", open_count


def build_chapter_readiness(
    chapter7_payload: dict[str, Any] | None,
    chapter8_payload: dict[str, Any] | None,
    chapter9_payload: dict[str, Any] | None,
    *,
    chapter8_structured_context: dict[str, Any] | None = None,
) -> pd.DataFrame:
    ch7_state, ch7_handoff, ch7_open = _chapter7_readiness(chapter7_payload)
    ch8_state, ch8_handoff, ch8_open = _chapter8_readiness(
        chapter8_payload, chapter7_payload, chapter8_structured_context
    )
    ch9_state, ch9_handoff, ch9_open = _chapter9_readiness(chapter9_payload, chapter7_payload)
    rows = [
        {
            "Chapter": "Chapter 7",
            "Question Range": "Q33–Q38",
            "Questions": len(ch7.QUESTION_KEYS),
            "Research / Closure State": ch7_state,
            "Handoff State": ch7_handoff,
            "Open / Blocking Items": ch7_open,
            "Manager Identity Basis": MANAGER_IDENTITY_SSOT,
            "Boundary": "Background/classification research only",
        },
        {
            "Chapter": "Chapter 8",
            "Question Range": "Q39–Q47",
            "Questions": len(ch8.QUESTION_KEYS),
            "Research / Closure State": ch8_state,
            "Handoff State": ch8_handoff,
            "Open / Blocking Items": ch8_open,
            "Manager Identity Basis": MANAGER_IDENTITY_SSOT,
            "Boundary": "Operating-competence research only",
        },
        {
            "Chapter": "Chapter 9",
            "Question Range": "Q48–Q52",
            "Questions": len(ch9.QUESTION_KEYS),
            "Research / Closure State": ch9_state,
            "Handoff State": ch9_handoff,
            "Open / Blocking Items": ch9_open,
            "Manager Identity Basis": MANAGER_IDENTITY_SSOT,
            "Boundary": "Management-trait research only",
        },
    ]
    return pd.DataFrame(rows, columns=CHAPTER_READINESS_COLUMNS)


def build_management_handoff(
    chapter7_payload: dict[str, Any] | None,
    chapter8_payload: dict[str, Any] | None,
    chapter9_payload: dict[str, Any] | None,
    *,
    chapter8_structured_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the immutable/derived Chapters 7–9 research handoff package."""
    ch7_copy = deepcopy(chapter7_payload or {})
    ch8_copy = deepcopy(chapter8_payload or {})
    ch9_copy = deepcopy(chapter9_payload or {})

    readiness = build_chapter_readiness(
        ch7_copy,
        ch8_copy,
        ch9_copy,
        chapter8_structured_context=deepcopy(chapter8_structured_context or {}),
    )
    questions = build_question_ledger(ch7_copy, ch8_copy, ch9_copy)
    roster = build_manager_roster(ch7_copy)
    evidence = build_evidence_ledger(ch7_copy, ch8_copy, ch9_copy)
    gaps = build_gap_ledger(ch7_copy, ch8_copy, ch9_copy)
    open_gaps = build_gap_ledger(ch7_copy, ch8_copy, ch9_copy, open_only=True)
    warnings = build_lineage_warnings(ch7_copy, ch8_copy, ch9_copy)

    chapter_ready = readiness["Handoff State"].astype(str).str.startswith("Ready")
    overall_ready = bool(len(readiness) == 3 and chapter_ready.all() and warnings.empty)
    if overall_ready:
        handoff_state = "Ready — Chapters 7–9 research handoff complete"
    elif not warnings.empty:
        handoff_state = "Blocked — manager lineage reconciliation required"
    else:
        handoff_state = "Open — cross-chapter research closure incomplete"

    return {
        "handoff_name": "Management Synthesis Handoff — Chapters 7–9",
        "manager_identity_ssot": MANAGER_IDENTITY_SSOT,
        "source_question_range": "Q33–Q52",
        "total_questions": len(ch7.QUESTION_KEYS) + len(ch8.QUESTION_KEYS) + len(ch9.QUESTION_KEYS),
        "chapter_count": 3,
        "manager_count": len(roster),
        "evidence_rows": len(evidence),
        "research_gaps_total": len(gaps),
        "research_gaps_open": len(open_gaps),
        "lineage_warnings": len(warnings),
        "handoff_state": handoff_state,
        "ready_for_analyst_synthesis": overall_ready,
        "chapter_readiness": readiness,
        "question_ledger": questions,
        "manager_roster": roster,
        "evidence_ledger": evidence,
        "research_gap_ledger": gaps,
        "open_research_gaps": open_gaps,
        "lineage_warning_table": warnings,
        "analyst_synthesis_generated": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "boundary": SYNTHESIS_BOUNDARY,
    }


__all__ = [
    "CHAPTER7_QUESTION_TITLES",
    "CHAPTER_READINESS_COLUMNS",
    "EVIDENCE_LEDGER_COLUMNS",
    "GAP_LEDGER_COLUMNS",
    "LINEAGE_WARNING_COLUMNS",
    "MANAGER_IDENTITY_SSOT",
    "MANAGER_ROSTER_COLUMNS",
    "QUESTION_LEDGER_COLUMNS",
    "SYNTHESIS_BOUNDARY",
    "build_chapter_readiness",
    "build_evidence_ledger",
    "build_gap_ledger",
    "build_lineage_warnings",
    "build_management_handoff",
    "build_manager_roster",
    "build_question_ledger",
]
