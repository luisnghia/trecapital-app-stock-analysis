from __future__ import annotations

"""Michael Shearn Appendix A — Building a Human Intelligence Network.

V90 is a source-lock and architecture-mapping contract only. Appendix A is treated as a
research-source workflow, not as a new investment checklist score.

Source-locked boundaries
------------------------
- Human research supplements public information when unanswered questions remain.
- Primary and secondary sources are explicitly distinguished; secondary-source opinions are
  leads to investigate, never conclusions to accept without supporting evidence.
- AI remains a Research Assistant: it may organize source records, interview notes and gaps;
  the analyst owns interpretation and conclusions.
- Interview notes preserve what the source said separately from analyst commentary.
- V90 creates no human-source score, credibility score, weighted research score,
  BUY/HOLD/SELL signal, MOS change, intrinsic-value change or Investment Research Gate change.
- V90 adds no duplicate financial/company SSOT and performs no web crawling or contact action.
"""

from copy import deepcopy
from typing import Any


APPENDIX_KEY = "A"
APPENDIX_TITLE = "Building a Human Intelligence Network"
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Appendix A"
SOURCE_PRINT_PAGES = (323, 330)

SECTION_KEYS = (
    "evaluating_information_sources",
    "locating_human_sources",
    "contacting_human_sources",
    "interview_database",
)
SECTION_TITLES = {
    "evaluating_information_sources": "Evaluating Information Sources",
    "locating_human_sources": "How to Locate Human Sources",
    "contacting_human_sources": "How to Contact Human Sources—and Get the Information You Want",
    "interview_database": "Create a Database of Your Interviews for Future Reference",
}
SECTION_SOURCE_PAGES = {
    "evaluating_information_sources": 324,
    "locating_human_sources": 324,
    "contacting_human_sources": 328,
    "interview_database": 329,
}

SOURCE_CLASS_OPTIONS = ("Primary", "Secondary", "Unknown")
SOURCE_CLASS_DEFINITIONS = {
    "Primary": "First-hand knowledge about the business, such as management, employees, suppliers or competitors.",
    "Secondary": "Interprets information from other sources, such as stock analysts or journalists.",
    "Unknown": "Source class has not yet been established by the analyst.",
}

HUMAN_SOURCE_TYPES = (
    "Customer",
    "Journalist",
    "Industry conference participant",
    "Industry insider / associate",
    "Professor / business-school dean",
    "Headhunter / recruiter",
    "Management",
    "Employee",
    "Supplier",
    "Competitor",
    "Other",
)

NOTE_STATEMENT_TYPES = (
    "Assumption",
    "Theory",
    "Fact",
    "Question",
    "Idea",
    "Related point",
    "Unknown",
)

SOURCE_RECORD_COLUMNS = [
    "Source ID",
    "Source Name / Alias",
    "Source Class",
    "Source Type",
    "Organization / Context",
    "First-hand Relationship",
    "Industry Tenure / History",
    "Why This Source May Know",
    "Introduced / Referred By",
    "Last Contact Date",
    "Next Contact Note",
    "Analyst Note",
]

INTERVIEW_NOTE_COLUMNS = [
    "Interview ID",
    "Source ID",
    "Interview Date",
    "Question / Prompt",
    "Source Response / Observation",
    "Statement Type",
    "Uncertainty Noted",
    "Related DCA Question / Topic",
    "Analyst Commentary",
]

RESEARCH_GAP_COLUMNS = [
    "Gap ID",
    "Unanswered Question / Assumption",
    "Preferred Source Type",
    "Why First-hand Evidence Matters",
    "Status",
    "Analyst Note",
]

CONTACT_PRINCIPLES = (
    "Learn as much as practical about the source before making contact.",
    "Explain why you are contacting the source and how the information will be used.",
    "Use broad questions to learn why things are happening and uncover unknown unknowns.",
    "At the end of the conversation, ask who else is knowledgeable and worth contacting.",
    "Protect source identity and build trust.",
    "Maintain contact with valuable sources rather than reaching out only during a crisis.",
)

NOTE_TAKING_PRINCIPLES = (
    "Record conversation details without silently inserting analyst interpretation into the source response.",
    "If meaning is uncertain, record the uncertainty instead of rationalizing the answer.",
    "Classify source statements as assumption, theory, fact, question, idea or related point when possible.",
    "Keep full responses so apparently minor observations remain available for later pattern recognition.",
    "Add a brief source synopsis as context, separate from the source's substantive statements.",
)


def empty_payload(ticker: str, company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": str(ticker or "").strip().upper(),
        "company_name": str(company_name or "").strip(),
        "source_lock": SOURCE_LOCK,
        "sections": {key: "Unknown" for key in SECTION_KEYS},
        "sources": [],
        "interviews": [],
        "research_gaps": [],
        "analyst_synthesis": "",
    }


def normalize_payload(
    payload: dict[str, Any] | None,
    ticker: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    out = empty_payload(
        ticker or str(source.get("ticker", "")),
        company_name or str(source.get("company_name", "")),
    )
    if not isinstance(payload, dict):
        return out

    for key in out:
        if key in payload:
            out[key] = deepcopy(payload[key])

    out["ticker"] = str(out.get("ticker") or "").strip().upper()
    out["company_name"] = str(out.get("company_name") or "").strip()
    out["source_lock"] = SOURCE_LOCK
    if not isinstance(out.get("sections"), dict):
        out["sections"] = {}
    for key in SECTION_KEYS:
        if out["sections"].get(key) not in {"Unknown", "Partial", "Covered", "N/A"}:
            out["sections"][key] = "Unknown"
    for key in ("sources", "interviews", "research_gaps"):
        if not isinstance(out.get(key), list):
            out[key] = []
    out["analyst_synthesis"] = str(out.get("analyst_synthesis") or "")
    return out


def classify_source(source_class: str | None) -> str:
    """Normalize source class only; this is not a credibility or quality score."""
    value = str(source_class or "").strip().title()
    return value if value in SOURCE_CLASS_OPTIONS else "Unknown"


def research_gap_warnings(payload: dict[str, Any] | None) -> list[str]:
    """Return research-completeness warnings only, never investment conclusions."""
    data = normalize_payload(payload or {})
    warnings: list[str] = []
    for key in SECTION_KEYS:
        if data["sections"].get(key) in {"Unknown", "Partial"}:
            warnings.append(f"Appendix A — {SECTION_TITLES[key]} remains incomplete; analyst review required.")
    return warnings


__all__ = [
    "APPENDIX_KEY",
    "APPENDIX_TITLE",
    "CONTACT_PRINCIPLES",
    "HUMAN_SOURCE_TYPES",
    "INTERVIEW_NOTE_COLUMNS",
    "NOTE_STATEMENT_TYPES",
    "NOTE_TAKING_PRINCIPLES",
    "RESEARCH_GAP_COLUMNS",
    "SECTION_KEYS",
    "SECTION_SOURCE_PAGES",
    "SECTION_TITLES",
    "SOURCE_CLASS_DEFINITIONS",
    "SOURCE_CLASS_OPTIONS",
    "SOURCE_LOCK",
    "SOURCE_PRINT_PAGES",
    "SOURCE_RECORD_COLUMNS",
    "classify_source",
    "empty_payload",
    "normalize_payload",
    "research_gap_warnings",
]
