from __future__ import annotations

"""Automatic same-industry peer discovery and canonical refresh for Chapter 4 Q17/Q19.

The module reuses the same Simplize peer crawler and Module-1 normalization/cache pipeline
already used by Trecapital.  It does not invent peers and it does not classify industry quality.
"""

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from adapters.vn_public_crawler import PublicSimplizeCrawler


DEFAULT_MAX_PEERS = 60


def _safe_ticker(value: Any) -> str:
    text = "".join(ch for ch in str(value or "").upper().strip() if ch.isalnum() or ch in {".", "-"})
    return text[:20]


@dataclass(frozen=True)
class IndustryPeerDiscovery:
    target: str
    industry_group: str
    peers: pd.DataFrame
    note: str
    raw_path: str
    truncated: bool = False

    @property
    def tickers(self) -> list[str]:
        if self.peers is None or self.peers.empty or "ticker" not in self.peers.columns:
            return [self.target] if self.target else []
        out: list[str] = []
        for item in [self.target, *self.peers["ticker"].tolist()]:
            ticker = _safe_ticker(item)
            if ticker and ticker not in out:
                out.append(ticker)
        return out


def _normalize_peer_frame(df: pd.DataFrame, target: str, max_peers: int = DEFAULT_MAX_PEERS) -> tuple[pd.DataFrame, bool]:
    columns = [
        "ticker", "company_name", "exchange", "industry", "sub_industry", "peer_group",
        "market_cap_bil", "current_price", "pe", "pb", "roe_pct", "source", "updated_at",
    ]
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=columns), False
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            out[col] = None if col in {"market_cap_bil", "current_price", "pe", "pb", "roe_pct"} else ""
    out["ticker"] = out["ticker"].map(_safe_ticker)
    out = out[out["ticker"].str.len() >= 2].drop_duplicates("ticker", keep="first")
    out["market_cap_bil"] = pd.to_numeric(out["market_cap_bil"], errors="coerce")
    out["_target"] = out["ticker"].eq(_safe_ticker(target)).astype(int)
    out = out.sort_values(["_target", "market_cap_bil", "ticker"], ascending=[False, False, True], na_position="last")
    truncated = False
    if max_peers and max_peers > 0 and len(out) > max_peers:
        out = out.head(max_peers).copy()
        truncated = True
    return out.drop(columns=["_target"], errors="ignore")[columns].reset_index(drop=True), truncated


def discover_same_industry_peers(
    ticker: str,
    raw_dir: str | Path,
    max_peers: int = DEFAULT_MAX_PEERS,
    crawler_factory: Callable[[str | Path], Any] = PublicSimplizeCrawler,
) -> IndustryPeerDiscovery:
    """Resolve the target's Simplize industry page and return the actual listed peer set.

    No synthetic fallback is used.  If the external page cannot be resolved, the result contains
    only the target ticker through ``tickers`` and an empty peer dataframe.
    """
    safe = _safe_ticker(ticker)
    if not safe:
        return IndustryPeerDiscovery("", "", pd.DataFrame(), "Mã cổ phiếu chưa hợp lệ.", "")
    try:
        raw_path, peer_df, note = crawler_factory(raw_dir).fetch_industry_peers(safe)
    except Exception as exc:
        return IndustryPeerDiscovery(safe, "", pd.DataFrame(), f"Không lấy được danh sách cùng ngành: {exc}", "")
    normalized, truncated = _normalize_peer_frame(peer_df, safe, max_peers=max_peers)
    industry_group = ""
    if not normalized.empty:
        for col in ("peer_group", "sub_industry", "industry"):
            vals = normalized[col].fillna("").astype(str).str.strip()
            vals = vals[vals.ne("")]
            if not vals.empty:
                industry_group = vals.iloc[0]
                break
    if truncated:
        note = f"{note} Hệ thống dùng tối đa {max_peers} mã lớn/đại diện để tránh crawl BCTC không giới hạn trong một lần cập nhật."
    return IndustryPeerDiscovery(
        target=safe,
        industry_group=industry_group,
        peers=normalized,
        note=str(note or ""),
        raw_path=str(raw_path or ""),
        truncated=truncated,
    )


