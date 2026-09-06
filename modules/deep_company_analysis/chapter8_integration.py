from __future__ import annotations

"""Chapter 8 Phase 8E integration helpers.

These helpers expose analyst-owned Chapter 8 state to the unified Deep Company Analysis
workspace and the consolidated report. They are intentionally descriptive only: no management
score, investment signal, MOS change, or Research Gate mutation is produced here.
"""

from typing import Any

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8


_CLOSED_GAP_STATUSES = {"closed", "done", "resolved", "completed", "n/a"}


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.to_dict("records")
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    return []


def build_chapter8_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    statuses = data.get("question_status") or {}
    confidence = data.get("confidence") or {}
    assessments = data.get("analyst_assessment") or {}

    counts = {status: 0 for status in ch8.QUESTION_STATUS_OPTIONS}
    for question in ch8.QUESTION_KEYS:
        status = str(statuses.get(question) or "Unknown")
        if status not in counts:
            status = "Unknown"
        counts[status] += 1

    evidence = _rows(data.get("evidence"))
    gaps = _rows(data.get("research_gaps"))
    open_gaps = sum(
        1
        for row in gaps
        if str(row.get("Status") or "").strip().casefold() not in _CLOSED_GAP_STATUSES
    )
    analyst_conclusions = sum(
        1
        for question in ch8.QUESTION_KEYS
        if str(assessments.get(question) or "").strip() not in {"", "Unknown"}
    )
    confidence_known = sum(
        1
        for question in ch8.QUESTION_KEYS
        if str(confidence.get(question) or "Unknown") != "Unknown"
    )

    return {
        "total_questions": len(ch8.QUESTION_KEYS),
        "answered": counts["Answered"],
        "partial": counts["Partial"],
        "unknown": counts["Unknown"],
        "not_applicable": counts["N/A"],
        "analyst_conclusions": analyst_conclusions,
        "confidence_known": confidence_known,
        "promoted_evidence": len(evidence),
        "research_gaps_total": len(gaps),
        "research_gaps_open": open_gaps,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
    }


def build_chapter8_status_table(payload: dict[str, Any] | None) -> pd.DataFrame:
    data = payload if isinstance(payload, dict) else {}
    statuses = data.get("question_status") or {}
    confidence = data.get("confidence") or {}
    assessments = data.get("analyst_assessment") or {}
    rows: list[dict[str, Any]] = []
    for question in ch8.QUESTION_KEYS:
        rows.append(
            {
                "Question": question,
                "Question Title": ch8.QUESTION_TITLES[question],
                "Research Status": str(statuses.get(question) or "Unknown"),
                "Analyst Confidence": str(confidence.get(question) or "Unknown"),
                "Analyst Assessment": str(assessments.get(question) or "Unknown"),
            }
        )
    return pd.DataFrame(rows)


def build_chapter8_report_frames(payload: dict[str, Any] | None) -> dict[str, pd.DataFrame]:
    data = payload if isinstance(payload, dict) else {}
    return {
        "status": build_chapter8_status_table(data),
        "evidence": pd.DataFrame(_rows(data.get("evidence")), columns=ch8.EVIDENCE_COLUMNS),
        "research_gaps": pd.DataFrame(_rows(data.get("research_gaps")), columns=ch8.RESEARCH_GAP_COLUMNS),
        "capital_allocation": pd.DataFrame(
            _rows(data.get("q46_capital_allocation")), columns=ch8.CAPITAL_ALLOCATION_COLUMNS
        ),
        "buybacks": pd.DataFrame(_rows(data.get("q47_buyback_history")), columns=ch8.BUYBACK_HISTORY_COLUMNS),
    }


__all__ = [
    "build_chapter8_summary",
    "build_chapter8_status_table",
    "build_chapter8_report_frames",
]
