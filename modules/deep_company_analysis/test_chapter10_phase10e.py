from __future__ import annotations

import pandas as pd

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_research as research
import modules.deep_company_analysis.chapter10_store as store


def test_store_roundtrip_is_unknown_first(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "ch10.db")
    p = store.load_record("dgc", "Demo")
    assert p["ticker"] == "DGC"
    assert all(p["question_status"][q] == "Unknown" for q in ch10.QUESTION_KEYS)
    p["question_status"]["Q53"] = "Partial"
    saved = store.save_record("DGC", p, "Demo")
    loaded = store.load_record("DGC")
    assert saved["question_status"]["Q53"] == "Partial"
    assert loaded["question_status"]["Q53"] == "Partial"


def test_promotion_is_explicit_and_does_not_mutate_conclusions():
    p = ch10.empty_payload("DGC")
    p["growth_mode"] = "Organic"
    p["confidence"]["Q53"] = "Low"
    frame = research.build_candidates([{
        "dimension_id": "q53_growth_style_continuum",
        "title": "Annual report",
        "url": "https://example.com/report",
        "text": "Organic expansion with selective acquisitions",
    }])
    cid = str(frame.iloc[0]["Candidate ID"])
    unchanged = research.promote_selected_candidates(p, frame, [])
    assert unchanged["evidence"] == []
    promoted = research.promote_selected_candidates(p, frame, [cid])
    assert len(promoted["evidence"]) == 1
    assert promoted["growth_mode"] == "Organic"
    assert promoted["confidence"]["Q53"] == "Low"
    assert promoted["question_status"]["Q53"] == "Unknown"
    assert promoted["dimension_status"]["q53_growth_style_continuum"] == "Unknown"


def test_promoted_candidate_ids_support_ui_dedupe():
    p = ch10.empty_payload("DGC")
    p["evidence"] = [{"Candidate ID": "abc"}, {"Candidate ID": "abc"}, {"Candidate ID": "xyz"}]
    assert store.promoted_candidate_ids(p) == {"abc", "xyz"}


def test_store_payload_has_no_canonical_financial_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "ch10.db")
    p = ch10.empty_payload("DGC")
    store.save_record("DGC", p)
    loaded = store.load_record("DGC")
    forbidden = {"revenue", "cash_flow_operations", "ccc", "dio", "dso", "dpo", "intrinsic_value", "mos"}
    assert forbidden.isdisjoint(loaded.keys())


def test_research_status_is_completion_only_not_score():
    p = ch10.empty_payload("DGC")
    p["question_status"]["Q53"] = "Answered"
    status = store.research_status(p)
    assert status.startswith("1/5 Answered")
    assert "score" not in status.casefold()


def test_all_34_dimensions_remain_available():
    assert len(ch10.dimension_ids()) == 34
    assert ch10.dimension_count_by_question() == {"Q53": 4, "Q54": 4, "Q55": 4, "Q56": 15, "Q57": 7}
