from __future__ import annotations

from pathlib import Path

from modules.deep_company_analysis.appendix_a_history import (
    build_interview_lineage,
    build_version_lineage,
    compare_versions,
    history_summary,
    source_baseline_fingerprint,
)
from modules.deep_company_analysis.appendix_a_store import (
    create_appendix_a_snapshot,
    list_appendix_a_snapshots,
    load_appendix_a_snapshot,
)
from modules.deep_company_analysis.appendix_a_workspace import make_interview_record, make_research_gap, make_source_record, normalize_workspace


def _workspace(note: str = ""):
    source = make_source_record(source_name="Supplier A", source_class="Primary", source_type="Supplier")
    interview = make_interview_record(
        source_id=source["source_id"], interview_date="2026-09-08", question_prompt="What changed?",
        source_response_observation="Lead times shortened.", statement_type="Fact",
        uncertainty_noted="Exact month not specified.", related_question_refs=["Q03", "Q59"],
        analyst_commentary=note,
    )
    return normalize_workspace({"ticker": "ABC", "company_name": "ABC Co", "sources": [source], "interviews": [interview]})


def test_source_baseline_is_deterministic_and_changes_only_with_workspace_research_state():
    a = _workspace("")
    b = _workspace("")
    assert source_baseline_fingerprint(a) == source_baseline_fingerprint(b)
    b["sections"]["interview_database"] = "Covered"
    assert source_baseline_fingerprint(a) != source_baseline_fingerprint(b)


def test_interview_lineage_is_descriptive_not_credibility_scoring():
    frame = build_interview_lineage(_workspace("Needs corroboration"))
    assert len(frame) == 1
    row = frame.iloc[0].to_dict()
    assert row["Statement Type"] == "Fact"
    assert row["Uncertainty Noted"] == "Yes"
    assert row["Analyst Commentary Present"] == "Yes"
    assert not any("score" in str(column).casefold() or "credibility" in str(column).casefold() for column in frame.columns)


def test_delta_vocabulary_is_neutral_only():
    before = _workspace("")
    after = _workspace("Analyst note")
    delta = compare_versions(before, after)
    assert set(delta["Delta"]).issubset({"Unchanged", "Added", "Removed", "Changed"})
    assert "Changed" in set(delta["Delta"])


def test_history_summary_never_changes_investment_or_scoring_state():
    summary = history_summary(_workspace(""), _workspace("Changed"))
    assert summary["automatic_human_source_score"] is False
    assert summary["automatic_credibility_score"] is False
    assert summary["automatic_weighted_research_score"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["automatic_mos_change"] is False
    assert summary["automatic_research_gate_change"] is False
    assert summary["historical_source_freshness_reconstructed"] is False


def test_snapshot_roundtrip_is_immutable_and_normalized(tmp_path: Path):
    db = tmp_path / "appa.sqlite3"
    ws = _workspace("Original")
    snap = create_appendix_a_snapshot(ws, db_path=db)
    ws["analyst_synthesis"] = "Changed after snapshot"
    loaded = load_appendix_a_snapshot(snap["snapshot_id"], db_path=db)
    assert loaded["payload"]["analyst_synthesis"] == ""
    assert loaded["payload"]["interviews"][0]["analyst_commentary"] == "Original"
    assert loaded["schema_version"] == 1


def test_snapshot_allowlist_drops_financial_and_investment_payloads(tmp_path: Path):
    db = tmp_path / "appa.sqlite3"
    raw = _workspace("")
    raw.update({"research_gate": "PASS", "intrinsic_value": 999, "margin_of_safety": 0.9, "buy_hold_sell": "BUY", "financials": {"revenue": 1}})
    snap = create_appendix_a_snapshot(raw, db_path=db)
    payload = snap["payload"]
    for key in ("research_gate", "intrinsic_value", "margin_of_safety", "buy_hold_sell", "financials"):
        assert key not in payload


def test_list_snapshots_and_version_lineage_are_ordered(tmp_path: Path):
    db = tmp_path / "appa.sqlite3"
    create_appendix_a_snapshot(_workspace("A"), db_path=db)
    create_appendix_a_snapshot(_workspace("B"), db_path=db)
    snapshots = list_appendix_a_snapshots("abc", db_path=db)
    assert [item["snapshot_id"] for item in snapshots] == sorted(item["snapshot_id"] for item in snapshots)
    lineage = build_version_lineage(snapshots)
    assert len(lineage) == 2
    assert all(str(v).startswith("Snapshot #") for v in lineage["Version"])


def test_research_gap_delta_does_not_resolve_or_rewrite_gap_automatically():
    before = _workspace("")
    before["research_gaps"] = [make_research_gap(unanswered_question_assumption="Why did churn change?", preferred_source_type="Customer", status="Open")]
    after = normalize_workspace(before)
    delta = compare_versions(before, after)
    assert set(delta["Delta"]) == {"Unchanged"}
    assert after["research_gaps"][0]["status"] == "Open"
