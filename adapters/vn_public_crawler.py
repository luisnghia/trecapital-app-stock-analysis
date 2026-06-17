from __future__ import annotations

"""No-token public crawlers for FireAnt/Simplize and legacy Vietstock financial fallback.

V14 behavior:
- FireAnt crawler follows the VBA module TCReport_FireAnt from the user's Financial-v1.3.0.xlsm;
- So sánh doanh nghiệp peer universe uses Simplize industry pages, no browser automation;
- save raw responses for audit;
- normalize public JSON/table data directly into Tổng quan doanh nghiệp schema;
- when the dashboard calls these crawlers, normalized data is written to cache and displayed immediately.

The endpoints are intentionally public/no-token. If a site changes structure or blocks public access,
this module returns empty normalized frames plus raw files instead of crashing the dashboard.
"""

from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Iterable
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
import warnings

import httpx
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning, module=__name__)
from bs4 import BeautifulSoup

from .base import ProviderResult, normalize_columns, MODULE1_OVERVIEW_COLUMNS, MODULE1_TIMESERIES_COLUMNS

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://fireant.vn",
    "Referer": "https://fireant.vn/",
}


@dataclass
class CrawlResponse:
    source: str
    url: str
    status_code: int | None
    content_type: str | None
    body: str | None
    error: str | None = None


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(12.0, connect=8.0), follow_redirects=True, headers=HEADERS)


def _simplize_client() -> httpx.Client:
    headers = dict(HEADERS)
    headers.update({
        "Origin": "https://simplize.vn",
        "Referer": "https://simplize.vn/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
        "X-Requested-With": "",
    })
    return httpx.Client(timeout=httpx.Timeout(10.0, connect=6.0), follow_redirects=True, headers=headers)


def _now_year() -> int:
    return datetime.now().year


def _save_raw(raw_dir: Path, ticker: str, source: str, payload: Any) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{source}_{ticker.upper()}_{int(time.time())}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _get(client: httpx.Client, source: str, url: str) -> CrawlResponse:
    try:
        resp = client.get(url)
        ct = resp.headers.get("content-type")
        text = resp.text[:3_000_000] if resp.text else ""
        return CrawlResponse(source, url, resp.status_code, ct, text)
    except Exception as exc:
        return CrawlResponse(source, url, None, None, None, str(exc))


def _try_json(text: str | None) -> Any | None:
    if not text:
        return None
    stripped = text.strip().lstrip("\ufeff")
    if not stripped:
        return None
    # A few endpoints return JSON after harmless leading characters. Keep it tolerant.
    if stripped[0] not in "[{":
        m = re.search(r"([\[{].*)", stripped, flags=re.S)
        stripped = m.group(1).strip() if m else stripped
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except Exception:
        return None


def _norm_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d").replace("Đ", "D")
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


# V23.24: strict ticker validation for peer crawling.
# Vietstock/FireAnt JSON/HTML may contain generic words such as STOCK/HOSTC/HTML that match a loose
# uppercase regex but are not Vietnamese listed tickers. Keep this centralized so peer lists do not
# contain false codes.
PEER_TICKER_BLACKLIST = {
    "HTML", "HTTP", "HTTPS", "JSON", "POST", "GET", "VN", "EN", "API", "CSS", "JS", "PDF", "XLS",
    "ROE", "ROA", "ROIC", "EPS", "PE", "PB", "PS", "FCF", "CFO", "EBIT", "EBITDA", "LNST", "LNTT", "TTM", "YOY", "QOQ", "MOS", "WACC", "NIM", "CASA", "NPL",
    "TRUE", "FALSE", "NULL", "NONE", "NAN", "STOCK", "STOCKS", "HOSTC", "HOST", "HOSE", "HNX", "UPCOM",
    "INDEX", "CODE", "NAME", "SYMBOL", "TICKER", "MARKET", "FLOOR", "HOME", "LOGIN", "LOGO", "DATA",
    "IR", "PR", "ETF", "GDP", "PMI", "RRG", "GMT", "OK", "ID", "URL", "TAB",  "XML", "SVG",
}


def _is_probable_vn_ticker(code: Any, *, base_ticker: str = "") -> bool:
    code_text = str(code or "").upper().strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,5}", code_text):
        return False
    if code_text in PEER_TICKER_BLACKLIST:
        return False
    if base_ticker and code_text == base_ticker.upper().strip():
        return True
    # Most Vietnamese stock tickers are 3 characters; allow 2-4/5 for special cases but reject
    # long English words that escaped the blacklist.
    if len(code_text) > 4 and not any(ch.isdigit() for ch in code_text):
        return False
    if re.search(r"(HTML|HTTP|JSON|STOCK|HOST|INDEX|LOGIN|DATA|ROE|ROA|EPS|FCF|CFO|MOS|WACC)", code_text):
        return False
    return True


def _slugify_vietstock(value: Any) -> str:
    s = _norm_text(value)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s



def _extract_vietstock_gics_from_html(html_text: str | None) -> dict[str, Any]:
    """Extract GICS level codes/names embedded in Vietstock stock-detail scripts."""
    out: dict[str, Any] = {}
    if not html_text:
        return out
    for level, code in re.findall(r"_gicsLevel([1-4])\s*=\s*([0-9]+)", html_text):
        out[f"level{level}"] = code
    for level, _quote, name in re.findall(r"_gicsNameLevel([1-4])\s*=\s*([\"'])(.*?)\2", html_text):
        out[f"name{level}"] = name
    names: list[str] = []
    for i in range(1, 5):
        name = str(out.get(f"name{i}") or "").strip()
        if name and name not in names:
            names.append(name)
    out["industry_path"] = " > ".join(names)
    return out



# V23.25: no synthetic peer fallback lists are kept in code.
# If Vietstock dynamic browser/API extraction fails, So sánh doanh nghiệp returns an empty peer list and asks the user to import CSV.


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"none", "nan", "null", "-", "--"}:
        return None
    neg = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9,\.\-]", "", text)
    if "," in cleaned and "." not in cleaned:
        # Decimal comma: 17,5. Thousands separators: 379,778,413 or 17,355.
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) != 3:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." in cleaned:
        # Prefer comma as thousands separator for web JSON/table strings like 1,234.56.
        cleaned = cleaned.replace(",", "")
    try:
        val = float(cleaned)
        return -abs(val) if neg else val
    except Exception:
        return None


def _value_to_bil(value: Any) -> float | None:
    """Heuristic scale to billion VND.

    Public sources may expose raw VND, thousand VND, million VND or already-billions.
    The heuristic avoids dividing already-small ratio/EPS values, and keeps typical billion-scale
    financial statements readable on the dashboard.
    """
    v = _to_float(value)
    if v is None:
        return None
    av = abs(v)
    if av >= 1_000_000_000:  # likely raw VND
        return v / 1_000_000_000
    if av >= 1_000_000:  # likely million VND
        return v / 1_000
    return v


def _maybe_pct(value: Any) -> float | None:
    v = _to_float(value)
    if v is None:
        return None
    return v * 100 if abs(v) <= 3 else v




def _avg_current_and_previous(df: pd.DataFrame, value_col: str) -> pd.Series:
    """Average current and previous period value within annual/quarterly groups."""
    if value_col not in df.columns:
        return pd.Series(index=df.index, dtype="float64")
    sort_cols = [c for c in ["period_type", "year", "quarter"] if c in df.columns]
    if "period_type" in df.columns and sort_cols:
        tmp = df[sort_cols + [value_col]].copy().sort_values(sort_cols)
        prev = tmp.groupby("period_type", dropna=False)[value_col].shift(1)
        avg = (tmp[value_col] + prev) / 2
        avg = avg.fillna(tmp[value_col])
        return avg.reindex(df.index)
    return ((df[value_col] + df[value_col].shift(1)) / 2).fillna(df[value_col])


def _effective_tax_rate_from_df(df: pd.DataFrame) -> pd.Series:
    if {"tax_expense_bil", "pretax_profit_bil"}.issubset(df.columns):
        rate = pd.to_numeric(df["tax_expense_bil"], errors="coerce") / pd.to_numeric(df["pretax_profit_bil"], errors="coerce").replace({0: pd.NA})
        return rate.clip(lower=0, upper=0.5).fillna(0.20)
    return pd.Series(0.20, index=df.index, dtype="float64")


