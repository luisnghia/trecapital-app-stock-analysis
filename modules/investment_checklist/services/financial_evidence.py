from __future__ import annotations

"""Read-only question evidence adapter for the canonical Trecapital financial dataframe.

V99 deliberately does not fetch data and does not calculate finance metrics.  It only translates
already-normalized annual/TTM fields into auditable evidence rows for the Investment Checklist
report.  Missing canonical fields stay missing instead of being converted to zero or inferred.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd


MISSING_STANDARDIZED_DATA = "chưa có dữ liệu chuẩn hóa"
CANONICAL_SOURCE_MODULE = "Trecapital Data Layer"
CANONICAL_DATA_ORIGIN = "trecapital_canonical_financial_timeseries"


@dataclass(frozen=True)
class MetricSpec:
    code: str
    label: str
    unit: str
    fields: tuple[str, ...]


METRICS: dict[str, MetricSpec] = {
    "revenue": MetricSpec("revenue", "Doanh thu", "tỷ đồng", ("revenue_bil",)),
    "gross_profit": MetricSpec("gross_profit", "Lợi nhuận gộp", "tỷ đồng", ("gross_profit_bil",)),
    "operating_profit": MetricSpec(
        "operating_profit", "Lợi nhuận hoạt động / EBIT", "tỷ đồng",
        ("operating_profit_bil", "core_operating_profit_bil", "ebit_bil"),
    ),
    "net_profit": MetricSpec("net_profit", "Lợi nhuận sau thuế", "tỷ đồng", ("net_profit_bil", "net_income_bil")),
    "cfo": MetricSpec("cfo", "Dòng tiền từ HĐKD (CFO)", "tỷ đồng", ("cfo_bil", "operating_cash_flow_bil")),
    "capex": MetricSpec("capex", "Capex", "tỷ đồng", ("capex_bil",)),
    "fcf": MetricSpec("fcf", "Free Cash Flow", "tỷ đồng", ("free_cash_flow_bil",)),
    "cash": MetricSpec("cash", "Tiền và tương đương tiền", "tỷ đồng", ("cash_equivalents_bil",)),
    "short_investments": MetricSpec(
        "short_investments", "Đầu tư tài chính ngắn hạn", "tỷ đồng", ("short_term_investments_bil",),
    ),
    "cash_short_investments": MetricSpec(
        "cash_short_investments", "Tiền + đầu tư ngắn hạn", "tỷ đồng", ("cash_and_short_investments_bil",),
    ),
    "total_assets": MetricSpec("total_assets", "Tổng tài sản", "tỷ đồng", ("total_assets_bil",)),
    "equity": MetricSpec(
        "equity", "Vốn chủ sở hữu", "tỷ đồng", ("total_equity_bil", "equity_bil", "shareholders_equity_bil"),
    ),
    "debt": MetricSpec(
        "debt", "Nợ vay có lãi", "tỷ đồng",
        ("interest_bearing_debt_bil", "total_debt_bil", "borrowings_bil"),
    ),
    "accounts_receivable": MetricSpec(
        "accounts_receivable", "Phải thu khách hàng", "tỷ đồng", ("accounts_receivable_bil",),
    ),
    "inventory": MetricSpec("inventory", "Hàng tồn kho", "tỷ đồng", ("inventory_bil",)),
    "accounts_payable": MetricSpec(
        "accounts_payable", "Phải trả người bán", "tỷ đồng", ("accounts_payable_bil",),
    ),
    "ccc": MetricSpec(
        "ccc", "Cash Conversion Cycle", "ngày", ("cash_conversion_cycle_days", "ccc_days"),
    ),
    "roic": MetricSpec(
        "roic", "ROIC", "%", ("roic_standard_pct", "roic_pct", "return_on_invested_capital_pct"),
    ),
    "shares": MetricSpec(
        "shares", "Cổ phiếu lưu hành", "triệu cp", ("shares_outstanding_mil",),
    ),
    "treasury_shares": MetricSpec(
        "treasury_shares", "Cổ phiếu quỹ", "triệu cp", ("treasury_shares_mil",),
    ),
    "buyback": MetricSpec(
        "buyback", "Chi mua lại cổ phiếu", "tỷ đồng",
        ("share_buyback_bil", "share_repurchase_bil", "treasury_share_purchase_bil"),
    ),
    "cash_dividend": MetricSpec(
        "cash_dividend", "Cổ tức tiền mặt", "tỷ đồng", ("cash_dividend_bil",),
    ),
    "goodwill": MetricSpec("goodwill", "Lợi thế thương mại", "tỷ đồng", ("goodwill_bil",)),
    "acquisition_cashflow": MetricSpec(
        "acquisition_cashflow", "Dòng tiền M&A / mua công ty con", "tỷ đồng",
        ("acquisitions_bil", "acquisition_cash_outflow_bil", "purchase_subsidiaries_bil"),
    ),
}


QUESTION_METRICS: dict[str, tuple[str, ...]] = {
    "Q25": ("cash_short_investments", "cash", "short_investments", "total_assets", "equity", "debt"),
    "Q26": ("roic", "operating_profit", "net_profit", "total_assets", "equity"),
    "Q27": ("net_profit", "cfo", "accounts_receivable", "inventory"),
    "Q28": ("revenue", "gross_profit", "cfo"),
    "Q29": ("revenue", "gross_profit", "operating_profit", "net_profit"),
    "Q30": ("revenue", "gross_profit", "operating_profit", "net_profit"),
    "Q31": ("cfo", "accounts_receivable", "inventory", "accounts_payable", "ccc"),
    "Q32": ("capex", "cfo", "fcf"),
    "Q46": ("roic", "capex", "fcf", "cash_dividend", "debt"),
    "Q47": ("shares", "treasury_shares", "buyback"),
    "Q53": ("revenue", "total_assets", "goodwill", "acquisition_cashflow"),
    "Q54": ("revenue", "capex", "debt", "total_assets"),
    "Q55": ("revenue", "operating_profit", "net_profit", "roic", "cfo", "fcf"),
    "Q56": ("revenue", "operating_profit", "net_profit", "total_assets"),
    "Q57": ("revenue", "total_assets", "equity", "debt", "cfo", "capex"),
}


def _safe_value(value: Any) -> float | int | str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
        if pd.notna(number):
            return number
    except Exception:
        pass
    text = str(value).strip()
    return text or None


def _period_text(row: dict[str, Any]) -> str:
    value = row.get("period")
    if _safe_value(value) is None:
        value = row.get("year")
    if _safe_value(value) is None:
        return "kỳ chưa xác định"
    try:
        number = float(value)
        if number.is_integer() and 1900 <= int(number) <= 2200:
            return str(int(number))
    except Exception:
        pass
    return str(value).strip()


def _is_ttm(period: str) -> bool:
    token = str(period or "").upper()
    return "TTM" in token or "T12M" in token


def _year(period: str, row: dict[str, Any]) -> int:
    y = _safe_value(row.get("year"))
    try:
        if y is not None:
            return int(float(y))
    except Exception:
        pass
    for token in str(period).replace("/", " ").replace("-", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return 9999 if _is_ttm(period) else 0


def canonical_period_rows(provider, *, max_years: int = 10) -> list[dict[str, Any]]:
    """Return up to 10 annual periods plus TTM from the provider's canonical dataframe."""
    frame = getattr(provider, "annual_df", None)
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    rows: list[tuple[int, int, dict[str, Any]]] = []
    for order, (_, series) in enumerate(frame.iterrows()):
        row = series.to_dict()
        period = _period_text(row)
        period_type = str(row.get("period_type") or "").upper().strip()
        if period_type and period_type not in {"Y", "YEAR", "ANNUAL"} and not _is_ttm(period):
            continue
        rows.append((_year(period, row), order, row))
    annual = sorted((item for item in rows if not _is_ttm(_period_text(item[2]))), key=lambda x: (x[0], x[1]))
    ttm = sorted((item for item in rows if _is_ttm(_period_text(item[2]))), key=lambda x: (x[0], x[1]))
    selected = annual[-max(1, int(max_years)):] + (ttm[-1:] if ttm else [])
    return [row for _, _, row in selected]


