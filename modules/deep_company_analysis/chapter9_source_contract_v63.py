from __future__ import annotations

"""Chapter 9 Phase 9B — source-locked evidence dimensions for Q48-Q52.

This module operationalizes the source text in Michael Shearn's *The Investment Checklist*,
Chapter 9, without converting behavioral observations into a score, grade, or investment signal.
It distinguishes exact prompts/named subsections from evidence dimensions derived directly from
explicit source paragraphs. The analyst remains responsible for every qualitative conclusion.

Boundaries
----------
- Chapter 7 remains the manager identity/background SSOT.
- No manager score, weighting, ranking, automatic positive/negative label, MOS, Research Gate,
  or BUY/HOLD/SELL behavior is introduced.
- No UI, database, web-research adapter, or financial-data bridge is introduced in Phase 9B.
- Source examples/red flags are research cues, not deterministic judgments.
"""

from dataclasses import asdict, dataclass
from typing import Any

from modules.deep_company_analysis import chapter9 as ch9


ORIGIN_EXPLICIT_PROMPT = "Explicit prompt"
ORIGIN_NAMED_SUBSECTION = "Named subsection"
ORIGIN_EXPLICIT_TRAIT_LIST = "Explicit trait list"
ORIGIN_SOURCE_PARAGRAPH = "Source paragraph"


@dataclass(frozen=True)
class SourceDimension:
    key: str
    question: str
    label: str
    origin: str
    source_pages: tuple[int, ...]
    evidence_targets: tuple[str, ...] = ()
    red_flags: tuple[str, ...] = ()
    counter_signals: tuple[str, ...] = ()
    analyst_note: str = ""


# Q49: five response patterns explicitly listed in the adversity section on p. 267.
# The fifth pattern is favorable in the source; the first four are adverse patterns.
Q49_ADVERSITY_RESPONSE_PATTERNS: tuple[str, ...] = (
    "Adversity overwhelms management; management evades rather than confronts the problem.",
    "Management blames others or outside events and relies on heavily lawyered / PR-crafted statements instead of acting.",
    "Management strikes back quickly without thinking the response through and may move in the wrong direction.",
    "Management applies a quick remedy that solves the problem only in the short run and fails to follow up.",
    "Management quickly and openly communicates how it is thinking about the problem and outlines how it will solve it for the long term.",
)


# Q50: exact items the book says a useful shareholder letter should describe/explain (p. 269).
Q50_SHAREHOLDER_LETTER_ELEMENTS: tuple[str, ...] = (
    "What is important at their business.",
    "What is driving their decisions.",
    "The issues they have encountered.",
    "The metrics that are important to monitor the health of the business.",
    "How the CEO plans to resolve issues faced by the business.",
)


# Q50: exact four questions explicitly listed after the good-news discussion (p. 273).
Q50_COMMUNICATION_CHECKS: tuple[str, ...] = (
    "Is the manager easy to listen to?",
    "Do you learn from the manager?",
    "Does the manager use corporate speak?",
    "Does the manager use double speak?",
)


# Q52: exact six traits in the source's self-promoter list (p. 277).
Q52_SELF_PROMOTER_TRAITS: tuple[str, ...] = (
    "Flamboyant.",
    "Have lots of charisma.",
    "Engage in aggressive salesmanship.",
    "Tend to command the center of attention.",
    "Take over discussions.",
    "Have an attitude that they are smarter than everybody else.",
)

Q52_WALL_STREET_EVENT_RED_FLAG_TEXT = (
    "If senior managers are present at Wall Street events more than two to four times per month, "
    "the source treats that frequency as a possible promotional warning signal."
)
Q52_FINANCING_CONTEXT_EXCEPTION = (
    "Promotion can be necessary when the business depends on Wall Street to finance expansion, "
    "debt/equity issuance, or acquisitions; financing purpose must therefore be recorded as context."
)


