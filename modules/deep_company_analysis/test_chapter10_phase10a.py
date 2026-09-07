from __future__ import annotations

from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10


EXPECTED_TITLES = {
    "Q53": "Does the business grow through mergers and acquisitions, or does it grow organically?",
    "Q54": "What is the management team’s motivation to grow the business?",
    "Q55": "Has historical growth been profitable and will it continue?",
    "Q56": "What are the future growth prospects for the business?",
    "Q57": "Is the management team growing the business too quickly or at a steady pace?",
}


def test_chapter10_title_and_q53_q57_are_exactly_source_locked() -> None:
    assert ch10.CHAPTER_NUMBER == 10
    assert ch10.CHAPTER_TITLE == "Evaluating Growth Opportunities"
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.QUESTION_TITLES == EXPECTED_TITLES
    assert ch10.QUESTION_SOURCE_PAGES == {"Q53": 281, "Q54": 282, "Q55": 283, "Q56": 284, "Q57": 296}
    assert ch10.SOURCE_LOCK == "Michael Shearn — The Investment Checklist — Chapter 10 — Q53-Q57"
    assert ch10.SOURCE_QUESTION_RANGE == "Q53-Q57"


def test_phase10a_is_unknown_first_and_analyst_owned() -> None:
    payload = ch10.empty_payload("dgc", "Duc Giang Chemicals")
    assert payload["ticker"] == "DGC"
    assert payload["growth_mode"] == "Unknown"
    assert set(payload["question_status"].values()) == {"Unknown"}
    assert set(payload["confidence"].values()) == {"Unknown"}
    assert set(payload["analyst_assessment"].values()) == {"Unknown"}
    assert payload["evidence"] == []
    assert payload["research_gaps"] == []
    assert payload["growth_events"] == []


def test_normalization_cannot_override_source_lock_or_question_range() -> None:
    payload = ch10.empty_payload("DGC")
    payload["source_lock"] = "wrong"
    payload["source_question_range"] = "Q1-Q99"
    payload["question_status"]["Q53"] = "invalid"
    payload["confidence"]["Q54"] = "certain"
    payload["growth_mode"] = "Hypergrowth"
    normalized = ch10.normalize_payload(payload)
    assert normalized["source_lock"] == ch10.SOURCE_LOCK
    assert normalized["source_question_range"] == ch10.SOURCE_QUESTION_RANGE
    assert normalized["question_status"]["Q53"] == "Unknown"
    assert normalized["confidence"]["Q54"] == "Unknown"
    assert normalized["growth_mode"] == "Unknown"


def test_phase10a_research_focus_covers_only_source_questions() -> None:
    assert tuple(ch10.QUESTION_RESEARCH_FOCUS) == ch10.QUESTION_KEYS
    joined = " ".join(ch10.QUESTION_RESEARCH_FOCUS.values()).casefold()
    assert "growth route" in joined
    assert "motivation" in joined
    assert "profitable" in joined
    assert "runway" in joined
    assert "disciplined" in joined


def test_qualitative_schemas_do_not_create_scores_or_valuation_outputs() -> None:
    all_columns = ch10.EVIDENCE_COLUMNS + ch10.RESEARCH_GAP_COLUMNS + ch10.GROWTH_EVENT_COLUMNS
    joined = " ".join(all_columns).casefold()
    for forbidden in (
        "growth score", "weighted score", "buy signal", "sell signal", "research gate",
        "intrinsic value", "margin of safety", "mos", "target price",
    ):
        assert forbidden not in joined


def test_chapter10_source_module_has_no_ui_db_web_or_live_financial_bridge() -> None:
    source = Path(ch10.__file__).read_text(encoding="utf-8").casefold()
    forbidden_imports = (
        "import streamlit", "from streamlit", "import httpx", "import requests", "from adapters",
        "import psycopg", "import sqlite3", "chapter10_store", "module1_dashboard", "module2_dashboard",
        "fireant", "simplize", "vietstock",
    )
    assert all(item not in source for item in forbidden_imports)
    assert "web research" in source
    assert "buy/hold/sell" in source
    assert "duplicate financial ssot" in source


def test_research_warnings_measure_completeness_only() -> None:
    payload = ch10.empty_payload("HPG")
    warnings = ch10.research_gap_warnings(payload)
    assert len(warnings) == 5
    assert all("growth-opportunity research remains incomplete; analyst review required" in item for item in warnings)
    payload["question_status"]["Q53"] = "Answered"
    warnings = ch10.research_gap_warnings(payload)
    assert len(warnings) == 4
    joined = " ".join(warnings).casefold()
    assert "good growth" not in joined
    assert "bad growth" not in joined
    assert "buy" not in joined
    assert "sell" not in joined


def test_q53_q57_range_does_not_bleed_into_adjacent_chapters() -> None:
    assert all(53 <= int(key[1:]) <= 57 for key in ch10.QUESTION_KEYS)
    assert "Q52" not in ch10.QUESTION_TITLES
    assert "Q58" not in ch10.QUESTION_TITLES