def _first_direct_field(row: dict[str, Any], spec: MetricSpec) -> tuple[str | None, Any]:
    for field in spec.fields:
        if field not in row:
            continue
        value = _safe_value(row.get(field))
        if value is not None:
            return field, value
    return None, None


def format_evidence_value(value: Any, unit: str) -> str:
    value = _safe_value(value)
    if value is None:
        return MISSING_STANDARDIZED_DATA
    if isinstance(value, (int, float)):
        if unit == "%":
            return f"{float(value):,.1f}%"
        if unit == "ngày":
            return f"{float(value):,.1f} ngày"
        if unit == "VND/cp":
            return f"{float(value):,.0f} VND/cp"
        if unit == "triệu cp":
            return f"{float(value):,.1f} triệu cp"
        if unit == "tỷ đồng":
            return f"{float(value):,.1f} tỷ đồng"
        return f"{float(value):,.2f}"
    return str(value)


def extract_question_financial_evidence(provider, question_id: str, *, max_years: int = 10) -> list[dict[str, Any]]:
    """Translate canonical fields into traceable evidence rows; never derive a finance metric."""
    qid = str(question_id or "").upper().strip()
    metric_codes = QUESTION_METRICS.get(qid, ())
    if not metric_codes:
        return []
    periods = canonical_period_rows(provider, max_years=max_years)
    evidence: list[dict[str, Any]] = []
    for row in periods:
        period = _period_text(row)
        source_module = str(row.get("source_module") or CANONICAL_SOURCE_MODULE)
        data_origin = str(row.get("data_origin") or CANONICAL_DATA_ORIGIN)
        for metric_code in metric_codes:
            spec = METRICS[metric_code]
            field, value = _first_direct_field(row, spec)
            if field is None:
                continue
            evidence.append({
                "question_id": qid,
                "metric_code": spec.code,
                "metric": spec.label,
                "value": value,
                "value_display": format_evidence_value(value, spec.unit),
                "unit": spec.unit,
                "source_field": field,
                "source_module": source_module,
                "source_period": period,
                "data_origin": data_origin,
                "evidence_status": "available",
            })
    if evidence:
        return evidence
    return [{
        "question_id": qid,
        "metric_code": "missing",
        "metric": "Financial evidence",
        "value": None,
        "value_display": MISSING_STANDARDIZED_DATA,
        "unit": "",
        "source_field": None,
        "source_module": CANONICAL_SOURCE_MODULE,
        "source_period": None,
        "data_origin": CANONICAL_DATA_ORIGIN,
        "evidence_status": "missing",
    }]


def financial_evidence_map(provider, *, max_years: int = 10) -> dict[str, list[dict[str, Any]]]:
    return {
        qid: extract_question_financial_evidence(provider, qid, max_years=max_years)
        for qid in QUESTION_METRICS
    }


__all__ = [
    "MISSING_STANDARDIZED_DATA", "CANONICAL_SOURCE_MODULE", "CANONICAL_DATA_ORIGIN",
    "QUESTION_METRICS", "canonical_period_rows", "extract_question_financial_evidence",
    "financial_evidence_map", "format_evidence_value",
]
