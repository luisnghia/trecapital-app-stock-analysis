from __future__ import annotations

import pandas as pd

from modules.deep_company_analysis.chapter4_peer_selection import (
    PEER_SELECTION_COLUMNS,
    build_peer_selection_table,
    guardrails,
    selected_peer_tickers,
)


def _discovered():
    return pd.DataFrame([
        {"ticker": "DGC", "company_name": "Duc Giang", "exchange": "HOSE", "industry": "Hóa chất", "sub_industry": "Hóa chất cơ bản", "market_cap_bil": 40000, "source": "Simplize"},
        {"ticker": "DCM", "company_name": "Ca Mau Fertilizer", "exchange": "HOSE", "industry": "Hóa chất", "sub_industry": "Phân bón", "market_cap_bil": 20000, "source": "Simplize"},
        {"ticker": "CSV", "company_name": "South Basic Chemicals", "exchange": "HOSE", "industry": "Hóa chất", "sub_industry": "Hóa chất cơ bản", "market_cap_bil": 5000, "source": "Simplize"},
    ])


def test_first_discovery_selects_candidates_but_does_not_refresh_anything():
    df = build_peer_selection_table(_discovered(), "DGC")
    assert list(df.columns) == PEER_SELECTION_COLUMNS
    assert set(df["Ticker"]) == {"DGC", "DCM", "CSV"}
    assert df["Use?"].all()


def test_saved_curated_list_does_not_silently_expand_when_new_peer_discovered():
    df = build_peer_selection_table(_discovered(), "DGC", saved_peer_tickers=["DCM"])
    use = dict(zip(df["Ticker"], df["Use?"]))
    assert use["DGC"] is True
    assert use["DCM"] is True
    assert use["CSV"] is False


def test_analyst_can_remove_and_add_peers_before_confirming():
    df = build_peer_selection_table(_discovered(), "DGC")
    df.loc[df["Ticker"] == "CSV", "Use?"] = False
    df = pd.concat([df, pd.DataFrame([{"Use?": True, "Ticker": "LAS"}])], ignore_index=True)
    selected = selected_peer_tickers(df, "DGC")
    assert selected[0] == "DGC"
    assert "DCM" in selected
    assert "CSV" not in selected
    assert "LAS" in selected


def test_target_is_always_kept_even_if_analyst_unchecks_it():
    df = build_peer_selection_table(_discovered(), "DGC")
    df.loc[df["Ticker"] == "DGC", "Use?"] = False
    selected = selected_peer_tickers(df, "DGC")
    assert selected[0] == "DGC"


def test_peer_selection_guardrails_all_false():
    flags = guardrails()
    assert flags
    assert all(value is False for value in flags.values())
