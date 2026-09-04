from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.deep_company_analysis.chapter5 import empty_payload
from modules.deep_company_analysis.chapter5_evidence import (
    Chapter5EvidenceAgent,
    candidate_coverage,
    evidence_quality_summary,
    guardrails,
    merge_candidates_into_record,
    research_gaps,
)


def main() -> None:
    ticker = "DGC"
    company_name = "CTCP Tập đoàn Hóa chất Đức Giang"
    raw_dir = ROOT / "data_cache" / "deep_company_analysis_evidence_ci"

    print("=== DGC CHAPTER 5 PHASE 5C SOURCE-FIRST DIAGNOSTIC ===")
    result = Chapter5EvidenceAgent(raw_dir).search(ticker, company_name, max_results_per_query=3)
    print(result.note)
    print("Coverage:", candidate_coverage(result.candidates))
    print(evidence_quality_summary(result.candidates).to_string(index=False))

    assert not result.candidates.empty, "No real DGC candidate evidence found; synthetic fallback is forbidden."
    assert result.candidates["Evidence Quality"].astype(str).str.startswith("A —").any(), "DGC diagnostic requires at least one first-party/official evidence candidate."
    assert set(result.candidates["Question"]).issubset({"Q21", "Q22", "Q23", "Q24", "Q25", "Q26"})
    assert all(value is False for value in guardrails().values())

    # Verify the Research Assistant cannot overwrite analyst judgement or manual registers.
    record = empty_payload(ticker, company_name)
    record["q21"]["overall_assessment"] = "Stable"
    record["q21"]["conclusion"] = "Manual DGC analyst conclusion"
    record["q23_risks"][0]["Frequency"] = "Rare"
    record["q23_risks"][0]["Severity"] = "High"
    record["q25"]["balance_sheet_assessment"] = "Strong"
    record["q26"]["current_roic_quality"] = "High"
    before = deepcopy(record)

    gaps = research_gaps(result.candidates)
    merged = merge_candidates_into_record(record, result.candidates, gaps)
    for key in (
        "q21", "q22", "q23", "q24", "q25", "q26",
        "q21_fundamentals", "q22_metrics", "q22_metric_history", "q23_risks",
        "q24_inflation_exposures", "q25_debt_instruments", "q25_covenants",
        "q25_off_balance_obligations", "q26_roic_adjustments", "q26_reinvestment",
    ):
        assert merged[key] == before[key], f"Research Assistant overwrote analyst-owned field: {key}"

    assert merged["evidence_matrix"], "Candidate evidence was not appended."
    assert all(str(row.get("Status")) == "Candidate — Analyst verify" for row in merged["evidence_matrix"])
    print("Research gaps:", len(gaps))
    for gap in gaps:
        print(" -", gap["Question"], gap["Research Gap"])
    print("Guardrails:", guardrails())
    print("PASS: DGC Phase 5C uses real source-first evidence, preserves analyst judgement, and emits no automatic investment conclusion.")


if __name__ == "__main__":
    main()
