from __future__ import annotations

from copy import deepcopy

import pandas as pd

from modules.deep_company_analysis.chapter5 import empty_payload
from modules.deep_company_analysis.chapter5_lock import (
    SOURCE_LOCK_QUESTIONS,
    dgc_lock_acceptance,
    evaluate_chapter5_lock,
    guardrails,
    implementation_checks,
    research_readiness,
)


def _quant_context() -> dict:
    return {
        "q22_context": pd.DataFrame([{"Kỳ": "2025", "Doanh thu (tỷ)": 1000.0}]),
        "q25_context": pd.DataFrame([{"Kỳ": "2025", "Nợ vay (tỷ)": 100.0}]),
        "q26_variants": pd.DataFrame([
            {"ROIC View": "Trecapital Canonical ROIC", "Origin": "Trecapital canonical", "Value %": 18.5}
        ]),
        "canonical_roic_latest": 18.5,
        "provenance": {
            "source_module": "Trecapital Module 1 canonical normalized data",
            "data_origin": "Trecapital canonical cache",
            "source_label": "FireAnt + Vietstock",
        },
        "guardrails": {
            "auto_operating_kpi_conclusion": False,
            "auto_balance_sheet_conclusion": False,
            "auto_roic_quality_conclusion": False,
            "auto_compounder_conclusion": False,
        },
    }


def _candidates() -> pd.DataFrame:
    rows = []
    for q in SOURCE_LOCK_QUESTIONS:
        rows.append({
            "Question": q,
            "Subtopic": "Test candidate",
            "Direction": "Neutral — Candidate",
            "Evidence Quality": "A — Company/Official disclosure",
            "Explicitness": "Candidate — analyst verify",
            "Title": f"{q} official evidence",
            "URL": f"https://example.com/{q.lower()}",
            "Snippet": f"Official source snippet for {q}",
            "Source Group": "Nguồn doanh nghiệp/IR",
            "Query": "test",
            "Focus": q,
            "Source Method": "Official direct extraction",
        })
    return pd.DataFrame(rows)


def test_source_lock_has_exact_six_shearn_questions():
    assert list(SOURCE_LOCK_QUESTIONS) == ["Q21", "Q22", "Q23", "Q24", "Q25", "Q26"]
    assert SOURCE_LOCK_QUESTIONS["Q21"] == "What are the fundamentals of the business?"
    assert SOURCE_LOCK_QUESTIONS["Q26"] == "What is the return on invested capital for the business?"


def test_clean_record_passes_implementation_lock_with_canonical_context():
    record = empty_payload("DGC", "Duc Giang")
    report = evaluate_chapter5_lock(record, _quant_context(), _candidates())
    assert report.passed
    assert report.implementation_status == "PASS"
    assert report.implementation_checks["PASS"].all()


def test_confidence_field_is_hard_lock_failure():
    record = empty_payload("DGC")
    record["q21"]["confidence"] = "High"
    checks = implementation_checks(record, _quant_context(), _candidates())
    row = checks[checks["Check"].eq("No Confidence field")].iloc[0]
    assert not bool(row["PASS"])


def test_noncanonical_provenance_is_hard_lock_failure():
    record = empty_payload("DGC")
    quant = _quant_context()
    quant["provenance"] = {"source_module": "Parallel parser", "data_origin": "ad hoc", "source_label": "Unknown"}
    report = evaluate_chapter5_lock(record, quant, _candidates())
    assert not report.passed
    failed = report.implementation_checks.loc[~report.implementation_checks["PASS"], "Check"].tolist()
    assert "Canonical provenance / Single Source of Truth" in failed


def test_missing_quant_is_readiness_gap_not_architecture_failure():
    record = empty_payload("DGC")
    report = evaluate_chapter5_lock(record, None, _candidates())
    assert report.passed
    readiness = report.research_readiness.set_index("Question")
    assert readiness.loc["Q22", "Canonical Quant"] == "No"
    assert "thiếu canonical quant context" in readiness.loc["Q22", "Readiness"]
    assert readiness.loc["Q25", "Canonical Quant"] == "No"
    assert readiness.loc["Q26", "Canonical Quant"] == "No"


def test_missing_evidence_is_gap_not_weak_business_conclusion():
    record = empty_payload("DGC")
    report = evaluate_chapter5_lock(record, _quant_context(), pd.DataFrame())
    assert report.passed
    assert set(report.research_readiness["Readiness"]) == {"Gap — chưa có candidate evidence"}
    assert record["q25"]["balance_sheet_assessment"] == "Unknown"
    assert record["q26"]["current_roic_quality"] == "Unknown"


def test_phase5d_does_not_require_counter_evidence_to_fake_a_pass():
    readiness = research_readiness(_quant_context(), _candidates())
    assert (readiness["Counter-Evidence Candidates"] == 0).all()
    assert (readiness["Readiness"] == "Research-ready — analyst verify").all()
    assert all("quality score" in str(x).lower() for x in readiness["Reminder"])


def test_phase5d_merge_safety_preserves_analyst_owned_fields():
    record = empty_payload("DGC")
    record["q21"]["overall_assessment"] = "Stable"
    record["q25"]["balance_sheet_assessment"] = "Strong"
    record["q26"]["current_roic_quality"] = "High"
    before = deepcopy(record)
    report = evaluate_chapter5_lock(record, _quant_context(), _candidates())
    assert report.passed
    assert record == before


def test_cross_question_diagnostics_do_not_change_lock_or_record():
    record = empty_payload("DGC")
    record["q24"]["inflation_resilience"] = "Resilient"
    chapter4 = {"q16": {"pricing_power": "Weak"}, "q15": {"overall_moat_trend": "Stable"}}
    before = deepcopy(record)
    report = evaluate_chapter5_lock(record, _quant_context(), _candidates(), chapter4)
    assert report.passed
    assert report.cross_question_diagnostics
    assert any("Q24 ↔ Ch4/Q16" in item for item in report.cross_question_diagnostics)
    assert record == before


def test_dgc_acceptance_requires_real_coverage_and_canonical_tables():
    record = empty_payload("DGC")
    ok, failures = dgc_lock_acceptance(record, _quant_context(), _candidates())
    assert ok
    assert failures == []

    incomplete = _candidates()[lambda x: x["Question"].ne("Q25")]
    ok2, failures2 = dgc_lock_acceptance(record, _quant_context(), incomplete)
    assert not ok2
    assert "Q25: no real candidate evidence" in failures2


def test_phase5d_guardrails_all_false():
    flags = guardrails()
    assert flags
    assert all(value is False for value in flags.values())
    assert flags["implementation_pass_is_investment_score"] is False
    assert flags["lock_emits_buy_hold_sell"] is False
    assert flags["counter_evidence_absence_means_safe"] is False
