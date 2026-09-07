from __future__ import annotations

"""Live DGC acceptance for Chapter 8 Phase 8K direct official URL ingestion V56.

The exchange/CDN can block GitHub-hosted runners or respond intermittently. Acceptance therefore
verifies the direct-source contract, canonical DGC context, official-domain allow-list, bounded
fetch attempts, ticker validation and analyst boundaries. A fixed count of live-fetched documents
is deliberately not required; unavailable official sources remain logged gaps rather than being
fabricated.
"""

import json
from pathlib import Path

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter8_data_bridge import build_phase8b_context
from modules.deep_company_analysis.chapter8_gap_engine import validate_source_locks
from modules.deep_company_analysis.chapter8_official_source_adapters import (
    DGC_ACCEPTANCE_OFFICIAL_URLS,
    OfficialURLIngestionAgent,
    is_official_url,
)


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
    manager_reference = bridge.get("manager_reference", pd.DataFrame())
    if not isinstance(manager_reference, pd.DataFrame):
        manager_reference = pd.DataFrame()

    # One current public HOSE-hosted DGC disclosure is enough to exercise the live transport.
    # The deterministic tests cover multiple URLs, wrong-ticker rejection and extraction behavior.
    live_urls = list(DGC_ACCEPTANCE_OFFICIAL_URLS[:1])
    assert live_urls and all(is_official_url(url, ticker) for url in live_urls)

    direct = OfficialURLIngestionAgent("data_cache/chapter8_direct_official_v56/direct").ingest(
        ticker,
        live_urls,
        existing_candidates=pd.DataFrame(),
        manager_reference=manager_reference,
        max_targets=48,
        max_urls=1,
    )

    assert isinstance(direct.attempts, pd.DataFrame) and len(direct.attempts) == len(live_urls)
    assert direct.attempts["Official"].eq("Yes").all()
    fetched = direct.attempts[direct.attempts["Status"].eq("Fetched")]
    if not fetched.empty:
        assert fetched["Ticker Match"].eq("Yes").all()
    assert _open_count(direct.after_coverage) <= _open_count(direct.before_coverage)

    if not direct.new_candidates.empty:
        assert direct.new_candidates["Status"].eq("Candidate — analyst verify").all()
        assert direct.new_candidates["Select"].eq(False).all()
        valid_ids = set(manager_reference.get("Manager ID", pd.Series(dtype="object")).fillna("").astype(str))
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
        "acceptance_meaning": "DGC canonical context and direct official-source ingestion contract pass. Live exchange/CDN availability is observed, not assumed; inaccessible sources remain logged gaps.",
        "ticker": ticker,
        "company_name": company_name,
        "canonical_refresh_ok": True,
        "canonical_note": str(canonical_note),
        "latest_period": latest_period,
        "financial_ssot": bridge["financial_ssot"],
        "manager_ssot": bridge["manager_ssot"],
        "direct_official_urls_supplied": len(live_urls),
        "direct_official_urls_fetched": int(len(fetched)),
        "direct_official_network_available_in_ci": bool(len(fetched)),
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
