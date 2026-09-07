from __future__ import annotations

from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as v63


EXPECTED_Q49_PATTERNS = (
    "Adversity overwhelms management; management evades rather than confronts the problem.",
    "Management blames others or outside events and relies on heavily lawyered / PR-crafted statements instead of acting.",
    "Management strikes back quickly without thinking the response through and may move in the wrong direction.",
    "Management applies a quick remedy that solves the problem only in the short run and fails to follow up.",
    "Management quickly and openly communicates how it is thinking about the problem and outlines how it will solve it for the long term.",
)

EXPECTED_Q50_LETTER_ELEMENTS = (
    "What is important at their business.",
    "What is driving their decisions.",
    "The issues they have encountered.",
    "The metrics that are important to monitor the health of the business.",
    "How the CEO plans to resolve issues faced by the business.",
)

EXPECTED_Q50_CHECKS = (
    "Is the manager easy to listen to?",
    "Do you learn from the manager?",
    "Does the manager use corporate speak?",
    "Does the manager use double speak?",
)

EXPECTED_Q52_TRAITS = (
    "Flamboyant.",
    "Have lots of charisma.",
    "Engage in aggressive salesmanship.",
    "Tend to command the center of attention.",
    "Take over discussions.",
    "Have an attitude that they are smarter than everybody else.",
)


def test_phase9b_preserves_q48_exact_six_prompts_as_dimensions() -> None:
    dims = v63.QUESTION_DIMENSIONS["Q48"]
    assert len(dims) == 6
    assert tuple(dim.label for dim in dims) == ch9.Q48_PASSION_RESEARCH_PROMPTS
    assert all(dim.origin == v63.ORIGIN_EXPLICIT_PROMPT for dim in dims)


def test_q49_preserves_five_explicit_adversity_response_patterns() -> None:
    assert v63.Q49_ADVERSITY_RESPONSE_PATTERNS == EXPECTED_Q49_PATTERNS
    dims = v63.QUESTION_DIMENSIONS["Q49"]
    assert len(dims) == 4
    adversity = next(dim for dim in dims if dim.key == "q49_adversity_response_pattern")
    assert adversity.red_flags == EXPECTED_Q49_PATTERNS[:4]
    assert adversity.counter_signals == (EXPECTED_Q49_PATTERNS[4],)
    unknown_note = next(dim for dim in dims if dim.key == "q49_integrity_moment").red_flags
    assert any("remains unknown" in item for item in unknown_note)


def test_q50_source_named_subsections_and_explicit_questions_are_locked() -> None:
    assert v63.Q50_SHAREHOLDER_LETTER_ELEMENTS == EXPECTED_Q50_LETTER_ELEMENTS
    assert v63.Q50_COMMUNICATION_CHECKS == EXPECTED_Q50_CHECKS
    dims = v63.QUESTION_DIMENSIONS["Q50"]
    assert len(dims) == 8
    labels = {dim.label for dim in dims}
    assert "Sequential annual-report shareholder letters" in labels
    assert "Historical conference-call transcripts and question-and-answer behavior" in labels
    assert "How managers communicate when confronted with adversity" in labels
    assert "Whether management only emphasizes good news in communications" in labels
    assert set(EXPECTED_Q50_CHECKS) <= labels


def test_q51_keeps_independence_long_term_focus_and_copycat_risk_separate() -> None:
    dims = v63.QUESTION_DIMENSIONS["Q51"]
    assert len(dims) == 3
    keys = {dim.key for dim in dims}
    assert keys == {
        "q51_resist_industry_copying",
        "q51_long_term_focus",
        "q51_own_plan_vs_benchmark_copy",
    }
    assert any("short-term" in " ".join(dim.red_flags).casefold() for dim in dims)
    red_flags = " ".join(" ".join(dim.red_flags) for dim in dims).casefold()
    assert "competitor" in red_flags
    assert "copies visible" in red_flags or "similar products" in red_flags


