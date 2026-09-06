from __future__ import annotations

"""Michael Shearn Chapter 8 — Management Competence: How Management Operates the Business.

Phase 8A is a source-locked analyst workspace contract for Q39-Q47 from
*The Investment Checklist*. It defines the evidence structures needed to research
management competence without creating a management score or an investment signal.

Boundaries:
- AI/Data may organize evidence, but the analyst owns every qualitative conclusion.
- Chapter 8 does not change BUY/HOLD/SELL, MOS or Research Gate.
- Qualitative/event evidence is not fabricated into TTM rows.
- Chapter 7 remains the manager-identity/background source; Chapter 8 must not create
  a second manager master.
- Later numeric bridges must use Trecapital canonical data rather than web numbers as
  an independent financial source of truth.
"""

from copy import deepcopy
from typing import Any


QUESTION_KEYS = ("Q39", "Q40", "Q41", "Q42", "Q43", "Q44", "Q45", "Q46", "Q47")
QUESTION_TITLES: dict[str, str] = {
    "Q39": "Does the CEO manage the business to benefit all stakeholders?",
    "Q40": "Does the management team improve its operations day-to-day or does it use a strategic plan to conduct its business?",
    "Q41": "Do the CEO and CFO issue guidance regarding earnings?",
    "Q42": "Is the business managed in a centralized or decentralized way?",
    "Q43": "Does management value its employees?",
    "Q44": "Does the management team know how to hire well?",
    "Q45": "Does the management team focus on cutting unnecessary costs?",
    "Q46": "Are the CEO and CFO disciplined in making capital allocation decisions?",
    "Q47": "Do the CEO and CFO buy back stock opportunistically?",
}

QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")
ORG_STRUCTURE_OPTIONS = ("Unknown", "Centralized", "Mixed", "Decentralized")
GUIDANCE_OUTCOME_OPTIONS = ("Unknown", "Beat", "Meet", "Miss", "N/A")
GUIDANCE_EVENT_OPTIONS = ("Issued", "Revised", "Withdrawn", "No guidance disclosed", "Unknown")

# Q39: source-locked stakeholder groups. "Other stakeholders" avoids pretending every
# issuer discloses a specific community/partner taxonomy.
STAKEHOLDER_GROUPS = (
    "Customers",
    "Employees",
    "Suppliers",
    "Shareholders",
    "Business partners",
    "Other stakeholders",
)

# Q43: the fourteen employee-relation checks listed by Shearn. They are evidence prompts,
# not a scorecard. No dimension is auto-weighted or rolled into an overall grade.
EMPLOYEE_RELATION_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("employees_assets_or_liabilities", "Does management treat its employees as assets or liabilities?"),
    ("employee_contributions", "Does management talk about the contributions of their employees?"),
    ("retention_critical", "Does management believe that retaining employees is critical?"),
    ("promote_from_within", "Does the business promote from within?"),
    ("promotion_path", "Does management show employees how they can get promoted?"),
    ("training_resources", "Does the business invest significant resources in employee training?"),
    ("applicant_attraction", "Does the business attract a great number of applicants?"),
    ("employees_recruited_away", "Are employees avidly recruited from the business?"),
    ("benefit_gap", "Are there large differences between the benefits that the top managers receive versus employees?"),
    ("respectful_layoffs", "Does management treat employees with respect when they lay them off?"),
    ("listens_to_employees", "Does management listen to its employees?"),
    ("strong_culture", "Does the business have a strong culture?"),
    ("shared_values", "Does the business have identifiable, shared values?"),
    ("employee_retention_rate", "What is the employee-retention rate?"),
)

# Q46: the exact five uses of excess free cash flow enumerated in Chapter 8.
# Debt paydown may later be useful as a Trecapital extension, but it is intentionally not
# inserted into this source-locked Shearn tuple.
CAPITAL_ALLOCATION_ACTIONS = (
    "Reinvest in business / new projects",
    "Hold cash",
    "Pay dividends",
    "Buy back stock",
    "Make acquisitions",
)

STAKEHOLDER_EVIDENCE_COLUMNS = [
    "Stakeholder",
    "Claim",
    "Supporting Evidence",
    "Counter-Evidence",
    "Source",
    "Evidence Date",
    "Analyst Note",
]

OPERATING_APPROACH_COLUMNS = [
    "Date",
    "Observation",
    "Continuous Improvement Evidence",
    "Strategic Plan / Transformational Bet Evidence",
    "Frontline Feedback Evidence",
    "Adaptation Evidence",
    "Source",
    "Analyst Note",
]

GUIDANCE_HISTORY_COLUMNS = [
    "Issued Date",
    "Metric",
    "Horizon",
    "Guidance Low",
    "Guidance High",
    "Guidance Point",
    "Guidance Event",
    "Actual",
    "Outcome",
    "Source",
    "Analyst Note",
]

ORG_STRUCTURE_COLUMNS = [
    "Unit",
    "Decision Area",
    "Decision Owner",
    "Central / Local",
    "Autonomy Evidence",
    "Escalation / Control Evidence",
    "Customer-Proximity Evidence",
    "Source",
    "Analyst Note",
]

EMPLOYEE_RELATION_COLUMNS = [
    "Dimension Key",
    "Dimension",
    "Supporting Evidence",
    "Counter-Evidence",
    "Metric / Observation",
    "Metric Period / As-of",
    "Source",
    "Evidence Direction",
    "Analyst Note",
]

HIRING_EVIDENCE_COLUMNS = [
    "Date",
    "Manager ID",
    "Decision / Person",
    "Role",
    "Internal / External",
    "Selection Evidence",
    "Candor / Challenge Evidence",
    "Observed Outcome",
    "Board / Governance Relevance",
    "Source",
    "Analyst Note",
]

