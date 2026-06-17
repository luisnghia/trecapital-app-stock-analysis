from __future__ import annotations

"""Self-check for Tổng quan doanh nghiệp dashboard logic.

Usage:
    python tools/run_self_check.py /path/to/Financial-v1.3.0.xlsm --ticker DCM
"""

from pathlib import Path
import argparse
import py_compile
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*DrawingML support.*")
warnings.filterwarnings("ignore", message=".*Sparkline Group extension.*")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.excel_financial_provider import ExcelFinancialProvider
from module1_engine import (
    load_overview_from_csv,
    load_timeseries_from_csv,
    ensure_derived_metrics,
    append_ttm_row,
    build_fcf_analysis_table,
    build_financial_ratio_table,
    build_financial_ratio_scorecard,
    build_financial_ratio_alerts,
    build_mos_valuation_table,
    build_combined_assessment_table,
)
from module1_charts import make_line_fig, make_fcf_generation_fig, make_fcf_usage_fig, make_fcf_conversion_fig


def check(workbook: Path, ticker: str) -> None:
    tmp = ROOT / "sample_data" / "_self_check"
    tmp.mkdir(parents=True, exist_ok=True)
    result = ExcelFinancialProvider(workbook).export_csv(ticker, tmp)

    annual_raw = ensure_derived_metrics(load_timeseries_from_csv(tmp / "financial_timeseries_year.csv", ticker, "Y", 10))
    quarterly = ensure_derived_metrics(load_timeseries_from_csv(tmp / "financial_timeseries_quarter.csv", ticker, "Q", 20))
    annual = append_ttm_row(annual_raw, quarterly)
    company = load_overview_from_csv(tmp / "company_overview_sample.csv", ticker)

    annual_periods = [str(x) for x in annual["period"].tolist()]
    quarterly_periods = [str(x) for x in quarterly["period"].tolist()]

    assert len(result.overview) == 1, "Overview must have exactly one ticker row"
    assert len(annual_periods) == len(set(annual_periods)), "Annual periods are duplicated"
    assert len(quarterly_periods) == len(set(quarterly_periods)), "Quarterly periods are duplicated"
    assert not any(p.endswith(".0") for p in annual_periods + quarterly_periods), "Period labels must not end with .0"
    annual_without_ttm = [p for p in annual_periods if p.upper() not in {"TTM", "T12M"}]
    assert annual_without_ttm == sorted(annual_without_ttm, key=lambda x: int(x)), "Annual periods must sort ascending"
    if len(quarterly) >= 4:
        assert any(p.upper() in {"TTM", "T12M"} for p in annual_periods), "Annual data should include a TTM row when quarterly data is available"

    fig = make_line_fig(annual, ["revenue_bil", "net_profit_bil"], "Self-check", "tỷ đồng")
    assert len(fig.data) >= 1, "Plotly chart should have at least one data trace"
    assert fig.layout.hovermode == "x unified", "Plotly chart should show unified hover tooltip"

    fcf_generation = make_fcf_generation_fig(annual)
    fcf_usage = make_fcf_usage_fig(annual)
    fcf_conversion = make_fcf_conversion_fig(annual)
    fcf_table = build_fcf_analysis_table(annual)
    ratio_table = build_financial_ratio_table(annual)
    ratio_score = build_financial_ratio_scorecard(annual)
    ratio_alerts = build_financial_ratio_alerts(annual)
    valuation = build_mos_valuation_table(company, annual)
    combined_alerts = build_combined_assessment_table(company, annual, quarterly, valuation)
    assert len(fcf_generation.data) >= 1, "FCF generation chart should have at least one trace"
    assert len(fcf_usage.data) >= 1, "FCF usage chart should have at least one trace"
    assert len(fcf_conversion.data) >= 1, "FCF conversion chart should have at least one trace"
    assert not fcf_table.empty and "Nhóm / chỉ tiêu" in fcf_table.columns, "FCF analysis table should be available"
    assert not ratio_table.empty and "Nhóm / chỉ tiêu" in ratio_table.columns, "Financial ratio table should be available"
    assert not ratio_score.empty and "TỔNG ĐIỂM CHỈ SỐ TÀI CHÍNH" in " ".join(ratio_score["Nhóm tiêu chí"].astype(str).tolist()), "Financial ratio scorecard should be available"
    assert not ratio_alerts.empty, "Financial ratio alerts should be available"
    assert not valuation.empty, "MOS valuation table should be available"
    assert not combined_alerts.empty and {"Nguồn đánh giá", "Mức độ", "Nội dung", "Diễn giải"}.issubset(combined_alerts.columns), "Combined assessment table should be available"

    for file in ["module1_engine.py", "module1_charts.py", "module1_dashboard.py", "adapters/vn_public_crawler.py", "adapters/excel_financial_provider.py"]:
        py_compile.compile(str(ROOT / file), doraise=True)

    print("SELF_CHECK_OK")
    print(f"Overview rows: {len(result.overview)}")
    print(f"Annual rows: {len(annual)} | periods: {annual_periods}")
    print(f"Quarter rows: {len(quarterly)} | periods: {quarterly_periods}")
    print("Chart hover: x unified")
    print("FCF_TAB_CHECK_OK")
    print("FINANCIAL_RATIO_TAB_CHECK_OK")
    print("TTM_ROW_OK")
    print("MOS_VALUATION_CHECK_OK")
    print("COMBINED_ALERTS_CHECK_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--ticker", default="DCM")
    args = parser.parse_args()
    check(args.workbook, args.ticker.upper().strip())
