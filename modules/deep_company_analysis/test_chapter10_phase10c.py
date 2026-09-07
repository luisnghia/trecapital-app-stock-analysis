from copy import deepcopy

from modules.deep_company_analysis import chapter10
from modules.deep_company_analysis import chapter10_data_bridge as bridge


def test_source_lock_and_dimension_count_are_unchanged():
    assert chapter10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert chapter10.QUESTION_SOURCE_PAGES == {"Q53": 281, "Q54": 282, "Q55": 283, "Q56": 284, "Q57": 296}
    assert len(chapter10.dimension_catalog()) == 34
    assert bridge.BRIDGE_CONTRACT == "canonical-read-only"


def test_missing_canonical_payload_is_unknown_first():
    result = bridge.bridge_payload({})
    assert result["dimension_count"] == 34
    assert all(row["direction"] == "Unknown" for row in result["evidence"])
    assert all(row["status"] == "Unknown" for row in result["evidence"])
    assert result["ccc"]["status"] == "Unknown"


def test_nested_canonical_metrics_are_consumed_with_provenance():
    payload = {
        "source": "financial_ssot",
        "as_of_date": "2026-06-30",
        "metrics": {"revenue": [100, 120], "gross_margin": [0.31, 0.33], "operating_units": [10, 12]},
    }
    rows = bridge.build_dimension_evidence(payload)
    target = next(row for row in rows if row["dimension_id"] == "q55_unit_growth_vs_gross_margin")
    assert target["status"] == "Evidence found"
    assert set(target["available_dependencies"]) == {"gross_margin", "operating_units"}
    assert target["provenance"]["source"] == "financial_ssot"
    assert target["provenance"]["locations"]["gross_margin"] == "metrics.gross_margin"


def test_partial_dependencies_remain_explicit_not_inferred():
    rows = bridge.build_dimension_evidence({"metrics": {"gross_margin": [0.3, 0.31]}})
    target = next(row for row in rows if row["dimension_id"] == "q55_unit_growth_vs_gross_margin")
    assert target["status"] == "Evidence found"
    assert target["available_dependencies"] == ("gross_margin",)
    assert target["missing_dependencies"] == ("operating_units",)


def test_qualitative_dimension_is_not_auto_answered():
    rows = bridge.build_dimension_evidence({"metrics": {"revenue": 123}})
    target = next(row for row in rows if row["dimension_id"] == "q54_pressure_to_grow")
    assert target["status"] == "Unknown"
    assert target["direction"] == "Unknown"


def test_ccc_is_read_only_when_canonical_value_exists():
    state = bridge.ccc_bridge_state({"derived_metrics": {"cash_conversion_cycle": 42.5}})
    assert state["status"] == "Evidence found"
    assert state["ccc"] == 42.5
    assert state["canonical_key"] == "cash_conversion_cycle"
    assert state["computed_by_chapter10"] is False


def test_ccc_is_never_recomputed_from_components():
    payload = {"metrics": {"dio": 60.0, "dso": 35.0, "dpo": 25.0}}
    state = bridge.ccc_bridge_state(payload)
    assert state["status"] == "Unknown"
    assert state["ccc"] is None
    assert state["computed_by_chapter10"] is False
    assert all(state["components_available"].values())
    assert "does not recompute" in state["reason"]


def test_bridge_does_not_mutate_analyst_payload():
    analyst = chapter10.empty_payload("ABC", "ABC Corp")
    analyst["question_status"]["Q53"] = "Partial"
    analyst["confidence"]["Q53"] = "Medium"
    analyst["analyst_assessment"]["Q53"] = "Mixed"
    before = deepcopy(analyst)
    result = bridge.bridge_payload({"metrics": {"revenue": [1, 2]}}, analyst)
    assert analyst == before
    assert result["analyst_payload"] == before


def test_no_automatic_growth_or_investment_conclusion():
    result = bridge.bridge_payload({"metrics": {"revenue": [100, 200], "eps": [1, 2]}})
    assert result["automatic_growth_score"] is False
    assert result["automatic_growth_forecast"] is False
    assert result["automatic_investment_signal"] is False
    assert result["mos_or_research_gate_changed"] is False


def test_dependency_alias_lookup_does_not_calculate():
    payload = {"financials": {"operating_cash_flow": 500, "capital_expenditures": 100}}
    assert bridge.canonical_lookup(payload, "cash_flow_operations")["value"] == 500
    assert bridge.canonical_lookup(payload, "capex")["value"] == 100
    assert bridge.canonical_lookup(payload, "ccc")["available"] is False
