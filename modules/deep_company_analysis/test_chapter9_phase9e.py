from __future__ import annotations

from copy import deepcopy
import inspect

import pandas as pd

import modules.deep_company_analysis.chapter9 as ch9
import modules.deep_company_analysis.chapter9_research as research
import modules.deep_company_analysis.chapter9_store as store
import modules.deep_company_analysis.chapter9_workspace as ws


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


def _candidate(
    *,
    question: str = "Q48",
    dimension_key: str = "q48_lifelong_learning",
    manager_id: str = "M001",
    manager: str = "Nguyễn Văn A",
    select: bool = True,
) -> dict:
    row = {column: "" for column in research.CANDIDATE_COLUMNS}
    row.update(
        {
            "Select": select,
            "Candidate ID": f"cand-{question}-{dimension_key}-{manager_id or 'none'}",
            "Question": question,
            "Dimension Key": dimension_key,
            "Dimension": "Source-locked dimension",
            "Manager ID": manager_id,
            "Manager": manager,
            "Current Role": "Tổng Giám đốc / CEO" if manager_id == "M001" else "CFO",
            "Source Family": "Published manager interview/profile",
            "Direction": "Supporting cue — analyst assess",
            "Source Grade": "A — Company/Official disclosure",
            "Explicitness": "Extracted original source text — analyst verify context",
            "Source Title": "Annual report interview",
            "Source URL / File": "https://example.com/annual-report",
            "Source Date": "2026-04-01",
            "As-of Date": "2026",
            "Evidence Text / Reference": "The CEO described continuous improvement and learning practices.",
            "Source Method": "Phase 9D official/document extraction",
            "Data Origin": "Direct source text — analyst verification required",
            "Status": "Candidate — analyst verify",
        }
    )
    return row


def test_selected_candidate_promotes_without_overwriting_analyst_fields_or_candidate_input() -> None:
    payload = ch9.empty_payload("DGC", "Duc Giang Chemicals")
    payload["analyst_assessment"]["Q48"] = "Existing analyst view"
    payload["question_status"]["Q48"] = "Partial"
    payload["confidence"]["Q48"] = "High"
    candidate = _candidate()
    before = deepcopy(candidate)

    out, added = ws.promote_selected_candidates(
        payload, pd.DataFrame([candidate]), chapter7_payload=_chapter7_payload()
    )

    assert added == 1
    assert candidate == before
    assert out["analyst_assessment"]["Q48"] == "Existing analyst view"
    assert out["question_status"]["Q48"] == "Partial"
    assert out["confidence"]["Q48"] == "High"
    evidence = out["evidence"][0]
    assert evidence["Status"] == "Promoted — analyst verified"
    assert evidence["Candidate ID"] == candidate["Candidate ID"]
    assert evidence["Dimension Key"] == "q48_lifelong_learning"
    assert evidence["Source URL / File"] == candidate["Source URL / File"]
    assert evidence["Research Direction Cue"] == candidate["Direction"]


def test_unselected_and_duplicate_candidates_are_not_promoted_twice() -> None:
    payload = ch9.empty_payload("DGC")
    selected = _candidate()
    unselected = _candidate(select=False)
    out, added = ws.promote_selected_candidates(
        payload, [selected, selected, unselected], chapter7_payload=_chapter7_payload()
    )
    assert added == 1
    out2, added2 = ws.promote_selected_candidates(
        out, [selected], chapter7_payload=_chapter7_payload()
    )
    assert added2 == 0
    assert len(out2["evidence"]) == 1


def test_q48_q52_require_exact_chapter7_ceo_link_before_promotion() -> None:
    payload = ch9.empty_payload("DGC")
    no_manager = _candidate(manager_id="", manager="")
    wrong_manager = _candidate(manager_id="M002", manager="Trần Văn B")
    valid, reason = ws.validate_candidate_for_promotion(no_manager, _chapter7_payload())
    assert valid is False and "CEO-specific" in reason
    valid, reason = ws.validate_candidate_for_promotion(wrong_manager, _chapter7_payload())
    assert valid is False and "explicitly scoped Chapter 7 CEO" in reason
    out, added = ws.promote_selected_candidates(
        payload, [no_manager, wrong_manager], chapter7_payload=_chapter7_payload()
    )
    assert added == 0
    assert out["evidence"] == []


def test_q49_q51_allow_management_wide_unassigned_evidence_but_never_unknown_manager_id() -> None:
    management_wide = _candidate(
        question="Q50",
        dimension_key="q50_shareholder_letters",
        manager_id="",
        manager="",
    )
    valid, _ = ws.validate_candidate_for_promotion(management_wide, _chapter7_payload())
    assert valid is True

    invented = dict(management_wide)
    invented["Manager ID"] = "M999"
    invented["Manager"] = "Invented Manager"
    valid, reason = ws.validate_candidate_for_promotion(invented, _chapter7_payload())
    assert valid is False
    assert "Chapter 7 manager master" in reason