QUESTION_DIMENSIONS: dict[str, tuple[SourceDimension, ...]] = {
    "Q48": (
        SourceDimension(
            "q48_career_vs_job",
            "Q48",
            ch9.Q48_PASSION_RESEARCH_PROMPTS[0],
            ORIGIN_EXPLICIT_PROMPT,
            (257,),
            ("Career chronology", "Industry tenure", "Consistency of prior roles"),
            ("Frequent industry-to-industry jumps without a clear operating thread",),
            ("Long-term involvement in the same field or mission",),
        ),
        SourceDimension(
            "q48_refuse_sale",
            "Q48",
            ch9.Q48_PASSION_RESEARCH_PROMPTS[1],
            ORIGIN_EXPLICIT_PROMPT,
            (258,),
            ("Documented acquisition approaches", "CEO response to sale offers", "Founder control rationale"),
            (),
            ("Documented refusal to sell despite a very high offer because the business/mission comes first",),
        ),
        SourceDimension(
            "q48_money_motivation",
            "Q48",
            ch9.Q48_PASSION_RESEARCH_PROMPTS[2],
            ORIGIN_EXPLICIT_PROMPT,
            (258, 259, 260),
            ("Long-run lifestyle/spending pattern", "Public property records", "In-depth profiles"),
            ("Lifestyle/spending pattern suggesting external money motivation when corroborated by broader evidence",),
            ("Wealth changes materially while personal lifestyle remains comparatively stable",),
            "Lifestyle is an indicator, not definitive proof; the source explicitly requires deeper study.",
        ),
        SourceDimension(
            "q48_appearances_vs_business",
            "Q48",
            ch9.Q48_PASSION_RESEARCH_PROMPTS[3],
            ORIGIN_EXPLICIT_PROMPT,
            (260, 261),
            ("Outside boards", "Social engagements", "Time allocation", "Proxy biography"),
            ("Extensive prestige/social commitments that appear to distract from operating the business",),
            ("Outside activities are limited or clearly tied to a genuine mission rather than status",),
        ),
        SourceDimension(
            "q48_philanthropy",
            "Q48",
            ch9.Q48_PASSION_RESEARCH_PROMPTS[4],
            ORIGIN_EXPLICIT_PROMPT,
            (262, 263),
            ("Foundation Form 990", "Giving history", "Nonprofit affiliations", "Corporate giving"),
            ("Social-scene philanthropy or use of corporate assets mainly to improve personal social standing",),
            ("Long-run giving pattern is consistent with a genuine mission and not merely social recognition",),
            "Philanthropy is a window into priorities, not proof of ethics; the source gives explicit counterexamples.",
        ),
        SourceDimension(
            "q48_lifelong_learning",
            "Q48",
            ch9.Q48_PASSION_RESEARCH_PROMPTS[5],
            ORIGIN_EXPLICIT_PROMPT,
            (263, 264),
            ("Repeated improvement initiatives", "Learning behavior", "Response to technological/market change"),
            ("Complacency; treating past success as final; refusing to adapt to important change",),
            ("Continual improvement and treating success as a base for further learning",),
        ),
    ),
    "Q49": (
        SourceDimension(
            "q49_words_actions_consistency",
            "Q49",
            "Consistency between what the manager says and what the manager does",
            ORIGIN_SOURCE_PARAGRAPH,
            (264,),
            ("Repeated public statements", "Subsequent actions", "Standards set for others vs personal behavior"),
            ("Says one thing and acts differently", "Sets standards or performance expectations and personally violates them"),
            ("Repeated statements remain consistent with later actions",),
        ),
        SourceDimension(
            "q49_integrity_moment",
            "Q49",
            "Documented moment of integrity under stress, adversity, crisis, or an ethical situation",
            ORIGIN_SOURCE_PARAGRAPH,
            (264, 265),
            ("Difficult situation", "Decision/action taken", "Who bore the cost/benefit", "Contemporaneous source"),
            ("No documented integrity moment means the behavior remains unknown; it is not evidence of bad character",),
            ("Manager follows the stated/right path when adverse incentives make that costly or difficult",),
        ),
        SourceDimension(
            "q49_adversity_response_pattern",
            "Q49",
            "How management responds when the business encounters a difficult situation",
            ORIGIN_EXPLICIT_TRAIT_LIST,
            (266, 267),
            ("Economic downturn", "Product recall", "Negative media", "Lawsuit", "Press releases", "Conference-call transcripts"),
            Q49_ADVERSITY_RESPONSE_PATTERNS[:4],
            (Q49_ADVERSITY_RESPONSE_PATTERNS[4],),
        ),
        SourceDimension(
            "q49_long_term_problem_solving",
            "Q49",
            "Whether the response solves the underlying problem for the long term rather than only applying a quick remedy",
            ORIGIN_SOURCE_PARAGRAPH,
            (266, 267, 268),
            ("Initial response", "Follow-up action", "Outcome over time", "Communication with affected stakeholders"),
            ("Quick remedy without follow-up", "Reactive action taken mainly to make the immediate problem disappear"),
            ("Calm, intentional response with open communication and durable follow-through",),
        ),
    ),
    "Q50": (
        SourceDimension(
            "q50_shareholder_letters",
            "Q50",
            "Sequential annual-report shareholder letters",
            ORIGIN_NAMED_SUBSECTION,
            (269,),
            Q50_SHAREHOLDER_LETTER_ELEMENTS,
            ("Letter reads like PR copy or duplicates MD&A without giving insight into how the CEO thinks",),
            ("Clear explanation of business drivers, issues, important metrics, decisions, and planned remedies",),
        ),
        SourceDimension(
            "q50_conference_calls",
            "Q50",
            "Historical conference-call transcripts and question-and-answer behavior",
            ORIGIN_NAMED_SUBSECTION,
            (269, 270, 271),
            ("Direct answers", "Unanswered questions", "Reasons for withholding", "Prepared remarks vs Q&A time"),
            ("Responds without answering", "Uses 'proprietary' as a broad excuse for business-specific questions", "Uses scripts to crowd out Q&A"),
            ("Open answers to business-specific questions", "More time for unscripted shareholder questions"),
        ),
        SourceDimension(
            "q50_adversity_communication",
            "Q50",
            "How managers communicate when confronted with adversity",
            ORIGIN_NAMED_SUBSECTION,
            (271, 272),
            ("Timing", "Candor", "Ownership of mistakes", "Explanation of response"),
            ("Face-saving behavior", "Heavily lawyered releases that avoid the issue", "Hiding behind lack of visibility"),
            ("Open communication during economic or competitive stress", "Acknowledges responsibility and explains response"),
        ),
        SourceDimension(
            "q50_good_news_balance",
            "Q50",
            "Whether management only emphasizes good news in communications",
            ORIGIN_NAMED_SUBSECTION,
            (272, 273),
            ("Good-news/bad-news balance", "GAAP vs adjusted/pro-forma emphasis", "Items selected for prominence"),
            ("Promotes favorable adjusted/pro-forma figures while obscuring materially worse underlying results",),
            ("Presents adverse information with the same clarity as favorable information",),
        ),
        SourceDimension(
            "q50_easy_to_listen",
            "Q50",
            Q50_COMMUNICATION_CHECKS[0],
            ORIGIN_EXPLICIT_PROMPT,
            (273,),
            ("Clarity", "Conversational engagement", "Ability to follow explanation"),
            ("Communication is persistently difficult to follow or feels combative rather than explanatory",),
            (),
        ),
        SourceDimension(
            "q50_learn_from_manager",
            "Q50",
            Q50_COMMUNICATION_CHECKS[1],
            ORIGIN_EXPLICIT_PROMPT,
            (273,),
            ("Operating explanations", "Business-specific teaching", "Evidence of practical understanding"),
            ("Analyst repeatedly feels the need to teach management how its own business should be run",),
            ("Manager's explanations improve the analyst's understanding of how the business is run",),
        ),
        SourceDimension(
            "q50_corporate_speak",
            "Q50",
            Q50_COMMUNICATION_CHECKS[2],
            ORIGIN_EXPLICIT_PROMPT,
            (273, 274),
            ("Use of jargon", "Generic statements", "Ability to explain the business in plain terms"),
            ("Heavy corporate jargon may indicate weak understanding or self-promotion",),
            ("Plain, specific explanations tied to actual business operations",),
            "The source treats jargon as a possible indicator, not standalone proof.",
        ),
        SourceDimension(
            "q50_double_speak",
            "Q50",
            Q50_COMMUNICATION_CHECKS[3],
            ORIGIN_EXPLICIT_PROMPT,
            (274,),
            ("Contradictory statements", "Statement vs disclaimer", "Claim vs subsequent explanation"),
            ("Contradictory statements that cannot be reconciled by the disclosed facts",),
            ("Consistent language across statements and subsequent explanations",),
        ),
    ),
    "Q51": (
        SourceDimension(
            "q51_resist_industry_copying",
            "Q51",
            "Resists copying competitors merely because competitors are earning attractive profits",
            ORIGIN_SOURCE_PARAGRAPH,
            (275,),
            ("Peer behavior", "Management decision not to follow", "Reason for the decision", "Subsequent outcome"),
            ("Chasing an industry profit pool without evidence that it is sustainable or fits the business",),
            ("Maintains a different course when management believes peer behavior is reckless or unsustainable",),
        ),
        SourceDimension(
            "q51_long_term_focus",
            "Q51",
            "Maintains a long-term focus despite shareholder pressure to maximize short-term profits",
            ORIGIN_SOURCE_PARAGRAPH,
            (275,),
            ("Long-horizon investment/operating decision", "Short-term pressure", "Management rationale"),
            ("Abandons a long-term operating advantage mainly to satisfy short-term profit pressure",),
            ("Protects long-term customer/service/culture economics even when a short-term alternative appears financially attractive",),
        ),
        SourceDimension(
            "q51_own_plan_vs_benchmark_copy",
            "Q51",
            "Uses an independent operating plan rather than continually benchmarking against or copying competitors' past success",
            ORIGIN_SOURCE_PARAGRAPH,
            (275, 276),
            ("Benchmarking language", "Copycat products/services", "Customer-need rationale", "Distinct operating insight"),
            ("Announces similar products/services mainly because competitors have been successful", "Copies visible features without understanding the underlying cause of success"),
            ("Plan is grounded in the business's own customers, capabilities, and operating insight",),
        ),
    ),
    "Q52": (
        SourceDimension(
            "q52_self_brand_and_pitch",
            "Q52",
            "Whether the CEO makes themself the brand and relies on a polished pitch / larger-than-life persona",
            ORIGIN_SOURCE_PARAGRAPH,
            (276, 277),
            ("Headline-grabbing projections", "Transformational announcements", "Public persona", "Accomplishment claims"),
            Q52_SELF_PROMOTER_TRAITS,
            ("Collegial, team-oriented, soft-spoken behavior with results rather than persona as the main message",),
        ),
        SourceDimension(
            "q52_wall_street_event_frequency",
            "Q52",
            "Frequency and purpose of Wall Street / sell-side investor-conference attendance",
            ORIGIN_SOURCE_PARAGRAPH,
            (277,),
            ("IR event calendar", "Who attended", "Monthly frequency", "Financing purpose"),
            (Q52_WALL_STREET_EVENT_RED_FLAG_TEXT,),
            ("Limited promotional conference attendance when external financing is not needed",),
        ),
        SourceDimension(
            "q52_media_touting",
            "Q52",
            "Time spent with TV outlets and financial press to promote the company or stock",
            ORIGIN_SOURCE_PARAGRAPH,
            (277, 278),
            ("TV appearances", "Financial-press frequency", "Content of appearances"),
            ("Persistent financial-media presence primarily aimed at bringing attention to the stock",),
            ("CEO spends little time promoting and focuses more directly on the business, employees, and customers",),
        ),
        SourceDimension(
            "q52_stock_price_focus",
            "Q52",
            "Whether the CEO focuses on the stock price rather than the underlying business",
            ORIGIN_SOURCE_PARAGRAPH,
            (278,),
            ("Public goals", "Annual-report language", "Statements about stock-price performance", "Acquisition financing dependence"),
            ("Treats stock-price performance itself as a central operating goal",),
            ("Communications emphasize business results and long-term operating objectives rather than stock-price targets",),
        ),
        SourceDimension(
            "q52_financing_context",
            "Q52",
            "Whether external promotion is necessary because Wall Street financing is required",
            ORIGIN_SOURCE_PARAGRAPH,
            (277,),
            ("Debt/equity issuance", "Acquisition financing", "Expansion funding need", "Conference purpose"),
            (),
            (Q52_FINANCING_CONTEXT_EXCEPTION,),
            "This is an explicit source exception/context control so necessary financing activity is not misclassified as self-promotion.",
        ),
    ),
}


