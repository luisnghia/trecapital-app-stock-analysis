from __future__ import annotations

from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from modules.investment_checklist.industry_overlay import (
    QUESTION_MAP,
    build_driver_coverage,
    build_industry_kpi_table,
    build_metric_coverage,
)


def test_normal_overlay_uses_sign_safe_cash_conversion():
    df = pd.DataFrame([
        {"period": "2024", "period_type": "Y", "year": 2024, "revenue_bil": 1000, "net_profit_bil": 100, "cfo_bil": 120, "free_cash_flow_bil": 80},
        {"period": "2025", "period_type": "Y", "year": 2025, "revenue_bil": 900, "net_profit_bil": -50, "cfo_bil": -30, "free_cash_flow_bil": -40},
    ])
    out = build_industry_kpi_table(df, "cyclical")
    assert out.iloc[0]["CFO/LNST"] == 1.2
    assert pd.isna(out.iloc[1]["CFO/LNST"])


def test_bank_overlay_uses_bank_kpis_and_does_not_surface_industrial_fcf_ccc():
    df = pd.DataFrame([{"period": "TTM", "nim_pct": 3.7, "casa_pct": 28.2, "npl_pct": 1.4, "roe_pct": 18.1}])
    out = build_industry_kpi_table(df, "bank")
    assert {"NIM", "CASA", "NPL", "ROE"}.issubset(out.columns)
    assert "FCF" not in out.columns
    assert "CCC" not in out.columns
    assert "CFO/LNST" not in out.columns


def test_overlay_exposes_metric_and_driver_research_gaps():
    df = pd.DataFrame([{"period": "2025", "revenue_bil": 100}])
    coverage = build_metric_coverage(df, "normal")
    assert set(coverage["Trạng thái"]) == {"Có dữ liệu", "Research gap"}
    drivers = build_driver_coverage(df, "normal")
    assert drivers.loc[drivers["Field"].eq("revenue_bil"), "Trạng thái"].iloc[0] == "Có dữ liệu"
    assert "Research gap" in set(drivers["Trạng thái"])
    assert {"Q15–Q20", "Q22–Q26", "Q29–Q32", "Q55–Q57"} == set(QUESTION_MAP["Cụm câu hỏi"])


def test_phase3a_is_single_source_and_top_level_navigation_contract():
    engine = Path("modules/investment_checklist/industry_overlay.py").read_text(encoding="utf-8").lower()
    ui = Path("modules/investment_checklist/ui/industry_overlay.py").read_text(encoding="utf-8")
    shell = Path("modules/investment_checklist/ui/integration_preview.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import httpx", "urllib.request", "openai", "anthropic"):
        assert forbidden not in engine
    assert '"🏭 Industry & Moat"' in shell
    assert "build_porter_moat_scorecard" in ui
    assert "build_value_chain_table" in ui
    assert "không tự ghi assessment" in ui
    assert "_render_responsive_table" in ui
    assert "white-space:normal!important" in ui
    assert "overflow-wrap:anywhere" in ui
    assert "-webkit-overflow-scrolling:touch" in ui
    assert "st.html(markup)" in ui
    assert "st.markdown(\n        markup" not in ui


def test_phase3a_streamlit_overlay_renders_without_exception():
    app = r'''
from types import SimpleNamespace
import pandas as pd
from modules.investment_checklist.ui.industry_overlay import render_industry_overlay

class Provider:
    annual_df = pd.DataFrame([
        {"period":"2024","period_type":"Y","year":2024,"revenue_bil":1000,"gross_profit_bil":300,"net_profit_bil":100,"cfo_bil":120,"free_cash_flow_bil":80,"ebitda_bil":180,"net_debt_bil":100},
        {"period":"2025","period_type":"Y","year":2025,"revenue_bil":1100,"gross_profit_bil":340,"net_profit_bil":110,"cfo_bil":130,"free_cash_flow_bil":90,"ebitda_bil":200,"net_debt_bil":80},
    ])
class Integration:
    def get_inventory_prefill(self):
        return SimpleNamespace(market_cap=2000, shares_outstanding_mil=100, market_price=20000)
host = SimpleNamespace(company=SimpleNamespace(ticker="TST", company_name="Test", exchange="HOSE", industry_name="Industrial", company_type="normal"))
render_industry_overlay(Integration(), host, Provider())
'''
    at = AppTest.from_string(app, default_timeout=15).run()
    assert len(at.exception) == 0
    assert any("Industry & Moat" in str(item.value) for item in at.markdown)
    # V23.89 proved that de-indenting Markdown was insufficient in the live
    # fragment. Lock the production renderer to Streamlit's HTML element so
    # raw <div>/<table> markup can never become visible page text again.
    html_elements = at.get("html")
    assert len(html_elements) >= 4
    assert all(str(item.proto.body).startswith("<style>") for item in html_elements)
    assert all('<div class="industry-' in str(item.proto.body) for item in html_elements)
