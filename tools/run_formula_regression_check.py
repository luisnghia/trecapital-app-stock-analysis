from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from module1_engine import CompanyOverview, ensure_derived_metrics, build_mos_valuation_table, append_ttm_row
from module2_engine import build_module2_valuation_table, build_porter_moat_scorecard, build_beneish_mscore_table


def _company() -> CompanyOverview:
    return CompanyOverview(
        ticker="TST", company_name="TestCo", exchange="TEST", industry="Sản xuất", sub_industry="Test",
        market_cap_bil=1_000, shares_outstanding_mil=100, current_price=10_000,
        eps=None, pe=None, pb=None, ps=None, roe=None, roa=None, roic=None,
    )


def main() -> int:
    base = pd.DataFrame([
        {
            "ticker": "TST", "period_type": "Y", "period": "2023", "year": 2023,
            "revenue_bil": 900, "net_profit_bil": 90, "pretax_profit_bil": 110,
            "gross_profit_bil": 300, "selling_expense_bil": -40, "admin_expense_bil": -30,
            "cfo_bil": 100, "capex_bil": 20, "depreciation_bil": 10,
            "receivables_change_bil": -10, "inventory_change_bil": -5, "payables_change_bil": 3,
            "interest_paid_bil": -7, "tax_paid_bil": -20, "other_operating_cash_out_bil": -2,
            "cash_equivalents_bil": 40, "short_term_investments_bil": 10,
            "current_assets_bil": 300, "current_liabilities_bil": 120,
            "accounts_receivable_bil": 80, "accounts_payable_bil": 60, "inventory_bil": 70, "fixed_assets_bil": 400,
            "short_term_debt_bil": 30, "current_portion_long_term_debt_bil": 10,
            "long_term_debt_bil": 50, "bonds_payable_bil": 20, "lease_liabilities_bil": 5,
            "interest_expense_bil": -5, "financial_expense_bil": -25,
            "total_assets_bil": 1_000, "equity_bil": 600, "shares_outstanding_mil": 100,
            "cost_of_goods_sold_bil": 600,
        },
        {
            "ticker": "TST", "period_type": "Y", "period": "2024", "year": 2024,
            "revenue_bil": 1_200, "net_profit_bil": 120, "pretax_profit_bil": 150,
            "gross_profit_bil": 420, "selling_expense_bil": -50, "admin_expense_bil": -40,
            "cfo_bil": 100, "capex_bil": -20, "depreciation_bil": 12,
            "receivables_change_bil": -10, "inventory_change_bil": -5, "payables_change_bil": 3,
            "interest_paid_bil": -7, "tax_paid_bil": -20, "other_operating_cash_out_bil": -2,
            "cash_equivalents_bil": 50, "short_term_investments_bil": 20,
            "current_assets_bil": 320, "current_liabilities_bil": 100,
            "accounts_receivable_bil": 90, "accounts_payable_bil": 70, "inventory_bil": 80, "fixed_assets_bil": 440,
            "short_term_debt_bil": 30, "current_portion_long_term_debt_bil": 10,
            "long_term_debt_bil": 50, "bonds_payable_bil": 20, "lease_liabilities_bil": 5,
            "interest_expense_bil": -5, "financial_expense_bil": -25,
            "total_assets_bil": 1_200, "equity_bil": 700, "shares_outstanding_mil": 100,
            "cost_of_goods_sold_bil": 780,
        },
    ])
    out = ensure_derived_metrics(base)
    y2023 = out[out["period"].astype(str) == "2023"].iloc[0]
    y2024 = out[out["period"].astype(str) == "2024"].iloc[0]

    checks = {
        "FCF positive capex treated as outflow": abs(float(y2023["free_cash_flow_bil"]) - 80.0) < 1e-9,
        "FCF negative capex unchanged": abs(float(y2024["free_cash_flow_bil"]) - 80.0) < 1e-9,
        "WC excludes interest tax other CFO bridge": abs(float(y2024["working_capital_change_bil"]) - (-12.0)) < 1e-9,
        "DuPont asset turnover uses average assets": abs(float(y2024["asset_turnover"]) - (1200 / 1100)) < 1e-9,
        "Net debt includes CP LTD bonds leases": abs(float(y2024["net_debt_bil"]) - (30 + 10 + 50 + 20 + 5 - 50 - 20)) < 1e-9,
        "Interest coverage prioritizes interest expense": abs(float(y2024["interest_coverage"]) - (330 / 5)) < 1e-9,
        "Operating WC excludes cash investments and current debt": abs(float(y2024["operating_working_capital_bil"]) - (320 - 50 - 20 - (100 - 30 - 10))) < 1e-9,
        "Li Lu deployed capital uses debt-adjusted operating WC": abs(float(y2024["deployed_capital_bil"]) - ((320 - 50 - 20 - (100 - 30 - 10)) + float(y2024["fixed_assets_bil"]))) < 1e-9 if pd.notna(y2024.get("fixed_assets_bil")) else True,
        "ROCE is computed as EBIT proxy over capital employed": abs(float(y2024["roce_pct"]) - (330 / (1200 - 100) * 100)) < 1e-9,
    }

    stale_eps_company = _company()
    stale_eps_company.eps = 100_000.0
    mos_table = build_mos_valuation_table(stale_eps_company, out, mos_rate=0.5)
    eps_discount_value = float(mos_table.loc[mos_table["Phương pháp"] == "Phil Town/EPS chiết khấu", "Giá trị nội tại (đ/cp)"].iloc[0])
    # If stale overview EPS were used, this row would be ~1,000,000 đ/cp.
    checks["Module1 MOS derives EPS from statements before overview fallback"] = eps_discount_value < 20_000

    dashboard_source = (ROOT / "module1_dashboard.py").read_text(encoding="utf-8")
    checks["FCF analysis renderer applies app heatmap"] = "_style_financial_table(display).apply(section_styles" in dashboard_source

    valuation = build_module2_valuation_table(_company(), out)
    method_names = set(valuation["Phương pháp"].astype(str))
    checks["NLA strict row separated from NCAV"] = {"Net Liquid Asset strict", "Adjusted NCAV / Liquidation check"}.issubset(method_names)
    checks["NLA strict excludes inventory"] = valuation.loc[valuation["Phương pháp"] == "Net Liquid Asset strict", "Cơ sở tính"].astype(str).str.contains("Không cộng tồn kho", regex=False).any()

    moat = build_porter_moat_scorecard(_company(), out)
    checks["Moat weights sum to 100"] = abs(pd.to_numeric(moat["Trọng số %"], errors="coerce").sum() - 100.0) < 1e-9
    checks["Moat total score bounded 0-100"] = 0.0 <= float(moat.attrs.get("total_score", -1)) <= 100.0

    beneish = build_beneish_mscore_table(_company(), out)
    latest_beneish = beneish.iloc[-1]
    # Balance-sheet accruals 2024 = ΔCA 20 - ΔCash 10 - ΔCL(-20) + ΔSTD 0 - Dep 12 = 18; / TA 1200 = 0.015.
    checks["Beneish TATA uses balance-sheet accruals before CFO proxy"] = abs(float(latest_beneish["TATA"]) - 0.015) < 1e-9
    checks["Beneish discloses TATA method"] = "Balance-sheet accruals" in str(latest_beneish.get("Cách tính TATA", ""))


    # V23.67: TTM rows should sum flow items and use trailing-quarter average denominators.
    quarters = pd.DataFrame([
        {"ticker":"TST","period_type":"Q","period":"Q1/2024","year":2024,"quarter":1,"revenue_bil":100,"net_profit_bil":10,"cfo_bil":12,"capex_bil":-2,"cost_of_goods_sold_bil":60,"cash_and_short_investments_change_bil":1,"total_assets_bil":900,"equity_bil":500,"current_assets_bil":300,"current_liabilities_bil":100,"cash_equivalents_bil":40,"short_term_investments_bil":10,"fixed_assets_bil":400,"shares_outstanding_mil":100,"roe_pct":99,"roa_pct":99,"roic_pct":99,"pe":99,"pb":99,"ps":99},
        {"ticker":"TST","period_type":"Q","period":"Q2/2024","year":2024,"quarter":2,"revenue_bil":110,"net_profit_bil":11,"cfo_bil":13,"capex_bil":-3,"cost_of_goods_sold_bil":66,"cash_and_short_investments_change_bil":2,"total_assets_bil":1000,"equity_bil":550,"current_assets_bil":310,"current_liabilities_bil":105,"cash_equivalents_bil":42,"short_term_investments_bil":12,"fixed_assets_bil":410,"shares_outstanding_mil":100,"roe_pct":99,"roa_pct":99,"roic_pct":99,"pe":99,"pb":99,"ps":99},
        {"ticker":"TST","period_type":"Q","period":"Q3/2024","year":2024,"quarter":3,"revenue_bil":120,"net_profit_bil":12,"cfo_bil":14,"capex_bil":-4,"cost_of_goods_sold_bil":72,"cash_and_short_investments_change_bil":3,"total_assets_bil":1100,"equity_bil":600,"current_assets_bil":320,"current_liabilities_bil":110,"cash_equivalents_bil":44,"short_term_investments_bil":14,"fixed_assets_bil":420,"shares_outstanding_mil":100,"roe_pct":99,"roa_pct":99,"roic_pct":99,"pe":99,"pb":99,"ps":99},
        {"ticker":"TST","period_type":"Q","period":"Q4/2024","year":2024,"quarter":4,"revenue_bil":130,"net_profit_bil":13,"cfo_bil":15,"capex_bil":-5,"cost_of_goods_sold_bil":78,"cash_and_short_investments_change_bil":4,"total_assets_bil":1200,"equity_bil":650,"current_assets_bil":330,"current_liabilities_bil":115,"cash_equivalents_bil":46,"short_term_investments_bil":16,"fixed_assets_bil":430,"shares_outstanding_mil":100,"roe_pct":99,"roa_pct":99,"roic_pct":99,"pe":99,"pb":99,"ps":99},
    ])
    ttm_df = append_ttm_row(out, ensure_derived_metrics(quarters))
    ttm = ttm_df[ttm_df["period"].astype(str).str.upper().eq("TTM")].iloc[-1]
    checks["TTM cash/STI change is 4Q sum"] = abs(float(ttm["cash_and_short_investments_change_bil"]) - 10.0) < 1e-9
    checks["TTM COGS is 4Q sum"] = abs(float(ttm["cost_of_goods_sold_bil"]) - (60+66+72+78)) < 1e-9
    checks["TTM avg assets uses trailing-quarter mean"] = abs(float(ttm["avg_total_assets_bil"]) - 1050.0) < 1e-9
    checks["TTM avg equity uses trailing-quarter mean"] = abs(float(ttm["avg_equity_bil"]) - 575.0) < 1e-9
    checks["TTM ROE recalculates from TTM profit and avg equity"] = abs(float(ttm["roe_actual_pct"]) - ((10+11+12+13) / 575.0 * 100)) < 1e-9 and abs(float(ttm["roe_pct"]) - 99.0) > 1e-9
    checks["TTM ROA recalculates from TTM profit and avg assets"] = abs(float(ttm["roa_actual_pct"]) - ((10+11+12+13) / 1050.0 * 100)) < 1e-9 and abs(float(ttm["roa_pct"]) - 99.0) > 1e-9
    checks["TTM does not carry stale quarterly valuation multiples"] = all(pd.isna(ttm.get(c)) for c in ["pe", "pb", "ps"] if c in ttm.index)

    bank_company = CompanyOverview(
        ticker="BNK", company_name="Mock Bank", exchange="TEST", industry="Ngân hàng", sub_industry="Bank",
        market_cap_bil=1_000, shares_outstanding_mil=100, current_price=10_000,
        eps=1_000, pe=None, pb=None, ps=None, roe=15, roa=None, roic=None,
    )
    bank_valuation = build_module2_valuation_table(bank_company, out)
    non_core = bank_valuation[bank_valuation["Phương pháp"].isin([
        "Earnings Power / P-E chuẩn hóa", "Giá trị theo lợi nhuận chủ sở hữu", "Vốn hóa dòng tiền tự do", "Net Liquid Asset strict", "Adjusted NCAV / Liquidation check"
    ])]
    checks["Financial company non-core valuation weights zero"] = (pd.to_numeric(non_core["Trọng số %"], errors="coerce").fillna(0) == 0).all()

    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
