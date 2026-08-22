from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.services.extension_schema_cache import ensure_extension_schema
from modules.investment_checklist.services.portfolio_extensions import save_table_override, set_watchlist
from modules.investment_checklist.services.watchlist_v2 import list_watchlist_rows_v2, refresh_watchlist_cagrs_if_changed
from modules.investment_checklist.ui.watchlist_v2 import _formatted_dataframe, _style

CATALOG = Path("modules/investment_checklist/catalog/question_catalog_prd.csv")


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "checklist.db", CATALOG)
    repo.initialize()
    ensure_extension_schema(repo)
    return repo


class _LiveProvider:
    def __init__(self, *, ebit=200.0):
        self.ebit = ebit
        self.annual_df = pd.DataFrame([
            {"period_type": "Y", "year": 2020, "revenue_bil": 100, "net_profit_bil": 10},
            {"period_type": "Y", "year": 2025, "revenue_bil": 200, "net_profit_bil": 20},
        ])

    def get_inventory_source_data(self, _ctx):
        return SimpleNamespace(
            as_of_date="TTM", tev=1000.0, ebit=self.ebit, ebitda=250.0, normalized_earnings=160.0,
            total_debt=300.0, interest_expense=20.0, fcf_current=80.0, market_cap=900.0,
            dividend_per_share=1000.0, market_price=10000.0, fcf_estimate=900.0,
            target_price=15000.0, ccc_days=40.0, mos=1/3, source_module="live_test",
        )


def test_watchlist_uses_live_financial_data_not_latest_review(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:LST", ticker="LST", company_name="Latest Semantics")
    old = repo.create_review(cid, "2025-12-31", review_reason="Old review")
    repo.save_inventory_snapshot(company_ref_id=cid, as_of_date="2025-12-31", review_id=old, ebit=100, market_price=10000, note="old")
    repo.create_review(cid, "2026-08-21", review_reason="Newest review, no inventory yet")
    provider = _LiveProvider(ebit=220.0)
    set_watchlist(repo, cid, active=True, actor="analyst", provider=provider)
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=provider, actor="analyst") is True
    row = list_watchlist_rows_v2(repo)[0]
    assert row["financial_as_of_date"] == "TTM"
    assert row["ebit"] == 220.0
    assert row["source_module"] == "live_test"
    assert row["has_financial_cache"] is True


def test_live_table12_overlay_recalculates_derived_watchlist_metrics(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:CALC", ticker="CALC", company_name="Calc")
    provider = _LiveProvider(ebit=100.0)
    set_watchlist(repo, cid, active=True, actor="analyst", provider=provider)
    save_table_override(
        repo, cid, table_key="Table 1.2", period_key="TTM",
        metric_key="EBIT", value=200, reason="Normalize one-off expense", actor="analyst",
    )
    refresh_watchlist_cagrs_if_changed(repo, cid, provider=provider, actor="analyst")
    row = list_watchlist_rows_v2(repo)[0]
    assert row["ebit"] == 200
    assert row["tev_ebit"] == pytest.approx(5.0)
    assert row["pretax_earnings_yield"] == pytest.approx(0.2)
    assert "EBIT" in row["analyst_adjusted_metrics"]


def test_watchlist_refresh_writes_only_on_explicit_change(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:PERF", ticker="PERF", company_name="Perf")
    provider = _LiveProvider()
    set_watchlist(repo, cid, active=True, actor="analyst", provider=provider)
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=provider, actor="analyst") is True
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=provider, actor="analyst") is False
    provider.annual_df.loc[provider.annual_df["year"].eq(2025), "revenue_bil"] = 220
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=provider, actor="analyst") is True
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=provider, actor="analyst") is False


def test_extension_schema_wrapper_runs_uncached_ddl_only_once_per_repo_instance():
    class Conn:
        def __init__(self): self.execute_count = 0
        def execute(self, *args, **kwargs): self.execute_count += 1; return self
    class Repo:
        def __init__(self): self.conn = Conn()
        @contextmanager
        def _conn(self): yield self.conn
    repo = Repo()
    ensure_extension_schema(repo)
    first = repo.conn.execute_count
    ensure_extension_schema(repo)
    assert first == 3
    assert repo.conn.execute_count == first


def test_safe_watchlist_navigation_clears_old_active_bundle_source_contract():
    source = Path("modules/investment_checklist/ui/watchlist_v2.py").read_text(encoding="utf-8")
    for key in ["active_ticker", "active_overview_csv", "active_year_csv", "active_quarter_csv", "active_source_label"]:
        assert f'"{key}"' in source
    assert 'st.session_state["checklist_section_global"] = "🏠 Research Home"' in source
    assert "app không ghi DB ở mỗi lần đổi Question hoặc rerun" in source


def test_operating_leverage_stress_table_has_analyst_override_renderer_contract():
    quant = Path("modules/investment_checklist/ui/quant_tools.py").read_text(encoding="utf-8")
    hub = Path("modules/investment_checklist/ui/analytical_hub_v2.py").read_text(encoding="utf-8")
    assert "auxiliary_table_renderer" in quant
    assert 'auxiliary_table_renderer("Operating Leverage Stress", stress_df)' in quant
    assert "_render_stress_override_table" in hub
    assert 'table_key = f"Analytical · {name}"' in hub


def test_watchlist_materializes_table12_format_before_selectable_dataframe():
    raw = pd.DataFrame([{
        "Mã CP": "VIP", "CAGR LN 5Y": 7.123, "TEV": 12296.507403,
        "EBIT": 2619.018872, "Normalized earnings": None,
        "TEV/EBIT": 4.695082, "CCC": 42.4, "MOS": -3.25,
    }])
    shown = _formatted_dataframe(raw)
    assert shown.iloc[0].to_dict() == {
        "Mã CP": "VIP", "CAGR LN 5Y": "7.1%", "TEV": "12,297",
        "EBIT": "2,619", "Normalized earnings": "—",
        "TEV/EBIT": "4.7x", "CCC": "42 ngày", "MOS": "-3.2%",
    }
    # The Styler data itself is already formatted, so Streamlit 1.40 cannot leak raw floats/None.
    assert _style(raw, {0: {"EBIT"}}).data.iloc[0]["Normalized earnings"] == "—"
