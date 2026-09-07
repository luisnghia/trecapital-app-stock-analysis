from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from modules.deep_company_analysis.chapter9_synthesis_review import (
    accept_current_source_after_re_review,
    build_re_review_checklist,
    build_source_review_state,
)
from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    capture_source_baseline,
    empty_synthesis_workspace,
    source_drift_status,
)


REPORT_PATH = Path("reports/CH9_PHASE9K_CONSOLIDATED_REREVIEW_V72.json")


def fixture_handoff() -> dict:
    return {
        "source_question_range": "Q33–Q52",
        "manager_identity_ssot": "Chapter 7 manager master",
        "handoff_state": "Ready — Chapters 7–9 research handoff complete",
        "ready_for_analyst_synthesis": True,
        "total_questions": 20,
        "manager_count": 2,
        "evidence_rows": 2,
        "research_gaps_total": 1,
        "research_gaps_open": 0,
        "lineage_warnings": 0,
        "question_ledger": pd.DataFrame([
            {"Chapter": "Chapter 7", "Question": "Q33", "Analyst Assessment / Conclusion": "A"},
            {"Chapter": "Chapter 9", "Question": "Q48", "Analyst Assessment / Conclusion": "B"},
        ]),
        "manager_roster": pd.DataFrame([
            {"Manager ID": "M1", "Manager": "CEO", "Identity Source": "Chapter 7 manager master"},
            {"Manager ID": "M2", "Manager": "CFO", "Identity Source": "Chapter 7 manager master"},
        ]),
        "evidence_ledger": pd.DataFrame([
            {"Chapter": "Chapter 8", "Question": "Q39", "Manager ID": "M1", "Source URL / File": "a.pdf"},
            {"Chapter": "Chapter 9", "Question": "Q48", "Manager ID": "M1", "Source URL / File": "b.pdf"},
        ]),
        "research_gap_ledger": pd.DataFrame([
            {"Chapter": "Chapter 9", "Question": "Q50", "Research Gap": "Known unknown", "Status": "Closed"}
        ]),
        "chapter_readiness": pd.DataFrame([
            {"Chapter": "Chapter 7", "Handoff State": "Ready"},
            {"Chapter": "Chapter 8", "Handoff State": "Ready"},
            {"Chapter": "Chapter 9", "Handoff State": "Ready"},
        ]),
        "lineage_warning_table": pd.DataFrame(),
    }


def changed_handoff() -> dict:
    handoff = fixture_handoff()
    handoff["evidence_ledger"] = pd.concat([
        handoff["evidence_ledger"],
        pd.DataFrame([{"Chapter": "Chapter 9", "Question": "Q52", "Manager ID": "M1", "Source URL / File": "new.pdf"}]),
    ], ignore_index=True)
    handoff["evidence_rows"] = 3
    return handoff


