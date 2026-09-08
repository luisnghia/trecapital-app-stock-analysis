from __future__ import annotations

import json
import tempfile
from pathlib import Path

from modules.deep_company_analysis.appendix_b_history import (
    build_session_lineage,
    build_version_lineage,
    compare_versions,
    history_summary,
    normalize_history_payload,
    source_baseline_fingerprint,
)
from modules.deep_company_analysis.appendix_b_store import (
    create_snapshot,
    list_re_reviews,
    list_snapshots,
    load_snapshot,
    record_re_review,
    save_research_gap,
    save_session,
)
from modules.deep_company_analysis.appendix_b_workspace import new_research_gap, new_session


def _sample():
    session = new_session("FPT", "CEO", "2026-09-08", "FPT")
    session["status"] = "Completed"
    session["topic_entries"][0]["open_ended_question"] = "How did you make the decision?"
    session["topic_entries"][0]["management_response_observation"] = "Management described a prior hiring decision."
    session["topic_entries"][0]["past_behavior_evidence"] = "Prior decision record noted by analyst."
    session["topic_entries"][0]["dca_question_refs"] = ["Q43", "Q49"]
    gap = new_research_gap("FPT", "Clarify succession evidence", ["Q43"], session["session_id"])
    return session, gap


def test_v95_history_payload_is_allow_listed_and_stable():
    session, gap = _sample()
    dirty = {
        "ticker": "FPT", "company_name": "FPT", "sessions": [session], "research_gaps": [gap],
        "research_gate": "PASS", "intrinsic_value": 999, "financials": {"revenue": 1}, "management_score": 100,
    }
    clean = normalize_history_payload(dirty)
    serialized = json.dumps(clean, ensure_ascii=False, sort_keys=True).casefold()
    for forbidden in ("research_gate", "intrinsic_value", "financials", "management_score"):
        assert forbidden not in serialized
    assert source_baseline_fingerprint(clean) == source_baseline_fingerprint(clean)


def test_v95_neutral_delta_uses_only_allowed_vocabulary():
    session, gap = _sample()
    before = {"ticker": "FPT", "sessions": [session], "research_gaps": [gap]}
    session2 = json.loads(json.dumps(session))
    session2["analyst_session_note"] = "New analyst note"
    after = {"ticker": "FPT", "sessions": [session2], "research_gaps": [gap]}
    delta = compare_versions(before, after)
    assert set(delta["Delta"]).issubset({"Unchanged", "Added", "Removed", "Changed"})
    assert "better" not in " ".join(delta["Delta"]).casefold()
    summary = history_summary(before, after)
    assert summary["automatic_management_score"] is False
    assert summary["automatic_ceo_quality_classifier"] is False
    assert summary["automatic_research_gate_change"] is False


def test_v95_session_lineage_reports_provenance_not_quality():
    session, gap = _sample()
    session["topic_entries"][1]["hypothetical_flag"] = True
    session["topic_entries"][2]["face_to_face_caveat"] = "Personality affinity risk"
    frame = build_session_lineage({"ticker": "FPT", "sessions": [session], "research_gaps": [gap]})
    assert len(frame) == 1
    assert frame.iloc[0]["Hypothetical Caveats"] == 1
    assert frame.iloc[0]["Face-to-Face Caveats"] == 1
    assert not any("score" in c.casefold() for c in frame.columns)


def test_v95_snapshot_is_immutable_and_re_review_is_separate():
    session, gap = _sample()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "appb.sqlite"
        save_session(db, session)
        save_research_gap(db, gap)
        snap = create_snapshot(db, "FPT", [session], [gap], "FPT")
        original = load_snapshot(db, snap["snapshot_id"])
        session["analyst_session_note"] = "Changed after snapshot"
        save_session(db, session)
        again = load_snapshot(db, snap["snapshot_id"])
        assert original == again
        record = record_re_review(db, "FPT", "Appendix B", "Analyst checked changed evidence")
        assert record["scope"] == "Appendix B"
        assert len(list_re_reviews(db, "FPT")) == 1
        assert len(list_snapshots(db, "FPT")) == 1


def test_v95_version_lineage_is_deterministic():
    session, gap = _sample()
    records = [
        {"snapshot_id": 2, "created_at": "2026-09-08 12:00:00", "schema_version": 1, "payload": {"ticker": "FPT", "sessions": [session], "research_gaps": [gap]}},
        {"snapshot_id": 1, "created_at": "2026-09-08 11:00:00", "schema_version": 1, "payload": {"ticker": "FPT", "sessions": [], "research_gaps": []}},
    ]
    frame = build_version_lineage(records)
    assert frame["Snapshot ID"].tolist() == [1, 2]
    assert frame.iloc[1]["Sessions"] == 1
