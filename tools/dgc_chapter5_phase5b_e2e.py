from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter4_peer_auto import refresh_peer_canonical_bundle
from modules.deep_company_analysis.chapter4_peer_selection import build_peer_selection_table, selected_peer_tickers
from modules.deep_company_analysis.chapter5 import RISK_COLUMNS, RISK_UI_COLUMNS
from modules.deep_company_analysis.chapter5_quant import build_chapter5_quant_context


def main() -> None:
    print("=== DGC CHAPTER 5 PHASE 5B + CH4 PEER CURATION DIAGNOSTIC ===")
    assert "Origin" in RISK_COLUMNS and "Origin" not in RISK_UI_COLUMNS
    print("Q23 Origin hidden from UI: PASS")

    discovered = pd.DataFrame([
        {"ticker": "DGC", "company_name": "Duc Giang", "industry": "Hóa chất"},
        {"ticker": "DCM", "company_name": "Ca Mau Fertilizer", "industry": "Hóa chất"},
        {"ticker": "CSV", "company_name": "South Basic Chemicals", "industry": "Hóa chất"},
    ])
    selection = build_peer_selection_table(discovered, "DGC")
    selection.loc[selection["Ticker"] == "CSV", "Use?"] = False
    selection = pd.concat([selection, pd.DataFrame([{"Use?": True, "Ticker": "LAS"}])], ignore_index=True)
    selected = selected_peer_tickers(selection, "DGC")
    assert selected[0] == "DGC" and "CSV" not in selected and "LAS" in selected
    print("Analyst-curated peer selection before refresh: PASS", selected)

    ok, paths, note = refresh_peer_canonical_bundle("DGC")
    print(note)
    assert ok and paths, "DGC canonical refresh failed; no synthetic fallback is allowed."
    overview, year, quarter = paths
    company = m1._load_overview_cached(str(overview), "DGC")
    annual_raw = m1._load_timeseries_cached(str(year), "DGC", "Y", 11)
    quarterly = m1._load_timeseries_cached(str(quarter), "DGC", "Q", 20)
    annual = append_ttm_row(annual_raw, quarterly)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    ctx = build_chapter5_quant_context("DGC", company_name, annual, source_label="DGC live canonical")

    assert ctx and isinstance(ctx.get("q22_context"), pd.DataFrame) and not ctx["q22_context"].empty
    assert ctx.get("canonical_roic_latest") is not None
    assert all(value is False for value in ctx.get("guardrails", {}).values())
    print("DGC company:", company_name)
    print("Data period:", ctx.get("latest_period"))
    print("Q22 rows:", len(ctx["q22_context"]))
    print("Q25 rows:", len(ctx.get("q25_context", pd.DataFrame())))
    print("Canonical ROIC latest:", ctx.get("canonical_roic_latest"))
    print("ROIC variants:")
    print(ctx["q26_variants"][["ROIC View", "Value %", "Status / Requirement"]].to_string(index=False))
    print("Guardrails:", ctx["guardrails"])
    print("PASS: Phase 5B consumes canonical data and generates no automatic investment conclusion.")


if __name__ == "__main__":
    main()
