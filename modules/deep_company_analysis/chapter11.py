from __future__ import annotations

"""Michael Shearn Chapter 11 — Evaluating Mergers & Acquisitions.

Phase 11A is deliberately a source-lock contract only. It preserves the exact Chapter 11
question set (Q58-Q59) from *The Investment Checklist* and defines neutral analyst/research
structures without automatically scoring acquisition quality, forecasting M&A outcomes, or
creating an investment signal.

Boundaries
----------
- AI/Data may organize evidence; the analyst owns every qualitative conclusion.
- Phase 11A does not calculate acquisition success, synergy realization, deal returns,
  intrinsic value, MOS, or investment Research Gate outcomes.
- Historical financial/operating calculations and canonical company-data bridges are deferred
  to later Chapter 11 phases so this source contract cannot create a duplicate financial SSOT.
- Phase 11A adds no web research, database/store, UI, valuation bridge, portfolio action,
  or BUY/HOLD/SELL logic.
- Missing M&A evidence remains Unknown / a research gap; it is never converted into a
  favorable or unfavorable conclusion automatically.
"""

from copy import deepcopy
from typing import Any


CHAPTER_NUMBER = 11
CHAPTER_TITLE = "Evaluating Mergers & Acquisitions"
QUESTION_KEYS = ("Q58", "Q59")
QUESTION_TITLES: dict[str, str] = {
    "Q58": "How does management make M&A decisions?",
    "Q59": "Have past acquisitions been successful?",
}
QUESTION_SOURCE_PAGES: dict[str, int] = {
    "Q58": 305,
    "Q59": 310,
}
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Chapter 11 — Q58-Q59"
SOURCE_QUESTION_RANGE = "Q58-Q59"

QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")

QUESTION_RESEARCH_FOCUS: dict[str, str] = {
    "Q58": "Management's acquisition decision process, rationale, motivation, expected benefits, costs, risks, and discipline.",
    "Q59": "Whether historical acquisitions were successful, including strategic fit, operating understanding, customer and employee retention, price discipline, and financing outcomes.",
}

EVIDENCE_COLUMNS = [
    "Question",
    "Observation / Claim",
    "Period / Date",
    "M&A Topic",
    "Source Grade",
    "Source Title",
    "Source URL / File",
    "Source Date",
    "As-of Date",
    "Evidence Text / Reference",
    "Direction",
    "Status",
    "Analyst Note",
]

RESEARCH_GAP_COLUMNS = [
    "Question",
    "Research Gap",
    "Materiality",
    "Next Action",
    "Status",
    "Analyst Note",
]

MA_EVENT_COLUMNS = [
    "Event Date",
    "Publication Date",
    "Target / Transaction",
    "Observed Event / Change",
    "Questions Potentially Affected",
    "Source",
    "Analyst Review Status",
    "Analyst Note",
]


def empty_payload(ticker: str, company_name: str = "") -> dict[str, Any]:
    symbol = str(ticker or "").strip().upper()
    return {
        "ticker": symbol,
        "company_name": str(company_name or "").strip(),
        "source_lock": SOURCE_LOCK,
        "source_question_range": SOURCE_QUESTION_RANGE,
        "question_status": {key: "Unknown" for key in QUESTION_KEYS},
        "confidence": {key: "Unknown" for key in QUESTION_KEYS},
        "analyst_assessment": {key: "Unknown" for key in QUESTION_KEYS},
        "evidence": [],
        "research_gaps": [],
        "ma_events": [],
    }


def normalize_payload(
    payload: dict[str, Any] | None,
    ticker: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    base = empty_payload(
        ticker or str(source.get("ticker", "")),
        company_name or str(source.get("company_name", "")),
    )
    if not isinstance(payload, dict):
        return base

    out = deepcopy(base)
    for key in out:
        if key in payload:
            out[key] = deepcopy(payload[key])

    out["ticker"] = str(out.get("ticker") or "").strip().upper()
    out["company_name"] = str(out.get("company_name") or "").strip()
    out["source_lock"] = SOURCE_LOCK
    out["source_question_range"] = SOURCE_QUESTION_RANGE

    if not isinstance(out.get("question_status"), dict):
        out["question_status"] = {}
    if not isinstance(out.get("confidence"), dict):
        out["confidence"] = {}
    if not isinstance(out.get("analyst_assessment"), dict):
        out["analyst_assessment"] = {}

    for question in QUESTION_KEYS:
        if out["question_status"].get(question) not in QUESTION_STATUS_OPTIONS:
            out["question_status"][question] = "Unknown"
        if out["confidence"].get(question) not in CONFIDENCE_OPTIONS:
            out["confidence"][question] = "Unknown"
        if question not in out["analyst_assessment"]:
            out["analyst_assessment"][question] = "Unknown"

    for rows_key in ("evidence", "research_gaps", "ma_events"):
        if not isinstance(out.get(rows_key), list):
            out[rows_key] = []

    return out


def research_gap_warnings(payload: dict[str, Any] | None) -> list[str]:
    """Return research-completeness warnings only; never an M&A-quality or investment rating."""
    data = normalize_payload(payload or {})
    warnings: list[str] = []
    for question in QUESTION_KEYS:
        if data["question_status"].get(question) in {"Unknown", "Partial"}:
            warnings.append(f"{question}: M&A research remains incomplete; analyst review required.")
    return warnings


__all__ = [
    "CHAPTER_NUMBER",
    "CHAPTER_TITLE",
    "CONFIDENCE_OPTIONS",
    "EVIDENCE_COLUMNS",
    "EVIDENCE_DIRECTION_OPTIONS",
    "MA_EVENT_COLUMNS",
    "QUESTION_KEYS",
    "QUESTION_RESEARCH_FOCUS",
    "QUESTION_SOURCE_PAGES",
    "QUESTION_STATUS_OPTIONS",
    "QUESTION_TITLES",
    "RESEARCH_GAP_COLUMNS",
    "SOURCE_LOCK",
    "SOURCE_QUESTION_RANGE",
    "empty_payload",
    "normalize_payload",
    "research_gap_warnings",
]
