from __future__ import annotations

from pathlib import Path

from modules.deep_company_analysis.appendix_a import SOURCE_LOCK
from modules.deep_company_analysis.appendix_a_store import load_appendix_a_workspace, save_appendix_a_workspace
from modules.deep_company_analysis.appendix_a_workspace import (
    QUESTION_IDS,
    make_interview_record,
    make_research_gap,
    make_source_record,
    normalize_question_refs,
    normalize_workspace,
)


def test_question_reference_contract_is_q01_to_q59_only():
    assert QUESTION_IDS[0] == "Q01"
    assert QUESTION_IDS[-1] == "Q59"
    assert len(QUESTION_IDS) == 59
    assert normalize_question_refs(["q01", "Q59", "Q60", "Q01", "BUY"]) == ["Q01", "Q59"]


def test_source_identity_is_deterministic_and_source_class_is_not_a_score():
    a = make_source_record(source_name="Alias A", source_class="Primary", source_type="Supplier", organization_context="Industry X")
    b = make_source_record(source_name="Alias A", source_class="Primary", source_type="Supplier", organization_context="Industry X")
    assert a["source_id"] == b["source_id"]
    assert a["source_class"] == "Primary"
    assert "score" not in a
    assert "credibility" not in a


def test_interview_keeps_source_response_separate_from_analyst_commentary():
    item = make_interview_record(
        source_id="SRC-1", interview_date="2026-09-08", question_prompt="What changed?",
        source_response_observation="The source said demand slowed.",
        statement_type="Fact", uncertainty_noted="Time period not specified.",
        related_question_refs=["Q03", "Q58"], analyst_commentary="Analyst needs corroboration."
    )
    assert item["source_response_observation"] == "The source said demand slowed."
    assert item["analyst_commentary"] == "Analyst needs corroboration."
    assert item["uncertainty_noted"]
    assert item["related_question_refs"] == ["Q03", "Q58"]


def test_research_gap_links_are_reference_only():
    gap = make_research_gap(
        unanswered_question_assumption="Is customer retention changing?",
        preferred_source_type="Customer", related_question_refs=["Q42", "Q59"], status="Open"
    )
    assert gap["related_question_refs"] == ["Q42", "Q59"]
    forbidden = {"research_gate", "mos", "margin_of_safety", "intrinsic_value", "buy_hold_sell"}
    assert not forbidden.intersection(gap)


def test_workspace_is_unknown_first_and_source_locked():
    ws = normalize_workspace({}, ticker="abc", company_name="ABC Co")
    assert ws["ticker"] == "ABC"
    assert ws["source_lock"] == SOURCE_LOCK
    assert set(ws["sections"].values()) == {"Unknown"}
    assert ws["sources"] == [] and ws["interviews"] == [] and ws["research_gaps"] == []


def test_workspace_allowlist_drops_financial_and_investment_payloads():
    raw = {
        "ticker": "ABC", "intrinsic_value": 100, "margin_of_safety": 0.4,
        "research_gate": "PASS", "financials": {"revenue": 999}, "buy_hold_sell": "BUY",
        "sources": [make_source_record(source_name="X", source_type="Customer")],
    }
    ws = normalize_workspace(raw)
    for key in ("intrinsic_value", "margin_of_safety", "research_gate", "financials", "buy_hold_sell"):
        assert key not in ws


def test_workspace_deduplicates_sources_and_interviews():
    source = make_source_record(source_name="X", source_type="Competitor")
    interview = make_interview_record(source_id=source["source_id"], interview_date="2026-09-08", question_prompt="Why?", source_response_observation="Because X")
    ws = normalize_workspace({"ticker": "ABC", "sources": [source, source], "interviews": [interview, interview]})
    assert len(ws["sources"]) == 1
    assert len(ws["interviews"]) == 1


def test_sqlite_roundtrip_persists_only_normalized_workspace(tmp_path: Path):
    db = tmp_path / "appa.sqlite3"
    source = make_source_record(source_name="Supplier A", source_class="Primary", source_type="Supplier")
    interview = make_interview_record(source_id=source["source_id"], interview_date="2026-09-08", source_response_observation="Observation", analyst_commentary="Comment")
    raw = {"ticker": "ABC", "company_name": "ABC Co", "sources": [source], "interviews": [interview], "research_gate": "PASS", "intrinsic_value": 123}
    saved = save_appendix_a_workspace(raw, db_path=db)
    loaded = load_appendix_a_workspace("abc", db_path=db)
    assert loaded == saved
    assert loaded["interviews"][0]["source_response_observation"] == "Observation"
    assert loaded["interviews"][0]["analyst_commentary"] == "Comment"
    assert "research_gate" not in loaded and "intrinsic_value" not in loaded


def test_no_automatic_contact_or_investment_action_contract():
    ws = normalize_workspace({"ticker": "ABC"})
    forbidden = {"send_email", "contact_source", "auto_contact", "buy", "sell", "hold", "score"}
    assert not forbidden.intersection(ws)
