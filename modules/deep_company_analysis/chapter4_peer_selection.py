from __future__ import annotations

"""Analyst-curated peer selection for Chapter 4 Q17/Q19.

Discovery and canonical refresh are intentionally separated:
1) Trecapital discovers a broad same-industry candidate universe.
2) The analyst removes/adds/selects comparable companies.
3) Only the confirmed list is sent to the canonical financial refresh.

The target ticker is always retained as the benchmark anchor. No peer is invented.
"""

from typing import Any, Iterable

import pandas as pd


PEER_SELECTION_COLUMNS = [
    "Use?",
    "Ticker",
    "Company Name",
    "Exchange",
    "Industry",
    "Sub-industry",
    "Market Cap (tỷ)",
    "Source",
]


def _safe_ticker(value: Any) -> str:
    return "".join(ch for ch in str(value or "").upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "x", "✓", "dùng", "chon", "chọn"}


def normalize_ticker_list(values: Iterable[Any], target: str, max_peers: int = 60) -> list[str]:
    safe_target = _safe_ticker(target)
    out: list[str] = [safe_target] if safe_target else []
    for value in values:
        ticker = _safe_ticker(value)
        if len(ticker) < 2 or ticker in out:
            continue
        out.append(ticker)
        if max_peers and len(out) >= max_peers:
            break
    return out


def build_peer_selection_table(
    peer_df: pd.DataFrame,
    target: str,
    saved_peer_tickers: Iterable[Any] | None = None,
) -> pd.DataFrame:
    """Build editable candidate rows without downloading financial statements.

    On first discovery all candidates are selected. If a curated list already exists, only
    previously confirmed peers are selected by default; newly discovered names remain visible but
    unchecked so a refresh cannot silently expand the peer set.
    """
    safe_target = _safe_ticker(target)
    saved_values = list(saved_peer_tickers or [])
    saved = set(normalize_ticker_list(saved_values, safe_target)) if saved_values else set()
    has_saved = bool(saved_values)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    if isinstance(peer_df, pd.DataFrame) and not peer_df.empty:
        for _, item in peer_df.iterrows():
            ticker = _safe_ticker(item.get("ticker"))
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            rows.append({
                "Use?": True if ticker == safe_target else (ticker in saved if has_saved else True),
                "Ticker": ticker,
                "Company Name": str(item.get("company_name") or ""),
                "Exchange": str(item.get("exchange") or ""),
                "Industry": str(item.get("industry") or item.get("peer_group") or ""),
                "Sub-industry": str(item.get("sub_industry") or ""),
                "Market Cap (tỷ)": item.get("market_cap_bil"),
                "Source": str(item.get("source") or "Same-industry discovery"),
            })

    if safe_target and safe_target not in seen:
        rows.insert(0, {
            "Use?": True,
            "Ticker": safe_target,
            "Company Name": "",
            "Exchange": "",
            "Industry": "",
            "Sub-industry": "",
            "Market Cap (tỷ)": None,
            "Source": "Target company",
        })
        seen.add(safe_target)

    # Preserve analyst-added peers from an already confirmed list even if discovery no longer
    # returns them. They remain editable and auditable rather than disappearing silently.
    for ticker in normalize_ticker_list(saved_values, safe_target):
        if ticker in seen:
            continue
        rows.append({
            "Use?": True,
            "Ticker": ticker,
            "Company Name": "",
            "Exchange": "",
            "Industry": "Analyst-added / verify",
            "Sub-industry": "",
            "Market Cap (tỷ)": None,
            "Source": "Analyst-curated",
        })
        seen.add(ticker)

    df = pd.DataFrame(rows, columns=PEER_SELECTION_COLUMNS)
    if not df.empty:
        df["Use?"] = df["Use?"].astype(bool)
    return df


def selected_peer_tickers(selection_df: pd.DataFrame, target: str, max_peers: int = 60) -> list[str]:
    """Return only analyst-confirmed rows; target is always included first."""
    safe_target = _safe_ticker(target)
    if not isinstance(selection_df, pd.DataFrame) or selection_df.empty:
        return [safe_target] if safe_target else []
    selected: list[str] = []
    for _, row in selection_df.iterrows():
        ticker = _safe_ticker(row.get("Ticker"))
        if not ticker or ticker == safe_target:
            continue
        if _truthy(row.get("Use?")):
            selected.append(ticker)
    return normalize_ticker_list(selected, safe_target, max_peers=max_peers)


def guardrails() -> dict[str, bool]:
    return {
        "refresh_before_analyst_confirmation": False,
        "auto_add_newly_discovered_peer_to_confirmed_set": False,
        "synthetic_peer": False,
        "target_can_be_removed_from_benchmark": False,
    }
