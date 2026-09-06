from __future__ import annotations

from pathlib import Path
import inspect

import pandas as pd

import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter8_store as store
import modules.deep_company_analysis.chapter8_workspace as ws
import modules.deep_company_analysis.chapter8_page_support as ui
import modules.deep_company_analysis.chapter8_research as research


def _candidate(select: bool = True) -> dict:
    row = {column: "" for column in research.CANDIDATE_COLUMNS}
    row.update({
        "Select": select,
        "Candidate ID": "cand-1",
        "Question": "Q39",
        "Manager ID": "M001",
        "Manager": "Example Manager",
        "Subtopic": "Employees",
        "Direction": "Supporting cue — analyst assess",
        "Source Grade": "A — Company/Official disclosure",
        "Source Title": "Annual report",
        "Source URL / File": "https://example.com/annual-report",
        "As-of Date": "2026",
        "Evidence Text / Reference": "Management described employee training and retention programs.",
        "Data Origin": "Direct source text — analyst verification required",
        "Status": "Candidate — analyst verify",
    })
    return row


def test_promote_selected_candidate_preserves_analyst_fields():
    payload = ch8.empty_payload("DGC", "Duc Giang Chemicals")
    payload["analyst_assessment"]["Q39"] = "My existing analyst conclusion"
    payload["question_status"]["Q39"] = "Partial"
    payload["confidence"]["Q39"] = "High"

    out, added = ws.promote_selected_candidates(payload, pd.DataFrame([_candidate(True)]))
    assert added == 1
    assert out["analyst_assessment"]["Q39"] == "My existing analyst conclusion"
    assert out["question_status"]["Q39"] == "Partial"
    assert out["confidence"]["Q39"] == "High"
    assert out["evidence"][0]["Status"] == "Promoted — analyst verified"
    assert out["evidence"][0]["Direction"] == "Supporting"


def test_promote_is_deduplicated_and_unselected_rows_are_ignored():
    payload = ch8.empty_payload("DGC")
    out, added = ws.promote_selected_candidates(payload, [_candidate(True), _candidate(True), _candidate(False)])
    assert added == 1
    out2, added2 = ws.promote_selected_candidates(out, [_candidate(True)])
    assert added2 == 0
    assert len(out2["evidence"]) == 1


def test_merge_research_gaps_preserves_existing_analyst_note():
    payload = ch8.empty_payload("DGC")
    existing = {
        "Question": "Q47", "Manager ID": "", "Manager": "",
        "Research Gap": "No explicit buyback evidence.", "Materiality": "High",
        "Next Action": "Read disclosures.", "Status": "Open — evidence gap",
        "Analyst Note": "Keep this note",
    }
    payload["research_gaps"] = [existing.copy()]
    incoming = pd.DataFrame([existing.copy(), {
        **existing,
        "Question": "Q41",
        "Research Gap": "No guidance evidence.",
        "Analyst Note": "",
    }])
    out, added = ws.merge_research_gaps(payload, incoming)
    assert added == 1
    q47 = [x for x in out["research_gaps"] if x["Question"] == "Q47"][0]
    assert q47["Analyst Note"] == "Keep this note"


def test_store_roundtrip_and_snapshot(tmp_path):
    original = store.DB_PATH
    try:
        store.DB_PATH = tmp_path / "chapter8_test.db"
        payload = ch8.empty_payload("DGC", "Duc Giang Chemicals")
        payload["analyst_assessment"]["Q46"] = "Analyst-owned capital allocation view"
        payload["question_status"]["Q46"] = "Partial"
        saved = store.save_record("DGC", payload, "Duc Giang Chemicals")
        loaded = store.load_record("DGC")
        assert loaded["analyst_assessment"]["Q46"] == saved["analyst_assessment"]["Q46"]
        assert loaded["question_status"]["Q46"] == "Partial"
        snapshot_id = store.create_snapshot("DGC", loaded)
        assert snapshot_id >= 1
        snapshots = store.list_snapshots("DGC")
        assert snapshots and snapshots[0]["id"] == snapshot_id
    finally:
        store.DB_PATH = original


def test_phase8d_ui_contract_exposes_research_promote_sources_save_and_snapshot():
    src = inspect.getsource(ui)
    assert "Tự nghiên cứu Q39–Q47" in src
    assert "Promote evidence đã chọn" in src
    assert "LinkColumn" in src
    assert "Research Gap Workflow" in src
    assert "Lưu Chapter 8 workspace" in src
    assert "Lưu snapshot Chapter 8" in src
    assert "Chapter8ResearchAgent" in src
    assert "load_chapter7_record" in src
    assert "build_phase8b_context" in src


def test_phase8d_route_and_sidebar_are_wired():
    root = Path(__file__).resolve().parents[2]
    page = root / "pages" / "09_Phan_tich_chuyen_sau_Chuong_8.py"
    sidebar = root / "tre_sidebar_nav.py"
    assert page.exists()
    assert "render_chapter8_tab" in page.read_text(encoding="utf-8")
    assert "09_Phan_tich_chuyen_sau_Chuong_8.py" in sidebar.read_text(encoding="utf-8")


def test_ui_does_not_replace_source_locked_five_capital_allocation_actions():
    assert len(ch8.CAPITAL_ALLOCATION_ACTIONS) == 5
    assert not any("debt" in action.casefold() for action in ch8.CAPITAL_ALLOCATION_ACTIONS)
