from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
import json
import sqlite3

import pandas as pd

from modules.investment_checklist.ui.phase2_2_fixes import metric_candidates_fixed, render_wrapped_table_fixed
from modules.investment_checklist.services.portfolio_extensions import set_watchlist
from modules.investment_checklist.services.watchlist_v2 import (
    list_watchlist_rows_v2,
    refresh_watchlist_cagrs_if_changed,
)


def test_empty_numeric_line_items_remain_available_for_analyst_override():
    df = pd.DataFrame(
        {
            "Kỳ": ["TTM", "2025"],
            "Net income": [100.0, 90.0],
            "Provision": [None, None],
            "Actual charge-off/write-off": [None, None],
            "Text note": ["a", "b"],
        }
    )
    metrics = metric_candidates_fixed(df, {"Kỳ"})
    assert "Net income" in metrics
    assert "Provision" in metrics
    assert "Actual charge-off/write-off" in metrics
    assert "Text note" not in metrics


def test_formula_table_renderer_emits_dedented_real_html(monkeypatch):
    calls = []

    def capture(body, **kwargs):
        calls.append((body, kwargs))

    monkeypatch.setattr("modules.investment_checklist.ui.phase2_2_fixes.st.markdown", capture)
    render_wrapped_table_fixed(pd.DataFrame([{"Tool": "Q27", "Formula": "CFO / Net income"}]), css_class="formula-test")
    assert calls
    body, kwargs = calls[0]
    assert body.startswith("<style>")
    assert '<div class="formula-test-wrap"><table' in body
    assert kwargs.get("unsafe_allow_html") is True


class _Repo:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute(
            """CREATE TABLE checklist_company_refs(
                id INTEGER PRIMARY KEY,
                host_company_key TEXT UNIQUE,
                ticker TEXT,
                exchange TEXT,
                company_name TEXT
            )"""
        )
        self.db.execute(
            "INSERT INTO checklist_company_refs(id,host_company_key,ticker,exchange,company_name) VALUES(1,'TICKER:AAA','AAA','HOSE','AAA Corp')"
        )
        self.db.commit()

    @contextmanager
    def _conn(self):
        try:
            yield self.db
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _audit(self, *args, **kwargs):
        return None


class _Provider:
    def __init__(self):
        self.annual_df = pd.DataFrame(
            {
                "year": [2020, 2021, 2022, 2023, 2024, 2025],
                "revenue_bil": [100, 110, 120, 130, 145, 160],
                "net_profit_bil": [10, 11, 12, 13, 14, 16],
            }
        )

    def get_inventory_source_data(self, _company_context):
        return SimpleNamespace(
            as_of_date="TTM",
            tev=1000.0,
            ebit=100.0,
            ebitda=125.0,
            normalized_earnings=90.0,
            total_debt=200.0,
            interest_expense=20.0,
            fcf_current=80.0,
            market_cap=900.0,
            dividend_per_share=1000.0,
            market_price=30000.0,
            fcf_estimate=2500.0,
            target_price=45000.0,
            ccc_days=45.0,
            mos=1.0 / 3.0,
            source_module="test_trecapital_latest",
        )


def test_watchlist_uses_latest_financial_cache_without_any_review_table():
    repo = _Repo()
    provider = _Provider()
    set_watchlist(repo, 1, active=True, actor="tester", provider=provider)
    changed = refresh_watchlist_cagrs_if_changed(repo, 1, provider=provider, actor="tester")
    assert changed is True

    # Deliberately do not create research_reviews/opportunity_inventory_snapshots. If the Watchlist
    # still depended on latest review semantics this call would fail or return empty financials.
    rows = list_watchlist_rows_v2(repo)
    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "AAA"
    assert row["financial_as_of_date"] == "TTM"
    assert row["source_module"] == "test_trecapital_latest"
    assert row["tev"] == 1000.0
    assert row["tev_ebit"] == 10.0
    assert row["has_financial_cache"] is True
    assert row["revenue_cagr_5y"] is not None
    assert row["profit_cagr_5y"] is not None
