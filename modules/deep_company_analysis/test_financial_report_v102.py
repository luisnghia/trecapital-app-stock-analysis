from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pandas as pd
from docx import Document

from modules.deep_company_analysis.financial_report_v102 import (
    MAX_ANNUAL_PERIODS,
    financial_matrix,
    financial_provenance,
    financial_report_guardrails,
)
from modules.deep_company_analysis.investment_checklist_report_v102 import build_investment_checklist_report_v102_docx


def _df() -> pd.DataFrame:
    rows = []
    for year in range(2015, 2025):
        n = year - 2014
        rows.append({
            "year": year, "period": str(year), "period_type": "Y",
            "revenue_bil": 1000.0 + n * 100, "gross_profit_bil": 300.0 + n * 30,
            "ebit_bil": 180.0 + n * 18, "ebitda_bil": 220.0 + n * 20,
            "net_profit_bil": 120.0 + n * 12, "npat_mi_bil": 110.0 + n * 11,
            "cfo_bil": 150.0 + n * 13, "capex_bil": -(40.0 + n),
            "cash_bil": 250.0 + n * 10, "total_debt_bil": 100.0 + n * 5,
            "equity_bil": 600.0 + n * 40, "roic_pct": 12.0 + n / 10,
            "roce_pct": 14.0 + n / 10, "accounts_receivable_bil": 120.0 + n,
            "inventory_bil": 100.0 + n * 2, "accounts_payable_bil": 80.0 + n,
            "ccc_days": 45.0 + n / 2, "source_module": "Trecapital Data Layer",
            "data_origin": "fixture/canonical",
        })
    rows.append({
        "year": 2025, "period": "TTM 2025", "period_type": "TTM",
        "revenue_bil": 2200.0, "gross_profit_bil": 660.0, "ebit_bil": 396.0,
        "ebitda_bil": 450.0, "net_profit_bil": 260.0, "npat_mi_bil": 245.0,
        "cfo_bil": 300.0, "capex_bil": -60.0, "cash_bil": 390.0,
        "total_debt_bil": 150.0, "equity_bil": 1050.0, "roic_pct": 14.0,
        "roce_pct": 16.0, "accounts_receivable_bil": 150.0, "inventory_bil": 140.0,
        "accounts_payable_bil": 105.0, "ccc_days": 49.0,
        "source_module": "Trecapital Data Layer", "data_origin": "fixture/canonical",
    })
    return pd.DataFrame(rows)


def test_matrix_is_max_10_annual_plus_ttm_and_derives_without_mutating_source() -> None:
    df = _df()
    original = df.copy(deep=True)
    matrix = financial_matrix(df)
    periods = list(matrix.columns[3:])
    assert len(periods) == MAX_ANNUAL_PERIODS + 1
    assert "TTM" in periods[-1].upper()
    fcf = matrix.loc[matrix["metric"] == "fcf", periods[-1]].iloc[0]
    assert fcf == 240.0
    cfo_ni = matrix.loc[matrix["metric"] == "cfo_to_ni", periods[-1]].iloc[0]
    assert round(float(cfo_ni), 1) == 115.4
    pd.testing.assert_frame_equal(df, original)


def test_provenance_has_required_contract_and_derived_fields() -> None:
    prov = financial_provenance(_df())
    for col in ("source_field", "source_module", "source_period", "data_origin"):
        assert col in prov.columns
    fcf = prov[prov["metric"] == "fcf"]
    assert not fcf.empty
    assert fcf["source_field"].str.contains("abs", regex=False).any()
    assert set(prov["source_module"]) == {"Trecapital Data Layer"}


def test_v102_docx_composes_v101_exact_checklist_and_embeds_charts() -> None:
    payload = build_investment_checklist_report_v102_docx(
        company_name="DGC",
        as_of="TTM 2025",
        canonical_financial_df=_df(),
        answers={},
        what_changed=["Canonical financial evidence refreshed."],
        critical_unknowns=["Q33-Q52 remain Unknown without evidence."],
    )
    document = Document(BytesIO(payload))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Investment Checklist Report" in text
    assert "10Y + TTM Financial Evidence" in text
    assert "Growth / cyclical normalization" in text
    assert "Financial provenance / source table" in text
    with ZipFile(BytesIO(payload)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]
    assert media, "V102 must embed quantitative chart image(s)"


def test_guardrails_forbid_investment_decision_side_effects() -> None:
    warnings = " ".join(financial_report_guardrails(_df())).lower()
    assert "second ssot" in warnings
    assert "valuation engine" in warnings
    assert "buy/hold/sell" in warnings
    assert "research gate" in warnings
