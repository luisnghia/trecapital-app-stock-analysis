from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from modules.deep_company_analysis.chapter9_synthesis_history import (
    SYNTHESIS_FIELD_SPECS,
    SYNTHESIS_HISTORY_BOUNDARY,
    build_version_lineage,
    compare_synthesis_versions,
    synthesis_history_summary,
)
from modules.deep_company_analysis.chapter9_synthesis_workspace import empty_synthesis_workspace


def _workspace() -> dict:
    data = empty_synthesis_workspace("DGC", "Duc Giang")
    data["workspace_status"] = "Reviewed"
    data["analyst_confidence"] = "Medium"
    data["management_strengths"] = "Capital allocation discipline"
    data["management_concerns"] = "Succession evidence incomplete"
    data["final_management_synthesis"] = "Analyst-owned conclusion"
    data["source_fingerprint"] = "a" * 64
    data["source_counts"] = {"total_questions": 20, "evidence_rows": 8}
    data["source_captured_at"] = "2026-09-01T00:00:00+00:00"
    data["analyst_reviewed_at"] = "2026-09-01T00:05:00+00:00"
    return data


def test_phase9l_unchanged_versions_are_all_unchanged() -> None:
    before = _workspace()
    frame = compare_synthesis_versions(before, deepcopy(before), before_label="S1", after_label="S2")
    assert len(frame) == len(SYNTHESIS_FIELD_SPECS)
    assert set(frame["Delta"]) == {"Unchanged"}
    summary = synthesis_history_summary(before, deepcopy(before))
    assert summary["changed_fields"] == 0
    assert summary["unchanged_fields"] == len(SYNTHESIS_FIELD_SPECS)


def test_phase9l_added_removed_and_changed_are_structural_labels_only() -> None:
    before = _workspace()
    before["chapter9_traits_takeaway"] = ""
    after = deepcopy(before)
    after["chapter9_traits_takeaway"] = "New analyst note"
    after["management_concerns"] = ""
    after["workspace_status"] = "Finalized"
    frame = compare_synthesis_versions(before, after).set_index("Field")
    assert frame.loc["Chapter 9 Management Traits Takeaway", "Delta"] == "Added"
    assert frame.loc["Management Concerns", "Delta"] == "Removed"
    assert frame.loc["Synthesis Status", "Delta"] == "Changed"
    assert "improved" not in " ".join(frame["Delta"].astype(str)).casefold()
    assert "worsened" not in " ".join(frame["Delta"].astype(str)).casefold()


def test_phase9l_summary_detects_status_confidence_and_final_text_without_interpretation() -> None:
    before = _workspace()
    after = deepcopy(before)
    after["workspace_status"] = "Finalized"
    after["analyst_confidence"] = "High"
    after["final_management_synthesis"] = "Revised analyst-owned conclusion"
    summary = synthesis_history_summary(before, after)
    assert summary["status_changed"] is True
    assert summary["confidence_changed"] is True
    assert summary["final_synthesis_changed"] is True
    assert summary["automatic_workspace_status_change"] is False
    assert summary["automatic_confidence_change"] is False
    assert summary["automatic_analyst_text_change"] is False


def test_phase9l_source_baseline_delta_uses_stored_fingerprint_only() -> None:
    before = _workspace()
    after = deepcopy(before)
    after["source_fingerprint"] = "b" * 64
    frame = compare_synthesis_versions(before, after).set_index("Field")
    assert frame.loc["Source Baseline Fingerprint", "Before"] == "a" * 16
    assert frame.loc["Source Baseline Fingerprint", "After"] == "b" * 16
    assert frame.loc["Source Baseline Fingerprint", "Delta"] == "Changed"
    summary = synthesis_history_summary(before, after)
    assert summary["source_baseline_changed"] is True
    assert summary["historical_source_freshness_reconstructed"] is False


def test_phase9l_re_review_metadata_is_versioned_and_compared() -> None:
    before = _workspace()
    after = deepcopy(before)
    after["last_re_review_at"] = "2026-09-07T10:00:00+00:00"
    after["last_re_review_note"] = "Reviewed new Q52 evidence."
    after["last_re_review_sections"] = ["evidence_ledger"]
    frame = compare_synthesis_versions(before, after).set_index("Field")
    assert frame.loc["Last Re-review At", "Delta"] == "Added"
    assert frame.loc["Last Re-review Note", "Delta"] == "Added"
    assert frame.loc["Last Re-review Sections", "After"] == "evidence_ledger"


