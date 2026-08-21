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


def _has_explicit_normalized_earnings(provider) -> bool:
    df = getattr(provider, "annual_df", None)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    for field in _NORMALIZED_FIELDS:
        if field in df.columns and pd.to_numeric(df[field], errors="coerce").notna().any():
            return True
    return False


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

        explicit_normalized = _has_explicit_normalized_earnings(self.inner)
        if self.company_type == "cyclical" and not explicit_normalized:
            notes.append(
                "CẢNH BÁO: Doanh nghiệp chu kỳ chưa có normalized earnings được xác nhận; "
                "raw TTM pre-tax profit không được dùng thay normalized earnings. TEV/Norm.E và Pre-tax yield để trống chờ analyst/scenario."
            )
            return replace(data, normalized_earnings=None, source_notes=tuple(notes))

        if not explicit_normalized and data.normalized_earnings is not None:
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

        if self.company_type == "cyclical" and not _has_explicit_normalized_earnings(self.inner):
            for row in rows:
                row["normalized_earnings"] = None
                _recompute_row_metrics(row)
        return rows