SOURCE_EVIDENCE_FAMILIES: dict[str, tuple[str, ...]] = {
    "Q48": (
        "Published in-depth manager interviews/profiles",
        "Proxy/background biographies",
        "Public property/tax records where lawfully available",
        "Foundation Form 990 / nonprofit giving records",
        "Company and personal philanthropy disclosures",
    ),
    "Q49": (
        "Historical articles during adversity",
        "Regulatory/company filings",
        "Press releases issued during the event",
        "Historical conference-call transcripts",
        "Prior-employer history when current tenure is limited",
    ),
    "Q50": (
        "Sequential annual-report shareholder letters",
        "Historical conference-call transcripts",
        "Press releases / stakeholder communications",
        "Selected financial-data and adjusted/pro-forma disclosures",
    ),
    "Q51": (
        "Documented strategic/operating decisions",
        "Shareholder communications",
        "Manager interviews explaining the rationale",
        "Peer actions used only as context, not as a management-quality benchmark",
    ),
    "Q52": (
        "Investor-relations conference calendar",
        "Financial-press and TV appearances",
        "Annual-report / shareholder-letter language",
        "Debt/equity/acquisition financing context",
    ),
}


def all_dimensions() -> tuple[SourceDimension, ...]:
    return tuple(dimension for question in ch9.QUESTION_KEYS for dimension in QUESTION_DIMENSIONS[question])


