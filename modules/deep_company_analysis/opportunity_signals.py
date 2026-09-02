from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Optional
import json
import math
import re

import pandas as pd

from adapters.module2_web_research import WebEvidenceAgent


DATE_ALIASES = (
    "Date", "date", "TradingDate", "tradingDate", "TradingTime", "tradingTime",
    "Time", "time", "Ngay", "ngay",
)
PRICE_ALIASES = (
    "PriceClose", "Close", "close", "ClosePrice", "closePrice", "Price", "price",
    "AdjustedClose", "AdjClose", "PriceAverage", "PriceCurrent", "PriceLast",
)
SYMBOL_ALIASES = ("Symbol", "symbol", "Ticker", "ticker", "Code", "code")

EVENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Quản trị / pháp lý": (
        "khởi tố", "khoi to", "bắt tạm giam", "bat tam giam", "điều tra", "dieu tra",
        "truy tố", "truy to", "tạm đình chỉ", "tam dinh chi", "đình chỉ", "dinh chi",
        "xử phạt", "xu phat", "vi phạm", "vi pham", "lawsuit", "investigation", "sanction",
    ),
    "Kiểm toán / BCTC": (
        "ngoại trừ", "ngoai tru", "ý kiến kiểm toán", "y kien kiem toan", "kiểm toán", "kiem toan",
        "restatement", "điều chỉnh hồi tố", "dieu chinh hoi to",
    ),
    "Thay đổi quản lý": (
        "từ nhiệm", "tu nhiem", "miễn nhiệm", "mien nhiem", "bổ nhiệm", "bo nhiem",
        "thay tổng giám đốc", "thay tong giam doc", "thay chủ tịch", "thay chu tich",
    ),
    "Forced selling / chỉ số": (
        "loại khỏi chỉ số", "loai khoi chi so", "rời rổ", "roi ro", "etf", "index review",
        "index", "forced selling", "bán bắt buộc", "ban bat buoc",
    ),
    "Tái cấu trúc / M&A": (
        "tái cấu trúc", "tai cau truc", "sáp nhập", "sap nhap", "m&a", "mua lại", "mua lai",
        "thoái vốn", "thoai von", "spin-off", "chia tách", "chia tach", "chuyển nhượng", "chuyen nhuong",
    ),
    "Sự kiện vận hành": (
        "tạm dừng", "tam dung", "đóng cửa", "dong cua", "sự cố", "su co", "cháy", "chay",
        "thu hồi", "thu hoi", "đứt gãy", "dut gay", "khởi công", "khoi cong", "vận hành", "van hanh",
        "chạy thử", "chay thu", "mở rộng công suất", "mo rong cong suat",
    ),
    "Hành động vốn": (
        "phát hành", "phat hanh", "mua cổ phiếu quỹ", "mua co phieu quy", "cổ tức đặc biệt", "co tuc dac biet",
        "tăng vốn", "tang von", "giảm vốn", "giam von",
    ),
}


class OpportunityEventEvidenceAgent(WebEvidenceAgent):
    """Reuse Trecapital's existing web-evidence plumbing with Chapter 1 event-focused queries."""

    def _build_queries(self, ticker: str, company_name: str) -> list[str]:  # type: ignore[override]
        clean_name = self._clean_company_name(company_name)
        name = clean_name or company_name or ticker
        return [
            f'"{ticker}" "{name}" khởi tố OR điều tra OR kiểm toán OR ngoại trừ OR từ nhiệm OR tạm dừng',
            f'"{ticker}" "{name}" "loại khỏi chỉ số" OR ETF OR "tái cấu trúc" OR M&A OR "phát hành"',
        ]


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return out if math.isfinite(out) else None
    except Exception:
        return None


def _first_by_alias(record: dict[str, Any], aliases: Iterable[str]) -> Any:
    for key in aliases:
        if key in record and record.get(key) not in (None, ""):
            return record.get(key)
    lower = {str(k).lower(): v for k, v in record.items()}
    for key in aliases:
        value = lower.get(str(key).lower())
        if value not in (None, ""):
            return value
    return None


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def _parse_date(value: Any) -> Optional[pd.Timestamp]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    # Prefer ISO-like timestamps because FireAnt normally emits yyyy-mm-dd.
    for dayfirst in (False, True):
        try:
            ts = pd.to_datetime(text, errors="coerce", dayfirst=dayfirst)
            if pd.notna(ts):
                ts = pd.Timestamp(ts)
                if ts.tzinfo is not None:
                    ts = ts.tz_convert(None)
                if 1990 <= ts.year <= datetime.now().year + 1:
                    return ts.normalize()
        except Exception:
            continue
    return None


