from __future__ import annotations

from datetime import datetime
import json

import pandas as pd

from modules.deep_company_analysis.opportunity_signals import (
    build_opportunity_signals,
    compute_52w_signal,
    compute_historical_valuation_percentile,
    compute_price_fundamental_divergence,
    load_event_candidates,
    load_fireant_price_history,
)


class _Provider:
    def get_inventory_proxy_history(self, years=10):
        return [
            {"period": "2021", "source_type": "10Y proxy", "tev_ebit": 12.0, "tev_ebitda": 9.0, "fcf_yield_market": 0.05},
            {"period": "2022", "source_type": "10Y proxy", "tev_ebit": 10.0, "tev_ebitda": 8.0, "fcf_yield_market": 0.06},
            {"period": "2023", "source_type": "10Y proxy", "tev_ebit": 14.0, "tev_ebitda": 10.0, "fcf_yield_market": 0.04},
            {"period": "2024", "source_type": "10Y proxy", "tev_ebit": 11.0, "tev_ebitda": 8.5, "fcf_yield_market": 0.055},
            {"period": "2025", "source_type": "10Y proxy", "tev_ebit": 9.0, "tev_ebitda": 7.0, "fcf_yield_market": 0.07},
            {"period": "TTM", "source_type": "TTM", "tev_ebit": 8.0, "tev_ebitda": 6.5, "fcf_yield_market": 0.08},
        ]


def _annual_df():
    return pd.DataFrame([
        {"period": "2025", "period_type": "Y", "year": 2025, "core_operating_profit_bil": 100.0, "cfo_bil": 120.0, "capex_bil": 30.0},
        {"period": "TTM", "period_type": "TTM", "year": 2026, "core_operating_profit_bil": 120.0, "cfo_bil": 150.0, "capex_bil": 30.0},
    ])


def test_load_price_history_and_52w(tmp_path):
    raw_dir = tmp_path / "raw_data"
    raw_dir.mkdir()
    payload = [
        {"Symbol": "DGC", "Date": "2025-09-02", "PriceClose": 100000},
        {"Symbol": "DGC", "Date": "2026-02-01", "PriceClose": 90000},
        {"Symbol": "DGC", "Date": "2026-08-30", "PriceClose": 60000},
    ]
    (raw_dir / "fireant_DGC_json_1_1.json").write_text(json.dumps(payload), encoding="utf-8")
    prices = load_fireant_price_history(raw_dir, "DGC")
    assert len(prices) == 3
    signal = compute_52w_signal(prices, current_price=50000, now=datetime(2026, 9, 2))
    assert round(signal["drawdown_52w_pct"], 1) == 50.0
    assert signal["high_52w"] == 100000
    assert signal["low_52w"] == 50000
    assert signal["price_history_fresh"] is True


def test_historical_valuation_percentile_low_multiple_is_cheap():
    signal = compute_historical_valuation_percentile(_Provider())
    assert signal["valuation_metric"] == "TEV/EBIT"
    assert signal["valuation_current"] == 8.0
    assert signal["valuation_history_n"] == 5
    assert signal["valuation_percentile"] == 0.0


def test_price_fundamental_divergence_detects_price_down_fundamentals_up():
    prices = pd.DataFrame([
        {"date": pd.Timestamp("2025-09-02"), "close": 100000},
        {"date": pd.Timestamp("2026-08-30"), "close": 62000},
    ])
    signal = compute_price_fundamental_divergence(prices, _annual_df(), current_price=60000, now=datetime(2026, 9, 2))
    assert signal["price_earnings_divergence"] == "Có"
    assert signal["price_return_1y_pct"] <= -39.0
    assert signal["earnings_change_pct"] >= 19.0


def test_event_candidate_from_existing_trecapital_evidence_cache(tmp_path):
    raw_dir = tmp_path / "raw_data"
    folder = raw_dir / "internet_evidence" / "DGC"
    folder.mkdir(parents=True)
    payload = {
        "queries": [
            {"items": [
                {
                    "Tiêu đề": "DGC công bố thay đổi Tổng giám đốc sau quyết định khởi tố",
                    "Trích yếu": "Doanh nghiệp công bố thông tin về thay đổi quản lý.",
                    "Nguồn/URL": "https://example.com/dgc",
                }
            ]}
        ]
    }
    (folder / "evidence_1.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    events = load_event_candidates(raw_dir, "DGC")
    assert events
    assert events[0]["category"] in {"Quản trị / pháp lý", "Thay đổi quản lý"}
    assert "DGC" in events[0]["title"]


def test_build_opportunity_signals_integration(tmp_path):
    raw_dir = tmp_path / "raw_data"
    raw_dir.mkdir()
    payload = [
        {"Symbol": "DGC", "Date": "2025-09-02", "PriceClose": 100000},
        {"Symbol": "DGC", "Date": "2026-08-30", "PriceClose": 60000},
    ]
    (raw_dir / "fireant_DGC_json_1_1.json").write_text(json.dumps(payload), encoding="utf-8")
    signal = build_opportunity_signals(_Provider(), _annual_df(), raw_dir, "DGC", current_price=60000, now=datetime(2026, 9, 2))
    assert round(signal["drawdown_52w_pct"], 1) == 40.0
    assert signal["valuation_percentile"] == 0.0
    assert signal["price_earnings_divergence"] == "Có"
