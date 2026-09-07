from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_history as history
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


ROOT = Path(__file__).resolve().parents[2]


def _chapter7_payload() -> dict:
    return {
        "ticker": "DGC",
        "management_profiles": [
            {
                "Manager ID": "M001",
                "Manager": "Nguyễn Văn A",
                "Current Role": "Tổng Giám đốc / CEO",
                "Confidence": "High",
            },
            {
                "Manager ID": "M002",
                "Manager": "Trần Văn B",
                "Current Role": "CFO",
                "Confidence": "Medium",
            },
        ],
    }


def _evidence(candidate_id: str = "C-001") -> dict:
    return {
        "Candidate ID": candidate_id,
        "Question": "Q48",
        "Dimension Key": "q48_career_vs_job",
        "Dimension": "Career vs job",
        "Manager ID": "M001",
        "Manager": "Nguyễn Văn A",
        "Observation / Claim": "Verified observation",
        "Source URL / File": "https://example.com/original",
        "Evidence Text / Reference": "Original source reference",
        "Status": "Promoted — analyst verified",
        "Direction": "Neutral",
        "Analyst Note": "Analyst note",
    }


def test_report_preserves_q48_q52_source_order_and_26_dimensions() -> None:
    payload = ch9.empty_payload("DGC")
    frames = history.build_chapter9_report_frames(payload, _chapter7_payload())
    assert list(frames["questions"]["Question"]) == list(ch9.QUESTION_KEYS)
    assert len(frames["questions"]) == 5
    assert len(frames["dimension_closure"]) == 26
    assert frames["dimension_closure"]["Dimension Key"].nunique() == 26
    assert len(contract.all_dimensions()) == 26


def test_consolidated_question_report_preserves_analyst_text_verbatim() -> None:
    payload = ch9.empty_payload("DGC")
    payload["question_status"]["Q49"] = "Answered"
    payload["confidence"]["Q49"] = "Medium"
    payload["analyst_assessment"]["Q49"] = "Analyst conclusion — keep this verbatim."
    frame = history.build_question_report(payload, _chapter7_payload())
    row = frame[frame["Question"].eq("Q49")].iloc[0]
    assert row["Research Status"] == "Answered"
    assert row["Analyst Confidence"] == "Medium"
    assert row["Analyst Assessment"] == "Analyst conclusion — keep this verbatim."
    assert payload["analyst_assessment"]["Q49"] == "Analyst conclusion — keep this verbatim."


def test_summary_is_research_metadata_not_management_score() -> None:
    summary = history.build_chapter9_summary(ch9.empty_payload("DGC"), _chapter7_payload())
    assert summary["total_questions"] == 5
    assert summary["source_dimension_count"] == 26
    assert summary["automatic_management_score"] is False
    assert summary["automatic_character_classification"] is False
    assert summary["automatic_investment_signal"] is False
    assert "score" not in summary
    assert "rank" not in summary


def test_question_delta_detects_status_confidence_and_assessment_changes() -> None:
    before = ch9.empty_payload("DGC")
    after = deepcopy(before)
    after["question_status"]["Q50"] = "Partial"
    after["confidence"]["Q50"] = "Low"
    after["analyst_assessment"]["Q50"] = "Analyst changed assessment"
    delta = history.compare_chapter9_payloads(before, after, _chapter7_payload())
    q = delta["question_delta"]
    assert len(q) == 3
    assert set(q["Field"]) == {"Research Status", "Analyst Confidence", "Analyst Assessment"}
    assert delta["summary"]["question_field_changes"] == 3


def test_evidence_delta_uses_candidate_id_and_detects_add_remove_change() -> None:
    before = ch9.empty_payload("DGC")
    before["evidence"] = [_evidence("C-001"), _evidence("C-OLD")]
    after = deepcopy(before)
    after["evidence"] = [_evidence("C-001"), _evidence("C-NEW")]
    after["evidence"][0]["Analyst Note"] = "Changed note"
    delta = history.compare_chapter9_payloads(before, after, _chapter7_payload())
    changes = set(delta["evidence_delta"]["Change"])
    assert changes == {"Added", "Removed", "Changed"}
    assert delta["summary"]["evidence_added"] == 1
    assert delta["summary"]["evidence_removed"] == 1
    assert delta["summary"]["evidence_changed"] == 1


