from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from modules.deep_company_analysis.chapter4_peer_auto import (
    discover_same_industry_peers,
    guardrails,
    peer_refresh_plan,
    refresh_peer_canonical_bundle,
)


class FakeCrawler:
    def __init__(self, raw_dir):
        self.raw_dir = raw_dir

    def fetch_industry_peers(self, ticker):
        df = pd.DataFrame([
            {"ticker": "DDV", "company_name": "DDV", "peer_group": "Hóa chất", "market_cap_bil": 3500},
            {"ticker": ticker, "company_name": ticker, "peer_group": "Hóa chất", "market_cap_bil": 22000},
            {"ticker": "LAS", "company_name": "LAS", "peer_group": "Hóa chất", "market_cap_bil": 2000},
            {"ticker": "DDV", "company_name": "dup", "peer_group": "Hóa chất", "market_cap_bil": 1},
        ])
        return Path("raw.json"), df, "ok"


def test_discovery_uses_real_rows_and_deduplicates():
    result = discover_same_industry_peers("DGC", ".", crawler_factory=FakeCrawler)
    assert result.industry_group == "Hóa chất"
    assert result.tickers == ["DGC", "DDV", "LAS"]
    assert list(result.peers["ticker"]) == ["DGC", "DDV", "LAS"]


def test_refresh_uses_existing_normalization_pipeline_without_search_and_bind():
    fake_result = SimpleNamespace()
    calls = []

    def fetch_source(ticker, source):
        calls.append((ticker, source))
        return fake_result, "fireant_vietstock"

    def has_data(result):
        return result is fake_result

    def export_result(result, ticker, source_key):
        assert result is fake_result
        assert source_key == "fireant_vietstock"
        return "o.csv", "y.csv", "q.csv", {"overview": 1, "annual": 10, "quarterly": 20}

    ok, paths, note = refresh_peer_canonical_bundle("DGC", fetch_source, has_data, export_result)
    assert ok is True
    assert calls == [("DGC", "FireAnt + Vietstock")]
    assert paths is not None and paths[1].name == "y.csv"
    assert "năm 10" in note


def test_no_synthetic_peer_or_industry_judgement():
    flags = guardrails()
    assert flags["synthetic_peer_fallback"] is False
    assert flags["auto_industry_quality_conclusion"] is False
    assert flags["auto_ideal_company_selection"] is False


def test_refresh_plan_target_first():
    result = discover_same_industry_peers("DGC", ".", crawler_factory=FakeCrawler)
    assert peer_refresh_plan(result)[0] == "DGC"
