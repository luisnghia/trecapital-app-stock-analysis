from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from modules.investment_checklist.repositories.postgres_repository import PostgresChecklistRepository
from modules.investment_checklist.repositories.sqlite_repository import SQLiteChecklistRepository, ValidationError
from modules.investment_checklist.services.portfolio_extensions import (
    compute_5y_cagrs,
    ensure_extension_schema,
    latest_table_overrides,
    list_watchlist_rows,
    save_table_override,
    set_watchlist,
)

CATALOG = Path("modules/investment_checklist/catalog/question_catalog_prd.csv")


def _repo(tmp_path):
    repo = SQLiteChecklistRepository(tmp_path / "checklist.db", CATALOG)
    repo.initialize()
    ensure_extension_schema(repo)
    return repo


def test_strict_five_year_cagr_uses_canonical_fy_endpoints():
    df = pd.DataFrame([
        {"period_type": "Y", "year": 2020, "revenue_bil": 100.0, "net_profit_bil": 10.0},
        {"period_type": "Y", "year": 2021, "revenue_bil": 115.0, "net_profit_bil": 11.0},
        {"period_type": "Y", "year": 2022, "revenue_bil": 130.0, "net_profit_bil": 12.0},
        {"period_type": "Y", "year": 2023, "revenue_bil": 145.0, "net_profit_bil": 13.0},
        {"period_type": "Y", "year": 2024, "revenue_bil": 170.0, "net_profit_bil": 15.0},
        {"period_type": "Y", "year": 2025, "revenue_bil": 200.0, "net_profit_bil": 20.0},
        {"period_type": "TTM", "year": 2026, "revenue_bil": 999.0, "net_profit_bil": 999.0},
    ])
    out = compute_5y_cagrs(df)
    assert out["revenue_cagr_5y"] == pytest.approx(2 ** (1 / 5) - 1)
    assert out["profit_cagr_5y"] == pytest.approx(2 ** (1 / 5) - 1)
    assert out["cagr_source_period"] == "FY2020→FY2025"


def test_profit_cagr_is_unknown_across_nonpositive_endpoint():
    df = pd.DataFrame([
        {"period_type": "Y", "year": 2020, "revenue_bil": 100.0, "net_profit_bil": -2.0},
        {"period_type": "Y", "year": 2025, "revenue_bil": 150.0, "net_profit_bil": 20.0},
    ])
    out = compute_5y_cagrs(df)
    assert out["revenue_cagr_5y"] is not None
    assert out["profit_cagr_5y"] is None


def test_watchlist_reads_latest_review_table12_snapshot(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:AAA", ticker="AAA", company_name="AAA Co")
    r1 = repo.create_review(cid, "2025-12-31", review_reason="FY2025 review")
    repo.save_inventory_snapshot(company_ref_id=cid, as_of_date="2025-12-31", review_id=r1, ebit=100, ebitda=120, market_cap=1000, market_price=10000, target_price=12000, note="snapshot 1")
    r2 = repo.create_review(cid, "2026-08-21", review_reason="TTM update")
    repo.save_inventory_snapshot(company_ref_id=cid, as_of_date="2026-08-21", review_id=r2, ebit=150, ebitda=180, market_cap=1500, market_price=15000, target_price=20000, note="snapshot 2")
    annual = pd.DataFrame([
        {"period_type": "Y", "year": 2020, "revenue_bil": 100, "net_profit_bil": 10},
        {"period_type": "Y", "year": 2025, "revenue_bil": 200, "net_profit_bil": 20},
    ])
    set_watchlist(repo, cid, active=True, actor="analyst", provider=annual)
    rows = list_watchlist_rows(repo)
    assert len(rows) == 1
    assert rows[0]["latest_review_id"] == r2
    assert rows[0]["latest_review_as_of"] == "2026-08-21"
    assert rows[0]["ebit"] == 150
    assert rows[0]["market_price"] == 15000
    assert rows[0]["revenue_cagr_5y"] is not None


def test_historical_override_is_append_only_and_reason_required(tmp_path):
    repo = _repo(tmp_path)
    cid = repo.upsert_company_ref(host_company_key="TICKER:BBB", ticker="BBB", company_name="BBB Co")
    with pytest.raises(ValidationError):
        save_table_override(repo, cid, table_key="Table 1.2", period_key="2024", metric_key="EBIT", value=100, reason="", actor="analyst")
    v1 = save_table_override(repo, cid, table_key="Table 1.2", period_key="2024", metric_key="EBIT", value=100, reason="Reclassify one-off", actor="analyst")
    v2 = save_table_override(repo, cid, table_key="Table 1.2", period_key="2024", metric_key="EBIT", value=110, reason="Updated annual report note", actor="analyst")
    assert (v1, v2) == (1, 2)
    latest = latest_table_overrides(repo, cid, "Table 1.2")
    assert latest[("2024", "EBIT")]["version_no"] == 2
    assert latest[("2024", "EBIT")]["value_numeric"] == 110


def test_extension_schema_works_on_real_postgres_when_ci_database_available():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    repo = PostgresChecklistRepository(url, CATALOG)
    repo.initialize()
    ensure_extension_schema(repo)
    cid = repo.upsert_company_ref(host_company_key="WATCH:CI", ticker="WCI", company_name="Watch CI")
    set_watchlist(repo, cid, active=True, actor="ci", provider=pd.DataFrame([
        {"period_type": "Y", "year": 2020, "revenue_bil": 10, "net_profit_bil": 1},
        {"period_type": "Y", "year": 2025, "revenue_bil": 20, "net_profit_bil": 2},
    ]))
    save_table_override(repo, cid, table_key="Analytical · CI", period_key="2024", metric_key="ROIC", value=12.5, reason="CI override", actor="ci")
    assert list_watchlist_rows(repo)[0]["ticker"] == "WCI"
    assert latest_table_overrides(repo, cid, "Analytical · CI")[("2024", "ROIC")]["value_numeric"] == 12.5
    repo.close()
