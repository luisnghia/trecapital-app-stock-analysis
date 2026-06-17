from __future__ import annotations
import json, math, os, re, subprocess, sys, time
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from module1_engine import (
    CompanyOverview, ensure_derived_metrics, append_ttm_row,
    load_overview_from_csv, load_timeseries_from_csv, build_mos_valuation_table,
    build_fcf_analysis_table, build_financial_ratio_table, build_combined_assessment_table,
)
from module2_engine import (
    build_module2_valuation_table, build_valuation_range, build_porter_moat_scorecard,
    build_beneish_mscore_table, build_accrual_quality_table, build_modified_jones_kothari_table,
    build_real_earnings_management_table, classify_company,
)
from report_exporter import _format_number_for_source_rule


def _company(industry="Sản xuất", ticker="TST"):
    return CompanyOverview(
        ticker=ticker, company_name="TestCo", exchange="TEST", industry=industry, sub_industry="Test",
        market_cap_bil=1_000, shares_outstanding_mil=100, current_price=10_000,
        eps=None, pe=None, pb=None, ps=None, roe=None, roa=None, roic=None,
    )


def _base_df(order="sorted"):
    rows = [
        {
            "ticker":"TST","period_type":"Y","period":"2023","year":2023,"revenue_bil":900,"net_profit_bil":90,"pretax_profit_bil":110,
            "gross_profit_bil":300,"selling_expense_bil":-40,"admin_expense_bil":-30,"cfo_bil":100,"capex_bil":20,"depreciation_bil":10,
            "receivables_change_bil":-10,"inventory_change_bil":-5,"payables_change_bil":3,"interest_paid_bil":-7,"tax_paid_bil":-20,
            "cash_equivalents_bil":40,"short_term_investments_bil":10,"current_assets_bil":300,"current_liabilities_bil":120,
            "accounts_receivable_bil":80,"accounts_payable_bil":60,"inventory_bil":70,"fixed_assets_bil":400,
            "short_term_debt_bil":30,"current_portion_long_term_debt_bil":10,"long_term_debt_bil":50,"bonds_payable_bil":20,"lease_liabilities_bil":5,
            "interest_expense_bil":-5,"financial_expense_bil":-25,"total_assets_bil":1000,"equity_bil":600,"shares_outstanding_mil":100,"cost_of_goods_sold_bil":600,
            "market_cap_bil":1000,"year_end_price":10000,
        },
        {
            "ticker":"TST","period_type":"Y","period":"2024","year":2024,"revenue_bil":1200,"net_profit_bil":120,"pretax_profit_bil":150,
            "gross_profit_bil":420,"selling_expense_bil":-50,"admin_expense_bil":-40,"cfo_bil":100,"capex_bil":-20,"depreciation_bil":12,
            "receivables_change_bil":-10,"inventory_change_bil":-5,"payables_change_bil":3,"interest_paid_bil":-7,"tax_paid_bil":-20,
            "cash_equivalents_bil":50,"short_term_investments_bil":20,"current_assets_bil":320,"current_liabilities_bil":100,
            "accounts_receivable_bil":90,"accounts_payable_bil":70,"inventory_bil":80,"fixed_assets_bil":440,
            "short_term_debt_bil":30,"current_portion_long_term_debt_bil":10,"long_term_debt_bil":50,"bonds_payable_bil":20,"lease_liabilities_bil":5,
            "interest_expense_bil":-5,"financial_expense_bil":-25,"total_assets_bil":1200,"equity_bil":700,"shares_outstanding_mil":100,"cost_of_goods_sold_bil":780,
            "market_cap_bil":1100,"year_end_price":11000,
        },
    ]
    if order == "reverse":
        rows = list(reversed(rows))
    return pd.DataFrame(rows)


def _quarter_df():
    qs=[]
    for i,(rev,np_,cfo,capex,assets,equity) in enumerate([(100,10,12,-2,900,500),(110,11,13,-3,1000,550),(120,12,14,-4,1100,600),(130,13,15,-5,1200,650)], start=1):
        qs.append({
            "ticker":"TST","period_type":"Q","period":f"Q{i}/2024","year":2024,"quarter":i,"revenue_bil":rev,"net_profit_bil":np_,"pretax_profit_bil":np_*1.25,
            "gross_profit_bil":rev*0.4,"selling_expense_bil":-5,"admin_expense_bil":-4,"cfo_bil":cfo,"capex_bil":capex,"depreciation_bil":1,
            "current_assets_bil":300+i*10,"current_liabilities_bil":100+i*5,"cash_equivalents_bil":40+i*2,"short_term_investments_bil":10+i*2,
            "fixed_assets_bil":400+i*10,"total_assets_bil":assets,"equity_bil":equity,"shares_outstanding_mil":100,"cost_of_goods_sold_bil":rev*0.6,
            "short_term_debt_bil":20,"current_portion_long_term_debt_bil":5,"long_term_debt_bil":50,"bonds_payable_bil":0,"lease_liabilities_bil":0,
            "cash_and_short_investments_change_bil":i,"roe_pct":99,"roa_pct":99,"roic_pct":99,"pe":99,"pb":99,"ps":99,"year_end_price":10000+i*100,
        })
    return pd.DataFrame(qs)


