from __future__ import annotations

"""Live DGC diagnostic for Chapter 4 Phase 4C.2.

The diagnostic measures evidence retrieval only. It never produces an investment conclusion.
External-source failures remain visible and are not replaced with synthetic evidence.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import module1_dashboard as m1
from modules.deep_company_analysis.chapter4_peer_auto import DEFAULT_MAX_PEERS, discover_same_industry_peers
from modules.deep_company_analysis.chapter4_evidence_c2 import Phase4C2Engine, c2_quality_summary, guardrails


def main() -> None:
    ticker = "DGC"
    company_name = "CTCP Tập đoàn Hóa chất Đức Giang"
    print("=== DGC CHAPTER 4 PHASE 4C.2 LIVE DIAGNOSTIC ===")
    discovery = discover_same_industry_peers(ticker, m1.RAW_DIR, max_peers=DEFAULT_MAX_PEERS)
    print(f"Target: {ticker}")
    print(f"Industry: {discovery.industry_group or 'UNKNOWN'}")
    print(f"Peer rows: {len(discovery.peers)}")
    print(f"Synthetic peer fallback: NO")

    result = Phase4C2Engine(m1.RAW_DIR).search(
        ticker,
        company_name,
        discovery.industry_group or "Hóa chất",
        discovery.peers,
    )
    print(result.note)
    print("\nQuality summary:")
    print(c2_quality_summary(result).to_string(index=False))

    print("\nQ16 pricing candidates:")
    if result.pricing_candidates.empty:
        print("- NONE — gap remains visible")
    else:
        for _, row in result.pricing_candidates.head(12).iterrows():
            print(
                f"- {row.get('Period Candidate') or '—'} | {row.get('Explicitness')} | "
                f"{row.get('Event Type Candidate')} | {row.get('Evidence Quality')} | {row.get('Title')}"
            )

    print("\nQ19 competitor universe candidates:")
    if result.competitor_universe.empty:
        print("- NONE")
    else:
        for _, row in result.competitor_universe.head(12).iterrows():
            print(f"- {row.get('Ticker')} | {row.get('Company Name')} | market cap={row.get('Market Cap (tỷ)')}")

    print("\nQ19 evidence candidates:")
    if result.competitor_evidence.empty:
        print("- NONE — gap remains visible")
    else:
        for _, row in result.competitor_evidence.head(16).iterrows():
            print(
                f"- {row.get('Subtopic')} | {row.get('Direction')} | {row.get('Evidence Quality')} | {row.get('Title')}"
            )

    flags = guardrails()
    print("\nGuardrails:")
    for key, value in flags.items():
        print(f"- {key}={value}")
    assert all(value is False for value in flags.values())
    print("Guardrail PASS: candidates only; no analyst conclusion was generated.")


if __name__ == "__main__":
    main()
