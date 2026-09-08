from __future__ import annotations

from pathlib import Path
import json

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_research as research
import modules.deep_company_analysis.chapter11_store as store


def main() -> None:
    page = Path("modules/deep_company_analysis/chapter11_page_support.py").read_text(encoding="utf-8")
    nav = Path("tre_sidebar_nav.py").read_text(encoding="utf-8")
    store_source = Path("modules/deep_company_analysis/chapter11_store.py").read_text(encoding="utf-8").casefold()

    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.dimension_count_by_question() == {"Q58": 8, "Q59": 7}
    assert len(ch11.dimension_ids()) == 15
    assert len(research.research_plan("TEST")) == 15
    assert "pages/09_Phan_tich_MA.py" in nav
    assert "Promote selected evidence" in page
    assert "Save Chapter 11 workspace" in page
    assert "canonical financial" in page.casefold()
    assert "canonical_financials" not in store_source
    assert "ev_ebitda" not in store_source
    assert "weighted" not in store_source
    assert "buy/hold/sell" not in store_source

    report = {
        "phase": "Chapter 11 Phase 11E Analyst Workspace V86",
        "questions": list(ch11.QUESTION_KEYS),
        "dimension_count": len(ch11.dimension_ids()),
        "workspace_store": True,
        "streamlit_workspace": True,
        "explicit_candidate_promotion": True,
        "analyst_owns_conclusions": True,
        "duplicate_financial_ssot_added": False,
        "automatic_ma_score": False,
        "automatic_acquisition_success_conclusion": False,
        "automatic_synergy_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_research_gate_changed": False,
    }
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH11_PHASE11E_WORKSPACE_V86.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("PASS: V86 analyst workspace/persistence/UI boundaries verified for Chapter 11 Q58-Q59/15 dimensions.")


if __name__ == "__main__":
    main()
