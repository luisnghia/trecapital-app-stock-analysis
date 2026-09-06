from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter8_data_bridge as bridge


def _canonical_df() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "period": "2024", "year": 2024, "period_type": "Y",
            "revenue_bil": 1000.0, "gross_profit_bil": 300.0,
            "operating_profit_bil": 180.0, "cfo_bil": 220.0,
            "capex_bil": -80.0, "fcf_bil": 140.0,
            "cash_bil": 500.0, "cash_dividend_bil": -50.0,
            "share_buyback_cash_bil": -20.0, "shares_repurchased": 2.0,
            "shares_outstanding_mil": 100.0, "roic_pct": 18.0,
            "selling_expense_bil": 25.0, "admin_expense_bil": 35.0,
        },
        {
            "period": "2025", "year": 2025, "period_type": "Y",
            "revenue_bil": 1100.0, "gross_profit_bil": 352.0,
            "operating_profit_bil": 210.0, "cfo_bil": 250.0,
            "capex_bil": -90.0, "fcf_bil": 160.0,
            "cash_bil": 560.0, "cash_dividend_bil": -55.0,
            "shares_outstanding_mil": 97.0, "roic_pct": 19.0,
            "selling_expense_bil": 26.0, "admin_expense_bil": 36.0,
        },
    ])


def test_manager_reference_reuses_chapter7_ids_only():
    ch7_payload = {"management_profiles": [
        {"Manager ID": "m1", "Manager": "CEO A", "Current Role": "CEO", "Analyst Classification": "LT1", "Confidence": "Medium"},
        {"Manager ID": "m2", "Manager": "CFO B", "Current Role": "CFO", "Analyst Classification": "Unknown", "Confidence": "Unknown"},
    ]}
    out = bridge.build_manager_reference(ch7_payload)
    assert out["Manager ID"].tolist() == ["m1", "m2"]
    assert set(out["Source"]) == {bridge.MANAGER_SOURCE_LABEL}


def test_manager_reference_does_not_invent_manager_when_ch7_missing():
    out = bridge.build_manager_reference(None)
    assert out.empty


def test_guidance_outcome_is_arithmetic_only():
    out = bridge.normalize_guidance_rows([
        {"Issued Date": "2025-01-01", "Metric": "EPS", "Horizon": "FY2025", "Guidance Low": 10, "Guidance High": 12, "Actual": 12.5, "Guidance Event": "Issued", "Source": "Official disclosure"},
        {"Issued Date": "2025-06-01", "Metric": "EPS", "Horizon": "FY2025", "Guidance Point": 11, "Actual": 11, "Guidance Event": "Issued", "Source": "Official disclosure"},
        {"Issued Date": "2025-09-01", "Metric": "EPS", "Horizon": "FY2025", "Guidance Event": "Withdrawn", "Actual": 9, "Source": "Official disclosure"},
    ])
    assert out["Outcome"].tolist() == ["Beat", "Meet", "N/A"]
    assert not any(term in " ".join(out.columns).lower() for term in ["manipulation", "sandbagging", "quality score"])


def test_q45_cost_context_uses_canonical_and_derives_cogs_without_quality_judgment():
    out = bridge.build_q45_cost_context(_canonical_df())
    assert out.iloc[0]["COGS canonical/derived (tỷ)"] == 700.0
    assert out.iloc[0]["SG&A explicit (tỷ)"] == 60.0
    assert set(out["Source"]) == {bridge.CANONICAL_SOURCE_LABEL}
    assert "analyst determines" in out.iloc[0]["Boundary"].lower()


def test_q46_keeps_exact_five_shearn_buckets_and_does_not_add_debt_paydown():
    out = bridge.build_q46_capital_allocation_context(_canonical_df())
    bucket_cols = [c for c in out.columns if c[:2] in {"1.", "2.", "3.", "4.", "5."}]
    assert len(bucket_cols) == 5
    assert not any("debt" in c.lower() or "nợ vay" in c.lower() for c in bucket_cols)
    assert out.iloc[0]["1. Reinvest — CAPEX proxy (tỷ)"] == 80.0
    assert out.iloc[0]["2. Hold cash — Ending cash stock (tỷ)"] == 500.0


def test_q47_share_count_decline_is_not_relabelled_as_buyback():
    out = bridge.build_q47_buyback_context(_canonical_df())
    assert out.iloc[0]["Explicit buyback field available?"] == "Yes"
    assert out.iloc[1]["Share-count change"] == -3.0
    assert out.iloc[1]["Explicit buyback field available?"] == "No"
    assert "not proof of buyback" in out.iloc[1]["Boundary"].lower()


def test_missing_explicit_buyback_stays_missing():
    df = pd.DataFrame([
        {"period": "2024", "year": 2024, "period_type": "Y", "shares_outstanding_mil": 100},
        {"period": "2025", "year": 2025, "period_type": "Y", "shares_outstanding_mil": 90},
    ])
    out = bridge.build_q47_buyback_context(df)
    assert out["Buyback cash explicit (tỷ)"].isna().all()
    assert out["Shares repurchased explicit"].isna().all()
    assert set(out["Explicit buyback field available?"]) == {"No"}


def test_phase8b_package_keeps_ssot_and_analyst_boundary():
    package = bridge.build_phase8b_context("dgc", _canonical_df(), chapter7_payload=None, guidance_rows=None)
    assert package["ticker"] == "DGC"
    assert package["financial_ssot"] == bridge.CANONICAL_SOURCE_LABEL
    assert package["manager_ssot"] == bridge.MANAGER_SOURCE_LABEL
    assert "no management score" in package["analyst_boundary"].lower()
    assert any("manager master" in warning.lower() for warning in package["warnings"])
    assert any("guidance" in warning.lower() for warning in package["warnings"])
