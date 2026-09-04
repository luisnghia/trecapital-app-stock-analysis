from __future__ import annotations

"""Live DGC acceptance diagnostic for Chapter 4 Phase 4D lock.

The tool validates the research system, evidence hygiene and guardrails.  It never produces a moat,
Pricing Power, industry-quality, competition-intensity or investment recommendation.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import module1_dashboard as m1
from modules.deep_company_analysis.chapter4_peer_auto import DEFAULT_MAX_PEERS, discover_same_industry_peers
from modules.deep_company_analysis.chapter4_evidence_c3 import Phase4C3Engine
from modules.deep_company_analysis.chapter4_lock import build_lock_audit, guardrail_audit


def main() -> None:
    ticker = "DGC"
    company_name = "CTCP Tập đoàn Hóa chất Đức Giang"
    print("=== DGC CHAPTER 4 PHASE 4D FINAL LOCK DIAGNOSTIC ===")
    discovery = discover_same_industry_peers(ticker, m1.RAW_DIR, max_peers=DEFAULT_MAX_PEERS)
    industry = discovery.industry_group or "Hóa chất"
    print(f"Target: {ticker}")
    print(f"Industry: {industry}")
    print(f"Peer rows: {len(discovery.peers)}")
    print("Synthetic peer fallback: NO")

    result = Phase4C3Engine(m1.RAW_DIR).search(
        ticker,
        company_name,
        industry,
        discovery.peers,
    )
    audit = build_lock_audit(result, ticker, company_name, industry)
    print(result.note)
    print(audit.note)

    print("\nFinal acceptance checks:")
    print(audit.checks.to_string(index=False))

    print("\nEvidence hygiene:")
    print(f"- retained candidates: {len(audit.retained_candidates)}")
    print(f"- quarantined candidates: {len(audit.quarantined_candidates)}")
    if not audit.quarantined_candidates.empty:
        for _, row in audit.quarantined_candidates.head(10).iterrows():
            print(f"  * {row.get('Quarantine Reason')} | {row.get('Title')}")

    print("\nQ19 A/B lock coverage:")
    print(audit.q19_coverage.to_string(index=False))

    print("\nLegitimate competitor-failure evidence:")
    if audit.failure_candidates.empty:
        print("- NONE — stock-specific Research Gap remains explicit; no evidence fabricated.")
    else:
        for _, row in audit.failure_candidates.head(10).iterrows():
            print(f"- {row.get('Evidence Quality')} | {row.get('Title')} | {row.get('URL')}")

    print("\nOpen stock-specific research gaps:")
    if not audit.research_gaps:
        print("- NONE")
    else:
        for gap in audit.research_gaps:
            print(f"- {gap}")

    print("\nGuardrails:")
    flags = guardrail_audit()
    for key, value in flags.items():
        print(f"- {key}={value}")
    assert all(value is False for value in flags.values())
    assert audit.lock_ready, audit.note
    print("\nCHAPTER 4 LOCK ACCEPTANCE: PASS")
    print("LOCK meaning: implementation/persistence/evidence guardrails are frozen; stock-specific gaps may remain visible for analyst research.")


if __name__ == "__main__":
    main()
