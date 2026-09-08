from __future__ import annotations

"""Appendix A V91 — analyst-owned human-source workspace.

The workspace implements Michael Shearn's Appendix A as a durable research aid.  It stores
source records, interview notes and references to unanswered DCA questions.  It deliberately
does not score sources, infer credibility, change any chapter Research Gate, or generate an
investment conclusion.
"""

from copy import deepcopy
from datetime import date
from hashlib import sha256
from typing import Any, Iterable

from .appendix_a import (
    HUMAN_SOURCE_TYPES,
    NOTE_STATEMENT_TYPES,
    SOURCE_CLASS_OPTIONS,
    SOURCE_LOCK,
    classify_source,
    empty_payload,
    normalize_payload,
)

QUESTION_IDS = tuple(f"Q{i:02d}" for i in range(1, 60))
SECTION_STATUS_OPTIONS = ("Unknown", "Partial", "Covered", "N/A")
GAP_STATUS_OPTIONS = ("Open", "In research", "Resolved", "N/A")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _digest(*parts: Any) -> str:
    raw = "|".join(_text(part).casefold() for part in parts)
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_question_refs(values: Iterable[Any] | None) -> list[str]:
    """Return unique Q01–Q59 references only; these are links, not copied chapter state."""
    out: list[str] = []
    for value in values or []:
        ref = _text(value).upper()
        if ref in QUESTION_IDS and ref not in out:
            out.append(ref)
    return out


def make_source_record(
    *,
    source_name: str,
    source_class: str = "Unknown",
    source_type: str = "Other",
    organization_context: str = "",
    first_hand_relationship: str = "",
    industry_tenure_history: str = "",
    why_source_may_know: str = "",
    introduced_by: str = "",
    last_contact_date: str = "",
    next_contact_note: str = "",
    analyst_note: str = "",
) -> dict[str, Any]:
    source_type = source_type if source_type in HUMAN_SOURCE_TYPES else "Other"
    record = {
        "source_id": "",
        "source_name": _text(source_name),
        "source_class": classify_source(source_class),
        "source_type": source_type,
        "organization_context": _text(organization_context),
        "first_hand_relationship": _text(first_hand_relationship),
        "industry_tenure_history": _text(industry_tenure_history),
        "why_source_may_know": _text(why_source_may_know),
        "introduced_by": _text(introduced_by),
        "last_contact_date": _text(last_contact_date),
        "next_contact_note": _text(next_contact_note),
        "analyst_note": _text(analyst_note),
    }
    record["source_id"] = "SRC-" + _digest(
        record["source_name"], record["source_type"], record["organization_context"]
    )
    return record


def make_interview_record(
    *,
    source_id: str,
    interview_date: str | None = None,
    question_prompt: str = "",
    source_response_observation: str = "",
    statement_type: str = "Unknown",
    uncertainty_noted: str = "",
    related_question_refs: Iterable[Any] | None = None,
    analyst_commentary: str = "",
) -> dict[str, Any]:
    """Create an interview note with source words kept separate from analyst interpretation."""
    statement_type = statement_type if statement_type in NOTE_STATEMENT_TYPES else "Unknown"
    interview_date = _text(interview_date) or date.today().isoformat()
    record = {
        "interview_id": "",
        "source_id": _text(source_id),
        "interview_date": interview_date,
        "question_prompt": _text(question_prompt),
        "source_response_observation": _text(source_response_observation),
        "statement_type": statement_type,
        "uncertainty_noted": _text(uncertainty_noted),
        "related_question_refs": normalize_question_refs(related_question_refs),
        "analyst_commentary": _text(analyst_commentary),
    }
    record["interview_id"] = "INT-" + _digest(
        record["source_id"], record["interview_date"], record["question_prompt"],
        record["source_response_observation"]
    )
    return record


