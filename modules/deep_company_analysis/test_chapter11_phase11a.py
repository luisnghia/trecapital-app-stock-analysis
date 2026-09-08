from copy import deepcopy

import modules.deep_company_analysis.chapter11 as ch11


def test_source_lock_exact_questions_and_pages():
    assert ch11.CHAPTER_NUMBER == 11
    assert ch11.CHAPTER_TITLE == "Evaluating Mergers & Acquisitions"
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.QUESTION_TITLES == {
        "Q58": "How does management make M&A decisions?",
        "Q59": "Have past acquisitions been successful?",
    }
    assert ch11.QUESTION_SOURCE_PAGES == {"Q58": 305, "Q59": 310}
    assert ch11.SOURCE_QUESTION_RANGE == "Q58-Q59"


def test_empty_payload_is_unknown_first():
    payload = ch11.empty_payload("fpt", "FPT")
    assert payload["ticker"] == "FPT"
    assert payload["question_status"] == {"Q58": "Unknown", "Q59": "Unknown"}
    assert payload["confidence"] == {"Q58": "Unknown", "Q59": "Unknown"}
    assert payload["analyst_assessment"] == {"Q58": "Unknown", "Q59": "Unknown"}
    assert payload["evidence"] == []
    assert payload["research_gaps"] == []
    assert payload["ma_events"] == []


def test_normalize_preserves_source_lock_and_known_analyst_fields():
    payload = ch11.empty_payload("FPT")
    payload["source_lock"] = "runtime override"
    payload["source_question_range"] = "Q1-Q99"
    payload["question_status"]["Q58"] = "Answered"
    payload["confidence"]["Q58"] = "High"
    payload["analyst_assessment"]["Q58"] = "Documented decision process"
    normalized = ch11.normalize_payload(payload)
    assert normalized["source_lock"] == ch11.SOURCE_LOCK
    assert normalized["source_question_range"] == "Q58-Q59"
    assert normalized["question_status"]["Q58"] == "Answered"
    assert normalized["confidence"]["Q58"] == "High"
    assert normalized["analyst_assessment"]["Q58"] == "Documented decision process"


def test_normalize_rejects_invalid_status_and_confidence():
    payload = ch11.empty_payload("FPT")
    payload["question_status"]["Q58"] = "Bullish"
    payload["confidence"]["Q59"] = "Certain"
    normalized = ch11.normalize_payload(payload)
    assert normalized["question_status"]["Q58"] == "Unknown"
    assert normalized["confidence"]["Q59"] == "Unknown"


def test_normalize_does_not_accept_adjacent_question_injection():
    payload = ch11.empty_payload("FPT")
    payload["question_status"]["Q57"] = "Answered"
    payload["question_status"]["Q60"] = "Answered"
    normalized = ch11.normalize_payload(payload)
    assert set(normalized["question_status"]) >= {"Q58", "Q59"}
    assert "Q57" not in ch11.QUESTION_KEYS
    assert "Q60" not in ch11.QUESTION_KEYS


def test_rows_are_neutral_containers_only():
    payload = ch11.empty_payload("FPT")
    payload["evidence"] = [{"Question": "Q58", "Direction": "Mixed"}]
    payload["research_gaps"] = [{"Question": "Q59", "Status": "Open"}]
    payload["ma_events"] = [{"Target / Transaction": "Example deal"}]
    normalized = ch11.normalize_payload(payload)
    assert normalized["evidence"] == payload["evidence"]
    assert normalized["research_gaps"] == payload["research_gaps"]
    assert normalized["ma_events"] == payload["ma_events"]


def test_research_warnings_only_reflect_completeness():
    payload = ch11.empty_payload("FPT")
    warnings = ch11.research_gap_warnings(payload)
    assert "Q58: M&A research remains incomplete; analyst review required." in warnings
    assert "Q59: M&A research remains incomplete; analyst review required." in warnings
    payload["question_status"]["Q58"] = "Answered"
    warnings = ch11.research_gap_warnings(payload)
    assert "Q58: M&A research remains incomplete; analyst review required." not in warnings
    assert "Q59: M&A research remains incomplete; analyst review required." in warnings


def test_normalize_is_deterministic_and_does_not_mutate_input():
    payload = ch11.empty_payload("FPT")
    payload["analyst_assessment"]["Q59"] = "Unknown"
    before = deepcopy(payload)
    first = ch11.normalize_payload(payload)
    second = ch11.normalize_payload(payload)
    assert first == second
    assert payload == before
