from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_history as hist
import modules.deep_company_analysis.chapter11_store as store


def _payload() -> dict:
    p = ch11.empty_payload("FPT", "FPT")
    p["question_status"]["Q58"] = "Answered"
    p["confidence"]["Q58"] = "High"
    p["analyst_assessment"]["Q58"] = "Evidence supports disciplined process"
    first_dim = ch11.dimension_ids("Q58")[0]
    p["dimension_status"][first_dim] = "Evidence found"
    p["evidence"] = [{"Question":"Q58","Dimension ID":first_dim,"Observation / Claim":"documented process","Candidate ID":"c1"}]
    p["ma_synthesis"] = {
        "status":"Draft",
        "decision_process_takeaway":"Analyst takeaway",
        "final_ma_synthesis":"Analyst conclusion",
        "analyst_reviewed_at":"2026-09-08T00:00:00Z",
    }
    return p


def test_v88_source_lock_unchanged():
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.SOURCE_QUESTION_RANGE == "Q58-Q59"
    assert len(ch11.dimension_ids()) == 15


def test_source_fingerprint_is_deterministic_and_ignores_noncontract_financial_values():
    p = _payload()
    one = hist.source_baseline_fingerprint(p)
    assert one == hist.source_baseline_fingerprint(deepcopy(p))
    assert len(one) == 64
    p["canonical_ebitda"] = 999999
    p["intrinsic_value"] = 123456
    assert hist.source_baseline_fingerprint(p) == one


def test_delta_is_neutral_and_detects_analyst_change():
    before = _payload()
    after = deepcopy(before)
    after["ma_synthesis"]["final_ma_synthesis"] = "Changed analyst conclusion"
    df = hist.compare_versions(before, after, before_label="S1", after_label="Current")
    row = df[df["Field"] == "Final Analyst M&A Synthesis"].iloc[0]
    assert row["Delta"] == "Changed"
    summary = hist.history_summary(before, after)
    assert summary["automatic_ma_score"] is False
    assert summary["automatic_acquisition_success_classification"] is False
    assert summary["automatic_synergy_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_investment_research_gate_changed"] is False


def test_lineage_uses_stored_metadata_only():
    p = _payload()
    rows = [{"snapshot_id": 1, "created_at": "2026-09-08T01:00:00Z", "schema_version": 3, "research_status": "1/2 Answered", "payload": p}]
    df = hist.build_version_lineage(rows)
    assert list(df["Snapshot ID"]) == [1]
    assert df.iloc[0]["Final Synthesis Present"] == "Yes"
    assert len(df.iloc[0]["Source Baseline"]) == 16


def test_snapshot_store_is_immutable_and_re_review_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch11.db")
    p = _payload()
    store.save_record("FPT", p, "FPT")
    snap = store.create_snapshot("FPT", reason="baseline")
    sid = snap["snapshot_id"]
    changed = deepcopy(p)
    changed["ma_synthesis"]["final_ma_synthesis"] = "Current changed"
    store.save_record("FPT", changed, "FPT")
    old = store.load_snapshot("FPT", sid)
    assert old is not None
    assert old["payload"]["ma_synthesis"]["final_ma_synthesis"] == "Analyst conclusion"
    reviewed = store.mark_explicit_re_review("FPT", ["Q58", "M&A Synthesis"], "Reviewed source change")
    syn = reviewed["ma_synthesis"]
    assert syn["last_re_review_sections"] == ["Q58", "M&A Synthesis"]
    assert syn["last_re_review_note"] == "Reviewed source change"
    assert reviewed["question_status"]["Q58"] == "Answered"
    assert reviewed["confidence"]["Q58"] == "High"


def test_snapshot_list_is_oldest_to_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch11.db")
    store.save_record("FPT", _payload(), "FPT")
    a = store.create_snapshot("FPT", reason="one")
    b = store.create_snapshot("FPT", reason="two")
    rows = store.list_snapshots("FPT")
    assert [r["snapshot_id"] for r in rows] == [a["snapshot_id"], b["snapshot_id"]]
    assert [r["reason"] for r in rows] == ["one", "two"]


def test_v88_no_investment_or_duplicate_financial_logic_in_new_module():
    source = Path(hist.__file__).read_text(encoding="utf-8").casefold()
    assert "buy/hold/sell" in source
    assert "automatic_ma_score" in source
    assert "automatic_synergy_forecast" in source
    assert "historical source freshness is never reconstructed" in source
    assert "ebitda =" not in source
    assert "intrinsic_value =" not in source
