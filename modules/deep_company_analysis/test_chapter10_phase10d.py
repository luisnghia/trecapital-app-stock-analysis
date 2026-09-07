from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_research as research


def test_research_plan_covers_all_source_locked_dimensions():
    plan = research.research_plan("ABC", "ABC Corp", "abc.com")
    assert len(plan) == 34
    assert set(plan["Question"]) == set(ch10.QUESTION_KEYS)
    assert set(plan["Dimension ID"]) == set(ch10.dimension_ids())
    assert plan["Official Query"].str.contains("site:abc.com", regex=False).all()


def test_query_terms_locked_to_q53_q57():
    assert tuple(research.QUERY_TERMS) == ch10.QUESTION_KEYS
    assert all(len(v) == 2 for v in research.QUERY_TERMS.values())


def test_source_grade_official_company_and_regulator():
    assert research.source_grade_from_url("https://investor.abc.com/report", "abc.com") == "A — Official"
    assert research.source_grade_from_url("https://www.sec.gov/Archives/test", "abc.com") == "A — Official"
    assert research.source_grade_from_url("https://example.com/article", "abc.com") == "B — Independent"


def test_explicit_candidate_normalization_preserves_dimension_contract():
    row = research.normalize_candidate(
        {"title": "Annual report", "url": "https://abc.com/ar.pdf", "text": "Acquisition spend and operating cash flow."},
        dimension_id="q53_acquisition_spend_vs_cfo",
        official_domain="abc.com",
    )
    assert row["Question"] == "Q53"
    assert row["Dimension ID"] == "q53_acquisition_spend_vs_cfo"
    assert row["Source Grade"] == "A — Official"
    assert row["Select"] is False
    assert "analyst review" in row["Status"].lower()


def test_matching_is_research_only_and_can_find_growth_dimensions():
    matched = research.match_dimensions("cash flow operations acquisition spend acquisitions", "Q53")
    assert "q53_acquisition_spend_vs_cfo" in matched
    assert all(x.startswith("q53_") for x in matched)


def test_build_candidates_deduplicates_same_record_dimension():
    records = [
        {"dimension_id": "q56_rd_commitment", "title": "Annual report", "url": "https://abc.com/a", "text": "R&D expense as percentage of sales"},
        {"dimension_id": "q56_rd_commitment", "title": "Annual report", "url": "https://abc.com/a", "text": "R&D expense as percentage of sales"},
    ]
    table = research.build_candidates(records, official_domain="abc.com")
    assert len(table) == 1
    assert table.iloc[0]["Dimension ID"] == "q56_rd_commitment"


def test_research_gaps_unknown_first():
    candidates = pd.DataFrame([
        research.normalize_candidate(
            {"title": "A", "url": "https://abc.com/a", "text": "evidence"},
            dimension_id="q53_acquisition_spend_vs_cfo",
        )
    ])
    gaps = research.research_gaps(candidates)
    assert len(gaps) == 33
    assert "q53_acquisition_spend_vs_cfo" not in set(gaps["Dimension ID"])
    assert set(gaps["Status"]) == {"Open"}


def test_promotion_requires_explicit_selection_and_does_not_mutate_analyst_fields():
    original = ch10.empty_payload("ABC", "ABC Corp")
    before_status = dict(original["question_status"])
    before_confidence = dict(original["confidence"])
    before_assessment = dict(original["analyst_assessment"])
    before_dimensions = dict(original["dimension_status"])
    row = research.normalize_candidate(
        {"title": "Annual report", "url": "https://abc.com/a", "text": "Acquisition spend evidence"},
        dimension_id="q53_acquisition_spend_vs_cfo",
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
    assert promoted["growth_mode"] == "Unknown"


def test_phase_summary_preserves_investment_boundary():
    summary = research.phase_summary()
    assert summary["dimensions"] == 34
    assert summary["analyst_promotion_required"] is True
    assert summary["automatic_growth_score"] is False
    assert summary["automatic_growth_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_research_gate_changed"] is False
    assert summary["duplicate_financial_ssot_added"] is False
