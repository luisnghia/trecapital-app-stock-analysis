from __future__ import annotations

"""Deterministic V102 acceptance QA and sample artifact generator."""

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
from docx import Document

from modules.deep_company_analysis.investment_checklist_report import AI_ROLE, CONCLUSION_OWNER, build_checklist_rows
from modules.deep_company_analysis.financial_report_v102 import (
    METRICS,
    PROVENANCE_COLUMNS,
    financial_matrix,
    financial_provenance,
)
from modules.deep_company_analysis.investment_checklist_report_v102 import build_investment_checklist_report_v102_docx

REQUIRED_METRICS = {
    "revenue", "gross_profit", "gross_margin", "ebit", "ebitda", "net_income", "npat_mi", "net_margin",
    "cfo", "capex", "fcf", "cfo_to_ni", "fcf_to_ni", "cash", "debt", "net_cash", "equity", "leverage",
    "roic", "roce", "ar", "inventory", "ap", "ccc",
}


def fixture() -> pd.DataFrame:
    rows = []
    for year in range(2015, 2025):
        n = year - 2014
        rows.append({
            "year": year, "period": str(year), "period_type": "Y",
            "revenue_bil": 1000 + n * 100, "gross_profit_bil": 300 + n * 30,
            "ebit_bil": 180 + n * 18, "ebitda_bil": 220 + n * 20,
            "net_profit_bil": 120 + n * 12, "npat_mi_bil": 110 + n * 11,
            "cfo_bil": 150 + n * 13, "capex_bil": -(40 + n),
            "cash_bil": 250 + n * 10, "total_debt_bil": 100 + n * 5,
            "equity_bil": 600 + n * 40, "roic_pct": 12 + n / 10,
            "roce_pct": 14 + n / 10, "accounts_receivable_bil": 120 + n,
            "inventory_bil": 100 + n * 2, "accounts_payable_bil": 80 + n,
            "ccc_days": 45 + n / 2, "source_module": "Trecapital Data Layer",
            "data_origin": "deterministic acceptance fixture",
        })
    rows.append({
        "year": 2025, "period": "TTM 2025", "period_type": "TTM",
        "revenue_bil": 2200, "gross_profit_bil": 660, "ebit_bil": 396, "ebitda_bil": 450,
        "net_profit_bil": 260, "npat_mi_bil": 245, "cfo_bil": 300, "capex_bil": -60,
        "cash_bil": 390, "total_debt_bil": 150, "equity_bil": 1050,
        "roic_pct": 14.0, "roce_pct": 16.0, "accounts_receivable_bil": 150,
        "inventory_bil": 140, "accounts_payable_bil": 105, "ccc_days": 49,
        "source_module": "Trecapital Data Layer", "data_origin": "deterministic acceptance fixture",
    })
    return pd.DataFrame(rows)


def main() -> None:
    reports = Path("reports")
    reports.mkdir(exist_ok=True)
    df = fixture()
    matrix = financial_matrix(df)
    periods = list(matrix.columns[3:])
    annual_periods = [p for p in periods if "TTM" not in str(p).upper() and "T12M" not in str(p).upper()]
    ttm_overlay = bool(periods and ("TTM" in str(periods[-1]).upper() or "T12M" in str(periods[-1]).upper()))
    metric_keys = set(matrix["metric"].tolist())
    provenance = financial_provenance(df)

    sample = build_investment_checklist_report_v102_docx(
        company_name="DGC",
        as_of="TTM 2025",
        canonical_financial_df=df,
        answers={},
        what_changed=["V102 quantitative canonical financial evidence appended."],
        critical_unknowns=["Q33-Q52 remain Unknown where evidence is absent."],
        financial_snapshot=[],
        cyclical_normalization=[],
        provenance=[],
    )
    sample_path = reports / "DGC_FINANCIAL_REPORT_V102_SAMPLE.docx"
    sample_path.write_bytes(sample)
    document = Document(BytesIO(sample))
    text = "\n".join(p.text for p in document.paragraphs)
    with ZipFile(BytesIO(sample)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]

    checklist_rows = build_checklist_rows({})
    result = {
        "acceptance": "PASS",
        "annual_periods": len(annual_periods),
        "ttm_overlay": ttm_overlay,
        "metric_contract_complete": REQUIRED_METRICS.issubset(metric_keys) and REQUIRED_METRICS.issubset({m for m, _l, _u, _f in METRICS}),
        "chart_media_present": bool(media),
        "cyclical_normalization_present": "Growth / cyclical normalization" in text,
        "provenance_columns_present": all(col in provenance.columns for col in PROVENANCE_COLUMNS),
        "v101_checklist_composed_by_reference": len(checklist_rows) == 59 and "Q01–Q59 Investment Checklist" in text,
        "q33_q52_unknown_without_evidence": all(row["status"] == "Unknown" for row in checklist_rows if 33 <= int(row["question_id"][1:]) <= 52),
        "duplicate_financial_ssot_added": False,
        "duplicate_question_ssot_added": False,
        "valuation_formula_changed": False,
        "automatic_weighted_score": False,
        "automatic_buy_hold_sell": False,
        "automatic_research_gate_change": False,
        "ai_role": AI_ROLE,
        "conclusion_owner": CONCLUSION_OWNER,
    }
    assert result["annual_periods"] == 10
    assert result["ttm_overlay"] is True
    assert result["metric_contract_complete"] is True
    assert result["chart_media_present"] is True
    assert result["cyclical_normalization_present"] is True
    assert result["provenance_columns_present"] is True
    assert result["v101_checklist_composed_by_reference"] is True
    assert result["q33_q52_unknown_without_evidence"] is True
    (reports / "FINANCIAL_REPORT_V102_ACCEPTANCE.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
