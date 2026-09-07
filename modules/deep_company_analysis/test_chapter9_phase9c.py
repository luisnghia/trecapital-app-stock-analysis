from __future__ import annotations

from pathlib import Path

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_source_contract_v63 as v63
import modules.deep_company_analysis.chapter9_workspace_v64 as ws
import modules.deep_company_analysis.chapter9_completion_v64 as completion


def _chapter7_payload() -> dict:
    return {
        "management_profiles": [
            {"Manager ID": "M001", "Manager": "Nguyen Van A", "Current Role": "CEO"},
            {"Manager ID": "M002", "Manager": "Tran Thi B", "Current Role": "CFO"},
        ]
    }


def test_phase9c_default_workspace_has_exact_26_unknown_first_dimensions() -> None:
    payload = ws.empty_workspace_payload("DGC", "Duc Giang Chemicals")
    rows = payload["dimension_evidence"]
    assert len(rows) == 26
    assert [row["Dimension Key"] for row in rows] == [dim.key for dim in v63.all_dimensions()]
    assert all(row["Evidence Status"] == "Open — analyst research required" for row in rows)
    assert all(row["Supporting Evidence"] == "" for row in rows)
    assert all(row["Counter-Evidence"] == "" for row in rows)


def test_normalization_preserves_analyst_fields_but_relocks_source_fields() -> None:
    payload = ws.empty_workspace_payload("DGC")
    row = payload["dimension_evidence"][0]
    row["Question"] = "Q52"
    row["Dimension"] = "tampered"
    row["Supporting Evidence"] = "analyst evidence"
    row["Evidence Status"] = "Partial — analyst review"
    normalized = ws.normalize_workspace_payload(payload)
    first = normalized["dimension_evidence"][0]
    assert first["Question"] == "Q48"
    assert first["Dimension"] == ch9.Q48_PASSION_RESEARCH_PROMPTS[0]
    assert first["Supporting Evidence"] == "analyst evidence"
    assert first["Evidence Status"] == "Partial — analyst review"


def test_apply_dimension_edits_never_allows_contract_fields_to_be_overwritten() -> None:
    payload = ws.empty_workspace_payload("DGC")
    key = payload["dimension_evidence"][0]["Dimension Key"]
    edited, applied, rejected = ws.apply_dimension_edits(
        payload,
        [{
            "Dimension Key": key,
            "Question": "Q52",
            "Dimension": "invented dimension",
            "Source Origin": "invented",
            "Source Pages": "999",
            "Supporting Evidence": "verified text",
            "Evidence Status": "Closed — analyst verified",
        }],
    )
    row = edited["dimension_evidence"][0]
    assert applied == 1 and rejected == []
    assert row["Question"] == "Q48"
    assert row["Dimension"] == ch9.Q48_PASSION_RESEARCH_PROMPTS[0]
    assert row["Source Origin"] == v63.ORIGIN_EXPLICIT_PROMPT
    assert row["Source Pages"] == "257"
    assert row["Supporting Evidence"] == "verified text"


def test_manager_id_must_come_from_chapter7_when_reference_is_supplied() -> None:
    payload = ws.empty_workspace_payload("DGC")
    key = payload["dimension_evidence"][0]["Dimension Key"]
    _, applied, rejected = ws.apply_dimension_edits(
        payload,
        [{"Dimension Key": key, "Manager ID": "FAKE", "Manager": "Invented"}],
        chapter7_payload=_chapter7_payload(),
    )
    assert applied == 0
    assert rejected and "Chapter 7 manager master" in rejected[0]


def test_confirmed_chapter7_manager_link_is_accepted_but_name_mismatch_is_rejected() -> None:
    payload = ws.empty_workspace_payload("DGC")
    key = payload["dimension_evidence"][0]["Dimension Key"]
    linked, applied, rejected = ws.apply_dimension_edits(
        payload,
        [{"Dimension Key": key, "Manager ID": "M001", "Manager": "Nguyen Van A"}],
        chapter7_payload=_chapter7_payload(),
    )
    assert applied == 1 and rejected == []
    assert linked["dimension_evidence"][0]["Manager ID"] == "M001"

    _, applied2, rejected2 = ws.apply_dimension_edits(
        payload,
        [{"Dimension Key": key, "Manager ID": "M001", "Manager": "Wrong Person"}],
        chapter7_payload=_chapter7_payload(),
    )
    assert applied2 == 0
    assert rejected2 and "does not match" in rejected2[0]