def make_research_gap(
    *,
    unanswered_question_assumption: str,
    preferred_source_type: str = "Other",
    why_first_hand_evidence_matters: str = "",
    related_question_refs: Iterable[Any] | None = None,
    status: str = "Open",
    analyst_note: str = "",
) -> dict[str, Any]:
    preferred_source_type = preferred_source_type if preferred_source_type in HUMAN_SOURCE_TYPES else "Other"
    status = status if status in GAP_STATUS_OPTIONS else "Open"
    record = {
        "gap_id": "",
        "unanswered_question_assumption": _text(unanswered_question_assumption),
        "preferred_source_type": preferred_source_type,
        "why_first_hand_evidence_matters": _text(why_first_hand_evidence_matters),
        "related_question_refs": normalize_question_refs(related_question_refs),
        "status": status,
        "analyst_note": _text(analyst_note),
    }
    record["gap_id"] = "GAP-" + _digest(
        record["unanswered_question_assumption"], ",".join(record["related_question_refs"])
    )
    return record


def _dedupe(records: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for record in records:
        rid = _text(record.get(id_key))
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(record)
    return out


def normalize_workspace(payload: dict[str, Any] | None, ticker: str = "", company_name: str = "") -> dict[str, Any]:
    """Allow-list Appendix A state and intentionally drop financial/valuation/chapter SSOT payloads."""
    base = normalize_payload(payload or {}, ticker=ticker, company_name=company_name)
    out = empty_payload(base["ticker"], base["company_name"])
    out["source_lock"] = SOURCE_LOCK
    out["sections"] = {
        key: value if value in SECTION_STATUS_OPTIONS else "Unknown"
        for key, value in base["sections"].items()
        if key in out["sections"]
    }
    for key in list(out["sections"]):
        out["sections"].setdefault(key, "Unknown")

    sources: list[dict[str, Any]] = []
    for item in base.get("sources", []):
        if not isinstance(item, dict):
            continue
        sources.append(make_source_record(
            source_name=item.get("source_name", ""),
            source_class=item.get("source_class", "Unknown"),
            source_type=item.get("source_type", "Other"),
            organization_context=item.get("organization_context", ""),
            first_hand_relationship=item.get("first_hand_relationship", ""),
            industry_tenure_history=item.get("industry_tenure_history", ""),
            why_source_may_know=item.get("why_source_may_know", ""),
            introduced_by=item.get("introduced_by", ""),
            last_contact_date=item.get("last_contact_date", ""),
            next_contact_note=item.get("next_contact_note", ""),
            analyst_note=item.get("analyst_note", ""),
        ))
    out["sources"] = _dedupe(sources, "source_id")

    interviews: list[dict[str, Any]] = []
    for item in base.get("interviews", []):
        if not isinstance(item, dict):
            continue
        interviews.append(make_interview_record(
            source_id=item.get("source_id", ""),
            interview_date=item.get("interview_date", ""),
            question_prompt=item.get("question_prompt", ""),
            source_response_observation=item.get("source_response_observation", ""),
            statement_type=item.get("statement_type", "Unknown"),
            uncertainty_noted=item.get("uncertainty_noted", ""),
            related_question_refs=item.get("related_question_refs", []),
            analyst_commentary=item.get("analyst_commentary", ""),
        ))
    out["interviews"] = _dedupe(interviews, "interview_id")

    gaps: list[dict[str, Any]] = []
    for item in base.get("research_gaps", []):
        if not isinstance(item, dict):
            continue
        gaps.append(make_research_gap(
            unanswered_question_assumption=item.get("unanswered_question_assumption", ""),
            preferred_source_type=item.get("preferred_source_type", "Other"),
            why_first_hand_evidence_matters=item.get("why_first_hand_evidence_matters", ""),
            related_question_refs=item.get("related_question_refs", []),
            status=item.get("status", "Open"),
            analyst_note=item.get("analyst_note", ""),
        ))
    out["research_gaps"] = _dedupe(gaps, "gap_id")
    out["analyst_synthesis"] = _text(base.get("analyst_synthesis", ""))
    return deepcopy(out)


__all__ = [
    "GAP_STATUS_OPTIONS", "QUESTION_IDS", "SECTION_STATUS_OPTIONS", "make_interview_record",
    "make_research_gap", "make_source_record", "normalize_question_refs", "normalize_workspace",
]
