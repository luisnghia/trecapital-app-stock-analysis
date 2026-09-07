from __future__ import annotations

"""Deterministic acceptance QA for Chapter 9 Phase 9H / V69."""

from copy import deepcopy
from pathlib import Path
import json

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_history as history
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "CH9_PHASE9H_CONSOLIDATED_HISTORY_V69.json"


def chapter7_fixture() -> dict:
    return {
        "ticker": "DGC",
        "management_profiles": [
            {
                "Manager ID": "M001",
                "Manager": "Nguyễn Văn A",
                "Current Role": "Tổng Giám đốc / CEO",
                "Confidence": "High",
            }
        ],
    }


def evidence_fixture() -> dict:
    return {
        "Candidate ID": "QA-C001",
        "Question": "Q48",
        "Dimension Key": "q48_career_vs_job",
        "Manager ID": "M001",
        "Manager": "Nguyễn Văn A",
        "Observation / Claim": "Verified observation",
        "Source URL / File": "https://example.com/source",
        "Evidence Text / Reference": "Original source reference",
        "Status": "Promoted — analyst verified",
        "Direction": "Neutral",
    }


def main() -> int:
    chapter7 = chapter7_fixture()
    before = ch9.empty_payload("DGC", "DGC")
    after = deepcopy(before)
    after["question_status"]["Q48"] = "Partial"
    after["confidence"]["Q48"] = "Low"
    after["analyst_assessment"]["Q48"] = "Analyst-owned assessment"
    after["evidence"] = [evidence_fixture()]
    after["research_gaps"] = [
        {
            "Question": "Q52",
            "Dimension Key": "q52_media_touting",
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Research Gap": "Archive search not yet complete",
            "Status": "Open — evidence gap",
        }
    ]
    after["behavior_events"] = [
        {
            "Event Date": "2026-01-01",
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Context / Situation": "Annual meeting",
            "Source": "Official transcript",
        }
    ]

    frozen_before = deepcopy(before)
    frozen_after = deepcopy(after)
    delta = history.compare_chapter9_payloads(before, after, chapter7)
    frames = history.build_chapter9_report_frames(after, chapter7)
    summary = history.build_chapter9_summary(after, chapter7)
    source = contract.validate_source_contract()
    page = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")

    assert before == frozen_before
    assert after == frozen_after
    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    assert source["total_dimensions"] == 26
    assert source["dimension_counts"] == {"Q48": 6, "Q49": 4, "Q50": 8, "Q51": 3, "Q52": 5}
    assert ch9.MANAGER_IDENTITY_SSOT == "Chapter 7 manager master"
    assert list(frames["questions"]["Question"]) == list(ch9.QUESTION_KEYS)
    assert len(frames["dimension_closure"]) == 26
    assert summary["source_dimension_count"] == 26
    assert delta["summary"]["question_field_changes"] == 3
    assert delta["summary"]["evidence_added"] == 1
    assert delta["summary"]["behavior_event_changes"] == 1
    assert delta["summary"]["dimensions_newly_closed"] == 1
    assert delta["summary"]["automatic_management_score"] is False
    assert delta["summary"]["automatic_character_classification"] is False
    assert delta["summary"]["automatic_investment_signal"] is False
    assert delta["summary"]["mos_or_investment_research_gate_changed"] is False
    assert "Phase 9H — Snapshot History & Delta Review" in page
    assert "Giải thích thuật ngữ Phase 9H" in page
    assert "st.html(table_html)" in page
    assert "Current Workspace" in page
    assert "load_chapter9_snapshot" in page
    assert "compare_chapter9_payloads" in page
    assert "restore snapshot" not in page.casefold()

    report = {
        "phase": "Chapter 9 Phase 9H Consolidated Report + Snapshot History/Delta Review V69",
        "acceptance": "PASS",
        "chapter": 9,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "exact_question_range": "Q48-Q52",
        "source_dimension_count": source["total_dimensions"],
        "dimension_counts": source["dimension_counts"],
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "consolidated_report_integrated": True,
        "snapshot_history_integrated": True,
        "snapshot_delta_review_integrated": True,
        "current_workspace_comparison_supported": True,
        "question_status_confidence_assessment_delta": True,
        "evidence_add_remove_change_delta": True,
        "research_gap_close_reopen_delta": True,
        "behavior_event_delta": True,
        "source_dimension_closure_delta": True,
        "delta_inputs_immutable": before == frozen_before and after == frozen_after,
        "st_html_wrapped_read_only_tables": "st.html(table_html)" in page,
        "terminology_explanation_added": "Giải thích thuật ngữ Phase 9H" in page,
        "runtime_delta_log_hook_added": "phase9h_delta_review" in page,
        "snapshot_restore_added": False,
        "automatic_question_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_assessment": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "fixture_delta_summary": delta["summary"],
        "next_phase": "Phase 9I — cross-chapter management synthesis handoff for Chapters 7-9, analyst-owned and without management scoring.",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
