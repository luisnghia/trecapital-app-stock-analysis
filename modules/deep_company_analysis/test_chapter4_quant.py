from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter4_quant import (
    build_company_snapshot,
    build_industry_distribution,
    build_peer_benchmark,
    build_peer_table,
    pricing_context,
    supply_chain_context,
)


def _annual() -> pd.DataFrame:
    rows = []
    for idx, year in enumerate(range(2017, 2027), start=1):
        revenue = 1000.0 + idx * 100.0
        gross_margin = 20.0 + idx
        ebit_margin = 10.0 + idx * 0.5
        rows.append({
            "ticker": "AAA",
            "period": str(year),
            "period_type": "Y",
            "year": year,
            "revenue_bil": revenue,
            "gross_margin_pct": gross_margin,
            "core_operating_margin_pct": ebit_margin,
            "free_cash_flow_bil": revenue * 0.08,
            "roic_pct": float(idx),
            "cash_conversion_cycle_days": 50.0 - idx,
            "inventory_turnover": 3.0 + idx * 0.1,
            "dso_days": 30.0,
            "dio_days": 40.0,
            "dpo_days": 20.0 + idx,
            "revenue_growth_yoy_pct": 5.0 + idx * 0.2,
        })
    rows.append({
        "ticker": "AAA",
        "period": "TTM",
        "period_type": "TTM",
        "revenue_bil": 2200.0,
        "gross_margin_pct": 32.0,
        "core_operating_margin_pct": 16.0,
        "free_cash_flow_bil": 220.0,
        "roic_pct": 12.0,
        "cash_conversion_cycle_days": 37.0,
        "inventory_turnover": 4.4,
        "dso_days": 29.0,
        "dio_days": 35.0,
        "dpo_days": 27.0,
    })
    return pd.DataFrame(rows)


def test_company_snapshot_uses_annual_medians_and_ttm_latest():
    snap = build_company_snapshot("AAA", "Alpha", _annual(), "fixture")
    assert snap["latest_period"] == "TTM"
    assert snap["roic_latest"] == 12.0
    assert snap["roic_5y_median"] == 8.0
    assert snap["roic_10y_median"] == 5.5
    assert snap["roic_min"] == 1.0
    assert snap["roic_max"] == 10.0
    assert snap["gross_margin_latest"] == 32.0
    assert snap["fcf_margin_latest"] == 10.0
    assert snap["provenance"]["source_label"] == "fixture"


def test_phase4b_has_explicit_no_auto_judgement_guardrails():
    snap = build_company_snapshot("AAA", "Alpha", _annual(), "fixture")
    guardrails = snap["guardrails"]
    assert guardrails["auto_moat_conclusion"] is False
    assert guardrails["auto_pricing_power_conclusion"] is False
    assert guardrails["auto_industry_quality_conclusion"] is False
    assert guardrails["auto_competition_intensity_conclusion"] is False
    assert guardrails["auto_supplier_quality_conclusion"] is False


def test_peer_distribution_is_descriptive_not_good_bad_classifier():
    a = build_company_snapshot("AAA", "Alpha", _annual(), "fixture")
    b_df = _annual().copy()
    b_df["roic_pct"] = pd.to_numeric(b_df["roic_pct"], errors="coerce") + 10.0
    b = build_company_snapshot("BBB", "Beta", b_df, "fixture")
    peers = build_peer_table([a, b])
    dist = build_industry_distribution(peers)
    assert dist["peer_count"] == 2
    assert dist["median_roic"] == 17.0
    assert dist["spread_roic"] == 10.0
    assert dist["industry_quality"] is None


def test_peer_benchmark_does_not_choose_ideal_company():
    a = build_company_snapshot("AAA", "Alpha", _annual(), "fixture")
    b_df = _annual().copy()
    b_df["gross_margin_pct"] = pd.to_numeric(b_df["gross_margin_pct"], errors="coerce") + 5.0
    b = build_company_snapshot("BBB", "Beta", b_df, "fixture")
    bench = build_peer_benchmark(build_peer_table([a, b]), "AAA")
    assert not bench.empty
    assert "Peer Min" in bench.columns
    assert "Peer Max" in bench.columns
    assert "Ideal Source" not in bench.columns
    assert "Best" not in bench.columns


def test_pricing_context_is_margin_history_only_not_price_event_inference():
    snap = build_company_snapshot("AAA", "Alpha", _annual(), "fixture")
    ctx = pricing_context(snap)
    assert len(ctx) == 10
    assert "Gross Margin %" in ctx.columns
    assert "EBIT Margin %" in ctx.columns
    assert "Price Increase %" not in ctx.columns
    assert "Pricing Power" not in ctx.columns


def test_supply_chain_context_keeps_operating_metrics_without_supplier_judgement():
    snap = build_company_snapshot("AAA", "Alpha", _annual(), "fixture")
    ctx = supply_chain_context(snap)
    assert len(ctx) == 10
    assert "Vòng quay tồn kho" in ctx.columns
    assert "CCC ngày" in ctx.columns
    assert "Supplier Relationship" not in ctx.columns
    assert "Supplier Quality" not in ctx.columns


def test_missing_roic_is_left_missing_not_fabricated():
    df = _annual().drop(columns=["roic_pct"])
    snap = build_company_snapshot("AAA", "Alpha", df, "fixture")
    assert snap["roic_latest"] is None
    assert snap["roic_5y_median"] is None
    peers = build_peer_table([snap])
    assert build_industry_distribution(peers) == {}