def test_phase9l_version_lineage_sorts_oldest_to_newest_deterministically() -> None:
    first = _workspace()
    second = deepcopy(first)
    second["workspace_status"] = "Finalized"
    second["last_re_review_sections"] = ["evidence_ledger"]
    records = [
        {"snapshot_id": 12, "created_at": "2026-09-07T12:00:00Z", "schema_version": 2, "payload": second},
        {"snapshot_id": 11, "created_at": "2026-09-06T12:00:00Z", "schema_version": 2, "payload": first},
    ]
    lineage = build_version_lineage(records)
    assert lineage["Snapshot ID"].tolist() == [11, 12]
    assert lineage["Version"].tolist() == ["Snapshot #11", "Snapshot #12"]
    assert lineage.iloc[1]["Synthesis Status"] == "Finalized"
    assert lineage.iloc[1]["Last Re-review Sections"] == "evidence_ledger"


def test_phase9l_lineage_does_not_claim_historical_freshness() -> None:
    lineage = build_version_lineage([
        {"snapshot_id": 1, "created_at": "2026-09-01T00:00:00Z", "schema_version": 2, "payload": _workspace()}
    ])
    assert "Source Freshness" not in lineage.columns
    assert "Historical Freshness" not in lineage.columns
    assert "historical source freshness" in Path(
        "modules/deep_company_analysis/chapter9_synthesis_history.py"
    ).read_text(encoding="utf-8").casefold()


def test_phase9l_comparison_is_pure_and_does_not_mutate_inputs() -> None:
    before = _workspace()
    after = deepcopy(before)
    after["management_unknowns"] = "New known unknown"
    before_copy = deepcopy(before)
    after_copy = deepcopy(after)
    compare_synthesis_versions(before, after)
    synthesis_history_summary(before, after)
    build_version_lineage([
        {"snapshot_id": 1, "created_at": "2026-09-01T00:00:00Z", "payload": before},
        {"snapshot_id": 2, "created_at": "2026-09-02T00:00:00Z", "payload": after},
    ])
    assert before == before_copy
    assert after == after_copy


def test_phase9l_ui_uses_wrapped_read_only_tables_terminology_and_runtime_log() -> None:
    ui = Path("modules/deep_company_analysis/chapter9_synthesis_ui.py").read_text(encoding="utf-8")
    assert "Phase 9L — Analyst Synthesis History & Delta Review" in ui
    assert "Version Lineage" in ui
    assert "Source Baseline" in ui
    assert "Re-review Lineage" in ui
    assert "static_table_html" in ui
    assert "st.html(html)" in ui
    assert "phase9l_synthesis_delta_view" in ui
    assert "Current saved workspace" in ui
    assert "restore" in ui.casefold()


def test_phase9l_consolidated_report_and_boundaries_preserve_v72_store_contract() -> None:
    report = Path("modules/deep_company_analysis/chapter9_synthesis_report.py").read_text(encoding="utf-8")
    store = Path("modules/deep_company_analysis/chapter9_synthesis_store.py").read_text(encoding="utf-8")
    history = Path("modules/deep_company_analysis/chapter9_synthesis_history.py").read_text(encoding="utf-8").casefold()
    assert "Phase 9L — Management Synthesis Version Lineage" in report
    assert "build_version_lineage" in report
    assert "compare_synthesis_versions" in report
    assert "st.html(html)" in report
    assert "SCHEMA_VERSION = 2" in store
    assert "management_synthesis_current" in store
    assert "management_synthesis_snapshots" in store
    assert "sqlite3" not in history
    assert "streamlit" not in history
    assert "management quality score" in SYNTHESIS_HISTORY_BOUNDARY.casefold()
    assert "investment research gate" in SYNTHESIS_HISTORY_BOUNDARY.casefold()
    summary = synthesis_history_summary(_workspace(), _workspace())
    assert summary["automatic_management_score"] is False
    assert summary["automatic_character_classification"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_investment_research_gate_changed"] is False