def _price_rows_from_payload(payload: Any, ticker: str) -> list[tuple[pd.Timestamp, float]]:
    rows: list[tuple[pd.Timestamp, float]] = []
    safe = str(ticker or "").upper().strip()
    for record in _iter_dicts(payload):
        symbol = _first_by_alias(record, SYMBOL_ALIASES)
        if symbol not in (None, "") and safe and str(symbol).upper().strip() != safe:
            continue
        date_value = _first_by_alias(record, DATE_ALIASES)
        price_value = _first_by_alias(record, PRICE_ALIASES)
        date = _parse_date(date_value)
        price = _safe_float(price_value)
        if date is None or price is None or price <= 0:
            continue
        rows.append((date, price))
    return rows


def load_fireant_price_history(raw_dir: str | Path, ticker: str, max_files: int = 80) -> pd.DataFrame:
    """Read daily historical quotes already downloaded by the canonical FireAnt crawler.

    No new market endpoint is introduced here. The Chapter 1 page only consumes the raw JSON that
    Module 1 already saves while probing FireAnt HistoricalQuotes / PriceHistory endpoints.
    """
    raw_path = Path(raw_dir)
    safe = str(ticker or "").upper().strip()
    if not raw_path.exists() or not safe:
        return pd.DataFrame(columns=["date", "close"])

    patterns = [
        f"fireant_{safe}_json_*.json",
        f"fireant_excel_vba_{safe}_*.json",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(raw_path.glob(pattern))
    files = sorted(set(files), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:max_files]

    rows: list[tuple[pd.Timestamp, float]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.extend(_price_rows_from_payload(payload, safe))

    if not rows:
        return pd.DataFrame(columns=["date", "close"])
    df = pd.DataFrame(rows, columns=["date", "close"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"])
    df = df[df["close"] > 0].sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return df.reset_index(drop=True)


def compute_52w_signal(price_history: pd.DataFrame, current_price: Optional[float] = None, now: Optional[datetime] = None) -> dict[str, Any]:
    if not isinstance(price_history, pd.DataFrame) or price_history.empty:
        return {
            "drawdown_52w_pct": None,
            "high_52w": None,
            "low_52w": None,
            "rebound_from_low_pct": None,
            "price_history_as_of": "",
            "price_history_observations": 0,
            "price_history_fresh": False,
        }
    work = price_history.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work = work.dropna(subset=["date", "close"])
    if work.empty:
        return compute_52w_signal(pd.DataFrame())

    reference_now = now or datetime.now()
    latest_date = pd.Timestamp(work["date"].max()).normalize()
    effective_price = _safe_float(current_price)
    as_of = pd.Timestamp(reference_now.date()) if effective_price is not None and effective_price > 0 else latest_date
    start = as_of - pd.Timedelta(days=365)
    window = work[(work["date"] >= start) & (work["date"] <= as_of)].copy()
    if window.empty:
        return compute_52w_signal(pd.DataFrame())

    high = _safe_float(window["close"].max())
    low = _safe_float(window["close"].min())
    if effective_price is None or effective_price <= 0:
        effective_price = _safe_float(window.iloc[-1]["close"])
    if effective_price is not None:
        high = max(high or effective_price, effective_price)
        low = min(low or effective_price, effective_price)
    drawdown = ((high - effective_price) / high * 100.0) if high and effective_price is not None and high > 0 else None
    rebound = ((effective_price - low) / low * 100.0) if low and effective_price is not None and low > 0 else None
    latest_age_days = max(0, (pd.Timestamp(reference_now.date()) - latest_date).days)
    return {
        "drawdown_52w_pct": drawdown,
        "high_52w": high,
        "low_52w": low,
        "rebound_from_low_pct": rebound,
        "price_history_as_of": latest_date.strftime("%Y-%m-%d"),
        "price_history_observations": int(len(window)),
        "price_history_fresh": bool(latest_age_days <= 10),
    }


def _percentile_low_is_cheap(current: float, history: list[float]) -> Optional[float]:
    values = [float(x) for x in history if _safe_float(x) is not None and float(x) > 0]
    if len(values) < 4:
        return None
    return sum(1 for value in values if value <= current) / len(values) * 100.0


def _percentile_high_is_cheap(current: float, history: list[float]) -> Optional[float]:
    values = [float(x) for x in history if _safe_float(x) is not None]
    if len(values) < 4:
        return None
    return sum(1 for value in values if value >= current) / len(values) * 100.0


def compute_historical_valuation_percentile(provider: Any, years: int = 10) -> dict[str, Any]:
    try:
        rows = list(provider.get_inventory_proxy_history(years=years) or [])
    except Exception:
        rows = []
    if not rows:
        return {"valuation_percentile": None, "valuation_metric": "", "valuation_current": None, "valuation_history_n": 0}

    current_row = next((row for row in reversed(rows) if str(row.get("source_type", "")).upper() == "TTM"), rows[-1])
    historical = [row for row in rows if row is not current_row and str(row.get("source_type", "")).upper() != "TTM"]
    metric_specs = (
        ("tev_ebit", "TEV/EBIT", False),
        ("tev_ebitda", "TEV/EBITDA", False),
        ("fcf_yield_market", "FCF Yield / Market Cap", True),
    )
    for key, label, high_is_cheap in metric_specs:
        current = _safe_float(current_row.get(key))
        values = [_safe_float(row.get(key)) for row in historical]
        values = [value for value in values if value is not None and (high_is_cheap or value > 0)]
        if current is None or (not high_is_cheap and current <= 0) or len(values) < 4:
            continue
        percentile = _percentile_high_is_cheap(current, values) if high_is_cheap else _percentile_low_is_cheap(current, values)
        if percentile is None:
            continue
        return {
            "valuation_percentile": percentile,
            "valuation_metric": label,
            "valuation_current": current,
            "valuation_history_n": len(values),
            "valuation_percentile_interpretation": "0% = rẻ nhất lịch sử; 100% = đắt nhất lịch sử",
        }
    return {"valuation_percentile": None, "valuation_metric": "", "valuation_current": None, "valuation_history_n": 0}


def _row_metric(row: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _row_fcf(row: dict[str, Any]) -> Optional[float]:
    direct = _row_metric(row, "free_cash_flow_bil")
    if direct is not None:
        return direct
    cfo = _row_metric(row, "cfo_bil")
    capex = _row_metric(row, "capex_bil")
    if cfo is not None and capex is not None:
        return cfo - abs(capex)
    return None


def _fundamental_pair(annual_df: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(annual_df, pd.DataFrame) or annual_df.empty:
        return {}, {}
    work = annual_df.copy()
    current: dict[str, Any] = {}
    if "period" in work.columns:
        ttm = work[work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        if not ttm.empty:
            current = ttm.iloc[-1].to_dict()
    annual = work
    if "period_type" in annual.columns:
        annual = annual[annual["period_type"].astype(str).eq("Y")]
    if "year" in annual.columns:
        annual = annual.assign(_year=pd.to_numeric(annual["year"], errors="coerce")).sort_values("_year")
    if current:
        previous = annual.iloc[-1].to_dict() if not annual.empty else {}
        return current, previous
    if len(annual) >= 2:
        return annual.iloc[-1].to_dict(), annual.iloc[-2].to_dict()
    return {}, {}


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or abs(previous) < 1e-9:
        return None
    return (current - previous) / abs(previous) * 100.0


def _price_around_one_year_ago(price_history: pd.DataFrame, as_of: pd.Timestamp) -> Optional[float]:
    if not isinstance(price_history, pd.DataFrame) or price_history.empty:
        return None
    target = as_of - pd.Timedelta(days=365)
    work = price_history.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce")
    work["close"] = pd.to_numeric(work["close"], errors="coerce")
    work = work.dropna(subset=["date", "close"])
    if work.empty:
        return None
    work["distance"] = (work["date"] - target).abs().dt.days
    nearest = work.sort_values("distance").iloc[0]
    if int(nearest["distance"]) > 60:
        return None
    return _safe_float(nearest["close"])


def compute_price_fundamental_divergence(
    price_history: pd.DataFrame,
    annual_df: pd.DataFrame,
    current_price: Optional[float] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    if not isinstance(price_history, pd.DataFrame) or price_history.empty:
        return {"price_earnings_divergence": "— Chưa xác định", "divergence_evidence": "Thiếu chuỗi giá lịch sử."}
    work = price_history.copy().sort_values("date")
    latest_date = pd.Timestamp(work["date"].max()).normalize()
    effective_price = _safe_float(current_price) or _safe_float(work.iloc[-1].get("close"))
    as_of = pd.Timestamp((now or datetime.now()).date()) if _safe_float(current_price) else latest_date
    one_year_price = _price_around_one_year_ago(work, as_of)
    price_return = _pct_change(effective_price, one_year_price)

    current_row, previous_row = _fundamental_pair(annual_df)
    current_earnings = _row_metric(current_row, "core_operating_profit_bil", "operating_profit_bil", "pretax_profit_bil", "net_profit_bil")
    previous_earnings = _row_metric(previous_row, "core_operating_profit_bil", "operating_profit_bil", "pretax_profit_bil", "net_profit_bil")
    current_fcf = _row_fcf(current_row)
    previous_fcf = _row_fcf(previous_row)
    earnings_change = _pct_change(current_earnings, previous_earnings)
    fcf_change = _pct_change(current_fcf, previous_fcf)

    if price_return is None or (earnings_change is None and fcf_change is None):
        result = "— Chưa xác định"
    else:
        improved = (earnings_change is not None and earnings_change >= 5.0) or (fcf_change is not None and fcf_change >= 10.0)
        result = "Có" if price_return <= -15.0 and improved else "Không"
    evidence = (
        f"Giá ~1 năm: {price_return:,.1f}%" if price_return is not None else "Giá ~1 năm: —"
    ) + "; " + (
        f"earnings: {earnings_change:,.1f}%" if earnings_change is not None else "earnings: —"
    ) + "; " + (
        f"FCF: {fcf_change:,.1f}%" if fcf_change is not None else "FCF: —"
    )
    return {
        "price_earnings_divergence": result,
        "price_return_1y_pct": price_return,
        "earnings_change_pct": earnings_change,
        "fcf_change_pct": fcf_change,
        "divergence_evidence": evidence,
        "divergence_rule": "Có khi giá giảm ≥15% nhưng earnings tăng ≥5% hoặc FCF tăng ≥10%; đây là research signal, không phải Buy Signal.",
    }


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _event_category(text: str) -> tuple[str, int]:
    lowered = text.lower()
    best_category = ""
    best_hits = 0
    for category, keywords in EVENT_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword.lower() in lowered)
        if hits > best_hits:
            best_category, best_hits = category, hits
    return best_category, best_hits


def _evidence_items_from_payload(payload: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in _iter_dicts(payload):
        title = _normalize_text(record.get("Tiêu đề") or record.get("title"))
        snippet = _normalize_text(record.get("Trích yếu") or record.get("snippet"))
        url = _normalize_text(record.get("Nguồn/URL") or record.get("url"))
        if not title and not snippet:
            continue
        items.append({"title": title, "snippet": snippet, "url": url})
    return items


def load_event_candidates(raw_dir: str | Path, ticker: str, max_files: int = 8) -> list[dict[str, Any]]:
    folder = Path(raw_dir) / "internet_evidence" / str(ticker or "").upper().strip()
    if not folder.exists():
        return []
    files = sorted(folder.glob("evidence_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:max_files]
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in _evidence_items_from_payload(payload):
            text = f"{item['title']} {item['snippet']}"
            category, hits = _event_category(text)
            if hits <= 0:
                continue
            key = (item["title"], item["url"])
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "category": category,
                "title": item["title"],
                "snippet": item["snippet"][:500],
                "url": item["url"],
                "keyword_hits": hits,
                "evidence_fetched_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            })
    candidates.sort(key=lambda row: (row.get("keyword_hits", 0), row.get("evidence_fetched_at", "")), reverse=True)
    return candidates[:5]


def build_opportunity_signals(
    provider: Any,
    annual_df: pd.DataFrame,
    raw_dir: str | Path,
    ticker: str,
    current_price: Optional[float] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    price_history = load_fireant_price_history(raw_dir, ticker)
    signal_52w = compute_52w_signal(price_history, current_price=current_price, now=now)
    valuation = compute_historical_valuation_percentile(provider)
    divergence = compute_price_fundamental_divergence(price_history, annual_df, current_price=current_price, now=now)
    events = load_event_candidates(raw_dir, ticker)
    top_event = events[0] if events else None
    special_event = ""
    if top_event:
        special_event = f"Ứng viên cần xác minh [{top_event['category']}]: {top_event['title']}"
    return {
        **signal_52w,
        **valuation,
        **divergence,
        "special_event": special_event,
        "event_candidates": events,
        "event_source": "Trecapital WebEvidence cache" if events else "",
        "signal_generated_at": (now or datetime.now()).isoformat(timespec="seconds"),
    }
