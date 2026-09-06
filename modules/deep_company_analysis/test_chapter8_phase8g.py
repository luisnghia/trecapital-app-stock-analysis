from __future__ import annotations

import inspect

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter8_gap_engine import (
    BOUNDARY,
    QUESTION_DIMENSIONS,
    build_dimension_coverage,
    build_question_coverage_summary,
    enhanced_research_gaps,
    validate_source_locks,
)
import modules.deep_company_analysis.chapter8_research_v52 as v52


def _candidate(question: str, text: str, *, manager_id: str = "", manager: str = "", grade: str = "A — Company/Official disclosure") -> dict:
    return {
        "Question": question,
        "Manager ID": manager_id,
        "Manager": manager,
        "Subtopic": "",
        "Source Title": "Official disclosure",
        "Evidence Text / Reference": text,
        "Source Grade": grade,
    }


def _manager_reference() -> pd.DataFrame:
    return pd.DataFrame([
        {"Manager ID": "MGR-001", "Manager": "Nguyen Van A", "Role": "CEO", "Source": "Chapter 7"},
        {"Manager ID": "MGR-002", "Manager": "Tran Thi B", "Role": "CFO", "Source": "Chapter 7"},
    ])


def test_q43_uses_all_fourteen_source_locked_shearn_dimensions_exactly():
    locks = validate_source_locks()
    expected_keys = tuple(key for key, _ in ch8.EMPLOYEE_RELATION_DIMENSIONS)
    expected_labels = tuple(label for _, label in ch8.EMPLOYEE_RELATION_DIMENSIONS)
    actual = QUESTION_DIMENSIONS["Q43"]
    assert locks["q43_dimension_count"] == 14
    assert tuple(x.key for x in actual) == expected_keys
    assert tuple(x.label for x in actual) == expected_labels
    assert all(x.source_locked for x in actual)


def test_q46_has_exactly_five_source_locked_actions_and_context_is_not_sixth_bucket():
    locks = validate_source_locks()
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert len(locks["q46_context_dimensions"]) == 1
    assert "context" in locks["q46_context_dimensions"][0].lower()
    assert "debt" not in " ".join(locks["q46_source_locked_actions"]).lower()


def test_q47_share_count_decline_does_not_create_buyback_coverage():
    candidates = pd.DataFrame([
        _candidate("Q47", "Shares outstanding declined from 400 million to 380 million shares during the year."),
    ])
    coverage = build_dimension_coverage(candidates)
    q47 = coverage[(coverage["Question"] == "Q47") & (coverage["Source Locked"] == "Yes")]
    assert int(q47["Candidates"].sum()) == 0
    assert q47["Coverage Status"].str.startswith("Open").all()
    assert validate_source_locks()["q47_share_count_is_proof"] is False


def test_many_candidates_in_one_q43_dimension_do_not_hide_other_dimension_gaps():
    candidates = pd.DataFrame([
        _candidate("Q43", f"The company continued tuyển dụng and thu hút ứng viên in campaign {i}.")
        for i in range(30)
    ])
    summary = build_question_coverage_summary(candidates)
    q43 = summary[summary["Question"] == "Q43"].iloc[0]
    assert q43["Dimensions Required"] == 14
    assert q43["Dimensions Covered"] == 1
    assert q43["Dimensions Open"] == 13
    assert q43["Status"] == "Open — dimension coverage gaps"

    gaps = enhanced_research_gaps(candidates)
    q43_subtopic_gaps = gaps[(gaps["Question"] == "Q43") & gaps["Status"].astype(str).str.contains("subtopic")]
    assert len(q43_subtopic_gaps) >= 13


def test_many_dividend_candidates_do_not_make_q46_five_action_coverage_complete():
    candidates = pd.DataFrame([
        _candidate("Q46", f"The AGM approved cash dividend distribution for year {2020 + i % 6}.")
        for i in range(36)
    ])
    summary = build_question_coverage_summary(candidates, _manager_reference())
    q46 = summary[summary["Question"] == "Q46"].iloc[0]
    assert q46["Dimensions Required"] == 5
    assert q46["Dimensions Covered"] == 1
    assert q46["Dimensions Open"] == 4


def test_manager_scoped_questions_keep_identity_gap_when_chapter7_master_missing():
    candidates = pd.DataFrame([
        _candidate("Q41", "The company issued profit guidance for 2026."),
        _candidate("Q44", "The company described recruitment and succession plans."),
        _candidate("Q46", "The company approved a dividend."),
        _candidate("Q47", "The board approved a repurchase program."),
    ])
    gaps = enhanced_research_gaps(candidates, pd.DataFrame())
    manager_gaps = gaps[gaps["Status"] == "Open — manager identity gap"]
    assert set(manager_gaps["Question"]) == {"Q41", "Q44", "Q46", "Q47"}
    assert manager_gaps["Next Action"].str.contains("do not create replacement manager IDs", case=False).all()


def test_existing_chapter7_master_still_requires_manager_scoped_candidate_mapping():
    candidates = pd.DataFrame([
        _candidate("Q46", "The company approved a dividend but the disclosure excerpt does not name the CEO or CFO."),
    ])
    gaps = enhanced_research_gaps(candidates, _manager_reference())
    scoped = gaps[(gaps["Question"] == "Q46") & (gaps["Status"] == "Open — manager-scoped evidence gap")]
    assert len(scoped) == 1
    assert "confirmed Chapter 7 manager" in scoped.iloc[0]["Research Gap"]


def test_manager_scoped_candidate_uses_existing_manager_id_and_closes_only_scope_gap():
    candidates = pd.DataFrame([
        _candidate(
            "Q46",
            "CEO Nguyen Van A discussed dividend discipline and capital allocation.",
            manager_id="MGR-001",
            manager="Nguyen Van A",
        ),
    ])
    gaps = enhanced_research_gaps(candidates, _manager_reference())
    scoped = gaps[(gaps["Question"] == "Q46") & gaps["Status"].astype(str).str.contains("manager")]
    assert scoped.empty
    # Subtopic gaps remain because a named dividend candidate is not five-action coverage.
    assert ((gaps["Question"] == "Q46") & gaps["Status"].astype(str).str.contains("subtopic")).any()


def test_secondary_only_dimension_is_source_quality_gap_not_coverage_success():
    candidates = pd.DataFrame([
        _candidate("Q39", "Customers are a strategic priority.", grade="C — Secondary/context source"),
    ])
    coverage = build_dimension_coverage(candidates)
    customers = coverage[(coverage["Question"] == "Q39") & (coverage["Dimension Key"] == "customers")].iloc[0]
    assert customers["Candidates"] == 1
    assert customers["A — Official"] == 0
    assert customers["Coverage Status"] == "Open — subtopic source-quality gap"


def test_v52_boundary_is_coverage_only_without_management_score_or_investment_signal():
    source = inspect.getsource(v52).casefold() + inspect.getsource(build_dimension_coverage).casefold()
    assert "not a management score" in BOUNDARY.casefold()
    assert "buy/hold/sell" not in source
    assert "automatic_management_score" not in source
    assert "investment signal" not in source
    assert "percentage" not in source


def test_question_summary_reports_counts_not_a_numeric_score():
    candidates = pd.DataFrame([_candidate("Q39", "Customers and shareholders are discussed in the annual report.")])
    summary = build_question_coverage_summary(candidates)
    assert "Score" not in summary.columns
    assert "Coverage %" not in summary.columns
    assert {"Dimensions Required", "Dimensions Covered", "Dimensions Open"}.issubset(summary.columns)
    assert summary["Boundary"].str.contains("not a management score").all()
