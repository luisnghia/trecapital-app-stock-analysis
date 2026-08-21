from __future__ import annotations

"""Industry/source policy applied on top of the Trecapital checklist data bridge.

This layer deliberately suppresses metrics that are economically misleading for special industries
and prevents raw TTM pre-tax profit from masquerading as normalized earnings for cyclicals.
"""

from dataclasses import replace
from typing import Any

import pandas as pd

from .services.formulas import inventory_metrics


_SPECIAL_FINANCIAL_TYPES = {"bank", "insurance", "securities"}
_NORMALIZED_FIELDS = (
    "normalized_earnings_bil",
    "normalized_pretax_profit_bil",
    "normalized_ebt_bil",
    "normalized_operating_earnings_bil",
)


def _period_token(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "T12M" in text:
        return "TTM"
    if "TTM" in text:
        return "TTM"
    try:
        number = float(text)
        if number.is_integer() and 1900 <= int(number) <= 2200:
            return str(int(number))
    except Exception:
        pass
    return text


def _explicit_normalized_for_period(provider, period: Any) -> float | None:
    """Return a confirmed normalized value only from the same period.

    A normalized annual value from 2025 must not authorize the app to label raw TTM 2026 pre-tax
    profit as normalized. Period matching is therefore deliberate and strict.
    """
    df = getattr(provider, "annual_df", None)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    target = _period_token(period)
    if "period" in df.columns:
        mask = df["period"].map(_period_token).eq(target)
        candidates = df[mask]
    elif target.isdigit() and "year" in df.columns:
        years = pd.to_numeric(df["year"], errors="coerce")
        candidates = df[years.eq(float(target))]
    else:
        return None
    if candidates.empty:
        return None
    for _, row in candidates.iloc[::-1].iterrows():
        for field in _NORMALIZED_FIELDS:
            if field not in row.index:
                continue
            value = pd.to_numeric(pd.Series([row.get(field)]), errors="coerce").iloc[0]
            if pd.notna(value):
                return float(value)
    return None


def _recompute_row_metrics(row: dict[str, Any]) -> dict[str, Any]:
    metrics = inventory_metrics(
        tev=row.get("tev"),
        ebit=row.get("ebit"),
        ebitda=row.get("ebitda"),
        normalized_earnings=row.get("normalized_earnings"),
        total_debt=row.get("total_debt"),
        interest_expense=row.get("interest_expense"),
        fcf_current=row.get("fcf_current"),
        market_cap=row.get("market_cap"),
        dividend_per_share=row.get("dividend_per_share"),
        market_price=row.get("market_price"),
        target_price=row.get("target_price"),
    )
    row.update(metrics)
    return row


class SourcePolicyDataProvider:
    """Transparent proxy around a TrecapitalDataProvider."""

    def __init__(self, inner, company_type: str = "normal"):
        self.inner = inner
        self.company_type = str(company_type or "normal").lower()

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def get_inventory_source_data(self, company_context):
        data = self.inner.get_inventory_source_data(company_context)
        if data is None:
            return None
        notes = list(getattr(data, "source_notes", ()) or ())

        if self.company_type in _SPECIAL_FINANCIAL_TYPES:
            notes.append(
                "CẢNH BÁO: Overlay ngành tài chính đang khóa TEV/EBITDA/FCF/CCC kiểu doanh nghiệp công nghiệp; "
                "các chỉ tiêu này không được dùng làm kết luận chính cho bank/insurance/securities."
            )
            return replace(
                data,
                tev=None,
                ebit=None,
                ebitda=None,
                normalized_earnings=None,
                total_debt=None,
                interest_expense=None,
                fcf_current=None,
                fcf_estimate=None,
                ccc_days=None,
                source_notes=tuple(notes),
            )

        explicit_current = _explicit_normalized_for_period(self.inner, data.as_of_date)
        if explicit_current is not None:
            notes.append(
                f"Normalized earnings dùng giá trị đã chuẩn hóa cùng kỳ {data.as_of_date} từ Trecapital Data Layer: "
                f"{explicit_current:,.0f} tỷ đồng."
            )
            return replace(data, normalized_earnings=explicit_current, source_notes=tuple(notes))

        if self.company_type == "cyclical":
            notes.append(
                "CẢNH BÁO: Doanh nghiệp chu kỳ chưa có normalized earnings cùng kỳ được xác nhận; "
                "raw TTM/pre-tax profit không được dùng thay normalized earnings. TEV/Norm.E và Pre-tax yield để trống chờ analyst/scenario."
            )
            return replace(data, normalized_earnings=None, source_notes=tuple(notes))

        if data.normalized_earnings is not None:
            notes.append(
                "Normalized earnings hiện là baseline proxy từ pre-tax profit gần nhất/TTM; "
                "chưa điều chỉnh one-off hoặc chuẩn hóa chu kỳ. Analyst cần override khi có bằng chứng chuẩn hóa."
            )
            return replace(data, source_notes=tuple(notes))

        return data

    def get_inventory_proxy_history(self, years: int = 10):
        getter = getattr(self.inner, "get_inventory_proxy_history", None)
        if not callable(getter):
            return []
        rows = [dict(x) for x in (getter(years) or [])]

        if self.company_type in _SPECIAL_FINANCIAL_TYPES:
            for row in rows:
                for key in (
                    "tev", "ebit", "ebitda", "normalized_earnings", "total_debt", "interest_expense",
                    "fcf_current", "fcf_estimate", "ccc_days",
                ):
                    row[key] = None
                _recompute_row_metrics(row)
            return rows

        for row in rows:
            explicit = _explicit_normalized_for_period(self.inner, row.get("period"))
            if explicit is not None:
                row["normalized_earnings"] = explicit
                _recompute_row_metrics(row)
            elif self.company_type == "cyclical":
                row["normalized_earnings"] = None
                _recompute_row_metrics(row)
        return rows
