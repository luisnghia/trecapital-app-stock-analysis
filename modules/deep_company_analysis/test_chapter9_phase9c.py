from __future__ import annotations

import inspect
from copy import deepcopy

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_data_bridge as bridge
import modules.deep_company_analysis.chapter9_source_contract_v63 as v63


def _chapter7_payload() -> dict:
    return {
        "ticker": "DGC",
        "management_profiles": [
            {
                "Manager ID": "M001",
                "Manager": "Nguyễn Văn A",
                "Current Role": "Tổng Giám đốc / CEO",
                "Analyst Classification": "Unknown",
                "Confidence": "High",
            },
            {
                "Manager ID": "M002",
                "Manager": "Trần Văn B",
                "Current Role": "CFO",
                "Analyst Classification": "Unknown",
                "Confidence": "Medium",
            },
        ],
    }


def test_phase9c_preserves_source_contract_and_analyst_boundary():
    assert len(v63.all_dimensions()) == 26
    assert bridge.MANAGER_SOURCE_LABEL == ch9.MANAGER_IDENTITY_SSOT == "Chapter 7 manager master"
    assert "analyst research and judgment required" in bridge.RESEARCH_BOUNDARY
    src = inspect.getsource(bridge).casefold()
    assert "no management score" in src
    assert "no automatic character conclusion" in src
    assert "no buy/hold/sell" in src
    assert "analyst_assessment" not in src
    assert "import httpx" not in src
    assert "import streamlit" not in src


def test_manager_reference_uses_chapter7_ids_and_never_creates_replacement_ids():
    reference = bridge.chapter7_manager_reference(_chapter7_payload())
    assert list(reference["Manager ID"]) == ["M001", "M002"]
    assert list(reference["Manager"]) == ["Nguyễn Văn A", "Trần Văn B"]
    assert set(reference["Source"]) == {"Chapter 7 manager master"}


def test_ceo_specific_q48_q52_scope_only_to_explicit_chapter7_ceo():
    scope = bridge.build_dimension_scope(_chapter7_payload())
    for question in bridge.CEO_QUESTIONS:
        sub = scope[scope["Question"].eq(question)]
        assert not sub.empty
        assert set(sub["Manager ID"]) == {"M001"}
        assert set(sub["Manager"]) == {"Nguyễn Văn A"}
        assert set(sub["Scope Status"]) == {"Scoped — explicit Chapter 7 CEO role"}

    # Every Phase 9B dimension remains represented after manager scoping.
    assert scope["Dimension Key"].nunique() == 26


def test_q49_q51_reference_known_chapter7_managers_without_judging_materiality():
    scope = bridge.build_dimension_scope(_chapter7_payload())
    for question in bridge.MANAGEMENT_QUESTIONS:
        sub = scope[scope["Question"].eq(question)]
        assert set(sub["Manager ID"]) == {"M001", "M002"}
        assert set(sub["Scope Status"]) == {"Scoped — Chapter 7 manager reference"}
        assert set(sub["Evidence Status"]) == {"Open — analyst research required"}
        assert set(sub["Supporting Evidence"]) == {""}
        assert set(sub["Counter-Evidence"]) == {""}


def test_deputy_ceo_is_not_silently_promoted_to_ceo_scope():
    payload = {
        "management_profiles": [
            {
                "Manager ID": "M009",
                "Manager": "Phạm Văn C",
                "Current Role": "Phó Tổng Giám đốc / Deputy CEO",
                "Confidence": "High",
            }
        ]
    }
    scope = bridge.build_dimension_scope(payload)
    q48_q52 = scope[scope["Question"].isin(bridge.CEO_QUESTIONS)]
    assert set(q48_q52["Manager ID"]) == {""}
    assert set(q48_q52["Scope Status"]) == {"Open — CEO identity/role gap"}
    gaps = bridge.build_scope_gaps(payload)
    assert set(gaps["Question"]) == set(bridge.CEO_QUESTIONS)
    assert set(gaps["Status"]) == {"Open — CEO identity/role gap"}


def test_missing_chapter7_manager_master_keeps_all_26_dimensions_unknown_and_unassigned():
    scope = bridge.build_dimension_scope({})
    assert len(scope) == 26
    assert scope["Dimension Key"].nunique() == 26
    assert set(scope["Manager ID"]) == {""}
    assert set(scope["Manager"]) == {""}
    assert set(scope["Evidence Status"]) == {"Open — analyst research required"}
    assert all(status.startswith("Open —") for status in set(scope["Scope Status"]))

    gaps = bridge.build_scope_gaps({})
    assert set(gaps["Question"]) == set(ch9.QUESTION_KEYS)
    assert set(gaps["Status"]) == {"Open — manager identity gap"}
    text = " ".join(gaps["Next Action"].astype(str)).casefold()
    assert "do not create replacement manager ids" in text


def test_context_bundle_never_mutates_chapter7_payload():
    payload = _chapter7_payload()
    before = deepcopy(payload)
    result = bridge.build_context(payload)
    assert payload == before
    assert isinstance(result.manager_reference, pd.DataFrame)
    assert isinstance(result.dimension_scope, pd.DataFrame)
    assert isinstance(result.gaps, pd.DataFrame)
    assert "Analyst judgment remains required" in result.note


def test_context_snapshot_is_coverage_only_not_management_or_investment_score():
    snap = bridge.context_snapshot(_chapter7_payload())
    assert snap["question_keys"] == list(ch9.QUESTION_KEYS)
    assert snap["source_dimension_count"] == 26
    assert snap["scoped_unique_dimension_count"] == 26
    assert snap["manager_reference_count"] == 2
    assert snap["automatic_management_score"] is False
    assert snap["automatic_investment_signal"] is False
    assert snap["web_research_added"] is False
    assert snap["financial_bridge_added"] is False