def default_dimension_rows() -> list[dict[str, Any]]:
    """Return neutral analyst-review rows; no source cue is pre-judged as true for a company."""
    rows: list[dict[str, Any]] = []
    for dim in all_dimensions():
        rows.append(
            {
                "Question": dim.question,
                "Dimension Key": dim.key,
                "Dimension": dim.label,
                "Source Origin": dim.origin,
                "Source Pages": ", ".join(str(page) for page in dim.source_pages),
                "Supporting Evidence": "",
                "Counter-Evidence": "",
                "Evidence Status": "Open — analyst research required",
                "Source": "",
                "Analyst Note": "",
            }
        )
    return rows


def source_contract_snapshot() -> dict[str, Any]:
    counts = {question: len(QUESTION_DIMENSIONS[question]) for question in ch9.QUESTION_KEYS}
    origin_counts: dict[str, int] = {}
    for dim in all_dimensions():
        origin_counts[dim.origin] = origin_counts.get(dim.origin, 0) + 1
    return {
        "chapter": ch9.CHAPTER_NUMBER,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "question_keys": list(ch9.QUESTION_KEYS),
        "dimension_counts": counts,
        "total_dimensions": sum(counts.values()),
        "origin_counts": origin_counts,
        "q48_explicit_prompts": len(ch9.Q48_PASSION_RESEARCH_PROMPTS),
        "q49_adversity_patterns": len(Q49_ADVERSITY_RESPONSE_PATTERNS),
        "q50_shareholder_letter_elements": len(Q50_SHAREHOLDER_LETTER_ELEMENTS),
        "q50_communication_checks": len(Q50_COMMUNICATION_CHECKS),
        "q52_self_promoter_traits": len(Q52_SELF_PROMOTER_TRAITS),
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
    }