def _assert(name, cond, issues):
    if not bool(cond):
        issues.append(name)


def subprocess_ok(cmd, timeout=180):
    p = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return p.returncode == 0, p.stdout[-4000:]


def run_one_round(round_no:int):
    issues=[]; details={}
    # Runtime/compile checks.
    for label, cmd in {
        "compileall": [sys.executable, "-m", "compileall", "-q", "."],
        "formula_regression": [sys.executable, "tools/run_formula_regression_check.py"],
        "module2_self_check": [sys.executable, "tools/run_module2_self_check.py"],
    }.items():
        ok, out = subprocess_ok(cmd)
        details[label] = out
        _assert(f"{label} failed", ok, issues)

    # Financial formula checks on synthetic data, including unsorted input.
    out = ensure_derived_metrics(_base_df("reverse"))
    y2023 = out[out["period"].astype(str)=="2023"].iloc[0]
    y2024 = out[out["period"].astype(str)=="2024"].iloc[0]
    _assert("FCF positive capex normalized as outflow", abs(float(y2023["free_cash_flow_bil"])-80)<1e-9, issues)
    _assert("FCF negative capex normalized as outflow", abs(float(y2024["free_cash_flow_bil"])-80)<1e-9, issues)
    _assert("Operating WC excludes cash/STI/current debt", abs(float(y2024["operating_working_capital_bil"])-(320-50-20-(100-30-10)))<1e-9, issues)
    _assert("DuPont avg assets unaffected by input order", abs(float(y2024["asset_turnover"])-(1200/1100))<1e-9, issues)
    _assert("ROE avg equity unaffected by input order", abs(float(y2024["roe_actual_pct"])-(120/650*100))<1e-9, issues)
    _assert("Net debt includes interest-bearing debt components", abs(float(y2024["net_debt_bil"])-(30+10+50+20+5-50-20))<1e-9, issues)
    _assert("ROCE uses EBIT/core OP over capital employed", abs(float(y2024["roce_pct"])-(330/(1200-100)*100))<1e-9, issues)
    _assert("Interest coverage uses interest expense not total financial expense", abs(float(y2024["interest_coverage"])-(330/5))<1e-9, issues)
    _assert("WACC generated with audit detail", "WACC =" in str(y2024.get("wacc_formula_detail")), issues)

    # TTM correctness.
    ttm_df = append_ttm_row(out, ensure_derived_metrics(_quarter_df()))
    ttm = ttm_df[ttm_df["period"].astype(str).str.upper().eq("TTM")].iloc[-1]
    _assert("TTM revenue sums 4 quarters", abs(float(ttm["revenue_bil"])-460)<1e-9, issues)
    _assert("TTM CFO sums 4 quarters", abs(float(ttm["cfo_bil"])-54)<1e-9, issues)
    _assert("TTM avg assets uses trailing quarter mean", abs(float(ttm["avg_total_assets_bil"])-1050)<1e-9, issues)
    _assert("TTM ROE recalculates, does not copy quarterly ratio", abs(float(ttm["roe_actual_pct"])-(46/575*100))<1e-9 and abs(float(ttm.get("roe_pct"))-99)>1e-9, issues)
    _assert("TTM stale PE/PB/PS cleared", all(pd.isna(ttm.get(c)) for c in ["pe","pb","ps"] if c in ttm.index), issues)

    # MOS and valuation.
    c = _company()
    mos = build_mos_valuation_table(c, out, mos_rate=0.5)
    _assert("Module1 MOS valuation generated", not mos.empty and "Giá MOS chọn (đ/cp)" in mos.columns, issues)
    _assert("MOS prices are numeric VND per share", pd.to_numeric(mos["Giá MOS chọn (đ/cp)"], errors="coerce").notna().any(), issues)
    val = build_module2_valuation_table(c, out)
    rng = build_valuation_range(val, c.current_price)
    _assert("Module2 valuation has intrinsic values", val["Giá trị nội tại/cp"].notna().any(), issues)
    _assert("Module2 weighted valuation positive", rng.weighted_vnd is not None and rng.weighted_vnd > 0, issues)
    _assert("Giá mua MOS formatting is not percent", _format_number_for_source_rule(12345.6,"Giá mua MOS 30%") == "12,346", issues)
    _assert("MOS percent column remains percent", _format_number_for_source_rule(30,"MOS hiện tại %") == "30.0%", issues)

    # NLA/NCAV and bank logic.
    methods = set(val["Phương pháp"].astype(str))
    _assert("NLA and NCAV separated", {"Net Liquid Asset strict","Adjusted NCAV / Liquidation check"}.issubset(methods), issues)
    bank = _company("Ngân hàng", "BNK")
    bank_val = build_module2_valuation_table(bank, out)
    non_core = bank_val[bank_val["Phương pháp"].isin(["Earnings Power / P-E chuẩn hóa", "Giá trị theo lợi nhuận chủ sở hữu", "Vốn hóa dòng tiền tự do", "Net Liquid Asset strict", "Adjusted NCAV / Liquidation check"])]
    _assert("Bank non-core FCF/OE/NLA valuation weights zero", (pd.to_numeric(non_core["Trọng số %"], errors="coerce").fillna(0)==0).all(), issues)

    # Fraud/manipulation and moat.
    beneish = build_beneish_mscore_table(c, out)
    _assert("Beneish table generated", not beneish.empty and "M-Score" in beneish.columns, issues)
    _assert("Beneish TATA method disclosed", "Cách tính TATA" in beneish.columns, issues)
    accrual = build_accrual_quality_table(c, out)
    jones = build_modified_jones_kothari_table(c, out)
    rem = build_real_earnings_management_table(c, out)
    _assert("Accrual quality table generated", not accrual.empty, issues)
    _assert("Modified Jones/Kothari table generated", not jones.empty, issues)
    _assert("REM table generated", not rem.empty, issues)
    moat = build_porter_moat_scorecard(c, out)
    _assert("Moat weights sum to 100", abs(pd.to_numeric(moat["Trọng số %"], errors="coerce").sum()-100)<1e-9, issues)
    _assert("Moat total bounded 0-100", 0 <= float(moat.attrs.get("total_score", -999)) <= 100, issues)

    # Report/table format and source options.
    src_texts = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in [ROOT/"module1_dashboard.py", ROOT/"module2_dashboard.py", ROOT/"report_exporter.py", ROOT/"module2_engine.py", ROOT/"requirements.txt"] if p.exists())
    _assert("Online vnstock/KBS option removed", "Online vnstock/KBS" not in src_texts, issues)
    _assert("Online vnstock/VCI option removed", "Online vnstock/VCI" not in src_texts, issues)
    _assert("FCF tables use subheader title", 'st.subheader("Bảng phân tích sử dụng dòng tiền theo năm")' in src_texts and 'st.subheader("Bảng phân tích sử dụng dòng tiền theo quý")' in src_texts, issues)
    _assert("FCF tables use heatmap", "_style_financial_table(display).apply(section_styles" in src_texts, issues)

    # Sample data acquisition/normalization from CSV.
    sample_overview = load_overview_from_csv(ROOT/"sample_data/company_overview_sample.csv", "DCM")
    sample_y = ensure_derived_metrics(load_timeseries_from_csv(ROOT/"sample_data/financial_timeseries_year.csv", "DCM", "Y", 12))
    sample_q = ensure_derived_metrics(load_timeseries_from_csv(ROOT/"sample_data/financial_timeseries_quarter.csv", "DCM", "Q", 24))
    sample_ttm = append_ttm_row(sample_y, sample_q)
    _assert("Sample overview loads", sample_overview.ticker == "DCM", issues)
    _assert("Sample annual data loads", not sample_y.empty, issues)
    _assert("Sample quarterly data loads", not sample_q.empty, issues)
    _assert("Sample TTM row appended", sample_ttm["period"].astype(str).str.upper().isin(["TTM","T12M"]).any(), issues)
    _assert("Sample FCF analysis table generated", not build_fcf_analysis_table(sample_ttm).empty, issues)
    _assert("Sample financial ratio table generated", not build_financial_ratio_table(sample_ttm).empty, issues)
    sample_val = build_mos_valuation_table(sample_overview, sample_ttm)
    sample_alerts = build_combined_assessment_table(sample_overview, sample_ttm, sample_q, sample_val)
    _assert("Sample MOS valuation table generated", not sample_val.empty, issues)
    _assert("Sample combined assessment generated", not sample_alerts.empty, issues)

    return {"round": round_no, "issues": issues, "issue_count": len(issues), "details": details}


def main():
    max_rounds = int(os.environ.get("DEEP_AUDIT_MAX_ROUNDS", "20"))
    required_clean = int(os.environ.get("DEEP_AUDIT_REQUIRED_CLEAN", "5"))
    results=[]; clean_streak=0
    start=time.time()
    for i in range(1, max_rounds+1):
        r=run_one_round(i)
        results.append({k:v for k,v in r.items() if k != "details"})
        if r["issue_count"]==0:
            clean_streak += 1
        else:
            clean_streak = 0
        print(f"ROUND {i}: issues={r['issue_count']} clean_streak={clean_streak}")
        if r["issues"]:
            for issue in r["issues"]:
                print(" -", issue)
        if clean_streak >= required_clean:
            break
    summary={"required_clean_streak":required_clean,"max_rounds":max_rounds,"executed_rounds":len(results),"final_clean_streak":clean_streak,"passed":clean_streak>=required_clean,"elapsed_seconds":round(time.time()-start,2),"results":results}
    out=ROOT/"reports"/"V23_69_deep_audit_loop_summary.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY_JSON", out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
