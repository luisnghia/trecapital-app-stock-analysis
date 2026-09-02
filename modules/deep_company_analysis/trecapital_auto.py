from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from modules.investment_checklist.services.formulas import inventory_metrics


QUANTITATIVE_CRITERIA = {
    "strong_financials",
    "high_roic",
    "low_capex",
    "strong_balance_sheet",
}

CONF_LOW = 1
CONF_MEDIUM = 2
CONF_HIGH = 3


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _number(row: dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        value = _safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _preferred_rows(df: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    work = df.copy()
    rows: list[dict[str, Any]] = []
    if "period" in work.columns:
        ttm_mask = work["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        for _, row in work[ttm_mask].iloc[::-1].iterrows():
            rows.append(row.to_dict())
    for _, row in work.iloc[::-1].iterrows():
        data = row.to_dict()
        period = str(data.get("period") or "").upper()
        if "TTM" in period or "T12M" in period:
            continue
        rows.append(data)
    return rows


def _latest_metric(df: pd.DataFrame, *keys: str) -> Optional[float]:
    for row in _preferred_rows(df):
        value = _number(row, *keys)
        if value is not None:
            return value
    return None


def _pct_from_row(row: dict[str, Any], pct_keys: tuple[str, ...], legacy_keys: tuple[str, ...] = ()) -> Optional[float]:
    """Read canonical *_pct fields as percentage points; convert only legacy fraction fields."""
    value = _number(row, *pct_keys)
    if value is not None:
        return value
    value = _number(row, *legacy_keys)
    if value is None:
        return None
    return value * 100.0 if abs(value) <= 2.0 else value


def _recent_roic_values(df: pd.DataFrame, years: int = 5) -> list[float]:
    values: list[float] = []
    for row in _preferred_rows(df):
        value = _pct_from_row(
            row,
            ("roic_standard_pct", "roic_pct", "return_on_invested_capital_pct"),
            ("roic", "return_on_invested_capital"),
        )
        if value is not None:
            values.append(value)
        if len(values) >= years:
            break
    return values


def _fmt(value: Optional[float], decimals: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}{suffix}"


def _suggest(status: str, confidence: int, evidence: str, *, rule: str) -> dict[str, Any]:
    return {
        "status": status,
        "confidence": int(confidence),
        "evidence": evidence,
        "rule": rule,
        "source": "Trecapital canonical data",
    }


def build_quantitative_suggestions(source: Any, annual_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Build conservative Data Suggested results for the four quantitative Table 1.1 criteria.

    These are research-assistant suggestions only. They must never overwrite a saved analyst
    assessment. Thresholds are Trecapital implementation heuristics, not rules stated by Shearn.
    """
    metrics = inventory_metrics(
        tev=_safe_float(getattr(source, "tev", None)),
        ebit=_safe_float(getattr(source, "ebit", None)),
        ebitda=_safe_float(getattr(source, "ebitda", None)),
        normalized_earnings=_safe_float(getattr(source, "normalized_earnings", None)),
        total_debt=_safe_float(getattr(source, "total_debt", None)),
        interest_expense=_safe_float(getattr(source, "interest_expense", None)),
        fcf_current=_safe_float(getattr(source, "fcf_current", None)),
        market_cap=_safe_float(getattr(source, "market_cap", None)),
        dividend_per_share=_safe_float(getattr(source, "dividend_per_share", None)),
        market_price=_safe_float(getattr(source, "market_price", None)),
        target_price=_safe_float(getattr(source, "target_price", None)),
    )

    ebit = _safe_float(getattr(source, "ebit", None))
    fcf = _safe_float(getattr(source, "fcf_current", None))
    debt_ebitda = _safe_float(metrics.get("debt_ebitda"))
    ebit_interest = _safe_float(metrics.get("ebit_interest"))
    market_cap = _safe_float(getattr(source, "market_cap", None))
    tev = _safe_float(getattr(source, "tev", None))
    net_debt = (tev - market_cap) if tev is not None and market_cap is not None else None

    out: dict[str, dict[str, Any]] = {}

    # Strong Financials: operating profitability + cash generation + debt service capacity.
    if ebit is None or fcf is None:
        out["strong_financials"] = _suggest(
            "— Chưa biết",
            CONF_LOW,
            f"EBIT {_fmt(ebit, 0)} tỷ; FCF {_fmt(fcf, 0)} tỷ. Chưa đủ hai đầu vào cốt lõi.",
            rule="Cần EBIT và FCF; sau đó kiểm tra leverage/interest cover khi có dữ liệu.",
        )
    elif ebit <= 0 or fcf <= 0 or (debt_ebitda is not None and debt_ebitda > 3.5) or (ebit_interest is not None and ebit_interest < 2.0):
        out["strong_financials"] = _suggest(
            "X Không",
            CONF_HIGH if ebit <= 0 or fcf <= 0 else CONF_MEDIUM,
            f"EBIT {_fmt(ebit, 0)} tỷ; FCF {_fmt(fcf, 0)} tỷ; Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; EBIT/Interest {_fmt(ebit_interest, 1, 'x')}.",
            rule="Không nếu EBIT/FCF âm, Debt/EBITDA >3.5x hoặc interest cover <2x.",
        )
    elif (debt_ebitda is None or debt_ebitda <= 2.5) and (ebit_interest is None or ebit_interest >= 4.0):
        out["strong_financials"] = _suggest(
            "✓ Có",
            CONF_MEDIUM,
            f"EBIT {_fmt(ebit, 0)} tỷ; FCF {_fmt(fcf, 0)} tỷ; Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; EBIT/Interest {_fmt(ebit_interest, 1, 'x')}.",
            rule="Có nếu EBIT/FCF dương, Debt/EBITDA ≤2.5x và interest cover ≥4x khi các ratio có dữ liệu.",
        )
    else:
        out["strong_financials"] = _suggest(
            "— Chưa biết",
            CONF_MEDIUM,
            f"EBIT {_fmt(ebit, 0)} tỷ; FCF {_fmt(fcf, 0)} tỷ; Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; EBIT/Interest {_fmt(ebit_interest, 1, 'x')}.",
            rule="Vùng trung gian: cần analyst xem xu hướng nhiều năm và chất lượng lợi nhuận.",
        )

    # High ROIC: canonical ROIC percentage points, recent 5 observations.
    roics = _recent_roic_values(annual_df, 5)
    latest_roic = roics[0] if roics else None
    median_roic = float(pd.Series(roics).median()) if roics else None
    if latest_roic is None:
        out["high_roic"] = _suggest(
            "— Chưa biết", CONF_LOW, "Trecapital chưa có ROIC canonical đủ tin cậy.", rule="Không suy diễn ROIC từ chỉ tiêu khác khi canonical ROIC thiếu."
        )
    elif latest_roic >= 15.0 and (median_roic is None or median_roic >= 15.0):
        out["high_roic"] = _suggest(
            "✓ Có",
            CONF_HIGH if len(roics) >= 3 else CONF_MEDIUM,
            f"ROIC gần nhất {_fmt(latest_roic, 1, '%')}; trung vị tối đa 5 kỳ {_fmt(median_roic, 1, '%')} ({len(roics)} kỳ có dữ liệu).",
            rule="Trecapital heuristic: ROIC gần nhất và trung vị 5 kỳ ≥15%.",
        )
    elif latest_roic < 10.0 and (median_roic is None or median_roic < 10.0):
        out["high_roic"] = _suggest(
            "X Không",
            CONF_HIGH if len(roics) >= 3 else CONF_MEDIUM,
            f"ROIC gần nhất {_fmt(latest_roic, 1, '%')}; trung vị tối đa 5 kỳ {_fmt(median_roic, 1, '%')}.",
            rule="Trecapital heuristic: ROIC gần nhất và trung vị 5 kỳ <10%.",
        )
    else:
        out["high_roic"] = _suggest(
            "— Chưa biết",
            CONF_MEDIUM,
            f"ROIC gần nhất {_fmt(latest_roic, 1, '%')}; trung vị tối đa 5 kỳ {_fmt(median_roic, 1, '%')}.",
            rule="ROIC nằm vùng 10–15% hoặc không đồng nhất; cần analyst đánh giá ngành/chu kỳ.",
        )

    # Low Capex: total capex is only a proxy for maintenance capex, so confidence is capped at Medium.
    revenue = _latest_metric(annual_df, "revenue_bil")
    capex = _latest_metric(annual_df, "capex_bil")
    cfo = _latest_metric(annual_df, "cfo_bil")
    capex_to_revenue = abs(capex) / revenue if capex is not None and revenue is not None and revenue > 0 else None
    fcf_to_cfo = fcf / cfo if fcf is not None and cfo is not None and cfo > 0 else None
    evidence = (
        f"Capex/Revenue {_fmt(None if capex_to_revenue is None else capex_to_revenue * 100, 1, '%')}; "
        f"FCF/CFO {_fmt(None if fcf_to_cfo is None else fcf_to_cfo * 100, 1, '%')}. "
        "Lưu ý: đây là total capex proxy, chưa tách maintenance capex."
    )
    if capex_to_revenue is None:
        out["low_capex"] = _suggest("— Chưa biết", CONF_LOW, evidence, rule="Cần Revenue và Capex; maintenance capex vẫn cần evidence định tính.")
    elif capex_to_revenue <= 0.08 and (fcf_to_cfo is None or fcf_to_cfo >= 0.70):
        out["low_capex"] = _suggest("✓ Có", CONF_MEDIUM, evidence, rule="Proxy: Capex/Revenue ≤8% và FCF/CFO ≥70% khi có CFO.")
    elif capex_to_revenue > 0.15 or (fcf_to_cfo is not None and fcf_to_cfo < 0.50):
        out["low_capex"] = _suggest("X Không", CONF_MEDIUM, evidence, rule="Proxy: Capex/Revenue >15% hoặc FCF/CFO <50%.")
    else:
        out["low_capex"] = _suggest("— Chưa biết", CONF_LOW, evidence, rule="Vùng trung gian; cần tách growth capex và maintenance capex.")

    # Strong Balance Sheet: net-cash first, then leverage/coverage guardrails.
    if net_debt is not None and net_debt <= 0:
        out["strong_balance_sheet"] = _suggest(
            "✓ Có",
            CONF_HIGH,
            f"Net debt proxy = TEV - Market Cap = {_fmt(net_debt, 0)} tỷ (net cash); Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}.",
            rule="Net cash là tín hiệu bảng cân đối mạnh; vẫn cần xem nghĩa vụ ngoài bảng cân đối ở chương sâu hơn.",
        )
    elif debt_ebitda is None:
        out["strong_balance_sheet"] = _suggest(
            "— Chưa biết", CONF_LOW, f"Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; net debt {_fmt(net_debt, 0)} tỷ.", rule="Cần debt/EBITDA hoặc bằng chứng net cash đủ tin cậy."
        )
    elif debt_ebitda <= 2.0 and (ebit_interest is None or ebit_interest >= 5.0):
        out["strong_balance_sheet"] = _suggest(
            "✓ Có", CONF_HIGH if ebit_interest is not None else CONF_MEDIUM,
            f"Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; EBIT/Interest {_fmt(ebit_interest, 1, 'x')}; net debt {_fmt(net_debt, 0)} tỷ.",
            rule="Có nếu Debt/EBITDA ≤2x và interest cover ≥5x khi có dữ liệu.",
        )
    elif debt_ebitda > 3.0 or (ebit_interest is not None and ebit_interest < 2.0):
        out["strong_balance_sheet"] = _suggest(
            "X Không", CONF_HIGH,
            f"Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; EBIT/Interest {_fmt(ebit_interest, 1, 'x')}; net debt {_fmt(net_debt, 0)} tỷ.",
            rule="Không nếu Debt/EBITDA >3x hoặc interest cover <2x.",
        )
    else:
        out["strong_balance_sheet"] = _suggest(
            "— Chưa biết", CONF_MEDIUM,
            f"Debt/EBITDA {_fmt(debt_ebitda, 1, 'x')}; EBIT/Interest {_fmt(ebit_interest, 1, 'x')}; net debt {_fmt(net_debt, 0)} tỷ.",
            rule="Vùng trung gian cần kiểm tra kỳ hạn nợ, liquidity và nghĩa vụ tiềm ẩn.",
        )

    return out


def build_chapter1_auto_data(provider: Any, annual_df: pd.DataFrame) -> dict[str, Any]:
    """Translate the existing Trecapital provider into Chapter 1 form defaults + suggestions."""
    source = provider.get_inventory_source_data(None)
    metrics = inventory_metrics(
        tev=_safe_float(getattr(source, "tev", None)),
        ebit=_safe_float(getattr(source, "ebit", None)),
        ebitda=_safe_float(getattr(source, "ebitda", None)),
        normalized_earnings=_safe_float(getattr(source, "normalized_earnings", None)),
        total_debt=_safe_float(getattr(source, "total_debt", None)),
        interest_expense=_safe_float(getattr(source, "interest_expense", None)),
        fcf_current=_safe_float(getattr(source, "fcf_current", None)),
        market_cap=_safe_float(getattr(source, "market_cap", None)),
        dividend_per_share=_safe_float(getattr(source, "dividend_per_share", None)),
        market_price=_safe_float(getattr(source, "market_price", None)),
        target_price=_safe_float(getattr(source, "target_price", None)),
    )
    mos = _safe_float(getattr(source, "mos", None))
    valuation = {
        "current_price": _safe_float(getattr(source, "market_price", None)),
        "target_price": _safe_float(getattr(source, "target_price", None)),
        "mos_pct": None if mos is None else mos * 100.0,
        "stock_price_vs_target_pct": None if metrics.get("price_vs_target") is None else metrics["price_vs_target"] * 100.0,
        "fcf_yield_pct": None if metrics.get("fcf_yield_market") is None else metrics["fcf_yield_market"] * 100.0,
        "dividend_yield_pct": None if metrics.get("dividend_yield") is None else metrics["dividend_yield"] * 100.0,
        "tev_ebit": _safe_float(metrics.get("tev_ebit")),
        "tev_ebitda": _safe_float(metrics.get("tev_ebitda")),
        "debt_ebitda": _safe_float(metrics.get("debt_ebitda")),
        "ebit_interest": _safe_float(metrics.get("ebit_interest")),
    }
    return {
        "as_of": str(getattr(source, "as_of_date", "") or ""),
        "source_module": str(getattr(source, "source_module", "") or ""),
        "source_notes": list(getattr(source, "source_notes", ()) or ()),
        "valuation": valuation,
        "quality_suggestions": build_quantitative_suggestions(source, annual_df),
    }
