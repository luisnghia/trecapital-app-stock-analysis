from __future__ import annotations

"""Michael Shearn Chapter 10 — Evaluating Growth Opportunities.

Phase 10B extends the Phase 10A source contract by locking the evidence dimensions explicitly
supported by Chapter 10 (Q53-Q57). It remains a neutral research schema: no automatic growth
forecast, growth-quality score, valuation conclusion, MOS change, Research Gate change, or
BUY/HOLD/SELL signal is created.

Boundaries
----------
- AI/Data may organize evidence; the analyst owns every qualitative conclusion.
- Missing evidence remains Unknown / a research gap.
- Source dimensions are descriptive research requirements, not weighted factors.
- Financial metrics named by the book are dependency labels only in 10B; calculations must be
  supplied by the canonical financial/data SSOT in later bridge phases.
- Phase 10B adds no Streamlit UI, database/store, web research, valuation bridge, portfolio action,
  or duplicate financial SSOT.
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
QUESTION_SOURCE_PAGE_RANGES: dict[str, tuple[int, int]] = {
    "Q53": (281, 282),
    "Q54": (282, 283),
    "Q55": (283, 284),
    "Q56": (284, 296),
    "Q57": (296, 303),
}
SOURCE_LOCK = "Michael Shearn — The Investment Checklist — Chapter 10 — Q53-Q57"
SOURCE_QUESTION_RANGE = "Q53-Q57"
SOURCE_EDITION_NOTE = "Wiley 2012; Chapter 10 printed pages 281-303"

QUESTION_STATUS_OPTIONS = ("Unknown", "Partial", "Answered", "N/A")
CONFIDENCE_OPTIONS = ("Unknown", "Low", "Medium", "High")
DIMENSION_STATUS_OPTIONS = ("Unknown", "Evidence found", "Not found", "N/A")
EVIDENCE_DIRECTION_OPTIONS = ("Supporting", "Counter", "Neutral", "Mixed", "Unknown")
GROWTH_MODE_OPTIONS = ("Unknown", "Organic", "Selective acquirer", "Serial acquirer", "Mixed", "N/A")

QUESTION_RESEARCH_FOCUS: dict[str, str] = {
    "Q53": "Growth route, acquisition intensity, acquisition risk, and whether reported growth is material to the existing revenue base.",
    "Q54": "Management's motivation and pressure to grow, especially growth outside the core business or area of expertise.",
    "Q55": "Whether unit growth translated into gross margin, operating margin, and operating-profit-per-unit economics over time.",
    "Q56": "Duration, runway, replicability, secular/innovation drivers, market-size evidence, slowing-growth signals, and management continuity.",
    "Q57": "Whether growth is disciplined and supportable by internal funding, working capital, economics, people, infrastructure, and location quality.",
}

# Every dimension below is traceable to Chapter 10 printed pages 281-303. These are research
# dimensions only; order does not imply weight and no dimension carries an automatic score.
EVIDENCE_DIMENSIONS: dict[str, tuple[dict[str, Any], ...]] = {
    "Q53": (
        {"id": "q53_acquisition_spend_vs_cfo", "label": "Acquisition spend as a percentage of cash flow from operations over 5-10 years", "pages": (281, 282), "anchor": "Acquisitions subsection in the investing section of the cash-flow statement", "ssot_dependency": "cash_flow_operations; acquisition_cash_spend"},
        {"id": "q53_growth_style_continuum", "label": "Organic vs selective-acquirer vs serial-acquirer growth style", "pages": (281, 282), "anchor": "Continuum of growth styles", "ssot_dependency": "none"},
        {"id": "q53_acquisition_risks", "label": "Acquisition risks: overpayment, leverage, and integration difficulty", "pages": (282, 282), "anchor": "Risks associated with acquisitions", "ssot_dependency": "debt; acquisition_cash_spend"},
        {"id": "q53_growth_materiality_to_revenue", "label": "Growth contribution placed in context of the existing revenue base", "pages": (282, 282), "anchor": "Place growth in context to revenues", "ssot_dependency": "revenue; segment_revenue"},
    ),
    "Q54": (
        {"id": "q54_pressure_to_grow", "label": "Evidence that management is under pressure to grow top-line or support the stock price", "pages": (282, 283), "anchor": "Pressure on management teams to grow", "ssot_dependency": "none"},
        {"id": "q54_core_growth_slowdown", "label": "Whether pursuit of new growth coincides with slowing core-business growth", "pages": (282, 283), "anchor": "If growth of the core business slows", "ssot_dependency": "revenue; segment_revenue"},
        {"id": "q54_outside_core_initiatives", "label": "New initiatives or acquisitions outside the core business / area of expertise", "pages": (282, 283), "anchor": "Growth initiatives outside of its core business", "ssot_dependency": "none"},
        {"id": "q54_focus_and_reversal_cost", "label": "Evidence of management distraction, later sale, closure, or reversal of non-core growth initiatives", "pages": (283, 283), "anchor": "Spend valuable time selling or closing them", "ssot_dependency": "none"},
    ),
    "Q55": (
        {"id": "q55_unit_growth_vs_gross_margin", "label": "Unit growth compared with gross margin over 3-5 years", "pages": (283, 284), "anchor": "Compare gross ... margins to unit growth", "ssot_dependency": "gross_margin; operating_units"},
        {"id": "q55_unit_growth_vs_operating_margin", "label": "Unit growth compared with operating margin over 3-5 years", "pages": (284, 284), "anchor": "Compare ... operating income margins to unit growth", "ssot_dependency": "operating_margin; operating_units"},
        {"id": "q55_operating_profit_per_unit", "label": "Operating-income growth and operating profit per unit/transaction", "pages": (284, 284), "anchor": "Compare operating income growth to unit growth", "ssot_dependency": "operating_income; operating_units"},
        {"id": "q55_profitability_persistence", "label": "Evidence whether historical profitable or less-profitable growth economics are likely to continue", "pages": (284, 284), "anchor": "Determine whether this is a trend that will continue", "ssot_dependency": "none"},
    ),
    "Q56": (
        {"id": "q56_management_disclosed_opportunities", "label": "Growth opportunities disclosed in business description and MD&A", "pages": (284, 284), "anchor": "Business description section and MD&A", "ssot_dependency": "none"},
        {"id": "q56_growth_duration_and_runway", "label": "Number of years growth can be sustained, not merely the single-year growth rate", "pages": (284, 285), "anchor": "Number of years it can grow at any rate", "ssot_dependency": "none"},
        {"id": "q56_replicability_and_saturation", "label": "Replicability across geography and evidence of location/customer saturation", "pages": (285, 285), "anchor": "Can be replicated broadly ... saturation point", "ssot_dependency": "operating_units"},
        {"id": "q56_operating_driver_vs_earnings", "label": "Earnings growth compared with a relevant operating metric to identify sustainable underlying drivers", "pages": (285, 286), "anchor": "Place earnings growth next to the specific metric of a business", "ssot_dependency": "eps; industry_operating_metric"},
        {"id": "q56_secular_vs_cyclical", "label": "Secular demand trend distinguished from shorter-term business-cycle changes", "pages": (286, 288), "anchor": "Is the business growing because of secular trends?", "ssot_dependency": "none"},
        {"id": "q56_price_vs_unit_growth", "label": "Commodity-price contribution separated from unit growth over at least 3-5 years where relevant", "pages": (287, 287), "anchor": "Commodity prices versus changes in unit growth", "ssot_dependency": "revenue; operating_units; commodity_price"},
        {"id": "q56_secular_trend_measurement", "label": "Specific demographic/social evidence that measures the secular trend supporting demand", "pages": (288, 289), "anchor": "Identify and measure the secular growth trends", "ssot_dependency": "none"},
        {"id": "q56_rd_commitment", "label": "Management commitment to innovation measured by R&D expense as a percentage of sales over time", "pages": (289, 289), "anchor": "Is innovation a management priority?", "ssot_dependency": "rd_expense; revenue"},
        {"id": "q56_rd_output_success", "label": "R&D effectiveness measured by the percentage of sales generated from new products/services", "pages": (289, 291), "anchor": "Are R&D efforts successful?", "ssot_dependency": "new_product_revenue; revenue"},
        {"id": "q56_transformational_product_validation", "label": "Customer and channel evidence for transformational products when historical patterns are unavailable", "pages": (291, 292), "anchor": "Survey target customers ... message boards ... salespeople", "ssot_dependency": "none"},
        {"id": "q56_market_size_share_integrity", "label": "Market size/share opportunity with consistent definitions and cross-checks against competitors", "pages": (292, 294), "anchor": "Using market share figures to extrapolate ... figure out how market share figures are calculated", "ssot_dependency": "revenue; market_size"},
        {"id": "q56_effective_market_quality", "label": "Whether apparent market-share runway is distorted by redefinition, overlapping segments, geography, informal markets, or a shrinking effective market", "pages": (292, 294), "anchor": "Watch out for shrinking effective markets ... overlapping segments, distribution, and geography", "ssot_dependency": "market_size"},
        {"id": "q56_growth_slowing_signals", "label": "Slowing-growth signals: new customer base, core-model change, or higher dividend payout", "pages": (294, 295), "anchor": "Watch for signs that growth is slowing", "ssot_dependency": "dividends_paid; earnings"},
        {"id": "q56_price_expectation_risk", "label": "Evidence that expected growth embedded in valuation may be vulnerable to multiple compression if growth slows", "pages": (295, 296), "anchor": "Beware of paying too high a price for growth", "ssot_dependency": "pe_ratio; eps"},
        {"id": "q56_management_continuity", "label": "Whether the management team responsible for historical growth remains intact", "pages": (296, 296), "anchor": "Management team ... responsible for historical growth still leading", "ssot_dependency": "none"},
    ),
    "Q57": (
        {"id": "q57_disciplined_growth_pace", "label": "Evidence that growth is controlled and disciplined rather than steep and undisciplined", "pages": (296, 297), "anchor": "Disciplined or undisciplined growth strategy", "ssot_dependency": "none"},
        {"id": "q57_internal_funding_capacity", "label": "Extent to which growth is funded by internally generated cash rather than debt or equity", "pages": (297, 298), "anchor": "Is the business growing within its means?", "ssot_dependency": "cash_flow_operations; debt_issuance; equity_issuance"},
        {"id": "q57_cash_conversion_cycle", "label": "Cash-conversion cycle evidence (DIO + DSO - DPO) as a constraint on internal funding speed", "pages": (297, 298), "anchor": "Calculate the cash-conversion cycle", "ssot_dependency": "dio; dso; dpo; ccc"},
        {"id": "q57_growth_investment_payback", "label": "Short-term earnings drag from growth investments and time until new investments reach profitability", "pages": (298, 299), "anchor": "Growing at the expense of short-term earnings", "ssot_dependency": "cash_flow_operations; capex; operating_income"},
        {"id": "q57_human_capital_capacity", "label": "Ability to hire, train, retain, and internally develop enough qualified people to support expansion", "pages": (299, 300), "anchor": "Growing within the limits of its human capital", "ssot_dependency": "employee_count; operating_units"},
        {"id": "q57_infrastructure_capacity", "label": "Finance, operations, human-resources, and technology infrastructure capacity to support growth", "pages": (300, 301), "anchor": "Does the business have the proper infrastructure to grow?", "ssot_dependency": "none"},
        {"id": "q57_location_discipline", "label": "Opportunistic location selection and return discipline rather than opening sites merely to hit growth targets", "pages": (301, 302), "anchor": "Is the business finding the right locations?", "ssot_dependency": "operating_units; return_on_capital"},
    ),
}

EVIDENCE_COLUMNS = [
    "Question", "Dimension ID", "Dimension", "Observation / Claim", "Period / Date",
    "Metric / Growth Driver", "Source Grade", "Source Title", "Source URL / File", "Source Date",
    "As-of Date", "Evidence Text / Reference", "Direction", "Status", "Analyst Note",
]
RESEARCH_GAP_COLUMNS = ["Question", "Dimension ID", "Research Gap", "Materiality", "Next Action", "Status", "Analyst Note"]
GROWTH_EVENT_COLUMNS = ["Event Date", "Publication Date", "Event Type", "Observed Event / Change", "Questions Potentially Affected", "Source", "Analyst Review Status", "Analyst Note"]


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
        "growth_mode": "Unknown",
        "dimension_status": {dim_id: "Unknown" for dim_id in dimension_ids()},
        "evidence": [],
        "research_gaps": [],
        "growth_events": [],
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
    for field in ("question_status", "confidence", "analyst_assessment", "dimension_status"):
        if not isinstance(out.get(field), dict):
            out[field] = {}
    for question in QUESTION_KEYS:
        if out["question_status"].get(question) not in QUESTION_STATUS_OPTIONS:
            out["question_status"][question] = "Unknown"
        if out["confidence"].get(question) not in CONFIDENCE_OPTIONS:
            out["confidence"][question] = "Unknown"
        if question not in out["analyst_assessment"]:
            out["analyst_assessment"][question] = "Unknown"
    for dim_id in dimension_ids():
        if out["dimension_status"].get(dim_id) not in DIMENSION_STATUS_OPTIONS:
            out["dimension_status"][dim_id] = "Unknown"
    out["dimension_status"] = {dim_id: out["dimension_status"][dim_id] for dim_id in dimension_ids()}
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
    "CHAPTER_NUMBER", "CHAPTER_TITLE", "CONFIDENCE_OPTIONS", "DIMENSION_STATUS_OPTIONS",
    "EVIDENCE_COLUMNS", "EVIDENCE_DIMENSIONS", "EVIDENCE_DIRECTION_OPTIONS", "GROWTH_EVENT_COLUMNS",
    "GROWTH_MODE_OPTIONS", "QUESTION_KEYS", "QUESTION_RESEARCH_FOCUS", "QUESTION_SOURCE_PAGES",
    "QUESTION_SOURCE_PAGE_RANGES", "QUESTION_STATUS_OPTIONS", "QUESTION_TITLES", "RESEARCH_GAP_COLUMNS",
    "SOURCE_EDITION_NOTE", "SOURCE_LOCK", "SOURCE_QUESTION_RANGE", "dimension_catalog",
    "dimension_count_by_question", "dimension_ids", "empty_payload", "normalize_payload", "research_gap_warnings",
]
