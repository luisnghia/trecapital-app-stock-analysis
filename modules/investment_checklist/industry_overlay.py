from __future__ import annotations

"""Phase 3A industry/moat evidence built only from the Trecapital Data Layer."""

from dataclasses import dataclass
from typing import Any
import math

import pandas as pd

from financial_sign_policy import positive_denominator_ratio
from module1_engine import ensure_derived_metrics


FINANCIAL_TYPES = {"bank", "insurance", "securities"}


@dataclass(frozen=True)
class MetricSpec:
    label: str
    fields: tuple[str, ...]
    kind: str
    questions: tuple[str, ...]


COMMON_SPECS = (
    MetricSpec("Doanh thu", ("revenue_bil",), "money", ("Q22", "Q55")),
    MetricSpec("Biên gộp", ("gross_margin_pct",), "pct", ("Q17", "Q24")),
    MetricSpec("Biên HĐ cốt lõi", ("core_operating_margin_pct", "operating_margin_pct"), "pct", ("Q24", "Q29")),
    MetricSpec("Biên ròng", ("net_margin_pct",), "pct", ("Q24",)),
    MetricSpec("ROIC", ("roic_standard_pct", "roic_pct"), "pct", ("Q26", "Q32")),
    MetricSpec("FCF", ("free_cash_flow_bil",), "money", ("Q27", "Q32")),
    MetricSpec("CCC", ("cash_conversion_cycle_days", "ccc_days"), "days", ("Q31",)),
)

BANK_SPECS = (
    MetricSpec("ROE", ("roe_actual_pct", "roe_pct"), "pct", ("Q26",)),
    MetricSpec("ROA", ("roa_actual_pct", "roa_pct"), "pct", ("Q26",)),
    MetricSpec("NIM", ("nim_pct", "net_interest_margin_pct"), "pct", ("Q22", "Q24")),
    MetricSpec("CASA", ("casa_pct", "casa_ratio_pct"), "pct", ("Q18", "Q22")),
    MetricSpec("LDR", ("ldr_pct", "loan_to_deposit_pct"), "pct", ("Q25",)),
    MetricSpec("NPL", ("npl_pct", "npl_ratio_pct"), "pct", ("Q25", "Q27")),
    MetricSpec("Nợ nhóm 2", ("group2_debt_pct", "group_2_debt_pct"), "pct", ("Q25", "Q27")),
    MetricSpec("LLR", ("llr_pct", "loan_loss_reserve_coverage_pct"), "pct", ("Q25", "Q27")),
    MetricSpec("CAR", ("car_pct", "capital_adequacy_ratio_pct"), "pct", ("Q25",)),
    MetricSpec("CIR", ("cir_pct", "cost_to_income_pct"), "pct", ("Q24", "Q29")),
    MetricSpec("Credit cost", ("credit_cost_pct",), "pct", ("Q25", "Q27")),
    MetricSpec("Tăng trưởng tín dụng", ("loan_growth_pct", "credit_growth_pct"), "pct", ("Q22", "Q55")),
    MetricSpec("Tăng trưởng tiền gửi", ("deposit_growth_pct",), "pct", ("Q22", "Q55")),
)

INSURANCE_SPECS = (
    MetricSpec("ROE", ("roe_actual_pct", "roe_pct"), "pct", ("Q26",)),
    MetricSpec("Tăng trưởng phí BH", ("premium_growth_pct", "gross_written_premium_growth_pct"), "pct", ("Q22", "Q55")),
    MetricSpec("Loss ratio", ("loss_ratio_pct",), "pct", ("Q24", "Q25")),
    MetricSpec("Combined ratio", ("combined_ratio_pct",), "pct", ("Q24", "Q25")),
    MetricSpec("Lợi suất đầu tư", ("investment_yield_pct",), "pct", ("Q24", "Q26")),
    MetricSpec("Biên khả năng thanh toán", ("solvency_margin_pct", "solvency_ratio_pct"), "pct", ("Q25",)),
)

SECURITIES_SPECS = (
    MetricSpec("ROE", ("roe_actual_pct", "roe_pct"), "pct", ("Q26",)),
    MetricSpec("Doanh thu môi giới", ("brokerage_revenue_bil",), "money", ("Q22", "Q55")),
    MetricSpec("Biên môi giới", ("brokerage_margin_pct",), "pct", ("Q24",)),
    MetricSpec("Dư nợ margin/VCSH", ("margin_loans_to_equity", "margin_lending_to_equity"), "ratio", ("Q25",)),
    MetricSpec("Tỷ trọng tự doanh", ("proprietary_trading_share_pct",), "pct", ("Q24", "Q25")),
    MetricSpec("Tài sản thanh khoản", ("liquid_assets_to_assets_pct",), "pct", ("Q25",)),
)

