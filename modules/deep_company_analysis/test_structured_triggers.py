from __future__ import annotations

from modules.deep_company_analysis import monitoring
from modules.deep_company_analysis.structured_triggers import build_numeric_trigger, build_statement_period_trigger


def test_structured_numeric_trigger_strings_round_trip():
    cases = [
        ("current_price", "<", 80000.0, "current_price", 80000.0),
        ("mos_pct", ">", 25.0, "mos_pct", 25.0),
        ("roic_pct", "<", 15.0, "roic_pct", 15.0),
        ("debt_ebitda", ">", 2.0, "debt_ebitda", 2.0),
        ("valuation_percentile", "<", 20.0, "valuation_percentile", 20.0),
    ]
    for metric, operator, threshold, parsed_metric, parsed_threshold in cases:
        text = build_numeric_trigger(metric, operator, threshold)
        rule = monitoring.parse_trigger(text)
        assert rule.kind == "numeric"
        assert rule.metric == parsed_metric
        assert rule.operator == operator
        assert rule.threshold == parsed_threshold


def test_specific_statement_period_trigger_round_trip():
    text = build_statement_period_trigger(2026, 3)
    assert text == "Review khi có BCTC Q3/2026"
    rule = monitoring.parse_trigger(text)
    assert rule.kind == "statement_period"
    assert rule.target_period == "2026-Q3"


def test_specific_statement_period_arms_before_target():
    text = "Review khi có BCTC Q3/2026"
    result = monitoring.evaluate_trigger("DGC", text, {"as_of": "2026-Q2"})
    assert result["status"] == "armed"
    assert not result["triggered"]
    assert result["target_period"] == "2026-Q3"


def test_specific_statement_period_triggers_at_target_or_later():
    text = "Review khi có BCTC Q3/2026"
    at_target = monitoring.evaluate_trigger("DGC", text, {"as_of": "2026-Q3"})
    assert at_target["triggered"]
    later = monitoring.evaluate_trigger("DGC", text, {"as_of": "2026-Q4"})
    assert later["triggered"]


def test_generic_statement_new_remains_backward_compatible():
    rule = monitoring.parse_trigger("Review khi có BCTC mới")
    assert rule.kind == "statement_new"
    assert not rule.target_period
