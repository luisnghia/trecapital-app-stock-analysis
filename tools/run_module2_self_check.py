from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from module1_engine import load_overview_from_csv, load_timeseries_from_csv, ensure_derived_metrics, append_ttm_row
from module2_engine import (
    classify_company,
    build_module2_valuation_table,
    build_valuation_range,
    build_porter_moat_scorecard,
    build_value_chain_table,
    build_risk_scenario_table,
    build_beneish_mscore_table,
    build_accrual_quality_table,
    build_modified_jones_kothari_table,
    build_real_earnings_management_table,
)


def main() -> int:
    ticker = "DCM"
    company = load_overview_from_csv(ROOT / "sample_data" / "company_overview_sample.csv", ticker)
    annual = ensure_derived_metrics(load_timeseries_from_csv(ROOT / "sample_data" / "financial_timeseries_year.csv", ticker, "Y", 12))
    quarterly = ensure_derived_metrics(load_timeseries_from_csv(ROOT / "sample_data" / "financial_timeseries_quarter.csv", ticker, "Q", 24))
    annual = append_ttm_row(annual, quarterly)
    cls = classify_company(company, annual)
    valuation = build_module2_valuation_table(company, annual)
    rng = build_valuation_range(valuation, company.current_price)
    moat = build_porter_moat_scorecard(company, annual)
    chain = build_value_chain_table(company, annual)
    scenario = build_risk_scenario_table(company, annual, rng)
    beneish = build_beneish_mscore_table(company, annual)
    accrual_quality = build_accrual_quality_table(company, annual)
    modified_jones = build_modified_jones_kothari_table(company, annual)
    rem = build_real_earnings_management_table(company, annual)
    checks = {
        "classification": bool(cls.company_type),
        "valuation_rows": len(valuation) >= 5,
        "valuation_has_valid_method": valuation["Giá trị nội tại/cp"].notna().any(),
        "moat_score_rows": len(moat) >= 8,
        "value_chain_rows": len(chain) >= 8,
        "scenario_rows": len(scenario) == 3,
        "beneish_rows": len(beneish) >= 1 and "M-Score" in beneish.columns,
        "accrual_quality_rows": len(accrual_quality) >= 1 and "Sloan accrual ratio" in accrual_quality.columns,
        "modified_jones_rows": len(modified_jones) >= 1 and "DA Modified Jones" in modified_jones.columns,
        "rem_rows": len(rem) >= 1 and "Abnormal CFO" in rem.columns,
    }
    for name, ok in checks.items():
        print(f"{name}: {'OK' if ok else 'FAIL'}")
    print(f"Company type: {cls.company_type}")
    print(f"Moat score: {moat.attrs.get('total_score')} - {moat.attrs.get('level')}")
    print(f"Weighted value: {rng.weighted_vnd}")
    print(f"Beneish latest: {beneish.attrs.get('latest_score')} - {beneish.attrs.get('latest_risk')}")
    print(f"Accrual latest: {accrual_quality.attrs.get('latest_score')} - {accrual_quality.attrs.get('latest_risk')}")
    print(f"Jones latest: {modified_jones.attrs.get('latest_score')} - {modified_jones.attrs.get('latest_risk')}")
    print(f"REM latest: {rem.attrs.get('latest_score')} - {rem.attrs.get('latest_risk')}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
