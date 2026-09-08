from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import chapter11
from modules.deep_company_analysis import chapter11_data_bridge as bridge

REPORT_PATH = Path("reports/CH11_PHASE11C_DATA_BRIDGE_V84.json")


def main() -> None:
    canonical = {
        "source": "qa_fixture",
        "as_of_date": "2026-09-08",
        "metrics": {
            "revenue": 1000,
            "revenue_by_segment": {"core": 750, "adjacent": 250},
            "opex": 620,
            "ebit_margin": 0.18,
            "total_debt": 300,
            "finance_cost": 20,
            "customer_retention_rate": 0.9,
            "headcount": 1000,
            "staff_turnover": 0.1,
            "purchase_price": 400,
            "operating_income": 180,
            "ebitda": 240,
            "fcf": 140,
            "shareholders_equity": 650,
            "cash_and_equivalents": 160,
            "dscr": 2.8,
            "equity_issued": 35,
            "shares_outstanding": 100,
        },
    }
    analyst = chapter11.empty_payload("QA")
    analyst["question_status"]["Q58"] = "Partial"
    analyst["analyst_assessment"]["Q58"] = "Analyst-owned QA text"

    result = bridge.bridge_payload(canonical, analyst)
    rows = result["evidence"]

    checks = {
        "source_lock_preserved": result["source_lock"] == chapter11.SOURCE_LOCK,
        "question_range_q58_q59": result["question_range"] == "Q58-Q59",
        "dimension_count_15": result["dimension_count"] == 15 == len(rows),
        "q58_count_8": sum(row["question"] == "Q58" for row in rows) == 8,
        "q59_count_7": sum(row["question"] == "Q59" for row in rows) == 7,
        "analyst_payload_preserved": result["analyst_payload"] == analyst,
        "qualitative_unknown": next(row for row in rows if row["dimension_id"] == "q58_management_motivation")["status"] == "Unknown",
        "canonical_retention_found": next(row for row in rows if row["dimension_id"] == "q59_customer_retention")["status"] == "Evidence found",
        "ratio_formula_not_computed": bridge.valuation_ratio_policy()["computed_by_chapter11"] is False,
        "financing_metrics_not_computed": bridge.financing_policy()["computed_by_chapter11"] is False,
        "automatic_ma_score_false": result["automatic_ma_score"] is False,
        "automatic_success_conclusion_false": result["automatic_acquisition_success_conclusion"] is False,
        "automatic_synergy_forecast_false": result["automatic_synergy_forecast"] is False,
        "automatic_investment_signal_false": result["automatic_investment_signal"] is False,
        "mos_or_gate_unchanged": result["mos_or_research_gate_changed"] is False,
    }
    passed = all(checks.values())
    report = {
        "phase": bridge.PHASE,
        "version": bridge.VERSION,
        "contract": bridge.BRIDGE_CONTRACT,
        "passed": passed,
        "checks": checks,
        "available_dimension_count": sum(row["status"] == "Evidence found" for row in rows),
        "unknown_dimension_count": sum(row["status"] == "Unknown" for row in rows),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not passed:
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("PASS: Chapter 11 V84 canonical read-only data bridge acceptance.")


if __name__ == "__main__":
    main()
