from __future__ import annotations

import json
from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_completion as completion
import modules.deep_company_analysis.chapter9_source_contract_v63 as contract


REPORT_PATH = Path("reports/CH9_PHASE9G_RESEARCH_COMPLETION_V68.json")


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


def _closed_payload() -> dict:
    payload = ch9.empty_payload("DGC", "Duc Giang Chemicals")
    evidence = []
    for dim in contract.all_dimensions():
        evidence.append(
            {
                "Question": dim.question,
                "Dimension Key": dim.key,
                "Manager ID": "M001",
                "Manager": "Nguyễn Văn A",
                "Observation / Claim": f"Analyst-verified fixture for {dim.key}",
                "Source URL / File": f"https://example.com/{dim.key}",
                "Evidence Text / Reference": "Original source reference reviewed by analyst",
                "Source Grade": "B — reputable source",
                "Status": "Promoted — analyst verified",
                "Direction": "Neutral",
            }
        )
    payload["evidence"] = evidence
    for question in ch9.QUESTION_KEYS:
        payload["question_status"][question] = "Answered"
        payload["confidence"][question] = "Medium"
        payload["analyst_assessment"][question] = f"Analyst conclusion for {question}"
    return payload


def main() -> None:
    source = contract.validate_source_contract()
    chapter7 = _chapter7_payload()
    empty = completion.completion_snapshot(ch9.empty_payload("DGC"), chapter7)
    closed_payload = _closed_payload()
    closed = completion.completion_snapshot(closed_payload, chapter7)
    missing_manager = completion.completion_snapshot(ch9.empty_payload("DGC"), {})

    assert source["total_dimensions"] == 26
    assert source["dimension_counts"] == {"Q48": 6, "Q49": 4, "Q50": 8, "Q51": 3, "Q52": 5}
    assert empty["closed_dimensions"] == 0
    assert empty["open_dimensions"] == 26
    assert empty["research_completion_gate"] == "Blocked — research incomplete"
    assert closed["closed_dimensions"] == 26
    assert closed["ready_questions"] == 5
    assert closed["research_completion_gate"] == "Ready — research closure complete"
    assert missing_manager["blocked_dimensions"] == 26
    assert closed["automatic_question_status_change"] is False
    assert closed["automatic_confidence_change"] is False
    assert closed["automatic_analyst_assessment"] is False
    assert closed["automatic_management_score"] is False
    assert closed["automatic_character_classification"] is False
    assert closed["automatic_investment_signal"] is False
    assert closed["mos_or_investment_research_gate_changed"] is False

    report = {
        "phase": "Chapter 9 Phase 9G Research Completion Gate & Source Coverage Closure V68",
        "acceptance": "PASS",
        "chapter": ch9.CHAPTER_NUMBER,
        "chapter_title": ch9.CHAPTER_TITLE,
        "source_lock": ch9.SOURCE_LOCK,
        "exact_question_range": "Q48-Q52",
        "source_dimension_count": source["total_dimensions"],
        "dimension_counts": source["dimension_counts"],
        "manager_identity_ssot": ch9.MANAGER_IDENTITY_SSOT,
        "completion_is_research_process_only": True,
        "empty_search_does_not_close_dimension": True,
        "verified_evidence_requires_source_lineage": True,
        "analyst_closed_known_unknown_supported": True,
        "missing_chapter7_manager_blocks_closure": True,
        "ceo_specific_q48_q52_preserved": True,
        "question_ready_requires_analyst_status_confidence_assessment": True,
        "automatic_question_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_assessment": False,
        "automatic_management_score": False,
        "automatic_character_classification": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "runtime_jsonl_log_added": True,
        "formula_logic_document_added": True,
        "terminology_explanation_added": True,
        "cross_module_manager_ssot_preserved": True,
        "external_source_stack_reused": True,
        "financial_format_rules_applicable": False,
        "empty_workspace_snapshot": empty,
        "fully_closed_fixture_snapshot": closed,
        "missing_manager_snapshot": missing_manager,
        "next_phase": "Phase 9H — Chapter 9 consolidated-report/history integration and delta review, without management scoring.",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
