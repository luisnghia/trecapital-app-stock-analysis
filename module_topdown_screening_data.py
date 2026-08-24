"""Automatic, click-triggered data intake for Fisher Top-Down quantitative screening.

This module deliberately reuses the same normalized public-data layer as Trecapital.  It never
fetches on import or page load: callers must explicitly invoke :func:`fetch_screening_table` after
an analyst clicks the update button.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Iterable

import pandas as pd

from adapters.base import MODULE1_OVERVIEW_COLUMNS, MODULE1_TIMESERIES_COLUMNS, ProviderResult, normalize_columns
from adapters.vn_public_crawler import PublicFireAntCrawler, PublicVietstockCrawler


APP_ROOT = Path(__file__).resolve().parent
DATA_CACHE_DIR = APP_ROOT / "data_cache"
RAW_DIR = APP_ROOT / "raw_data" / "topdown_screening"

SCREENING_COLUMNS = [
    "Mã CK",
    "Tên doanh nghiệp",
    "Mã ngành",
    "Vốn hóa (tỷ đồng)",
    "P/E (lần)",
    "P/B (lần)",
    "P/CF (lần)",
    "P/S (lần)",
    "Nợ vay/Vốn chủ (lần)",
    "GTGD bình quân 20 phiên (tỷ đồng)",
]


@dataclass(frozen=True)
class ScreeningFetchResult:
    row: dict[str, Any]
    source: str
    note: str


def parse_tickers(raw: str | Iterable[str], *, limit: int = 20) -> list[str]:
    """Normalize a comma/space/newline separated ticker list without guessing invalid codes."""
    tokens = list(raw) if not isinstance(raw, str) else re.split(r"[\s,;|]+", raw.upper())
    result: list[str] = []
    for token in tokens:
        ticker = str(token or "").upper().strip()
        if not ticker or ticker in result:
            continue
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,5}", ticker):
            raise ValueError(f"Mã chứng khoán không hợp lệ: {ticker[:20]}")
        result.append(ticker)
        if len(result) > limit:
            raise ValueError(f"Mỗi lần chỉ cập nhật tối đa {limit} mã để tránh gọi nguồn quá mức.")
    if not result:
        raise ValueError("Hãy nhập ít nhất một mã chứng khoán.")
    return result


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _latest_row(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    out = df.copy()
    sort_cols = [column for column in ("year", "quarter", "period") if column in out.columns]
    if sort_cols:
        for column in ("year", "quarter"):
            if column in out.columns:
                out[column] = pd.to_numeric(out[column], errors="coerce")
        try:
            out = out.sort_values(sort_cols, na_position="first")
        except TypeError:
            pass
    return out.iloc[-1]


def _latest_flow(annual: pd.DataFrame, quarterly: pd.DataFrame, column: str) -> float | None:
    if quarterly is not None and not quarterly.empty and column in quarterly.columns:
        values = pd.to_numeric(quarterly[column], errors="coerce").dropna()
        if len(values) >= 4:
            return _finite(values.tail(4).sum())
    row = _latest_row(annual)
    return _finite(row.get(column)) if row is not None and column in row.index else None


def _latest_balance(annual: pd.DataFrame, quarterly: pd.DataFrame, column: str) -> float | None:
    for frame in (quarterly, annual):
        row = _latest_row(frame)
        if row is not None and column in row.index:
            value = _finite(row.get(column))
            if value is not None:
                return value
    return None


def _interest_bearing_debt(annual: pd.DataFrame, quarterly: pd.DataFrame) -> float | None:
    direct = _latest_balance(annual, quarterly, "interest_bearing_debt_bil")
    if direct is not None:
        return direct
    parts = (
        "short_term_debt_bil",
        "current_portion_long_term_debt_bil",
        "long_term_debt_bil",
        "bonds_payable_bil",
        "lease_liabilities_bil",
        "finance_lease_liabilities_bil",
    )
    values = [_latest_balance(annual, quarterly, column) for column in parts]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


_SECTOR_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("REA", ("bất động sản", "bat dong san", "real estate")),
    ("FIN", ("ngân hàng", "ngan hang", "bank", "bảo hiểm", "bao hiem", "securities", "chứng khoán", "tai chinh", "tài chính")),
    ("ENE", ("dầu", "dau khi", "oil", "gas", "năng lượng", "nang luong", "energy", "than ")),
    ("MAT", ("vật liệu", "vat lieu", "materials", "thép", "thep", "hóa chất", "hoa chat", "phân bón", "phan bon", "cao su", "khai khoáng")),
    ("IND", ("công nghiệp", "cong nghiep", "industrials", "xây dựng", "xay dung", "vận tải", "van tai", "logistics", "hàng không", "hang khong")),
    ("CDI", ("không thiết yếu", "khong thiet yeu", "consumer discretionary", "bán lẻ", "ban le", "ô tô", "o to", "du lịch", "du lich")),
    ("CST", ("thiết yếu", "thiet yeu", "consumer staples", "thực phẩm", "thuc pham", "đồ uống", "do uong", "nông nghiệp", "nong nghiep")),
    ("HEA", ("y tế", "y te", "health", "dược", "duoc", "pharma")),
    ("ITE", ("công nghệ", "cong nghe", "technology", "phần mềm", "phan mem", "bán dẫn", "ban dan")),
    ("TEL", ("viễn thông", "vien thong", "telecom", "truyền thông", "truyen thong", "communication services")),
    ("UTI", ("tiện ích", "tien ich", "utilities", "điện lực", "dien luc", "sản xuất điện", "san xuat dien", "nước sạch", "nuoc sach")),
)


def infer_sector_code(industry: Any, sub_industry: Any = "") -> str:
    text = f"{industry or ''} {sub_industry or ''}".lower()
    for code, keywords in _SECTOR_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return code
    return ""


def _walk_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_records(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_records(nested)


def _first_number(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = _finite(lowered.get(key.lower()))
        if value is not None:
            return value
    return None


def average_trading_value_20(raw_path: Path | None) -> float | None:
    """Extract average matched value from FireAnt price-history responses, in billion VND."""
    if raw_path is None or not Path(raw_path).exists():
        return None
    try:
        payload = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    values: list[float] = []
    for response in payload.get("responses", []) if isinstance(payload, dict) else []:
        url = str(response.get("url", "")).lower()
        if not any(token in url for token in ("historicalquotes", "pricehistory", "symbolpricehistory")):
            continue
        try:
            body = json.loads(str(response.get("body") or ""))
        except json.JSONDecodeError:
            continue
        for row in _walk_records(body):
            value = _first_number(
                row,
                ("totalValue", "tradingValue", "matchedValue", "totalTradingValue", "dealValue"),
            )
            if value is None:
                close = _first_number(row, ("close", "closePrice", "price", "matchPrice"))
                volume = _first_number(row, ("volume", "totalVolume", "matchedVolume", "dealVolume"))
                if close is not None and volume is not None:
                    # Vietnamese quote APIs commonly express price in VND or thousand VND.
                    value = close * volume * (1_000 if close < 1_000 else 1)
            if value is not None and value > 0:
                values.append(value / 1_000_000_000 if value >= 1_000_000 else value)
    return _finite(pd.Series(values[-20:], dtype="float64").mean()) if values else None


def screening_row_from_provider(ticker: str, result: ProviderResult, *, source: str) -> ScreeningFetchResult:
    ticker = ticker.upper().strip()
    overview = result.overview if isinstance(result.overview, pd.DataFrame) else pd.DataFrame()
    annual = result.annual if isinstance(result.annual, pd.DataFrame) else pd.DataFrame()
    quarterly = result.quarterly if isinstance(result.quarterly, pd.DataFrame) else pd.DataFrame()
    selected = overview
    if not overview.empty and "ticker" in overview.columns:
        matched = overview[overview["ticker"].astype(str).str.upper() == ticker]
        selected = matched if not matched.empty else overview
    ov = selected.iloc[-1] if not selected.empty else pd.Series(dtype="object")

    market_cap = _finite(ov.get("market_cap_bil"))
    cfo = _latest_flow(annual, quarterly, "cfo_bil")
    debt = _interest_bearing_debt(annual, quarterly)
    equity = _latest_balance(annual, quarterly, "equity_bil")
    pcf = market_cap / cfo if market_cap is not None and cfo is not None and cfo > 0 else None
    debt_equity = debt / equity if debt is not None and equity is not None and equity > 0 else None
    industry = ov.get("industry", "")
    sub_industry = ov.get("sub_industry", "")
    liquidity = average_trading_value_20(result.raw_path)

    missing = []
    metrics = {
        "vốn hóa": market_cap,
        "P/E": _finite(ov.get("pe")),
        "P/B": _finite(ov.get("pb")),
        "P/CF": pcf,
        "P/S": _finite(ov.get("ps")),
        "nợ vay/vốn chủ": debt_equity,
        "GTGD bình quân 20 phiên": liquidity,
    }
    missing.extend(name for name, value in metrics.items() if value is None)
    note_parts = [str(result.note or "").strip()]
    if missing:
        note_parts.append("Thiếu: " + ", ".join(missing))
    row = {
        "Mã CK": ticker,
        "Tên doanh nghiệp": str(ov.get("company_name", "") or ""),
        "Mã ngành": infer_sector_code(industry, sub_industry),
        "Vốn hóa (tỷ đồng)": market_cap,
        "P/E (lần)": metrics["P/E"],
        "P/B (lần)": metrics["P/B"],
        "P/CF (lần)": pcf,
        "P/S (lần)": metrics["P/S"],
        "Nợ vay/Vốn chủ (lần)": debt_equity,
        "GTGD bình quân 20 phiên (tỷ đồng)": liquidity,
        "Nguồn dữ liệu": source,
        "Ghi chú dữ liệu": " ".join(part for part in note_parts if part),
    }
    return ScreeningFetchResult(row=row, source=source, note=row["Ghi chú dữ liệu"])


def _is_usable(result: ProviderResult) -> bool:
    return any(
        isinstance(frame, pd.DataFrame) and not frame.empty
        for frame in (result.overview, result.annual, result.quarterly)
    )


def _cache_dir(ticker: str) -> Path:
    return DATA_CACHE_DIR / "topdown_screening" / ticker.upper()


def _save_cache(result: ProviderResult, ticker: str) -> None:
    target = _cache_dir(ticker)
    target.mkdir(parents=True, exist_ok=True)
    normalize_columns(result.overview, MODULE1_OVERVIEW_COLUMNS).to_csv(
        target / "company_overview_sample.csv", index=False, encoding="utf-8-sig"
    )
    normalize_columns(result.annual, MODULE1_TIMESERIES_COLUMNS).to_csv(
        target / "financial_timeseries_year.csv", index=False, encoding="utf-8-sig"
    )
    normalize_columns(result.quarterly, MODULE1_TIMESERIES_COLUMNS).to_csv(
        target / "financial_timeseries_quarter.csv", index=False, encoding="utf-8-sig"
    )
    if result.raw_path and Path(result.raw_path).exists():
        (target / "raw_path.txt").write_text(str(Path(result.raw_path).resolve()), encoding="utf-8")


def _load_cache(ticker: str) -> ProviderResult | None:
    candidates = sorted(
        DATA_CACHE_DIR.glob(f"*/{ticker.upper()}/company_overview_sample.csv"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for overview_path in candidates:
        folder = overview_path.parent
        year_path = folder / "financial_timeseries_year.csv"
        quarter_path = folder / "financial_timeseries_quarter.csv"
        try:
            overview = pd.read_csv(overview_path)
            annual = pd.read_csv(year_path) if year_path.exists() else pd.DataFrame()
            quarterly = pd.read_csv(quarter_path) if quarter_path.exists() else pd.DataFrame()
        except (OSError, pd.errors.ParserError):
            continue
        raw_path = None
        raw_pointer = folder / "raw_path.txt"
        if raw_pointer.exists():
            try:
                pointed = Path(raw_pointer.read_text(encoding="utf-8").strip())
                raw_path = pointed if pointed.exists() else None
            except OSError:
                raw_path = None
        result = ProviderResult(overview=overview, annual=annual, quarterly=quarterly, raw_path=raw_path)
        if _is_usable(result):
            result.note = f"Bộ nhớ dữ liệu Trecapital: {folder.name}."
            return result
    return None


def fetch_screening_record(
    ticker: str,
    *,
    fireant_factory: Callable[..., Any] = PublicFireAntCrawler,
    vietstock_factory: Callable[..., Any] = PublicVietstockCrawler,
) -> ScreeningFetchResult:
    """Fetch one ticker from Trecapital's public crawlers, falling back to its normalized cache."""
    ticker = parse_tickers([ticker], limit=1)[0]
    errors: list[str] = []
    for label, factory in (("FireAnt/Trecapital", fireant_factory), ("Vietstock/Trecapital", vietstock_factory)):
        try:
            result = factory(raw_dir=RAW_DIR).fetch(ticker)
            if _is_usable(result):
                _save_cache(result, ticker)
                return screening_row_from_provider(ticker, result, source=label)
            errors.append(f"{label}: không có dữ liệu chuẩn hóa")
        except Exception as exc:  # network/source changes are represented as a data gap
            errors.append(f"{label}: {type(exc).__name__}")
    cached = _load_cache(ticker)
    if cached is not None:
        cached.note = f"{cached.note} Nguồn mới lỗi ({'; '.join(errors)})."
        return screening_row_from_provider(ticker, cached, source="Trecapital cache")
    empty = ProviderResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), note="; ".join(errors))
    return screening_row_from_provider(ticker, empty, source="Research gap")


def fetch_screening_table(
    tickers: str | Iterable[str],
    *,
    progress: Callable[[int, int, str], None] | None = None,
    fetcher: Callable[[str], ScreeningFetchResult] = fetch_screening_record,
) -> pd.DataFrame:
    symbols = parse_tickers(tickers)
    rows = []
    for index, ticker in enumerate(symbols, start=1):
        if progress:
            progress(index, len(symbols), ticker)
        rows.append(fetcher(ticker).row)
    return pd.DataFrame(rows)


__all__ = [
    "SCREENING_COLUMNS",
    "ScreeningFetchResult",
    "average_trading_value_20",
    "fetch_screening_record",
    "fetch_screening_table",
    "infer_sector_code",
    "parse_tickers",
    "screening_row_from_provider",
]
