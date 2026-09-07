from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd

import modules.deep_company_analysis.chapter7 as ch7
from modules.deep_company_analysis.chapter7_closure import FINAL_CHECKLIST_ITEMS, default_final_checklist_rows
import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_synthesis as synthesis


ROOT = Path(__file__).resolve().parents[2]


def _ch7() -> dict:
    payload = ch7.empty_payload("DGC", "DGC")
    payload["management_profiles"] = [
        {
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Current Role": "Tổng Giám đốc / CEO",
            "Founder?": "No",
            "Joined Company": "2015",
            "Started Current Role": "2020",
            "Analyst Classification": "LT1",
            "Confidence": "High",
        },
        {
            "Manager ID": "M002",
            "Manager": "Trần Văn B",
            "Current Role": "CFO",
            "Analyst Classification": "LT2",
            "Confidence": "Medium",
        },
    ]
    return payload


def _evidence(question: str, manager_id: str, manager: str, claim: str) -> dict:
    return {
        "Question": question,
        "Manager ID": manager_id,
        "Manager": manager,
        "Claim": claim,
        "Direction": "Neutral",
        "Status": "Promoted — analyst verified",
        "Source Grade": "A — Official",
        "Source Title": "Official source",
        "Source URL / File": "https://example.com/source",
        "Evidence Text / Reference": "Original reference",
        "Data Origin": "Analyst workspace",
    }


def test_phase9i_preserves_exact_cross_chapter_question_ranges() -> None:
    assert ch7.QUESTION_KEYS == ("Q33", "Q34", "Q35", "Q36", "Q37", "Q38")
    assert ch8.QUESTION_KEYS == ("Q39", "Q40", "Q41", "Q42", "Q43", "Q44", "Q45", "Q46", "Q47")
    assert ch9.QUESTION_KEYS == ("Q48", "Q49", "Q50", "Q51", "Q52")
    ledger = synthesis.build_question_ledger(_ch7(), ch8.empty_payload("DGC"), ch9.empty_payload("DGC"))
    assert ledger["Question"].tolist() == [f"Q{i}" for i in range(33, 53)]
    assert len(ledger) == 20


def test_manager_roster_comes_only_from_chapter7_manager_master() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    ch8_payload["evidence"] = [_evidence("Q39", "M999", "Invented", "Must not create manager")]
    ch9_payload["evidence"] = [
        {
            **_evidence("Q49", "M888", "Other invented", "Must not create manager"),
            "Observation / Claim": "Must not create manager",
        }
    ]
    roster = synthesis.build_manager_roster(ch7_payload)
    assert roster["Manager ID"].tolist() == ["M001", "M002"]
    assert set(roster["Identity Source"]) == {"Chapter 7 manager master"}
    assert "M999" not in set(roster["Manager ID"])
    assert "M888" not in set(roster["Manager ID"])


def test_invented_manager_references_become_lineage_warnings_not_new_roster_rows() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    ch8_payload["evidence"] = [_evidence("Q43", "M999", "Invented", "Candidate-like row")]
    ch9_payload["research_gaps"] = [
        {
            "Question": "Q50",
            "Manager ID": "M888",
            "Manager": "Unknown",
            "Research Gap": "Needs identity reconciliation",
            "Status": "Open",
        }
    ]
    warnings = synthesis.build_lineage_warnings(ch7_payload, ch8_payload, ch9_payload)
    assert set(warnings["Manager ID"]) == {"M999", "M888"}
    assert all("Chapter 7" in text for text in warnings["Required Action"].astype(str))


def test_analyst_conclusions_and_statuses_are_copied_verbatim() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    ch7_payload["question_status"]["Q33"] = "Answered"
    ch7_payload["q33"]["conclusion"] = "Chapter 7 analyst conclusion — verbatim."
    ch8_payload["question_status"]["Q39"] = "Partial"
    ch8_payload["confidence"]["Q39"] = "Medium"
    ch8_payload["analyst_assessment"]["Q39"] = "Chapter 8 analyst assessment — verbatim."
    ch9_payload["question_status"]["Q48"] = "Answered"
    ch9_payload["confidence"]["Q48"] = "High"
    ch9_payload["analyst_assessment"]["Q48"] = "Chapter 9 analyst assessment — verbatim."
    ledger = synthesis.build_question_ledger(ch7_payload, ch8_payload, ch9_payload).set_index("Question")
    assert ledger.loc["Q33", "Analyst Assessment / Conclusion"] == "Chapter 7 analyst conclusion — verbatim."
    assert ledger.loc["Q39", "Research Status"] == "Partial"
    assert ledger.loc["Q39", "Analyst Confidence"] == "Medium"
    assert ledger.loc["Q39", "Analyst Assessment / Conclusion"] == "Chapter 8 analyst assessment — verbatim."
    assert ledger.loc["Q48", "Analyst Confidence"] == "High"
    assert ledger.loc["Q48", "Analyst Assessment / Conclusion"] == "Chapter 9 analyst assessment — verbatim."


def test_unknown_is_preserved_as_unknown_and_not_converted_to_negative_trait() -> None:
    ledger = synthesis.build_question_ledger(_ch7(), ch8.empty_payload("DGC"), ch9.empty_payload("DGC"))
    q48 = ledger[ledger["Question"].eq("Q48")].iloc[0]
    assert q48["Research Status"] == "Unknown"
    assert q48["Analyst Confidence"] == "Unknown"
    assert q48["Analyst Assessment / Conclusion"] == "Unknown"
    assert "negative" not in str(q48).casefold()


