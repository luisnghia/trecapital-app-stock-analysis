from __future__ import annotations

"""Chapter 8 Phase 8D V45 acceptance runner.

Uses live DGC canonical refresh, then validates structured bridge + analyst-owned
promotion/persistence/snapshot without running a second live web research crawl.
"""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
import modules.deep_company_analysis.chapter8 as ch8
import modules.deep_company_analysis.chapter8_store as store
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_research import CANDIDATE_COLUMNS
from modules.deep_company_analysis.chapter8_workspace import merge_research_gaps, promote_selected_candidates
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle


def main() -> int:
    ticker = "DGC"
    ok, paths, note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, f"DGC canonical refresh failed: {note}"
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"
    assert not bridge["q46_capital_allocation_context"].empty
    assert len(ch8.CAPITAL_ALLOCATION_ACTIONS) == 5

    company_name = str(getattr(company, "company_name", "") or "CTCP Tập đoàn Hóa chất Đức Giang")
    payload = ch8.empty_payload(ticker, company_name)
    payload["analyst_assessment"]["Q39"] = "Acceptance sentinel — analyst owned"
    row = {column: "" for column in CANDIDATE_COLUMNS}
    row.update({
        "Select": True,
        "Candidate ID": "v45-acceptance",
        "Question": "Q39",
        "Subtopic": "Employees",
        "Direction": "Supporting cue — analyst assess",
        "Source Grade": "A — Company/Official disclosure",
        "Source Title": "DGC official disclosure",
        "Source URL / File": "https://ducgiangchem.vn/",
        "As-of Date": "2026",
        "Evidence Text / Reference": "Acceptance candidate for manual promotion contract.",
        "Data Origin": "Synthetic acceptance candidate — not investment evidence",
        "Status": "Candidate — analyst verify",
    })
    promoted, added = promote_selected_candidates(payload, pd.DataFrame([row]))
    assert added == 1
    assert promoted["analyst_assessment"]["Q39"] == "Acceptance sentinel — analyst owned"

    gaps = pd.DataFrame([{
        "Question": "Q47", "Manager ID": "", "Manager": "",
        "Research Gap": "Explicit buyback authorization/execution not established by acceptance fixture.",
        "Materiality": "Analyst decide",
        "Next Action": "Verify original disclosures.",
        "Status": "Open — evidence gap", "Analyst Note": "",
    }])
    promoted, gap_added = merge_research_gaps(promoted, gaps)
    assert gap_added == 1

    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    original_db = store.DB_PATH
    try:
        store.DB_PATH = reports / "chapter8_phase8d_v45_acceptance.sqlite"
        if store.DB_PATH.exists():
            store.DB_PATH.unlink()
        saved = store.save_record(ticker, promoted, company_name)
        loaded = store.load_record(ticker)
        snapshot_id = store.create_snapshot(ticker, loaded)
        assert loaded["analyst_assessment"]["Q39"] == "Acceptance sentinel — analyst owned"
        assert snapshot_id >= 1
    finally:
        store.DB_PATH = original_db

    latest = ""
    q46 = bridge["q46_capital_allocation_context"]
    if not q46.empty:
        latest = str(q46.iloc[-1].get("Kỳ") or "")

    out = {
        "phase": "Chapter 8 Phase 8D Streamlit Analyst Workspace V45",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(note),
        "latest_period": latest,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "capital_allocation_source_locked_actions": len(ch8.CAPITAL_ALLOCATION_ACTIONS),
        "promoted_evidence": int(added),
        "research_gaps_added": int(gap_added),
        "analyst_assessment_preserved": True,
        "snapshot_persistence": "PASS",
        "automatic_management_score": False,
        "automatic_investment_signal": False,
    }
    reports.joinpath("CHAPTER8_PHASE8D_V45_ACCEPTANCE.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
