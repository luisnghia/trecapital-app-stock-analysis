from __future__ import annotations

from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9


EXPECTED_TITLES = {
    "Q48": "Does the CEO love the money or the business?",
    "Q49": "Can you identify a moment of integrity for the manager?",
    "Q50": "Are managers clear and consistent in their communications and actions with stakeholders?",
    "Q51": "Does management think independently and remain unswayed by what others in their industry are doing?",
    "Q52": "Is the CEO self-promoting?",
}

EXPECTED_Q48_PROMPTS = (
    "Is the business a career or just a job for the manager?",
    "Would the CEO refuse to sell the business, no matter what the price?",
    "Is the manager interested in money or motivated by money?",
    "Does the manager focus on appearances instead of the business?",
    "What type of philanthropic endeavors is the manager involved in?",
    "Are the managers lifelong learners who focus on continuous improvement?",
)


def test_chapter9_title_and_q48_q52_are_exactly_source_locked() -> None:
    assert ch9.CHAPTER_NUMBER == 9
    assert ch9.CHAPTER_TITLE == "Assessing the Quality of Management—Positive and Negative Traits"
    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    assert ch9.QUESTION_TITLES == EXPECTED_TITLES
    assert ch9.QUESTION_SOURCE_PAGES == {"Q48": 256, "Q49": 264, "Q50": 268, "Q51": 275, "Q52": 276}
    assert ch9.SOURCE_LOCK == "Michael Shearn — The Investment Checklist — Chapter 9 — Q48-Q52"


def test_q48_preserves_shearn_six_passion_research_prompts_without_scoring() -> None:
    assert ch9.Q48_PASSION_RESEARCH_PROMPTS == EXPECTED_Q48_PROMPTS
    rows = ch9.default_q48_passion_rows()
    assert len(rows) == 6
    assert tuple(row["Prompt"] for row in rows) == EXPECTED_Q48_PROMPTS
    assert all("score" not in str(key).casefold() for row in rows for key in row)
    assert all(row["Supporting Evidence"] == "" and row["Counter-Evidence"] == "" for row in rows)


def test_payload_is_unknown_first_and_chapter7_is_manager_identity_ssot() -> None:
    payload = ch9.empty_payload("dgc", "Duc Giang Chemicals")
    assert payload["ticker"] == "DGC"
    assert payload["manager_identity_ssot"] == "Chapter 7 manager master"
    assert set(payload["question_status"].values()) == {"Unknown"}
    assert set(payload["confidence"].values()) == {"Unknown"}
    assert set(payload["analyst_assessment"].values()) == {"Unknown"}
    assert "manager_master" not in payload
    assert "managers" not in payload


def test_normalization_cannot_override_source_lock_or_manager_ssot() -> None:
    payload = ch9.empty_payload("DGC")
    payload["source_lock"] = "wrong"
    payload["manager_identity_ssot"] = "new manager database"
    payload["question_status"]["Q48"] = "invalid"
    payload["confidence"]["Q49"] = "certain"
    normalized = ch9.normalize_payload(payload)
    assert normalized["source_lock"] == ch9.SOURCE_LOCK
    assert normalized["manager_identity_ssot"] == ch9.MANAGER_IDENTITY_SSOT
    assert normalized["question_status"]["Q48"] == "Unknown"
    assert normalized["confidence"]["Q49"] == "Unknown"


def test_qualitative_schemas_do_not_fabricate_ttm_or_investment_signals() -> None:
    all_columns = ch9.Q48_PASSION_COLUMNS + ch9.EVIDENCE_COLUMNS + ch9.RESEARCH_GAP_COLUMNS + ch9.BEHAVIOR_EVENT_COLUMNS
    joined = " ".join(all_columns).casefold()
    assert "ttm" not in joined
    assert "t12m" not in joined
    for forbidden in (
        "management score",
        "weighted score",
        "buy signal",
        "sell signal",
        "research gate",
        "margin of safety",
        "mos",
    ):
        assert forbidden not in joined


def test_phase9a_source_module_has_no_ui_db_web_or_financial_bridge() -> None:
    source = Path(ch9.__file__).read_text(encoding="utf-8").casefold()
    forbidden_imports = (
        "import streamlit",
        "from streamlit",
        "import httpx",
        "import requests",
        "from adapters",
        "import psycopg",
        "import sqlite3",
        "chapter9_store",
        "module1_dashboard",
        "module2_dashboard",
        "fireant",
        "simplize",
        "vietstock",
    )
    assert all(item not in source for item in forbidden_imports)
    assert "buy/hold/sell" in source
    assert "phase 9a adds no web research" in source


def test_research_warnings_measure_completeness_only() -> None:
    payload = ch9.empty_payload("HPG")
    warnings = ch9.research_gap_warnings(payload)
    assert len(warnings) == 5
    assert all("research remains incomplete; analyst review required" in item for item in warnings)
    payload["question_status"]["Q48"] = "Answered"
    warnings = ch9.research_gap_warnings(payload)
    assert len(warnings) == 4
    joined = " ".join(warnings).casefold()
    assert "good manager" not in joined
    assert "bad manager" not in joined
    assert "buy" not in joined
    assert "sell" not in joined


def test_q48_q52_range_does_not_bleed_into_adjacent_chapters() -> None:
    assert all(48 <= int(key[1:]) <= 52 for key in ch9.QUESTION_KEYS)
    assert "Q47" not in ch9.QUESTION_TITLES
    assert "Q53" not in ch9.QUESTION_TITLES
