from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_history as hist
import modules.deep_company_analysis.chapter10_store as store


def _payload() -> dict:
    p = ch10.empty_payload("VNM", "Vinamilk")
    p["question_status"]["Q53"] = "Answered"
    p["confidence"]["Q53"] = "High"
    p["analyst_assessment"]["Q53"] = "Mixed"
    p["growth_mode"] = "Mixed"
    p["dimension_status"]["q53_growth_style_continuum"] = "Evidence found"
    p["evidence"] = [{"Question":"Q53","Dimension ID":"q53_growth_style_continuum","Observation / Claim":"mixed growth","Candidate ID":"c1"}]
    p["growth_synthesis"] = {"growth_route":"Mixed", "final_growth_synthesis":"Analyst conclusion", "analyst_reviewed_at":"2026-09-08T00:00:00Z"}
    return p


def test_v80_source_lock_unchanged():
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.SOURCE_QUESTION_RANGE == "Q53-Q57"
    assert len(ch10.dimension_ids()) == 34


def test_source_fingerprint_is_deterministic_and_financial_ssot_not_required():
    p = _payload()
    one = hist.source_baseline_fingerprint(p)
    two = hist.source_baseline_fingerprint(deepcopy(p))
    assert one == two and len(one) == 64
    p["canonical_revenue"] = 999999
    assert hist.source_baseline_fingerprint(p) == one


def test_delta_is_neutral_and_detects_analyst_change():
    before = _payload()
    after = deepcopy(before)
    after["growth_synthesis"]["final_growth_synthesis"] = "Changed analyst conclusion"
    df = hist.compare_versions(before, after, before_label="S1", after_label="Current")
    row = df[df["Field"] == "Final Analyst Growth Synthesis"].iloc[0]
    assert row["Delta"] == "Changed"
    summary = hist.history_summary(before, after)
    assert summary["automatic_growth_score"] is False
    assert summary["automatic_growth_forecast"] is False
    assert summary["automatic_investment_signal"] is False
    assert summary["mos_or_investment_research_gate_changed"] is False


def test_lineage_uses_stored_metadata_only():
    p = _payload()
    rows = [{"snapshot_id": 1, "created_at": "2026-09-08T01:00:00Z", "schema_version": 2, "research_status": "1/5 Answered", "payload": p}]
    df = hist.build_version_lineage(rows)
    assert list(df["Snapshot ID"]) == [1]
    assert df.iloc[0]["Final Synthesis Present"] == "Yes"
    assert len(df.iloc[0]["Source Baseline"]) == 16


def test_snapshot_store_is_immutable_and_re_review_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch10.db")
    p = _payload()
    store.save_record("VNM", p, "Vinamilk")
    snap = store.create_snapshot("VNM", reason="baseline")
    sid = snap["snapshot_id"]
    changed = deepcopy(p)
    changed["growth_synthesis"]["final_growth_synthesis"] = "Current changed"
    store.save_record("VNM", changed, "Vinamilk")
    old = store.load_snapshot("VNM", sid)
    assert old is not None
    assert old["payload"]["growth_synthesis"]["final_growth_synthesis"] == "Analyst conclusion"
    reviewed = store.mark_explicit_re_review("VNM", ["Q53", "Growth Synthesis"], "Reviewed source change")
    syn = reviewed["growth_synthesis"]
    assert syn["last_re_review_sections"] == ["Q53", "Growth Synthesis"]
    assert syn["last_re_review_note"] == "Reviewed source change"
    assert reviewed["question_status"]["Q53"] == "Answered"
    assert reviewed["confidence"]["Q53"] == "High"


def test_snapshot_list_is_oldest_to_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch10.db")
    store.save_record("FPT", _payload(), "FPT")
    a = store.create_snapshot("FPT", reason="one")
    b = store.create_snapshot("FPT", reason="two")
    rows = store.list_snapshots("FPT")
    assert [r["snapshot_id"] for r in rows] == [a["snapshot_id"], b["snapshot_id"]]
    assert [r["reason"] for r in rows] == ["one", "two"]


def test_v80_no_investment_or_duplicate_financial_logic_in_new_module():
    source = Path(hist.__file__).read_text(encoding="utf-8").casefold()
    assert "buy/hold/sell" in source
    assert "automatic_growth_forecast" in source
    assert "automatic_investment_signal" in source
    assert "ccc =" not in source
    assert "intrinsic_value" not in source