def test_wrong_dimension_question_pair_is_rejected_without_adding_new_criteria() -> None:
    candidate = _candidate(question="Q49", dimension_key="q48_lifelong_learning")
    valid, reason = ws.validate_candidate_for_promotion(candidate, _chapter7_payload())
    assert valid is False
    assert "source-locked question" in reason


def test_financing_context_keeps_exception_cue_as_neutral_workspace_evidence() -> None:
    row = _candidate(question="Q52", dimension_key="q52_financing_context")
    row["Direction"] = "Context / exception cue — analyst assess"
    row["Evidence Text / Reference"] = "Investor roadshow accompanied a bond issuance for acquisition financing."
    mapped = ws.candidate_to_evidence(row)
    assert mapped["Direction"] == "Neutral"
    assert mapped["Research Direction Cue"] == "Context / exception cue — analyst assess"
    assert "Counter" not in mapped["Direction"]


def test_research_gap_merge_is_dimension_level_and_preserves_analyst_note() -> None:
    payload = ch9.empty_payload("DGC")
    existing = {
        "Question": "Q50",
        "Dimension Key": "q50_shareholder_letters",
        "Manager ID": "",
        "Manager": "",
        "Research Gap": "Need a sequence of shareholder letters.",
        "Materiality": "Analyst decide",
        "Next Action": "Collect historical letters.",
        "Status": "Open — evidence gap",
        "Analyst Note": "Keep this analyst note",
    }
    payload["research_gaps"] = [existing.copy()]
    incoming = pd.DataFrame(
        [
            existing.copy(),
            {
                **existing,
                "Dimension Key": "q50_conference_calls",
                "Research Gap": "Need historical conference-call transcripts.",
                "Analyst Note": "",
            },
        ]
    )
    out, added = ws.merge_research_gaps(payload, incoming)
    assert added == 1
    first = [x for x in out["research_gaps"] if x["Dimension Key"] == "q50_shareholder_letters"][0]
    assert first["Analyst Note"] == "Keep this analyst note"


def test_store_roundtrip_and_snapshot_preserve_promoted_evidence_lineage(tmp_path) -> None:
    original = store.DB_PATH
    try:
        store.DB_PATH = tmp_path / "chapter9_test.db"
        payload = ch9.empty_payload("DGC", "Duc Giang Chemicals")
        payload, added = ws.promote_selected_candidates(
            payload, [_candidate()], chapter7_payload=_chapter7_payload()
        )
        assert added == 1
        payload["analyst_assessment"]["Q48"] = "Analyst-owned conclusion"
        payload["question_status"]["Q48"] = "Partial"

        saved = store.save_record("DGC", payload, "Duc Giang Chemicals")
        loaded = store.load_record("DGC")
        assert loaded["analyst_assessment"]["Q48"] == "Analyst-owned conclusion"
        assert loaded["evidence"][0]["Candidate ID"] == saved["evidence"][0]["Candidate ID"]
        assert loaded["evidence"][0]["Dimension Key"] == "q48_lifelong_learning"

        snapshot_id = store.create_snapshot("DGC", loaded)
        assert snapshot_id >= 1
        snapshots = store.list_snapshots("DGC")
        assert snapshots and snapshots[0]["id"] == snapshot_id
        snap_payload = store.load_snapshot(snapshot_id)
        assert snap_payload is not None
        assert snap_payload["evidence"][0]["Candidate ID"] == loaded["evidence"][0]["Candidate ID"]
    finally:
        store.DB_PATH = original


def test_workspace_snapshot_is_research_completeness_only() -> None:
    payload = ch9.empty_payload("DGC")
    payload["question_status"]["Q48"] = "Answered"
    payload["question_status"]["Q49"] = "Partial"
    snap = ws.workspace_snapshot(payload)
    assert snap["question_count"] == 5
    assert snap["source_dimension_count"] == 26
    assert snap["answered"] == 1
    assert snap["partial"] == 1
    assert snap["automatic_management_score"] is False
    assert snap["automatic_character_classification"] is False
    assert snap["automatic_investment_signal"] is False


def test_workspace_layer_has_no_streamlit_or_automatic_investment_logic() -> None:
    source = inspect.getsource(ws).casefold()
    assert "import streamlit" not in source
    assert "from streamlit" not in source
    assert "analyst_assessment\"] =" not in source
    assert "buy/hold/sell" in source
    assert "explicit analyst selection" in source
