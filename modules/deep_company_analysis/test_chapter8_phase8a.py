from __future__ import annotations

import modules.deep_company_analysis.chapter8 as ch8


EXPECTED_TITLES = {
    "Q39": "Does the CEO manage the business to benefit all stakeholders?",
    "Q40": "Does the management team improve its operations day-to-day or does it use a strategic plan to conduct its business?",
    "Q41": "Do the CEO and CFO issue guidance regarding earnings?",
    "Q42": "Is the business managed in a centralized or decentralized way?",
    "Q43": "Does management value its employees?",
    "Q44": "Does the management team know how to hire well?",
    "Q45": "Does the management team focus on cutting unnecessary costs?",
    "Q46": "Are the CEO and CFO disciplined in making capital allocation decisions?",
    "Q47": "Do the CEO and CFO buy back stock opportunistically?",
}

EXPECTED_EMPLOYEE_DIMENSIONS = [
    "Does management treat its employees as assets or liabilities?",
    "Does management talk about the contributions of their employees?",
    "Does management believe that retaining employees is critical?",
    "Does the business promote from within?",
    "Does management show employees how they can get promoted?",
    "Does the business invest significant resources in employee training?",
    "Does the business attract a great number of applicants?",
    "Are employees avidly recruited from the business?",
    "Are there large differences between the benefits that the top managers receive versus employees?",
    "Does management treat employees with respect when they lay them off?",
    "Does management listen to its employees?",
    "Does the business have a strong culture?",
    "Does the business have identifiable, shared values?",
    "What is the employee-retention rate?",
]


def test_q39_to_q47_exact_questions_are_source_locked():
    assert ch8.QUESTION_KEYS == ("Q39", "Q40", "Q41", "Q42", "Q43", "Q44", "Q45", "Q46", "Q47")
    assert ch8.QUESTION_TITLES == EXPECTED_TITLES
    payload = ch8.empty_payload("dgc")
    assert payload["ticker"] == "DGC"
    assert list(payload["question_status"]) == list(ch8.QUESTION_KEYS)
    assert set(payload["question_status"].values()) == {"Unknown"}
    assert set(payload["confidence"].values()) == {"Unknown"}
    assert set(payload["analyst_assessment"].values()) == {"Unknown"}


def test_q43_preserves_exact_fourteen_employee_prompts_without_scoring():
    assert len(ch8.EMPLOYEE_RELATION_DIMENSIONS) == 14
    assert [label for _, label in ch8.EMPLOYEE_RELATION_DIMENSIONS] == EXPECTED_EMPLOYEE_DIMENSIONS
    rows = ch8.default_employee_relation_rows()
    assert len(rows) == 14
    assert [row["Dimension"] for row in rows] == EXPECTED_EMPLOYEE_DIMENSIONS
    assert all(row["Evidence Direction"] == "Unknown" for row in rows)
    assert all("score" not in str(key).lower() for row in rows for key in row)


def test_q46_preserves_shearn_exact_five_capital_allocation_actions():
    assert ch8.CAPITAL_ALLOCATION_ACTIONS == (
        "Reinvest in business / new projects",
        "Hold cash",
        "Pay dividends",
        "Buy back stock",
        "Make acquisitions",
    )
    assert len(ch8.CAPITAL_ALLOCATION_ACTIONS) == 5
    assert not any("debt" in action.lower() for action in ch8.CAPITAL_ALLOCATION_ACTIONS)


def test_q41_guidance_history_keeps_target_actual_revision_and_does_not_infer_fraud():
    cols = set(ch8.GUIDANCE_HISTORY_COLUMNS)
    assert {"Issued Date", "Metric", "Horizon", "Guidance Low", "Guidance High", "Guidance Point", "Guidance Event", "Actual", "Outcome", "Source"} <= cols
    assert ch8.GUIDANCE_OUTCOME_OPTIONS == ("Unknown", "Beat", "Meet", "Miss", "N/A")
    assert "Revised" in ch8.GUIDANCE_EVENT_OPTIONS
    assert "Withdrawn" in ch8.GUIDANCE_EVENT_OPTIONS
    joined = " ".join(ch8.GUIDANCE_HISTORY_COLUMNS).lower()
    assert "fraud" not in joined
    assert "manipulation" not in joined


