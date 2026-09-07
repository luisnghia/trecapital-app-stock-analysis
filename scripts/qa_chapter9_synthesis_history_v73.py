from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

from modules.deep_company_analysis.chapter9_synthesis_history import (
    SYNTHESIS_FIELD_SPECS,
    SYNTHESIS_HISTORY_BOUNDARY,
    build_version_lineage,
    compare_synthesis_versions,
    synthesis_history_summary,
)
from modules.deep_company_analysis.chapter9_synthesis_workspace import empty_synthesis_workspace


REPORT_PATH = Path("reports/CH9_PHASE9L_SYNTHESIS_HISTORY_V73.json")


def _workspace() -> dict:
    data = empty_synthesis_workspace("DGC", "Duc Giang")
    data["workspace_status"] = "Reviewed"
    data["analyst_confidence"] = "Medium"
    data["management_strengths"] = "Analyst-recorded strength"
    data["management_concerns"] = "Analyst-recorded concern"
    data["final_management_synthesis"] = "Version A analyst synthesis"
    data["source_fingerprint"] = "a" * 64
    data["source_counts"] = {"total_questions": 20, "evidence_rows": 8}
    data["source_handoff_state"] = "Ready — Chapters 7–9 research handoff complete"
    data["source_captured_at"] = "2026-09-01T00:00:00+00:00"
    data["analyst_reviewed_at"] = "2026-09-01T00:05:00+00:00"
    return data


