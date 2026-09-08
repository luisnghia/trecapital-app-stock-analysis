from __future__ import annotations

"""Michael Shearn Appendix B — How to Interview the Management Team.

V93 is a source-lock and architecture-mapping contract only. Appendix B is treated as a
management-interview research protocol, not as a management-quality scoring engine.

Source-locked boundaries
------------------------
- Ask one open-ended question at a time, listen, and clarify rather than leading the answer.
- Prefer evidence from what managers actually did and why; avoid treating hypothetical answers
  as evidence of future behavior.
- Face-to-face access can increase confidence without increasing accuracy. Visual, personality,
  familiarity and liking cues are recorded as possible assessment caveats, never quality signals.
- Use interviews to understand how management thinks, operates and measures the organization;
  the analyst owns interpretation and conclusions.
- Contextual operating record, accomplishments and other informed views remain relevant checks
  against impressions formed in a meeting.
- V93 creates no management score, CEO-quality classifier, credibility/personality score,
  weighted research score, BUY/HOLD/SELL signal, MOS/intrinsic-value change, or Investment
  Research Gate change. It adds no duplicate financial/company SSOT.
"""

from copy import deepcopy
from typing import Any


APPENDIX_KEY = "B"
APPENDIX_TITLE = "How to Interview the Management Team"
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Appendix B"
SOURCE_PRINT_PAGES = (331, 334)

SECTION_KEYS = (
    "ask_open_ended_questions",
    "face_to_face_assessment_danger",
)
SECTION_TITLES = {
    "ask_open_ended_questions": "Ask Open-Ended Questions",
    "face_to_face_assessment_danger": "Be Aware of the Danger of Face-to-Face Assessments of Managers",
}

INTERVIEW_PROTOCOL = (
    "Ask one open-ended question at a time.",
    "Listen before moving to the next question.",
    "Clarify or neutrally re-ask when the response is incomplete or unclear.",
    "Prefer questions about actual past behavior and follow up on why management acted that way.",
    "Avoid relying on hypothetical answers as evidence of future behavior.",
)

MANAGEMENT_INTERVIEW_TOPICS = (
    "Management style and selection of the management team",
    "Operational changes and inherited-versus-created business practices",
    "Major challenges over the last five or ten years",
    "Career background, prior roles and important turning points",
    "Mistakes and lessons learned",
    "Best and worst parts of the job",
    "Succession, strongest managers and future roles",
    "Changes or improvements management would make",
)

FACE_TO_FACE_CAVEATS = (
    "False confidence from direct access or meeting management",
    "Overweighting visual or body-language cues",
    "Snap impressions from presentation style or handshake-like cues",
    "Liking, similarity, common-interest or appearance bias",
    "Mistaking accessibility or charisma for operating quality",
)

CONTEXTUAL_CHECKS = (
    "Operating record",
    "Management accomplishments",
    "Views of other informed managers or relevant sources",
    "Evidence about how management thinks, operates and measures the organization",
)

SESSION_NOTE_COLUMNS = [
    "Session ID",
    "Management Participant / Role",
    "Interview Date",
    "Topic",
    "Open-Ended Question",
    "Management Response / Observation",
    "Clarification / Follow-up",
    "Past-Behavior Evidence",
    "Hypothetical Flag",
    "Face-to-Face Caveat Noted",
    "Related DCA Question / Topic",
    "Analyst Commentary",
]

CAVEAT_OPTIONS = ("Not noted", "Possible", "Material for re-review", "Unknown")
SECTION_STATUS_OPTIONS = ("Unknown", "Partial", "Covered", "N/A")


def empty_payload(ticker: str, company_name: str = "") -> dict[str, Any]:
    return {
        "ticker": str(ticker or "").strip().upper(),
        "company_name": str(company_name or "").strip(),
        "source_lock": SOURCE_LOCK,
        "sections": {key: "Unknown" for key in SECTION_KEYS},
        "sessions": [],
        "contextual_checks": [],
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
        if out["sections"].get(key) not in SECTION_STATUS_OPTIONS:
            out["sections"][key] = "Unknown"
    for key in ("sessions", "contextual_checks", "research_gaps"):
        if not isinstance(out.get(key), list):
            out[key] = []
    out["analyst_synthesis"] = str(out.get("analyst_synthesis") or "")
    return out


def normalize_caveat(value: str | None) -> str:
    """Normalize a review caveat only; this is not a management or credibility score."""
    text = str(value or "").strip()
    return text if text in CAVEAT_OPTIONS else "Unknown"


def research_gap_warnings(payload: dict[str, Any] | None) -> list[str]:
    """Return interview-research completeness warnings, never investment conclusions."""
    data = normalize_payload(payload or {})
    warnings: list[str] = []
    for key in SECTION_KEYS:
        if data["sections"].get(key) in {"Unknown", "Partial"}:
            warnings.append(
                f"Appendix B — {SECTION_TITLES[key]} remains incomplete; analyst review required."
            )
    return warnings


__all__ = [
    "APPENDIX_KEY",
    "APPENDIX_TITLE",
    "CAVEAT_OPTIONS",
    "CONTEXTUAL_CHECKS",
    "FACE_TO_FACE_CAVEATS",
    "INTERVIEW_PROTOCOL",
    "MANAGEMENT_INTERVIEW_TOPICS",
    "SECTION_KEYS",
    "SECTION_STATUS_OPTIONS",
    "SECTION_TITLES",
    "SESSION_NOTE_COLUMNS",
    "SOURCE_LOCK",
    "SOURCE_PRINT_PAGES",
    "empty_payload",
    "normalize_caveat",
    "normalize_payload",
    "research_gap_warnings",
]
