from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from modules.deep_company_analysis import chapter9_synthesis_store as store
from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    SYNTHESIS_WORKSPACE_BOUNDARY,
    build_source_signature,
    capture_source_baseline,
    empty_synthesis_workspace,
    source_drift_status,
    synthesis_workspace_summary,
)


def _handoff() -> dict:
    return {
        "source_question_range": "Q33–Q52",
        "manager_identity_ssot": "Chapter 7 manager master",
        "handoff_state": "Ready — Chapters 7–9 research handoff complete",
        "ready_for_analyst_synthesis": True,
        "total_questions": 20,
        "manager_count": 1,
        "evidence_rows": 2,
        "research_gaps_total": 1,
        "research_gaps_open": 0,
        "lineage_warnings": 0,
        "question_ledger": pd.DataFrame([
            {"Chapter": "Chapter 7", "Question": "Q33", "Analyst Assessment / Conclusion": "A"},
            {"Chapter": "Chapter 9", "Question": "Q52", "Analyst Assessment / Conclusion": "B"},
        ]),
        "manager_roster": pd.DataFrame([
            {"Manager ID": "M1", "Manager": "CEO One", "Current Role": "CEO", "Identity Source": "Chapter 7 manager master"}
        ]),
        "evidence_ledger": pd.DataFrame([
            {"Chapter": "Chapter 7", "Question": "Q33", "Manager ID": "M1", "Source URL / File": "a.pdf"},
            {"Chapter": "Chapter 9", "Question": "Q52", "Manager ID": "M1", "Source URL / File": "b.pdf"},
        ]),
        "research_gap_ledger": pd.DataFrame([
            {"Chapter": "Chapter 9", "Question": "Q50", "Research Gap": "known unknown", "Status": "Closed"}
        ]),
        "chapter_readiness": pd.DataFrame([
            {"Chapter": "Chapter 7", "Handoff State": "Ready"},
            {"Chapter": "Chapter 8", "Handoff State": "Ready"},
            {"Chapter": "Chapter 9", "Handoff State": "Ready"},
        ]),
        "lineage_warning_table": pd.DataFrame(),
    }


def test_source_signature_is_stable_to_dataframe_row_order() -> None:
    first = _handoff()
    second = deepcopy(first)
    second["evidence_ledger"] = second["evidence_ledger"].iloc[::-1].reset_index(drop=True)
    assert build_source_signature(first)["fingerprint"] == build_source_signature(second)["fingerprint"]


def test_capture_source_baseline_preserves_analyst_owned_text() -> None:
    workspace = empty_synthesis_workspace("DGC", "DGC Corp")
    workspace["workspace_status"] = "Finalized"
    workspace["analyst_confidence"] = "High"
    workspace["final_management_synthesis"] = "Analyst-written final synthesis."
    workspace["management_concerns"] = "Concern remains."
    captured = capture_source_baseline(workspace, _handoff(), mark_reviewed=True)
    assert captured["workspace_status"] == "Finalized"
    assert captured["analyst_confidence"] == "High"
    assert captured["final_management_synthesis"] == "Analyst-written final synthesis."
    assert captured["management_concerns"] == "Concern remains."
    assert captured["source_fingerprint"]
    assert captured["analyst_reviewed_at"]


def test_source_drift_flags_question_change_without_mutating_finalized_status() -> None:
    workspace = empty_synthesis_workspace("DGC")
    workspace["workspace_status"] = "Finalized"
    workspace["final_management_synthesis"] = "Keep me unchanged."
    saved = capture_source_baseline(workspace, _handoff())
    changed = _handoff()
    changed["question_ledger"] = changed["question_ledger"].copy()
    changed["question_ledger"].loc[0, "Analyst Assessment / Conclusion"] = "Changed source conclusion"
    before = deepcopy(saved)
    drift = source_drift_status(saved, changed)
    assert drift["changed"] is True
    assert "question_ledger" in drift["changed_sections"]
    assert saved == before
    assert saved["workspace_status"] == "Finalized"
    assert saved["final_management_synthesis"] == "Keep me unchanged."


def test_source_drift_detects_evidence_and_manager_changes() -> None:
    saved = capture_source_baseline(empty_synthesis_workspace("DGC"), _handoff())
    changed = _handoff()
    changed["evidence_ledger"] = pd.concat([
        changed["evidence_ledger"],
        pd.DataFrame([{"Chapter": "Chapter 8", "Question": "Q41", "Manager ID": "M1", "Source URL / File": "c.pdf"}]),
    ], ignore_index=True)
    changed["manager_roster"] = pd.concat([
        changed["manager_roster"],
        pd.DataFrame([{"Manager ID": "M2", "Manager": "CFO Two", "Current Role": "CFO", "Identity Source": "Chapter 7 manager master"}]),
    ], ignore_index=True)
    drift = source_drift_status(saved, changed)
    assert drift["changed"] is True
    assert {"evidence_ledger", "manager_roster"}.issubset(set(drift["changed_sections"]))


def test_summary_is_completeness_only_not_management_score() -> None:
    workspace = empty_synthesis_workspace("DGC")
    workspace["management_strengths"] = "Strength"
    workspace["final_management_synthesis"] = "Conclusion"
    summary = synthesis_workspace_summary(workspace, _handoff())
    assert summary["completed_text_sections"] == 2
    assert summary["automatic_management_score"] is False
    assert summary["automatic_character_classification"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_investment_research_gate_changed"] is False
    assert "Management Quality Score" in SYNTHESIS_WORKSPACE_BOUNDARY


def test_store_current_and_immutable_snapshot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "synthesis.db")
    workspace = empty_synthesis_workspace("DGC", "DGC Corp")
    workspace["final_management_synthesis"] = "Version one"
    workspace = capture_source_baseline(workspace, _handoff())
    store.save_workspace("DGC", workspace, "DGC Corp")
    snapshot_id = store.create_snapshot("DGC", workspace)

    updated = deepcopy(workspace)
    updated["final_management_synthesis"] = "Version two"
    store.save_workspace("DGC", updated, "DGC Corp")

    current = store.load_workspace("DGC")
    snapshot = store.load_snapshot(snapshot_id)
    assert current["final_management_synthesis"] == "Version two"
    assert snapshot is not None
    assert snapshot["final_management_synthesis"] == "Version one"
    assert store.list_snapshots("DGC")[0]["id"] == snapshot_id


def test_ui_is_wired_into_existing_chapter9_page_without_auto_write() -> None:
    page = Path("modules/deep_company_analysis/chapter9_page_support.py").read_text(encoding="utf-8")
    ui = Path("modules/deep_company_analysis/chapter9_synthesis_ui.py").read_text(encoding="utf-8")
    assert "render_management_synthesis_workspace" in page
    assert "Phase 9A–9J" in page
    assert "Final Analyst Management Synthesis" in ui
    assert "source_drift_status" in ui
    assert "capture_source_baseline" in ui
    assert "AI auto-write" in ui
    assert "score" not in ui.casefold().replace("no auto-score", "") or "không" in ui.casefold()


def test_phase9j_engine_has_no_streamlit_or_investment_formula_mutation() -> None:
    engine = Path("modules/deep_company_analysis/chapter9_synthesis_workspace.py").read_text(encoding="utf-8").casefold()
    assert "import streamlit" not in engine
    assert "buy/hold/sell" in engine
    assert "management quality score" in engine
    assert "investment research gate" in engine
    assert "mos change" in engine
