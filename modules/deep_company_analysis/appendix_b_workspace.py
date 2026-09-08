from __future__ import annotations

"""Appendix B V94 — analyst-owned management interview workspace.

This module operationalizes the V93 source lock without evaluating management quality.
It stores interview observations, analyst commentary and research-gap references only.
DCA links are references to Q01–Q59; they never mutate chapter state.
"""

from copy import deepcopy
from datetime import date
from hashlib import sha256
from typing import Any, Iterable

from modules.deep_company_analysis.appendix_b import (
    CAVEAT_OPTIONS,
    MANAGEMENT_INTERVIEW_TOPICS,
    SOURCE_LOCK,
    normalize_caveat,
)

DCA_QUESTION_IDS = tuple(f"Q{i:02d}" for i in range(1, 60))
SESSION_STATUS_OPTIONS = ("Planned", "In progress", "Completed", "Needs follow-up")
GAP_STATUS_OPTIONS = ("Open", "Researching", "Resolved", "N/A")

# Persistence is deliberately allow-listed. These concepts must remain upstream SSOT / analyst decisions.
FORBIDDEN_PERSISTENCE_KEYS = frozenset(
    {
        "research_gate", "investment_research_gate", "intrinsic_value", "margin_of_safety",
        "mos", "buy_hold_sell", "recommendation", "management_score", "ceo_quality_score",
        "credibility_score", "personality_score", "weighted_score", "financials", "valuation",
    }
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def stable_id(prefix: str, *parts: Any) -> str:
    material = "|".join(_text(part).casefold() for part in parts)
    return f"{prefix}_{sha256(material.encode('utf-8')).hexdigest()[:16]}"


def normalize_dca_question_refs(values: Iterable[Any] | None) -> list[str]:
    valid = set(DCA_QUESTION_IDS)
    out: list[str] = []
    for value in values or []:
        item = _text(value).upper()
        if item in valid and item not in out:
            out.append(item)
    return out


def empty_topic_entry(topic: str) -> dict[str, Any]:
    return {
        "topic": topic,
        "open_ended_question": "",
        "management_response_observation": "",
        "clarification_follow_up": "",
        "past_behavior_evidence": "",
        "hypothetical_flag": False,
        "face_to_face_caveat": "Not noted",
        "dca_question_refs": [],
        "analyst_commentary": "",
    }


def new_session(
    ticker: str,
    participant_role: str,
    interview_date: str = "",
    company_name: str = "",
) -> dict[str, Any]:
    ticker = _text(ticker).upper()
    participant_role = _text(participant_role)
    interview_date = _text(interview_date) or date.today().isoformat()
    return {
        "session_id": stable_id("MB", ticker, participant_role, interview_date),
        "ticker": ticker,
        "company_name": _text(company_name),
        "source_lock": SOURCE_LOCK,
        "management_participant_role": participant_role,
        "interview_date": interview_date,
        "status": "Planned",
        "topic_entries": [empty_topic_entry(topic) for topic in MANAGEMENT_INTERVIEW_TOPICS],
        "contextual_checks": [],
        "analyst_session_note": "",
    }


def normalize_topic_entry(value: Any, fallback_topic: str = "") -> dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    out = empty_topic_entry(_text(src.get("topic")) or fallback_topic)
    for key in (
        "open_ended_question", "management_response_observation", "clarification_follow_up",
        "past_behavior_evidence", "analyst_commentary",
    ):
        out[key] = _text(src.get(key))
    out["hypothetical_flag"] = bool(src.get("hypothetical_flag", False))
    out["face_to_face_caveat"] = normalize_caveat(src.get("face_to_face_caveat"))
    out["dca_question_refs"] = normalize_dca_question_refs(src.get("dca_question_refs"))
    return out


def normalize_session(value: Any) -> dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    ticker = _text(src.get("ticker")).upper()
    participant = _text(src.get("management_participant_role"))
    interview_date = _text(src.get("interview_date"))
    out = new_session(ticker, participant, interview_date, _text(src.get("company_name")))
    supplied_id = _text(src.get("session_id"))
    if supplied_id:
        out["session_id"] = supplied_id
    status = _text(src.get("status"))
    out["status"] = status if status in SESSION_STATUS_OPTIONS else "Planned"
    supplied_entries = src.get("topic_entries") if isinstance(src.get("topic_entries"), list) else []
    by_topic = {
        _text(item.get("topic")): item
        for item in supplied_entries if isinstance(item, dict) and _text(item.get("topic"))
    }
    out["topic_entries"] = [normalize_topic_entry(by_topic.get(topic, {}), topic) for topic in MANAGEMENT_INTERVIEW_TOPICS]
    checks = src.get("contextual_checks") if isinstance(src.get("contextual_checks"), list) else []
    out["contextual_checks"] = [_text(x) for x in checks if _text(x)]
    out["analyst_session_note"] = _text(src.get("analyst_session_note"))
    out["source_lock"] = SOURCE_LOCK
    return out


def new_research_gap(ticker: str, gap_text: str, dca_question_refs: Iterable[Any] | None, session_id: str = "") -> dict[str, Any]:
    ticker = _text(ticker).upper()
    gap_text = _text(gap_text)
    refs = normalize_dca_question_refs(dca_question_refs)
    return {
        "gap_id": stable_id("MBG", ticker, session_id, gap_text, ",".join(refs)),
        "ticker": ticker,
        "session_id": _text(session_id),
        "gap_text": gap_text,
        "dca_question_refs": refs,
        "status": "Open",
        "analyst_note": "",
    }


def normalize_research_gap(value: Any) -> dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    out = new_research_gap(src.get("ticker", ""), src.get("gap_text", ""), src.get("dca_question_refs"), src.get("session_id", ""))
    if _text(src.get("gap_id")):
        out["gap_id"] = _text(src.get("gap_id"))
    status = _text(src.get("status"))
    out["status"] = status if status in GAP_STATUS_OPTIONS else "Open"
    out["analyst_note"] = _text(src.get("analyst_note"))
    return out


def referenced_dca_questions(session: Any) -> list[str]:
    refs: list[str] = []
    for entry in normalize_session(session)["topic_entries"]:
        for qid in entry["dca_question_refs"]:
            if qid not in refs:
                refs.append(qid)
    return refs


def workspace_summary(sessions: Iterable[Any], gaps: Iterable[Any]) -> dict[str, Any]:
    normalized_sessions = [normalize_session(x) for x in sessions]
    normalized_gaps = [normalize_research_gap(x) for x in gaps]
    refs: list[str] = []
    for session in normalized_sessions:
        for qid in referenced_dca_questions(session):
            if qid not in refs:
                refs.append(qid)
    for gap in normalized_gaps:
        for qid in gap["dca_question_refs"]:
            if qid not in refs:
                refs.append(qid)
    return {
        "sessions": deepcopy(normalized_sessions),
        "research_gaps": deepcopy(normalized_gaps),
        "referenced_dca_questions": refs,
        "research_assistant_role": "organize evidence and gaps; analyst owns interpretation and conclusions",
    }


__all__ = [
    "DCA_QUESTION_IDS", "FORBIDDEN_PERSISTENCE_KEYS", "GAP_STATUS_OPTIONS", "SESSION_STATUS_OPTIONS",
    "empty_topic_entry", "new_research_gap", "new_session", "normalize_dca_question_refs",
    "normalize_research_gap", "normalize_session", "normalize_topic_entry", "referenced_dca_questions",
    "stable_id", "workspace_summary",
]
