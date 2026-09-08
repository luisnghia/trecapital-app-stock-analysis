from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modules.deep_company_analysis.appendix_b import MANAGEMENT_INTERVIEW_TOPICS, SOURCE_LOCK
from modules.deep_company_analysis.appendix_b_store import list_research_gaps, list_sessions, load_session, save_research_gap, save_session
from modules.deep_company_analysis.appendix_b_workspace import (
    DCA_QUESTION_IDS,
    new_research_gap,
    new_session,
    normalize_dca_question_refs,
    normalize_session,
    stable_id,
    workspace_summary,
)


def test_v94_session_is_source_locked_and_has_all_topics():
    session = new_session("fpt", "CEO", "2026-09-08", "FPT")
    assert session["ticker"] == "FPT"
    assert session["source_lock"] == SOURCE_LOCK
    assert len(session["topic_entries"]) == len(MANAGEMENT_INTERVIEW_TOPICS) == 8
    assert all(entry["management_response_observation"] == "" for entry in session["topic_entries"])
    assert all(entry["analyst_commentary"] == "" for entry in session["topic_entries"])


def test_v94_stable_ids_are_deterministic():
    assert stable_id("MB", "FPT", "CEO", "2026-09-08") == stable_id("MB", "fpt", "CEO", "2026-09-08")


def test_v94_dca_links_are_reference_only_and_allowlisted():
    assert normalize_dca_question_refs(["q01", "Q59", "Q60", "research_gate", "Q01"]) == ["Q01", "Q59"]
    assert len(DCA_QUESTION_IDS) == 59


def test_v94_separates_management_response_from_analyst_commentary():
    session = new_session("FPT", "CEO", "2026-09-08")
    session["topic_entries"][0]["management_response_observation"] = "Management said X."
    session["topic_entries"][0]["analyst_commentary"] = "Analyst interpretation Y."
    clean = normalize_session(session)
    assert clean["topic_entries"][0]["management_response_observation"] == "Management said X."
    assert clean["topic_entries"][0]["analyst_commentary"] == "Analyst interpretation Y."


def test_v94_normalization_strips_non_contract_investment_fields():
    session = new_session("FPT", "CEO", "2026-09-08")
    session.update({"management_score": 99, "research_gate": "PASS", "intrinsic_value": 123, "financials": {"revenue": 1}})
    clean = normalize_session(session)
    dumped = json.dumps(clean).casefold()
    for token in ("management_score", "research_gate", "intrinsic_value", "financials"):
        assert token not in dumped


def test_v94_persistence_round_trip_and_upsert():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "v94.sqlite"
        session = new_session("FPT", "CEO", "2026-09-08")
        session["topic_entries"][1]["management_response_observation"] = "Observed response"
        save_session(db, session)
        session["status"] = "Completed"
        save_session(db, session)
        rows = list_sessions(db, "FPT")
        assert len(rows) == 1
        loaded = load_session(db, "FPT", session["session_id"])
        assert loaded is not None and loaded["status"] == "Completed"
        assert loaded["topic_entries"][1]["management_response_observation"] == "Observed response"


def test_v94_research_gap_persistence_links_q01_q59_only():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "v94.sqlite"
        gap = new_research_gap("FPT", "Clarify succession evidence", ["Q01", "Q59", "Q60"])
        save_research_gap(db, gap)
        rows = list_research_gaps(db, "FPT")
        assert len(rows) == 1
        assert rows[0]["dca_question_refs"] == ["Q01", "Q59"]


def test_v94_workspace_summary_has_no_score_or_investment_signal():
    session = new_session("FPT", "CEO", "2026-09-08")
    session["topic_entries"][0]["dca_question_refs"] = ["Q47"]
    gap = new_research_gap("FPT", "Need operating record check", ["Q48"])
    summary = workspace_summary([session], [gap])
    assert summary["referenced_dca_questions"] == ["Q47", "Q48"]
    dumped = json.dumps(summary).casefold()
    assert "buy/hold/sell" not in dumped
    assert "management_score" not in dumped
    assert "research_gate" not in dumped


def test_v94_hypothetical_flag_is_preserved_as_caveat_not_prediction():
    session = new_session("FPT", "CEO", "2026-09-08")
    session["topic_entries"][0]["hypothetical_flag"] = True
    clean = normalize_session(session)
    assert clean["topic_entries"][0]["hypothetical_flag"] is True
    assert "prediction" not in clean["topic_entries"][0]
