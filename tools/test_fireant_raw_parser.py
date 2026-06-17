from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.vn_public_crawler import _normalize_from_payloads


def main() -> None:
    parser = argparse.ArgumentParser(description="Test FireAnt parser against saved fireant_*.json raw files.")
    parser.add_argument("raw_dir", help="Folder containing fireant_DGC_json_*.json or crawler raw JSON files")
    parser.add_argument("--ticker", default="DGC")
    args = parser.parse_args()

    paths = sorted(glob.glob(str(Path(args.raw_dir) / f"fireant_{args.ticker.upper()}_json_*.json")))
    if not paths:
        paths = sorted(glob.glob(str(Path(args.raw_dir) / "fireant_*_json_*.json")))
    payloads = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            # Skip error-only HTTP diagnostic payloads.
            if isinstance(obj, dict) and obj.get("Message"):
                continue
            payloads.append(obj)
        except Exception as exc:
            print(f"SKIP {path}: {exc}")
    result = _normalize_from_payloads(payloads, [], args.ticker.upper(), "FireAnt")
    print("FIREANT_RAW_PARSER_OK")
    print(f"overview={len(result.overview)} annual={len(result.annual)} quarterly={len(result.quarterly)}")
    if not result.overview.empty:
        keep = [c for c in ["ticker", "company_name", "exchange", "current_price", "eps", "pe", "pb", "ps", "roe", "roa", "roic"] if c in result.overview.columns]
        print(result.overview[keep].to_string(index=False))
    if not result.annual.empty:
        keep = [c for c in ["period", "revenue_bil", "net_profit_bil", "cash_dividend_yield_pct", "cfo_bil", "capex_bil", "free_cash_flow_bil", "eps_vnd", "oeps_vnd", "roe_pct", "roe_actual_pct", "roic_pct", "roe_dupont_pct"] if c in result.annual.columns]
        print(result.annual[keep].tail(10).to_string(index=False))
    if not result.quarterly.empty:
        keep = [c for c in ["period", "revenue_bil", "net_profit_bil", "cash_dividend_yield_pct", "cfo_bil", "capex_bil", "free_cash_flow_bil", "eps_vnd", "oeps_vnd", "roe_pct", "roe_actual_pct", "roic_pct", "roe_dupont_pct"] if c in result.quarterly.columns]
        print(result.quarterly[keep].tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
