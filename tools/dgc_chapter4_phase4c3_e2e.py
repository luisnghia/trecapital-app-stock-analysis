from __future__ import annotations

"""Live DGC diagnostic for Chapter 4 Phase 4C.3.

The diagnostic measures evidence coverage/corroboration only.  It never produces an investment
conclusion. External-source failures remain visible and are not replaced with synthetic evidence.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import module1_dashboard as m1
from modules.deep_company_analysis.chapter4_peer_auto import DEFAULT_MAX_PEERS, discover_same_industry_peers
from modules.deep_company_analysis.chapter4_evidence_c3 import Phase4C3Engine, guardrails


def main() -> None:
    ticker = "DGC"
    company_name = "CTCP Tập đoàn Hóa chất Đức Giang"
    print("=== DGC CHAPTER 4 PHASE 4C.3 LIVE DIAGNOSTIC ===")
    discovery = discover_same_industry_peers(ticker, m1.RAW_DIR, max_peers=DEFAULT_MAX_PEERS)
    print(f"Target: {ticker}")
    print(f"Industry: {discovery.industry_group or 'UNKNOWN'}")
    print(f"Peer rows: {len(discovery.peers)}")
    print("Synthetic peer fallback: NO")

    result = Phase4C3Engine(m1.RAW_DIR).search(
        ticker,
        company_name,
        discovery.industry_group or "Hóa chất",
        discovery.peers,
    )
    print(result.note)

    print("\nQ16 corroboration:")
    if result.pricing_corroboration.empty:
        print("- NONE — gap remains visible")
    else:
        print(result.pricing_corroboration.to_string(index=False))

    print("\nQ19 full Shearn coverage:")
    print(result.q19_coverage.to_string(index=False))

    print("\nResearch gaps:")
    if not result.gaps:
        print("- NONE at machine-detectable coverage level; analyst verification is still required")
    else:
        for gap in result.gaps:
            print(f"- {gap}")

    print("\nQ19 multi-label evidence sample:")
    if result.q19_evidence.empty:
        print("- NONE")
    else:
        for _, row in result.q19_evidence.head(24).iterrows():
            print(
                f"- {row.get('Subtopic')} | {row.get('Direction')} | {row.get('Evidence Quality')} | "
                f"{row.get('Title')}"
            )

    flags = guardrails()
    print("\nGuardrails:")
    for key, value in flags.items():
        print(f"- {key}={value}")
    assert all(value is False for value in flags.values())
    print("Guardrail PASS: coverage/corroboration candidates only; no analyst conclusion was generated.")


if __name__ == "__main__":
    main()
