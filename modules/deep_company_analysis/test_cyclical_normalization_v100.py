import pandas as pd

from modules.deep_company_analysis.cyclical_normalization import (
    comparability_breaks,
    historical_cycle_table,
    normalization_guardrails,
    normalization_table,
)


def _sample():
    rows = []
    for year, revenue, gm, ebitm, roic, ni in [
        (2017, 100, 20, 10, 8, 8),
        (2018, 110, 21, 11, 9, 9),
        (2019, 120, 22, 12, 10, 10),
        (2020, 70, 12, 3, 2, 1),
        (2021, 130, 24, 13, 11, 12),
        (2022, 150, 27, 15, 14, 15),
        (2023, 160, 28, 16, 15, 17),
        (2024, 170, 29, 17, 16, 18),
        (2025, 180, 30, 18, 17, 20),
    ]:
        rows.append({
            "period": str(year), "period_type": "Y", "year": year,
            "revenue_bil": revenue, "gross_margin_pct": gm,
            "operating_margin_pct": ebitm, "roic_pct": roic,
            "net_profit_bil": ni,
            "comparability_status": "Not comparable" if year == 2020 else "Comparable",
            "comparability_note": "COVID disruption / accounting presentation break" if year == 2020 else "",
        })
    rows.append({
        "period": "TTM", "period_display": "TTM đến Q2/2026", "year": 2026,
        "revenue_bil": 190, "gross_margin_pct": 31, "operating_margin_pct": 18.5,
        "roic_pct": 17.5, "net_profit_bil": 21,
    })
    return pd.DataFrame(rows)


def test_normalization_excludes_ttm_from_baseline_and_keeps_overlay():
    table = normalization_table(_sample(), years=10)
    revenue = table.loc[table.metric == "revenue"].iloc[0]
    assert revenue.observations == 9
    assert revenue.latest_annual == 180
    assert revenue.latest_ttm == 190
    assert revenue.source_period == "TTM đến Q2/2026"


def test_trimmed_mean_reduces_single_cycle_outlier_in_long_window():
    table = normalization_table(_sample(), years=10)
    gm = table.loc[table.metric == "gross_margin"].iloc[0]
    assert gm.trimmed_mean > 20
    assert gm.trimmed_mean != gm.trough
    # Series.median is a method; use label access for the normalization column.
    assert gm.p25 <= gm["median"] <= gm.p75


def test_comparability_break_is_explicit_not_silently_removed():
    breaks = comparability_breaks(_sample())
    assert len(breaks) == 1
    assert breaks.iloc[0]["Period"] == "2020"
    assert "COVID" in breaks.iloc[0]["Comparability Note"]


def test_cycle_flags_cover_peak_and_trough_zones():
    history = historical_cycle_table(_sample())
    assert history["Cycle Flags"].str.contains("trough-zone").any()
    assert history["Cycle Flags"].str.contains("peak-zone").any()


def test_guardrails_preserve_analyst_and_valuation_boundary():
    warnings = normalization_guardrails(_sample())
    joined = " ".join(warnings)
    assert "intrinsic value" in joined
    assert "TTM" in joined
    assert "Comparability breaks" in joined


def test_sparse_data_stays_low_confidence_and_does_not_invent_metrics():
    df = pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 100},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 120},
    ])
    table = normalization_table(df)
    roic = table.loc[table.metric == "roic"].iloc[0]
    assert roic.observations == 0
    assert pd.isna(roic["median"])
    assert any("Fewer than 5 annual observations" in item for item in normalization_guardrails(df))