def _recompute_roic_and_roe_v14(out: pd.DataFrame) -> pd.DataFrame:
    """Recompute ROIC/ROE using average capital and separate Li Lu/Deployed view.

    Main `roic_pct` is conservative NOPAT / average capital employed.
    `roic_lilu_pct` is an additional Li Lu-style return on deployed operating capital.
    """
    if out.empty:
        return out
    out = out.copy()
    # Core operating profit excludes financial income/expense when cash and financial investments are excluded from capital.
    if {"gross_profit_bil", "selling_expense_bil", "admin_expense_bil"}.issubset(out.columns):
        if "core_operating_profit_bil" not in out.columns:
            out["core_operating_profit_bil"] = pd.NA
        core = out["gross_profit_bil"] - out["selling_expense_bil"].abs() - out["admin_expense_bil"].abs()
        out["core_operating_profit_bil"] = out["core_operating_profit_bil"].fillna(core)
    elif {"operating_profit_bil", "financial_income_bil", "financial_expense_bil"}.issubset(out.columns):
        if "core_operating_profit_bil" not in out.columns:
            out["core_operating_profit_bil"] = pd.NA
        core = out["operating_profit_bil"] - out["financial_income_bil"].fillna(0) + out["financial_expense_bil"].fillna(0)
        out["core_operating_profit_bil"] = out["core_operating_profit_bil"].fillna(core)
    elif "operating_profit_bil" in out.columns:
        if "core_operating_profit_bil" not in out.columns:
            out["core_operating_profit_bil"] = pd.NA
        out["core_operating_profit_bil"] = out["core_operating_profit_bil"].fillna(out["operating_profit_bil"])

    if "nopat_bil" not in out.columns:
        out["nopat_bil"] = pd.NA
    if "core_operating_profit_bil" in out.columns:
        tax_rate = _effective_tax_rate_from_df(out)
        out["nopat_bil"] = out["nopat_bil"].fillna(out["core_operating_profit_bil"] * (1 - tax_rate))

    if {"current_assets_bil", "current_liabilities_bil"}.issubset(out.columns):
        if "working_capital_bil" not in out.columns:
            out["working_capital_bil"] = pd.NA
        out["working_capital_bil"] = out["working_capital_bil"].fillna(out["current_assets_bil"] - out["current_liabilities_bil"])
        cash = out["cash_equivalents_bil"] if "cash_equivalents_bil" in out.columns else 0
        sti = out["short_term_investments_bil"] if "short_term_investments_bil" in out.columns else 0
        if "operating_working_capital_bil" not in out.columns:
            out["operating_working_capital_bil"] = pd.NA
        out["operating_working_capital_bil"] = out["operating_working_capital_bil"].fillna(out["current_assets_bil"] - cash - sti - out["current_liabilities_bil"])
    if {"total_assets_bil", "current_liabilities_bil"}.issubset(out.columns):
        if "capital_employed_bil" not in out.columns:
            out["capital_employed_bil"] = pd.NA
        out["capital_employed_bil"] = out["capital_employed_bil"].fillna(out["total_assets_bil"] - out["current_liabilities_bil"])
        if "avg_capital_employed_bil" not in out.columns:
            out["avg_capital_employed_bil"] = pd.NA
        out["avg_capital_employed_bil"] = out["avg_capital_employed_bil"].fillna(_avg_current_and_previous(out, "capital_employed_bil"))
    if {"operating_working_capital_bil", "fixed_assets_bil"}.issubset(out.columns):
        if "deployed_capital_bil" not in out.columns:
            out["deployed_capital_bil"] = pd.NA
        out["deployed_capital_bil"] = out["deployed_capital_bil"].fillna(out["operating_working_capital_bil"] + out["fixed_assets_bil"])
        if "avg_deployed_capital_bil" not in out.columns:
            out["avg_deployed_capital_bil"] = pd.NA
        out["avg_deployed_capital_bil"] = out["avg_deployed_capital_bil"].fillna(_avg_current_and_previous(out, "deployed_capital_bil"))

    # Annual uses annual NOPAT. Quarterly uses TTM numerator with average capital of the latest quarter.
    if "roic_standard_pct" not in out.columns:
        out["roic_standard_pct"] = pd.NA
    if "roic_lilu_pct" not in out.columns:
        out["roic_lilu_pct"] = pd.NA
    if {"nopat_bil", "avg_capital_employed_bil"}.issubset(out.columns):
        roic_std = (out["nopat_bil"] / out["avg_capital_employed_bil"].replace({0: pd.NA}) * 100).where(out["avg_capital_employed_bil"] > 0)
        out["roic_standard_pct"] = out["roic_standard_pct"].fillna(roic_std)
    if {"core_operating_profit_bil", "avg_deployed_capital_bil"}.issubset(out.columns):
        roic_lilu = (out["core_operating_profit_bil"] / out["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(out["avg_deployed_capital_bil"] > 0)
        out["roic_lilu_pct"] = out["roic_lilu_pct"].fillna(roic_lilu)
    qmask = out.get("period_type", pd.Series(index=out.index, dtype="object")).eq("Q")
    if qmask.any():
        q = out.loc[qmask].sort_values(["year", "quarter"]).copy()
        if {"nopat_bil", "avg_capital_employed_bil"}.issubset(q.columns):
            nopat_ttm = q["nopat_bil"].rolling(4, min_periods=4).sum()
            q_roic_std = (nopat_ttm / q["avg_capital_employed_bil"].replace({0: pd.NA}) * 100).where(q["avg_capital_employed_bil"] > 0)
            out.loc[q.index, "roic_standard_pct"] = q_roic_std.combine_first(out.loc[q.index, "roic_standard_pct"])
        if {"core_operating_profit_bil", "avg_deployed_capital_bil"}.issubset(q.columns):
            core_ttm = q["core_operating_profit_bil"].rolling(4, min_periods=4).sum()
            q_roic_lilu = (core_ttm / q["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(q["avg_deployed_capital_bil"] > 0)
            out.loc[q.index, "roic_lilu_pct"] = q_roic_lilu.combine_first(out.loc[q.index, "roic_lilu_pct"])

    if "roic_pct" not in out.columns:
        out["roic_pct"] = pd.NA
    # Override old V13 deployed ROIC if present; main metric should be conservative standard ROIC.
    out["roic_pct"] = out["roic_standard_pct"].combine_first(out.get("roic_fireant_pct", pd.Series(index=out.index, dtype="float64"))).combine_first(out["roic_pct"])

    # ROE self-calculated should use average equity, not ending equity.
    if {"net_profit_bil", "equity_bil"}.issubset(out.columns):
        if "avg_equity_bil" not in out.columns:
            out["avg_equity_bil"] = pd.NA
        out["avg_equity_bil"] = out["avg_equity_bil"].fillna(_avg_current_and_previous(out, "equity_bil"))
        if "roe_actual_pct" not in out.columns:
            out["roe_actual_pct"] = pd.NA
        roe_calc = out["net_profit_bil"] / out["avg_equity_bil"].replace({0: pd.NA}) * 100
        out["roe_actual_pct"] = roe_calc.combine_first(out["roe_actual_pct"])
    return out

def _clean_key(key: str) -> str:
    return _norm_text(key).replace("_", "").replace(" ", "")


def _find_key(record: dict[str, Any], aliases: Iterable[str]) -> str | None:
    lookup = {_clean_key(str(k)): k for k in record.keys()}
    for alias in aliases:
        k = lookup.get(_clean_key(alias))
        if k is not None:
            return k
    return None


def _get_by_alias(record: dict[str, Any], aliases: Iterable[str]) -> Any:
    k = _find_key(record, aliases)
    return record.get(k) if k is not None else None


def _collect_records(obj: Any, max_records: int = 250_000) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def walk(x: Any) -> None:
        if len(out) >= max_records:
            return
        if isinstance(x, dict):
            out.append(x)
            for v in x.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return out


def _extract_html_tables(raw_dir: Path, ticker: str, source: str, responses: list[dict[str, Any]]) -> tuple[list[str], list[pd.DataFrame]]:
    saved: list[str] = []
    tables_out: list[pd.DataFrame] = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for idx, resp in enumerate(responses, start=1):
        body = resp.get("body") or ""
        ctype = (resp.get("content_type") or "").lower()
        if "<table" not in body.lower() and "html" not in ctype:
            continue
        try:
            tables = pd.read_html(StringIO(body))
        except Exception:
            continue
        for t_idx, table in enumerate(tables, start=1):
            if table.empty:
                continue
            out = raw_dir / f"{source}_{ticker.upper()}_table_{idx}_{t_idx}_{int(time.time())}.csv"
            table.to_csv(out, index=False, encoding="utf-8-sig")
            saved.append(str(out))
            tables_out.append(table)
    return saved, tables_out


def _extract_json_preview(raw_dir: Path, ticker: str, source: str, responses: list[dict[str, Any]]) -> tuple[list[str], list[Any]]:
    saved: list[str] = []
    parsed_payloads: list[Any] = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for idx, resp in enumerate(responses, start=1):
        parsed = _try_json(resp.get("body"))
        if parsed is None:
            continue
        out = raw_dir / f"{source}_{ticker.upper()}_json_{idx}_{int(time.time())}.json"
        out.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        saved.append(str(out))
        parsed_payloads.append(parsed)
    return saved, parsed_payloads



METRIC_MAP = {
    # Income statement
    "revenue_bil": ["doanh thu thuan", "doanh thu ban hang", "doanh thu ban hang va cung cap dich vu", "net revenue", "total revenue", "total_revenue", "revenue", "sales", "net sales", "doanh thu", "3. doanh thu thuan"],
    "gross_revenue_bil": ["tong doanh thu", "gross revenue", "gross_revenue"],
    "gross_profit_bil": ["loi nhuan gop", "gross profit", "gross_profit"],
    "net_profit_bil": ["loi nhuan sau thue cua co dong cua cong ty me", "loi nhuan sau thue thu nhap doanh nghiep", "loi nhuan sau thue", "lnst", "loi nhuan rong", "net income", "net_income", "net profit", "net_profit", "profit after tax", "profit_after_tax", "profit after tax attributable"],
    "pretax_profit_bil": ["loi nhuan truoc thue", "lntt", "profit before tax", "pre tax", "pre_tax_income", "pre_tax_profit"],
    # Cash flow
    "cfo_bil": ["luu chuyen tien thuan tu hoat dong kinh doanh", "luu chuyen tien tu hoat dong kinh doanh", "net cash flows from operating activities", "net_cash_flow_from_operating_activities", "cash flow from operating", "operating cash flow", "operating_cash_flow", "cfo"],
    "cfi_bil": ["luu chuyen tien thuan tu hoat dong dau tu", "cash flow from investing", "investing_cash_flow", "cfi"],
    "cff_bil": ["luu chuyen tien thuan tu hoat dong tai chinh", "cash flow from financing", "financing_cash_flow", "cff"],
    "capex_bil": ["tien chi de mua sam", "mua sam xay dung tscd", "tien chi de mua sam xay dung tscd", "purchase of fixed assets", "capital expenditure", "capital_expenditures", "capex", "purchase of property"],
    "cash_dividend_bil": ["co tuc loi nhuan da tra cho chu so huu", "co tuc da tra", "co tuc tien mat", "dividend paid", "dividend_payments", "cash dividend", "dividends paid"],
    "depreciation_bil": ["khau hao", "depreciation", "depreciation_amortization", "amortization"],
    "working_capital_change_bil": ["thay doi von luu dong", "change in working capital", "working_capital_changes", "other operating assets and liabilities"],
    # Balance sheet / ratios
    "total_assets_bil": ["tong cong tai san", "tong tai san", "total assets", "total_assets"],
    "equity_bil": ["von chu so huu", "equity", "total_equity", "stockholders equity", "shareholders equity", "shareholders_equity"],
    "eps_vnd": ["eps", "earnings per share", "earnings_per_share", "lai co ban tren co phieu"],
    "roe_pct": ["roe", "return on equity", "return_on_equity"],
    "roa_pct": ["roa", "return on assets", "return_on_assets"],
    "roic_pct": ["roic", "return_on_invested_capital", "return on invested capital"],
    "gross_margin_pct": ["bien loi nhuan gop", "gross margin", "gross_profit_margin"],
    "net_margin_pct": ["bien loi nhuan rong", "net margin", "net_profit_margin"],
    "asset_turnover": ["asset_turnover", "vong quay tai san"],
    "equity_multiplier": ["equity_multiplier", "don bay tai chinh"],
}


def _metric_from_label(label: Any) -> str | None:
    n = _norm_text(label)
    if not n:
        return None
    # Exact match first to avoid broad aliases such as "equity" capturing "return on equity".
    exact: list[tuple[str, str]] = []
    contains: list[tuple[int, str, str]] = []
    for field, aliases in METRIC_MAP.items():
        for alias in aliases:
            a = _norm_text(alias)
            if not a:
                continue
            exact.append((a, field))
            contains.append((len(a), a, field))
    for a, field in exact:
        if n == a:
            return field
    for _, a, field in sorted(contains, key=lambda x: x[0], reverse=True):
        if a in n:
            return field
    return None


def _extract_period(record: dict[str, Any], default_quarterly: bool = False) -> tuple[str, int, int | None, str] | None:
    """Return (period_type, year, quarter, label).

    Handles Vietstock/VNDIRECT shapes such as:
    - Year/Quarter numeric fields
    - period labels: 2025, Q1/2026, 2026Q1
    - date/fiscalDate/reportDate: 2026-03-31. If the record says QUARTER or default_quarterly=True,
      infer quarter from the month.
    """
    year = _to_float(_get_by_alias(record, ["year", "nam", "reportyear", "fiscalyear", "report_year", "fiscal_year", "fiscalYear"]))
    quarter = _to_float(_get_by_alias(record, ["quarter", "quy", "reportquarter", "fiscalquarter", "report_quarter", "fiscal_quarter", "fiscalQuarter"]))
    period = _get_by_alias(record, ["period", "periodname", "ky", "term", "date", "reportdate", "report_date", "fiscaldate", "fiscal_date", "tradingdate", "namquy", "yearquarter", "periodDate"])
    report_type = _norm_text(_get_by_alias(record, ["reporttype", "report_type", "ReportTermType", "termType", "type"]))
    force_quarter = default_quarterly or any(x in report_type for x in ["quarter", "quy", "quarterly", "2"])

    if year is None and period is not None:
        text_raw = str(period).strip()
        text = text_raw.upper().replace(" ", "")
        text = text.replace("QUÝ", "Q").replace("QUY", "Q")
        m = re.search(r"Q([1-4])[/\-.]?(20\d{2}|19\d{2})", text)
        if m:
            quarter = float(m.group(1))
            year = float(m.group(2))
        else:
            m = re.search(r"(20\d{2}|19\d{2})[/\-.]?Q([1-4])", text)
            if m:
                year = float(m.group(1))
                quarter = float(m.group(2))
            else:
                # Date or bare year. Infer quarter from month only for quarterly records.
                mdate = re.search(r"(20\d{2}|19\d{2})[-/\.](\d{1,2})[-/\.](\d{1,2})", text)
                if mdate:
                    year = float(mdate.group(1))
                    if force_quarter:
                        month = int(mdate.group(2))
                        quarter = float((month - 1) // 3 + 1)
                else:
                    m = re.search(r"(20\d{2}|19\d{2})", text)
                    if m:
                        year = float(m.group(1))
    if year is None:
        return None
    y = int(year)
    q = int(quarter) if quarter is not None and 1 <= int(quarter) <= 4 else None
    if q:
        return "Q", y, q, f"Q{q}/{y}"
    if force_quarter:
        return None
    return "Y", y, None, str(y)

def _extract_value_record_timeseries(records: list[dict[str, Any]], ticker: str, default_quarterly: bool = False) -> pd.DataFrame:
    rows: dict[tuple[str, int, int | None], dict[str, Any]] = {}
    label_aliases = [
        "name", "title", "item", "indicator", "metric", "field", "rowname", "rowName", "criteria",
        "tenchitieu", "chitieu", "label", "itemName", "normName", "displayName", "codeName", "Name", "name"
    ]
    value_aliases = ["value", "Value", "val", "data", "amount", "numericValue", "gia tri", "giatri", "column2", "value1"]

    for rec in records:
        if not isinstance(rec, dict):
            continue
        report_type_raw = _get_by_alias(rec, ["reporttype", "report_type", "reportType", "ReportTermType", "termType"])
        rt = _norm_text(report_type_raw)
        rec_default_quarterly = default_quarterly or any(x in rt for x in ["quarter", "quy", "2"])
        period = _extract_period(rec, default_quarterly=rec_default_quarterly)
        if period is None:
            continue
        period_type, year, quarter, label_period = period
        row_key = (period_type, year, quarter)
        base = rows.setdefault(row_key, {"ticker": ticker, "period_type": period_type, "period": label_period, "year": year, "quarter": quarter})

        # Shape 1: {itemName: "Doanh thu thuần", numericValue: 123, fiscalDate: "2025-12-31"}
        label = _get_by_alias(rec, label_aliases)
        field = _metric_from_label(label)
        value = _get_by_alias(rec, value_aliases)
        if field and value is not None:
            if field.endswith("_pct"):
                base[field] = _maybe_pct(value)
            elif field in {"eps_vnd"}:
                base[field] = _to_float(value)
            else:
                base[field] = _value_to_bil(value)

        # Shape 2: {Year: 2024, Revenue: 123, NetProfit: 45, ...}
        for k, v in rec.items():
            field = _metric_from_label(k)
            if field is None or v is None:
                continue
            if field.endswith("_pct"):
                base[field] = _maybe_pct(v)
            elif field in {"eps_vnd"}:
                base[field] = _to_float(v)
            else:
                base[field] = _value_to_bil(v)

    if not rows:
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    df = pd.DataFrame(rows.values())
    if "period_type" in df.columns:
        annual = df[df["period_type"].eq("Y")].drop_duplicates(["year"], keep="last").sort_values("year")
        quarterly = df[df["period_type"].eq("Q")].drop_duplicates(["year", "quarter"], keep="last").sort_values(["year", "quarter"])
        df = pd.concat([annual, quarterly], ignore_index=True)
    return normalize_columns(df, MODULE1_TIMESERIES_COLUMNS)

def _extract_wide_table_timeseries(tables: list[pd.DataFrame], ticker: str) -> pd.DataFrame:
    """Extract financial series from Vietstock/FireAnt wide HTML tables.

    Many public pages return tables in the shape:
    [Chỉ tiêu | 2025 | 2024 | 2023] or [Chỉ tiêu | Q1/2026 | Q4/2025 ...].
    The previous parser only handled JSON records where each row already had Year/Quarter fields;
    this parser pivots wide tables into the dashboard schema.
    """
    rows: dict[tuple[str, int, int | None], dict[str, Any]] = {}
    if not tables:
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)

    for table in tables:
        if not isinstance(table, pd.DataFrame) or table.empty:
            continue
        clean = table.copy()
        # Flatten MultiIndex columns and normalize duplicate names.
        flat_cols: list[str] = []
        for col in clean.columns:
            if isinstance(col, tuple):
                text = " ".join(str(x) for x in col if str(x) != "nan")
            else:
                text = str(col)
            flat_cols.append(text.strip())
        clean.columns = flat_cols

        # Choose the most likely label column.
        label_col = clean.columns[0]
        for col in clean.columns:
            n = _norm_text(col)
            if any(x in n for x in ["chi tieu", "chỉ tiêu", "criteria", "indicator", "khoan muc", "name"]):
                label_col = col
                break

        period_cols: list[tuple[str, tuple[str, int, int | None, str]]] = []
        for col in clean.columns:
            if col == label_col:
                continue
            period = _extract_period({"period": col})
            if period is not None:
                period_cols.append((col, period))
        if not period_cols:
            continue

        for _, row in clean.iterrows():
            field = _metric_from_label(row.get(label_col))
            if field is None:
                continue
            for col, period in period_cols:
                period_type, year, quarter, label_period = period
                value = row.get(col)
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    continue
                row_key = (period_type, year, quarter)
                base = rows.setdefault(
                    row_key,
                    {"ticker": ticker.upper(), "period_type": period_type, "period": label_period, "year": year, "quarter": quarter},
                )
                if field.endswith("_pct"):
                    base[field] = _maybe_pct(value)
                elif field in {"eps_vnd"}:
                    base[field] = _to_float(value)
                else:
                    base[field] = _value_to_bil(value)

    if not rows:
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    df = pd.DataFrame(rows.values())
    annual = df[df["period_type"].eq("Y")].drop_duplicates(["year"], keep="last").sort_values("year")
    quarterly = df[df["period_type"].eq("Q")].drop_duplicates(["year", "quarter"], keep="last").sort_values(["year", "quarter"])
    return normalize_columns(pd.concat([annual, quarterly], ignore_index=True), MODULE1_TIMESERIES_COLUMNS)

def _build_overview_from_records(records: list[dict[str, Any]], ticker: str, source: str) -> pd.DataFrame:
    aliases = {
        "symbol": ["symbol", "ticker", "stockcode", "code"],
        "company_name": ["companyname", "company_name", "name", "fullname", "organname", "tencongty"],
        "exchange": ["exchange", "floor", "san", "market"],
        "industry": ["industry", "sector", "nganh"],
        "sub_industry": ["subindustry", "sub_industry", "icbname", "nganhcap2"],
        "market_cap_bil": ["marketcap", "marketcapitalization", "market_cap", "vonthihoa"],
        "shares_outstanding_mil": ["sharesoutstanding", "outstandingshares", "listedshares", "shares", "soluongcpniemyet"],
        "current_price": ["price", "lastprice", "closeprice", "currentprice", "matchprice"],
        "eps": ["eps"],
        "pe": ["pe", "peratio"],
        "pb": ["pb", "pbratio"],
        "ps": ["ps", "psratio"],
        "roe": ["roe"],
        "roa": ["roa"],
        "roic": ["roic"],
    }
    best: dict[str, Any] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        rec_symbol = _get_by_alias(rec, aliases["symbol"])
        # Prefer exact ticker records, but allow quote payloads without symbol aliases if they hold many financial ratios.
        if rec_symbol is not None and str(rec_symbol).upper() != ticker.upper():
            continue
        candidate: dict[str, Any] = {"ticker": ticker.upper(), "updated_at": f"Dữ liệu cập nhật {datetime.now():%Y-%m-%d %H:%M:%S}"}
        for out_col, keys in aliases.items():
            if out_col == "symbol":
                continue
            val = _get_by_alias(rec, keys)
            if val is not None:
                candidate[out_col] = val
        if len(candidate) > len(best):
            best = candidate

    if not best:
        return pd.DataFrame(columns=MODULE1_OVERVIEW_COLUMNS)

    # Numeric scaling.
    for col in ["market_cap_bil"]:
        if col in best:
            best[col] = _value_to_bil(best[col])
    if "shares_outstanding_mil" in best:
        v = _to_float(best["shares_outstanding_mil"])
        if v is not None and abs(v) >= 1_000_000:
            v = v / 1_000_000
        best["shares_outstanding_mil"] = v
    for col in ["current_price", "eps", "pe", "pb", "ps"]:
        if col in best:
            best[col] = _to_float(best[col])
    for col in ["roe", "roa", "roic"]:
        if col in best:
            best[col] = _maybe_pct(best[col])
    return normalize_columns(pd.DataFrame([best]), MODULE1_OVERVIEW_COLUMNS)




def _html_to_text(html: str | None) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        return re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html or "")


def _extract_tables_from_payload_strings(raw_dir: Path, ticker: str, source: str, payloads: list[Any]) -> tuple[list[str], list[pd.DataFrame]]:
    """Parse tables embedded inside JSON strings, common in Vietstock AJAX responses."""
    tables: list[pd.DataFrame] = []
    saved: list[str] = []
    raw_dir.mkdir(parents=True, exist_ok=True)

    def walk(x: Any):
        if isinstance(x, dict):
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
        elif isinstance(x, str) and ("<table" in x.lower() or "<tr" in x.lower()):
            yield x

    for idx, html in enumerate(walk(payloads), start=1):
        try:
            found = pd.read_html(StringIO(html))
        except Exception:
            # Some Vietstock payloads contain only rows; wrap in table.
            try:
                found = pd.read_html(StringIO(f"<table>{html}</table>"))
            except Exception:
                continue
        for j, table in enumerate(found, start=1):
            if table.empty:
                continue
            out = raw_dir / f"{source}_{ticker.upper()}_json_table_{idx}_{j}_{int(time.time())}.csv"
            table.to_csv(out, index=False, encoding="utf-8-sig")
            saved.append(str(out))
            tables.append(table)
    return saved, tables


def _extract_overview_from_html(responses: list[dict[str, Any]], ticker: str, source: str) -> pd.DataFrame:
    """Extract basic profile/quote values from FireAnt/Vietstock static HTML text when JSON is blocked."""
    best: dict[str, Any] = {}
    for resp in responses:
        body = resp.get("body") or ""
        if not body:
            continue
        text = _html_to_text(body)
        norm = _norm_text(text)
        if ticker.lower() not in norm:
            continue
        cand: dict[str, Any] = {"ticker": ticker.upper(), "updated_at": f"Dữ liệu cập nhật {datetime.now():%Y-%m-%d %H:%M:%S}"}
        # Company name patterns from title/meta or text chunks.
        m = re.search(r"<title>(.*?)</title>", body, flags=re.I | re.S)
        if m:
            title = BeautifulSoup(m.group(1), "html.parser").get_text(" ").strip()
            if title:
                cand["company_name"] = title.split("|")[0].strip()
        m = re.search(rf"{re.escape(ticker.upper())}\s*[-–]\s*([^<\n\r|]+)", body, flags=re.I)
        if m:
            cand["company_name"] = re.sub(r"\s+", " ", m.group(1)).strip()
        # Vietstock profile title: CTCP ... (HOSE: DGC)
        m = re.search(r"([^<>]{5,120})\((HOSE|HNX|UPCOM)\s*:\s*" + re.escape(ticker.upper()) + r"\)", body, flags=re.I)
        if m:
            cand["company_name"] = BeautifulSoup(m.group(1), "html.parser").get_text(" ").strip()
            cand["exchange"] = m.group(2).upper()
        label_patterns = {
            "market_cap_bil": [r"Thị giá vốn\s*([0-9.,]+)\s*tỷ", r"Thi gia von\s*([0-9.,]+)\s*ty"],
            "shares_outstanding_mil": [r"Số lượng CPLH\s*([0-9.,]+)", r"So luong CPLH\s*([0-9.,]+)"],
            "pe": [r"P/E\s*([0-9.,]+)"],
            "eps": [r"EPS\s*([0-9.,]+)"],
            "current_price": [r"Giá hiện tại\s*([0-9.,]+)", r"Gia hien tai\s*([0-9.,]+)"],
        }
        for col, pats in label_patterns.items():
            if col in cand:
                continue
            for pat in pats:
                m = re.search(pat, text, flags=re.I)
                if m:
                    val = _to_float(m.group(1))
                    if val is None:
                        continue
                    if col == "shares_outstanding_mil" and abs(val) >= 1_000_000:
                        val = val / 1_000_000
                    cand[col] = val
                    break
        if len(cand) > len(best):
            best = cand
    if not best:
        return pd.DataFrame(columns=MODULE1_OVERVIEW_COLUMNS)
    return normalize_columns(pd.DataFrame([best]), MODULE1_OVERVIEW_COLUMNS)


def _iter_fireant_period_values(obj: Any) -> Iterable[dict[str, Any]]:
    """Yield nested FireAnt period-value dictionaries.

    The VBA module TCReport_FireAnt.Ex reads LastestFinancialReports by splitting records with
    {"ID":...} and then applying this regex inside each item:
    {"Period":"...","Year":yyyy,"Quarter":q,"Value":...}
    A normal recursive JSON flattener loses the parent "Name" label; this helper keeps the parent
    financial line item and attaches every nested period value to it.
    """
    if isinstance(obj, dict):
        has_period_value = (
            _find_key(obj, ["Year", "year"]) is not None
            and _find_key(obj, ["Quarter", "quarter"]) is not None
            and _find_key(obj, ["Value", "value"]) is not None
        )
        if has_period_value:
            yield obj
        for v in obj.values():
            if isinstance(v, (dict, list)):
                yield from _iter_fireant_period_values(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_fireant_period_values(item)


def _extract_fireant_nested_reports(payloads: list[Any], ticker: str) -> pd.DataFrame:
    """Parse FireAnt LastestFinancialReports shape exactly like the Excel VBA module.

    FireAnt returns rows such as:
    {
      "ID": ..., "Name": "Doanh thu thuần", "Level": 1,
      "Values": [{"Period":"...", "Year":2025, "Quarter":0, "Value":12345}, ...]
    }
    The dashboard needs the inverse shape: one row per period with each metric as a column.
    """
    rows: dict[tuple[str, int, int | None], dict[str, Any]] = {}

    def walk(parent: Any) -> None:
        if isinstance(parent, dict):
            label = _get_by_alias(parent, ["Name", "name", "Title", "title", "ItemName", "itemName", "DisplayName", "displayName"])
            field = _metric_from_label(label)
            if field:
                for pv in _iter_fireant_period_values(parent):
                    year = _to_float(_get_by_alias(pv, ["Year", "year"]))
                    quarter_raw = _to_float(_get_by_alias(pv, ["Quarter", "quarter"]))
                    value = _get_by_alias(pv, ["Value", "value"])
                    if year is None or value is None:
                        continue
                    q = int(quarter_raw) if quarter_raw is not None else 0
                    if q > 0:
                        period_type, quarter, period_label = "Q", q, f"Q{q}/{int(year)}"
                    else:
                        period_type, quarter, period_label = "Y", None, str(int(year))
                    key = (period_type, int(year), quarter)
                    base = rows.setdefault(
                        key,
                        {"ticker": ticker.upper(), "period_type": period_type, "period": period_label, "year": int(year), "quarter": quarter},
                    )
                    if field.endswith("_pct"):
                        base[field] = _maybe_pct(value)
                    elif field == "eps_vnd":
                        base[field] = _to_float(value)
                    else:
                        base[field] = _value_to_bil(value)
            # Still descend because some payloads wrap the report rows under data/items.
            for v in parent.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(parent, list):
            for item in parent:
                walk(item)

    for payload in payloads:
        walk(payload)

    if not rows:
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    df = pd.DataFrame(rows.values())
    annual = df[df["period_type"].eq("Y")].drop_duplicates(["year"], keep="last").sort_values("year")
    quarterly = df[df["period_type"].eq("Q")].drop_duplicates(["year", "quarter"], keep="last").sort_values(["year", "quarter"])
    return normalize_columns(pd.concat([annual, quarterly], ignore_index=True), MODULE1_TIMESERIES_COLUMNS)


def _merge_timeseries_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Merge rows that belong to the same period without losing metrics.

    FireAnt data can come from multiple endpoints: LastestFinancialReports contributes KQKD/CDKT/LCTT
    line items, while FinancialInfo contributes ratios. A plain drop_duplicates would keep only one endpoint
    and discard the other metrics, so we merge by taking the first non-empty value per column.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return normalize_columns(pd.DataFrame(), MODULE1_TIMESERIES_COLUMNS)
    df = normalize_columns(df, MODULE1_TIMESERIES_COLUMNS).copy()
    key_cols = ["period_type", "year", "quarter"]
    rows = []
    for key, grp in df.groupby(key_cols, dropna=False, sort=False):
        row = {"period_type": key[0], "year": int(key[1]) if pd.notna(key[1]) else None, "quarter": int(key[2]) if pd.notna(key[2]) else None}
        row["period"] = f"Q{row['quarter']}/{row['year']}" if row["period_type"] == "Q" and row["quarter"] else str(row["year"])
        ticker_vals = grp["ticker"].dropna().astype(str)
        row["ticker"] = ticker_vals.iloc[0] if not ticker_vals.empty else ""
        for col in MODULE1_TIMESERIES_COLUMNS:
            if col in {"ticker", "period_type", "period", "year", "quarter"}:
                continue
            vals = grp[col].dropna()
            if not vals.empty:
                row[col] = vals.iloc[0]
        rows.append(row)
    out = pd.DataFrame(rows)
    annual = out[out["period_type"].eq("Y")].sort_values("year")
    quarterly = out[out["period_type"].eq("Q")].sort_values(["year", "quarter"])
    return normalize_columns(pd.concat([annual, quarterly], ignore_index=True), MODULE1_TIMESERIES_COLUMNS)



# -----------------------------
# FireAnt parser V14
# -----------------------------
# V14 uses exact FireAnt shapes captured from the user's DGC raw files and the Excel VBA module.
# It avoids the broad recursive metric scanner for FireAnt because that scanner can map headers or
# duplicate endpoint fragments incorrectly and is slow on large raw payloads.

FIREANT_INCOME_ID_MAP = {
    1: "gross_revenue_bil",
    3: "revenue_bil",
    5: "gross_profit_bil",
    6: "financial_income_bil",
    7: "financial_expense_bil",
    9: "selling_expense_bil",
    10: "admin_expense_bil",
    11: "operating_profit_bil",
    15: "pretax_profit_bil",
    18: "tax_expense_bil",
    19: "net_profit_bil",
    21: "net_profit_bil",  # prefer parent-company profit when present; appears after ID 19 in FireAnt payload
}

FIREANT_BALANCE_ID_MAP = {
    101: "current_assets_bil",
    10101: "cash_equivalents_bil",
    10102: "short_term_investments_bil",
    10103: "accounts_receivable_bil",
    10104: "inventory_bil",
    102: "fixed_assets_bil",  # MOS_LILU uses the long-term asset block as Fixed Assets / capital assets
    2: "total_assets_bil",
    301: "liabilities_bil",
    30101: "current_liabilities_bil",
    3010103: "accounts_payable_bil",
    302: "equity_bil",
    30201: "equity_bil",
}

FIREANT_CASHFLOW_ID_MAP = {
    102: "noncash_adjustments_bil",
    10201: "depreciation_bil",
    103: "operating_cash_before_wc_bil",
    10301: "receivables_change_bil",
    10302: "inventory_change_bil",
    10303: "payables_change_bil",
    10304: "prepaid_change_bil",
    10305: "other_current_assets_change_bil",
    10306: "interest_paid_bil",
    10307: "tax_paid_bil",
    10308: "other_operating_cash_in_bil",
    10309: "other_operating_cash_out_bil",
    104: "cfo_bil",
    201: "capex_bil",
    205: "investment_subsidiary_bil",
    207: "investment_subsidiary_bil",
    212: "cfi_bil",
    301: "equity_issued_bil",
    302: "buyback_bil",
    303: "debt_raised_bil",
    304: "debt_repaid_bil",
    308: "cash_dividend_bil",
    311: "cff_bil",
}

FIREANT_RATIO_MAP = {
    # annual YearlyFinancialInfo
    "Sales": "revenue_bil",
    "ProfitAfterTax": "net_profit_bil",
    "ProfitBeforeTax": "pretax_profit_bil",
    "TotalAssets": "total_assets_bil",
    "Equity": "equity_bil",
    "BasicEPS": "eps_vnd",
    "DilutedEPS": "eps_vnd",
    "ROE": "roe_pct",
    "ROA": "roa_pct",
    "ROIC": "roic_fireant_pct",
    "GrossMargin": "gross_margin_pct",
    "ProfitMargin": "net_margin_pct",
    "NetProfitMargin": "net_margin_pct",
    "AssetsTurnover": "asset_turnover",
    # quarterly QuarterlyFinancialInfo
    "NetSales_MRQ": "revenue_bil",
    "ProfitAfterTax_MRQ": "net_profit_bil",
    "ProfitBeforeTax_MRQ": "pretax_profit_bil",
    "TotalAssets_MRQ": "total_assets_bil",
    "Equity_MRQ": "equity_bil",
    "BasicEPS_MRQ": "eps_vnd",
    "DilutedEPS_MRQ": "eps_vnd",
    "ROE_TTM": "roe_pct",
    "ROA_TTM": "roa_pct",
    "ROIC_TTM": "roic_fireant_pct",
    "GrossMargin_TTM": "gross_margin_pct",
    "NetProfitMargin_TTM": "net_margin_pct",
    "AssetsTurnover_TTM": "asset_turnover",
}


def _is_fireant_statement_payload(payload: Any) -> bool:
    return isinstance(payload, list) and bool(payload) and isinstance(payload[0], dict) and "ID" in payload[0] and "Values" in payload[0]


def _is_fireant_financial_info_payload(payload: Any) -> bool:
    if not (isinstance(payload, list) and payload and isinstance(payload[0], dict)):
        return False
    keys = set(payload[0].keys())
    return "Symbol" in keys and "Year" in keys and ("BasicEPS" in keys or "BasicEPS_TTM" in keys or "NetSales_MRQ" in keys)


def _fireant_row_id(row: dict[str, Any]) -> int | None:
    try:
        return int(row.get("ID"))
    except Exception:
        return None


def _fireant_statement_map_for_payload(payload: list[dict[str, Any]]) -> dict[int, str]:
    """Classify one LastestFinancialReports payload by its line-item IDs/names."""
    names = " | ".join(str(x.get("Name", "")) for x in payload[:8] if isinstance(x, dict))
    n = _norm_text(names)
    if "tong doanh thu" in n or "doanh thu thuan" in n or "loi nhuan gop" in n:
        return FIREANT_INCOME_ID_MAP
    if "luu chuyen tien" in n or "tien chi de mua sam" in n or "khau hao" in n:
        return FIREANT_CASHFLOW_ID_MAP
    if "tai san" in n or "nguon von" in n or "von chu so huu" in n:
        return FIREANT_BALANCE_ID_MAP
    return {}


FIREANT_MONETARY_FIELDS = {
    "revenue_bil", "gross_revenue_bil", "gross_profit_bil", "operating_profit_bil", "core_operating_profit_bil", "net_profit_bil", "pretax_profit_bil",
    "financial_income_bil", "financial_expense_bil", "selling_expense_bil", "admin_expense_bil", "tax_expense_bil", "nopat_bil",
    "cfo_bil", "cfi_bil", "cff_bil", "capex_bil", "cash_dividend_bil", "depreciation_bil", "noncash_adjustments_bil", "operating_cash_before_wc_bil",
    "receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil", "interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil",
    "equity_issued_bil", "buyback_bil", "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "cash_and_short_investments_bil",
    "maintenance_capex_bil", "free_cash_flow_bil", "owner_earnings_bil", "current_assets_bil", "current_liabilities_bil", "accounts_receivable_bil", "liabilities_bil",
    "working_capital_bil", "roic_working_capital_bil", "operating_working_capital_bil", "fixed_assets_bil", "cash_equivalents_bil", "short_term_investments_bil",
    "capital_employed_bil", "avg_capital_employed_bil", "deployed_capital_bil", "avg_deployed_capital_bil", "accounts_payable_bil", "accounts_receivable_bil", "inventory_bil", "investment_subsidiary_bil",
    "expansion_investment_bil", "total_investment_bil", "total_assets_bil", "equity_bil", "avg_equity_bil",
}


def _fireant_raw_vnd_to_bil(value: Any) -> float | None:
    v = _to_float(value)
    return None if v is None else v / 1_000_000_000


def _put_metric_value(base: dict[str, Any], field: str, value: Any) -> None:
    if value is None:
        return
    additive_fields = {"investment_subsidiary_bil"}
    if field.endswith("_pct"):
        parsed = _maybe_pct(value)
    elif field in {"eps_vnd", "oeps_vnd", "asset_turnover", "equity_multiplier", "roe_dupont_pct", "roe_actual_pct", "roic_operating_profit_pct", "roic_owner_earnings_pct", "roic_standard_pct", "roic_lilu_pct", "cash_dividend_yield_pct", "year_end_price", "shares_outstanding_mil", "cfo_to_net_profit", "fcf_to_net_profit", "fcf_to_pretax", "nibt_to_fcf", "noncash_to_pretax", "wc_to_pretax", "capex_to_pretax"}:
        parsed = _to_float(value)
    elif field in FIREANT_MONETARY_FIELDS:
        parsed = _fireant_raw_vnd_to_bil(value)
    else:
        parsed = _value_to_bil(value)
    if parsed is None:
        return
    if field in additive_fields and base.get(field) is not None:
        old = _to_float(base.get(field))
        base[field] = (old or 0) + parsed
    else:
        base[field] = parsed


def _fireant_period_key(period_value: dict[str, Any], default_quarter: int | None = None) -> tuple[str, int, int | None, str] | None:
    year = _to_float(period_value.get("Year") or period_value.get("year"))
    if year is None:
        return None
    q_raw = _to_float(period_value.get("Quarter") if "Quarter" in period_value else period_value.get("quarter"))
    q = int(q_raw) if q_raw is not None else (default_quarter or 0)
    y = int(year)
    if q and 1 <= q <= 4:
        return "Q", y, q, f"Q{q}/{y}"
    return "Y", y, None, str(y)


def _extract_fireant_statement_timeseries_exact(payloads: list[Any], ticker: str) -> pd.DataFrame:
    rows: dict[tuple[str, int, int | None], dict[str, Any]] = {}
    for payload in payloads:
        if not _is_fireant_statement_payload(payload):
            continue
        id_map = _fireant_statement_map_for_payload(payload)
        if not id_map:
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            rid = _fireant_row_id(item)
            field = id_map.get(rid)
            if not field:
                continue
            values = item.get("Values") or []
            if not isinstance(values, list):
                continue
            for pv in values:
                if not isinstance(pv, dict):
                    continue
                key = _fireant_period_key(pv)
                if key is None:
                    continue
                period_type, year, quarter, label = key
                value = pv.get("Value") if "Value" in pv else pv.get("value")
                if value is None:
                    continue
                row_key = (period_type, year, quarter)
                base = rows.setdefault(row_key, {"ticker": ticker.upper(), "period_type": period_type, "period": label, "year": year, "quarter": quarter})
                _put_metric_value(base, field, value)
    if not rows:
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    df = pd.DataFrame(rows.values())
    return normalize_columns(_sort_fireant_timeseries(df), MODULE1_TIMESERIES_COLUMNS)


def _extract_fireant_financial_info_exact(payloads: list[Any], ticker: str) -> pd.DataFrame:
    rows: dict[tuple[str, int, int | None], dict[str, Any]] = {}
    for payload in payloads:
        if not _is_fireant_financial_info_payload(payload):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            if str(item.get("Symbol", ticker)).upper() != ticker.upper():
                continue
            year = _to_float(item.get("Year"))
            if year is None:
                continue
            quarter = _to_float(item.get("Quarter"))
            if quarter is not None and 1 <= int(quarter) <= 4:
                period_type, q, label = "Q", int(quarter), f"Q{int(quarter)}/{int(year)}"
            else:
                period_type, q, label = "Y", None, str(int(year))
            row_key = (period_type, int(year), q)
            base = rows.setdefault(row_key, {"ticker": ticker.upper(), "period_type": period_type, "period": label, "year": int(year), "quarter": q})
            for src_key, field in FIREANT_RATIO_MAP.items():
                if src_key not in item or item.get(src_key) is None:
                    continue
                _put_metric_value(base, field, item.get(src_key))
            # Keep shares outstanding for EPS/OEPS and dividend-yield calculations.
            if item.get("SharesOutstanding_MRQ") is not None:
                shares_raw = _to_float(item.get("SharesOutstanding_MRQ"))
                if shares_raw is not None:
                    base["shares_outstanding_mil"] = shares_raw / 1_000_000 if abs(shares_raw) >= 1_000_000 else shares_raw
    if not rows:
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    df = pd.DataFrame(rows.values())
    return _sort_fireant_timeseries(df)


def _sort_fireant_timeseries(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    df = df.copy()
    df["year"] = pd.to_numeric(df.get("year"), errors="coerce")
    df["quarter"] = pd.to_numeric(df.get("quarter"), errors="coerce")
    annual = df[df.get("period_type").eq("Y")].sort_values("year") if "period_type" in df else pd.DataFrame()
    quarterly = df[df.get("period_type").eq("Q")].sort_values(["year", "quarter"]) if "period_type" in df else pd.DataFrame()
    return pd.concat([annual, quarterly], ignore_index=True)


def _merge_fireant_prefer_statement(statement_df: pd.DataFrame, info_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Merge exact FireAnt statement rows and FinancialInfo rows.

    Statement data has priority for accounting amounts (revenue, LNST, CFO, capex).
    FinancialInfo fills ratios/EPS and missing amounts. This prevents old V10 behavior where a broad
    parser could overwrite statement line items with partial endpoint data.
    """
    if (statement_df is None or statement_df.empty) and (info_df is None or info_df.empty):
        return pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    frames = []
    if isinstance(statement_df, pd.DataFrame) and not statement_df.empty:
        frames.append(statement_df.copy())
    if isinstance(info_df, pd.DataFrame) and not info_df.empty:
        frames.append(info_df.copy())
    df = pd.concat(frames, ignore_index=True, sort=False)
    amount_cols = {"revenue_bil", "gross_revenue_bil", "gross_profit_bil", "net_profit_bil", "pretax_profit_bil", "cfo_bil", "cfi_bil", "cff_bil", "capex_bil", "cash_dividend_bil", "depreciation_bil", "total_assets_bil", "equity_bil"}
    rows=[]
    for key, grp in df.groupby(["period_type", "year", "quarter"], dropna=False, sort=True):
        period_type, year, quarter = key
        year_i = int(year) if pd.notna(year) else None
        quarter_i = int(quarter) if pd.notna(quarter) and period_type == "Q" else None
        out = {"ticker": ticker.upper(), "period_type": period_type, "year": year_i, "quarter": quarter_i, "period": f"Q{quarter_i}/{year_i}" if period_type == "Q" and quarter_i else str(year_i)}
        # Build two subframes for precedence.
        st_part = grp.iloc[[i for i, idx in enumerate(grp.index) if isinstance(statement_df, pd.DataFrame) and idx < len(statement_df)]] if False else None
        for col in set(list(MODULE1_TIMESERIES_COLUMNS) + ["depreciation_bil", "shares_outstanding"]):
            if col in {"ticker", "period_type", "period", "year", "quarter"}:
                continue
            vals = grp[col].dropna() if col in grp.columns else pd.Series(dtype="float64")
            if vals.empty:
                continue
            # Since statement rows were concatenated before info rows, first non-empty means statement priority.
            out[col] = vals.iloc[0]
        rows.append(out)
    out_df = pd.DataFrame(rows)
    out_df = _sort_fireant_timeseries(out_df)
    # Derived fields.
    for col in ["cfo_bil", "cfi_bil", "cff_bil", "capex_bil", "cash_dividend_bil", "depreciation_bil", "noncash_adjustments_bil", "operating_cash_before_wc_bil", "working_capital_change_bil", "receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil", "interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil", "equity_issued_bil", "buyback_bil", "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "net_profit_bil", "revenue_bil", "total_assets_bil", "equity_bil", "gross_profit_bil", "operating_profit_bil", "core_operating_profit_bil", "financial_income_bil", "financial_expense_bil", "selling_expense_bil", "admin_expense_bil", "tax_expense_bil", "nopat_bil", "current_assets_bil", "current_liabilities_bil", "fixed_assets_bil", "cash_equivalents_bil", "short_term_investments_bil", "cash_and_short_investments_bil", "capital_employed_bil", "avg_capital_employed_bil", "operating_working_capital_bil", "deployed_capital_bil", "avg_deployed_capital_bil", "inventory_bil", "investment_subsidiary_bil"]:
        if col in out_df.columns:
            out_df[col] = pd.to_numeric(out_df[col], errors="coerce")
    if "free_cash_flow_bil" not in out_df.columns:
        out_df["free_cash_flow_bil"] = pd.NA
    if {"cfo_bil", "capex_bil"}.issubset(out_df.columns):
        out_df["free_cash_flow_bil"] = out_df["free_cash_flow_bil"].fillna(out_df["cfo_bil"] + out_df["capex_bil"])
    wc_parts = [c for c in ["receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil", "interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil"] if c in out_df.columns]
    if wc_parts:
        out_df["working_capital_change_bil"] = out_df.get("working_capital_change_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df[wc_parts].sum(axis=1, min_count=1))
    if {"pretax_profit_bil", "operating_cash_before_wc_bil"}.issubset(out_df.columns):
        out_df["noncash_adjustments_bil"] = out_df.get("noncash_adjustments_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["operating_cash_before_wc_bil"] - out_df["pretax_profit_bil"])
    elif "depreciation_bil" in out_df.columns:
        out_df["noncash_adjustments_bil"] = out_df.get("noncash_adjustments_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["depreciation_bil"])
    if {"debt_raised_bil", "debt_repaid_bil"}.issubset(out_df.columns):
        out_df["net_debt_cashflow_bil"] = out_df.get("net_debt_cashflow_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["debt_raised_bil"] + out_df["debt_repaid_bil"])
    if {"cash_equivalents_bil", "short_term_investments_bil"}.issubset(out_df.columns):
        out_df["cash_and_short_investments_bil"] = out_df.get("cash_and_short_investments_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["cash_equivalents_bil"] + out_df["short_term_investments_bil"])
    if {"current_assets_bil", "current_liabilities_bil"}.issubset(out_df.columns):
        out_df["working_capital_bil"] = out_df.get("working_capital_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["current_assets_bil"] - out_df["current_liabilities_bil"])
    if {"working_capital_bil", "fixed_assets_bil"}.issubset(out_df.columns):
        cash = out_df["cash_equivalents_bil"] if "cash_equivalents_bil" in out_df.columns else 0
        sti = out_df["short_term_investments_bil"] if "short_term_investments_bil" in out_df.columns else 0
        out_df["deployed_capital_bil"] = out_df.get("deployed_capital_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["working_capital_bil"] + out_df["fixed_assets_bil"] - cash - sti)
    if {"operating_profit_bil", "deployed_capital_bil"}.issubset(out_df.columns):
        roic_deployed = out_df["operating_profit_bil"] / out_df["deployed_capital_bil"].replace({0: pd.NA}) * 100
        roic_deployed = roic_deployed.where(out_df["deployed_capital_bil"] > 0)
        out_df["roic_pct"] = out_df.get("roic_pct", pd.Series(index=out_df.index, dtype="float64")).fillna(roic_deployed)
    if "expansion_investment_bil" not in out_df.columns:
        out_df["expansion_investment_bil"] = out_df.get("capex_bil")
    invest_parts = [c for c in ["expansion_investment_bil", "inventory_change_bil", "investment_subsidiary_bil"] if c in out_df.columns]
    if invest_parts:
        out_df["total_investment_bil"] = out_df.get("total_investment_bil", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df[invest_parts].sum(axis=1, min_count=1))
    if "owner_earnings_bil" not in out_df.columns:
        out_df["owner_earnings_bil"] = pd.NA
    # Owner Earnings proxy from FireAnt public data: CFO - average maintenance capex.
    # FireAnt capex is a cash outflow (negative), so the numeric formula is CFO + avg(capex_bil).
    if {"cfo_bil", "capex_bil"}.issubset(out_df.columns):
        if "maintenance_capex_bil" not in out_df.columns:
            out_df["maintenance_capex_bil"] = pd.NA
        for pt in ["Y", "Q"]:
            mask = out_df["period_type"].eq(pt)
            if mask.any():
                capex_avg = out_df.loc[mask, "capex_bil"].rolling(5 if pt == "Y" else 8, min_periods=1).mean()
                out_df.loc[mask, "maintenance_capex_bil"] = out_df.loc[mask, "maintenance_capex_bil"].fillna(pd.Series(capex_avg.values, index=out_df.index[mask]))
                oe = out_df.loc[mask, "cfo_bil"].reset_index(drop=True) + capex_avg.reset_index(drop=True)
                out_df.loc[mask, "owner_earnings_bil"] = out_df.loc[mask, "owner_earnings_bil"].fillna(pd.Series(oe.values, index=out_df.index[mask]))
    if {"net_profit_bil", "revenue_bil"}.issubset(out_df.columns):
        if "net_margin_pct" not in out_df.columns:
            out_df["net_margin_pct"] = pd.NA
        out_df["net_margin_pct"] = out_df["net_margin_pct"].fillna(out_df["net_profit_bil"] / out_df["revenue_bil"].replace({0: pd.NA}) * 100)
    if {"gross_profit_bil", "revenue_bil"}.issubset(out_df.columns):
        if "gross_margin_pct" not in out_df.columns:
            out_df["gross_margin_pct"] = pd.NA
        out_df["gross_margin_pct"] = out_df["gross_margin_pct"].fillna(out_df["gross_profit_bil"] / out_df["revenue_bil"].replace({0: pd.NA}) * 100)
    if {"revenue_bil", "total_assets_bil"}.issubset(out_df.columns):
        if "asset_turnover" not in out_df.columns:
            out_df["asset_turnover"] = pd.NA
        out_df["asset_turnover"] = out_df["asset_turnover"].fillna(out_df["revenue_bil"] / out_df["total_assets_bil"].replace({0: pd.NA}))
    if {"total_assets_bil", "equity_bil"}.issubset(out_df.columns):
        if "equity_multiplier" not in out_df.columns:
            out_df["equity_multiplier"] = pd.NA
        out_df["equity_multiplier"] = out_df["equity_multiplier"].fillna(out_df["total_assets_bil"] / out_df["equity_bil"].replace({0: pd.NA}))
    if {"net_margin_pct", "asset_turnover", "equity_multiplier"}.issubset(out_df.columns):
        if "roe_dupont_pct" not in out_df.columns:
            out_df["roe_dupont_pct"] = pd.NA
        out_df["roe_dupont_pct"] = out_df["roe_dupont_pct"].fillna(out_df["net_margin_pct"] / 100 * out_df["asset_turnover"] * out_df["equity_multiplier"] * 100)
    if {"cfo_bil", "net_profit_bil"}.issubset(out_df.columns):
        out_df["cfo_to_net_profit"] = out_df.get("cfo_to_net_profit", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["cfo_bil"] / out_df["net_profit_bil"].replace({0: pd.NA}))
    if {"free_cash_flow_bil", "net_profit_bil"}.issubset(out_df.columns):
        out_df["fcf_to_net_profit"] = out_df.get("fcf_to_net_profit", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["free_cash_flow_bil"] / out_df["net_profit_bil"].replace({0: pd.NA}))
    if {"free_cash_flow_bil", "pretax_profit_bil"}.issubset(out_df.columns):
        out_df["fcf_to_pretax"] = out_df.get("fcf_to_pretax", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["free_cash_flow_bil"] / out_df["pretax_profit_bil"].replace({0: pd.NA}))
        out_df["nibt_to_fcf"] = out_df.get("nibt_to_fcf", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["pretax_profit_bil"] / out_df["free_cash_flow_bil"].replace({0: pd.NA}))
    if {"noncash_adjustments_bil", "pretax_profit_bil"}.issubset(out_df.columns):
        out_df["noncash_to_pretax"] = out_df.get("noncash_to_pretax", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["noncash_adjustments_bil"] / out_df["pretax_profit_bil"].replace({0: pd.NA}))
    if {"working_capital_change_bil", "pretax_profit_bil"}.issubset(out_df.columns):
        out_df["wc_to_pretax"] = out_df.get("wc_to_pretax", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["working_capital_change_bil"] / out_df["pretax_profit_bil"].replace({0: pd.NA}))
    if {"capex_bil", "pretax_profit_bil"}.issubset(out_df.columns):
        out_df["capex_to_pretax"] = out_df.get("capex_to_pretax", pd.Series(index=out_df.index, dtype="float64")).fillna(out_df["capex_bil"] / out_df["pretax_profit_bil"].replace({0: pd.NA}))
    out_df = _recompute_roic_and_roe_v14(out_df)
    return normalize_columns(out_df, MODULE1_TIMESERIES_COLUMNS)




def _extract_fireant_year_end_prices(payloads: list[Any], ticker: str) -> dict[int, float]:
    """Extract year-end close prices from any FireAnt historical-price payload if available.

    The Excel VBA finance module does not contain a historical-price endpoint, but V14 tries a few
    public FireAnt market endpoints. When FireAnt returns daily quote records, this function picks
    the last available trading day of each calendar year. It returns prices in VND/share.
    """
    rows: list[tuple[int, str, float]] = []
    date_aliases = ["Date", "date", "TradingDate", "tradingDate", "TradingTime", "tradingTime", "Time", "time"]
    price_aliases = ["PriceClose", "Close", "close", "ClosePrice", "closePrice", "Price", "price", "AdjustedClose", "AdjClose", "PriceAverage", "PriceCurrent", "PriceLast"]
    for payload in payloads:
        for rec in _collect_records(payload):
            if not isinstance(rec, dict):
                continue
            sym = _get_by_alias(rec, ["Symbol", "symbol", "Ticker", "ticker"])
            if sym is not None and str(sym).upper() != ticker.upper():
                continue
            d = _get_by_alias(rec, date_aliases)
            price = _to_float(_get_by_alias(rec, price_aliases))
            if d is None or price is None or price <= 0:
                continue
            text = str(d)
            m = re.search(r"(20\d{2}|19\d{2})[-/\.](\d{1,2})[-/\.](\d{1,2})", text)
            if not m:
                continue
            y = int(m.group(1))
            rows.append((y, f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", price))
    latest: dict[int, tuple[str, float]] = {}
    for y, d, price in rows:
        if y not in latest or d > latest[y][0]:
            latest[y] = (d, price)
    return {y: price for y, (d, price) in latest.items()}


def _enrich_fireant_metrics_v12(df: pd.DataFrame, ticker: str, payloads: list[Any]) -> pd.DataFrame:
    """Fill V14 derived metrics after the exact FireAnt statement/ratio merge.

    Key fixes:
    - annual dividend chart uses dividend yield = cash dividend per share / year-end price;
    - no quarterly dividend-yield indicator;
    - annual EPS/OEPS/ROE/ROIC are filled from Q4 TTM or derived values when YearlyFinancialInfo is missing;
    - latest-quarter EPS/ROE/ROIC no longer become N/A when FireAnt's QuarterlyFinancialInfo stops before
      LastestFinancialReports.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return normalize_columns(pd.DataFrame(), MODULE1_TIMESERIES_COLUMNS)
    out = df.copy()
    for col in ["year", "quarter", "revenue_bil", "gross_profit_bil", "operating_profit_bil", "core_operating_profit_bil", "net_profit_bil", "pretax_profit_bil", "financial_income_bil", "financial_expense_bil", "selling_expense_bil", "admin_expense_bil", "tax_expense_bil", "nopat_bil", "cfo_bil", "cfi_bil", "cff_bil", "capex_bil", "cash_dividend_bil", "depreciation_bil", "noncash_adjustments_bil", "operating_cash_before_wc_bil", "working_capital_change_bil", "receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil", "interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil", "equity_issued_bil", "buyback_bil", "debt_raised_bil", "debt_repaid_bil", "net_debt_cashflow_bil", "cash_and_short_investments_bil", "free_cash_flow_bil", "owner_earnings_bil", "maintenance_capex_bil", "current_assets_bil", "current_liabilities_bil", "accounts_receivable_bil", "working_capital_bil", "roic_working_capital_bil", "operating_working_capital_bil", "fixed_assets_bil", "cash_equivalents_bil", "short_term_investments_bil", "capital_employed_bil", "avg_capital_employed_bil", "deployed_capital_bil", "avg_deployed_capital_bil", "accounts_payable_bil", "accounts_receivable_bil", "inventory_bil", "investment_subsidiary_bil", "expansion_investment_bil", "total_investment_bil", "total_assets_bil", "equity_bil", "avg_equity_bil", "eps_vnd", "oeps_vnd", "roe_pct", "roe_actual_pct", "roa_pct", "roic_pct", "roic_operating_profit_pct", "roic_owner_earnings_pct", "roic_standard_pct", "roic_lilu_pct", "roic_fireant_pct", "asset_turnover", "equity_multiplier", "roe_dupont_pct", "shares_outstanding_mil", "cash_dividend_yield_pct", "year_end_price", "wacc_pct", "cfo_to_net_profit", "fcf_to_net_profit", "fcf_to_pretax", "nibt_to_fcf", "noncash_to_pretax", "wc_to_pretax", "capex_to_pretax"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out = _sort_fireant_timeseries(out)

    wc_parts = [c for c in ["receivables_change_bil", "inventory_change_bil", "payables_change_bil", "prepaid_change_bil", "other_current_assets_change_bil", "interest_paid_bil", "tax_paid_bil", "other_operating_cash_in_bil", "other_operating_cash_out_bil"] if c in out.columns]
    if wc_parts:
        out["working_capital_change_bil"] = out.get("working_capital_change_bil", pd.Series(index=out.index, dtype="float64")).fillna(out[wc_parts].sum(axis=1, min_count=1))
    if {"pretax_profit_bil", "operating_cash_before_wc_bil"}.issubset(out.columns):
        out["noncash_adjustments_bil"] = out.get("noncash_adjustments_bil", pd.Series(index=out.index, dtype="float64")).fillna(out["operating_cash_before_wc_bil"] - out["pretax_profit_bil"])
    elif "depreciation_bil" in out.columns:
        out["noncash_adjustments_bil"] = out.get("noncash_adjustments_bil", pd.Series(index=out.index, dtype="float64")).fillna(out["depreciation_bil"])
    if {"debt_raised_bil", "debt_repaid_bil"}.issubset(out.columns):
        out["net_debt_cashflow_bil"] = out.get("net_debt_cashflow_bil", pd.Series(index=out.index, dtype="float64")).fillna(out["debt_raised_bil"] + out["debt_repaid_bil"])
    if {"cash_equivalents_bil", "short_term_investments_bil"}.issubset(out.columns):
        out["cash_and_short_investments_bil"] = out.get("cash_and_short_investments_bil", pd.Series(index=out.index, dtype="float64")).fillna(out["cash_equivalents_bil"] + out["short_term_investments_bil"])

    # Forward/back fill share count across quarterly rows; use Q4 share count for annual rows.
    if "shares_outstanding_mil" not in out.columns:
        out["shares_outstanding_mil"] = pd.NA
    qmask = out["period_type"].eq("Q")
    if qmask.any():
        qshares = out.loc[qmask, ["year", "quarter", "shares_outstanding_mil"]].sort_values(["year", "quarter"])
        filled = qshares["shares_outstanding_mil"].ffill().bfill()
        out.loc[qshares.index, "shares_outstanding_mil"] = filled
        q4_map = out.loc[qmask & out["quarter"].eq(4) & out["shares_outstanding_mil"].notna()].set_index("year")["shares_outstanding_mil"].to_dict()
        for idx, row in out[out["period_type"].eq("Y")].iterrows():
            if pd.isna(row.get("shares_outstanding_mil")):
                y = int(row["year"])
                if y in q4_map:
                    out.at[idx, "shares_outstanding_mil"] = q4_map[y]
                else:
                    # Pick the nearest available quarter. Prefer the latest quarter not after that fiscal year;
                    # if the ticker has no earlier quarterly share-count data, use the earliest following quarter
                    # so EPS/OEPS charts do not show avoidable gaps.
                    candidates = out.loc[qmask & (out["year"] <= y) & out["shares_outstanding_mil"].notna(), ["year", "quarter", "shares_outstanding_mil"]].sort_values(["year", "quarter"])
                    if not candidates.empty:
                        out.at[idx, "shares_outstanding_mil"] = candidates.iloc[-1]["shares_outstanding_mil"]
                    else:
                        candidates = out.loc[qmask & out["shares_outstanding_mil"].notna(), ["year", "quarter", "shares_outstanding_mil"]].sort_values(["year", "quarter"])
                        if not candidates.empty:
                            out.at[idx, "shares_outstanding_mil"] = candidates.iloc[0]["shares_outstanding_mil"]

    # Corrected MOS_LILU / Li Lu logic:
    # Deployed Capital = Current Assets - Cash - Short-term Investments - Accounts Payable + Fixed Assets.
    # Average Deployed Capital = average of current and previous Deployed Capital.
    # This fixes the V15 asymmetry that averaged current assets/AP but subtracted ending cash & investments.
    if {"current_assets_bil", "current_liabilities_bil"}.issubset(out.columns):
        out["working_capital_bil"] = out.get("working_capital_bil", pd.Series(index=out.index, dtype="float64")).fillna(out["current_assets_bil"] - out["current_liabilities_bil"])
    if {"current_assets_bil", "fixed_assets_bil"}.issubset(out.columns):
        cash = out["cash_equivalents_bil"] if "cash_equivalents_bil" in out.columns else 0
        sti = out["short_term_investments_bil"] if "short_term_investments_bil" in out.columns else 0
        ap = out["accounts_payable_bil"] if "accounts_payable_bil" in out.columns else (out["current_liabilities_bil"] if "current_liabilities_bil" in out.columns else 0)
        op_wc = out["current_assets_bil"] - cash - sti - ap
        out["roic_working_capital_bil"] = op_wc
        out["deployed_capital_bil"] = op_wc + out["fixed_assets_bil"]
        out["avg_deployed_capital_bil"] = _avg_current_and_previous(out, "deployed_capital_bil")
    elif {"current_assets_bil", "accounts_payable_bil"}.issubset(out.columns):
        out["roic_working_capital_bil"] = out["current_assets_bil"] - out["accounts_payable_bil"]
    if {"core_operating_profit_bil", "avg_deployed_capital_bil"}.issubset(out.columns):
        roic_op = (out["core_operating_profit_bil"] / out["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(out["avg_deployed_capital_bil"] > 0)
        out["roic_operating_profit_pct"] = out.get("roic_operating_profit_pct", pd.Series(index=out.index, dtype="float64"))
        # Override older cache values because V16 changed the denominator to average deployed capital.
        out["roic_operating_profit_pct"] = roic_op.combine_first(out["roic_operating_profit_pct"])
        out["roic_lilu_pct"] = roic_op.combine_first(out.get("roic_lilu_pct", pd.Series(index=out.index, dtype="float64")))
        out["roic_pct"] = out.get("roic_pct", pd.Series(index=out.index, dtype="float64"))
        # Quarterly ROIC should be read on TTM operating profit to reduce seasonality.
        qmask_roic = out["period_type"].eq("Q")
        if qmask_roic.any():
            q = out.loc[qmask_roic].sort_values(["year", "quarter"]).copy()
            op_ttm = q["core_operating_profit_bil"].rolling(4, min_periods=1).sum()
            q_roic = (op_ttm / q["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(q["avg_deployed_capital_bil"] > 0)
            out.loc[q.index, "roic_operating_profit_pct"] = q_roic.combine_first(out.loc[q.index, "roic_operating_profit_pct"])
            out.loc[q.index, "roic_lilu_pct"] = q_roic.combine_first(out.loc[q.index, "roic_lilu_pct"])
            # Do not overwrite roic_pct here; roic_pct remains the standard/FireAnt ROIC used on the main dashboard.
    if {"owner_earnings_bil", "avg_deployed_capital_bil"}.issubset(out.columns):
        roic_oe = (out["owner_earnings_bil"] / out["avg_deployed_capital_bil"].replace({0: pd.NA}) * 100).where(out["avg_deployed_capital_bil"] > 0)
        out["roic_owner_earnings_pct"] = out.get("roic_owner_earnings_pct", pd.Series(index=out.index, dtype="float64"))
        out["roic_owner_earnings_pct"] = roic_oe.combine_first(out["roic_owner_earnings_pct"])
    if "expansion_investment_bil" not in out.columns:
        out["expansion_investment_bil"] = out.get("capex_bil")
    invest_parts = [c for c in ["expansion_investment_bil", "inventory_change_bil", "investment_subsidiary_bil"] if c in out.columns]
    if invest_parts:
        out["total_investment_bil"] = out.get("total_investment_bil", pd.Series(index=out.index, dtype="float64")).fillna(out[invest_parts].sum(axis=1, min_count=1))

    shares = out["shares_outstanding_mil"].replace({0: pd.NA})
    if "eps_vnd" in out.columns and "net_profit_bil" in out.columns:
        derived_eps = out["net_profit_bil"] * 1000 / shares
        out["eps_vnd"] = out["eps_vnd"].fillna(derived_eps)
    if "oeps_vnd" in out.columns and "owner_earnings_bil" in out.columns:
        derived_oeps = out["owner_earnings_bil"] * 1000 / shares
        out["oeps_vnd"] = out["oeps_vnd"].fillna(derived_oeps)

    # Actual ROE from accounting net profit / ending equity; useful when FireAnt ratio endpoint returns blanks.
    if "roe_actual_pct" not in out.columns:
        out["roe_actual_pct"] = pd.NA
    if {"net_profit_bil", "equity_bil"}.issubset(out.columns):
        out["roe_actual_pct"] = out["roe_actual_pct"].fillna(out["net_profit_bil"] / out["equity_bil"].replace({0: pd.NA}) * 100)
    if {"net_profit_bil", "total_assets_bil"}.issubset(out.columns):
        if "roa_pct" not in out.columns:
            out["roa_pct"] = pd.NA
        out["roa_pct"] = out["roa_pct"].fillna(out["net_profit_bil"] / out["total_assets_bil"].replace({0: pd.NA}) * 100)

    # Quarterly TTM fallback for recent quarters missing FireAnt ratio fields.
    q = out[out["period_type"].eq("Q")].sort_values(["year", "quarter"]).copy()
    if not q.empty and {"net_profit_bil", "equity_bil"}.issubset(q.columns):
        net_ttm = q["net_profit_bil"].rolling(4, min_periods=1).sum()
        avg_equity = q["equity_bil"].rolling(4, min_periods=1).mean().replace({0: pd.NA})
        ttm_roe = net_ttm / avg_equity * 100
        for pos, idx in enumerate(q.index):
            if pd.isna(out.at[idx, "roe_pct"]):
                out.at[idx, "roe_pct"] = ttm_roe.iloc[pos]
    # Fill annual ROE/EPS/ROIC from Q4 TTM where available.
    q4 = out[(out["period_type"].eq("Q")) & (out["quarter"].eq(4))].set_index("year") if not out.empty else pd.DataFrame()
    for idx, row in out[out["period_type"].eq("Y")].iterrows():
        y = int(row["year"])
        if not q4.empty and y in q4.index:
            for col in ["roe_pct", "roa_pct", "roic_pct", "eps_vnd", "shares_outstanding_mil"]:
                if col in out.columns and pd.isna(out.at[idx, col]) and col in q4.columns and pd.notna(q4.at[y, col]):
                    out.at[idx, col] = q4.at[y, col]

    if "roe_pct" in out.columns:
        out["roe_pct"] = out["roe_pct"].fillna(out.get("roe_actual_pct"))
    # ROIC fallback: prefer Buffett/Li Lu deployed-capital ROIC; if not computable, use FireAnt ROIC.
    if "roic_pct" not in out.columns:
        out["roic_pct"] = pd.NA
    if "roic_fireant_pct" in out.columns:
        out["roic_pct"] = out["roic_pct"].fillna(out["roic_fireant_pct"])

    # Recompute DuPont components after all values are available.
    if {"net_profit_bil", "revenue_bil"}.issubset(out.columns):
        if "net_margin_pct" not in out.columns:
            out["net_margin_pct"] = pd.NA
        out["net_margin_pct"] = out["net_margin_pct"].fillna(out["net_profit_bil"] / out["revenue_bil"].replace({0: pd.NA}) * 100)
    if {"revenue_bil", "total_assets_bil"}.issubset(out.columns):
        if "asset_turnover" not in out.columns:
            out["asset_turnover"] = pd.NA
        out["asset_turnover"] = out["asset_turnover"].fillna(out["revenue_bil"] / out["total_assets_bil"].replace({0: pd.NA}))
    if {"total_assets_bil", "equity_bil"}.issubset(out.columns):
        if "equity_multiplier" not in out.columns:
            out["equity_multiplier"] = pd.NA
        out["equity_multiplier"] = out["equity_multiplier"].fillna(out["total_assets_bil"] / out["equity_bil"].replace({0: pd.NA}))
    if {"net_margin_pct", "asset_turnover", "equity_multiplier"}.issubset(out.columns):
        if "roe_dupont_pct" not in out.columns:
            out["roe_dupont_pct"] = pd.NA
        out["roe_dupont_pct"] = out["roe_dupont_pct"].fillna(out["net_margin_pct"] / 100 * out["asset_turnover"] * out["equity_multiplier"] * 100)

    # V14 formula correction: recompute main ROIC from NOPAT / average capital employed,
    # keep Li Lu/deployed capital ROIC as a separate supplementary metric.
    out = _recompute_roic_and_roe_v14(out)

    # Dividend yield: annual only. Do not keep the quarterly dividend indicator on dashboard charts.
    price_map = _extract_fireant_year_end_prices(payloads, ticker)
    if "year_end_price" not in out.columns:
        out["year_end_price"] = pd.NA
    for idx, row in out[out["period_type"].eq("Y")].iterrows():
        y = int(row["year"])
        if pd.isna(out.at[idx, "year_end_price"]) and y in price_map:
            out.at[idx, "year_end_price"] = price_map[y]
    if "cash_dividend_yield_pct" not in out.columns:
        out["cash_dividend_yield_pct"] = pd.NA
    annual_mask = out["period_type"].eq("Y")
    dps = out["cash_dividend_bil"].abs() * 1000 / out["shares_outstanding_mil"].replace({0: pd.NA})
    out.loc[annual_mask, "cash_dividend_yield_pct"] = out.loc[annual_mask, "cash_dividend_yield_pct"].fillna(dps[annual_mask] / out.loc[annual_mask, "year_end_price"].replace({0: pd.NA}) * 100)
    quarter_mask = out["period_type"].eq("Q")
    if quarter_mask.any():
        out.loc[quarter_mask, "cash_dividend_yield_pct"] = pd.NA

    return normalize_columns(_sort_fireant_timeseries(out), MODULE1_TIMESERIES_COLUMNS)

def _build_fireant_overview_exact(payloads: list[Any], ticker: str, ts: pd.DataFrame) -> pd.DataFrame:
    quote = None
    latest_info = None
    for payload in payloads:
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            if "PriceCurrent" in payload[0] and str(payload[0].get("Symbol", "")).upper() == ticker.upper():
                quote = payload[0]
            if _is_fireant_financial_info_payload(payload):
                for rec in payload:
                    if not isinstance(rec, dict):
                        continue
                    if str(rec.get("Symbol", ticker)).upper() != ticker.upper():
                        continue
                    if rec.get("Quarter") is not None:
                        if latest_info is None or (int(rec.get("Year", 0)), int(rec.get("Quarter", 0))) > (int(latest_info.get("Year", 0)), int(latest_info.get("Quarter", 0))):
                            latest_info = rec
    row = {"ticker": ticker.upper(), "updated_at": f"Dữ liệu cập nhật {datetime.now():%Y-%m-%d %H:%M:%S}"}
    if quote:
        row["company_name"] = quote.get("Name")
        exch = str(quote.get("Exchange") or "")
        row["exchange"] = {"HOSTC": "HOSE", "HASTC": "HNX", "UPCOM": "UPCoM"}.get(exch.upper(), exch)
        row["current_price"] = _to_float(quote.get("PriceCurrent") or quote.get("PriceLast") or quote.get("PriceClose"))
        row["industry"] = quote.get("IndustryName") or quote.get("Industry") or quote.get("IndustryCode")
        row["sub_industry"] = quote.get("IndustryCode")
    if latest_info:
        row["eps"] = _to_float(latest_info.get("BasicEPS_TTM") or latest_info.get("BasicEPS") or latest_info.get("DilutedEPS_TTM"))
        row["roe"] = _maybe_pct(latest_info.get("ROE_TTM") or latest_info.get("ROE"))
        row["roa"] = _maybe_pct(latest_info.get("ROA_TTM") or latest_info.get("ROA"))
        row["roic"] = None  # filled below from Buffett/Li Lu deployed-capital ROIC when available; FireAnt fallback if not.
        row["roic_fireant"] = _maybe_pct(latest_info.get("ROIC_TTM") or latest_info.get("ROIC"))
        shares = _to_float(latest_info.get("SharesOutstanding_MRQ"))
        if shares:
            row["shares_outstanding_mil"] = shares / 1_000_000 if abs(shares) >= 1_000_000 else shares
        price_tmp = _to_float(quote.get("PriceCurrent") or quote.get("PriceLast") or quote.get("PriceClose")) if quote else None
        bvps = _to_float(latest_info.get("BookValuePerShare_MRQ"))
        sps = _to_float(latest_info.get("SalesPerShare_TTM"))
        if price_tmp and bvps:
            row["pb"] = price_tmp / bvps
        if price_tmp and sps:
            row["ps"] = price_tmp / sps
    # Fill overview from latest timeseries if FinancialInfo is absent.
    latest_ts = ts.sort_values(["year", "quarter"], na_position="first").tail(1) if isinstance(ts, pd.DataFrame) and not ts.empty else pd.DataFrame()
    if not latest_ts.empty:
        lr = latest_ts.iloc[0]
        for out_col, ts_col in [("roe", "roe_pct"), ("roa", "roa_pct"), ("eps", "eps_vnd")]:
            if row.get(out_col) is None and ts_col in lr and pd.notna(lr[ts_col]):
                row[out_col] = lr[ts_col]
        if "roic_pct" in lr and pd.notna(lr.get("roic_pct")):
            row["roic"] = lr["roic_pct"]
        elif row.get("roic") is None and row.get("roic_fireant") is not None:
            row["roic"] = row.get("roic_fireant")
    # Valuation ratios cannot be pulled from the provided FireAnt VBA endpoints. Compute market cap if possible.
    price = _to_float(row.get("current_price"))
    shares_mil = _to_float(row.get("shares_outstanding_mil"))
    eps = _to_float(row.get("eps"))
    if price and shares_mil:
        row["market_cap_bil"] = price * shares_mil / 1000.0
    if price and eps and eps != 0:
        row["pe"] = price / eps
    # P/B and P/S from latest annual/Q statement when possible.
    if not latest_ts.empty and shares_mil and price:
        lr = latest_ts.iloc[0]
        if row.get("pb") is None and pd.notna(lr.get("equity_bil")) and shares_mil:
            bvps = lr["equity_bil"] * 1_000_000_000 / (shares_mil * 1_000_000)
            if bvps:
                row["pb"] = price / bvps
        if row.get("ps") is None and pd.notna(lr.get("revenue_bil")) and shares_mil:
            sales_per_share = lr["revenue_bil"] * 1_000_000_000 / (shares_mil * 1_000_000)
            if sales_per_share:
                row["ps"] = price / sales_per_share
    return normalize_columns(pd.DataFrame([row]), MODULE1_OVERVIEW_COLUMNS)


def _normalize_fireant_payloads_v11(payloads: list[Any], tables: list[pd.DataFrame], ticker: str, source: str, responses: list[dict[str, Any]] | None = None, raw_dir: Path | None = None) -> ProviderResult:
    statement_df = _extract_fireant_statement_timeseries_exact(payloads, ticker)
    info_df = _extract_fireant_financial_info_exact(payloads, ticker)
    ts = _merge_fireant_prefer_statement(statement_df, info_df, ticker)
    ts = _enrich_fireant_metrics_v12(ts, ticker, payloads)
    annual = ts[ts["period_type"].eq("Y")].copy() if not ts.empty else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    quarterly = ts[ts["period_type"].eq("Q")].copy() if not ts.empty else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    overview = _build_fireant_overview_exact(payloads, ticker, ts)
    note = (
        f"Parsed FireAnt V14 exact parser: statement annual={len(annual)}, quarterly={len(quarterly)}, "
        f"financial-info rows={len(info_df) if isinstance(info_df, pd.DataFrame) else 0}. "
        "Dữ liệu tiền tệ đã đổi về tỷ đồng; tỷ lệ ROE/ROA/ROIC đổi về %. V17 giữ công thức ROIC V16 và bổ sung đường giá trị 0 màu đỏ trên biểu đồ để phân biệt vùng âm/dương."
    )
    return ProviderResult(
        overview=normalize_columns(overview, MODULE1_OVERVIEW_COLUMNS),
        annual=normalize_columns(annual, MODULE1_TIMESERIES_COLUMNS),
        quarterly=normalize_columns(quarterly, MODULE1_TIMESERIES_COLUMNS),
        note=note,
    )

def _normalize_from_payloads(payloads: list[Any], tables: list[pd.DataFrame], ticker: str, source: str, responses: list[dict[str, Any]] | None = None, raw_dir: Path | None = None) -> ProviderResult:
    if source.lower().startswith("fireant"):
        return _normalize_fireant_payloads_v11(payloads, tables, ticker.upper().strip(), source, responses=responses, raw_dir=raw_dir)

    records: list[dict[str, Any]] = []
    extra_tables: list[pd.DataFrame] = []
    if payloads and raw_dir is not None:
        _saved, extra_tables = _extract_tables_from_payload_strings(raw_dir, ticker, source.lower(), payloads)
        tables = [*tables, *extra_tables]
    for payload in payloads:
        records.extend(_collect_records(payload))

    # HTML tables can contain already-row-shaped financial data; convert each row to dict too.
    for table in tables:
        try:
            clean = table.copy()
            clean.columns = [str(c) for c in clean.columns]
            records.extend(clean.to_dict("records"))
        except Exception:
            pass

    overview = _build_overview_from_records(records, ticker, source)
    if overview.empty and responses:
        overview = _extract_overview_from_html(responses, ticker, source)
    ts_records = _extract_value_record_timeseries(records, ticker)
    ts_tables = _extract_wide_table_timeseries(tables, ticker)
    ts_parts = [x for x in [ts_records, ts_tables] if isinstance(x, pd.DataFrame) and not x.empty]
    ts = pd.concat(ts_parts, ignore_index=True) if ts_parts else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    if not ts.empty:
        ts = _merge_timeseries_rows(ts)
    annual = ts[ts["period_type"].eq("Y")].copy() if not ts.empty else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    quarterly = ts[ts["period_type"].eq("Q")].copy() if not ts.empty else pd.DataFrame(columns=MODULE1_TIMESERIES_COLUMNS)
    return ProviderResult(
        overview=normalize_columns(overview, MODULE1_OVERVIEW_COLUMNS),
        annual=normalize_columns(annual, MODULE1_TIMESERIES_COLUMNS),
        quarterly=normalize_columns(quarterly, MODULE1_TIMESERIES_COLUMNS),
        note=f"Parsed public {source} payloads: records={len(records)}, annual={len(annual)}, quarterly={len(quarterly)}.",
    )

def _empty_result(raw_path: Path, note: str) -> ProviderResult:
    return ProviderResult(
        overview=normalize_columns(pd.DataFrame(), MODULE1_OVERVIEW_COLUMNS),
        annual=normalize_columns(pd.DataFrame(), MODULE1_TIMESERIES_COLUMNS),
        quarterly=normalize_columns(pd.DataFrame(), MODULE1_TIMESERIES_COLUMNS),
        raw_path=raw_path,
        note=note,
    )


class PublicFireAntCrawler:
    """No-token FireAnt crawler following the Financial-v1.3.0.xlsm VBA module.

    Source module extracted from the user's workbook:
    TCReport_FireAnt.cls builds URLs as:
    SIE_FireAnt & "api/Data/Finance/" & IIf(toQuarter=0,"Yearly","Quarterly") & "FinancialInfo?symbol="...
    SIE_FireAnt & "api/Data/Finance/LastestFinancialReports?symbol=" & MaSIC & "&type=" & ReportType...
    """

    def __init__(self, raw_dir: str | Path = "raw_data"):
        self.raw_dir = Path(raw_dir)

    @staticmethod
    def _fireant_urls(ticker: str) -> list[str]:
        ticker = ticker.upper().strip()
        current_year = _now_year()
        current_quarter = (datetime.now().month - 1) // 3 + 1
        from_year = current_year - 11
        q_from_year = current_year - 5
        hosts = ["https://www.fireant.vn/"]
        urls: list[str] = []
        for host in hosts:
            urls.append(f"{host}api/Data/Markets/Quotes?symbols={ticker}")

            # YearlyFinancialInfo appears to return a limited number of rows for a wide range.
            # The VBA workbook queries this endpoint; V14 calls it in small year chunks so the latest
            # annual EPS/ROE/ROIC records are not lost.
            y = from_year
            while y <= current_year:
                y2 = min(y + 4, current_year)
                urls.append(f"{host}api/Data/Finance/YearlyFinancialInfo?symbol={ticker}&fromYear={y}&toYear={y2}")
                y = y2 + 1

            # QuarterlyFinancialInfo is also chunked; one very long 20+ quarter request may return only
            # the earliest slice. Two-year windows keep all 20 dashboard quarters available.
            qy = q_from_year
            while qy <= current_year:
                qy2 = min(qy + 1, current_year)
                to_q = current_quarter if qy2 == current_year else 4
                urls.append(f"{host}api/Data/Finance/QuarterlyFinancialInfo?symbol={ticker}&fromYear={qy}&fromQuarter=1&toYear={qy2}&toQuarter={to_q}")
                qy = qy2 + 1

            # LastestFinancialReports report type mapping from VBA:
            # 1=CDKT, 2=KQKD, 3=LCTT trực tiếp, 4=LCTT gián tiếp. Annual uses quarter=0; quarterly uses quarter>0.
            for report_type in [1, 2, 3, 4]:
                urls.append(f"{host}api/Data/Finance/LastestFinancialReports?symbol={ticker}&type={report_type}&year={current_year}&quarter=0&count=12")
                urls.append(f"{host}api/Data/Finance/LastestFinancialReports?symbol={ticker}&type={report_type}&year={current_year}&quarter={current_quarter}&count=20")
                # Some tickers have latest completed quarter earlier than the calendar quarter.
                urls.append(f"{host}api/Data/Finance/LastestFinancialReports?symbol={ticker}&type={report_type}&year={current_year-1}&quarter=4&count=20")

            # V14: optional public historical-price probes for year-end dividend yield.
            # These endpoints are tried silently; if FireAnt returns 404/HTML, dashboard still works and
            # dividend-yield remains blank rather than using the wrong current-price denominator.
            start_date = f"{from_year}-01-01"
            end_date = f"{current_year}-12-31"
            urls.extend([
                f"{host}api/Data/Markets/HistoricalQuotes?symbol={ticker}&startDate={start_date}&endDate={end_date}",
                f"{host}api/Data/Markets/HistoricalQuotes?symbol={ticker}&fromDate={start_date}&toDate={end_date}",
                f"{host}api/Data/Markets/PriceHistory?symbol={ticker}&startDate={start_date}&endDate={end_date}",
                f"{host}api/Data/Markets/SymbolPriceHistory?symbol={ticker}&startDate={start_date}&endDate={end_date}",
            ])
        # Public pages only for overview text fallback; dashboard does not depend on them.
        urls.extend([
            f"https://fireant.vn/ma-chung-khoan/{ticker}",
            f"https://fireant.vn/home/content/symbols/{ticker}",
            f"https://www.fireant.vn/Home/StockDetail/{ticker}",
        ])
        # Preserve order while removing duplicates across host variants.
        deduped: list[str] = []
        seen: set[str] = set()
        for u in urls:
            if u not in seen:
                deduped.append(u)
                seen.add(u)
        return deduped

    def fetch_raw(self, ticker: str) -> tuple[Path, list[Any], list[pd.DataFrame]]:
        ticker = ticker.upper().strip()
        urls = self._fireant_urls(ticker)
        responses: list[dict[str, Any]] = []
        with _client() as client:
            for url in urls:
                # Match the Excel module's XMLHTTP request style but with browser-like AJAX headers.
                headers = dict(HEADERS)
                headers["Referer"] = f"https://fireant.vn/ma-chung-khoan/{ticker}"
                try:
                    resp = client.get(url, headers=headers)
                    responses.append({
                        "source": "fireant_excel_vba_endpoint",
                        "url": url,
                        "status_code": resp.status_code,
                        "content_type": resp.headers.get("content-type"),
                        "body": resp.text[:3_000_000],
                    })
                except Exception as exc:
                    responses.append({"source": "fireant_excel_vba_endpoint", "url": url, "status_code": None, "content_type": None, "body": None, "error": str(exc)})
        table_files, tables = _extract_html_tables(self.raw_dir, ticker, "fireant", responses)
        json_files, payloads = _extract_json_preview(self.raw_dir, ticker, "fireant") if False else ([], [])
        # Do not rely only on content-type; FireAnt may return JSON as text/plain.
        for idx, resp in enumerate(responses, start=1):
            parsed = _try_json(resp.get("body"))
            if parsed is not None:
                payloads.append(parsed)
                out = self.raw_dir / f"fireant_{ticker.upper()}_json_{idx}_{int(time.time())}.json"
                self.raw_dir.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                json_files.append(str(out))
        raw_path = _save_raw(self.raw_dir, ticker, "fireant_excel_vba", {
            "ticker": ticker,
            "mode": "TCReport_FireAnt VBA endpoints only; no vnstock; no browser automation",
            "responses": responses,
            "table_files": table_files,
            "json_files": json_files,
        })
        return raw_path, payloads, tables


    def fetch_industry_peers(self, ticker: str) -> tuple[Path, pd.DataFrame, str]:
        """Fetch Vietstock same-industry peer list for a ticker.

        The public page is dynamic, so this method is intentionally tolerant:
        1) save the raw same-industry page for audit;
        2) try several observed/legacy ajax endpoint shapes;
        3) parse JSON/table/link records recursively; and
        4) return an empty dataframe with a clear note instead of crashing when Vietstock blocks/changes structure.
        """
        ticker = ticker.upper().strip()
        url = f"https://finance.vietstock.vn/{ticker}/so-sanh-gia-co-phieu-cung-nganh.htm"
        payload: dict[str, Any] = {"ticker": ticker, "url": url, "responses": []}
        records: list[dict[str, Any]] = []
        industry_path = ""

        def add_record(code: Any, name: Any = "", exchange: Any = "", industry: Any = "", sub_industry: Any = "", source: str = "Vietstock") -> None:
            code_text = str(code or "").upper().strip()
            if not _is_probable_vn_ticker(code_text, base_ticker=ticker):
                return
            records.append({
                "ticker": code_text,
                "company_name": str(name or "").strip(),
                "exchange": str(exchange or "").strip(),
                "industry": str(industry or "").strip(),
                "sub_industry": str(sub_industry or "").strip(),
                "peer_group": str(sub_industry or industry or industry_path or "Vietstock cùng ngành").strip(),
                "source": source,
                "note": f"Crawl từ {url}",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        def walk_json(obj: Any) -> None:
            if isinstance(obj, dict):
                code = _get_by_alias(obj, ["ticker", "Ticker", "code", "Code", "symbol", "Symbol", "StockCode", "stockCode", "StockSymbol", "stockSymbol", "Ma", "MaCK", "mack"])
                name = _get_by_alias(obj, ["companyName", "CompanyName", "name", "Name", "ten", "Ten", "StockName", "stockName", "FullName", "fullName"])
                exchange = _get_by_alias(obj, ["exchange", "Exchange", "san", "San", "market", "Market", "floor", "Floor"])
                industry = _get_by_alias(obj, ["industry", "Industry", "sector", "Sector", "nganh", "Nganh", "industryName", "IndustryName"])
                sub = _get_by_alias(obj, ["subIndustry", "SubIndustry", "sub_industry", "SubIndustryName", "subIndustryName", "nganhCon", "NganhCon"])
                if code:
                    add_record(code, name, exchange, industry or industry_path, sub, "Vietstock JSON/API")
                for v in obj.values():
                    walk_json(v)
            elif isinstance(obj, list):
                for item in obj:
                    walk_json(item)

        with _client() as client:
            resp = _get(client, "vietstock_industry_peer_page", url)
            payload["responses"].append(resp.__dict__)
            body = resp.body or ""
            # Breadcrumb on the public page often contains: Ngành: Nguyên vật liệu > ... > Hóa chất
            if body:
                soup = BeautifulSoup(body, "html.parser")
                text = soup.get_text(" ", strip=True)
                m = re.search(r"Ngành:\s*([^\n\r]{3,180}?)(?:GD ký quỹ|\.\.\.|Tổng quan|Cùng ngành|$)", text, flags=re.I)
                if m:
                    industry_path = re.sub(r"\s+", " ", m.group(1)).strip(" >")
                for a in soup.find_all("a", href=True):
                    href = str(a.get("href") or "")
                    text_a = a.get_text(" ", strip=True)
                    m = re.search(r"finance\.vietstock\.vn/([A-Z][A-Z0-9]{1,9})(?:[/.]|$)", href, flags=re.I)
                    if m:
                        add_record(m.group(1), text_a, "", industry_path, "", "Vietstock HTML link")
                for table in pd.read_html(StringIO(body)) if "<table" in body.lower() else []:
                    if table.empty:
                        continue
                    cols = {str(c).strip().lower(): c for c in table.columns}
                    code_col = None
                    for key, col in cols.items():
                        if key in {"mã", "ma", "mã ck", "ma ck", "ticker", "code", "symbol"} or "mã" in key:
                            code_col = col
                            break
                    if code_col is not None:
                        for _, r in table.iterrows():
                            add_record(r.get(code_col), r.get(cols.get("tên", ""), ""), r.get(cols.get("sàn", ""), ""), industry_path, "", "Vietstock HTML table")

            token = self._token_from_html(body)
            headers = dict(HEADERS)
            headers.update({
                "Origin": "https://finance.vietstock.vn",
                "Referer": url,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            })
            if token:
                headers.update({"RequestVerificationToken": token, "__RequestVerificationToken": token})
            # Candidate endpoints observed/used across VietstockFinance versions. They are harmless if 404/blocked.
            endpoint_candidates: list[tuple[str, dict[str, Any]]] = []
            for page_size in [200]:
                common = {"code": ticker, "Code": ticker, "symbol": ticker, "Ticker": ticker, "page": 1, "Page": 1, "pageSize": page_size, "PageSize": page_size, "languageID": 1, "languageid": 1}
                for ep in [
                    "https://finance.vietstock.vn/data/GetStockSameIndustry",
                    "https://finance.vietstock.vn/data/StockSameIndustry",
                    "https://finance.vietstock.vn/data/GetStockByIndustry",
                    "https://finance.vietstock.vn/data/CompareStockSameIndustry",
                ]:
                    endpoint_candidates.append((ep, dict(common)))
            for ep, data in endpoint_candidates:
                try:
                    r = client.post(ep, data=data, headers=headers, timeout=4.0)
                    payload["responses"].append({"source": "vietstock_industry_peer_candidate", "url": ep, "status_code": r.status_code, "content_type": r.headers.get("content-type"), "request_data": data, "body": r.text[:2_000_000]})
                    parsed = _try_json(r.text)
                    if parsed is not None:
                        walk_json(parsed)
                    elif "<table" in (r.text or "").lower():
                        try:
                            for table in pd.read_html(StringIO(r.text)):
                                if table.empty:
                                    continue
                                # Find any ticker-like cells in ajax HTML.
                                for _, row in table.iterrows():
                                    vals = [str(x).strip() for x in row.tolist()]
                                    for val in vals[:3]:
                                        if re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", val.upper()):
                                            add_record(val.upper(), "", "", industry_path, "", "Vietstock AJAX table")
                        except Exception:
                            pass
                except Exception as exc:
                    payload["responses"].append({"source": "vietstock_industry_peer_candidate", "url": ep, "request_data": data, "error": str(exc)})

        # Deduplicate and remove the current ticker from candidate list only if other peers exist; keep it if alone for user context.
        df = pd.DataFrame(records)
        if not df.empty:
            df = df.drop_duplicates(subset=["ticker"], keep="last")
            if len(df) > 1:
                # keep current ticker too because comparison often includes base company; put it first.
                pass
            df["industry"] = df["industry"].replace({"": industry_path})
            df["peer_group"] = df["peer_group"].replace({"": industry_path or "Vietstock cùng ngành"})
            df = df.sort_values(["ticker"]).reset_index(drop=True)
        else:
            df = pd.DataFrame(columns=["ticker", "company_name", "exchange", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"])

        raw_path = _save_raw(self.raw_dir / "vietstock_peers", ticker, "vietstock_industry_peers", payload)
        csv_path = raw_path.with_suffix(".csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        if df.empty:
            note = "Không tách được danh sách cùng ngành từ Vietstock; raw HTML/API đã lưu để kiểm tra. Có thể Vietstock đổi endpoint hoặc chặn dữ liệu động."
        else:
            note = f"Đã lấy {len(df):,} mã từ Vietstock cùng ngành cho {ticker}. Nhóm ngành nhận diện: {industry_path or 'chưa rõ'}."
        return raw_path, df, note

    def fetch(self, ticker: str) -> ProviderResult:
        raw_path, payloads, tables = self.fetch_raw(ticker)
        raw_payload = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}
        result = _normalize_from_payloads(payloads, tables, ticker.upper().strip(), "FireAnt", responses=raw_payload.get("responses", []), raw_dir=self.raw_dir)
        result.raw_path = raw_path
        if result.overview.empty and result.annual.empty and result.quarterly.empty:
            return _empty_result(raw_path, "FireAnt crawler đã gọi đúng endpoint trong Excel VBA nhưng chưa tách được dữ liệu chuẩn. Xem raw_data để kiểm tra status/body.")
        result.note += " FireAnt Excel VBA endpoints; raw response đã lưu trong raw_data."
        return result


class PublicSimplizeCrawler:
    """Fast peer-universe crawler for Simplize industry pages.

    So sánh doanh nghiệp no longer uses Vietstock/Selenium for peers. The crawler resolves the current
    ticker to its Simplize industry page, then parses static stock links on that page.
    If Simplize changes the layout, it returns an empty dataframe with a clear audit note
    instead of inventing peers.
    """

    def __init__(self, raw_dir: str | Path):
        self.raw_dir = Path(raw_dir)

    @staticmethod
    def _clean_simplize_url(value: Any) -> str:
        url = str(value or "").strip()
        if not url:
            return ""
        if url.startswith("/"):
            url = "https://simplize.vn" + url
        if not url.startswith("https://simplize.vn/co-phieu/nganh/"):
            return ""
        return url.split("#", 1)[0].split("?", 1)[0]

    @staticmethod
    def _industry_group_from_url(url: str) -> str:
        try:
            parts = [x for x in url.split("/co-phieu/nganh/", 1)[1].split("/") if x]
        except Exception:
            return "Simplize cùng ngành"
        if not parts:
            return "Simplize cùng ngành"
        def title_slug(slug: str) -> str:
            return slug.replace("-", " ").strip().title()
        return " > ".join(title_slug(x) for x in parts)

    @staticmethod
    def _extract_industry_links_from_stock_html(html_text: str) -> list[str]:
        if not html_text:
            return []
        soup = BeautifulSoup(html_text, "html.parser")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = str(a.get("href") or "").strip()
            if "/co-phieu/nganh/" not in href:
                continue
            if href.startswith("/"):
                href = "https://simplize.vn" + href
            href = href.split("#", 1)[0].split("?", 1)[0]
            if href.startswith("https://simplize.vn/co-phieu/nganh/") and href not in links:
                links.append(href)
        # Prefer the deepest industry path, e.g. /co-phieu/nganh/cong-nghiep/co-so-ha-tang-giao-thong-van-tai
        return sorted(links, key=lambda u: (u.count("/"), len(u)), reverse=True)

    @staticmethod
    def _extract_industry_title(html_text: str, url: str) -> str:
        soup = BeautifulSoup(html_text or "", "html.parser")
        # Prefer dedicated heading/title so we keep Vietnamese accents exactly as Simplize displays them.
        for tag in soup.find_all(["h1", "title"]):
            t = tag.get_text(" ", strip=True)
            m = re.search(r"Cổ\s*Phiếu\s*Ngành\s+(.+?)(?:\s*-\s*Simplize|$)", t, flags=re.I)
            if m:
                val = re.sub(r"\s+", " ", m.group(1)).strip()
                if val:
                    return val
        text = soup.get_text(" ", strip=True)
        m = re.search(r"Cổ\s*Phiếu\s*Ngành\s+(.{3,90}?)(?:\s+Số lượng cổ phiếu|\s+Mã cổ phiếu|$)", text, flags=re.I)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
        return PublicSimplizeCrawler._industry_group_from_url(url)


    @staticmethod
    def _simplize_num(value: Any) -> float | None:
        """Parse Simplize display numbers such as 43,700, -0.53%, 2.10, or 156,54T.

        Percent signs are stripped and market-cap suffix T is interpreted as nghìn tỷ VND so the
        normalized value is kept in tỷ đồng, matching the rest of the app.
        """
        if value is None:
            return None
        text = str(value).strip()
        if not text or text in {"-", "--", "—", "–"}:
            return None
        neg = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
        # Simplize uses T for trillion VND display, e.g. 156,54T = 156,540 tỷ đồng.
        suffix_t = bool(re.search(r"T\s*$", text, flags=re.I))
        cleaned = re.sub(r"[^0-9,\.\-]", "", text)
        if not cleaned or cleaned in {"-", ".", ","}:
            return None
        # For Simplize market-cap suffix T, comma is a decimal separator: 32,243T = 32.243 nghìn tỷ = 32,243 tỷ.
        if suffix_t and "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "," in cleaned and "." not in cleaned:
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) != 3:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        try:
            val = float(cleaned)
        except Exception:
            return None
        if neg:
            val = -abs(val)
        if suffix_t:
            val *= 1000.0
        return val

    @staticmethod
    def _field_by_simplize_col(col: Any) -> str | None:
        n = _norm_text(col)
        if not n:
            return None
        checks = [
            ("ticker", ["ma co phieu", "ma ck", "ticker", "symbol", "stock code", "stockcode", "code"]),
            ("company_name", ["ten cong ty", "ten doanh nghiep", "company", "company name", "organ name", "name", "ten"]),
            ("current_price", ["gia hien tai", "gia", "price", "current price", "last price", "close price"]),
            ("price_change_pct", ["bien dong gia", "thay doi gia", "change percent", "price change", "per change", "% change"]),
            ("change_7d_pct", ["7 ngay", "7d", "1 tuan", "week"]),
            ("change_1y_pct", ["1 nam", "1y", "year", "nam"]),
            ("pe", ["p/e", "pe"]),
            ("pb", ["p/b", "pb"]),
            ("roe_pct", ["roe"]),
            ("forecast_profit_growth_3y_pct", ["truong lnst 3 nam du phong", "tang truong lnst 3 nam", "lnst 3 nam", "profit growth", "eps growth"]),
            ("dividend_yield_pct", ["ty suat co tuc", "dividend yield", "co tuc"]),
            ("exchange", ["san", "exchange", "floor"]),
            ("market_cap_bil", ["von hoa", "market cap", "capitalization"]),
        ]
        for field, aliases in checks:
            if any(a in n for a in aliases):
                return field
        return None

    def _record_from_simplize_mapping(self, mapping: dict[str, Any], industry_name: str, industry_url: str, base_ticker: str) -> dict[str, Any] | None:
        if not isinstance(mapping, dict):
            return None
        out: dict[str, Any] = {}
        # Known key aliases from public React/Next data and possible API shapes.
        key_aliases = {
            "ticker": ["ticker", "symbol", "stockCode", "stock_code", "code", "ma", "maCoPhieu"],
            "company_name": ["companyName", "organName", "organizationName", "name", "company", "ten", "shortName"],
            "current_price": ["price", "currentPrice", "lastPrice", "closePrice", "matchPrice", "giaHienTai"],
            "price_change_pct": ["priceChangePercent", "changePercent", "percentChange", "perChange", "changePct"],
            "change_7d_pct": ["change7d", "change7D", "return7d", "return7D", "performance7D"],
            "change_1y_pct": ["change1y", "change1Y", "return1y", "return1Y", "performance1Y"],
            "pe": ["pe", "PE", "priceToEarning", "priceToEarnings"],
            "pb": ["pb", "PB", "priceToBook"],
            "roe_pct": ["roe", "ROE", "returnOnEquity"],
            "forecast_profit_growth_3y_pct": ["forecastProfitGrowth3Y", "profitGrowth3YForecast", "netProfitGrowth3Y", "growth3Y"],
            "dividend_yield_pct": ["dividendYield", "dividend_yield", "cashDividendYield"],
            "exchange": ["exchange", "exchangeName", "floor", "san"],
            "market_cap_bil": ["marketCap", "market_cap", "marketCapital", "capitalization", "vonHoa"],
        }
        for field, aliases in key_aliases.items():
            for k in aliases:
                if k in mapping and mapping.get(k) not in (None, ""):
                    out[field] = mapping.get(k)
                    break
        # Normalized-key fallback.
        if "ticker" not in out:
            for k, v in mapping.items():
                field = self._field_by_simplize_col(k)
                if field and field not in out:
                    out[field] = v
        code = str(out.get("ticker") or "").upper().strip()
        if not _is_probable_vn_ticker(code, base_ticker=base_ticker):
            return None
        name = re.sub(r"\s+", " ", str(out.get("company_name") or "").strip())
        name = re.sub(rf"^{re.escape(code)}\s+", "", name, flags=re.I).strip()
        rec = {
            "ticker": code,
            "company_name": name,
            "exchange": str(out.get("exchange") or "").upper().strip(),
            "industry": industry_name,
            "sub_industry": industry_name,
            "peer_group": industry_name,
            "source": "Simplize industry page",
            "note": f"Crawl từ {industry_url}",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "current_price": self._simplize_num(out.get("current_price")),
            "price_change_pct": self._simplize_num(out.get("price_change_pct")),
            "change_7d_pct": self._simplize_num(out.get("change_7d_pct")),
            "change_1y_pct": self._simplize_num(out.get("change_1y_pct")),
            "pe": self._simplize_num(out.get("pe")),
            "pb": self._simplize_num(out.get("pb")),
            "roe_pct": self._simplize_num(out.get("roe_pct")),
            "forecast_profit_growth_3y_pct": self._simplize_num(out.get("forecast_profit_growth_3y_pct")),
            "dividend_yield_pct": self._simplize_num(out.get("dividend_yield_pct")),
            "market_cap_bil": self._simplize_num(out.get("market_cap_bil")),
            "chart_30d": "",
        }
        return rec

    @staticmethod
    def _walk_json_objects(obj: Any) -> Iterable[dict[str, Any]]:
        if isinstance(obj, dict):
            yield obj
            for v in obj.values():
                yield from PublicSimplizeCrawler._walk_json_objects(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from PublicSimplizeCrawler._walk_json_objects(v)

    def _records_from_next_json(self, html_text: str, industry_name: str, industry_url: str, base_ticker: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html_text or "", "html.parser")
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        scripts = []
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag and tag.string:
            scripts.append(tag.string)
        for script in soup.find_all("script"):
            txt = script.string or script.get_text(" ", strip=True)
            if txt and ("stock" in txt.lower() or "marketcap" in txt.lower() or "ma co phieu" in _norm_text(txt[:2000])):
                scripts.append(txt)
        for txt in scripts:
            candidates: list[Any] = []
            stripped = (txt or "").strip()
            if stripped.startswith("{") or stripped.startswith("["):
                candidates.append(stripped)
            # Extract JSON blobs assigned in scripts; keep conservative to avoid JS syntax.
            for m in re.finditer(r"(\{\s*\"(?:props|pageProps|stocks|data|industry|symbols)\".*?\})\s*(?:;|</script>|$)", stripped, flags=re.S):
                candidates.append(m.group(1))
            for cand in candidates:
                try:
                    obj = json.loads(cand)
                except Exception:
                    continue
                for d in self._walk_json_objects(obj):
                    rec = self._record_from_simplize_mapping(d, industry_name, industry_url, base_ticker)
                    if rec and rec["ticker"] not in seen:
                        seen.add(rec["ticker"])
                        records.append(rec)
        return records

    def _records_from_html_tables(self, html_text: str, industry_name: str, industry_url: str, base_ticker: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            tables = pd.read_html(StringIO(html_text or ""))
        except Exception:
            tables = []
        for table in tables:
            if table is None or table.empty:
                continue
            flat_cols = []
            for c in table.columns:
                if isinstance(c, tuple):
                    flat_cols.append(" ".join(str(x) for x in c if str(x) != "nan"))
                else:
                    flat_cols.append(str(c))
            table.columns = flat_cols
            mapped = {c: self._field_by_simplize_col(c) for c in table.columns}
            if "ticker" not in set(x for x in mapped.values() if x):
                # Sometimes first column is the ticker column without a label.
                mapped[table.columns[0]] = "ticker"
            for _, row in table.iterrows():
                data = {field: row[col] for col, field in mapped.items() if field}
                rec = self._record_from_simplize_mapping(data, industry_name, industry_url, base_ticker)
                if rec and rec["ticker"] not in seen:
                    seen.add(rec["ticker"])
                    records.append(rec)
        return records

    def _records_from_visible_text(self, html_text: str, industry_name: str, industry_url: str, base_ticker: str) -> list[dict[str, Any]]:
        """Heuristic parser for Simplize server-rendered grid text.

        It follows the visible column order shown on Simplize industry pages:
        Mã, Tên, Giá hiện tại, Biến động giá, 7 ngày, 1 năm, P/E, P/B, ROE,
        Tăng trưởng LNST 3 năm dự phóng, Tỷ suất cổ tức, Sàn, Vốn hóa.
        """
        soup = BeautifulSoup(html_text or "", "html.parser")
        lines = [re.sub(r"\s+", " ", x).strip() for x in soup.get_text("\n", strip=True).splitlines()]
        lines = [x for x in lines if x]
        # Focus after the table header when possible to avoid menus/search widgets.
        start = 0
        for i, line in enumerate(lines):
            if _norm_text(line) in {"ma co phieu", "ma ck"} or "ma co phieu" in _norm_text(line):
                start = i + 1
                break
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        i = start
        while i < len(lines):
            code = lines[i].upper().strip()
            if not _is_probable_vn_ticker(code, base_ticker=base_ticker):
                i += 1
                continue
            if i + 1 >= len(lines):
                break
            name = lines[i + 1]
            name_norm = _norm_text(name)
            header_like = {
                "gia hien tai", "bien dong gia", "7 ngay", "1 nam", "p/e", "p/b", "roe",
                "t truong lnst 3 nam du phong", "tang truong lnst 3 nam du phong",
                "ty suat co tuc", "san", "von hoa", "bieu do gia 30d", "so luong co phieu"
            }
            if name_norm in header_like or any(x in name_norm for x in ["du phong", "ty suat co tuc", "bieu do gia", "von hoa", "ma co phieu"]):
                i += 1
                continue
            # Avoid catching menu/header entries that do not have numeric stock data after company name.
            window = lines[i + 2:i + 16]
            if not any(re.search(r"\d", x) for x in window):
                i += 1
                continue
            vals = window + [""] * 14
            rec = {
                "ticker": code,
                "company_name": name,
                "exchange": str(vals[10] or "").upper().strip() if not re.search(r"\d", str(vals[10])) else "",
                "industry": industry_name,
                "sub_industry": industry_name,
                "peer_group": industry_name,
                "source": "Simplize visible table",
                "note": f"Crawl từ {industry_url}",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "current_price": self._simplize_num(vals[0]),
                "price_change_pct": self._simplize_num(vals[1]),
                "change_7d_pct": self._simplize_num(vals[2]),
                "change_1y_pct": self._simplize_num(vals[3]),
                "pe": self._simplize_num(vals[4]),
                "pb": self._simplize_num(vals[5]),
                "roe_pct": self._simplize_num(vals[6]),
                "forecast_profit_growth_3y_pct": self._simplize_num(vals[7]),
                "dividend_yield_pct": self._simplize_num(vals[8]),
                "market_cap_bil": self._simplize_num(vals[11] if str(vals[10]).upper() in {"HOSE", "HNX", "UPCOM"} else vals[10]),
                "chart_30d": "",
            }
            if code not in seen:
                seen.add(code)
                records.append(rec)
            i += 2
        return records

    def _parse_industry_page(self, html_text: str, industry_url: str, base_ticker: str) -> pd.DataFrame:
        soup = BeautifulSoup(html_text or "", "html.parser")
        industry_name = self._extract_industry_title(html_text, industry_url)
        records: list[dict[str, Any]] = []
        seen: set[str] = set()

        def merge_record(rec: dict[str, Any] | None) -> None:
            if not rec:
                return
            code = str(rec.get("ticker") or "").upper().strip()
            if not _is_probable_vn_ticker(code, base_ticker=base_ticker):
                return
            if code in seen:
                # Fill missing Simplize metrics if a later parser found them.
                for old in records:
                    if old.get("ticker") == code:
                        for k, v in rec.items():
                            old_val = old.get(k)
                            try:
                                old_missing = pd.isna(old_val) or old_val == ""
                            except Exception:
                                old_missing = old_val in (None, "")
                            if old_missing and v not in (None, ""):
                                old[k] = v
                        break
                return
            seen.add(code)
            rec["ticker"] = code
            records.append(rec)

        # 1) Parse structured Next/React JSON when available.
        for rec in self._records_from_next_json(html_text, industry_name, industry_url, base_ticker):
            merge_record(rec)

        # 2) Parse server-rendered HTML tables when Simplize exposes <table> markup.
        for rec in self._records_from_html_tables(html_text, industry_name, industry_url, base_ticker):
            merge_record(rec)

        # 3) Primary visible anchors: stock cards on Simplize industry page are anchors to /co-phieu/{TICKER}.
        for a in soup.find_all("a", href=True):
            href = str(a.get("href") or "").strip()
            if "/co-phieu/nganh/" in href:
                continue
            m = re.search(r"(?:https?://simplize\.vn)?/co-phieu/([A-Z][A-Z0-9]{1,5})(?:$|[/?#])", href, flags=re.I)
            if not m:
                continue
            code = m.group(1).upper()
            text = a.get_text(" ", strip=True)
            if text and not re.search(rf"\b{re.escape(code)}\b", text, flags=re.I):
                text = f"{code} {text}"
            rec = self._record_from_simplize_mapping({"ticker": code, "company_name": text}, industry_name, industry_url, base_ticker)
            merge_record(rec)

        # 4) Fallback from visible text in the exact table order seen on Simplize pages.
        if len(records) < 2 or not any(r.get("current_price") is not None for r in records):
            for rec in self._records_from_visible_text(html_text, industry_name, industry_url, base_ticker):
                merge_record(rec)

        df = pd.DataFrame(records)
        columns = [
            "ticker", "company_name", "current_price", "price_change_pct", "change_7d_pct", "change_1y_pct",
            "pe", "pb", "roe_pct", "forecast_profit_growth_3y_pct", "dividend_yield_pct", "exchange",
            "market_cap_bil", "chart_30d", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"
        ]
        if df.empty:
            return pd.DataFrame(columns=columns)
        for col in columns:
            if col not in df.columns:
                df[col] = "" if col not in {"current_price", "price_change_pct", "change_7d_pct", "change_1y_pct", "pe", "pb", "roe_pct", "forecast_profit_growth_3y_pct", "dividend_yield_pct", "market_cap_bil"} else None
        # Clean company names and sort like Simplize by market cap descending if available.
        df["company_name"] = df["company_name"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
        sort_series = pd.to_numeric(df.get("market_cap_bil"), errors="coerce")
        if sort_series.notna().any():
            df = df.assign(_sort_cap=sort_series).sort_values("_sort_cap", ascending=False).drop(columns=["_sort_cap"])
        else:
            df = df.sort_values("ticker")
        return df[columns].drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)


    def fetch_industry_peers(self, ticker: str, industry_url: str | None = None) -> tuple[Path, pd.DataFrame, str]:
        ticker = str(ticker or "").upper().strip()
        payload: dict[str, Any] = {"ticker": ticker, "requested_industry_url": industry_url or "", "responses": []}
        resolved_url = self._clean_simplize_url(industry_url)

        with _simplize_client() as client:
            if not resolved_url and ticker:
                stock_url = f"https://simplize.vn/co-phieu/{ticker}"
                stock_resp = _get(client, "simplize_stock_page", stock_url)
                payload["responses"].append(stock_resp.__dict__)
                links = self._extract_industry_links_from_stock_html(stock_resp.body or "")
                payload["industry_link_candidates"] = links
                resolved_url = links[0] if links else ""

            if resolved_url:
                industry_resp = _get(client, "simplize_industry_page", resolved_url)
                payload["resolved_industry_url"] = resolved_url
                payload["responses"].append(industry_resp.__dict__)
                df = self._parse_industry_page(industry_resp.body or "", resolved_url, ticker)
            else:
                df = pd.DataFrame(columns=["ticker", "company_name", "exchange", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"])

        raw_path = _save_raw(self.raw_dir / "simplize_peers", ticker or "UNKNOWN", "simplize_industry_peers", payload)
        df.to_csv(raw_path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
        if df.empty:
            note = "Không lấy được danh sách cùng ngành từ Simplize. Hãy nhập URL ngành Simplize hoặc import CSV thủ công; app không tự sinh peer suy đoán."
        else:
            group = str(df["peer_group"].iloc[0]) if "peer_group" in df.columns else "Simplize cùng ngành"
            note = f"Đã lấy {len(df):,} mã cùng ngành từ Simplize cho {ticker}. Nhóm ngành: {group}."
        return raw_path, df, note


class PublicVietstockCrawler:
    """No-token Vietstock crawler with anti-forgery-token preparation."""

    def __init__(self, raw_dir: str | Path = "raw_data"):
        self.raw_dir = Path(raw_dir)

    @staticmethod
    def _token_from_html(html: str | None) -> str | None:
        if not html:
            return None
        patterns = [
            r'name=["\']__RequestVerificationToken["\'][^>]*value=["\']([^"\']+)',
            r'__RequestVerificationToken[^>]+value=["\']([^"\']+)',
            r'var\s+_token\s*=\s*["\']([^"\']+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, flags=re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def fetch_raw(self, ticker: str) -> tuple[Path, list[Any], list[pd.DataFrame]]:
        ticker = ticker.upper().strip()
        payload: dict[str, Any] = {"ticker": ticker, "responses": []}
        current_year = _now_year()
        with _client() as client:
            search_url = f"https://api.vietstock.vn/search/stock?q={ticker.lower()}&limit=10&languageID=1"
            search_resp = _get(client, "vietstock_search", search_url)
            payload["responses"].append(search_resp.__dict__)

            pages = [
                f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm",
                f"https://finance.vietstock.vn/{ticker}/financials.htm",
                f"https://finance.vietstock.vn/{ticker}.htm",
                f"https://finance.vietstock.vn/{ticker}/tai-tai-lieu.htm",
                f"https://finance.vietstock.vn/{ticker}/transaction-statistics.htm?grid=market&languageid=1",
            ]
            page_resp = None
            for url in pages:
                resp = _get(client, "vietstock_page", url)
                payload["responses"].append(resp.__dict__)
                if page_resp is None or (resp.body and self._token_from_html(resp.body)):
                    page_resp = resp

            token = self._token_from_html(page_resp.body if page_resp else None)
            if token:
                finance_url = f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm"
                headers = dict(HEADERS)
                headers.update({
                    "Origin": "https://finance.vietstock.vn",
                    "Referer": finance_url,
                    "X-Requested-With": "XMLHttpRequest",
                    "RequestVerificationToken": token,
                    "__RequestVerificationToken": token,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                })
                candidates = []
                # Vietstock public endpoint commonly uses ReportType + ReportTermType + Page/PageSize.
                # Keep legacy field aliases too because the site has changed names across versions.
                for report_type in ["BCTT", "CDKT", "KQKD", "LC", "CSTC"]:
                    for term_type in [1, 2]:  # 1=annual, 2=quarterly
                        for unit in [1000000, 1000000000]:
                            candidates.append(("https://finance.vietstock.vn/data/financeinfo", {
                                "Code": ticker, "code": ticker,
                                "ReportType": report_type, "type": report_type,
                                "ReportTermType": str(term_type),
                                "Unit": str(unit),
                                "Page": "1", "PageSize": "20",
                                "languageID": "1", "languageid": "1",
                                "__RequestVerificationToken": token,
                            }))
                candidates.extend([
                    ("https://finance.vietstock.vn/data/getstockdealdetail", {"code": ticker, "Code": ticker, "languageID": 1, "languageid": 1}),
                    ("https://finance.vietstock.vn/data/financeinfo", {"Code": ticker, "ReportType": "BCTT", "ReportTermType": 1, "year": current_year, "quarter": 4, "languageID": 1}),
                ])
                for url, data in candidates:
                    try:
                        resp = client.post(url, data=data, headers=headers)
                        payload["responses"].append({
                            "source": "vietstock_post_candidate",
                            "url": url,
                            "status_code": resp.status_code,
                            "content_type": resp.headers.get("content-type"),
                            "request_data": data,
                            "body": resp.text[:3_000_000],
                        })
                    except Exception as exc:
                        payload["responses"].append({"source": "vietstock_post_candidate", "url": url, "request_data": data, "error": str(exc)})
            else:
                payload["note"] = "Không tìm thấy Vietstock anti-forgery token trên HTML public. App vẫn lưu raw page để kiểm tra/fallback."

        responses = payload["responses"]
        table_files, tables = _extract_html_tables(self.raw_dir, ticker, "vietstock", responses)
        json_files, payloads = _extract_json_preview(self.raw_dir, ticker, "vietstock", responses)
        payload["table_files"] = table_files
        payload["json_files"] = json_files
        payload["browser_files"] = []
        payload["browser_diagnostics"] = [{"note": "V14 không dùng browser automation để tránh lỗi subprocess trong Streamlit/Windows."}]
        raw_path = _save_raw(self.raw_dir, ticker, "vietstock_public", payload)
        return raw_path, payloads, tables


    def fetch_industry_peers(self, ticker: str) -> tuple[Path, pd.DataFrame, str]:
        """Fetch Vietstock same-industry peer list for a ticker.

        V23.25: the Vietstock "Cùng ngành" table is rendered dynamically. This method therefore:
        1) opens the real Vietstock page with Selenium/Chrome headless when available;
        2) reads the rendered DOM inside the same-industry widget and browser network JSON/HTML bodies;
        3) tries a small set of Vietstock AJAX candidates with the page anti-forgery token; and
        4) returns an empty dataframe with a clear warning if no real dynamic Vietstock peer table is available.

        Important: no curated/synthetic fallback peer list is generated. This avoids wrong peer lists such as
        STOCK/HOSTC or broad-sector guesses.
        """
        ticker = ticker.upper().strip()
        url = f"https://finance.vietstock.vn/{ticker}/so-sanh-gia-co-phieu-cung-nganh.htm"
        payload: dict[str, Any] = {"ticker": ticker, "url": url, "responses": [], "diagnostics": []}
        records: list[dict[str, Any]] = []
        industry_path = ""

        def add_record(code: Any, name: Any = "", exchange: Any = "", industry: Any = "", sub_industry: Any = "", source: str = "Vietstock") -> None:
            code_text = str(code or "").upper().strip()
            if not _is_probable_vn_ticker(code_text, base_ticker=ticker):
                return
            records.append({
                "ticker": code_text,
                "company_name": str(name or "").strip(),
                "exchange": str(exchange or "").strip(),
                "industry": str(industry or industry_path or "").strip(),
                "sub_industry": str(sub_industry or "").strip(),
                "peer_group": str(sub_industry or industry or industry_path or "Vietstock cùng ngành").strip(),
                "source": source,
                "note": f"Crawl từ {url}",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        def walk_json(obj: Any, source: str = "Vietstock JSON/API") -> None:
            if isinstance(obj, dict):
                code = _get_by_alias(obj, ["ticker", "Ticker", "code", "Code", "symbol", "Symbol", "StockCode", "stockCode", "StockSymbol", "stockSymbol", "Ma", "MaCK", "mack", "StockNo", "stockNo"])
                name = _get_by_alias(obj, ["companyName", "CompanyName", "name", "Name", "ten", "Ten", "StockName", "stockName", "FullName", "fullName", "Company", "company"])
                exchange = _get_by_alias(obj, ["exchange", "Exchange", "san", "San", "market", "Market", "floor", "Floor", "ExchangeName", "exchangeName"])
                industry = _get_by_alias(obj, ["industry", "Industry", "sector", "Sector", "nganh", "Nganh", "industryName", "IndustryName", "ICBName", "icbName"])
                sub = _get_by_alias(obj, ["subIndustry", "SubIndustry", "sub_industry", "SubIndustryName", "subIndustryName", "nganhCon", "NganhCon"])
                if code:
                    add_record(code, name, exchange, industry or industry_path, sub, source)
                for v in obj.values():
                    walk_json(v, source)
            elif isinstance(obj, list):
                for item in obj:
                    walk_json(item, source)
            elif isinstance(obj, str):
                text = obj.upper().strip()
                if _is_probable_vn_ticker(text, base_ticker=ticker):
                    add_record(text, "", "", industry_path, "", source)

        def parse_html_tables(html_text: str, source: str) -> None:
            if "<table" not in (html_text or "").lower():
                return
            try:
                for table in pd.read_html(StringIO(html_text)):
                    if table.empty:
                        continue
                    cols = {str(c).strip().lower(): c for c in table.columns}
                    code_col = None
                    name_col = None
                    exchange_col = None
                    for key, col in cols.items():
                        nkey = _norm_text(key)
                        if code_col is None and ("ma ck" in nkey or nkey == "ma" or nkey in {"ticker", "code", "symbol"}):
                            code_col = col
                        if name_col is None and ("ten" in nkey or "company" in nkey or "doanh nghiep" in nkey):
                            name_col = col
                        if exchange_col is None and ("san" in nkey or "exchange" in nkey or "market" in nkey):
                            exchange_col = col
                    if code_col is not None:
                        for _, row in table.iterrows():
                            add_record(row.get(code_col), row.get(name_col, "") if name_col is not None else "", row.get(exchange_col, "") if exchange_col is not None else "", industry_path, "", source)
            except Exception as exc:
                payload["diagnostics"].append({"parser": "html_table", "source": source, "error": str(exc)})

        def parse_stock_links_from_html(html_text: str, source: str, default_industry: str = "") -> None:
            if not html_text:
                return
            soup_local = BeautifulSoup(html_text, "html.parser")
            for a in soup_local.find_all("a", href=True):
                href = str(a.get("href") or "")
                label = a.get_text(" ", strip=True)
                code = ""
                for pat in [
                    r"finance\.vietstock\.vn/([A-Z][A-Z0-9]{1,5})(?:[/\.\-]|$)",
                    r"^/([A-Z][A-Z0-9]{1,5})(?:-[^/]+\.htm|/[a-z0-9-]+\.htm|/|$)",
                ]:
                    m = re.search(pat, href, flags=re.I)
                    if m:
                        code = m.group(1).upper()
                        break
                if not code or not _is_probable_vn_ticker(code, base_ticker=ticker):
                    continue
                if _norm_text(label) in {"", "tong quan", "giao dich", "tai chinh", "xep hang", "ho so", "tin tuc", "tai lieu", "cung nganh"}:
                    label = ""
                add_record(code, label, "", default_industry or industry_path, "", source)

        def parse_rendered_peer_area(html_text: str, source: str) -> None:
            """Parse only the rendered same-industry widget, not the whole Vietstock page/navigation."""
            if not html_text:
                return
            soup = BeautifulSoup(html_text, "html.parser")
            containers = []
            for selector in ["#stock-relation-container", ".stock-relation__container", ".relation-content"]:
                for c in soup.select(selector):
                    if c not in containers:
                        containers.append(c)
            if not containers:
                payload["diagnostics"].append({"browser_dom": "Không tìm thấy container #stock-relation-container/.relation-content trong DOM đã render."})
                return
            for container in containers:
                c_html = str(container)
                c_text = container.get_text(" ", strip=True)
                payload["responses"].append({
                    "source": f"{source}_container_html",
                    "url": url,
                    "status_code": 200,
                    "content_type": "text/html; rendered-container",
                    "body": c_html[:1_500_000],
                })
                parse_html_tables(c_html, source)
                parse_stock_links_from_html(c_html, source, industry_path)
                # Last resort within the widget only: visible ticker tokens. Do not scan the full page.
                for token in re.findall(r"\b[A-Z][A-Z0-9]{1,4}\b", c_text):
                    if _is_probable_vn_ticker(token, base_ticker=ticker):
                        add_record(token, "", "", industry_path, "", source)

        def try_selenium_browser() -> None:
            """Run Selenium in a short-lived subprocess so driver startup cannot freeze Streamlit."""
            try:
                worker_path = Path(__file__).resolve().parents[1] / "tools" / "vietstock_peer_browser_worker.py"
            except Exception:
                worker_path = Path("tools") / "vietstock_peer_browser_worker.py"
            if not worker_path.exists():
                payload["diagnostics"].append({"browser_automation": "worker_not_found", "worker": str(worker_path)})
                return
            out_dir = self.raw_dir / "vietstock_peers"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_json = out_dir / f"vietstock_browser_peer_{ticker}_{int(time.time())}.json"
            cmd = [sys.executable, str(worker_path), "--ticker", ticker, "--url", url, "--output", str(out_json)]
            try:
                completed = subprocess.run(
                    cmd,
                    cwd=str(Path(__file__).resolve().parents[1]),
                    capture_output=True,
                    text=True,
                    timeout=35,
                    check=False,
                )
                payload["diagnostics"].append({
                    "browser_worker": "completed",
                    "returncode": completed.returncode,
                    "stdout": (completed.stdout or "")[-4000:],
                    "stderr": (completed.stderr or "")[-4000:],
                    "output": str(out_json),
                })
            except subprocess.TimeoutExpired as exc:
                payload["diagnostics"].append({
                    "browser_worker": "timeout",
                    "timeout_seconds": 35,
                    "error": str(exc),
                    "hint": "Chrome/Selenium khởi động quá lâu hoặc bị chặn; app không dùng fallback suy đoán.",
                })
                return
            except Exception as exc:
                payload["diagnostics"].append({"browser_worker": "failed_to_start", "error": str(exc)})
                return
            if not out_json.exists():
                payload["diagnostics"].append({"browser_worker": "no_output_json", "output": str(out_json)})
                return
            try:
                browser_payload = json.loads(out_json.read_text(encoding="utf-8"))
            except Exception as exc:
                payload["diagnostics"].append({"browser_worker": "bad_output_json", "output": str(out_json), "error": str(exc)})
                return
            payload["diagnostics"].extend(browser_payload.get("diagnostics", []))
            page_source = browser_payload.get("page_source", "") or ""
            if page_source:
                payload["responses"].append({
                    "source": "vietstock_browser_page_source",
                    "url": url,
                    "status_code": 200,
                    "content_type": "text/html; selenium-rendered",
                    "body": page_source[:2_000_000],
                })
                parse_rendered_peer_area(page_source, "Vietstock browser DOM")
            for item in browser_payload.get("network_bodies", []) or []:
                body_text = item.get("body", "") or ""
                resp_url = item.get("url", "") or ""
                payload["responses"].append({
                    "source": "vietstock_browser_network",
                    "url": resp_url,
                    "status_code": item.get("status"),
                    "content_type": item.get("content_type"),
                    "body": body_text[:2_000_000],
                })
                parsed = _try_json(body_text)
                if parsed is not None:
                    walk_json(parsed, "Vietstock browser network")
                else:
                    parse_html_tables(body_text, "Vietstock browser network")
                    if "stock-relation" in body_text or "relation-content" in body_text or "RelCompanies" in body_text:
                        parse_rendered_peer_area(body_text, "Vietstock browser network")

        with _client() as client:
            resp = _get(client, "vietstock_industry_peer_page", url)
            payload["responses"].append(resp.__dict__)
            body = resp.body or ""
            gics = _extract_vietstock_gics_from_html(body)
            payload["vietstock_gics"] = gics
            if gics.get("industry_path"):
                industry_path = str(gics["industry_path"])

            if body:
                soup = BeautifulSoup(body, "html.parser")
                text = soup.get_text(" ", strip=True)
                m = re.search(r"Ngành:\s*([^\n\r]{3,220}?)(?:GD ký quỹ|XFVT|VN30|IR Awards|Tổng quan|Cùng ngành|$)", text, flags=re.I)
                if m:
                    from_breadcrumb = re.sub(r"\s+", " ", m.group(1)).strip(" >")
                    if (not industry_path) and from_breadcrumb and len(from_breadcrumb) <= 120 and not re.search(r"\d{2,}", from_breadcrumb):
                        industry_path = from_breadcrumb
                # Do not parse stock links from the full static HTML page; it includes navigation/demo links.

            # First priority: real browser-rendered Vietstock table/network.
            try_selenium_browser()

            token = self._token_from_html(body)
            headers = dict(HEADERS)
            headers.update({
                "Origin": "https://finance.vietstock.vn",
                "Referer": url,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            })
            if token:
                headers.update({"RequestVerificationToken": token, "__RequestVerificationToken": token})

            # Second priority: only Vietstock AJAX candidates. Do not use broad-sector seeds or non-Vietstock guessed peers.
            endpoint_candidates: list[tuple[str, dict[str, Any]]] = []
            for page_size in [200]:
                common = {"code": ticker, "Code": ticker, "symbol": ticker, "Ticker": ticker, "page": 1, "Page": 1, "pageSize": page_size, "PageSize": page_size, "languageID": 1, "languageid": 1}
                for ep in [
                    "https://finance.vietstock.vn/data/GetStockSameIndustry",
                    "https://finance.vietstock.vn/data/StockSameIndustry",
                    "https://finance.vietstock.vn/data/GetStockByIndustry",
                    "https://finance.vietstock.vn/data/CompareStockSameIndustry",
                ]:
                    endpoint_candidates.append((ep, dict(common)))
            for level in ["level4", "level3", "level2", "level1"]:
                gcode = str(gics.get(level, "") or "").strip()
                if not gcode:
                    continue
                for ep in [
                    "https://finance.vietstock.vn/data/GetStockByIndustry",
                    "https://finance.vietstock.vn/data/StockByIndustry",
                ]:
                    endpoint_candidates.append((ep, {"industryCode": gcode, "IndustryCode": gcode, "gicsCode": gcode, "GicsCode": gcode, "page": 1, "Page": 1, "pageSize": 200, "PageSize": 200, "languageID": 1, "languageid": 1}))

            seen_candidate_keys: set[tuple[str, str]] = set()
            for ep, data in endpoint_candidates:
                key = (ep, json.dumps(data, sort_keys=True, ensure_ascii=False))
                if key in seen_candidate_keys:
                    continue
                seen_candidate_keys.add(key)
                try:
                    r = client.post(ep, data=data, headers=headers, timeout=4.0)
                    body_text = r.text or ""
                    payload["responses"].append({"source": "vietstock_industry_peer_candidate", "url": ep, "status_code": r.status_code, "content_type": r.headers.get("content-type"), "request_data": data, "body": body_text[:2_000_000]})
                    parsed = _try_json(body_text)
                    if parsed is not None:
                        walk_json(parsed, "Vietstock JSON/API")
                    else:
                        parse_html_tables(body_text, "Vietstock AJAX table")
                except Exception as exc:
                    payload["responses"].append({"source": "vietstock_industry_peer_candidate", "url": ep, "request_data": data, "error": str(exc)})

        df = pd.DataFrame(records)
        if not df.empty:
            df = df.drop_duplicates(subset=["ticker"], keep="last")
            # If the only detected record is the base ticker, this is not a real same-industry list.
            non_base = set(df["ticker"].astype(str).str.upper()) - {ticker}
            if len(non_base) == 0:
                payload["diagnostics"].append({"peer_result": "base_ticker_only", "action": "return_empty_dataframe_no_synthetic_fallback"})
                df = pd.DataFrame(columns=["ticker", "company_name", "exchange", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"])
            else:
                df["_base_sort"] = df["ticker"].eq(ticker).map({True: 0, False: 1})
                df["industry"] = df["industry"].replace({"": industry_path})
                df["peer_group"] = df["peer_group"].replace({"": industry_path or "Vietstock cùng ngành"})
                df = df.sort_values(["_base_sort", "ticker"]).drop(columns=["_base_sort"]).reset_index(drop=True)
        else:
            df = pd.DataFrame(columns=["ticker", "company_name", "exchange", "industry", "sub_industry", "peer_group", "source", "note", "updated_at"])

        payload["final_peer_count"] = int(len(df))
        payload["final_peer_tickers"] = df["ticker"].tolist() if not df.empty and "ticker" in df.columns else []
        payload["industry_path"] = industry_path
        raw_path = _save_raw(self.raw_dir / "vietstock_peers", ticker, "vietstock_industry_peers", payload)
        csv_path = raw_path.with_suffix(".csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        if df.empty:
            note = (
                f"Chưa lấy được bảng động Vietstock cho {ticker}. App đã lưu raw HTML/browser/API để kiểm tra tại raw_data/vietstock_peers. "
                "Không tự sinh danh sách fallback để tránh so sánh sai ngành. Hãy thử bấm crawl lại, kiểm tra Chrome/Selenium, hoặc import CSV peer thủ công."
            )
        else:
            note = f"Đã lấy {len(df):,} mã từ bảng động/API Vietstock cho {ticker}. Nhóm ngành nhận diện: {industry_path or 'chưa rõ'}."
        return raw_path, df, note


    def fetch(self, ticker: str) -> ProviderResult:
        raw_path, payloads, tables = self.fetch_raw(ticker)
        result = _normalize_from_payloads(payloads, tables, ticker.upper().strip(), "Vietstock", responses=json.loads(raw_path.read_text(encoding="utf-8")).get("responses", []) if raw_path.exists() else None, raw_dir=self.raw_dir)
        result.raw_path = raw_path
        if result.overview.empty and result.annual.empty and result.quarterly.empty:
            return _empty_result(raw_path, "Vietstock public crawler đã lưu raw nhưng chưa tách được dữ liệu chuẩn để cập nhật dashboard.")
        result.note += " Raw response đã lưu trong raw_data."
        return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", default="DCM")
    parser.add_argument("--source", choices=["fireant", "vietstock", "both"], default="both")
    parser.add_argument("--raw-dir", default="raw_data")
    args = parser.parse_args()
    if args.source in {"fireant", "both"}:
        result = PublicFireAntCrawler(args.raw_dir).fetch(args.ticker)
        print(result.raw_path)
        print(result.note)
        print("overview", len(result.overview), "annual", len(result.annual), "quarterly", len(result.quarterly))
    if args.source in {"vietstock", "both"}:
        result = PublicVietstockCrawler(args.raw_dir).fetch(args.ticker)
        print(result.raw_path)
        print(result.note)
        print("overview", len(result.overview), "annual", len(result.annual), "quarterly", len(result.quarterly))
