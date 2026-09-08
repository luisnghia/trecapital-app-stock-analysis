from __future__ import annotations

"""Michael Shearn Chapter 11 — Evaluating Mergers & Acquisitions.

Phase 11B extends the Phase 11A source lock with evidence dimensions explicitly traceable to
Chapter 11 (Q58-Q59). The dimensions are neutral research requirements, not a scorecard.
AI/Data may organize evidence, but the analyst owns every qualitative conclusion.

Boundaries
----------
- Missing evidence remains Unknown / a research gap.
- Dimension order does not imply weight and dimensions never auto-produce an M&A score.
- Financial terms named by the book are dependency labels only; later phases must use canonical
  financial/data SSOT rather than recomputing acquisition returns, leverage, FCF, EBITDA, or book value.
- No automatic acquisition-success conclusion, synergy forecast, intrinsic value, MOS, Research Gate,
  portfolio action, BUY/HOLD/SELL, web research, database/store, or Streamlit UI is introduced here.
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
QUESTION_SOURCE_PAGES: dict[str, int] = {"Q58": 305, "Q59": 310}
QUESTION_SOURCE_PAGE_RANGES: dict[str, tuple[int, int]] = {
    "Q58": (305, 310),
    "Q59": (310, 322),
}
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Chapter 11 — Q58-Q59"
SOURCE_QUESTION_RANGE = "Q58-Q59"
SOURCE_EDITION_NOTE = "Wiley 2012; Chapter 11 printed pages 305-322"

QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
DIMENSION_STATUS_OPTIONS = ("Unknown", "Evidence found", "Not found", "N/A")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")

QUESTION_RESEARCH_FOCUS: dict[str, str] = {
    "Q58": "How and why management makes acquisition decisions: rationale, motivation, fit, expected benefits, costs, risks, synergy assumptions, and roll-up discipline.",
    "Q59": "Whether past acquisitions were successful using Shearn's seven evaluation lenses: core fit, operating understanding, customer retention, employee retention, price discipline, price paid, and financing.",
}

# Every dimension below is traceable to Chapter 11 printed pages 305-322.
# They are research dimensions only; no ordering or field carries an automatic weight or conclusion.
EVIDENCE_DIMENSIONS: dict[str, tuple[dict[str, Any], ...]] = {
    "Q58": (
        {
            "id": "q58_decision_process_and_rationale",
            "label": "How management reached the acquisition decision: merits, prospects, costs, risks, and stated rationale",
            "pages": (305, 307),
            "anchor": "Understand how acquisition decisions are made as well as why they are made",
            "ssot_dependency": "none",
        },
        {
            "id": "q58_management_motivation",
            "label": "Management motivation: customer/economic logic versus size, ego, excitement, or empire building",
            "pages": (307, 307),
            "anchor": "What Is the Motivation Behind an Acquisition?",
            "ssot_dependency": "none",
        },
        {
            "id": "q58_core_vs_unrelated_direction",
            "label": "Whether acquisition activity stays close to the core business/customer base or drifts into unrelated businesses",
            "pages": (307, 307),
            "anchor": "Acquiring a similar customer base generally carries less risk than unrelated expansion",
            "ssot_dependency": "segment_revenue",
        },
        {
            "id": "q58_revenue_synergy_assumptions",
            "label": "Revenue-synergy assumptions: cross-selling, new-market access, or pricing power, with evidence that customers actually behave as assumed",
            "pages": (307, 309),
            "anchor": "Revenue synergies and skepticism that promised increases will materialize",
            "ssot_dependency": "revenue; segment_revenue",
        },
        {
            "id": "q58_cost_synergy_assumptions",
            "label": "Cost-synergy assumptions: overhead, procurement, margin, tax, and other efficiencies, including evidence of realizability",
            "pages": (308, 309),
            "anchor": "Cost synergies are generally easier than revenue synergies but still require verification",
            "ssot_dependency": "operating_expenses; operating_margin",
        },
        {
            "id": "q58_customer_overlap_synergy_fit",
            "label": "Whether the merged businesses serve the same or compatible customers, a key condition for synergy realization",
            "pages": (309, 310),
            "anchor": "Synergies are least likely when businesses serve different customers or unrelated areas",
            "ssot_dependency": "none",
        },
        {
            "id": "q58_rollup_economics_and_leverage",
            "label": "Roll-up thesis and risks: duplicate-cost savings, purchasing power, advertising, financing leverage, and whether economics actually materialize",
            "pages": (309, 310),
            "anchor": "Roll-ups often fail to create value, especially when substantial debt is used",
            "ssot_dependency": "debt; interest_expense; operating_margin",
        },
        {
            "id": "q58_small_deal_predictive_pattern",
            "label": "Consistency of management's reasoning across small historical deals as evidence for how larger future acquisitions may be approached",
            "pages": (305, 307),
            "anchor": "Past acquisition reasoning can reduce uncertainty about future capital-allocation behavior",
            "ssot_dependency": "none",
        },
    ),
    "Q59": (
        {
            "id": "q59_core_competency_fit",
            "label": "1/7 — Acquisition fit with the core competencies, including distribution and sales method fit, not merely product similarity",
            "pages": (311, 312),
            "anchor": "Do Acquisitions Fit into the Core Competencies of the Business?",
            "ssot_dependency": "none",
        },
        {
            "id": "q59_management_understands_target",
            "label": "2/7 — Whether management intimately understands the target's industry, operations, customers, competitors, and improvement opportunities before buying",
            "pages": (312, 313),
            "anchor": "Does the Management Team Intimately Understand the Business It Is Acquiring?",
            "ssot_dependency": "none",
        },
        {
            "id": "q59_customer_retention",
            "label": "3/7 — Customer retention after acquisition, with a multi-year view where available",
            "pages": (313, 313),
            "anchor": "Does the Business Retain Its Customers After an Acquisition?",
            "ssot_dependency": "customer_retention",
        },
        {
            "id": "q59_employee_retention",
            "label": "4/7 — Employee/talent retention, culture preservation, communication, incentives, and treatment of acquired employees",
            "pages": (313, 315),
            "anchor": "Does the Business Retain Its Employees After an Acquisition?",
            "ssot_dependency": "employee_count; employee_turnover",
        },
        {
            "id": "q59_price_discipline_and_walkaway",
            "label": "5/7 — Management discipline against overpaying, including auction pressure, transformational-deal risk, market timing, and willingness to walk away",
            "pages": (315, 318),
            "anchor": "Does Management Have Discipline or Is There a Risk That They Will Overpay?",
            "ssot_dependency": "none",
        },
        {
            "id": "q59_price_paid_and_postdeal_economics",
            "label": "6/7 — Price paid and post-deal economics: consideration, EV/EBIT, EV/EBITDA, EV/FCF, book-value premium, and whether acquired earnings/cash flows support the price",
            "pages": (318, 320),
            "anchor": "Evaluating the Price Paid",
            "ssot_dependency": "acquisition_consideration; ebit; ebitda; free_cash_flow; book_value",
        },
        {
            "id": "q59_financing_and_risk_tolerance",
            "label": "7/7 — How the acquisition was financed: cash, debt, equity, or combination; leverage/refinancing risk and dilution from stock consideration",
            "pages": (320, 322),
            "anchor": "How Is the Acquisition Financed?",
            "ssot_dependency": "cash; debt; debt_coverage; free_cash_flow; equity_issuance; shares_outstanding",
        },
    ),
}

EVIDENCE_COLUMNS = [
    "Question", "Dimension ID", "Dimension", "Observation / Claim", "Period / Date",
    "M&A Topic", "Source Grade", "Source Title", "Source URL / File", "Source Date",
    "As-of Date", "Evidence Text / Reference", "Direction", "Status", "Analyst Note",
]
RESEARCH_GAP_COLUMNS = ["Question", "Dimension ID", "Research Gap", "Materiality", "Next Action", "Status", "Analyst Note"]
MA_EVENT_COLUMNS = ["Event Date", "Publication Date", "Target / Transaction", "Observed Event / Change", "Questions Potentially Affected", "Source", "Analyst Review Status", "Analyst Note"]


def dimension_ids(question: str | None = None) -> tuple[str, ...]:
    questions = (question,) if question in QUESTION_KEYS else QUESTION_KEYS
    return tuple(item["id"] for key in questions for item in EVIDENCE_DIMENSIONS[key])


def dimension_count_by_question() -> dict[str, int]:
    return {key: len(EVIDENCE_DIMENSIONS[key]) for key in QUESTION_KEYS}


def dimension_catalog() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for question in QUESTION_KEYS:
        for position, item in enumerate(EVIDENCE_DIMENSIONS[question], start=1):
            row = deepcopy(item)
            row["question"] = question
            row["position"] = position
            rows.append(row)
    return rows


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
        "dimension_status": {dim_id: "Unknown" for dim_id in dimension_ids()},
        "evidence": [],
        "research_gaps": [],
        "ma_events": [],
    }


def normalize_payload(payload: dict[str, Any] | None, ticker: str = "", company_name: str = "") -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    base = empty_payload(ticker or str(source.get("ticker", "")), company_name or str(source.get("company_name", "")))
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
    if not isinstance(out.get("dimension_status"), dict):
        out["dimension_status"] = {}
    for question in QUESTION_KEYS:
        if out["question_status"].get(question) not in QUESTION_STATUS_OPTIONS:
            out["question_status"][question] = "Unknown"
        if out["confidence"].get(question) not in CONFIDENCE_OPTIONS:
            out["confidence"][question] = "Unknown"
        if question not in out["analyst_assessment"]:
            out["analyst_assessment"][question] = "Unknown"
    valid_ids = set(dimension_ids())
    out["dimension_status"] = {
        dim_id: (out["dimension_status"].get(dim_id) if out["dimension_status"].get(dim_id) in DIMENSION_STATUS_OPTIONS else "Unknown")
        for dim_id in valid_ids
    }
    for rows_key in ("evidence", "research_gaps", "ma_events"):
        if not isinstance(out.get(rows_key), list):
            out[rows_key] = []
    return out


def research_gap_warnings(payload: dict[str, Any] | None) -> list[str]:
    """Research-completeness warnings only; never an M&A-quality or investment rating."""
    data = normalize_payload(payload or {})
    warnings: list[str] = []
    for question in QUESTION_KEYS:
        if data["question_status"].get(question) in {"Unknown", "Partial"}:
            warnings.append(f"{question}: M&A research remains incomplete; analyst review required.")
        unknown_dims = [item["id"] for item in EVIDENCE_DIMENSIONS[question] if data["dimension_status"].get(item["id"]) == "Unknown"]
        if unknown_dims:
            warnings.append(f"{question}: {len(unknown_dims)} source-locked evidence dimension(s) remain Unknown.")
    return warnings


__all__ = [
    "CHAPTER_NUMBER", "CHAPTER_TITLE", "CONFIDENCE_OPTIONS", "DIMENSION_STATUS_OPTIONS",
    "EVIDENCE_COLUMNS", "EVIDENCE_DIMENSIONS", "EVIDENCE_DIRECTION_OPTIONS", "MA_EVENT_COLUMNS",
    "QUESTION_KEYS", "QUESTION_RESEARCH_FOCUS", "QUESTION_SOURCE_PAGES", "QUESTION_SOURCE_PAGE_RANGES",
    "QUESTION_STATUS_OPTIONS", "QUESTION_TITLES", "RESEARCH_GAP_COLUMNS", "SOURCE_EDITION_NOTE",
    "SOURCE_LOCK", "SOURCE_QUESTION_RANGE", "dimension_catalog", "dimension_count_by_question",
    "dimension_ids", "empty_payload", "normalize_payload", "research_gap_warnings",
]