def test_gap_delta_detects_closed_and_reopened_without_interpreting_quality() -> None:
    before = ch9.empty_payload("DGC")
    before["research_gaps"] = [
        {
            "Question": "Q51",
            "Dimension Key": "q51_long_term_focus",
            "Manager ID": "M001",
            "Research Gap": "Need older interview",
            "Status": "Open — evidence gap",
        },
        {
            "Question": "Q52",
            "Dimension Key": "q52_media_touting",
            "Manager ID": "M001",
            "Research Gap": "Archive missing",
            "Status": "Closed — analyst accepted known unknown",
        },
    ]
    after = deepcopy(before)
    after["research_gaps"][0]["Status"] = "Closed — analyst accepted known unknown"
    after["research_gaps"][1]["Status"] = "Open — new archive lead"
    delta = history.compare_chapter9_payloads(before, after, _chapter7_payload())
    assert set(delta["gap_delta"]["Change"]) == {"Closed", "Reopened"}
    assert delta["summary"]["gaps_closed"] == 1
    assert delta["summary"]["gaps_reopened"] == 1
    assert delta["summary"]["automatic_management_score"] is False


def test_behavior_event_delta_detects_history_change() -> None:
    before = ch9.empty_payload("DGC")
    after = deepcopy(before)
    after["behavior_events"] = [
        {
            "Event Date": "2026-01-01",
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Context / Situation": "Annual meeting",
            "Source": "Official transcript",
        }
    ]
    delta = history.compare_chapter9_payloads(before, after, _chapter7_payload())
    assert len(delta["behavior_event_delta"]) == 1
    assert delta["behavior_event_delta"].iloc[0]["Change"] == "Added"
    assert delta["summary"]["behavior_event_changes"] == 1


def test_completion_delta_reports_newly_closed_dimension_descriptively() -> None:
    before = ch9.empty_payload("DGC")
    after = deepcopy(before)
    after["evidence"] = [_evidence()]
    delta = history.compare_chapter9_payloads(before, after, _chapter7_payload())
    closure = delta["closure_delta"]
    row = closure[closure["Dimension Key"].eq("q48_career_vs_job")].iloc[0]
    assert row["Change"] == "Newly closed"
    assert delta["summary"]["dimensions_newly_closed"] == 1
    assert "better" not in " ".join(closure.astype(str).stack()).casefold()


def test_same_payload_produces_zero_delta() -> None:
    payload = ch9.empty_payload("DGC")
    payload["evidence"] = [_evidence()]
    delta = history.compare_chapter9_payloads(payload, deepcopy(payload), _chapter7_payload())
    assert delta["question_delta"].empty
    assert delta["evidence_delta"].empty
    assert delta["gap_delta"].empty
    assert delta["behavior_event_delta"].empty
    assert delta["closure_delta"].empty
    assert delta["summary"]["question_field_changes"] == 0


def test_delta_engine_never_mutates_inputs() -> None:
    before = ch9.empty_payload("DGC")
    after = deepcopy(before)
    after["question_status"]["Q48"] = "Partial"
    chapter7 = _chapter7_payload()
    frozen_before = deepcopy(before)
    frozen_after = deepcopy(after)
    frozen_ch7 = deepcopy(chapter7)
    history.compare_chapter9_payloads(before, after, chapter7)
    assert before == frozen_before
    assert after == frozen_after
    assert chapter7 == frozen_ch7


def test_pure_history_engine_has_no_streamlit_or_database_writes() -> None:
    source = Path(history.__file__).read_text(encoding="utf-8").casefold()
    assert "import streamlit" not in source
    assert "sqlite3" not in source
    assert "save_record(" not in source
    assert "create_snapshot(" not in source
    assert "management score" in source
    assert "buy/hold/sell" in source


def test_phase9h_consolidated_report_ui_uses_real_st_html_wrapped_tables() -> None:
    page = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")
    assert "Deep Company Analysis — Chương 9" in page
    assert "Phase 9H — Snapshot History & Delta Review" in page
    assert "Giải thích thuật ngữ Phase 9H" in page
    assert "static_table_html" in page
    assert "st.html(table_html)" in page
    assert "compare_chapter9_payloads" in page
    assert "Current Workspace" in page
    assert "Ghi log Delta Review Chapter 9" in page


def test_phase9h_report_has_no_restore_or_automatic_investment_action() -> None:
    page = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8").casefold()
    assert "restore snapshot" not in page
    assert "management_score =" not in page
    assert "character_classification =" not in page
    assert "buy_signal =" not in page
    assert "sell_signal =" not in page
    assert "research_gate =" not in page