DRIVER_REGISTRY = {
    "normal": (
        ("revenue_bil", "Doanh thu"), ("sales_volume", "Sản lượng"), ("average_selling_price", "Giá bán bình quân"),
        ("capacity_utilization_pct", "Công suất sử dụng"), ("customer_count", "Số khách hàng"),
    ),
    "cyclical": (
        ("sales_volume", "Sản lượng"), ("average_selling_price", "Giá bán bình quân"),
        ("commodity_spread", "Spread hàng hóa"), ("capacity_utilization_pct", "Công suất sử dụng"),
        ("revenue_bil", "Doanh thu"),
    ),
    "bank": (
        ("loan_growth_pct", "Tăng trưởng tín dụng"), ("nim_pct", "NIM"), ("casa_pct", "CASA"),
        ("npl_pct", "NPL"), ("credit_cost_pct", "Credit cost"),
    ),
    "insurance": (
        ("premium_growth_pct", "Tăng trưởng phí"), ("loss_ratio_pct", "Loss ratio"),
        ("combined_ratio_pct", "Combined ratio"), ("investment_yield_pct", "Lợi suất đầu tư"),
    ),
    "securities": (
        ("brokerage_revenue_bil", "Doanh thu môi giới"), ("margin_loans_to_equity", "Dư nợ margin/VCSH"),
        ("proprietary_trading_share_pct", "Tỷ trọng tự doanh"), ("market_share_pct", "Thị phần"),
    ),
}


def canonical_annual_df(provider) -> pd.DataFrame:
    df = getattr(provider, "annual_df", None)
    if not isinstance(df, pd.DataFrame):
        inner = getattr(provider, "inner", None)
        df = getattr(inner, "annual_df", None)
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        out = float(value)
        return None if math.isnan(out) else out
    except Exception:
        return None


def _first(row: pd.Series, fields: tuple[str, ...]) -> float | None:
    for field in fields:
        if field in row.index:
            value = _number(row.get(field))
            if value is not None:
                return value
    return None


def _period(row: pd.Series) -> str:
    value = row.get("period")
    if value is None or pd.isna(value):
        value = row.get("year")
    if value is None or pd.isna(value):
        return "—"
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else str(value)
    except Exception:
        return str(value)


def metric_specs(company_type: str) -> tuple[MetricSpec, ...]:
    kind = str(company_type or "normal").lower()
    if kind == "bank":
        return BANK_SPECS
    if kind == "insurance":
        return INSURANCE_SPECS
    if kind == "securities":
        return SECURITIES_SPECS
    return COMMON_SPECS


def build_industry_kpi_table(df: pd.DataFrame, company_type: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    kind = str(company_type or "normal").lower()
    src = df.copy() if kind in FINANCIAL_TYPES else ensure_derived_metrics(df)
    specs = metric_specs(kind)
    rows: list[dict[str, Any]] = []
    for _, row in src.tail(10).iterrows():
        out: dict[str, Any] = {"Kỳ": _period(row)}
        for spec in specs:
            out[spec.label] = _first(row, spec.fields)
        if kind not in FINANCIAL_TYPES:
            out["CFO/LNST"] = positive_denominator_ratio(row.get("cfo_bil"), row.get("net_profit_bil"))
            out["Net Debt/EBITDA"] = positive_denominator_ratio(row.get("net_debt_bil"), row.get("ebitda_bil"))
        rows.append(out)
    result = pd.DataFrame(rows)
    # Remove metrics with no canonical data at all; coverage table reports them explicitly.
    keep = ["Kỳ"] + [c for c in result.columns if c != "Kỳ" and pd.to_numeric(result[c], errors="coerce").notna().any()]
    return result[keep]


def build_metric_coverage(df: pd.DataFrame, company_type: str) -> pd.DataFrame:
    specs = metric_specs(company_type)
    rows = []
    for spec in specs:
        available_field = next(
            (field for field in spec.fields if field in df.columns and pd.to_numeric(df[field], errors="coerce").notna().any()),
            None,
        )
        rows.append({
            "KPI ngành": spec.label,
            "Trạng thái": "Có dữ liệu" if available_field else "Research gap",
            "Field hiệu lực": available_field or "—",
            "Hỗ trợ câu hỏi": ", ".join(spec.questions),
        })
    return pd.DataFrame(rows)


def build_driver_coverage(df: pd.DataFrame, company_type: str) -> pd.DataFrame:
    kind = str(company_type or "normal").lower()
    registry = DRIVER_REGISTRY.get(kind, DRIVER_REGISTRY["normal"])
    rows = []
    for field, label in registry:
        available = field in df.columns and pd.to_numeric(df[field], errors="coerce").notna().any()
        rows.append({
            "Operating driver": label,
            "Field": field,
            "Trạng thái": "Có dữ liệu" if available else "Research gap",
            "Dùng cho": "Q22, Q55–Q57",
        })
    return pd.DataFrame(rows)


QUESTION_MAP = pd.DataFrame([
    {"Cụm câu hỏi": "Q15–Q20", "Overlay": "Cấu trúc ngành, Porter forces, switching cost, pricing power", "Vai trò": "Evidence, analyst tự kết luận"},
    {"Cụm câu hỏi": "Q22–Q26", "Overlay": "Operating KPI ngành, biên lợi nhuận, bảng cân đối, ROIC/ROE", "Vai trò": "Định lượng theo ngành"},
    {"Cụm câu hỏi": "Q29–Q32", "Overlay": "Cost structure, working capital/CCC, capex và tái đầu tư", "Vai trò": "Bridge vận hành"},
    {"Cụm câu hỏi": "Q55–Q57", "Overlay": "Operating driver → EPS và tính bền vững của earnings", "Vai trò": "Phát hiện divergence"},
])


__all__ = [
    "FINANCIAL_TYPES", "QUESTION_MAP", "canonical_annual_df", "metric_specs",
    "build_industry_kpi_table", "build_metric_coverage", "build_driver_coverage",
]
