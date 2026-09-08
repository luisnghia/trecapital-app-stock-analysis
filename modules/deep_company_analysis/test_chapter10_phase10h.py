from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import modules.deep_company_analysis.chapter10 as ch10
import modules.deep_company_analysis.chapter10_completion as completion
import modules.deep_company_analysis.chapter10_history as history
import modules.deep_company_analysis.chapter10_history_ui as history_ui
import modules.deep_company_analysis.chapter10_page_support as page_support
import modules.deep_company_analysis.chapter10_store as store


def _payload() -> dict:
    p = ch10.empty_payload("VNM", "Vinamilk")
    p["question_status"]["Q53"] = "Answered"
    p["confidence"]["Q53"] = "High"
    p["analyst_assessment"]["Q53"] = "Mixed organic and acquisition evidence"
    p["growth_mode"] = "Mixed"
    p["growth_synthesis"] = completion.normalize_synthesis({
        "status": "Reviewed",
        "growth_route_takeaway": "Mixed route",
        "profitability_takeaway": "Historical economics reviewed",
        "runway_takeaway": "Runway remains analyst judgment",
        "pace_and_funding_takeaway": "Funding evidence reviewed",
        "key_strengths": "Distribution",
        "key_concerns": "Execution",
        "key_unknowns": "Future market share",
        "final_growth_synthesis": "Analyst conclusion only",
        "analyst_note": "No investment signal",
    })
    return p


def test_v81_keeps_exact_chapter10_source_lock_and_dimensions():
    assert ch10.QUESTION_KEYS == ("Q53", "Q54", "Q55", "Q56", "Q57")
    assert ch10.SOURCE_QUESTION_RANGE == "Q53-Q57"
    assert len(ch10.dimension_ids()) == 34


def test_v81_re_review_metadata_survives_synthesis_normalization():
    syn = completion.normalize_synthesis({
        "status": "Reviewed",
        "final_growth_synthesis": "Analyst conclusion",
        "last_re_review_at": "2026-09-08T01:00:00Z",
        "last_re_review_note": "Checked source delta",
        "last_re_review_sections": ["Q53", "Growth Synthesis"],
    })
    round_trip = completion.normalize_synthesis(syn)
    assert round_trip["last_re_review_at"] == "2026-09-08T01:00:00Z"
    assert round_trip["last_re_review_note"] == "Checked source delta"
    assert round_trip["last_re_review_sections"] == ["Q53", "Growth Synthesis"]


def test_v81_history_tracks_real_synthesis_field_names():
    before = _payload()
    after = deepcopy(before)
    after["growth_synthesis"]["growth_route_takeaway"] = "Route changed by analyst"
    delta = history.compare_versions(before, after)
    row = delta[delta["Field"] == "Growth Route Takeaway"].iloc[0]
    assert row["Delta"] == "Changed"
    assert "growth_route_takeaway" in {key for _, key in history.SYNTHESIS_FIELDS}
    assert "growth_route" not in {key for _, key in history.SYNTHESIS_FIELDS}


def test_v81_history_report_section_uses_immutable_latest_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch10_v81.db")
    p = _payload()
    store.save_record("VNM", p, "Vinamilk")
    snap = store.create_snapshot("VNM", reason="baseline")
    current = deepcopy(p)
    current["growth_synthesis"]["final_growth_synthesis"] = "Current analyst revision"
    store.save_record("VNM", current, "Vinamilk")
    report = history_ui.history_report_section("VNM", current)
    assert report["snapshot_count"] == 1
    assert report["latest_snapshot_id"] == snap["snapshot_id"]
    changed = report["latest_to_current_delta"]
    row = changed[changed["Field"] == "Final Analyst Growth Synthesis"].iloc[0]
    assert row["Delta"] == "Changed"
    assert report["summary"]["automatic_investment_signal"] is False


def test_v81_explicit_re_review_does_not_change_analyst_conclusion(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", Path(tmp_path) / "ch10_v81.db")
    p = _payload()
    store.save_record("VNM", p, "Vinamilk")
    before = store.load_record("VNM")
    reviewed = store.mark_explicit_re_review("VNM", ["Q53", "Growth Synthesis"], "Re-read source")
    assert reviewed["growth_mode"] == before["growth_mode"]
    assert reviewed["question_status"] == before["question_status"]
    assert reviewed["confidence"] == before["confidence"]
    assert reviewed["analyst_assessment"] == before["analyst_assessment"]
    assert reviewed["growth_synthesis"]["final_growth_synthesis"] == before["growth_synthesis"]["final_growth_synthesis"]


def test_v81_page_integrates_history_panel_and_lineage_report():
    source = Path(page_support.__file__).read_text(encoding="utf-8")
    assert "history_ui.render_history_panel" in source
    assert "history_ui.history_report_section" in source
    assert "Latest immutable snapshot" in source


def test_v81_closure_has_no_duplicate_financial_or_investment_engine():
    files = [Path(history_ui.__file__), Path(history.__file__), Path(completion.__file__)]
    source = "\n".join(p.read_text(encoding="utf-8").casefold() for p in files)
    assert "ccc =" not in source
    assert "intrinsic_value" not in source
    assert "automatic_growth_score" in source
    assert "automatic_growth_forecast" in source
    assert "automatic_investment_signal" in source
    assert "mos_or_investment_research_gate_changed" in source
