from __future__ import annotations

import json
from pathlib import Path

from modules.deep_company_analysis import chapter10
from modules.deep_company_analysis import chapter10_data_bridge as bridge


def main() -> None:
    sample = {
        "source": "canonical_financial_ssot",
        "as_of_date": "2026-06-30",
        "metrics": {
            "revenue": [100, 115, 130],
            "gross_margin": [0.30, 0.31, 0.32],
            "operating_margin": [0.12, 0.13, 0.14],
            "operating_units": [10, 11, 12],
            "dio": 50,
            "dso": 30,
            "dpo": 20,
        },
    }
    analyst = chapter10.empty_payload("TEST", "Test Company")
    analyst_before = json.loads(json.dumps(analyst))
    result = bridge.bridge_payload(sample, analyst)

    assert chapter10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert len(chapter10.dimension_catalog()) == 34
    assert result["dimension_count"] == 34
    assert result["contract"] == "canonical-read-only"
    assert result["ccc"]["status"] == "Unknown"
    assert result["ccc"]["ccc"] is None
    assert result["ccc"]["computed_by_chapter10"] is False
    assert all(result["ccc"]["components_available"].values())
    assert analyst == analyst_before
    assert result["analyst_payload"] == analyst_before
    assert result["automatic_growth_score"] is False
    assert result["automatic_growth_forecast"] is False
    assert result["automatic_investment_signal"] is False
    assert result["mos_or_research_gate_changed"] is False
    assert all(row["direction"] == "Unknown" for row in result["evidence"])

    report = {
        "phase": "Chapter 10 Phase 10C Canonical Data Bridge V76",
        "acceptance": "PASS",
        "chapter": 10,
        "question_range": chapter10.SOURCE_QUESTION_RANGE,
        "dimension_count": result["dimension_count"],
        "bridge_contract": result["contract"],
        "canonical_read_only": True,
        "ccc_recomputed_by_chapter10": result["ccc"]["computed_by_chapter10"],
        "ccc_missing_remains_unknown": result["ccc"]["status"] == "Unknown",
        "analyst_payload_mutated": analyst != analyst_before,
        "automatic_growth_score": result["automatic_growth_score"],
        "automatic_growth_forecast": result["automatic_growth_forecast"],
        "automatic_investment_signal": result["automatic_investment_signal"],
        "mos_or_research_gate_changed": result["mos_or_research_gate_changed"],
        "web_research_added": False,
        "database_added": False,
        "ui_added": False,
        "next_phase": "Phase 10D — source research / Research Assistant bridge for qualitative and missing evidence.",
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH10_PHASE10C_DATA_BRIDGE_V76.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
