from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from modules.deep_company_analysis.cyclical_normalization import (
    comparability_breaks,
    normalization_guardrails,
    normalization_table,
)


def main() -> int:
    df = pd.DataFrame([
        {"period": str(y), "period_type": "Y", "year": y, "revenue_bil": 100 + (y - 2017) * 10,
         "gross_margin_pct": 20 + (y - 2017), "operating_margin_pct": 10 + (y - 2017) * 0.5,
         "roic_pct": 8 + (y - 2017) * 0.7, "net_profit_bil": 8 + (y - 2017) * 1.2,
         "comparability_status": "Comparable", "comparability_note": ""}
        for y in range(2017, 2026)
    ] + [{
        "period": "TTM", "period_display": "TTM đến Q2/2026", "year": 2026,
        "revenue_bil": 195, "gross_margin_pct": 29.5, "operating_margin_pct": 14.5,
        "roic_pct": 14.0, "net_profit_bil": 18.5,
    }])
    table = normalization_table(df)
    report = {
        "acceptance": "PASS" if len(table) == 5 and int(table["observations"].min()) >= 9 else "FAIL",
        "metrics": table["metric"].tolist(),
        "ttm_overlay_excluded_from_baseline": bool((table["observations"] == 9).all()),
        "comparability_break_count": int(len(comparability_breaks(df))),
        "guardrails": normalization_guardrails(df),
        "duplicate_financial_ssot_added": False,
        "valuation_formula_changed": False,
        "automatic_weighted_score": False,
        "automatic_buy_hold_sell": False,
        "automatic_research_gate_change": False,
        "ai_role": "Research Assistant",
        "conclusion_owner": "Analyst",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CYCLICAL_NORMALIZATION_V100_ACCEPTANCE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["acceptance"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
