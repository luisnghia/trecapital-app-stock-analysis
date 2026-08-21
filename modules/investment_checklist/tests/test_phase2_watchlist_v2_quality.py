from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository
from modules.investment_checklist.services.extension_schema_cache import ensure_extension_schema
from modules.investment_checklist.services.portfolio_extensions import save_table_override, set_watchlist
from modules.investment_checklist.services.watchlist_v2 import list_watchlist_rows_v2, refresh_watchlist_cagrs_if_changed

CATALOG = Path("modules/investment_checklist/catalog/question_catalog_prd.csv")


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "checklist.db", CATALOG)
    repo.initialize()
    ensure_extension_schema(repo)
    return repo


def test_latest_review_without_table12_does_not_fall_back_to_old_review(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:LST", ticker="LST", company_name="Latest Semantics")
    old = repo.create_review(cid, "2025-12-31", review_reason="Old review")
    repo.save_inventory_snapshot(company_ref_id=cid, as_of_date="2025-12-31", review_id=old, ebit=100, market_price=10000, note="old")
    latest = repo.create_review(cid, "2026-08-21", review_reason="Newest review, no inventory yet")
    set_watchlist(repo, cid, active=True, actor="analyst", provider=pd.DataFrame())
    row = list_watchlist_rows_v2(repo)[0]
    assert row["latest_review_id"] == latest
    assert row["latest_review_has_inventory"] is False
    assert row.get("ebit") is None
    assert row.get("market_price") is None


def test_latest_review_overlay_recalculates_derived_table12_metrics(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:CALC", ticker="CALC", company_name="Calc")
    rid = repo.create_review(cid, "2026-08-21", review_reason="Current")
    repo.save_inventory_snapshot(
        company_ref_id=cid, as_of_date="2026-08-21", review_id=rid,
        tev=1000, ebit=100, ebitda=200, normalized_earnings=80, total_debt=400,
        interest_expense=20, fcf_current=50, market_cap=900, market_price=9000, target_price=10000,
        note="base",
    )
    set_watchlist(repo, cid, active=True, actor="analyst", provider=pd.DataFrame())
    save_table_override(
        repo, cid, table_key="Table 1.2",
        period_key=f"2026-08-21 | Review/snapshot #{rid} · host_data_layer · v1",
        metric_key="EBIT", value=200, reason="Normalize one-off expense", actor="analyst",
    )
    row = list_watchlist_rows_v2(repo)[0]
    assert row["ebit"] == 200
    assert row["tev_ebit"] == pytest.approx(5.0)
    assert row["pretax_earnings_yield"] == pytest.approx(0.2)


def test_watchlist_cagr_refresh_is_noop_when_data_unchanged_and_writes_only_on_change(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:PERF", ticker="PERF", company_name="Perf")
    base = pd.DataFrame([
        {"period_type": "Y", "year": 2020, "revenue_bil": 100, "net_profit_bil": 10},
        {"period_type": "Y", "year": 2025, "revenue_bil": 200, "net_profit_bil": 20},
    ])
    set_watchlist(repo, cid, active=True, actor="analyst", provider=base)
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=base, actor="analyst") is False
    changed = base.copy()
    changed.loc[changed["year"].eq(2025), "revenue_bil"] = 220
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=changed, actor="analyst") is True
    assert refresh_watchlist_cagrs_if_changed(repo, cid, provider=changed, actor="analyst") is False


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
    assert "app không ghi/upsert Watchlist mỗi lần đổi Question" in source


def test_operating_leverage_stress_table_has_analyst_override_renderer_contract():
    quant = Path("modules/investment_checklist/ui/quant_tools.py").read_text(encoding="utf-8")
    hub = Path("modules/investment_checklist/ui/analytical_hub_v2.py").read_text(encoding="utf-8")
    assert "auxiliary_table_renderer" in quant
    assert 'auxiliary_table_renderer("Operating Leverage Stress", stress_df)' in quant
    assert "_render_stress_override_table" in hub
    assert 'table_key = f"Analytical · {name}"' in hub
