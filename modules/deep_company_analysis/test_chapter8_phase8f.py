from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_completion import (
    SOURCE_LOCKED_CAPITAL_ALLOCATION_ACTIONS,
    build_completion_gate,
    build_source_closure_table,
    completion_gate_text,
)


def _closed_payload() -> dict:
    payload = ch8.empty_payload("DGC", "Đức Giang")
    for q in ch8.QUESTION_KEYS:
        payload["question_status"][q] = "Answered"
        payload["confidence"][q] = "Medium"
        payload["analyst_assessment"][q] = f"Analyst conclusion for {q}"
        evidence = {column: "" for column in ch8.EVIDENCE_COLUMNS}
        evidence.update(
            {
                "Question": q,
                "Claim": f"Evidence for {q}",
                "Source Grade": "A — Company/Official disclosure",
                "Source Title": "Official disclosure",
                "Source URL / File": "https://example.com/official",
                "Direction": "Neutral",
                "Status": "Promoted — analyst evidence",
                "Data Origin": "Analyst-promoted evidence",
            }
        )
        payload["evidence"].append(evidence)
    return payload


def _structured_context() -> dict:
    return {
        "q41_guidance_history": pd.DataFrame([{"Metric": "Revenue"}]),
        "q45_cost_context": pd.DataFrame([{"Kỳ": "2025"}]),
        "q46_capital_allocation_context": pd.DataFrame([{"Kỳ": "2025"}]),
        "q47_buyback_context": pd.DataFrame(
            [{"Kỳ": "2025", "Explicit buyback field available?": "Yes"}]
        ),
    }


def _chapter7_payload() -> dict:
    return {
        "management_profiles": [
            {"Manager ID": "M001", "Manager": "CEO A", "Current Role": "CEO"},
            {"Manager ID": "M002", "Manager": "CFO B", "Current Role": "CFO"},
        ]
    }


def test_empty_payload_is_not_ready() -> None:
    gate = build_completion_gate(ch8.empty_payload("DGC"))
    assert gate["ready_for_chapter_close"] is False
    assert gate["closed_count"] == 0
    assert gate["open_questions"] == list(ch8.QUESTION_KEYS)
    assert gate["automatic_management_score"] is False
    assert gate["automatic_investment_signal"] is False


def test_answered_requires_analyst_assessment_and_promoted_evidence() -> None:
    payload = ch8.empty_payload("DGC")
    payload["question_status"]["Q39"] = "Answered"
    table = build_source_closure_table(payload)
    row = table.loc[table["Question"].eq("Q39")].iloc[0]
    assert row["Completion State"] == "Open"
    assert "Answered without analyst assessment" in row["Blocking Reason"]
    assert "Answered without promoted/manual evidence" in row["Blocking Reason"]


def test_na_can_close_without_fabricated_evidence() -> None:
    payload = ch8.empty_payload("DGC")
    for q in ch8.QUESTION_KEYS:
        payload["question_status"][q] = "N/A"
    gate = build_completion_gate(payload)
    assert gate["ready_for_chapter_close"] is True
    assert gate["closed_count"] == len(ch8.QUESTION_KEYS)


def test_open_research_gap_blocks_question_closure() -> None:
    payload = _closed_payload()
    payload["research_gaps"].append(
        {
            "Question": "Q47",
            "Manager ID": "",
            "Manager": "",
            "Research Gap": "Need explicit authorization",
            "Materiality": "High",
            "Next Action": "Read disclosure",
            "Status": "Open",
            "Analyst Note": "",
        }
    )
    gate = build_completion_gate(payload, structured_context=_structured_context())
    assert gate["ready_for_chapter_close"] is False
    assert "Q47" in gate["open_questions"]


def test_closed_research_gap_does_not_block() -> None:
    payload = _closed_payload()
    payload["research_gaps"].append(
        {
            "Question": "Q47",
            "Manager ID": "",
            "Manager": "",
            "Research Gap": "Checked explicit authorization",
            "Materiality": "High",
            "Next Action": "",
            "Status": "Resolved",
            "Analyst Note": "",
        }
    )
    gate = build_completion_gate(payload, structured_context=_structured_context())
    assert gate["ready_for_chapter_close"] is True


def test_q43_reports_dimension_coverage_without_scoring() -> None:
    payload = _closed_payload()
    first = payload["q43_employee_relations"][0]
    first["Supporting Evidence"] = "Training policy"
    first["Source"] = "Official annual report"
    gate = build_completion_gate(payload)
    assert gate["q43_dimensions_evidenced"] == 1
    assert gate["q43_dimensions_total"] == 14
    assert "management_score" not in gate


def test_q46_exact_source_lock_and_q47_explicit_semantics() -> None:
    assert tuple(ch8.CAPITAL_ALLOCATION_ACTIONS) == SOURCE_LOCKED_CAPITAL_ALLOCATION_ACTIONS
    payload = _closed_payload()
    gate = build_completion_gate(payload, structured_context=_structured_context())
    assert gate["q46_source_lock_ok"] is True
    assert gate["q47_explicit_buyback_field_available"] is True

    no_explicit = _structured_context()
    no_explicit["q47_buyback_context"] = pd.DataFrame(
        [{"Kỳ": "2025", "Explicit buyback field available?": "No", "Share-count change": -10}]
    )
    gate2 = build_completion_gate(payload, structured_context=no_explicit)
    assert gate2["q47_explicit_buyback_field_available"] is False


def test_manager_and_financial_ssot_are_descriptive_only() -> None:
    gate = build_completion_gate(
        _closed_payload(),
        structured_context=_structured_context(),
        chapter7_payload=_chapter7_payload(),
    )
    assert gate["manager_reference_rows"] == 2
    assert gate["manager_ssot"] == "Chapter 7 manager master"
    assert gate["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert completion_gate_text(gate).startswith("READY")