def test_q42_structure_is_descriptive_and_unknown_first():
    assert ch8.ORG_STRUCTURE_OPTIONS == ("Unknown", "Centralized", "Mixed", "Decentralized")
    payload = ch8.empty_payload("VCB")
    assert payload["q42_analyst_structure"] == "Unknown"
    assert payload["q42_organization_structure"] == []
    cols = set(ch8.ORG_STRUCTURE_COLUMNS)
    assert {"Decision Owner", "Central / Local", "Autonomy Evidence", "Escalation / Control Evidence", "Customer-Proximity Evidence"} <= cols


def test_q45_q47_schema_preserves_context_instead_of_auto_positive_signal():
    cost_cols = set(ch8.COST_ACTION_COLUMNS)
    assert {"Waste / Non-core", "Customer Impact", "Employee Impact", "Core Investment Preserved", "Restructuring / One-off"} <= cost_cols

    buyback_cols = set(ch8.BUYBACK_HISTORY_COLUMNS)
    assert {"Shares Repurchased", "Average Price", "Cash Spent (tỷ)", "Share Count Before", "Share Count After", "Dilution Offset?", "Valuation Context", "Liquidity / Cash Context"} <= buyback_cols

    all_columns = (
        ch8.STAKEHOLDER_EVIDENCE_COLUMNS
        + ch8.OPERATING_APPROACH_COLUMNS
        + ch8.GUIDANCE_HISTORY_COLUMNS
        + ch8.ORG_STRUCTURE_COLUMNS
        + ch8.EMPLOYEE_RELATION_COLUMNS
        + ch8.HIRING_EVIDENCE_COLUMNS
        + ch8.COST_ACTION_COLUMNS
        + ch8.CAPITAL_ALLOCATION_COLUMNS
        + ch8.BUYBACK_HISTORY_COLUMNS
        + ch8.EVIDENCE_COLUMNS
        + ch8.RESEARCH_GAP_COLUMNS
        + ch8.MANAGEMENT_EVENT_COLUMNS
    )
    joined = " ".join(all_columns).lower()
    for forbidden in ("competence score", "weighted score", "buy signal", "sell signal", "research gate", "mos"):
        assert forbidden not in joined


def test_phase8a_has_no_fake_ttm_in_qualitative_event_schemas():
    all_columns = (
        ch8.STAKEHOLDER_EVIDENCE_COLUMNS
        + ch8.OPERATING_APPROACH_COLUMNS
        + ch8.GUIDANCE_HISTORY_COLUMNS
        + ch8.ORG_STRUCTURE_COLUMNS
        + ch8.EMPLOYEE_RELATION_COLUMNS
        + ch8.HIRING_EVIDENCE_COLUMNS
        + ch8.COST_ACTION_COLUMNS
        + ch8.CAPITAL_ALLOCATION_COLUMNS
        + ch8.BUYBACK_HISTORY_COLUMNS
        + ch8.MANAGEMENT_EVENT_COLUMNS
    )
    text = " ".join(all_columns).upper()
    assert "TTM" not in text
    assert "T12M" not in text
    assert "Issued Date" in ch8.GUIDANCE_HISTORY_COLUMNS
    assert "Metric Period / As-of" in ch8.EMPLOYEE_RELATION_COLUMNS
    assert "Period / Date" in ch8.BUYBACK_HISTORY_COLUMNS


def test_research_gap_warnings_check_evidence_completion_not_management_quality():
    payload = ch8.empty_payload("HPG")
    warnings = ch8.research_gap_warnings(payload)
    assert len(warnings) == 9
    assert all("analyst review required" in warning for warning in warnings)

    payload["question_status"]["Q43"] = "Answered"
    payload["question_status"]["Q46"] = "Answered"
    payload["question_status"]["Q47"] = "Answered"
    warnings = ch8.research_gap_warnings(payload)
    assert any("Q43" in warning and "no source" in warning for warning in warnings)
    assert any("Q46" in warning and "no capital-allocation history" in warning for warning in warnings)
    assert any("Q47" in warning and "no buyback history" in warning for warning in warnings)
    joined = " ".join(warnings).lower()
    assert "good management" not in joined
    assert "bad management" not in joined
    assert "buy" not in joined.replace("buyback", "")
    assert "sell" not in joined
