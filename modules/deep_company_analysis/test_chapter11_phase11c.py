from copy import deepcopy

from modules.deep_company_analysis import chapter11
from modules.deep_company_analysis import chapter11_data_bridge as bridge


def _canonical_payload():
    return {
        "source": "canonical_test_fixture",
        "as_of_date": "2026-09-08",
        "metrics": {
            "revenue": 1000,
            "revenue_by_segment": {"core": 800, "new": 200},
            "opex": 600,
            "ebit_margin": 0.2,
            "total_debt": 300,
            "finance_cost": 25,
            "customer_retention_rate": 0.91,
            "headcount": 1200,
            "staff_turnover": 0.08,
            "purchase_price": 450,
            "operating_income": 200,
            "ebitda": 260,
            "fcf": 150,
            "shareholders_equity": 700,
            "cash_and_equivalents": 180,
            "dscr": 3.0,
            "equity_issued": 50,
            "shares_outstanding": 100,
        },
    }


def test_bridge_contract_and_dimension_count():
    rows = bridge.build_dimension_evidence(_canonical_payload())
    assert bridge.PHASE == "11C"
    assert bridge.VERSION == "V84"
    assert bridge.BRIDGE_CONTRACT == "canonical-read-only"
    assert len(rows) == 15
    assert len(rows) == sum(chapter11.dimension_count_by_question().values())
    assert {row["question"] for row in rows} == {"Q58", "Q59"}


def test_qualitative_dimensions_remain_unknown():
    rows = {row["dimension_id"]: row for row in bridge.build_dimension_evidence(_canonical_payload())}
    for dimension_id in (
        "q58_decision_process_and_rationale",
        "q58_management_motivation",
        "q58_customer_overlap_synergy_fit",
        "q59_core_competency_fit",
        "q59_management_understands_target",
        "q59_price_discipline_and_walkaway",
    ):
        assert rows[dimension_id]["status"] == "Unknown"
        assert rows[dimension_id]["direction"] == "Unknown"
        assert rows[dimension_id]["canonical_values"] == {}


def test_aliases_resolve_without_recalculation():
    payload = _canonical_payload()
    assert bridge.canonical_lookup(payload, "segment_revenue")["canonical_key"] == "revenue_by_segment"
    assert bridge.canonical_lookup(payload, "operating_expenses")["canonical_key"] == "opex"
    assert bridge.canonical_lookup(payload, "debt")["canonical_key"] == "total_debt"
    assert bridge.canonical_lookup(payload, "acquisition_consideration")["canonical_key"] == "purchase_price"
    assert bridge.canonical_lookup(payload, "ebit")["canonical_key"] == "operating_income"
    assert bridge.canonical_lookup(payload, "free_cash_flow")["canonical_key"] == "fcf"


def test_partial_availability_is_neutral_and_explicit():
    payload = {"metrics": {"ebitda": 50}}
    rows = {row["dimension_id"]: row for row in bridge.build_dimension_evidence(payload)}
    row = rows["q59_price_paid_and_postdeal_economics"]
    assert row["status"] == "Evidence found"
    assert row["direction"] == "Unknown"
    assert row["available_dependencies"] == ("ebitda",)
    assert set(row["missing_dependencies"]) == {
        "acquisition_consideration",
        "ebit",
        "free_cash_flow",
        "book_value",
    }


def test_missing_dependencies_remain_unknown():
    rows = {row["dimension_id"]: row for row in bridge.build_dimension_evidence({})}
    row = rows["q59_financing_and_risk_tolerance"]
    assert row["status"] == "Unknown"
    assert row["canonical_values"] == {}
    assert set(row["missing_dependencies"]) == {
        "cash",
        "debt",
        "debt_coverage",
        "free_cash_flow",
        "equity_issuance",
        "shares_outstanding",
    }


def test_analyst_payload_is_preserved_byte_for_byte_semantically():
    analyst = chapter11.empty_payload("AAA", "Example Co")
    analyst["question_status"]["Q58"] = "Partial"
    analyst["confidence"]["Q58"] = "Medium"
    analyst["analyst_assessment"]["Q58"] = "Analyst-owned text"
    analyst["dimension_status"]["q58_management_motivation"] = "Evidence found"
    before = deepcopy(analyst)
    result = bridge.bridge_payload(_canonical_payload(), analyst)
    assert analyst == before
    assert result["analyst_payload"] == before


def test_bridge_never_emits_ma_or_investment_conclusions():
    result = bridge.bridge_payload(_canonical_payload(), chapter11.empty_payload("AAA"))
    assert result["automatic_ma_score"] is False
    assert result["automatic_acquisition_success_conclusion"] is False
    assert result["automatic_synergy_forecast"] is False
    assert result["automatic_investment_signal"] is False
    assert result["mos_or_research_gate_changed"] is False


def test_ratio_and_financing_policies_are_upstream_ssot_only():
    ratio = bridge.valuation_ratio_policy()
    finance = bridge.financing_policy()
    assert ratio["computed_by_chapter11"] is False
    assert finance["computed_by_chapter11"] is False
    assert "EV/EBITDA" in ratio["ratios"]
    assert "equity dilution" in finance["metrics"]


def test_provenance_tracks_canonical_location_and_asof():
    rows = bridge.build_dimension_evidence(_canonical_payload())
    target = next(row for row in rows if row["dimension_id"] == "q59_customer_retention")
    assert target["provenance"]["source"] == "canonical_test_fixture"
    assert target["provenance"]["as_of_date"] == "2026-09-08"
    assert target["provenance"]["locations"]["customer_retention"] == "metrics.customer_retention_rate"
