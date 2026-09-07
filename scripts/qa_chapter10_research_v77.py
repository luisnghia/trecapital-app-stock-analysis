from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_research as research


def main() -> None:
    summary = research.phase_summary()
    plan = research.research_plan("TEST", "Test Company", "example.com")
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert len(ch10.dimension_ids()) == 34
    assert len(plan) == 34
    assert set(plan["Dimension ID"]) == set(ch10.dimension_ids())
    assert summary["analyst_promotion_required"] is True
    assert summary["automatic_growth_score"] is False
    assert summary["automatic_growth_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_research_gate_changed"] is False
    assert summary["duplicate_financial_ssot_added"] is False
    report = dict(summary)
    report.update({
        "acceptance": "PASS",
        "source_lock": ch10.SOURCE_LOCK,
        "source_locked_questions": len(ch10.QUESTION_KEYS),
        "source_locked_dimensions": len(ch10.dimension_ids()),
        "research_plan_dimension_coverage": len(set(plan["Dimension ID"])),
        "candidate_is_fact": False,
        "analyst_workspace_auto_mutation": False,
        "next_phase": "Phase 10E — analyst workspace/store/UI and research promotion workflow.",
    })
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH10_PHASE10D_RESEARCH_V77.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
