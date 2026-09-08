from __future__ import annotations

"""Michael Shearn Appendix C — Your Investment Checklist.

V96 is a source-lock and full-book architecture-mapping contract only. Appendix C consolidates
Q01-Q59 from the prior research chapters; it is therefore implemented as a referential checklist
index over the existing Deep Company Analysis question SSOT, not as a second answer store,
scoring engine, valuation layer, or investment-decision engine.

Source-locked boundaries
------------------------
- Preserve all 59 Appendix C questions, their wording, ordering, and ten printed section groups.
- Each item points back to its existing chapter/question owner; Appendix C does not copy analyst
  answers, evidence, financial data, formulas, snapshots, confidence, or research-gate state.
- AI remains a Research Assistant. The analyst owns interpretation and every conclusion.
- Missing/unfinished research remains a reference to the owning chapter; Appendix C never fills it.
- No weighted score, management/growth score, BUY/HOLD/SELL signal, intrinsic-value/MOS change,
  Investment Research Gate change, or duplicate financial/company SSOT is introduced here.
"""

from typing import Final, Iterable

APPENDIX_KEY: Final[str] = "C"
APPENDIX_TITLE: Final[str] = "Your Investment Checklist"
SOURCE_LOCK: Final[str] = "Michael Shearn — The Investment Checklist — Appendix C — Q01-Q59"
SOURCE_PRINT_PAGES: Final[tuple[int, int]] = (335, 338)
QUESTION_RANGE: Final[tuple[int, int]] = (1, 59)
QUESTION_COUNT: Final[int] = 59

SECTION_ORDER: Final[tuple[str, ...]] = (
    "understanding_business_basics",
    "customer_perspective",
    "business_industry_strengths_weaknesses",
    "operating_financial_health",
    "distribution_of_earnings_cash_flows",
    "management_background_classification",
    "management_competence",
    "management_positive_negative_traits",
    "growth_opportunities",
    "mergers_acquisitions",
)

SECTION_TITLES: Final[dict[str, str]] = {
    "understanding_business_basics": "Understanding the Business—The Basics",
    "customer_perspective": "Understanding the Business—from the Customer Perspective",
    "business_industry_strengths_weaknesses": "Evaluating the Strengths and Weaknesses of a Business and Industry",
    "operating_financial_health": "Measuring the Operating and Financial Health of the Business",
    "distribution_of_earnings_cash_flows": "Evaluating the Distribution of Earnings (Cash Flows)",
    "management_background_classification": "Assessing the Quality of Management—Background and Classification: Who Are They?",
    "management_competence": "Assessing the Quality of Management—Competence: How Management Operates the Business",
    "management_positive_negative_traits": "Assessing the Quality of Management—Positive and Negative Traits",
    "growth_opportunities": "Evaluating Growth Opportunities",
    "mergers_acquisitions": "Evaluating Mergers & Acquisitions",
}

# Appendix C is the book's consolidated index of prior chapter questions.
# owner_chapter is a reference only; it does not create another state store.
_SECTION_SPECS: Final[tuple[tuple[str, int, tuple[str, ...]], ...]] = (
    ("understanding_business_basics", 2, (
        "Do I want to spend a lot of time learning about this business?",
        "How would you evaluate this business if you were to become its CEO?",
        "Can you describe how the business operates, in your own words?",
        "How does the business make money?",
        "How has the business evolved over time?",
        "In what foreign markets does the business operate, and what are the risks of operating in these countries?",
    )),
    ("customer_perspective", 3, (
        "Who is the core customer of the business?",
        "Is the customer base concentrated or diversified?",
        "Is it easy or difficult to convince customers to buy the products or services?",
        "What is the customer retention rate for the business?",
        "What are the signs a business is customer oriented?",
        "What pain does the business alleviate for the customer?",
        "To what degree is the customer dependent on the products or services from the business?",
        "If the business disappeared tomorrow, what impact would this have on the customer base?",
    )),
    ("business_industry_strengths_weaknesses", 4, (
        "Does the business have a sustainable competitive advantage and what is its source?",
        "Does the business possess the ability to raise prices without losing customers?",
        "Does the business operate in a good or bad industry?",
        "How has the industry evolved over time?",
        "What is the competitive landscape, and how intense is the competition?",
        "What type of relationship does the business have with its suppliers?",
    )),
    ("operating_financial_health", 5, (
        "What are the fundamentals of the business?",
        "What are the operating metrics of the business that you need to monitor?",
        "What are the key risks the business faces?",
        "How does inflation affect the business?",
        "Is the business’s balance sheet strong or weak?",
        "What is the return on invested capital for the business?",
    )),
    ("distribution_of_earnings_cash_flows", 6, (
        "Are the accounting standards that management uses conservative or liberal?",
        "Does the business generate revenues that are recurring or from one-off transactions?",
        "To what degree is the business cyclical, countercyclical, or recession-resistant?",
        "To what degree does operating leverage impact the earnings of the business?",
        "How does working capital impact the cash flows of the business?",
        "Does the business have high or low capital-expenditure requirements?",
    )),
    ("management_background_classification", 7, (
        "What type of manager is leading the company?",
        "What are the effects on the business of bringing in outside management?",
        "Is the manager a lion or a hyena?",
        "How did the manager rise to lead the business?",
        "How are senior managers compensated, and how did they gain their ownership interest?",
        "Have the managers been buying or selling the stock?",
    )),
    ("management_competence", 8, (
        "Does the CEO manage the business to benefit all stakeholders?",
        "Does the management team improve its operations day-to-day or does it use a strategic plan to conduct its business?",
        "Do the CEO and CFO issue guidance regarding earnings?",
        "Is the business managed in a centralized or decentralized way?",
        "Does management value its employees?",
        "Does the management team know how to hire well?",
        "Does the management team focus on cutting unnecessary costs?",
        "Are the CEO and CFO disciplined in making capital-allocation decisions?",
        "Do the CEO and CFO buy back stock opportunistically?",
    )),
    ("management_positive_negative_traits", 9, (
        "Does the CEO love the money or the business?",
        "Can you identify a moment of integrity for the manager?",
        "Are managers clear and consistent in their communications and actions with stakeholders?",
        "Does management think independently and remain unswayed by what others in their industry are doing?",
        "Is the CEO self-promoting?",
    )),
    ("growth_opportunities", 10, (
        "Does the business grow through mergers and acquisitions, or does it grow organically?",
        "What is the management team’s motivation to grow the business?",
        "Has historical growth been profitable and will it continue?",
        "What are the future growth prospects for the business?",
        "Is the management team growing the business too quickly or at a steady pace?",
    )),
    ("mergers_acquisitions", 11, (
        "How does management make M&A decisions?",
        "Have past acquisitions been successful?",
    )),
)


