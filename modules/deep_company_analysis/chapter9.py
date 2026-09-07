from __future__ import annotations

"""Michael Shearn Chapter 9 — Positive and Negative Management Traits.

Phase 9A is deliberately a source-lock contract only. It preserves the exact Chapter 9
question set (Q48-Q52) from *The Investment Checklist* and defines neutral analyst-workspace
structures without creating a management-quality score or an investment signal.

Boundaries
----------
- AI/Data may organize evidence; the analyst owns every qualitative conclusion.
- Chapter 7 remains the manager identity/background source of truth.
- Chapter 9 must not create a second manager master.
- Phase 9A adds no web research, database/store, UI, financial bridge, MOS, Research Gate,
  or BUY/HOLD/SELL logic.
- Behavioral observations are dated evidence, never fabricated TTM/T12M facts.
"""

from copy import deepcopy
from typing import Any


CHAPTER_NUMBER = 9
CHAPTER_TITLE = "Assessing the Quality of Management—Positive and Negative Traits"
QUESTION_KEYS = ("Q48", "Q49", "Q50", "Q51", "Q52")
QUESTION_TITLES: dict[str, str] = {
    "Q48": "Does the CEO love the money or the business?",
    "Q49": "Can you identify a moment of integrity for the manager?",
    "Q50": "Are managers clear and consistent in their communications and actions with stakeholders?",
    "Q51": "Does management think independently and remain unswayed by what others in their industry are doing?",
    "Q52": "Is the CEO self-promoting?",
}
QUESTION_SOURCE_PAGES: dict[str, int] = {
    "Q48": 256,
    "Q49": 264,
    "Q50": 268,
    "Q51": 275,
    "Q52": 276,
}
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Chapter 9 — Q48-Q52"
MANAGER_IDENTITY_SSOT = "Chapter 7 manager master"

QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")

# Q48: source-locked diagnostic questions explicitly listed under "How Do You Identify Passion?".
# They are research prompts, not a scorecard and carry no automatic weighting.
Q48_PASSION_RESEARCH_PROMPTS: tuple[str, ...] = (
    "Is the business a career or just a job for the manager?",
    "Would the CEO refuse to sell the business, no matter what the price?",
    "Is the manager interested in money or motivated by money?",
    "Does the manager focus on appearances instead of the business?",
    "What type of philanthropic endeavors is the manager involved in?",
    "Are the managers lifelong learners who focus on continuous improvement?",
)

Q48_PASSION_COLUMNS = [
    "Prompt",
    "Manager ID",
    "Manager",
    "Supporting Evidence",
    "Counter-Evidence",
    "Source",
    "Evidence Date",
    "Analyst Note",
]

EVIDENCE_COLUMNS = [
    "Question",
    "Manager ID",
    "Manager",
    "Observation / Claim",
    "Evidence Type",
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
    "Manager ID",
    "Manager",
    "Research Gap",
    "Materiality",
    "Next Action",
    "Status",
    "Analyst Note",
]

BEHAVIOR_EVENT_COLUMNS = [
    "Event Date",
    "Publication Date",
    "Manager ID",
    "Manager",
    "Context / Situation",
    "Observed Words",
    "Observed Actions",
    "Questions Potentially Affected",
    "Source",
    "Analyst Review Status",
    "Analyst Note",
]


def default_q48_passion_rows() -> list[dict[str, Any]]:
    """Return the six source-locked Q48 prompts as empty analyst evidence rows."""
    return [
        {
            "Prompt": prompt,
            "Manager ID": "",
            "Manager": "",
            "Supporting Evidence": "",
            "Counter-Evidence": "",
            "Source": "",
            "Evidence Date": "",
            "Analyst Note": "",
        }
        for prompt in Q48_PASSION_RESEARCH_PROMPTS
    ]


def empty_payload(ticker: str, company_name: str = "") -> dict[str, Any]:
    symbol = str(ticker or "").strip().upper()
    return {
        "ticker": symbol,
        "company_name": str(company_name or "").strip(),
        "source_lock": SOURCE_LOCK,
        "manager_identity_ssot": MANAGER_IDENTITY_SSOT,
        "question_status": {key: "Unknown" for key in QUESTION_KEYS},
        "confidence": {key: "Unknown" for key in QUESTION_KEYS},
        "analyst_assessment": {key: "Unknown" for key in QUESTION_KEYS},
        "q48_passion_research": default_q48_passion_rows(),
        "evidence": [],
        "research_gaps": [],
        "behavior_events": [],
    }


def normalize_payload(payload: dict[str, Any] | None, ticker: str = "", company_name: str = "") -> dict[str, Any]:
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
    out["source_lock"] = SOURCE_LOCK
    out["manager_identity_ssot"] = MANAGER_IDENTITY_SSOT
    for q in QUESTION_KEYS:
        if out["question_status"].get(q) not in QUESTION_STATUS_OPTIONS:
            out["question_status"][q] = "Unknown"
        if out["confidence"].get(q) not in CONFIDENCE_OPTIONS:
            out["confidence"][q] = "Unknown"
        if q not in out["analyst_assessment"]:
            out["analyst_assessment"][q] = "Unknown"
    return out


def research_gap_warnings(payload: dict[str, Any]) -> list[str]:
    """Return research-completeness warnings only; never a character or quality rating."""
    data = normalize_payload(payload)
    warnings: list[str] = []
    for q in QUESTION_KEYS:
        if data["question_status"].get(q) in {"Unknown", "Partial"}:
            warnings.append(f"{q}: research remains incomplete; analyst review required.")
    return warnings


__all__ = [
    "BEHAVIOR_EVENT_COLUMNS",
    "CHAPTER_NUMBER",
    "CHAPTER_TITLE",
    "CONFIDENCE_OPTIONS",
    "EVIDENCE_COLUMNS",
    "EVIDENCE_DIRECTION_OPTIONS",
    "MANAGER_IDENTITY_SSOT",
    "Q48_PASSION_COLUMNS",
    "Q48_PASSION_RESEARCH_PROMPTS",
    "QUESTION_KEYS",
    "QUESTION_SOURCE_PAGES",
    "QUESTION_STATUS_OPTIONS",
    "QUESTION_TITLES",
    "RESEARCH_GAP_COLUMNS",
    "SOURCE_LOCK",
    "default_q48_passion_rows",
    "empty_payload",
    "normalize_payload",
    "research_gap_warnings",
]
