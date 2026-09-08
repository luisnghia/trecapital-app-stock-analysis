from __future__ import annotations

from copy import deepcopy

import pandas as pd

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_research as research
import modules.deep_company_analysis.chapter11_store as store


def test_v86_store_round_trip_preserves_analyst_owned_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "ch11.db")
    payload = ch11.empty_payload("DGC", "Test Co")
    payload["question_status"]["Q58"] = "Partial"
    payload["confidence"]["Q58"] = "Medium"
    payload["analyst_assessment"]["Q58"] = "Analyst-authored conclusion"
    payload["dimension_status"]["q58_management_motivation"] = "Evidence found"
    saved = store.save_record("DGC", payload, "Test Co")
    loaded = store.load_record("DGC")
    assert loaded == saved
    assert loaded["analyst_assessment"]["Q58"] == "Analyst-authored conclusion"


def test_v86_promotion_is_explicit_and_does_not_change_conclusions(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "ch11.db")
    payload = ch11.empty_payload("DGC")
    before = deepcopy(payload)
    candidates = research.build_candidates([{
        "dimension_id": "q59_price_discipline_and_walkaway",
        "title": "Annual report",
        "url": "https://example.com/report",
        "text": "Management declined a proposed transaction after price exceeded its limit.",
    }])
    assert len(candidates) == 1
    unchanged = research.promote_selected_candidates(payload, candidates, [])
    assert unchanged["evidence"] == []
    promoted = research.promote_selected_candidates(payload, candidates, candidates["Candidate ID"].tolist())
    assert len(promoted["evidence"]) == 1
    for field in ("question_status", "confidence", "analyst_assessment", "dimension_status"):
        assert promoted[field] == before[field]


def test_v86_store_drops_non_contract_financial_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "ch11.db")
    payload = ch11.empty_payload("DGC")
    payload["canonical_financials"] = {"debt": 999, "ebitda": 888}
    payload["ev_ebitda"] = 12.3
    store.save_record("DGC", payload)
    loaded = store.load_record("DGC")
    assert "canonical_financials" not in loaded
    assert "ev_ebitda" not in loaded


def test_v86_duplicate_candidate_promotion_is_idempotent():
    payload = ch11.empty_payload("DGC")
    candidates = research.build_candidates([{
        "dimension_id": "q58_decision_process_and_rationale",
        "title": "Filing",
        "url": "https://example.com/a",
        "text": "Board described acquisition rationale and risks.",
    }])
    ids = candidates["Candidate ID"].tolist()
    once = research.promote_selected_candidates(payload, candidates, ids)
    twice = research.promote_selected_candidates(once, candidates, ids)
    assert len(once["evidence"]) == len(twice["evidence"]) == 1
    assert store.promoted_candidate_ids(twice) == set(ids)


def test_v86_source_lock_and_dimension_coverage_unchanged():
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.dimension_count_by_question() == {"Q58": 8, "Q59": 7}
    assert len(ch11.dimension_ids()) == 15
    assert list(research.research_plan("TEST")["Dimension ID"]) == list(ch11.dimension_ids())


def test_v86_research_gaps_are_not_quality_scores():
    gaps = research.research_gaps(pd.DataFrame(columns=research.CANDIDATE_COLUMNS))
    assert len(gaps) == 15
    assert set(gaps["Materiality"]) == {"Analyst to assess"}
    assert "score" not in " ".join(gaps.columns).casefold()
