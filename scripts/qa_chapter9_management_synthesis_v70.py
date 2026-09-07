from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import modules.deep_company_analysis.chapter7 as ch7
import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract
from modules.deep_company_analysis.chapter9_synthesis import build_management_handoff


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "CH9_PHASE9I_MANAGEMENT_SYNTHESIS_V70.json"


def _chapter7_fixture() -> dict:
    payload = ch7.empty_payload("DGC", "DGC")
    payload["management_profiles"] = [
        {
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Current Role": "Tổng Giám đốc / CEO",
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
    payload["question_status"]["Q33"] = "Partial"
    payload["q33"]["conclusion"] = "Analyst-owned Chapter 7 conclusion."
    payload["evidence_matrix"] = [
        {
            "Question": "Q33",
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Claim": "Background evidence",
            "Source URL / File": "https://example.com/ch7",
            "Evidence Text / Reference": "Reference",
            "Status": "Promoted — analyst verified",
        }
    ]
    return payload


def _chapter8_fixture() -> dict:
    payload = ch8.empty_payload("DGC", "DGC")
    payload["question_status"]["Q39"] = "Partial"
    payload["confidence"]["Q39"] = "Medium"
    payload["analyst_assessment"]["Q39"] = "Analyst-owned Chapter 8 assessment."
    payload["evidence"] = [
        {
            "Question": "Q39",
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Claim": "Stakeholder evidence",
            "Source URL / File": "https://example.com/ch8",
            "Evidence Text / Reference": "Reference",
            "Status": "Promoted — analyst verified",
        }
    ]
    payload["research_gaps"] = [
        {"Question": "Q40", "Manager ID": "M001", "Research Gap": "Need operating evidence", "Status": "Open"}
    ]
    return payload


def _chapter9_fixture() -> dict:
    payload = ch9.empty_payload("DGC", "DGC")
    payload["question_status"]["Q48"] = "Partial"
    payload["confidence"]["Q48"] = "Low"
    payload["analyst_assessment"]["Q48"] = "Analyst-owned Chapter 9 assessment."
    payload["evidence"] = [
        {
            "Question": "Q48",
            "Dimension Key": "q48_career_vs_job",
            "Manager ID": "M001",
            "Manager": "Nguyễn Văn A",
            "Observation / Claim": "Passion evidence",
            "Source URL / File": "https://example.com/ch9",
            "Evidence Text / Reference": "Reference",
            "Status": "Promoted — analyst verified",
        }
    ]
    payload["research_gaps"] = [
        {
            "Question": "Q52",
            "Dimension Key": "q52_media_touting",
            "Manager ID": "M001",
            "Research Gap": "Need historical media review",
            "Status": "Open",
        }
    ]
    return payload


def main() -> None:
    chapter7 = _chapter7_fixture()
    chapter8 = _chapter8_fixture()
    chapter9 = _chapter9_fixture()
    before = (deepcopy(chapter7), deepcopy(chapter8), deepcopy(chapter9))
    handoff = build_management_handoff(chapter7, chapter8, chapter9)
    source = contract.validate_source_contract()
    page = (ROOT / "pages" / "04_Bao_cao_tong_hop.py").read_text(encoding="utf-8")
    engine = (ROOT / "modules" / "deep_company_analysis" / "chapter9_synthesis.py").read_text(encoding="utf-8")

    questions = handoff["question_ledger"]
    roster = handoff["manager_roster"]
    evidence = handoff["evidence_ledger"]
    gaps = handoff["open_research_gaps"]

    assert questions["Question"].tolist() == [f"Q{i}" for i in range(33, 53)]
    assert len(questions) == 20
    assert roster["Manager ID"].tolist() == ["M001", "M002"]
    assert set(roster["Identity Source"]) == {"Chapter 7 manager master"}
    assert evidence["Chapter"].tolist() == ["Chapter 7", "Chapter 8", "Chapter 9"]
    assert set(gaps["Question"]) == {"Q40", "Q52"}
    assert chapter7 == before[0]
    assert chapter8 == before[1]
    assert chapter9 == before[2]
    assert source["total_dimensions"] == 26
    assert "Management Synthesis Handoff — Chapters 7–9" in page
    assert "build_management_handoff" in page
    assert "st.html(table_html)" in page
    assert "import streamlit" not in engine.casefold()
    assert "sqlite3" not in engine.casefold()

    report = {
        "phase": "Chapter 9 Phase 9I Cross-Chapter Management Synthesis Handoff V70",
        "acceptance": "PASS",
        "source_question_range": "Q33-Q52",
        "chapter_question_counts": {"Chapter 7": 6, "Chapter 8": 9, "Chapter 9": 5},
        "total_questions": 20,
        "chapter9_source_dimension_count": source["total_dimensions"],
        "chapter9_dimension_counts": source["dimension_counts"],
        "manager_identity_ssot": handoff["manager_identity_ssot"],
        "manager_roster_from_chapter7_only": True,
        "cross_chapter_question_ledger": True,
        "cross_chapter_evidence_lineage": True,
        "cross_chapter_research_gap_ledger": True,
        "manager_lineage_reconciliation": True,
        "chapter_research_readiness": True,
        "consolidated_report_integrated": True,
        "st_html_wrapped_read_only_tables": True,
        "input_payloads_immutable": True,
        "analyst_synthesis_generated": handoff["analyst_synthesis_generated"],
        "automatic_management_score": handoff["automatic_management_score"],
        "automatic_character_classification": handoff["automatic_character_classification"],
        "automatic_investment_signal": handoff["automatic_investment_signal"],
        "mos_or_investment_research_gate_changed": handoff["mos_or_investment_research_gate_changed"],
        "fixture_handoff_state": handoff["handoff_state"],
        "fixture_manager_count": handoff["manager_count"],
        "fixture_evidence_rows": handoff["evidence_rows"],
        "fixture_open_research_gaps": handoff["research_gaps_open"],
        "fixture_lineage_warnings": handoff["lineage_warnings"],
        "next_phase": (
            "Phase 9J — analyst-owned cross-chapter management synthesis workspace and snapshot, "
            "without management scoring or automatic investment conclusions."
        ),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