def validate_source_contract() -> dict[str, Any]:
    dimensions = all_dimensions()
    keys = [dim.key for dim in dimensions]
    assert len(keys) == len(set(keys)), "Duplicate Chapter 9 dimension key"
    assert set(QUESTION_DIMENSIONS) == set(ch9.QUESTION_KEYS)
    assert len(ch9.Q48_PASSION_RESEARCH_PROMPTS) == 6
    assert len(Q49_ADVERSITY_RESPONSE_PATTERNS) == 5
    assert len(Q50_SHAREHOLDER_LETTER_ELEMENTS) == 5
    assert len(Q50_COMMUNICATION_CHECKS) == 4
    assert len(Q52_SELF_PROMOTER_TRAITS) == 6
    assert all(dim.question in ch9.QUESTION_KEYS for dim in dimensions)
    assert all(dim.source_pages and min(dim.source_pages) >= 256 and max(dim.source_pages) <= 279 for dim in dimensions)
    forbidden = ("score", "weight", "buy signal", "sell signal", "research gate", "margin of safety")
    structural_text = " ".join(
        [dim.key + " " + dim.label + " " + dim.origin for dim in dimensions]
        + list(SOURCE_EVIDENCE_FAMILIES.keys())
    ).casefold()
    assert all(token not in structural_text for token in forbidden)
    return source_contract_snapshot()


__all__ = [
    "ORIGIN_EXPLICIT_PROMPT",
    "ORIGIN_EXPLICIT_TRAIT_LIST",
    "ORIGIN_NAMED_SUBSECTION",
    "ORIGIN_SOURCE_PARAGRAPH",
    "Q49_ADVERSITY_RESPONSE_PATTERNS",
    "Q50_COMMUNICATION_CHECKS",
    "Q50_SHAREHOLDER_LETTER_ELEMENTS",
    "Q52_FINANCING_CONTEXT_EXCEPTION",
    "Q52_SELF_PROMOTER_TRAITS",
    "Q52_WALL_STREET_EVENT_RED_FLAG_TEXT",
    "QUESTION_DIMENSIONS",
    "SOURCE_EVIDENCE_FAMILIES",
    "SourceDimension",
    "all_dimensions",
    "default_dimension_rows",
    "source_contract_snapshot",
    "validate_source_contract",
]