def main() -> None:
    before = _workspace()
    after = deepcopy(before)
    after["workspace_status"] = "Finalized"
    after["analyst_confidence"] = "High"
    after["chapter9_traits_takeaway"] = "Analyst added a Chapter 9 takeaway"
    after["management_concerns"] = ""
    after["final_management_synthesis"] = "Version B analyst synthesis"
    after["source_fingerprint"] = "b" * 64
    after["last_re_review_at"] = "2026-09-07T10:00:00+00:00"
    after["last_re_review_note"] = "Reviewed changed evidence ledger."
    after["last_re_review_sections"] = ["evidence_ledger"]

    before_copy = deepcopy(before)
    after_copy = deepcopy(after)

    delta = compare_synthesis_versions(
        before,
        after,
        before_label="Snapshot #101",
        after_label="Snapshot #102",
    )
    summary = synthesis_history_summary(before, after)
    lineage = build_version_lineage([
        {"snapshot_id": 102, "created_at": "2026-09-07T10:05:00Z", "schema_version": 2, "payload": after},
        {"snapshot_id": 101, "created_at": "2026-09-01T00:10:00Z", "schema_version": 2, "payload": before},
    ])

    ui = Path("modules/deep_company_analysis/chapter9_synthesis_ui.py").read_text(encoding="utf-8")
    report_ui = Path("modules/deep_company_analysis/chapter9_synthesis_report.py").read_text(encoding="utf-8")
    history_source = Path("modules/deep_company_analysis/chapter9_synthesis_history.py").read_text(encoding="utf-8")
    store = Path("modules/deep_company_analysis/chapter9_synthesis_store.py").read_text(encoding="utf-8")
    formula_doc = Path("docs/FORMULA_EXPLANATION_CHAPTER9_PHASE9L_V73.md").read_text(encoding="utf-8")
    phase_doc = Path("docs/CHAPTER9_PHASE9L_SYNTHESIS_HISTORY_V73.md").read_text(encoding="utf-8")

    changed = delta[delta["Delta"] != "Unchanged"]
    checks = {
        "tracked_fields_complete": len(delta) == len(SYNTHESIS_FIELD_SPECS) == 19,
        "neutral_delta_vocabulary": set(delta["Delta"]).issubset({"Unchanged", "Added", "Removed", "Changed"}),
        "status_change_detected": summary["status_changed"] is True,
        "confidence_change_detected": summary["confidence_changed"] is True,
        "final_synthesis_change_detected": summary["final_synthesis_changed"] is True,
        "source_baseline_change_detected": summary["source_baseline_changed"] is True,
        "historical_freshness_not_reconstructed": summary["historical_source_freshness_reconstructed"] is False,
        "lineage_oldest_to_newest": lineage["Snapshot ID"].tolist() == [101, 102],
        "lineage_keeps_review_metadata": lineage.iloc[-1]["Last Re-review Sections"] == "evidence_ledger",
        "comparison_is_pure": before == before_copy and after == after_copy,
        "ui_integrated": "Phase 9L — Analyst Synthesis History & Delta Review" in ui,
        "ui_wrapped_tables": "static_table_html" in ui and "st.html(html)" in ui,
        "ui_terminology_help": all(term in ui for term in ("Version Lineage", "Source Baseline", "Re-review Lineage")),
        "runtime_log_integrated": "phase9l_synthesis_delta_view" in ui,
        "consolidated_report_integrated": "Phase 9L — Management Synthesis Version Lineage" in report_ui,
        "consolidated_report_read_only": "save_workspace" not in report_ui and "create_snapshot" not in report_ui,
        "consolidated_report_wrapped_tables": "st.html(html)" in report_ui,
        "history_backend_pure": "import streamlit" not in history_source.casefold() and "sqlite3" not in history_source.casefold(),
        "store_schema_v2": "SCHEMA_VERSION = 2" in store,
        "sql_table_shape_unchanged": "management_synthesis_current" in store and "management_synthesis_snapshots" in store,
        "formula_doc_no_financial_formula": "no financial valuation formula" in formula_doc.casefold(),
        "formula_doc_no_weighted_score": "no weighted score" in formula_doc.casefold(),
        "phase_doc_historical_boundary": "not reconstructed" in phase_doc.casefold(),
        "automatic_workspace_status_change": summary["automatic_workspace_status_change"] is False,
        "automatic_confidence_change": summary["automatic_confidence_change"] is False,
        "automatic_analyst_text_change": summary["automatic_analyst_text_change"] is False,
        "automatic_management_score": summary["automatic_management_score"] is False,
        "automatic_character_classification": summary["automatic_character_classification"] is False,
        "automatic_investment_signal": summary["automatic_investment_signal"] is False,
        "mos_or_investment_research_gate_changed": summary["mos_or_investment_research_gate_changed"] is False,
        "boundary_mentions_management_score": "management quality score" in SYNTHESIS_HISTORY_BOUNDARY.casefold(),
        "boundary_mentions_investment_gate": "investment research gate" in SYNTHESIS_HISTORY_BOUNDARY.casefold(),
    }
    failed = [name for name, ok in checks.items() if not ok]

    report = {
        "phase": "Chapter 9 Phase 9L Analyst Synthesis History & Delta Review V73",
        "acceptance": "FAIL" if failed else "PASS",
        "source_question_range": "Q33–Q52",
        "total_questions": 20,
        "manager_identity_ssot": "Chapter 7 manager master",
        "tracked_synthesis_fields": len(SYNTHESIS_FIELD_SPECS),
        "changed_fields_fixture": int(len(changed)),
        "delta_states": sorted(set(delta["Delta"].tolist())),
        "snapshot_lineage_ids": lineage["Snapshot ID"].tolist(),
        "source_baseline_changed": summary["source_baseline_changed"],
        "historical_source_freshness_reconstructed": summary["historical_source_freshness_reconstructed"],
        "store_schema_version": 2,
        "sql_table_shape_unchanged": checks["sql_table_shape_unchanged"],
        "ui_history_integrated": checks["ui_integrated"],
        "consolidated_report_integrated": checks["consolidated_report_integrated"],
        "wrapped_read_only_tables": checks["ui_wrapped_tables"] and checks["consolidated_report_wrapped_tables"],
        "runtime_log_integrated": checks["runtime_log_integrated"],
        "automatic_workspace_status_change": summary["automatic_workspace_status_change"],
        "automatic_confidence_change": summary["automatic_confidence_change"],
        "automatic_analyst_text_change": summary["automatic_analyst_text_change"],
        "automatic_management_score": summary["automatic_management_score"],
        "automatic_character_classification": summary["automatic_character_classification"],
        "automatic_investment_signal": summary["automatic_investment_signal"],
        "mos_or_investment_research_gate_changed": summary["mos_or_investment_research_gate_changed"],
        "no_financial_valuation_formula": checks["formula_doc_no_financial_formula"],
        "no_weighted_score": checks["formula_doc_no_weighted_score"],
        "checks": checks,
        "failed_checks": failed,
        "next_phase": "Phase 9M — analyst-authored management-synthesis change rationale / decision-journal linkage, without management scoring or automatic investment conclusions.",
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(f"Phase 9L acceptance failed: {', '.join(failed)}")


if __name__ == "__main__":
    main()
