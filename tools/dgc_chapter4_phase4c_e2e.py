from __future__ import annotations

"""Live diagnostic for Chapter 4 Phase 4C.1 using DGC.

This is an audit diagnostic, not an investment conclusion. External-source failures are reported
explicitly instead of being replaced with synthetic peers or fabricated financials/evidence.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.deep_company_analysis.chapter4_peer_auto import (
    DEFAULT_MAX_PEERS,
    discover_same_industry_peers,
    refresh_peer_canonical_universe,
)
from modules.deep_company_analysis.chapter4_evidence import (
    Chapter4EvidenceAgent,
    candidate_coverage,
    evidence_quality_summary,
    research_gaps,
)

import module1_dashboard as m1


def main() -> None:
    ticker = "DGC"
    print("=== DGC CHAPTER 4 PHASE 4C.1 LIVE DIAGNOSTIC ===")
    discovery = discover_same_industry_peers(ticker, m1.RAW_DIR, max_peers=DEFAULT_MAX_PEERS)
    print(f"Target: {discovery.target}")
    print(f"Industry: {discovery.industry_group or 'UNKNOWN'}")
    print(f"Peer rows discovered: {len(discovery.peers)}")
    print(f"Peer tickers: {', '.join(discovery.tickers[:60])}")
    print(f"Discovery note: {discovery.note}")
    print("Synthetic fallback: NO")

    sample = discovery.tickers[:3]
    print(f"Canonical refresh diagnostic sample: {', '.join(sample)}")
    results = refresh_peer_canonical_universe(sample, max_workers=3)
    successes = 0
    for peer, ok, paths, note in results:
        successes += int(ok)
        print(f"- {peer}: {'OK' if ok else 'MISSING'} | {note}")
        if paths:
            print("  paths:", " | ".join(str(Path(p)) for p in paths))
    print(f"Canonical sample success: {successes}/{len(sample)}")

    evidence = Chapter4EvidenceAgent(m1.RAW_DIR).search(
        ticker,
        "CTCP Tập đoàn Hóa chất Đức Giang",
        discovery.industry_group or "Hóa chất",
        max_results_per_query=3,
    )
    coverage = candidate_coverage(evidence.candidates)
    print(f"Evidence candidates: {len(evidence.candidates)}")
    print("Evidence coverage:", " | ".join(f"{q}={coverage[q]}" for q in coverage))
    if not evidence.candidates.empty:
        source_a = int(evidence.candidates["Evidence Quality"].astype(str).str.startswith("A —").sum())
        print(f"Source-A candidates: {source_a}")
        methods = evidence.candidates["Source Method"].astype(str).value_counts().to_dict() if "Source Method" in evidence.candidates.columns else {}
        print("Source methods:", methods)
        for _, row in evidence.candidates.head(18).iterrows():
            print(
                f"- {row.get('Question')} | {row.get('Subtopic')} | {row.get('Direction')} | "
                f"{row.get('Evidence Quality')} | {row.get('Source Method')} | {row.get('Title')}"
            )
    print("Quality summary:")
    summary = evidence_quality_summary(evidence.candidates)
    for _, row in summary.iterrows():
        print(
            f"- {row.get('Question')}: candidates={row.get('Candidates')} | A={row.get('Nguồn A')} | "
            f"B={row.get('Nguồn B')} | counter={row.get('Counter')} | status={row.get('Coverage Status')}"
        )
    gaps = research_gaps(evidence.candidates)
    print(f"Research gaps: {len(gaps)}")
    for gap in gaps:
        print(f"- {gap}")
    print(f"Evidence note: {evidence.note}")
    print("Guardrail: candidates only; no analyst conclusion was generated.")


if __name__ == "__main__":
    main()