def test_cross_chapter_evidence_ledger_preserves_source_and_manager_lineage() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    ch7_payload["evidence_matrix"] = [_evidence("Q33", "M001", "Nguyễn Văn A", "Background claim")]
    ch8_payload["evidence"] = [_evidence("Q39", "M001", "Nguyễn Văn A", "Stakeholder claim")]
    ch9_row = _evidence("Q49", "M001", "Nguyễn Văn A", "Integrity observation")
    ch9_row.pop("Claim")
    ch9_row["Observation / Claim"] = "Integrity observation"
    ch9_payload["evidence"] = [ch9_row]
    ledger = synthesis.build_evidence_ledger(ch7_payload, ch8_payload, ch9_payload)
    assert ledger["Chapter"].tolist() == ["Chapter 7", "Chapter 8", "Chapter 9"]
    assert ledger["Question"].tolist() == ["Q33", "Q39", "Q49"]
    assert ledger["Manager ID"].tolist() == ["M001", "M001", "M001"]
    assert all(ledger["Source URL / File"].astype(str).str.contains("example.com"))
    assert ledger.loc[ledger["Question"].eq("Q49"), "Claim / Observation"].iloc[0] == "Integrity observation"


def test_research_gap_ledger_can_show_open_only_without_treating_closed_known_unknown_as_evidence() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    ch7_payload["research_gaps_table"] = [
        {"Question": "Q36", "Research Gap": "Open career gap", "Status": "Open"}
    ]
    ch8_payload["research_gaps"] = [
        {"Question": "Q44", "Research Gap": "Resolved hiring gap", "Status": "Resolved"}
    ]
    ch9_payload["research_gaps"] = [
        {"Question": "Q52", "Research Gap": "Known unknown", "Status": "Closed — analyst accepted known unknown"}
    ]
    all_gaps = synthesis.build_gap_ledger(ch7_payload, ch8_payload, ch9_payload)
    open_gaps = synthesis.build_gap_ledger(ch7_payload, ch8_payload, ch9_payload, open_only=True)
    assert len(all_gaps) == 3
    assert open_gaps["Question"].tolist() == ["Q36"]
    assert "Q52" not in open_gaps["Question"].tolist()


def test_chapter_readiness_is_research_process_metadata_not_quality_score() -> None:
    readiness = synthesis.build_chapter_readiness(_ch7(), ch8.empty_payload("DGC"), ch9.empty_payload("DGC"))
    assert readiness["Chapter"].tolist() == ["Chapter 7", "Chapter 8", "Chapter 9"]
    assert readiness["Questions"].tolist() == [6, 9, 5]
    assert readiness["Handoff State"].astype(str).str.startswith(("Open", "Review", "Ready")).all()
    joined = " ".join(readiness.columns).casefold()
    assert "management score" not in joined
    assert "weighted score" not in joined
    assert "buy signal" not in joined


def test_handoff_blocks_on_manager_lineage_warning_without_auto_fixing_identity() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    ch9_payload["evidence"] = [
        {
            "Question": "Q50",
            "Dimension Key": "q50_shareholder_letters",
            "Manager ID": "M404",
            "Manager": "Not in Chapter 7",
            "Observation / Claim": "Unreconciled row",
            "Status": "Promoted — analyst verified",
            "Source URL / File": "https://example.com/x",
            "Evidence Text / Reference": "ref",
        }
    ]
    result = synthesis.build_management_handoff(ch7_payload, ch8_payload, ch9_payload)
    assert result["lineage_warnings"] == 1
    assert result["handoff_state"] == "Blocked — manager lineage reconciliation required"
    assert set(result["manager_roster"]["Manager ID"]) == {"M001", "M002"}


def test_management_handoff_does_not_mutate_any_chapter_payload() -> None:
    ch7_payload = _ch7()
    ch8_payload = ch8.empty_payload("DGC")
    ch9_payload = ch9.empty_payload("DGC")
    before = (deepcopy(ch7_payload), deepcopy(ch8_payload), deepcopy(ch9_payload))
    synthesis.build_management_handoff(ch7_payload, ch8_payload, ch9_payload)
    assert ch7_payload == before[0]
    assert ch8_payload == before[1]
    assert ch9_payload == before[2]


def test_management_handoff_never_generates_synthesis_score_or_investment_signal() -> None:
    result = synthesis.build_management_handoff(_ch7(), ch8.empty_payload("DGC"), ch9.empty_payload("DGC"))
    assert result["total_questions"] == 20
    assert result["chapter_count"] == 3
    assert result["analyst_synthesis_generated"] is False
    assert result["automatic_management_score"] is False
    assert result["automatic_character_classification"] is False
    assert result["automatic_investment_signal"] is False
    assert result["mos_or_investment_research_gate_changed"] is False
    assert "management quality score" in result["boundary"].casefold()


def test_phase9i_backend_is_pure_and_does_not_create_new_store_or_streamlit_ui() -> None:
    source = Path(synthesis.__file__).read_text(encoding="utf-8").casefold()
    assert "import streamlit" not in source
    assert "sqlite3" not in source
    assert "save_record(" not in source
    assert "create_snapshot(" not in source
    assert "management quality score" in source
    assert "chapter 7 manager master" in source


def test_phase9i_page_integration_uses_existing_consolidated_report_and_wrapped_read_only_tables() -> None:
    page = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")
    # This contract becomes active once the Phase 9I page patch is applied on the same branch.
    assert "Management Synthesis Handoff — Chapters 7–9" in page
    assert "build_management_handoff" in page
    assert "static_table_html" in page
    assert "st.html(table_html)" in page
    assert "Management Quality Score" in page
    assert "ready_for_analyst_synthesis" in page
