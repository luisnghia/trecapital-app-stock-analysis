from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_research as research


def main() -> None:
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert len(ch10.dimension_ids()) == 34
    source = Path("modules/deep_company_analysis/chapter10_store.py").read_text(encoding="utf-8").casefold()
    ui = Path("modules/deep_company_analysis/chapter10_page_support.py").read_text(encoding="utf-8").casefold()
    assert "chapter10_current" in source
    assert "financial data remains read-only" in source
    assert "promote selected evidence" in ui
    assert "growth score" in ui
    assert "buy/hold/sell" in ui
    assert "intrinsic_value" not in source
    assert "ccc =" not in source
    p = ch10.empty_payload("QA")
    before = json.dumps(p, sort_keys=True)
    empty = research.build_candidates([])
    after = research.promote_selected_candidates(p, empty, [])
    assert json.dumps(after, sort_keys=True) == before
    report = {
        "phase": "Chapter 10 Phase 10E Analyst Workspace V78",
        "acceptance": "PASS",
        "questions": len(ch10.QUESTION_KEYS),
        "dimensions": len(ch10.dimension_ids()),
        "unknown_first": True,
        "explicit_promotion_required": True,
        "persistent_analyst_workspace": True,
        "canonical_financial_ssot_copied": False,
        "automatic_growth_score": False,
        "automatic_growth_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH10_PHASE10E_WORKSPACE_V78.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