def test_q52_preserves_exact_six_self_promoter_traits_and_financing_exception() -> None:
    assert v63.Q52_SELF_PROMOTER_TRAITS == EXPECTED_Q52_TRAITS
    dims = v63.QUESTION_DIMENSIONS["Q52"]
    assert len(dims) == 5
    pitch = next(dim for dim in dims if dim.key == "q52_self_brand_and_pitch")
    assert pitch.red_flags == EXPECTED_Q52_TRAITS
    frequency = next(dim for dim in dims if dim.key == "q52_wall_street_event_frequency")
    assert "more than two to four times per month" in frequency.red_flags[0]
    financing = next(dim for dim in dims if dim.key == "q52_financing_context")
    assert v63.Q52_FINANCING_CONTEXT_EXCEPTION in financing.counter_signals
    assert "finance" in v63.Q52_FINANCING_CONTEXT_EXCEPTION.casefold()


def test_dimension_contract_distinguishes_source_origin_instead_of_pretending_all_are_exact_questions() -> None:
    dims = v63.all_dimensions()
    assert len(dims) == 26
    origins = {dim.origin for dim in dims}
    assert origins == {
        v63.ORIGIN_EXPLICIT_PROMPT,
        v63.ORIGIN_EXPLICIT_TRAIT_LIST,
        v63.ORIGIN_NAMED_SUBSECTION,
        v63.ORIGIN_SOURCE_PARAGRAPH,
    }
    assert all(dim.question in ch9.QUESTION_KEYS for dim in dims)
    assert all(min(dim.source_pages) >= 256 and max(dim.source_pages) <= 279 for dim in dims)


def test_default_rows_are_open_and_do_not_prejudge_source_cues() -> None:
    rows = v63.default_dimension_rows()
    assert len(rows) == 26
    assert all(row["Evidence Status"] == "Open — analyst research required" for row in rows)
    assert all(row["Supporting Evidence"] == "" for row in rows)
    assert all(row["Counter-Evidence"] == "" for row in rows)
    assert all(row["Source"] == "" for row in rows)


def test_source_evidence_families_follow_chapter_9_source_methods() -> None:
    assert set(v63.SOURCE_EVIDENCE_FAMILIES) == set(ch9.QUESTION_KEYS)
    q48 = " ".join(v63.SOURCE_EVIDENCE_FAMILIES["Q48"]).casefold()
    assert "interview" in q48
    assert "proxy" in q48
    assert "form 990" in q48
    q49 = " ".join(v63.SOURCE_EVIDENCE_FAMILIES["Q49"]).casefold()
    assert "conference-call" in q49
    q50 = " ".join(v63.SOURCE_EVIDENCE_FAMILIES["Q50"]).casefold()
    assert "shareholder" in q50 and "conference-call" in q50
    q52 = " ".join(v63.SOURCE_EVIDENCE_FAMILIES["Q52"]).casefold()
    assert "conference" in q52 and "financing" in q52


def test_phase9b_has_no_score_ui_db_web_or_financial_bridge() -> None:
    snapshot = v63.validate_source_contract()
    assert snapshot["total_dimensions"] == 26
    assert snapshot["dimension_counts"] == {"Q48": 6, "Q49": 4, "Q50": 8, "Q51": 3, "Q52": 5}
    assert snapshot["automatic_management_score"] is False
    assert snapshot["automatic_investment_signal"] is False

    source = Path(v63.__file__).read_text(encoding="utf-8").casefold()
    for forbidden_import in (
        "import streamlit",
        "from streamlit",
        "import httpx",
        "import requests",
        "import psycopg",
        "import sqlite3",
        "fireant",
        "simplize",
        "vietstock",
    ):
        assert forbidden_import not in source
    assert "no ui, database, web-research adapter, or financial-data bridge" in source
    assert "no manager score" in source
    assert "buy/hold/sell" in source