COST_ACTION_COLUMNS = [
    "Date",
    "Action",
    "Cost Category",
    "Waste / Non-core",
    "Customer Impact",
    "Employee Impact",
    "Core Investment Preserved",
    "Restructuring / One-off",
    "Amount (tỷ)",
    "Source",
    "Data Origin",
    "Analyst Note",
]

CAPITAL_ALLOCATION_COLUMNS = [
    "Date",
    "Action",
    "Amount (tỷ)",
    "Rationale",
    "Alternative Considered",
    "Discipline / Hurdle Evidence",
    "Observed Outcome",
    "Source",
    "Data Origin",
    "Analyst Note",
]

BUYBACK_HISTORY_COLUMNS = [
    "Period / Date",
    "Authorization",
    "Shares Repurchased",
    "Average Price",
    "Cash Spent (tỷ)",
    "Share Count Before",
    "Share Count After",
    "Stated Reason",
    "Dilution Offset?",
    "Valuation Context",
    "Liquidity / Cash Context",
    "Source",
    "Data Origin",
    "Analyst Note",
]

EVIDENCE_COLUMNS = [
    "Question",
    "Manager ID",
    "Manager",
    "Claim",
    "Evidence Type",
    "Source Grade",
    "Source Title",
    "Source URL / File",
    "Source Date",
    "As-of Date",
    "Evidence Text / Reference",
    "Direction",
    "Status",
    "Data Origin",
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

MANAGEMENT_EVENT_COLUMNS = [
    "Event Date",
    "Publication Date",
    "Manager ID",
    "Manager",
    "Event Type",
    "Description",
    "Questions Potentially Affected",
    "Source",
    "Analyst Review Status",
]


def default_stakeholder_rows() -> list[dict[str, Any]]:
    return [
        {
            "Stakeholder": stakeholder,
            "Claim": "",
            "Supporting Evidence": "",
            "Counter-Evidence": "",
            "Source": "",
            "Evidence Date": "",
            "Analyst Note": "",
        }
        for stakeholder in STAKEHOLDER_GROUPS
    ]


def default_employee_relation_rows() -> list[dict[str, Any]]:
    return [
        {
            "Dimension Key": key,
            "Dimension": label,
            "Supporting Evidence": "",
            "Counter-Evidence": "",
            "Metric / Observation": "",
            "Metric Period / As-of": "",
            "Source": "",
            "Evidence Direction": "Unknown",
            "Analyst Note": "",
        }
        for key, label in EMPLOYEE_RELATION_DIMENSIONS
    ]


def empty_payload(ticker: str, company_name: str = "") -> dict[str, Any]:
    symbol = str(ticker or "").strip().upper()
    return {
        "ticker": symbol,
        "company_name": str(company_name or "").strip(),
        "source_lock": "Michael Shearn — The Investment Checklist — Chapter 8 — Q39-Q47",
        "question_status": {key: "Unknown" for key in QUESTION_KEYS},
        "confidence": {key: "Unknown" for key in QUESTION_KEYS},
        "analyst_assessment": {key: "Unknown" for key in QUESTION_KEYS},
        "q39_stakeholders": default_stakeholder_rows(),
        "q40_operating_approach": [],
        "q41_guidance_history": [],
        "q42_organization_structure": [],
        "q42_analyst_structure": "Unknown",
        "q43_employee_relations": default_employee_relation_rows(),
        "q44_hiring_evidence": [],
        "q45_cost_actions": [],
        "q46_capital_allocation": [],
        "q47_buyback_history": [],
        "evidence": [],
        "research_gaps": [],
        "management_events": [],
    }


def normalize_payload(payload: dict[str, Any] | None, ticker: str = "", company_name: str = "") -> dict[str, Any]:
    base = empty_payload(ticker or str((payload or {}).get("ticker", "")), company_name or str((payload or {}).get("company_name", "")))
    if not isinstance(payload, dict):
        return base
    out = deepcopy(base)
    for key in out:
        if key in payload:
            out[key] = deepcopy(payload[key])
    out["ticker"] = str(out.get("ticker") or "").strip().upper()
    for q in QUESTION_KEYS:
        if out["question_status"].get(q) not in QUESTION_STATUS_OPTIONS:
            out["question_status"][q] = "Unknown"
        if out["confidence"].get(q) not in CONFIDENCE_OPTIONS:
            out["confidence"][q] = "Unknown"
    if out.get("q42_analyst_structure") not in ORG_STRUCTURE_OPTIONS:
        out["q42_analyst_structure"] = "Unknown"
    return out


def research_gap_warnings(payload: dict[str, Any]) -> list[str]:
    """Return evidence-completeness warnings only; never a competence judgment."""
    data = normalize_payload(payload)
    warnings: list[str] = []
    for q in QUESTION_KEYS:
        if data["question_status"].get(q) in {"Unknown", "Partial"}:
            warnings.append(f"{q}: research remains incomplete; analyst review required.")
    if data["question_status"].get("Q43") == "Answered":
        if not any(str(row.get("Source", "")).strip() for row in data.get("q43_employee_relations", [])):
            warnings.append("Q43: marked Answered but employee-relations evidence has no source.")
    if data["question_status"].get("Q46") == "Answered" and not data.get("q46_capital_allocation"):
        warnings.append("Q46: marked Answered but no capital-allocation history is recorded.")
    if data["question_status"].get("Q47") == "Answered" and not data.get("q47_buyback_history"):
        warnings.append("Q47: marked Answered but no buyback history is recorded.")
    return warnings
