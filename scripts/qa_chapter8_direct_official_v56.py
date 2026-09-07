from __future__ import annotations

"""Live DGC acceptance for Chapter 8 Phase 8K direct official URL ingestion V56."""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import build_dimension_coverage, validate_source_locks
from modules.deep_company_analysis.chapter8_official_source_adapters import (
    DGC_ACCEPTANCE_OFFICIAL_URLS,
    OfficialURLIngestionAgent,
)
from modules.deep_company_analysis.chapter8_research_v55 import Chapter8ResearchAgent as V55ResearchAgent


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
    assert ok and paths, canonical_note
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

    baseline = V55ResearchAgent("data_cache/chapter8_direct_official_v56/baseline").search(
        ticker,
        company_name,
        chapter7_payload=None,
        max_results_per_query=1,
        max_official_documents=8,
        max_gap_targets=6,
        max_gap_results_per_query=1,
        max_deep_targets=48,
        max_deep_index_pages=8,
        max_deep_documents=16,
        max_deep_depth=2,
        max_archive_queries=6,
        max_archive_results_per_query=1,
        max_archive_documents=8,
    )
    before = build_dimension_coverage(baseline.candidates)

    direct = OfficialURLIngestionAgent("data_cache/chapter8_direct_official_v56/direct").ingest(
        ticker,
        DGC_ACCEPTANCE_OFFICIAL_URLS,
        existing_candidates=baseline.candidates,
        manager_reference=baseline.manager_reference,
        max_targets=48,
        max_urls=10,
    )

    assert isinstance(direct.attempts, pd.DataFrame) and len(direct.attempts) == len(DGC_ACCEPTANCE_OFFICIAL_URLS)
    assert direct.attempts["Official"].eq("Yes").all()
    fetched = direct.attempts[direct.attempts["Status"].eq("Fetched")]
    assert not fetched.empty, "At least one direct official DGC disclosure must be retrievable"
    assert fetched["Ticker Match"].eq("Yes").all()
    assert _open_count(direct.after_coverage) <= _open_count(direct.before_coverage)

    if not direct.new_candidates.empty:
        assert direct.new_candidates["Status"].eq("Candidate — analyst verify").all()
        assert direct.new_candidates["Select"].eq(False).all()
        valid_ids = set(baseline.manager_reference.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str))
        observed = set(direct.new_candidates.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str)) - {""}
        assert observed.issubset(valid_ids)

    locks = validate_source_locks()
    assert locks["q43_dimension_count"] == 14
    assert locks["q46_source_locked_count"] == 5
    assert locks["q47_share_count_is_proof"] is False

    q46 = bridge.get("q46_capital_allocation_context")
    latest_period = _text(q46.iloc[-1].get("Kỳ")) if isinstance(q46, pd.DataFrame) and not q46.empty else ""

    direct.attempts.to_csv(REPORTS / "CH8_DGC_DIRECT_OFFICIAL_ATTEMPTS_V56.csv", index=False, encoding="utf-8-sig")
    direct.documents.to_csv(REPORTS / "CH8_DGC_DIRECT_OFFICIAL_DOCUMENTS_V56.csv", index=False, encoding="utf-8-sig")
    direct.new_candidates.to_csv(REPORTS / "CH8_DGC_DIRECT_OFFICIAL_NEW_CANDIDATES_V56.csv", index=False, encoding="utf-8-sig")
    direct.before_coverage.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_BEFORE_V56.csv", index=False, encoding="utf-8-sig")
    direct.after_coverage.to_csv(REPORTS / "CH8_DGC_DIMENSION_COVERAGE_AFTER_V56.csv", index=False, encoding="utf-8-sig")
    direct.remaining_gaps.to_csv(REPORTS / "CH8_DGC_REMAINING_GAPS_V56.csv", index=False, encoding="utf-8-sig")

    output = {
        "phase": "Chapter 8 Phase 8K Direct Official Source Adapters V56",
        "acceptance": "PASS",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "direct_official_urls_supplied": len(DGC_ACCEPTANCE_OFFICIAL_URLS),
        "direct_official_urls_fetched": int(len(fetched)),
        "direct_official_documents_retained": int(len(direct.documents)),
        "direct_official_new_candidates": int(len(direct.new_candidates)),
        "open_source_locked_dimensions_before_direct": _open_count(direct.before_coverage),
        "open_source_locked_dimensions_after_direct": _open_count(direct.after_coverage),
        "remaining_research_gaps": int(len(direct.remaining_gaps)),
        "q43_dimension_contract": locks["q43_dimension_count"],
        "q46_source_locked_actions": locks["q46_source_locked_count"],
        "q47_share_count_decline_is_not_buyback_proof": True,
        "automatic_management_score": False,
        "automatic_investment_signal": False,
        "auto_promoted_evidence": False,
        "analyst_workspace_mutated": False,
        "research_note": direct.note,
    }
    (REPORTS / "CH8_DGC_DIRECT_OFFICIAL_ACCEPTANCE_V56.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