def _build_items() -> tuple[dict[str, object], ...]:
    items: list[dict[str, object]] = []
    number = 1
    for section_key, owner_chapter, questions in _SECTION_SPECS:
        for question in questions:
            qid = f"Q{number:02d}"
            items.append({
                "question_id": qid,
                "question": question,
                "section_key": section_key,
                "section_title": SECTION_TITLES[section_key],
                "owner_chapter": owner_chapter,
                "ssot_reference": qid,
            })
            number += 1
    return tuple(items)


CHECKLIST_ITEMS: Final[tuple[dict[str, object], ...]] = _build_items()
QUESTION_IDS: Final[tuple[str, ...]] = tuple(str(item["question_id"]) for item in CHECKLIST_ITEMS)
QUESTION_TITLES: Final[dict[str, str]] = {
    str(item["question_id"]): str(item["question"]) for item in CHECKLIST_ITEMS
}
SECTION_COUNTS: Final[dict[str, int]] = {
    key: sum(1 for item in CHECKLIST_ITEMS if item["section_key"] == key) for key in SECTION_ORDER
}
OWNER_CHAPTER_BY_QUESTION: Final[dict[str, int]] = {
    str(item["question_id"]): int(item["owner_chapter"]) for item in CHECKLIST_ITEMS
}


def get_item(question_id: str) -> dict[str, object] | None:
    """Return Appendix C metadata for one existing DCA question reference."""
    qid = str(question_id or "").strip().upper()
    for item in CHECKLIST_ITEMS:
        if item["question_id"] == qid:
            return dict(item)
    return None


def items_for_section(section_key: str) -> tuple[dict[str, object], ...]:
    """Return source-ordered checklist references for one Appendix C section."""
    key = str(section_key or "").strip()
    return tuple(dict(item) for item in CHECKLIST_ITEMS if item["section_key"] == key)


def ssot_references(question_ids: Iterable[str] | None = None) -> tuple[str, ...]:
    """Return canonical Qxx references only; no answer/evidence state is copied into Appendix C."""
    if question_ids is None:
        return QUESTION_IDS
    requested = {str(q or "").strip().upper() for q in question_ids}
    return tuple(qid for qid in QUESTION_IDS if qid in requested)


def validate_source_lock() -> tuple[str, ...]:
    """Return deterministic source-lock errors. Empty tuple means the Appendix C contract is valid."""
    errors: list[str] = []
    expected_ids = tuple(f"Q{i:02d}" for i in range(1, QUESTION_COUNT + 1))
    if QUESTION_IDS != expected_ids:
        errors.append("Question IDs must be continuous Q01-Q59 in book order.")
    if len(CHECKLIST_ITEMS) != QUESTION_COUNT or len(set(QUESTION_IDS)) != QUESTION_COUNT:
        errors.append("Appendix C must contain exactly 59 unique questions.")
    if tuple(SECTION_COUNTS) != SECTION_ORDER:
        errors.append("Appendix C section order differs from the source.")
    if sum(SECTION_COUNTS.values()) != QUESTION_COUNT:
        errors.append("Appendix C section counts must sum to 59.")
    if any(item["ssot_reference"] != item["question_id"] for item in CHECKLIST_ITEMS):
        errors.append("Every Appendix C item must reference, not duplicate, its owning Qxx SSOT.")
    return tuple(errors)


__all__ = [
    "APPENDIX_KEY", "APPENDIX_TITLE", "CHECKLIST_ITEMS", "OWNER_CHAPTER_BY_QUESTION",
    "QUESTION_COUNT", "QUESTION_IDS", "QUESTION_RANGE", "QUESTION_TITLES", "SECTION_COUNTS",
    "SECTION_ORDER", "SECTION_TITLES", "SOURCE_LOCK", "SOURCE_PRINT_PAGES", "get_item",
    "items_for_section", "ssot_references", "validate_source_lock",
]