def test_open_dimension_gap_projection_is_pure_and_tracks_closure() -> None:
    payload = ws.empty_workspace_payload("DGC")
    before = ws.build_open_dimension_gaps(payload)
    assert len(before) == 26
    key = payload["dimension_evidence"][0]["Dimension Key"]
    updated, _, _ = ws.apply_dimension_edits(
        payload,
        [{"Dimension Key": key, "Evidence Status": "Closed — analyst verified", "Supporting Evidence": "source text"}],
    )
    after = ws.build_open_dimension_gaps(updated)
    assert len(after) == 25
    assert payload["dimension_evidence"][0]["Evidence Status"] == "Open — analyst research required"


def test_completion_gate_stays_open_until_all_dimensions_for_question_are_explicitly_closed() -> None:
    payload = ws.empty_workspace_payload("DGC")
    payload["question_status"]["Q48"] = "Answered"
    payload["analyst_assessment"]["Q48"] = "Analyst conclusion"
    first_key = v63.QUESTION_DIMENSIONS["Q48"][0].key
    payload, _, _ = ws.apply_dimension_edits(
        payload,
        [{"Dimension Key": first_key, "Evidence Status": "Closed — analyst verified", "Supporting Evidence": "source text"}],
    )
    table = completion.build_source_closure_table(payload)
    q48 = table.loc[table["Question"].eq("Q48")].iloc[0]
    assert q48["Completion State"] == "Open"
    assert q48["Open Dimensions"] == 5


def test_all_na_requires_explicit_dimension_closure_and_can_close_research_without_scoring() -> None:
    payload = ws.empty_workspace_payload("DGC")
    edits = [
        {"Dimension Key": dim.key, "Evidence Status": "N/A — analyst verified", "Analyst Note": "Analyst marked N/A"}
        for dim in v63.all_dimensions()
    ]
    payload, applied, rejected = ws.apply_dimension_edits(payload, edits)
    assert applied == 26 and rejected == []
    for q in ch9.QUESTION_KEYS:
        payload["question_status"][q] = "N/A"
    gate = completion.build_completion_gate(payload)
    assert gate["ready_for_chapter_close"] is True
    assert gate["closed_count"] == 5
    assert gate["automatic_management_score"] is False
    assert gate["automatic_investment_signal"] is False
    assert "not a management-quality rating" in completion.completion_gate_text(gate)


def test_open_research_gap_blocks_an_otherwise_closed_question() -> None:
    payload = ws.empty_workspace_payload("DGC")
    q48_edits = [
        {
            "Dimension Key": dim.key,
            "Evidence Status": "Closed — analyst verified",
            "Supporting Evidence": "verified evidence",
        }
        for dim in v63.QUESTION_DIMENSIONS["Q48"]
    ]
    payload, _, _ = ws.apply_dimension_edits(payload, q48_edits)
    payload["question_status"]["Q48"] = "Answered"
    payload["analyst_assessment"]["Q48"] = "Analyst conclusion"
    payload["research_gaps"] = [{
        "Question": "Q48", "Manager ID": "", "Manager": "", "Research Gap": "Follow-up source",
        "Materiality": "High", "Next Action": "Research", "Status": "Open", "Analyst Note": "",
    }]
    q48 = completion.build_source_closure_table(payload).loc[lambda x: x["Question"].eq("Q48")].iloc[0]
    assert q48["Completion State"] == "Open"
    assert q48["Open Research Gaps"] == 1


def test_workspace_has_no_ui_db_web_financial_bridge_or_investment_logic() -> None:
    for module in (ws, completion):
        source = Path(module.__file__).read_text(encoding="utf-8").casefold()
        for forbidden_import in (
            "import streamlit",
            "from streamlit",
            "import httpx",
            "import requests",
            "import psycopg",
            "import sqlite3",
            "fireant",
            "simplize",
            "vietstock",
        ):
            assert forbidden_import not in source
    snapshot = ws.workspace_snapshot(ws.empty_workspace_payload("DGC"))
    assert snapshot["total_dimensions"] == 26
    assert snapshot["manager_identity_ssot"] == "Chapter 7 manager master"
    assert snapshot["automatic_management_score"] is False
    assert snapshot["automatic_investment_signal"] is False
