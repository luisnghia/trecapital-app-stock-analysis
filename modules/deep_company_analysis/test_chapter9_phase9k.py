from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

from modules.deep_company_analysis.chapter9_synthesis_review import (
    SOURCE_REVIEW_CURRENT,
    SOURCE_REVIEW_NEEDS_REREVIEW,
    SOURCE_REVIEW_NO_BASELINE,
    accept_current_source_after_re_review,
    build_re_review_checklist,
    build_source_review_state,
)
from modules.deep_company_analysis.chapter9_synthesis_workspace import (
    build_source_signature,
    capture_source_baseline,
    empty_synthesis_workspace,
    normalize_synthesis_workspace,
    source_drift_status,
)


def _handoff() -> dict:
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


def _changed_handoff() -> dict:
    handoff = _handoff()
    handoff["evidence_ledger"] = pd.concat([
        handoff["evidence_ledger"],
        pd.DataFrame([{"Chapter": "Chapter 9", "Question": "Q52", "Manager ID": "M1", "Source URL / File": "new.pdf"}]),
    ], ignore_index=True)
    handoff["evidence_rows"] = 3
    return handoff


def test_phase9k_source_review_states_are_process_states_only() -> None:
    workspace = empty_synthesis_workspace("DGC")
    no_baseline = build_source_review_state(workspace, _handoff())
    assert no_baseline["state"] == SOURCE_REVIEW_NO_BASELINE
    assert no_baseline["report_label"] == "No baseline"

    current_workspace = capture_source_baseline(workspace, _handoff(), mark_reviewed=True)
    current = build_source_review_state(current_workspace, _handoff())
    assert current["state"] == SOURCE_REVIEW_CURRENT
    assert current["report_label"] == "Current"

    changed = build_source_review_state(current_workspace, _changed_handoff())
    assert changed["state"] == SOURCE_REVIEW_NEEDS_REREVIEW
    assert changed["report_label"] == "Needs Re-review"
    assert changed["changed_sections"] == ["evidence_ledger"]
    assert changed["automatic_workspace_status_change"] is False
    assert changed["automatic_analyst_text_change"] is False
    assert changed["automatic_management_score"] is False
    assert changed["automatic_investment_signal"] is False


def test_phase9k_checklist_pinpoints_changed_source_section() -> None:
    workspace = capture_source_baseline(empty_synthesis_workspace("DGC"), _handoff(), mark_reviewed=True)
    checklist = build_re_review_checklist(workspace, _changed_handoff())
    assert len(checklist) == 6
    changed_rows = checklist[checklist["Review State"] == "Changed — review required"]
    assert len(changed_rows) == 1
    assert changed_rows.iloc[0]["Source Section"] == "Cross-Chapter Evidence Ledger"
    assert "review" in changed_rows.iloc[0]["Required Analyst Action"].lower()


def test_phase9k_explicit_accept_preserves_analyst_owned_fields_and_rebaselines() -> None:
    workspace = empty_synthesis_workspace("DGC")
    workspace["workspace_status"] = "Finalized"
    workspace["analyst_confidence"] = "High"
    workspace["final_management_synthesis"] = "Analyst final conclusion"
    workspace["management_concerns"] = "Analyst concern"
    workspace = capture_source_baseline(workspace, _handoff(), mark_reviewed=True)

    before = deepcopy(workspace)
    assert source_drift_status(workspace, _changed_handoff())["changed"] is True
    accepted = accept_current_source_after_re_review(
        workspace,
        _changed_handoff(),
        analyst_review_note="Reviewed new Q52 evidence and retained conclusion.",
    )

    assert accepted["workspace_status"] == "Finalized"
    assert accepted["analyst_confidence"] == "High"
    assert accepted["final_management_synthesis"] == "Analyst final conclusion"
    assert accepted["management_concerns"] == "Analyst concern"
    assert accepted["last_re_review_sections"] == ["evidence_ledger"]
    assert "Reviewed new Q52 evidence" in accepted["last_re_review_note"]
    assert accepted["last_re_review_at"]
    assert source_drift_status(accepted, _changed_handoff())["changed"] is False
    assert workspace == before


def test_phase9k_normalizer_migrates_v71_payload_additively() -> None:
    old = {
        "schema_version": 1,
        "ticker": "DGC",
        "workspace_status": "Reviewed",
        "analyst_confidence": "Medium",
        "final_management_synthesis": "Keep me",
    }
    migrated = normalize_synthesis_workspace(old)
    assert migrated["schema_version"] == 2
    assert migrated["final_management_synthesis"] == "Keep me"
    assert migrated["last_re_review_at"] == ""
    assert migrated["last_re_review_note"] == ""
    assert migrated["last_re_review_sections"] == []


def test_phase9k_source_signature_remains_q33_q52_and_chapter7_ssot() -> None:
    signature = build_source_signature(_handoff())
    assert signature["source_question_range"] == "Q33–Q52"
    assert signature["manager_identity_ssot"] == "Chapter 7 manager master"
    assert signature["counts"]["total_questions"] == 20


def test_phase9k_ui_requires_explicit_re_review_and_normal_save_preserves_drift() -> None:
    ui = Path("modules/deep_company_analysis/chapter9_synthesis_ui.py").read_text(encoding="utf-8")
    assert "Explicit Re-review Acceptance" in ui
    assert "Tôi xác nhận đã rà soát các source section thay đổi" in ui
    assert "Xác nhận Re-review & chấp nhận baseline mới" in ui
    assert "giữ nguyên baseline cũ" in ui
    assert "accept_current_source_after_re_review" in ui
    assert "disabled=not confirmed" in ui
    assert "create_snapshot(ticker, workspace)" in ui


def test_phase9k_consolidated_report_shows_saved_synthesis_and_freshness() -> None:
    page = Path("pages/04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")
    report = Path("modules/deep_company_analysis/chapter9_synthesis_report.py").read_text(encoding="utf-8")
    assert "render_saved_management_synthesis_report" in page
    assert "Final Analyst Management Synthesis — Chapters 7–9" in report
    assert "Needs Re-review" in report
    assert "Current" in report
    assert "No baseline" in report
    assert "build_re_review_checklist" in report
    assert "st.html(html)" in report
    assert "read-only" in report.casefold()


def test_phase9k_report_and_review_engines_do_not_mutate_investment_gates() -> None:
    review = Path("modules/deep_company_analysis/chapter9_synthesis_review.py").read_text(encoding="utf-8").casefold()
    report = Path("modules/deep_company_analysis/chapter9_synthesis_report.py").read_text(encoding="utf-8").casefold()
    for text in (review, report):
        assert "management quality score" in text
        assert "investment" in text
    assert "buy/hold/sell" in report
    assert "mos" in report


def test_phase9k_store_schema_v2_and_existing_tables_remain_compatible() -> None:
    store = Path("modules/deep_company_analysis/chapter9_synthesis_store.py").read_text(encoding="utf-8")
    assert "SCHEMA_VERSION = 2" in store
    assert "management_synthesis_current" in store
    assert "management_synthesis_snapshots" in store
    assert "last_re_review" not in store  # audit fields stay additive inside payload_json; no SQL migration needed
