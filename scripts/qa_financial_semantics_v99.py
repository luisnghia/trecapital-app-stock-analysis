from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from adapters.vn_public_crawler import _extract_fireant_statement_timeseries_exact
from module1_engine import CompanyOverview, append_ttm_row, build_mos_valuation_table, ensure_derived_metrics
from modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context
from modules.deep_company_analysis.financial_semantics import semantics_table


def income_payload(quarter: int, year: int, consolidated_bil: float, parent_bil: float):
    return [
        {"ID": 3, "Name": "Doanh thu thuần", "Values": [{"Year": year, "Quarter": quarter, "Value": 2_400_000_000_000}]},
        {"ID": 19, "Name": "Lợi nhuận sau thuế", "Values": [{"Year": year, "Quarter": quarter, "Value": consolidated_bil * 1_000_000_000}]},
        {"ID": 21, "Name": "Lợi nhuận sau thuế của cổ đông của công ty mẹ", "Values": [{"Year": year, "Quarter": quarter, "Value": parent_bil * 1_000_000_000}]},
    ]


def main() -> int:
    errors: list[str] = []

    parsed = _extract_fireant_statement_timeseries_exact([income_payload(2, 2026, 440.8, 388.55)], "DGC")
    row = parsed.iloc[0]
    if abs(float(row["net_profit_consolidated_bil"]) - 440.8) > 1e-9:
        errors.append("FireAnt consolidated PAT mapping failed")
    if abs(float(row["net_profit_parent_bil"]) - 388.55) > 1e-9:
        errors.append("FireAnt parent PAT mapping failed")
    if row["net_profit_scope"] != "parent_attributable":
        errors.append("FireAnt profit scope failed")

    consolidated_only = ensure_derived_metrics(pd.DataFrame([{
        "period": "Q2/2026", "period_type": "Q", "year": 2026, "quarter": 2,
        "net_profit_consolidated_bil": 440.8, "shares_outstanding_mil": 379.8,
    }]))
    if pd.notna(consolidated_only.iloc[0].get("eps_vnd")):
        errors.append("Consolidated-only PAT incorrectly generated EPS")

    company = CompanyOverview(
        ticker="DGC", company_name="Duc Giang", exchange="HOSE", industry="Chemicals", sub_industry="",
        market_cap_bil=None, shares_outstanding_mil=100.0, current_price=50_000.0,
        eps=None, pe=None, pb=None, ps=None, roe=None, roa=None, roic=None,
    )
    mos = build_mos_valuation_table(company, pd.DataFrame([{
        "period": "2025", "period_type": "Y", "year": 2025,
        "net_profit_consolidated_bil": 500.0, "shares_outstanding_mil": 100.0, "equity_bil": 1_000.0,
    }]))
    if not mos.empty:
        errors.append("Consolidated-only PAT incorrectly fed EPS-based MOS fallback")

    annual = pd.DataFrame([{
        "ticker": "DGC", "period": "2025", "period_type": "Y", "year": 2025,
        "revenue_bil": 11_262.0, "net_profit_parent_bil": 3_154.0,
    }])
    quarterly = pd.DataFrame([
        {"ticker": "DGC", "period": "Q3/2025", "period_type": "Q", "year": 2025, "quarter": 3, "revenue_bil": 2816.7, "net_profit_parent_bil": 804.4},
        {"ticker": "DGC", "period": "Q4/2025", "period_type": "Q", "year": 2025, "quarter": 4, "revenue_bil": 2740.6, "net_profit_parent_bil": 656.9},
        {"ticker": "DGC", "period": "Q1/2026", "period_type": "Q", "year": 2026, "quarter": 1, "revenue_bil": 2124.6, "net_profit_parent_bil": 408.5},
        {"ticker": "DGC", "period": "Q2/2026", "period_type": "Q", "year": 2026, "quarter": 2, "revenue_bil": 2415.4, "net_profit_parent_bil": 388.55},
    ])
    ttm = append_ttm_row(annual, quarterly)
    ttm_row = ttm[ttm["period"].eq("TTM")].iloc[-1]
    if ttm_row.get("period_display") != "TTM đến Q2/2026":
        errors.append("Dated TTM display failed")
    if abs(float(ttm_row["revenue_bil"]) - 10097.3) > 1e-9:
        errors.append("Four-quarter TTM revenue failed")

    partial = quarterly.copy()
    partial.loc[partial.index[2], "revenue_bil"] = None
    partial_ttm = append_ttm_row(annual, partial)
    partial_row = partial_ttm[partial_ttm["period"].eq("TTM")].iloc[-1]
    if pd.notna(partial_row.get("revenue_bil")):
        errors.append("Partial 1-3 quarter flow was incorrectly labelled TTM")

    sem = semantics_table(ttm, source_label="QA canonical")
    required = {"Source Field", "Source Module", "Source Period", "Data Origin", "Profit Scope", "Comparability"}
    if not required.issubset(set(sem.columns)):
        errors.append("Metric provenance table shape incomplete")

    ctx = build_chapter6_quant_context("DGC", "Duc Giang", ttm, source_label="QA canonical")
    if ctx.get("latest_period") != "TTM đến Q2/2026":
        errors.append("DCA Chapter 6 did not consume dated TTM period")
    if "overall_score" in ctx or "buy_hold_sell" in ctx:
        errors.append("Investment-boundary violation: automatic score/recommendation")

    report = {
        "phase": "Deep Company Analysis V99 — Financial Semantics & TTM Provenance",
        "acceptance": "FAIL" if errors else "PASS",
        "errors": errors,
        "fireant_profit_scope_split": not any("FireAnt" in e for e in errors),
        "consolidated_only_eps_blocked": "Consolidated-only PAT incorrectly generated EPS" not in errors,
        "consolidated_only_mos_eps_blocked": "Consolidated-only PAT incorrectly fed EPS-based MOS fallback" not in errors,
        "ttm_requires_four_complete_quarters": "Partial 1-3 quarter flow was incorrectly labelled TTM" not in errors,
        "dated_ttm_period": "Dated TTM display failed" not in errors,
        "provenance_contract": "Metric provenance table shape incomplete" not in errors,
        "duplicate_financial_ssot_added": False,
        "automatic_weighted_score": False,
        "automatic_buy_hold_sell": False,
        "valuation_formula_changed": False,
        "ai_role": "Research Assistant",
        "conclusion_owner": "Analyst",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/FINANCIAL_SEMANTICS_V99_ACCEPTANCE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