def refresh_peer_canonical_bundle(
    ticker: str,
    fetch_source: Callable[[str, str], tuple[Any, str]] | None = None,
    result_has_data: Callable[[Any], bool] | None = None,
    export_result: Callable[[Any, str, str], tuple[Any, Any, Any, dict]] | None = None,
) -> tuple[bool, tuple[Path, Path, Path] | None, str]:
    """Refresh one peer through Trecapital's existing Module-1 source/normalization pipeline.

    This deliberately calls the low-level pipeline rather than ``_search_and_bind`` so a batch peer
    refresh does not mutate the active ticker or trigger ``st.rerun`` for every peer.
    """
    safe = _safe_ticker(ticker)
    if not safe:
        return False, None, "Ticker không hợp lệ."
    if fetch_source is None or result_has_data is None or export_result is None:
        import module1_dashboard as m1

        fetch_source = fetch_source or m1._fetch_source
        result_has_data = result_has_data or m1._result_has_dashboard_data
        export_result = export_result or m1._export_provider_result_to_cache
    try:
        result, source_key = fetch_source(safe, "FireAnt + Vietstock")
        if not result_has_data(result):
            return False, None, f"{safe}: nguồn ưu tiên chưa trả BCTC chuẩn; không tạo dữ liệu giả."
        overview, year, quarter, counts = export_result(result, safe, source_key)
        paths = (Path(str(overview)), Path(str(year)), Path(str(quarter)))
        note = (
            f"{safe}: canonical cache đã cập nhật — overview {int(counts.get('overview', 0))}, "
            f"năm {int(counts.get('annual', 0))}, quý {int(counts.get('quarterly', 0))}."
        )
        return True, paths, note
    except Exception as exc:
        return False, None, f"{safe}: cập nhật canonical data lỗi: {exc}"


def refresh_peer_canonical_universe(
    tickers: list[str],
    max_workers: int = 3,
) -> list[tuple[str, bool, tuple[Path, Path, Path] | None, str]]:
    """Refresh a real peer universe concurrently through the canonical pipeline.

    Concurrency is deliberately small to reduce total waiting time without hammering public sources.
    Results keep input order.  A failed peer stays failed/Unknown; there is no substitute data.
    """
    ordered: list[str] = []
    for item in tickers:
        safe = _safe_ticker(item)
        if safe and safe not in ordered:
            ordered.append(safe)
    if not ordered:
        return []
    workers = max(1, min(int(max_workers or 1), 4, len(ordered)))
    indexed: dict[str, tuple[bool, tuple[Path, Path, Path] | None, str]] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ch4-peer") as pool:
        futures = {pool.submit(refresh_peer_canonical_bundle, ticker): ticker for ticker in ordered}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                indexed[ticker] = future.result()
            except Exception as exc:
                indexed[ticker] = (False, None, f"{ticker}: cập nhật canonical data lỗi: {exc}")
    return [(ticker, *indexed.get(ticker, (False, None, f"{ticker}: không có kết quả."))) for ticker in ordered]


def peer_refresh_plan(discovery: IndustryPeerDiscovery, target_first: bool = True) -> list[str]:
    """Stable de-duplicated crawl plan from the real discovered same-industry universe."""
    tickers = discovery.tickers
    if target_first and discovery.target in tickers:
        tickers = [discovery.target] + [x for x in tickers if x != discovery.target]
    return tickers


def guardrails() -> dict[str, bool]:
    return {
        "synthetic_peer_fallback": False,
        "auto_industry_quality_conclusion": False,
        "auto_ideal_company_selection": False,
        "auto_competition_intensity_conclusion": False,
    }
