from __future__ import annotations

"""Chapter 8 Phase 8F V47 final closure + DGC end-to-end acceptance.

The live DGC run intentionally does not auto-promote web research or auto-close questions.
A live gate that remains OPEN is therefore the correct result until an analyst verifies evidence
and closes Q39-Q47. The acceptance validates the closure engine and all source boundaries.
"""

import inspect
import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter8_research as research_module
import modules.deep_company_analysis.chapter8_store as store
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_completion import build_completion_gate
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_integration import build_chapter8_report_frames, build_chapter8_summary
from modules.deep_company_analysis.chapter8_workspace import merge_research_gaps


def main() -> int:
    ticker = "DGC"
    ok, paths, canonical_note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, f"DGC canonical refresh failed: {canonical_note}"
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    company_name = str(
        getattr(company, "company_name", "")
        or getattr(company, "name", "")
        or "CTCP Tập đoàn Hóa chất Đức Giang"
    )
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"
    assert not bridge["q45_cost_context"].empty
    assert not bridge["q46_capital_allocation_context"].empty
    assert not bridge["q47_buyback_context"].empty
    assert tuple(ch8.CAPITAL_ALLOCATION_ACTIONS) == (
        "Reinvest in business / new projects",
        "Hold cash",
        "Pay dividends",
        "Buy back stock",
        "Make acquisitions",
    )

    research = research_module.Chapter8ResearchAgent("data_cache/chapter8_phase8f_v47").search(
        ticker,
        company_name,
        chapter7_payload=None,
        max_results_per_query=1,
        max_official_documents=12,
    )
    assert list(research.quality["Question"]) == list(ch8.QUESTION_KEYS)
    assert len(research.source_attempts) >= 1, "No DGC official/company source was attempted"
    if not research.candidates.empty:
        assert research.candidates["Status"].eq("Candidate — analyst verify").all()
        assert research.candidates["Manager ID"].fillna("").eq("").all(), (
            "Research assistant invented manager IDs without Chapter 7 manager master"
        )

    # Live candidates remain candidates. We only merge machine-generated gaps into an isolated
    # acceptance payload to verify the workflow; no live candidate is auto-promoted.
    payload = ch8.empty_payload(ticker, company_name)
    payload["analyst_assessment"]["Q39"] = "V47 acceptance sentinel — analyst owned"
    payload, gaps_added = merge_research_gaps(payload, research.gaps)
    live_gate = build_completion_gate(payload, structured_context=bridge, chapter7_payload=None)
    assert live_gate["ready_for_chapter_close"] is False
    assert set(live_gate["open_questions"]) == set(ch8.QUESTION_KEYS)
    assert payload["analyst_assessment"]["Q39"] == "V47 acceptance sentinel — analyst owned"

    # A fully analyst-closed N/A fixture proves the gate can close without fabricating evidence.
    closed_fixture = ch8.empty_payload(ticker, company_name)
    for question in ch8.QUESTION_KEYS:
        closed_fixture["question_status"][question] = "N/A"
    closed_gate = build_completion_gate(closed_fixture, structured_context=bridge, chapter7_payload=None)
    assert closed_gate["ready_for_chapter_close"] is True

    summary = build_chapter8_summary(payload)
    frames = build_chapter8_report_frames(payload)
    assert list(frames["status"]["Question"]) == list(ch8.QUESTION_KEYS)
    assert summary["automatic_management_score"] is False
    assert summary["automatic_investment_signal"] is False

    # Isolated persistence + snapshot roundtrip.
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    original_db = store.DB_PATH
    try:
        store.DB_PATH = reports / "chapter8_phase8f_v47_acceptance.sqlite"
        if store.DB_PATH.exists():
            store.DB_PATH.unlink()
        store.save_record(ticker, payload, company_name)
        loaded = store.load_record(ticker)
        snapshot_id = store.create_snapshot(ticker, loaded)
        assert loaded["analyst_assessment"]["Q39"] == "V47 acceptance sentinel — analyst owned"
        assert snapshot_id >= 1
    finally:
        store.DB_PATH = original_db

    # Static boundary audit: the research assistant must not own analyst conclusions.
    research_source = inspect.getsource(research_module).casefold()
    assert "chapter 7 remains the manager identity/background single source of truth" in research_source
    assert "trecapital canonical financial data remains the financial single source of truth" in research_source
    assert "analyst_assessment" not in research_source
    assert "no management score" in research_source
    assert "no buy/hold/sell" in research_source

    latest_period = ""
    q46 = bridge["q46_capital_allocation_context"]
    if isinstance(q46, pd.DataFrame) and not q46.empty:
        latest_period = str(q46.iloc[-1].get("Kỳ") or "")

    by_question = {
        q: int((research.candidates["Question"] == q).sum()) if not research.candidates.empty else 0
        for q in ch8.QUESTION_KEYS
    }
    source_grades = (
        {str(k): int(v) for k, v in research.candidates["Source Grade"].value_counts().to_dict().items()}
        if not research.candidates.empty
        else {}
    )

    out = {
        "phase": "Chapter 8 Phase 8F Final Source Closure & Completion Gate V47",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "capital_allocation_source_locked_actions": len(ch8.CAPITAL_ALLOCATION_ACTIONS),
        "research_candidates": int(len(research.candidates)),
        "candidate_by_question": by_question,
        "source_grades": source_grades,
        "source_attempts": int(len(research.source_attempts)),
        "research_gaps_detected": int(len(research.gaps)),
        "research_gaps_merged_in_isolated_acceptance": int(gaps_added),
        "live_dgc_completion_gate_ready": bool(live_gate["ready_for_chapter_close"]),
        "live_dgc_open_questions": list(live_gate["open_questions"]),
        "live_gate_open_is_correct_without_analyst_closure": True,
        "closed_fixture_gate_ready": bool(closed_gate["ready_for_chapter_close"]),
        "q43_dimension_contract": int(closed_gate["q43_dimensions_total"]),
        "q46_source_lock_ok": bool(closed_gate["q46_source_lock_ok"]),
        "q47_explicit_buyback_field_available": bool(live_gate["q47_explicit_buyback_field_available"]),
        "analyst_assessment_preserved": True,
        "snapshot_persistence": "PASS",
        "report_frames_q39_q47": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "note": (
            "PASS means the research-completion workflow and source boundaries are operational. "
            "It does not mean DGC management is good/bad or that Q39-Q47 have been analyst-closed."
        ),
    }
    reports.joinpath("CHAPTER8_PHASE8F_V47_ACCEPTANCE.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    reports.joinpath("CH8_PHASE8F_DGC_E2E_V47.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
