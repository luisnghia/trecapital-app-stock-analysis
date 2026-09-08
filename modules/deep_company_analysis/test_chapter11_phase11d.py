from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_research as research


def test_research_plan_covers_all_source_locked_dimensions():
    plan = research.research_plan("ABC", "ABC Corp", "abc.com")
    assert len(plan) == 15
    assert set(plan["Question"]) == set(ch11.QUESTION_KEYS)
    assert set(plan["Dimension ID"]) == set(ch11.dimension_ids())
    assert plan["Official Query"].str.contains("site:abc.com", regex=False).all()


def test_query_terms_locked_to_q58_q59():
    assert tuple(research.QUERY_TERMS) == ch11.QUESTION_KEYS
    assert all(len(v) == 2 for v in research.QUERY_TERMS.values())


def test_source_grade_official_company_and_regulator():
    assert research.source_grade_from_url("https://investor.abc.com/report", "abc.com") == "A — Official"
    assert research.source_grade_from_url("https://www.sec.gov/Archives/test", "abc.com") == "A — Official"
    assert research.source_grade_from_url("https://example.com/article", "abc.com") == "B — Independent"


def test_explicit_candidate_normalization_preserves_dimension_contract():
    row = research.normalize_candidate(
        {
            "title": "Annual report",
            "url": "https://abc.com/ar.pdf",
            "text": "Management explained acquisition rationale, risks and expected synergies.",
        },
        dimension_id="q58_decision_process_and_rationale",
        official_domain="abc.com",
    )
    assert row["Question"] == "Q58"
    assert row["Dimension ID"] == "q58_decision_process_and_rationale"
    assert row["Source Grade"] == "A — Official"
    assert row["Select"] is False
    assert "analyst review" in row["Status"].lower()


def test_matching_is_research_only_and_can_find_ma_dimensions():
    matched = research.match_dimensions(
        "customer retention acquired business acquisition customers retained after deal", "Q59"
    )
    assert "q59_customer_retention" in matched
    assert all(x.startswith("q59_") for x in matched)


def test_build_candidates_deduplicates_same_record_dimension():
    records = [
        {
            "dimension_id": "q59_price_discipline_and_walkaway",
            "title": "Conference call",
            "url": "https://abc.com/a",
            "text": "Management walked away when the acquisition price exceeded its limit.",
        },
        {
            "dimension_id": "q59_price_discipline_and_walkaway",
            "title": "Conference call",
            "url": "https://abc.com/a",
            "text": "Management walked away when the acquisition price exceeded its limit.",
        },
    ]
    table = research.build_candidates(records, official_domain="abc.com")
    assert len(table) == 1
    assert table.iloc[0]["Dimension ID"] == "q59_price_discipline_and_walkaway"


def test_research_gaps_unknown_first():
    candidates = pd.DataFrame([
        research.normalize_candidate(
            {"title": "A", "url": "https://abc.com/a", "text": "evidence"},
            dimension_id="q58_management_motivation",
        )
    ])
    gaps = research.research_gaps(candidates)
    assert len(gaps) == 14
    assert "q58_management_motivation" not in set(gaps["Dimension ID"])
    assert set(gaps["Status"]) == {"Open"}


def test_promotion_requires_explicit_selection_and_preserves_analyst_ownership():
    original = ch11.empty_payload("ABC", "ABC Corp")
    before_status = dict(original["question_status"])
    before_confidence = dict(original["confidence"])
    before_assessment = dict(original["analyst_assessment"])
    before_dimensions = dict(original["dimension_status"])
    row = research.normalize_candidate(
        {
            "title": "Annual report",
            "url": "https://abc.com/a",
            "text": "The company used cash and debt to finance the acquisition.",
        },
        dimension_id="q59_financing_and_risk_tolerance",
    )
    table = pd.DataFrame([row])
    untouched = research.promote_selected_candidates(original, table, [])
    assert untouched["evidence"] == []
    promoted = research.promote_selected_candidates(original, table, [row["Candidate ID"]])
    assert len(promoted["evidence"]) == 1
    assert promoted["question_status"] == before_status
    assert promoted["confidence"] == before_confidence
    assert promoted["analyst_assessment"] == before_assessment
    assert promoted["dimension_status"] == before_dimensions


def test_repromoting_same_candidate_is_idempotent():
    original = ch11.empty_payload("ABC")
    row = research.normalize_candidate(
        {"title": "Filing", "url": "https://abc.com/a", "text": "Customer retention evidence"},
        dimension_id="q59_customer_retention",
    )
    table = pd.DataFrame([row])
    once = research.promote_selected_candidates(original, table, [row["Candidate ID"]])
    twice = research.promote_selected_candidates(once, table, [row["Candidate ID"]])
    assert len(twice["evidence"]) == 1


def test_phase_summary_preserves_investment_boundary():
    summary = research.phase_summary()
    assert summary["dimensions"] == 15
    assert summary["analyst_promotion_required"] is True
    assert summary["automatic_ma_score"] is False
    assert summary["automatic_acquisition_success_conclusion"] is False
    assert summary["automatic_synergy_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_research_gate_changed"] is False
    assert summary["duplicate_financial_ssot_added"] is False
