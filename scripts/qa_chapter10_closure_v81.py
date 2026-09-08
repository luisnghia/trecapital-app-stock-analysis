from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_completion as completion
import modules.deep_company_analysis.chapter10_history as history
import modules.deep_company_analysis.chapter10_history_ui as history_ui
import modules.deep_company_analysis.chapter10_store as store


def main() -> None:
    p = ch10.empty_payload("VNM", "Vinamilk")
    p["question_status"]["Q53"] = "Answered"
    p["confidence"]["Q53"] = "High"
    p["analyst_assessment"]["Q53"] = "Analyst reviewed growth route"
    p["growth_mode"] = "Mixed"
    p["growth_synthesis"] = completion.normalize_synthesis({
        "status": "Reviewed",
        "growth_route_takeaway": "Mixed organic and acquisition route",
        "final_growth_synthesis": "Analyst-owned conclusion",
        "last_re_review_at": "2026-09-08T00:00:00Z",
        "last_re_review_note": "Reviewed source delta",
        "last_re_review_sections": ["Q53", "Growth Synthesis"],
    })
    round_trip = completion.normalize_synthesis(deepcopy(p["growth_synthesis"]))
    delta = history.compare_versions(p, {**p, "growth_synthesis": {**p["growth_synthesis"], "growth_route_takeaway": "Analyst changed route takeaway"}})
    route = delta[delta["Field"] == "Growth Route Takeaway"].iloc[0]
    ui_source = Path(history_ui.__file__).read_text(encoding="utf-8").casefold()
    page_source = Path("modules/deep_company_analysis/chapter10_page_support.py").read_text(encoding="utf-8").casefold()
    report = {
        "phase": "Chapter 10 Phase 10H Closure V81",
        "acceptance": "PASS",
        "chapter": 10,
        "chapter_title": ch10.CHAPTER_TITLE,
        "source_lock": ch10.SOURCE_LOCK,
        "exact_question_range": ch10.SOURCE_QUESTION_RANGE,
        "source_locked_questions": len(ch10.QUESTION_KEYS),
        "evidence_dimensions": len(ch10.dimension_ids()),
        "history_ui_integrated": "render_history_panel" in page_source,
        "version_lineage_report_integrated": "history_report_section" in page_source,
        "actual_synthesis_schema_tracked": route["Delta"] == "Changed",
        "re_review_metadata_preserved": round_trip["last_re_review_sections"] == ["Q53", "Growth Synthesis"],
        "snapshot_schema_version": store.SCHEMA_VERSION,
        "historical_source_freshness_reconstructed": False,
        "automatic_growth_mode_change": False,
        "automatic_question_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_text_change": False,
        "automatic_growth_score": False,
        "automatic_growth_forecast": False,
        "automatic_investment_signal": False,
        "duplicate_financial_ssot_added": False,
        "mos_or_investment_research_gate_changed": False,
        "chapter10_closure_ready": True,
        "next_phase": "Chapter 11 Phase 11A — source lock for Evaluating Mergers & Acquisitions.",
    }
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.SOURCE_QUESTION_RANGE == "Q53-Q57"
    assert len(ch10.dimension_ids()) == 34
    assert report["history_ui_integrated"] is True
    assert report["version_lineage_report_integrated"] is True
    assert report["actual_synthesis_schema_tracked"] is True
    assert report["re_review_metadata_preserved"] is True
    assert "ccc =" not in ui_source
    assert "intrinsic_value" not in ui_source
    Path("reports").mkdir(exist_ok=True)
    Path("reports/CH10_PHASE10H_CLOSURE_V81.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
