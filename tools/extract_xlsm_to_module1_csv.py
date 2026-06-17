from __future__ import annotations

"""Extract Financial/xFINN/LILU-style .xlsm data into Tổng quan doanh nghiệp normalized CSV files.

Usage:
    python tools/extract_xlsm_to_module1_csv.py "Financial-v1.3.0.xlsm" --ticker DCM --out sample_data

What this fixes versus older extractors:
- Time labels are normalized to "2024" or "Q4/2024" instead of "2024.0".
- Annual and quarterly data are de-duplicated by normalized period key.
- Chart data is sorted ascending before saving: 2016 -> 2025, Q2/2021 -> Q1/2026.
- Data is read from the workbook's ticker blocks, not by blind cell positions that can repeat years.
"""

from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.excel_financial_provider import ExcelFinancialProvider


def extract(path: Path, ticker: str, out_dir: Path) -> None:
    result = ExcelFinancialProvider(path).export_csv(ticker=ticker, out_dir=out_dir)
    print(f"Saved normalized Tổng quan doanh nghiệp CSV files to: {out_dir}")
    print(f"Overview rows: {len(result.overview)} | Annual rows: {len(result.annual)} | Quarterly rows: {len(result.quarterly)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--ticker", default="DCM")
    parser.add_argument("--out", type=Path, default=Path("sample_data"))
    args = parser.parse_args()
    extract(args.workbook, args.ticker.upper().strip(), args.out)
