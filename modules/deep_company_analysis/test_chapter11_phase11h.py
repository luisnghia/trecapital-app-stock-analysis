from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import modules.deep_company_analysis.chapter11 as ch11
import modules.deep_company_analysis.chapter11_completion as completion
import modules.deep_company_analysis.chapter11_history as history
import modules.deep_company_analysis.chapter11_history_ui as history_ui
import modules.deep_company_analysis.chapter11_store as store


def _payload() -> dict:
    p = ch11.empty_payload("FPT", "FPT")
    p["ma_synthesis"] = completion.default_synthesis()
    p["ma_synthesis"]["status"] = "Draft"
    p["ma_synthesis"]["final_ma_synthesis"] = "Analyst-owned M&A synthesis"
    return p


def test_v89_source_lock_and_chapter_closure_scope_unchanged():
    assert ch11.QUESTION_KEYS == ("Q58", "Q59")
    assert ch11.QUESTION_TITLES["Q58"] == "How does management make M&A decisions?"
    assert ch11.QUESTION_TITLES["Q59"] == "Have past acquisitions been successful?"
    assert ch11.SOURCE_QUESTION_RANGE == "Q58-Q59"
    assert len(ch11.dimension_ids()) == 15


def test_v89_synthesis_normalization_preserves_explicit_re_review_metadata():
    syn = completion.default_synthesis()
    syn.update({
        "last_re_review_at": "2026-09-08T08:00:00Z",
        "last_re_review_note": "Analyst re-reviewed changed evidence",
        "last_re_review_sections": ["Q58", "M&A Synthesis"],
    })
    out = completion.normalize_synthesis(syn)
    assert out["last_re_review_at"] == syn["last_re_review_at"]
    assert out["last_re_review_note"] == syn["last_re_review_note"]
    assert out["last_re_review_sections"] == ["Q58", "M&A Synthesis"]


def test_v89_explicit_re_review_survives_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch11.db")
    p = _payload()
    p["question_status"]["Q58"] = "Answered"
    p["confidence"]["Q58"] = "High"
    store.save_record("FPT", p, "FPT")
    reviewed = store.mark_explicit_re_review("FPT", ["Q58", "Source Baseline"], "Checked")
    normalized = deepcopy(reviewed)
    normalized["ma_synthesis"] = completion.normalize_synthesis(reviewed["ma_synthesis"])
    saved = store.save_record("FPT", normalized, "FPT")
    loaded = store.load_record("FPT", "FPT")
    assert saved["ma_synthesis"]["last_re_review_sections"] == ["Q58", "Source Baseline"]
    assert loaded["ma_synthesis"]["last_re_review_note"] == "Checked"
    assert loaded["question_status"]["Q58"] == "Answered"
    assert loaded["confidence"]["Q58"] == "High"


def test_v89_history_report_uses_latest_immutable_snapshot_and_neutral_delta(monkeypatch):
    before = _payload()
    after = deepcopy(before)
    after["ma_synthesis"]["final_ma_synthesis"] = "Updated by analyst"
    snapshots = [{
        "snapshot_id": 7,
        "created_at": "2026-09-08T07:00:00Z",
        "schema_version": 3,
        "research_status": "0/2 Answered",
        "reason": "baseline",
        "payload": before,
    }]
    monkeypatch.setattr(history_ui, "list_snapshots", lambda ticker: snapshots)
    report = history_ui.history_report_section("FPT", after)
    assert report["snapshot_count"] == 1
    assert report["latest_snapshot_id"] == 7
    changed = report["latest_to_current_delta"]
    row = changed[changed["Field"] == "Final Analyst M&A Synthesis"].iloc[0]
    assert row["Delta"] == "Changed"
    assert set(changed["Delta"]).issubset({"Unchanged", "Added", "Removed", "Changed"})
    assert report["summary"]["automatic_ma_score"] is False
    assert report["summary"]["automatic_investment_signal"] is False


def test_v89_history_ui_sections_are_source_locked_and_analyst_owned():
    assert history_ui.REVIEW_SECTIONS == ("Q58", "Q59", "M&A Synthesis", "Source Baseline")
    source = Path(history_ui.__file__).read_text(encoding="utf-8")
    assert "Create immutable snapshot" in source
    assert "Neutral delta" in source
    assert "Explicit analyst re-review" in source
    assert "Current saved workspace" in source


def test_v89_live_page_integrates_history_and_lineage_report():
    source = Path("modules/deep_company_analysis/chapter11_page_support.py").read_text(encoding="utf-8")
    assert "chapter11_history_ui" in source
    assert "history_ui.render_history_panel" in source
    assert "history_ui.history_report_section" in source
    assert "Chapter 11 Report — Version Lineage" in source
    assert "Latest immutable snapshot → current workspace" in source


def test_v89_closure_preserves_research_and_investment_boundaries():
    sources = "\n".join(Path(p).read_text(encoding="utf-8").casefold() for p in [
        completion.__file__, history.__file__, history_ui.__file__, "modules/deep_company_analysis/chapter11_page_support.py",
    ])
    assert "m&a score" in sources
    assert "buy/hold/sell" in sources
    assert "investment research gate" in sources
    assert "automatic_investment_signal" in sources
    assert "automatic_synergy_forecast" in sources
    assert "ebitda =" not in sources
    assert "intrinsic_value =" not in sources
