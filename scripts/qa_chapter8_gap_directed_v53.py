from __future__ import annotations

"""Live DGC acceptance for Chapter 8 Phase 8H gap-directed research V53.

Engineering acceptance means the assistant converts currently open source-locked dimensions
into bounded targeted queries and preserves all analyst/SSOT boundaries. It does not require
the public web to close a specific number of gaps on every run.
"""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
import modules.deep_company_analysis.chapter8 as ch8
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_research_v53 import Chapter8ResearchAgent


REPORTS = Path("reports")
REPORTS.mkdir(parents=True, exist_ok=True)


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _open_count(frame: pd.DataFrame) -> int:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return 0
    return int((frame["Source Locked"].eq("Yes") & ~frame["Coverage Status"].eq("Candidate coverage — analyst verify")).sum())


def main() -> int:
    ticker = "DGC"
    ok, paths, canonical_note = refresh_peer_canonical_bundle(ticker)
    assert ok and paths, f"DGC canonical refresh failed: {canonical_note}"
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    company_name = _text(getattr(company, "company_name", "")) or _text(getattr(company, "name", "")) or "CTCP Tập đoàn Hóa chất Đức Giang"
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty

    bridge = build_phase8b_context(ticker, annual, chapter7_payload=None, guidance_rows=None)
    assert bridge["financial_ssot"] == "Trecapital canonical financial data / Module 1"
    assert bridge["manager_ssot"] == "Chapter 7 manager master"

    agent = Chapter8ResearchAgent("data_cache/chapter8_gap_directed_v53")
    result = agent.search(
        ticker,
        company_name,
        chapter7_payload=None,
        max_results_per_query=1,
        max_official_documents=12,
        max_gap_targets=9,
        max_gap_results_per_query=1,
    )

    targets = getattr(result, "gap_directed_targets")
    query_log = getattr(result, "gap_directed_query_log")
    new_candidates = getattr(result, "gap_directed_new_candidates")
    before = getattr(result, "gap_directed_before_coverage")
    after = getattr(result, "gap_directed_after_coverage")

    assert isinstance(targets, pd.DataFrame) and 0 < len(targets) <= 9
    assert isinstance(query_log, pd.DataFrame) and len(query_log) == len(targets)
    assert targets["Question"].isin(ch8.QUESTION_KEYS).all()
    assert "discipline_hurdle_context" not in set(targets["Dimension Key"].astype(str))
    assert targets["Boundary"].astype(str).str.contains("not a management score", case=False).all()
    assert _open_count(after) <= _open_count(before)
    if isinstance(new_candidates, pd.DataFrame) and not new_candidates.empty:
        assert new_candidates["Status"].astype(str).eq("Candidate — analyst verify").all()
        assert new_candidates["Select"].fillna(False).astype(bool).eq(False).all()
        valid_ids = set(result.manager_reference.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str))
        observed_ids = set(new_candidates.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str)) - {""}
        assert observed_ids.issubset(valid_ids), "V53 must not invent Manager IDs outside Chapter 7"

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q46_source_locked_actions"] == tuple(ch8.CAPITAL_ALLOCATION_ACTIONS)
    assert locks["q47_share_count_is_proof"] is False

    q46 = bridge.get("q46_capital_allocation_context")
    latest_period = _text(q46.iloc[-1].get("Kỳ")) if isinstance(q46, pd.DataFrame) and not q46.empty else ""

    targets.to_csv(REPORTS / "CH8_DGC_GAP_TARGETS_V53.csv", index=False, encoding="utf-8-sig")
    query_log.to_csv(REPORTS / "CH8_DGC_GAP_QUERY_LOG_V53.csv", index=False, encoding="utf-8-sig")
    new_candidates.to_csv(REPORTS / "CH8_DGC_GAP_DIRECTED_NEW_CANDIDATES_V53.csv", index=False, encoding="utf-8-sig")
    before.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_BEFORE_V53.csv", index=False, encoding="utf-8-sig")
    after.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_AFTER_V53.csv", index=False, encoding="utf-8-sig")
    result.gaps.to_csv(REPORTS / "CH8_DGC_REMAINING_GAPS_V53.csv", index=False, encoding="utf-8-sig")

    output = {
        "phase": "Chapter 8 Phase 8H Gap-Directed Research V53",
        "acceptance": "PASS",
        "acceptance_meaning": "Open source-locked dimensions are converted into bounded targeted research; candidates remain analyst-verify and are never auto-promoted.",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "gap_targets_planned": int(len(targets)),
        "target_queries_attempted": int(query_log["Status"].astype(str).str.startswith("Attempted").sum()),
        "gap_directed_new_candidates": int(len(new_candidates)),
        "open_source_locked_dimensions_before": _open_count(before),
        "open_source_locked_dimensions_after": _open_count(after),
        "remaining_research_gaps": int(len(result.gaps)),
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q47_share_count_decline_is_not_buyback_proof": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "research_note": result.note,
    }
    (REPORTS / "CH8_DGC_GAP_DIRECTED_ACCEPTANCE_V53.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
