from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from modules.deep_company_analysis import chapter7 as ch7
from modules.deep_company_analysis import chapter7_closure as c


def _ready_payload():
    payload = ch7.empty_payload("ABC", "ABC Co")
    payload["question_status"] = {q: "Answered" for q in ch7.QUESTION_KEYS}
    payload["management_profiles"] = [{"Manager ID": "M1", "Manager": "Nguyen Van A", "Analyst Classification": "LT1"}]
    payload["q33"]["analyst_classification"] = "LT1"
    payload["outside_transitions"] = [{"Manager ID": "M1", "Manager": "Nguyen Van A", "Internal / External": "External"}]
    payload["q34"]["applicable"] = "Yes"
    payload["q35"]["overall_classification"] = "Mixed"
    payload["career_timeline"] = [{"Manager ID": "M1", "Manager": "Nguyen Van A", "From": "2018", "To": "2024", "Company": "ABC", "Role": "COO"}]
    payload["compensation_history"] = [{"Year": "2025", "Manager ID": "M1", "Manager": "Nguyen Van A", "Compensation Scope": "Individual", "Performance Metric": "EBIT", "Measurement Horizon": "3Y", "Compensation Consultant": "Unknown", "Guaranteed Component": "No", "Severance (tỷ)": 0}]
    payload["ownership_history"] = [{"As-of Date": "31/12/2025", "Manager ID": "M1", "Manager": "Nguyen Van A", "Actual Shares": 1000000, "Options": 0, "RSU / Restricted": 0, "Unvested Awards": 0, "Ownership Origin": "Open-market purchase"}]
    payload["insider_transactions"] = [{"Transaction Date": "01/06/2026", "Manager ID": "M1", "Insider": "Nguyen Van A", "Transaction": "Buy", "Transaction Type": "Open market", "Registered Shares": 10000, "Executed Shares": 10000, "Ownership Before": 1000000, "Ownership After": 1010000, "Stated Reason": "", "Analyst Materiality": "Low", "Analyst Interpretation": "Context only"}]
    payload["chapter7_final_checklist"] = c.default_final_checklist_rows()
    for row in payload["chapter7_final_checklist"]:
        row["Status"] = "Covered"
    payload["research_gaps_table"] = []
    payload["chapter7_residual_unknowns"] = []
    payload["final_management_classification"] = "LT1"
    payload["analyst_summary"] = "Analyst completed management background review with supporting and counter-evidence considered."
    return payload


def test_source_locked_final_checklist_has_exact_17_items_and_no_score():
    rows = c.default_final_checklist_rows()
    assert len(rows) == 17
    assert [row["ID"] for row in rows] == [f"7K{i:02d}" for i in range(1, 18)]
    text = " ".join(row["Source-Locked Requirement"] for row in rows).lower()
    assert "numerical score" in text
    assert "buy/sell signal" in text


def test_completion_gate_blocks_incomplete_research():
    payload = ch7.empty_payload("ABC")
    result = c.chapter7_completion_status(payload)
    assert result["ready"] is False
    assert result["status"] == "Not Started"
    assert any("Q33" in blocker for blocker in result["blockers"])
    assert "not Management Quality" in result["completion_boundary"]


def test_completion_gate_ready_only_after_source_closure():
    payload = _ready_payload()
    result = c.chapter7_completion_status(payload, open_conflicts=[], open_review_items=[])
    assert result["ready"] is True
    assert result["status"] == "Ready for Analyst Confirmation"
    assert result["blockers"] == []


def test_completion_confirmed_is_not_investment_gate():
    payload = _ready_payload()
    payload["chapter7_complete_confirmed"] = True
    result = c.chapter7_completion_status(payload, open_conflicts=[], open_review_items=[])
    assert result["status"] == "Complete — Analyst Confirmed"
    boundary = result["completion_boundary"].lower()
    assert "research/source completeness" in boundary
    assert "mos" in boundary
    assert "buy/hold/sell" in boundary


def test_new_management_event_forces_review_required_without_overwriting_conclusion():
    payload = _ready_payload()
    payload["chapter7_complete_confirmed"] = True
    before = deepcopy(payload["q33"])
    open_review = [{"id": 99, "status": "Open", "event_type": "CEO appointed", "questions_to_review": "Q33,Q34,Q36"}]
    result = c.chapter7_completion_status(payload, open_conflicts=[], open_review_items=open_review)
    assert result["status"] == "Complete — Review Required"
    assert result["ready"] is False
    assert payload["q33"] == before


def test_accepted_residual_unknown_can_cover_missing_q38_disclosure():
    payload = _ready_payload()
    payload["insider_transactions"] = []
    payload["chapter7_residual_unknowns"] = [{
        "Question": "Q38",
        "Unknown / Gap": "No insider transaction disclosure found after documented search.",
        "Materiality": "Medium",
        "Evidence Attempted": "Exchange + company governance disclosures",
        "Status": "Accepted Residual Unknown",
        "Acceptance Reason": "No disclosure available as of review date",
        "Accepted By Analyst": True,
        "Accepted At": "2026-09-06T05:00:00",
        "Analyst Note": "",
    }]
    result = c.chapter7_completion_status(payload, open_conflicts=[], open_review_items=[])
    assert result["ready"] is True


def test_q35_requires_exact_seven_source_locked_dimensions():
    payload = _ready_payload()
    payload["lion_hyena_matrix"] = payload["lion_hyena_matrix"][:-1]
    result = c.chapter7_completion_status(payload)
    assert result["ready"] is False
    assert any("7 dimensions" in blocker for blocker in result["blockers"])


def test_coverage_is_not_management_quality():
    payload = _ready_payload()
    payload["evidence_matrix"] = [{
        "Question": "Q33",
        "Source Grade": "A — Company/Official disclosure",
        "Direction": "Counter-evidence cue — analyst assess",
        "Claim": "Appointment history",
    }]
    frame = c.source_coverage_matrix(payload, conflicts=[])
    q33 = frame[frame["Question"] == "Q33"].iloc[0]
    assert q33["Coverage"] == "Covered"
    assert "not Management Quality" in q33["Boundary"]


def test_page_support_integrates_phase7d_after_analyst_dossier():
    page = Path(__file__).with_name("chapter7_page_support.py").read_text(encoding="utf-8")
    assert "render_chapter7_final_closure" in page
    assert "Phase 7A+7B+7C+7D" in page
    assert "Final source-closure vẫn thuộc Phase 7D" in page


def test_phase7d_does_not_cross_into_chapter8_q39():
    closure = Path(__file__).with_name("chapter7_closure.py").read_text(encoding="utf-8")
    ui = Path(__file__).with_name("chapter7_closure_ui.py").read_text(encoding="utf-8")
    assert "Q39" not in closure
    assert "Q39" not in ui
