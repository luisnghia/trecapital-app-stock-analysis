from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    build_source_signature,
    capture_source_baseline,
    empty_synthesis_workspace,
    source_drift_status,
    synthesis_workspace_summary,
)


REPORT_PATH = Path("reports/CH9_PHASE9J_ANALYST_SYNTHESIS_V71.json")


def fixture_handoff() -> dict:
    return {
        "source_question_range": "Q33–Q52",
        "manager_identity_ssot": "Chapter 7 manager master",
        "handoff_state": "Ready — Chapters 7–9 research handoff complete",
        "ready_for_analyst_synthesis": True,
        "total_questions": 20,
        "manager_count": 2,
        "evidence_rows": 3,
        "research_gaps_total": 1,
        "research_gaps_open": 0,
        "lineage_warnings": 0,
        "question_ledger": pd.DataFrame([
            {"Chapter": "Chapter 7", "Question": "Q33", "Analyst Assessment / Conclusion": "Background conclusion"},
            {"Chapter": "Chapter 8", "Question": "Q39", "Analyst Assessment / Conclusion": "Operating conclusion"},
            {"Chapter": "Chapter 9", "Question": "Q48", "Analyst Assessment / Conclusion": "Trait conclusion"},
        ]),
        "manager_roster": pd.DataFrame([
            {"Manager ID": "M1", "Manager": "CEO", "Identity Source": "Chapter 7 manager master"},
            {"Manager ID": "M2", "Manager": "CFO", "Identity Source": "Chapter 7 manager master"},
        ]),
        "evidence_ledger": pd.DataFrame([
            {"Chapter": "Chapter 7", "Question": "Q33", "Manager ID": "M1", "Source URL / File": "a.pdf"},
            {"Chapter": "Chapter 8", "Question": "Q39", "Manager ID": "M1", "Source URL / File": "b.pdf"},
            {"Chapter": "Chapter 9", "Question": "Q48", "Manager ID": "M1", "Source URL / File": "c.pdf"},
        ]),
        "research_gap_ledger": pd.DataFrame([
            {"Chapter": "Chapter 9", "Question": "Q50", "Research Gap": "closed known unknown", "Status": "Closed"}
        ]),
        "chapter_readiness": pd.DataFrame([
            {"Chapter": "Chapter 7", "Handoff State": "Ready"},
            {"Chapter": "Chapter 8", "Handoff State": "Ready"},
            {"Chapter": "Chapter 9", "Handoff State": "Ready"},
        ]),
        "lineage_warning_table": pd.DataFrame(),
    }


def main() -> None:
    handoff = fixture_handoff()
    signature = build_source_signature(handoff)
    workspace = empty_synthesis_workspace("DGC", "DGC Corp")
    workspace["workspace_status"] = "Finalized"
    workspace["analyst_confidence"] = "High"
    workspace["final_management_synthesis"] = "Analyst-owned synthesis."
    captured = capture_source_baseline(workspace, handoff, mark_reviewed=True)

    unchanged = source_drift_status(captured, handoff)
    changed_handoff = fixture_handoff()
    changed_handoff["evidence_ledger"] = pd.concat([
        changed_handoff["evidence_ledger"],
        pd.DataFrame([{"Chapter": "Chapter 9", "Question": "Q52", "Manager ID": "M1", "Source URL / File": "new.pdf"}]),
    ], ignore_index=True)
    changed_handoff["evidence_rows"] = 4
    changed = source_drift_status(captured, changed_handoff)
    summary = synthesis_workspace_summary(captured, changed_handoff)

    page = Path("modules/deep_company_analysis/chapter9_page_support.py").read_text(encoding="utf-8")
    ui = Path("modules/deep_company_analysis/chapter9_synthesis_ui.py").read_text(encoding="utf-8")
    store = Path("modules/deep_company_analysis/chapter9_synthesis_store.py").read_text(encoding="utf-8")
    docs = Path("docs/FORMULA_EXPLANATION_CHAPTER9_PHASE9J_V71.md").read_text(encoding="utf-8")

    report = {
        "phase": "Chapter 9 Phase 9J Analyst-Owned Management Synthesis Workspace V71",
        "acceptance": "PASS",
        "source_question_range": signature["source_question_range"],
        "total_questions": signature["counts"]["total_questions"],
        "manager_identity_ssot": signature["manager_identity_ssot"],
        "source_sections_fingerprinted": sorted(signature["section_fingerprints"].keys()),
        "source_fingerprint_present": bool(signature["fingerprint"]),
        "unchanged_source_detected": unchanged["changed"] is False and unchanged["status"].startswith("Unchanged"),
        "changed_source_detected": changed["changed"] is True and "evidence_ledger" in changed["changed_sections"],
        "finalized_status_preserved_after_drift": captured["workspace_status"] == "Finalized",
        "analyst_text_preserved_after_baseline_capture": captured["final_management_synthesis"] == "Analyst-owned synthesis.",
        "separate_synthesis_database": "deep_company_analysis_management_synthesis.db" in store,
        "immutable_snapshot_table": "management_synthesis_snapshots" in store,
        "unified_chapter9_ui_integrated": "render_management_synthesis_workspace" in page,
        "source_drift_ui_visible": "source_drift_status" in ui and "changed_sections" in ui,
        "saved_source_records_only": "saved Chapter 7–9 records only" in ui,
        "analyst_owned_final_synthesis_field": "Final Analyst Management Synthesis" in ui,
        "automatic_workspace_status_change": changed["automatic_workspace_status_change"],
        "automatic_analyst_text_change": changed["automatic_analyst_text_change"],
        "automatic_management_score": summary["automatic_management_score"],
        "automatic_character_classification": summary["automatic_character_classification"],
        "automatic_investment_signal": summary["automatic_investment_signal"],
        "mos_or_investment_research_gate_changed": summary["mos_or_investment_research_gate_changed"],
        "no_financial_valuation_formula": "no financial valuation formula" in docs.casefold(),
        "next_phase": "Phase 9K — consolidated-report integration of saved analyst synthesis plus explicit re-review workflow when source drift is detected, without management scoring or automatic investment conclusions.",
    }

    assert report["source_question_range"] == "Q33–Q52"
    assert report["total_questions"] == 20
    assert report["manager_identity_ssot"] == "Chapter 7 manager master"
    assert len(report["source_sections_fingerprinted"]) == 6
    assert report["source_fingerprint_present"] is True
    assert report["unchanged_source_detected"] is True
    assert report["changed_source_detected"] is True
    assert report["finalized_status_preserved_after_drift"] is True
    assert report["analyst_text_preserved_after_baseline_capture"] is True
    assert report["separate_synthesis_database"] is True
    assert report["immutable_snapshot_table"] is True
    assert report["unified_chapter9_ui_integrated"] is True
    assert report["source_drift_ui_visible"] is True
    assert report["saved_source_records_only"] is True
    assert report["analyst_owned_final_synthesis_field"] is True
    assert report["automatic_workspace_status_change"] is False
    assert report["automatic_analyst_text_change"] is False
    assert report["automatic_management_score"] is False
    assert report["automatic_character_classification"] is False
    assert report["automatic_investment_signal"] is False
    assert report["mos_or_investment_research_gate_changed"] is False
    assert report["no_financial_valuation_formula"] is True

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
