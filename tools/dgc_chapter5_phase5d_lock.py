from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter5 import empty_payload
from modules.deep_company_analysis.chapter5_evidence import Chapter5EvidenceAgent, research_gaps
from modules.deep_company_analysis.chapter5_lock import (
    dgc_lock_acceptance,
    evaluate_chapter5_lock,
    guardrails as lock_guardrails,
)
from modules.deep_company_analysis.chapter5_quant import build_chapter5_quant_context


def _build_live_quant_context(ticker: str) -> dict:
    ok, paths, note = refresh_peer_canonical_bundle(ticker)
    print("Canonical refresh:", note)
    assert ok and paths, "DGC canonical refresh failed; no fallback ticker/data is allowed."
    overview_path, annual_path, quarter_path = paths
    company = m1._load_overview_cached(str(overview_path), ticker)
    annual_raw = m1._load_timeseries_cached(str(annual_path), ticker, "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter_path), ticker, "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    assert isinstance(annual, pd.DataFrame) and not annual.empty, "DGC canonical annual bundle is empty."
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    ctx = build_chapter5_quant_context(
        ticker,
        company_name,
        annual,
        source_label="FireAnt + Vietstock",
        adjustments=[],
    )
    print("Canonical latest period:", ctx.get("latest_period"))
    print("Canonical ROIC latest:", ctx.get("canonical_roic_latest"))
    print("Canonical provenance:", ctx.get("provenance"))
    return ctx


def main() -> None:
    ticker = "DGC"
    company_name = "CTCP Tập đoàn Hóa chất Đức Giang"
    raw_dir = ROOT / "data_cache" / "deep_company_analysis_phase5d_ci"

    print("=== DGC CHAPTER 5 PHASE 5D END-TO-END LOCK ===")
    quant_ctx = _build_live_quant_context(ticker)

    evidence = Chapter5EvidenceAgent(raw_dir).search(ticker, company_name, max_results_per_query=3)
    print(evidence.note)
    print("Evidence candidates:", len(evidence.candidates))
    if not evidence.candidates.empty:
        print(evidence.candidates.groupby(["Question", "Evidence Quality"]).size().to_string())

    record = empty_payload(ticker, company_name)
    # Put real analyst-owned values in the record to prove the lock/research merge cannot overwrite them.
    record["q21"]["overall_assessment"] = "Stable"
    record["q21"]["conclusion"] = "DGC manual analyst test conclusion"
    record["q23_risks"][0]["Frequency"] = "Rare"
    record["q23_risks"][0]["Severity"] = "High"
    record["q25"]["balance_sheet_assessment"] = "Strong"
    record["q26"]["current_roic_quality"] = "High"
    before = deepcopy(record)

    gaps = research_gaps(evidence.candidates, quant_ctx)
    print("Phase 5C suggested research gaps:", len(gaps))

    report = evaluate_chapter5_lock(record, quant_ctx, evidence.candidates)
    print("Implementation status:", report.implementation_status)
    print(report.implementation_checks.to_string(index=False))
    print("Research readiness:")
    print(report.research_readiness.to_string(index=False))
    print("Cross-question diagnostics:", list(report.cross_question_diagnostics))

    ok, failures = dgc_lock_acceptance(record, quant_ctx, evidence.candidates)
    if failures:
        print("Acceptance failures:")
        for item in failures:
            print(" -", item)
    assert ok, f"DGC Phase 5D acceptance failed: {failures}"
    assert report.passed
    assert record == before, "Phase 5D evaluation mutated analyst-owned record."
    assert all(value is False for value in lock_guardrails().values())
    assert report.research_readiness["Readiness"].astype(str).str.startswith("Research-ready").all()

    # Counter-evidence may legitimately be absent. Absence must remain explicit and must not be synthesized.
    zero_counter = report.research_readiness["Counter-Evidence Candidates"].eq(0)
    print("Questions with zero counter-evidence candidates:", report.research_readiness.loc[zero_counter, "Question"].tolist())
    print("PASS: Chapter 5 implementation is locked; DGC has canonical Q22/Q25/Q26 context and real source-first evidence Q21–Q26.")
    print("PASS DOES NOT MEAN investment quality, Research Gate, BUY/HOLD/SELL, or analyst completion.")


if __name__ == "__main__":
    main()