def main() -> None:
    original = fixture_handoff()
    changed = changed_handoff()
    workspace = empty_synthesis_workspace("DGC", "DGC Corp")
    workspace["workspace_status"] = "Finalized"
    workspace["analyst_confidence"] = "High"
    workspace["final_management_synthesis"] = "Analyst-owned final management thesis."
    workspace["management_concerns"] = "Concern written by analyst."
    baseline = capture_source_baseline(workspace, original, mark_reviewed=True)

    current_state = build_source_review_state(baseline, original)
    stale_state = build_source_review_state(baseline, changed)
    checklist = build_re_review_checklist(baseline, changed)
    accepted = accept_current_source_after_re_review(
        baseline,
        changed,
        analyst_review_note="Reviewed the added Q52 source and accepted the updated research baseline.",
    )
    accepted_state = build_source_review_state(accepted, changed)

    ui = Path("modules/deep_company_analysis/chapter9_synthesis_ui.py").read_text(encoding="utf-8")
    report_ui = Path("modules/deep_company_analysis/chapter9_synthesis_report.py").read_text(encoding="utf-8")
    consolidated = Path("pages/04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")
    store = Path("modules/deep_company_analysis/chapter9_synthesis_store.py").read_text(encoding="utf-8")
    docs = Path("docs/FORMULA_EXPLANATION_CHAPTER9_PHASE9K_V72.md").read_text(encoding="utf-8")

    changed_rows = checklist[checklist["Review State"] == "Changed — review required"]
    report = {
        "phase": "Chapter 9 Phase 9K Consolidated Analyst Synthesis + Explicit Source Re-review V72",
        "acceptance": "PASS",
        "source_question_range": "Q33–Q52",
        "total_questions": 20,
        "manager_identity_ssot": "Chapter 7 manager master",
        "current_source_state": current_state["report_label"],
        "stale_source_state": stale_state["report_label"],
        "accepted_source_state": accepted_state["report_label"],
        "changed_sections": stale_state["changed_sections"],
        "checklist_rows": len(checklist),
        "changed_checklist_rows": len(changed_rows),
        "analyst_status_preserved": accepted["workspace_status"] == "Finalized",
        "analyst_confidence_preserved": accepted["analyst_confidence"] == "High",
        "analyst_synthesis_preserved": accepted["final_management_synthesis"] == "Analyst-owned final management thesis.",
        "analyst_concerns_preserved": accepted["management_concerns"] == "Concern written by analyst.",
        "explicit_re_review_note_saved": "added Q52" in accepted["last_re_review_note"],
        "explicit_re_review_timestamp_saved": bool(accepted["last_re_review_at"]),
        "ordinary_save_preserves_old_baseline_contract": "giữ nguyên baseline cũ" in ui and "source_drift_preserved" in ui,
        "explicit_confirmation_required": "disabled=not confirmed" in ui and "Tôi xác nhận đã rà soát" in ui,
        "normal_snapshot_does_not_rebaseline": "create_snapshot(ticker, workspace)" in ui,
        "consolidated_report_integrated": "render_saved_management_synthesis_report" in consolidated,
        "saved_final_synthesis_reported": "Final Analyst Management Synthesis — Chapters 7–9" in report_ui,
        "report_needs_rereview_visible": "Needs Re-review" in report_ui,
        "report_read_only": "read-only" in report_ui.casefold(),
        "wrapped_report_tables": "st.html(html)" in report_ui,
        "store_schema_version": 2 if "SCHEMA_VERSION = 2" in store else 0,
        "sql_table_shape_unchanged": "management_synthesis_current" in store and "management_synthesis_snapshots" in store,
        "automatic_workspace_status_change": stale_state["automatic_workspace_status_change"],
        "automatic_analyst_text_change": stale_state["automatic_analyst_text_change"],
        "automatic_management_score": stale_state["automatic_management_score"],
        "automatic_investment_signal": stale_state["automatic_investment_signal"],
        "mos_or_investment_research_gate_changed": False,
        "no_financial_valuation_formula": "no financial valuation formula" in docs.casefold(),
        "next_phase": "Phase 9L — cross-snapshot analyst-synthesis history/delta review and report version lineage, without management scoring or automatic investment conclusions.",
    }

    assert report["source_question_range"] == "Q33–Q52"
    assert report["total_questions"] == 20
    assert report["manager_identity_ssot"] == "Chapter 7 manager master"
    assert report["current_source_state"] == "Current"
    assert report["stale_source_state"] == "Needs Re-review"
    assert report["accepted_source_state"] == "Current"
    assert report["changed_sections"] == ["evidence_ledger"]
    assert report["checklist_rows"] == 6
    assert report["changed_checklist_rows"] == 1
    assert report["analyst_status_preserved"] is True
    assert report["analyst_confidence_preserved"] is True
    assert report["analyst_synthesis_preserved"] is True
    assert report["analyst_concerns_preserved"] is True
    assert report["explicit_re_review_note_saved"] is True
    assert report["explicit_re_review_timestamp_saved"] is True
    assert report["ordinary_save_preserves_old_baseline_contract"] is True
    assert report["explicit_confirmation_required"] is True
    assert report["normal_snapshot_does_not_rebaseline"] is True
    assert report["consolidated_report_integrated"] is True
    assert report["saved_final_synthesis_reported"] is True
    assert report["report_needs_rereview_visible"] is True
    assert report["report_read_only"] is True
    assert report["wrapped_report_tables"] is True
    assert report["store_schema_version"] == 2
    assert report["sql_table_shape_unchanged"] is True
    assert report["automatic_workspace_status_change"] is False
    assert report["automatic_analyst_text_change"] is False
    assert report["automatic_management_score"] is False
    assert report["automatic_investment_signal"] is False
    assert report["mos_or_investment_research_gate_changed"] is False
    assert report["no_financial_valuation_formula"] is True
    assert source_drift_status(accepted, changed)["changed"] is False

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
