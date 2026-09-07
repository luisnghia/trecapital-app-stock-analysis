from __future__ import annotations

"""Michael Shearn Chapter 10 — Evaluating Growth Opportunities.

Phase 10A is deliberately a source-lock contract only. It preserves the exact Chapter 10
question set (Q53-Q57) from *The Investment Checklist* and defines neutral analyst/research
structures without forecasting growth automatically, scoring growth quality, or creating an
investment signal.

Boundaries
----------
- AI/Data may organize evidence; the analyst owns every qualitative conclusion.
- Phase 10A does not calculate future growth, CAGR, sustainable growth, intrinsic value, MOS,
  or investment Research Gate outcomes.
- Historical financial/operating calculations and canonical company-data bridges are deferred
  to later Chapter 10 phases so this source contract cannot create a duplicate financial SSOT.
- Phase 10A adds no web research, database/store, UI, valuation bridge, portfolio action,
  or BUY/HOLD/SELL logic.
- Missing growth evidence remains Unknown / a research gap; it is never converted into a
  favorable or unfavorable conclusion automatically.
"""

from copy import deepcopy
from typing import Any


CHAPTER_NUMBER = 10
CHAPTER_TITLE = "Evaluating Growth Opportunities"
QUESTION_KEYS = ("Q53", "Q54", "Q55", "Q56", "Q57")
QUESTION_TITLES: dict[str, str] = {
    "Q53": "Does the business grow through mergers and acquisitions, or does it grow organically?",
    "Q54": "What is the management team’s motivation to grow the business?",
    "Q55": "Has historical growth been profitable and will it continue?",
    "Q56": "What are the future growth prospects for the business?",
    "Q57": "Is the management team growing the business too quickly or at a steady pace?",
}
QUESTION_SOURCE_PAGES: dict[str, int] = {
    "Q53": 281,
    "Q54": 282,
    "Q55": 283,
    "Q56": 284,
    "Q57": 296,
}
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Chapter 10 — Q53-Q57"
SOURCE_QUESTION_RANGE = "Q53-Q57"

QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")
GROWTH_MODE_OPTIONS = ("Unknown", "Organic", "M&A", "Mixed", "N/A")

# These labels preserve the five source questions as research subjects only. Detailed source
# dimensions/subsections are intentionally deferred until Phase 10B source verification.
QUESTION_RESEARCH_FOCUS: dict[str, str] = {
    "Q53": "Growth route: organic growth, mergers/acquisitions, or a mixture of both.",
    "Q54": "Management's stated and evidenced motivation for pursuing growth.",
    "Q55": "Whether historical growth translated into profitable economics and whether that pattern is supportable.",
    "Q56": "Evidence for the duration, runway, drivers, and limits of future growth opportunities.",
    "Q57": "Whether management is pursuing growth at a controlled, disciplined pace or expanding too quickly.",
}

EVIDENCE_COLUMNS = [
    "Question",
    "Observation / Claim",
    "Period / Date",
    "Metric / Growth Driver",
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

GROWTH_EVENT_COLUMNS = [
    "Event Date",
    "Publication Date",
    "Event Type",
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
        "growth_mode": "Unknown",
        "evidence": [],
        "research_gaps": [],
        "growth_events": [],
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

    if out.get("growth_mode") not in GROWTH_MODE_OPTIONS:
        out["growth_mode"] = "Unknown"

    for rows_key in ("evidence", "research_gaps", "growth_events"):
        if not isinstance(out.get(rows_key), list):
            out[rows_key] = []

    return out


def research_gap_warnings(payload: dict[str, Any] | None) -> list[str]:
    """Return research-completeness warnings only; never a growth-quality or investment rating."""
    data = normalize_payload(payload or {})
    warnings: list[str] = []
    for question in QUESTION_KEYS:
        if data["question_status"].get(question) in {"Unknown", "Partial"}:
            warnings.append(f"{question}: growth-opportunity research remains incomplete; analyst review required.")
    return warnings


__all__ = [
    "CHAPTER_NUMBER",
    "CHAPTER_TITLE",
    "CONFIDENCE_OPTIONS",
    "EVIDENCE_COLUMNS",
    "EVIDENCE_DIRECTION_OPTIONS",
    "GROWTH_EVENT_COLUMNS",
    "GROWTH_MODE_OPTIONS",
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
