from __future__ import annotations

"""Định giá chuyên sâu: Valuation + Porter Moat Engine.

This module is intentionally deterministic and auditable.  It uses the normalized
Tổng quan doanh nghiệp financial dataframe and produces valuation tables, moat scorecards,
value-chain diagnostics and risk/scenario summaries.  It does not try to force a
single valuation method on every company; instead it classifies the company and
assigns method weights according to available data and business characteristics.

All money statement inputs are expected in billion VND.  Per-share outputs are in
VND/share.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import math
import re

import pandas as pd
import numpy as np

try:
    from module1_engine import CompanyOverview, _fmt_pct, _fmt_ratio, _fmt_money_bil
except Exception:  # pragma: no cover - keeps module importable in isolated tests
    CompanyOverview = Any  # type: ignore


DEFAULT_ASSUMPTIONS: Dict[str, Any] = {
    "required_return_pct": 13.0,
    "terminal_growth_pct": 3.0,
    "conservative_growth_pct": 0.0,
    "base_growth_cap_pct": 8.0,
    "high_growth_cap_pct": 12.0,
    "mos_conservative_pct": 50.0,
    "mos_base_pct": 30.0,
    "target_mos_pct": 50.0,
    "target_pe_default": 10.0,
    "target_pe_quality": 14.0,
    "target_pb_bank": 1.2,
    "asset_haircut_cash_pct": 0.0,
    "asset_haircut_receivables_pct": 25.0,
    "asset_haircut_inventory_pct": 50.0,
    "asset_haircut_fixed_assets_pct": 60.0,
    "min_required_years_for_high_confidence": 5,
}

FINANCIAL_KEYWORDS = ["bank", "ngân hàng", "bao hiem", "bảo hiểm", "chứng khoán", "securities", "finance", "financial"]
CYCLICAL_KEYWORDS = ["thép", "steel", "dầu", "oil", "khí", "gas", "phân bón", "fertilizer", "cao su", "rubber", "than", "coal", "bds", "bất động sản", "real estate", "shipping", "vận tải", "hàng hóa"]


@dataclass
class ClassificationResult:
    company_type: str
    confidence: float
    reasons: List[str]
    preferred_methods: List[str]


@dataclass
class ValuationRange:
    low_vnd: Optional[float]
    base_vnd: Optional[float]
    high_vnd: Optional[float]
    weighted_vnd: Optional[float]
    mos_to_weighted_pct: Optional[float]
    recommendation: str


def load_assumptions(path: str | Path | None = None) -> Dict[str, Any]:
    assumptions = dict(DEFAULT_ASSUMPTIONS)
    if path:
        p = Path(path)
        if p.exists():
            try:
                user = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(user, dict):
                    assumptions.update(user)
            except Exception:
                pass
    return assumptions


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "null", "-", "--"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _num_series(df: pd.DataFrame, col: str) -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def _safe_div(num: Any, den: Any) -> Optional[float]:
    n = _to_float(num)
    d = _to_float(den)
    if n is None or d is None or abs(d) < 1e-12:
        return None
    return n / d


def _capitalization_denominator(required_return: float, growth_rate: float) -> Optional[float]:
    """Return a valid capitalization denominator, or None when r <= g."""
    spread = required_return - growth_rate
    if spread <= 0:
        return None
    return spread


def _latest_row(df: pd.DataFrame) -> Dict[str, Any]:
    if df is None or df.empty:
        return {}
    tmp = df.copy()
    # Prefer TTM/T12M row if it exists; otherwise latest sorted row.
    if "period" in tmp.columns:
        ttm = tmp[tmp["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)]
        if not ttm.empty:
            return ttm.iloc[-1].to_dict()
    return tmp.iloc[-1].to_dict()


def _recent_median(df: pd.DataFrame, col: str, n: int = 5) -> Optional[float]:
    s = _num_series(df, col).dropna()
    if s.empty:
        return None
    return float(s.tail(n).median())


def _recent_mean(df: pd.DataFrame, col: str, n: int = 5) -> Optional[float]:
    s = _num_series(df, col).dropna()
    if s.empty:
        return None
    return float(s.tail(n).mean())


def _recent_positive_ratio(df: pd.DataFrame, col: str, n: int = 5) -> Optional[float]:
    s = _num_series(df, col).dropna().tail(n)
    if s.empty:
        return None
    return float((s > 0).mean())


def _coefficient_of_variation(df: pd.DataFrame, col: str, n: int = 7) -> Optional[float]:
    s = _num_series(df, col).dropna().tail(n)
    s = s[s.abs() > 1e-9]
    if len(s) < 3 or abs(float(s.mean())) < 1e-9:
        return None
    return float(s.std(ddof=0) / abs(s.mean()))


def _cagr(series: pd.Series, years: int = 5) -> Optional[float]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 2:
        return None
    s = s.tail(years + 1)
    start = float(s.iloc[0])
    end = float(s.iloc[-1])
    periods = len(s) - 1
    if start <= 0 or end <= 0 or periods <= 0:
        return None
    return (end / start) ** (1 / periods) - 1


def _shares_mil(company: CompanyOverview, latest: Dict[str, Any]) -> Optional[float]:
    # Prefer directly supplied shares.  If overview shares are stale/inconsistent, infer from
    # Net profit and EPS in the financial time series because many Vietnamese exports include
    # EPS but not historical shares.
    direct = _to_float(latest.get("shares_outstanding_mil"))
    inferred = None
    np_bil = _to_float(latest.get("net_profit_bil"))
    eps_vnd = _to_float(latest.get("eps_vnd"))
    if np_bil is not None and eps_vnd is not None and eps_vnd > 0:
        inferred = np_bil * 1000 / eps_vnd
    overview = _to_float(getattr(company, "shares_outstanding_mil", None))
    if direct and direct > 0:
        return direct
    if inferred and inferred > 0 and overview and overview > 0:
        # If the two values differ materially, the inferred value better matches the BCTC series.
        if abs(inferred - overview) / max(overview, 1e-9) > 0.30:
            return inferred
        return overview
    if inferred and inferred > 0:
        return inferred
    return overview if overview and overview > 0 else None


def _per_share_from_bil(value_bil: Any, shares_mil: Optional[float]) -> Optional[float]:
    v = _to_float(value_bil)
    if v is None or shares_mil is None or shares_mil <= 0:
        return None
    # billion VND / million shares = 1,000 VND/share
    return v * 1000 / shares_mil


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def classify_company(company: CompanyOverview, annual_df: pd.DataFrame) -> ClassificationResult:
    if annual_df is None or annual_df.empty:
        return ClassificationResult(
            "Chưa có dữ liệu tài chính",
            0.0,
            ["Không tìm thấy dữ liệu BCTC nhiều kỳ cho mã đang nhập trong nguồn đã chọn. Hãy chọn mã có sẵn trong file tích hợp, import dữ liệu từ Tổng quan doanh nghiệp, hoặc chạy crawler/tải dữ liệu trước khi định giá."],
            ["Chưa thể chọn phương pháp định giá"],
        )
    industry = _clean_text(f"{getattr(company, 'industry', '')} {getattr(company, 'sub_industry', '')}")
    latest = _latest_row(annual_df)
    reasons: List[str] = []
    preferred: List[str] = []
    confidence = 55.0

    if any(k in industry for k in FINANCIAL_KEYWORDS):
        reasons.append("Ngành tài chính/ngân hàng/bảo hiểm: không dùng FCF/VLĐ tổng quát làm phương pháp lõi.")
        preferred = ["P/B chuẩn hóa ROE", "Sức sinh lời", "Dividend/Book Value"]
        return ClassificationResult("Financial / Bank / Insurance", 82.0, reasons, preferred)

    roic = _recent_median(annual_df, "roic_standard_pct") or _recent_median(annual_df, "roic_pct") or _to_float(getattr(company, "roic", None))
    roe = _recent_median(annual_df, "roe_actual_pct") or _recent_median(annual_df, "roe_pct") or _to_float(getattr(company, "roe", None))
    cfo_np = _recent_median(annual_df, "cfo_to_net_profit")
    fcf_positive = _recent_positive_ratio(annual_df, "free_cash_flow_bil")
    revenue_cagr = _cagr(_num_series(annual_df, "revenue_bil"), years=5)
    profit_cv = _coefficient_of_variation(annual_df, "net_profit_bil")
    pb = _to_float(getattr(company, "pb", None))
    current_assets = _to_float(latest.get("current_assets_bil"))
    liabilities = _to_float(latest.get("liabilities_bil")) or _to_float(latest.get("current_liabilities_bil"))
    market_cap = _to_float(getattr(company, "market_cap_bil", None))

    is_cyclical = any(k in industry for k in CYCLICAL_KEYWORDS) or (profit_cv is not None and profit_cv > 0.65)
    asset_discount = False
    if pb is not None and pb < 0.8:
        asset_discount = True
    if current_assets is not None and liabilities is not None and market_cap is not None and (current_assets - liabilities) > market_cap * 0.75:
        asset_discount = True

    compounder_signals = 0
    if roic is not None and roic >= 15:
        compounder_signals += 1
        reasons.append(f"ROIC trung vị gần đây khoảng {roic:.1f}%, cho thấy khả năng sinh lời trên vốn tốt.")
    if roe is not None and roe >= 15:
        compounder_signals += 1
        reasons.append(f"ROE trung vị gần đây khoảng {roe:.1f}%, cao hơn ngưỡng chất lượng thông thường.")
    if cfo_np is not None and cfo_np >= 0.8:
        compounder_signals += 1
        reasons.append(f"CFO/LNST trung vị gần đây khoảng {cfo_np:.1f} lần, lợi nhuận có khả năng chuyển hóa thành tiền.")
    if fcf_positive is not None and fcf_positive >= 0.6:
        compounder_signals += 1
        reasons.append("FCF dương trong đa số kỳ gần đây.")
    if revenue_cagr is not None and revenue_cagr > 0.05:
        compounder_signals += 1
        reasons.append(f"Doanh thu tăng trưởng kép gần đây khoảng {revenue_cagr*100:.1f}%/năm.")

    if is_cyclical:
        reasons.append("Lợi nhuận/ngành có tính chu kỳ, cần chuẩn hóa qua chu kỳ trước khi định giá.")
        preferred = ["Sức sinh lời chuẩn hóa", "P/B", "ROCE qua chu kỳ", "Giá trị tài sản"]
        return ClassificationResult("Cyclical", 76.0, reasons, preferred)
    if asset_discount:
        reasons.append("Cổ phiếu có tín hiệu asset play: P/B thấp hoặc tài sản ngắn hạn ròng đáng kể so với vốn hóa.")
        preferred = ["NCAV/NLA", "Giá trị thanh lý", "P/B", "Sức sinh lời"]
        return ClassificationResult("Asset Play / Deep Value", 72.0, reasons, preferred)
    if compounder_signals >= 4:
        preferred = ["Owner Earnings", "Sức sinh lời", "Tỷ suất dòng tiền tự do", "Tái đầu tư theo ROIC"]
        confidence = min(92.0, 58.0 + compounder_signals * 7)
        return ClassificationResult("Quality Compounder", confidence, reasons, preferred)

    if len(annual_df) >= 4:
        confidence = 65.0
    reasons.append("Chưa đủ tín hiệu moat mạnh hoặc tài sản rẻ rõ ràng; định giá nên dùng nhiều phương pháp và tăng biên an toàn.")
    preferred = ["Sức sinh lời", "Free Cash Flow", "P/E chuẩn hóa", "P/B tham chiếu"]
    return ClassificationResult("Normal Business", confidence, reasons, preferred)


def _valuation_row(method: str, role: str, intrinsic: Optional[float], current_price: Optional[float], weight: float,
                   confidence: str, basis: str, warning: str, assumptions: Dict[str, Any]) -> Dict[str, Any]:
    raw_selected_mos = assumptions.get("target_mos_pct", assumptions.get("mos_conservative_pct", 50.0))
    selected_mos = 50.0 if raw_selected_mos is None else float(raw_selected_mos)
    valid_intrinsic = intrinsic is not None and pd.notna(intrinsic) and float(intrinsic) > 0
    mos30 = intrinsic * (1 - assumptions["mos_base_pct"] / 100) if valid_intrinsic else None
    mos50 = intrinsic * (1 - assumptions["mos_conservative_pct"] / 100) if valid_intrinsic else None
    mos_selected = intrinsic * (1 - selected_mos / 100) if valid_intrinsic else None
    mos_current = ((intrinsic - current_price) / intrinsic * 100) if valid_intrinsic and current_price is not None and current_price > 0 else None
    return {
        "Phương pháp": method,
        "Vai trò": role,
        "Giá trị nội tại/cp": intrinsic,
        "Giá mua MOS 30%": mos30,
        "Giá mua MOS 50%": mos50,
        "Giá mua MOS chọn": mos_selected,
        "MOS chọn %": selected_mos,
        "Giá hiện tại": current_price,
        "MOS hiện tại %": mos_current,
        "Chênh lệch so với MOS yêu cầu %": (mos_current - selected_mos) if mos_current is not None else None,
        "Trọng số %": weight,
        "Độ tin cậy": confidence,
        "Cơ sở tính": basis,
        "Cảnh báo": warning,
    }


def build_module2_valuation_table(company: CompanyOverview, annual_df: pd.DataFrame, assumptions: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    assumptions = dict(DEFAULT_ASSUMPTIONS if assumptions is None else assumptions)
    if annual_df is None or annual_df.empty:
        current_price = _to_float(getattr(company, "current_price", None))
        rows = [
            _valuation_row("Earnings Power / P-E chuẩn hóa", "Chưa chạy", None, current_price, 0, "Không có dữ liệu", "Cần LNST/EPS nhiều kỳ.", "Không có dữ liệu BCTC cho mã trong nguồn đã chọn.", assumptions),
            _valuation_row("Giá trị theo lợi nhuận chủ sở hữu", "Chưa chạy", None, current_price, 0, "Không có dữ liệu", "Cần CFO, capex, khấu hao, thay đổi vốn lưu động.", "Không có dữ liệu BCTC cho mã trong nguồn đã chọn.", assumptions),
            _valuation_row("Vốn hóa dòng tiền tự do", "Chưa chạy", None, current_price, 0, "Không có dữ liệu", "Cần CFO và capex.", "Không có dữ liệu BCTC cho mã trong nguồn đã chọn.", assumptions),
            _valuation_row("Book Value / P-B tham chiếu", "Chưa chạy", None, current_price, 0, "Không có dữ liệu", "Cần vốn chủ sở hữu và số cổ phiếu.", "Không có dữ liệu Bảng cân đối kế toán.", assumptions),
            _valuation_row("Net Liquid Asset / NCAV bảo thủ", "Chưa chạy", None, current_price, 0, "Không có dữ liệu", "Cần tiền, đầu tư ngắn hạn, phải thu, tồn kho, nợ phải trả.", "Không có dữ liệu Bảng cân đối kế toán.", assumptions),
        ]
        return pd.DataFrame(rows)
    cls = classify_company(company, annual_df)
    is_financial = cls.company_type == "Financial / Bank / Insurance"
    latest = _latest_row(annual_df)
    current_price = _to_float(getattr(company, "current_price", None)) or _to_float(latest.get("year_end_price"))
    shares = _shares_mil(company, latest)
    rows: List[Dict[str, Any]] = []

    net_profit_norm = _recent_median(annual_df, "net_profit_bil") or _to_float(latest.get("net_profit_bil"))
    eps_norm = _recent_median(annual_df, "eps_vnd") or _per_share_from_bil(net_profit_norm, shares) or _to_float(getattr(company, "eps", None))
    owner_earnings_norm = _recent_median(annual_df, "owner_earnings_bil") or _to_float(latest.get("owner_earnings_bil"))
    owner_earnings_per_share_norm = _recent_median(annual_df, "oeps_vnd")
    fcf_norm = _recent_median(annual_df, "free_cash_flow_bil") or _to_float(latest.get("free_cash_flow_bil"))
    bvps = _per_share_from_bil(_to_float(latest.get("equity_bil")), shares)
    revenue_cagr = _cagr(_num_series(annual_df, "revenue_bil"), years=5) or 0.0
    oe_cagr = _cagr(_num_series(annual_df, "owner_earnings_bil"), years=5)
    growth_base = min(max(oe_cagr if oe_cagr is not None else revenue_cagr, 0.0), assumptions["base_growth_cap_pct"] / 100)
    discount = assumptions["required_return_pct"] / 100
    terminal = assumptions["terminal_growth_pct"] / 100

    # Method 1: Earnings Power Value / normalized PE
    target_pe = assumptions["target_pe_quality"] if cls.company_type == "Quality Compounder" else assumptions["target_pe_default"]
    epv = eps_norm * target_pe if eps_norm is not None else None
    rows.append(_valuation_row(
        "Earnings Power / P-E chuẩn hóa",
        "Không dùng lõi" if is_financial else ("Chính" if cls.company_type in {"Normal Business", "Cyclical", "Quality Compounder"} else "Phụ"),
        epv,
        current_price,
        0 if is_financial else (25 if epv is not None else 0),
        "Thấp" if is_financial else ("Trung bình" if epv is not None else "Thấp"),
        f"EPS chuẩn hóa = LNST trung vị gần đây / CPLH; P/E mục tiêu = {target_pe:.1f} lần.",
        "Doanh nghiệp tài chính/ngân hàng ưu tiên P/B điều chỉnh theo ROE và chất lượng tài sản; P/E chỉ để tham khảo." if is_financial else "Cần loại bỏ lợi nhuận bất thường nếu dữ liệu chi tiết có sẵn.",
        assumptions,
    ))

    # Method 2: Owner Earnings Gordon-style
    oe_den = _capitalization_denominator(discount, terminal)
    if owner_earnings_per_share_norm is not None:
        oe_per_share = owner_earnings_per_share_norm
        oe_value = oe_per_share * (1 + growth_base) / oe_den if oe_den else None
    elif owner_earnings_norm is not None and shares:
        oe_per_share = _per_share_from_bil(owner_earnings_norm, shares)
        oe_value = oe_per_share * (1 + growth_base) / oe_den if oe_per_share is not None and oe_den else None
    else:
        oe_value = None
    oe_warning = "Maintenance Capex là ước tính; nếu không tách được capex duy trì/mở rộng thì cần analyst kiểm tra."
    if is_financial:
        oe_warning = "Không dùng Owner Earnings/FCF làm định giá lõi cho doanh nghiệp tài chính/ngân hàng; CFO chịu ảnh hưởng cấu trúc bảng cân đối và hoạt động huy động/cho vay."
    elif oe_den is None:
        oe_warning = "Không tính Gordon khi suất sinh lời yêu cầu <= tăng trưởng dài hạn; cần chỉnh giả định thay vì tự floor mẫu số."
    rows.append(_valuation_row(
        "Giá trị theo lợi nhuận chủ sở hữu",
        "Không phù hợp" if is_financial else ("Chính" if cls.company_type == "Quality Compounder" else "Phụ"),
        oe_value,
        current_price,
        0 if is_financial else (25 if oe_value is not None and cls.company_type == "Quality Compounder" else (15 if oe_value is not None else 0)),
        "Thấp" if is_financial else ("Cao" if oe_value is not None and len(annual_df) >= 5 else ("Trung bình" if oe_value is not None else "Thấp")),
        f"Owner Earnings/cp chuẩn hóa, tăng trưởng cơ sở {growth_base*100:.1f}%, suất sinh lời yêu cầu {discount*100:.1f}%, tăng trưởng dài hạn {terminal*100:.1f}%.",
        oe_warning,
        assumptions,
    ))

    # Method 3: FCF yield capitalization
    fcf_per_share = _per_share_from_bil(fcf_norm, shares)
    fcf_den = _capitalization_denominator(discount, assumptions["conservative_growth_pct"] / 100)
    fcf_value = fcf_per_share / fcf_den if fcf_per_share is not None and fcf_per_share > 0 and fcf_den else None
    rows.append(_valuation_row(
        "Vốn hóa dòng tiền tự do",
        "Không phù hợp" if is_financial else "Đối chiếu dòng tiền",
        fcf_value,
        current_price,
        0 if is_financial else (15 if fcf_value is not None else 0),
        "Thấp" if is_financial else ("Trung bình" if fcf_value is not None else "Thấp"),
        f"Free Cash Flow/cp chuẩn hóa vốn hóa theo suất sinh lời yêu cầu {discount*100:.1f}%.",
        "Không dùng FCF tổng quát làm định giá lõi cho ngân hàng/bảo hiểm/chứng khoán." if is_financial else ("Không phù hợp nếu FCF âm do chu kỳ đầu tư mở rộng hoặc doanh nghiệp tài chính." if fcf_den else "Không tính khi suất sinh lời yêu cầu <= tăng trưởng thận trọng."),
        assumptions,
    ))

    # Method 4: Book value / PB, especially for financials and asset plays
    pb_target = assumptions["target_pb_bank"] if cls.company_type == "Financial / Bank / Insurance" else 1.0
    pb_value = bvps * pb_target if bvps is not None else None
    rows.append(_valuation_row(
        "Book Value / P-B tham chiếu",
        "Chính" if cls.company_type in {"Financial / Bank / Insurance", "Asset Play / Deep Value"} else "Phụ",
        pb_value,
        current_price,
        70 if cls.company_type == "Financial / Bank / Insurance" and pb_value is not None else (12 if pb_value is not None else 0),
        "Trung bình" if pb_value is not None else "Thấp",
        f"BVPS x P/B mục tiêu {pb_target:.1f} lần.",
        "Với ngân hàng/tài chính cần điều chỉnh theo ROE bền vững, NPL, dự phòng, CAR và chất lượng tài sản; P/B mặc định chỉ là proxy." if is_financial else "Book value cần kiểm tra chất lượng tài sản, nợ tiềm ẩn và khoản phải thu/tồn kho.",
        assumptions,
    ))

    # Method 5a: Net Liquid Asset strict (no inventory)
    cash = _to_float(latest.get("cash_equivalents_bil")) or 0.0
    sti = _to_float(latest.get("short_term_investments_bil")) or 0.0
    receivables = _to_float(latest.get("accounts_receivable_bil")) or 0.0
    inventory = _to_float(latest.get("inventory_bil")) or 0.0
    current_assets = _to_float(latest.get("current_assets_bil")) or (cash + sti + receivables + inventory)
    current_liabilities = _to_float(latest.get("current_liabilities_bil")) or 0.0
    liabilities = _to_float(latest.get("liabilities_bil")) or current_liabilities
    liquid_bil = (
        cash * (1 - assumptions["asset_haircut_cash_pct"] / 100)
        + sti * (1 - assumptions["asset_haircut_cash_pct"] / 100)
        + receivables * (1 - assumptions["asset_haircut_receivables_pct"] / 100)
        - current_liabilities
    )
    liquid_value = _per_share_from_bil(liquid_bil, shares) if liquid_bil > 0 else None
    rows.append(_valuation_row(
        "Net Liquid Asset strict",
        "Không phù hợp" if is_financial else "Downside check",
        liquid_value,
        current_price,
        0 if is_financial else (8 if liquid_value is not None else 0),
        "Trung bình" if liquid_value is not None else "Thấp",
        "Tiền + ĐTTC ngắn hạn + phải thu sau haircut - nợ ngắn hạn. Không cộng tồn kho vào tài sản thanh khoản.",
        "Không dùng NLA/NCAV tổng quát cho ngân hàng/tài chính; cần mô hình riêng về chất lượng tài sản và nợ phải trả." if is_financial else "Đây là kiểm tra thanh khoản ngắn hạn, không phải giá trị thanh lý đầy đủ.",
        assumptions,
    ))

    # Method 5b: Adjusted NCAV / liquidation check (inventory is allowed with haircut)
    adjusted_ncav_bil = (
        cash * (1 - assumptions["asset_haircut_cash_pct"] / 100)
        + sti * (1 - assumptions["asset_haircut_cash_pct"] / 100)
        + receivables * (1 - assumptions["asset_haircut_receivables_pct"] / 100)
        + inventory * (1 - assumptions["asset_haircut_inventory_pct"] / 100)
        + max(current_assets - cash - sti - receivables - inventory, 0.0) * 0.25
        - liabilities
    )
    ncav_value = _per_share_from_bil(adjusted_ncav_bil, shares) if adjusted_ncav_bil > 0 else None
    rows.append(_valuation_row(
        "Adjusted NCAV / Liquidation check",
        "Không phù hợp" if is_financial else ("Chính" if cls.company_type == "Asset Play / Deep Value" else "Downside check"),
        ncav_value,
        current_price,
        0 if is_financial else (20 if cls.company_type == "Asset Play / Deep Value" and ncav_value is not None else (6 if ncav_value is not None else 0)),
        "Trung bình" if ncav_value is not None else "Thấp",
        "Tài sản ngắn hạn sau haircut, có tồn kho sau haircut, trừ tổng nợ phải trả.",
        "Không dùng NCAV/Liquidation tổng quát cho ngân hàng/tài chính; cần mô hình riêng về chất lượng tài sản, dự phòng và an toàn vốn." if is_financial else "Không thay thế phân tích thanh lý chi tiết; cần kiểm tra phải thu khó đòi, tồn kho chậm luân chuyển và tài sản cầm cố.",
        assumptions,
    ))

    out = pd.DataFrame(rows)
    # Re-weight only valid rows.
    valid = out["Giá trị nội tại/cp"].notna() & (pd.to_numeric(out["Giá trị nội tại/cp"], errors="coerce") > 0) & (pd.to_numeric(out["Trọng số %"], errors="coerce") > 0)
    total_weight = pd.to_numeric(out.loc[valid, "Trọng số %"], errors="coerce").sum()
    if total_weight > 0:
        out.loc[valid, "Trọng số %"] = pd.to_numeric(out.loc[valid, "Trọng số %"], errors="coerce") / total_weight * 100
    return out


def build_valuation_range(valuation_df: pd.DataFrame, current_price: Optional[float], target_mos_pct: float = 30.0) -> ValuationRange:
    if valuation_df is None or valuation_df.empty:
        return ValuationRange(None, None, None, None, None, "Chưa đủ dữ liệu")
    vals = pd.to_numeric(valuation_df.get("Giá trị nội tại/cp"), errors="coerce")
    weights = pd.to_numeric(valuation_df.get("Trọng số %"), errors="coerce").fillna(0)
    valid = vals.notna() & (vals > 0) & (weights > 0)
    if not valid.any():
        return ValuationRange(None, None, None, None, None, "Chưa đủ dữ liệu")
    weighted = float((vals[valid] * weights[valid]).sum() / weights[valid].sum())
    low = float(vals[valid].quantile(0.25))
    base = float(vals[valid].median())
    high = float(vals[valid].quantile(0.75))
    mos = ((weighted - current_price) / weighted * 100) if weighted and current_price else None
    target_mos_pct = 30.0 if target_mos_pct is None else float(target_mos_pct)
    if mos is None:
        rec = "Thiếu giá hiện tại"
    elif mos >= target_mos_pct:
        rec = f"Đạt MOS yêu cầu {target_mos_pct:.0f}% - có biên an toàn theo mức đã chọn"
    elif mos >= 50:
        rec = f"MOS hiện tại {mos:.1f}% rất cao nhưng chưa đạt MOS yêu cầu {target_mos_pct:.0f}%"
    elif mos >= 30:
        rec = f"Có biên an toàn đáng chú ý nhưng chưa đạt MOS yêu cầu {target_mos_pct:.0f}%"
    elif mos >= 10:
        rec = f"Gần vùng hợp lý nhưng chưa đạt MOS yêu cầu {target_mos_pct:.0f}%"
    elif mos >= 0:
        rec = f"Biên an toàn mỏng, chưa đạt MOS yêu cầu {target_mos_pct:.0f}%"
    else:
        rec = "Đắt hơn giá trị nội tại ước tính"
    return ValuationRange(low, base, high, weighted, mos, rec)


def _score_between(value: Optional[float], good: float, ok: float, weight: float, reverse: bool = False) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return weight * 0.35
    v = value
    if reverse:
        if v <= good:
            return weight
        if v <= ok:
            return weight * 0.65
        return weight * 0.25
    if v >= good:
        return weight
    if v >= ok:
        return weight * 0.65
    return weight * 0.25


def build_porter_moat_scorecard(company: CompanyOverview, annual_df: pd.DataFrame) -> pd.DataFrame:
    if annual_df is None or annual_df.empty:
        rows = [
            {"Nhóm Porter/Moat": "Hiệu quả vốn / ROIC", "Trọng số %": 20, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần ROIC/ROE nhiều kỳ để đánh giá moat.", "Bằng chứng định lượng cần xem": "ROIC, ROE, ROCE, ROIC-WACC spread"},
            {"Nhóm Porter/Moat": "Cost advantage", "Trọng số %": 15, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần biên gộp, SG&A/doanh thu, vòng quay tài sản, CCC.", "Bằng chứng định lượng cần xem": "Biên gộp, SG&A/Doanh thu, vòng quay tài sản, CCC"},
            {"Nhóm Porter/Moat": "Differentiation / Pricing power", "Trọng số %": 15, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần biên gộp/biên ròng và bằng chứng định tính từ BCTN/tin IR.", "Bằng chứng định lượng cần xem": "Biên gộp, biên EBIT, thị phần, thương hiệu"},
            {"Nhóm Porter/Moat": "Cấu trúc ngành & chu kỳ", "Trọng số %": 15, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần lịch sử lợi nhuận và nợ vay để nhận diện chu kỳ/rủi ro.", "Bằng chứng định lượng cần xem": "Độ biến động LNST, nợ vay/EBITDA"},
            {"Nhóm Porter/Moat": "Chất lượng dòng tiền", "Trọng số %": 15, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần CFO/LNST, FCF/LNST để kiểm tra lợi nhuận có chuyển hóa thành tiền không.", "Bằng chứng định lượng cần xem": "CFO/LNST, FCF/LNST, capex, VLĐ"},
            {"Nhóm Porter/Moat": "Khả năng tái đầu tư", "Trọng số %": 10, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần tăng trưởng doanh thu/LNST và ROIC duy trì.", "Bằng chứng định lượng cần xem": "Tăng trưởng, vốn đầu tư, incremental ROIC"},
            {"Nhóm Porter/Moat": "Chuỗi giá trị vận hành", "Trọng số %": 10, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần DIO, DSO, DPO, CCC để đánh giá vận hành.", "Bằng chứng định lượng cần xem": "DIO, DSO, DPO, CCC"},
            {"Nhóm Porter/Moat": "Quản trị vốn & an toàn tài chính", "Trọng số %": 10, "Điểm đạt": 0.0, "Tín hiệu": "Chưa có dữ liệu", "Diễn giải": "Cần nợ vay, lãi vay, cổ tức/buyback/M&A.", "Bằng chứng định lượng cần xem": "Nợ vay, interest coverage, cổ tức, buyback"},
        ]
        out = pd.DataFrame(rows)
        out.attrs["total_score"] = 0.0
        out.attrs["level"] = "Chưa đủ dữ liệu"
        return out
    latest = _latest_row(annual_df)
    roic = _recent_median(annual_df, "roic_standard_pct") or _recent_median(annual_df, "roic_pct") or _to_float(getattr(company, "roic", None))
    roe = _recent_median(annual_df, "roe_actual_pct") or _recent_median(annual_df, "roe_pct") or _to_float(getattr(company, "roe", None))
    gross_margin = _recent_median(annual_df, "gross_margin_pct")
    net_margin = _recent_median(annual_df, "net_margin_pct")
    sgna = None
    rev = _recent_median(annual_df, "revenue_bil")
    if rev and rev > 0:
        selling = _recent_median(annual_df, "selling_expense_bil") or 0
        admin = _recent_median(annual_df, "admin_expense_bil") or 0
        sgna = (abs(selling) + abs(admin)) / rev * 100
    cfo_np = _recent_median(annual_df, "cfo_to_net_profit")
    fcf_np = _recent_median(annual_df, "fcf_to_net_profit")
    revenue_cagr = _cagr(_num_series(annual_df, "revenue_bil"), years=5)
    profit_cv = _coefficient_of_variation(annual_df, "net_profit_bil")
    debt_ebitda = _to_float(latest.get("net_debt_to_ebitda"))
    interest_coverage = _to_float(latest.get("interest_coverage"))
    inventory_turnover = _recent_median(annual_df, "inventory_turnover")
    dso = _recent_median(annual_df, "dso_days")
    ccc = _recent_median(annual_df, "cash_conversion_cycle_days")

    rows: List[Dict[str, Any]] = []
    def add(group: str, weight: float, score: float, signal: str, note: str, evidence: str) -> None:
        capped = round(max(0, min(score, weight)), 1)
        rows.append({
            "Nhóm Porter/Moat": group,
            "Trọng số %": weight,
            "Điểm đạt": capped,
            "Tỷ lệ đạt %": round(capped / weight * 100, 1) if weight else 0.0,
            "Tín hiệu": signal,
            "Diễn giải": note,
            "Bằng chứng định lượng cần xem": evidence,
        })

    eff_score = _score_between(roic, 15, 10, 20) * 0.7 + _score_between(roe, 15, 10, 20) * 0.3
    add("Hiệu quả vốn / ROIC", 20, eff_score, "Mạnh" if eff_score >= 15 else "Trung bình/yếu", "ROIC/ROE cao và bền vững là dấu hiệu moat nhưng phải đối chiếu chu kỳ ngành.", "ROIC, ROE, ROCE, ROIC-WACC spread")

    cost_weight = 12.5
    cost_score = _score_between(gross_margin, 25, 15, 6.5) + _score_between(sgna, 10, 18, 6.0, reverse=True)
    add("Cost advantage", cost_weight, cost_score, "Tốt" if cost_score >= cost_weight * 0.73 else "Cần kiểm chứng", "Nếu biên gộp tốt và chi phí bán hàng+QLDN/doanh thu thấp, doanh nghiệp có thể có quy mô, vận hành hoặc logistics tốt.", "Biên gộp, SG&A/Doanh thu, vòng quay tài sản, CCC")

    diff_weight = 12.5
    diff_score = _score_between(gross_margin, 30, 18, 6.5) + _score_between(net_margin, 12, 6, 6.0)
    add("Differentiation / Pricing power", diff_weight, diff_score, "Tốt" if diff_score >= diff_weight * 0.73 else "Chưa rõ", "Biên gộp và biên ròng cao bền vững có thể phản ánh thương hiệu, chất lượng sản phẩm, mạng lưới phân phối hoặc switching cost.", "Biên gộp, biên EBIT, thị phần, giá bán bình quân, thương hiệu")

    industry_score = _score_between(profit_cv, 0.35, 0.65, 8, reverse=True) + _score_between(debt_ebitda, 1.5, 3.0, 7, reverse=True)
    add("Cấu trúc ngành & chu kỳ", 15, industry_score, "Ổn định" if industry_score >= 11 else "Rủi ro chu kỳ", "Lợi nhuận ít biến động và đòn bẩy thấp giúp moat bền hơn qua chu kỳ.", "Độ biến động LNST, nợ vay/EBITDA, rào cản gia nhập, thay thế")

    cash_score = _score_between(cfo_np, 1.0, 0.75, 8) + _score_between(fcf_np, 0.6, 0.2, 7)
    add("Chất lượng dòng tiền", 15, cash_score, "Tốt" if cash_score >= 11 else "Cần kiểm tra", "Doanh nghiệp tốt phải chuyển lợi nhuận thành tiền; FCF yếu kéo dài làm giảm độ tin cậy định giá.", "CFO/LNST, FCF/LNST, capex, thay đổi vốn lưu động")

    reinvest_score = _score_between(revenue_cagr * 100 if revenue_cagr is not None else None, 8, 3, 6) + _score_between(roic, 15, 10, 4)
    add("Khả năng tái đầu tư", 10, reinvest_score, "Có runway" if reinvest_score >= 7 else "Hạn chế", "Compounder cần vừa tăng trưởng vừa duy trì ROIC; tăng trưởng bằng nợ hoặc giảm ROIC là tín hiệu yếu.", "Tăng trưởng doanh thu/LNST, tăng vốn đầu tư, incremental ROIC")

    working_weight = 8.0
    working_score = _score_between(inventory_turnover, 4, 2, 3.0) + _score_between(dso, 60, 100, 2.5, reverse=True) + _score_between(ccc, 60, 120, 2.5, reverse=True)
    add("Chuỗi giá trị vận hành", working_weight, working_score, "Hiệu quả" if working_score >= working_weight * 0.70 else "Cần soi VLĐ", "Vận hành tốt thường thể hiện qua tồn kho, phải thu và chu kỳ chuyển đổi tiền mặt.", "DIO, DSO, DPO, CCC, vòng quay hàng tồn kho")

    governance_weight = 7.0
    governance_score = _score_between(interest_coverage, 5, 2, 3.5) + _score_between(debt_ebitda, 1.5, 3.0, 3.5, reverse=True)
    add("Quản trị vốn & an toàn tài chính", governance_weight, governance_score, "An toàn" if governance_score >= governance_weight * 0.70 else "Rủi ro", "Phân bổ vốn tốt thể hiện ở đòn bẩy hợp lý, khả năng trả lãi, cổ tức/buyback không làm yếu bảng cân đối.", "Nợ vay, interest coverage, cổ tức, buyback, M&A, giao dịch liên quan")

    out = pd.DataFrame(rows)
    total_weight = pd.to_numeric(out["Trọng số %"], errors="coerce").sum()
    raw_total = pd.to_numeric(out["Điểm đạt"], errors="coerce").sum()
    total = raw_total / total_weight * 100 if total_weight > 0 else 0.0
    level = "Lợi thế mạnh" if total >= 80 else "Lợi thế khá" if total >= 60 else "Lợi thế trung bình" if total >= 40 else "Lợi thế yếu/chưa rõ"
    out.attrs["raw_score"] = round(float(raw_total), 1)
    out.attrs["total_weight"] = round(float(total_weight), 1)
    out.attrs["total_score"] = round(float(total), 1)
    out.attrs["level"] = level
    return out


def build_value_chain_table(company: CompanyOverview, annual_df: pd.DataFrame) -> pd.DataFrame:
    """Build Porter value-chain table with heatmap fields.

    V23.16: table now includes `Điểm nhiệt` and `Mức độ` so the dashboard can show heatmap colors for
    each activity, not only text.
    """
    if annual_df is None or annual_df.empty:
        rows = [
            ["Logistics đầu vào", "Cần BCTC/BCTN và dữ liệu tồn kho/nhà cung cấp", "Chưa có dữ liệu", "Cost advantage", "Chưa tìm thấy dữ liệu tài chính cho mã đang nhập."],
            ["Vận hành/sản xuất", "Cần biên gộp, công suất, định mức chi phí", "Chưa có dữ liệu", "Cost + Differentiation", "Chưa tìm thấy dữ liệu tài chính cho mã đang nhập."],
            ["Logistics đầu ra", "Cần CCC, DSO, kênh phân phối", "Chưa có dữ liệu", "Cost advantage", "Chưa tìm thấy dữ liệu tài chính cho mã đang nhập."],
            ["Marketing & bán hàng", "Cần SG&A/doanh thu, thương hiệu, thị phần", "Chưa có dữ liệu", "Differentiation", "Chưa tìm thấy dữ liệu tài chính cho mã đang nhập."],
            ["Dịch vụ sau bán hàng", "Cần tài liệu doanh nghiệp/tin công bố", "Chưa có dữ liệu", "Differentiation", "Chạy Bằng chứng định tính hoặc import BCTN."],
            ["Công nghệ/R&D", "Cần tài liệu doanh nghiệp/tin công bố", "Chưa có dữ liệu", "Differentiation + Cost", "Chạy Bằng chứng định tính hoặc import BCTN."],
            ["Nhân sự", "Cần dữ liệu nhân sự/năng suất lao động", "Chưa có dữ liệu", "Support activity", "Chạy Bằng chứng định tính hoặc import BCTN."],
            ["Hạ tầng quản trị", "Cần ROIC, nợ vay, giao dịch liên quan", "Chưa có dữ liệu", "Sustainability", "Chưa tìm thấy dữ liệu tài chính cho mã đang nhập."],
        ]
    else:
        gross_margin = _recent_median(annual_df, "gross_margin_pct")
        sgna_to_rev = None
        rev = _recent_median(annual_df, "revenue_bil")
        if rev and rev > 0:
            sgna_to_rev = ((abs(_recent_median(annual_df, "selling_expense_bil") or 0) + abs(_recent_median(annual_df, "admin_expense_bil") or 0)) / rev * 100)
        ccc = _recent_median(annual_df, "cash_conversion_cycle_days")
        inventory_turnover = _recent_median(annual_df, "inventory_turnover")
        roic = _recent_median(annual_df, "roic_standard_pct") or _recent_median(annual_df, "roic_pct")
        cfo_np = _recent_median(annual_df, "cfo_to_net_profit")

        def score(v: Optional[float], good: float, ok: float, reverse: bool = False) -> str:
            if v is None:
                return "Chưa đủ dữ liệu"
            if reverse:
                return "Tốt" if v <= good else "Trung bình" if v <= ok else "Yếu"
            return "Tốt" if v >= good else "Trung bình" if v >= ok else "Yếu"

        rows = [
            ["Logistics đầu vào", "Mua nguyên liệu, tồn kho, điều kiện thanh toán nhà cung cấp", score(inventory_turnover, 4, 2), "Cost advantage", f"Vòng quay HTK: {inventory_turnover:.1f} lần" if inventory_turnover is not None else "Thiếu vòng quay HTK"],
            ["Vận hành/sản xuất", "Năng suất, quy mô nhà máy, định mức chi phí, khấu hao", score(gross_margin, 25, 15), "Cost + Differentiation", f"Biên gộp trung vị: {gross_margin:.1f}%" if gross_margin is not None else "Thiếu biên gộp"],
            ["Logistics đầu ra", "Phân phối, giao hàng, tồn kho thành phẩm, thu tiền", score(ccc, 60, 120, reverse=True), "Cost advantage", f"CCC trung vị: {ccc:.0f} ngày" if ccc is not None else "Thiếu CCC"],
            ["Marketing & bán hàng", "Thương hiệu, kênh bán hàng, chi phí bán hàng/doanh thu", score(sgna_to_rev, 10, 18, reverse=True), "Differentiation", f"SG&A/DT trung vị: {sgna_to_rev:.1f}%" if sgna_to_rev is not None else "Thiếu SG&A/DT"],
            ["Dịch vụ sau bán hàng", "Bảo hành, chăm sóc khách hàng, tần suất mua lại", "Cần bổ sung bằng chứng", "Differentiation", "Tìm trong BCTN/tin IR: chất lượng dịch vụ, khách hàng lặp lại, khiếu nại"],
            ["Công nghệ/R&D", "Công nghệ, sáng chế, tiêu chuẩn chất lượng, tự động hóa", "Cần bổ sung bằng chứng", "Differentiation + Cost", "Tìm trong BCTN: R&D, CAPEX công nghệ, chứng chỉ, năng suất"],
            ["Nhân sự", "Đào tạo, văn hóa bán hàng/vận hành, giữ người", "Cần bổ sung bằng chứng", "Support activity", "Tìm trong BCTN: năng suất lao động, chính sách nhân sự, biến động nhân sự"],
            ["Hạ tầng quản trị", "Phân bổ vốn, kiểm soát rủi ro, minh bạch, quan hệ cổ đông", score(roic, 15, 10), "Sustainability", f"ROIC trung vị: {roic:.1f}% | CFO/LNST: {cfo_np:.1f}x" if roic is not None and cfo_np is not None else "Cần soi ROIC, CFO/LNST, nợ vay, giao dịch liên quan"],
        ]
    df = pd.DataFrame(rows, columns=["Hoạt động chuỗi giá trị", "Cần phân tích", "Đánh giá sơ bộ", "Loại lợi thế", "Bằng chứng hiện có/cần tìm"])
    score_map = {"Tốt": 100, "Trung bình": 55, "Yếu": 15, "Chưa đủ dữ liệu": 35, "Cần bổ sung bằng chứng": 35}
    level_map = {"Tốt": "Tốt", "Trung bình": "Theo dõi", "Yếu": "Cảnh báo", "Chưa đủ dữ liệu": "Theo dõi", "Cần bổ sung bằng chứng": "Theo dõi"}
    df["Điểm nhiệt"] = df["Đánh giá sơ bộ"].map(score_map).fillna(35).astype(float)
    df["Mức độ"] = df["Đánh giá sơ bộ"].map(level_map).fillna("Theo dõi")
    return df

def build_risk_scenario_table(company: CompanyOverview, annual_df: pd.DataFrame, valuation_range: ValuationRange) -> pd.DataFrame:
    latest = _latest_row(annual_df)
    profit_cv = _coefficient_of_variation(annual_df, "net_profit_bil")
    debt_ebitda = _to_float(latest.get("net_debt_to_ebitda"))
    fcf_np = _recent_median(annual_df, "fcf_to_net_profit")
    rows = []
    def add(scenario: str, value: Optional[float], mos: Optional[float], key_assumption: str, risk: str) -> None:
        rows.append({"Kịch bản": scenario, "Giá trị/cp": value, "MOS so với giá hiện tại %": mos, "Giả định chính": key_assumption, "Rủi ro cần kiểm tra": risk})
    current_price = _to_float(getattr(company, "current_price", None))
    for scenario, value, desc in [
        ("Bear", valuation_range.low_vnd, "Dùng phần thấp của dải định giá, tăng haircut tài sản/giảm tăng trưởng."),
        ("Base", valuation_range.weighted_vnd, "Dùng trung bình trọng số các phương pháp phù hợp."),
        ("Bull", valuation_range.high_vnd, "Dùng phần cao của dải định giá khi moat và tái đầu tư được xác nhận."),
    ]:
        mos = ((value - current_price) / value * 100) if value is not None and value > 0 and current_price is not None and current_price > 0 else None
        risk = []
        if profit_cv is not None and profit_cv > 0.65:
            risk.append("lợi nhuận biến động chu kỳ")
        if debt_ebitda is not None and debt_ebitda > 3:
            risk.append("đòn bẩy cao")
        if fcf_np is not None and fcf_np < 0.2:
            risk.append("FCF yếu so với LNST")
        add(scenario, value, mos, desc, "; ".join(risk) if risk else "Chưa có cảnh báo lớn từ dữ liệu định lượng")
    return pd.DataFrame(rows)



# ===== V23.51: Beneish M-Score - cảnh báo thao túng lợi nhuận/tài chính =====
BENEISH_SOURCE_NOTE = (
    "Beneish M-Score 8 biến: DSRI, GMI, AQI, SGI, DEPI, SGAI, TATA, LVGI. "
    "M-Score > -2.22 được gắn cờ rủi ro thao túng lợi nhuận. Đây là mô hình cảnh báo, "
    "không phải kết luận pháp lý về gian lận."
)


def _first_available(row: Dict[str, Any], *cols: str) -> Optional[float]:
    for col in cols:
        val = _to_float(row.get(col))
        if val is not None:
            return val
    return None


def _row_sum(row: Dict[str, Any], *cols: str, abs_value: bool = False) -> Optional[float]:
    vals = []
    for col in cols:
        val = _to_float(row.get(col))
        if val is not None:
            vals.append(abs(val) if abs_value else val)
    return sum(vals) if vals else None


def _beneish_input_rows(annual_df: pd.DataFrame) -> pd.DataFrame:
    """Return annual rows sorted ascending and excluding TTM/T12M rows."""
    if annual_df is None or annual_df.empty:
        return pd.DataFrame()
    df = annual_df.copy()
    if "period" in df.columns:
        mask_ttm = df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)
        df = df.loc[~mask_ttm].copy()
    if "period_type" in df.columns:
        # Module 2 feeds annual_df, but keep this guard to avoid quarterly data accidentally entering M-Score.
        mask_year = df["period_type"].astype(str).str.upper().isin(["Y", "A", "YEAR", "ANNUAL", "", "NAN"])
        if mask_year.any():
            df = df.loc[mask_year].copy()
    if "year" in df.columns:
        df["_sort_year"] = pd.to_numeric(df["year"], errors="coerce")
    else:
        df["_sort_year"] = pd.to_numeric(df.get("period", pd.Series(index=df.index)), errors="coerce")
    df = df.sort_values(["_sort_year", "period" if "period" in df.columns else "_sort_year"]).drop(columns=["_sort_year"], errors="ignore")
    return df.reset_index(drop=True)


def _beneish_required_status(row_t: Dict[str, Any], row_p: Dict[str, Any]) -> tuple[bool, List[str]]:
    missing: List[str] = []
    for label, cols in {
        "Doanh thu": ["revenue_bil", "gross_revenue_bil"],
        "Phải thu": ["accounts_receivable_bil"],
        "Lợi nhuận gộp hoặc giá vốn": ["gross_profit_bil", "cost_of_goods_sold_bil"],
        "Tài sản ngắn hạn": ["current_assets_bil", "short_term_assets_bil"],
        "TSCĐ/tài sản dài hạn": ["ppe_bil", "net_ppe_bil", "property_plant_equipment_bil", "fixed_assets_net_bil", "tangible_fixed_assets_bil", "fixed_assets_bil", "long_term_assets_bil", "non_current_assets_bil"],
        "Tổng tài sản": ["total_assets_bil", "assets_bil"],
        "Khấu hao/phi tiền mặt": ["depreciation_bil", "noncash_adjustments_bil"],
        "Chi phí bán hàng/quản lý": ["selling_expense_bil", "admin_expense_bil", "operating_profit_bil", "pretax_profit_bil"],
        "Nợ phải trả/nợ vay": ["liabilities_bil", "current_liabilities_bil", "interest_bearing_debt_bil", "long_term_debt_bil"],
        "CFO và LNST": ["cfo_bil", "net_profit_bil"],
    }.items():
        ok_t = any(_to_float(row_t.get(c)) is not None for c in cols)
        ok_p = any(_to_float(row_p.get(c)) is not None for c in cols)
        if not (ok_t and ok_p):
            missing.append(label)
    return len(missing) == 0, missing


def _gross_margin_from_row(row: Dict[str, Any]) -> Optional[float]:
    sales = _first_available(row, "revenue_bil", "gross_revenue_bil")
    gross_profit = _to_float(row.get("gross_profit_bil"))
    if sales is not None and sales != 0 and gross_profit is not None:
        return gross_profit / sales
    gm_pct = _to_float(row.get("gross_margin_pct"))
    if gm_pct is not None:
        return gm_pct / 100
    cogs = _to_float(row.get("cost_of_goods_sold_bil"))
    if sales is not None and sales != 0 and cogs is not None:
        return (sales - abs(cogs)) / sales
    return None


def _cogs_from_row(row: Dict[str, Any]) -> Optional[float]:
    cogs = _to_float(row.get("cost_of_goods_sold_bil"))
    if cogs is not None:
        return abs(cogs)
    sales = _first_available(row, "revenue_bil", "gross_revenue_bil")
    gross_profit = _to_float(row.get("gross_profit_bil"))
    if sales is not None and gross_profit is not None:
        return max(sales - gross_profit, 0.0)
    return None



def _sga_from_row(row: Dict[str, Any]) -> tuple[Optional[float], str]:
    """Return SG&A amount and method used.

    Priority: explicit selling + admin expense; then gross profit - operating profit;
    then gross profit - pretax profit as a conservative proxy when data source lacks SG&A detail.
    """
    explicit = _row_sum(row, "selling_expense_bil", "admin_expense_bil", abs_value=True)
    if explicit is not None:
        return explicit, "explicit"
    gp = _to_float(row.get("gross_profit_bil"))
    op = _first_available(row, "operating_profit_bil", "core_operating_profit_bil")
    if gp is not None and op is not None:
        return max(gp - op, 0.0), "proxy: gross profit - operating profit"
    pretax = _to_float(row.get("pretax_profit_bil"))
    if gp is not None and pretax is not None:
        return max(gp - pretax, 0.0), "proxy: gross profit - pretax profit"
    return None, "missing"

def _total_debt_like_from_row(row: Dict[str, Any]) -> Optional[float]:
    direct = _first_available(row, "liabilities_bil")
    if direct is not None:
        return direct
    parts = _row_sum(
        row,
        "current_liabilities_bil",
        "long_term_debt_bil",
        "bonds_payable_bil",
        "lease_liabilities_bil",
        "finance_lease_liabilities_bil",
        abs_value=True,
    )
    if parts is not None:
        return parts
    return _row_sum(row, "short_term_debt_bil", "current_portion_long_term_debt_bil", "long_term_debt_bil", "bonds_payable_bil", abs_value=True)


def _relative_close(a: Optional[float], b: Optional[float], tolerance: float = 0.03) -> bool:
    if a is None or b is None or abs(b) < 1e-12:
        return False
    return abs(a - b) / abs(b) <= tolerance


def _aqi_component_from_row(row: Dict[str, Any]) -> tuple[Optional[float], str]:
    """Return the Beneish AQI component and the data method used.

    Beneish AQI normally uses:
        1 - (Current Assets + PP&E) / Total Assets

    Vietnamese data providers sometimes expose only the whole long-term asset block
    under labels similar to "TSCĐ/tài sản dài hạn". If Current Assets + that field is
    approximately Total Assets, treating it as PP&E makes the AQI denominator zero.
    In that case, we compute a transparent proxy using the non-current-assets ratio:
        (Total Assets - Current Assets) / Total Assets
    and disclose that method in the output.
    """
    ca = _first_available(row, "current_assets_bil", "short_term_assets_bil")
    ta = _first_available(row, "total_assets_bil", "assets_bil")
    if ca is None or ta is None or abs(ta) < 1e-12:
        return None, "missing current assets/total assets"

    # Prefer explicit PP&E/TSCĐ aliases if any future adapter provides them.
    ppe_true = _first_available(
        row,
        "ppe_bil",
        "net_ppe_bil",
        "property_plant_equipment_bil",
        "fixed_assets_net_bil",
        "tangible_fixed_assets_bil",
        "tangible_assets_bil",
    )
    if ppe_true is not None:
        comp = 1 - (ca + ppe_true) / ta
        return comp, "AQI chuẩn: current assets + PP&E/TSCĐ"

    fixed_or_long_term = _first_available(row, "fixed_assets_bil", "long_term_assets_bil", "non_current_assets_bil")
    if fixed_or_long_term is not None:
        if _relative_close(ca + fixed_or_long_term, ta, 0.05):
            # fixed_assets_bil is actually the non-current asset block, not pure PP&E.
            comp = (ta - ca) / ta
            return comp, "AQI proxy: nguồn chỉ có Tài sản dài hạn, dùng Tài sản dài hạn/Tổng tài sản"
        comp = 1 - (ca + fixed_or_long_term) / ta
        return comp, "AQI gần chuẩn: dùng fixed_assets_bil như PP&E/TSCĐ"

    # Last-resort proxy from total and current assets.
    comp = (ta - ca) / ta
    return comp, "AQI proxy: suy ra Tài sản dài hạn = Tổng tài sản - Tài sản ngắn hạn"


def _period_name(row: Dict[str, Any]) -> str:
    return str(row.get("period") or row.get("year") or "N/A")


def _risk_from_mscore(mscore: Optional[float], missing: List[str]) -> tuple[str, str, float]:
    if mscore is None:
        return "Thiếu dữ liệu", "Không đủ dữ liệu để kết luận", 35.0
    if missing:
        return "Cần kiểm chứng", "M-Score tính được nhưng thiếu một số biến gốc; cần đọc BCTC/thuyết minh", 55.0
    if mscore > -1.78:
        return "Rủi ro rất cao", "M-Score vượt xa ngưỡng -2.22; cần kiểm tra doanh thu, accruals, nợ và ước tính kế toán", 92.0
    if mscore > -2.22:
        return "Rủi ro cao", "M-Score lớn hơn -2.22; mô hình gắn cờ khả năng thao túng lợi nhuận", 80.0
    if mscore > -2.70:
        return "Theo dõi", "M-Score dưới ngưỡng nhưng gần vùng cảnh báo", 55.0
    return "Thấp", "M-Score an toàn hơn ngưỡng -2.22 theo mô hình Beneish", 25.0


def build_beneish_mscore_table(company: CompanyOverview, annual_df: pd.DataFrame) -> pd.DataFrame:
    """Build Beneish M-Score table for non-financial companies using annual BCTC data.

    Inputs are expected in billion VND. The function computes one M-Score for each pair of
    consecutive annual rows. Missing variables are carried as None and disclosed in the table.
    """
    df = _beneish_input_rows(annual_df)
    if df.empty or len(df) < 2:
        out = pd.DataFrame([{ 
            "Kỳ": "N/A",
            "M-Score": None,
            "Mức cảnh báo": "Thiếu dữ liệu",
            "Tín hiệu": "Cần tối thiểu 2 năm BCTC để tính Beneish M-Score",
            "Biến thiếu/cần kiểm tra": "Cần dữ liệu 2 năm liên tiếp",
            "DSRI": None, "GMI": None, "AQI": None, "SGI": None, "DEPI": None, "SGAI": None, "TATA": None, "LVGI": None,
            "Nguồn/logic": BENEISH_SOURCE_NOTE,
        }])
        out.attrs["latest_score"] = None
        out.attrs["latest_risk"] = "Thiếu dữ liệu"
        out.attrs["latest_note"] = "Cần tối thiểu 2 năm dữ liệu BCTC năm."
        return out

    rows: List[Dict[str, Any]] = []
    for idx in range(1, len(df)):
        prev = df.iloc[idx - 1].to_dict()
        cur = df.iloc[idx].to_dict()
        missing: List[str] = []
        complete, base_missing = _beneish_required_status(cur, prev)
        missing.extend(base_missing)

        sales_t = _first_available(cur, "revenue_bil", "gross_revenue_bil")
        sales_p = _first_available(prev, "revenue_bil", "gross_revenue_bil")
        ar_t = _to_float(cur.get("accounts_receivable_bil"))
        ar_p = _to_float(prev.get("accounts_receivable_bil"))
        dsri = _safe_div(_safe_div(ar_t, sales_t), _safe_div(ar_p, sales_p))

        gm_t = _gross_margin_from_row(cur)
        gm_p = _gross_margin_from_row(prev)
        gmi = _safe_div(gm_p, gm_t)

        ca_t = _first_available(cur, "current_assets_bil", "short_term_assets_bil")
        ca_p = _first_available(prev, "current_assets_bil", "short_term_assets_bil")
        ppe_t = _first_available(cur, "ppe_bil", "net_ppe_bil", "property_plant_equipment_bil", "fixed_assets_net_bil", "tangible_fixed_assets_bil", "fixed_assets_bil", "long_term_assets_bil", "non_current_assets_bil")
        ppe_p = _first_available(prev, "ppe_bil", "net_ppe_bil", "property_plant_equipment_bil", "fixed_assets_net_bil", "tangible_fixed_assets_bil", "fixed_assets_bil", "long_term_assets_bil", "non_current_assets_bil")
        ta_t = _first_available(cur, "total_assets_bil", "assets_bil")
        ta_p = _first_available(prev, "total_assets_bil", "assets_bil")
        aqi_t, aqi_method_t = _aqi_component_from_row(cur)
        aqi_p, aqi_method_p = _aqi_component_from_row(prev)
        aqi = _safe_div(aqi_t, aqi_p)

        sgi = _safe_div(sales_t, sales_p)

        dep_t = _first_available(cur, "depreciation_bil", "noncash_adjustments_bil")
        dep_p = _first_available(prev, "depreciation_bil", "noncash_adjustments_bil")
        dep_t = abs(dep_t) if dep_t is not None else None
        dep_p = abs(dep_p) if dep_p is not None else None
        dep_rate_t = _safe_div(dep_t, (dep_t or 0) + (ppe_t or 0)) if (dep_t is not None or ppe_t is not None) else None
        dep_rate_p = _safe_div(dep_p, (dep_p or 0) + (ppe_p or 0)) if (dep_p is not None or ppe_p is not None) else None
        depi = _safe_div(dep_rate_p, dep_rate_t)

        sga_t, sga_method_t = _sga_from_row(cur)
        sga_p, sga_method_p = _sga_from_row(prev)
        sgai = _safe_div(_safe_div(sga_t, sales_t), _safe_div(sga_p, sales_p))

        debt_t = _total_debt_like_from_row(cur)
        debt_p = _total_debt_like_from_row(prev)
        lvgi = _safe_div(_safe_div(debt_t, ta_t), _safe_div(debt_p, ta_p))

        accruals_t, tata_method = _balance_sheet_total_accruals(cur, prev)
        tata = _safe_div(accruals_t, ta_t)

        variable_map = {
            "DSRI": dsri, "GMI": gmi, "AQI": aqi, "SGI": sgi, "DEPI": depi, "SGAI": sgai, "TATA": tata, "LVGI": lvgi,
        }
        for key, val in variable_map.items():
            if val is None or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
                missing.append(key)

        if all(v is not None and not (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) for v in variable_map.values()):
            mscore = (
                -4.84
                + 0.920 * float(dsri)
                + 0.528 * float(gmi)
                + 0.404 * float(aqi)
                + 0.892 * float(sgi)
                + 0.115 * float(depi)
                - 0.172 * float(sgai)
                + 4.679 * float(tata)
                - 0.327 * float(lvgi)
            )
        else:
            mscore = None
        missing_unique = []
        for item in missing:
            if item not in missing_unique:
                missing_unique.append(item)
        risk, signal, heat = _risk_from_mscore(mscore, missing_unique)

        variable_flags = []
        if 'proxy' in locals().get('aqi_method_t', '').lower() or 'proxy' in locals().get('aqi_method_p', '').lower():
            variable_flags.append(f"AQI dùng proxy do nguồn chưa tách PP&E/TSCĐ thuần: {aqi_method_t}; kỳ trước {aqi_method_p}")
        elif aqi is not None:
            variable_flags.append(f"AQI dùng dữ liệu: {aqi_method_t}; kỳ trước {aqi_method_p}")
        if 'proxy:' in locals().get('sga_method_t', '') or 'proxy:' in locals().get('sga_method_p', ''):
            variable_flags.append(f"SGAI dùng ước tính SG&A do nguồn dữ liệu thiếu chi tiết bán hàng/quản lý: {sga_method_t}; kỳ trước {sga_method_p}")
        if 'proxy' in locals().get('tata_method', '').lower():
            variable_flags.append(f"TATA dùng proxy dòng tiền do thiếu thành phần balance-sheet accruals: {tata_method}")
        elif tata is not None:
            variable_flags.append(f"TATA dùng {tata_method}")
        if dsri is not None and dsri > 1.2:
            variable_flags.append("DSRI cao: phải thu tăng nhanh hơn doanh thu")
        if gmi is not None and gmi > 1.0:
            variable_flags.append("GMI > 1: biên gộp suy giảm, tăng động cơ làm đẹp lợi nhuận")
        if aqi is not None and aqi > 1.0:
            variable_flags.append("AQI > 1: tài sản chất lượng thấp/chi phí hoãn lại tăng")
        if sgi is not None and sgi > 1.2:
            variable_flags.append("SGI cao: tăng trưởng tạo áp lực duy trì kỳ vọng")
        if depi is not None and depi > 1.0:
            variable_flags.append("DEPI > 1: tỷ lệ khấu hao giảm, cần kiểm tra thời gian hữu dụng TSCĐ")
        if sgai is not None and sgai > 1.0:
            variable_flags.append("SGAI > 1: SG&A/DT tăng")
        if tata is not None and tata > 0.05:
            variable_flags.append("TATA dương cao: lợi nhuận dựa nhiều vào accruals hơn dòng tiền")
        if lvgi is not None and lvgi > 1.0:
            variable_flags.append("LVGI > 1: đòn bẩy tăng, có thể tạo áp lực covenant/nợ")
        if not variable_flags and mscore is not None:
            variable_flags.append("Không có biến đơn lẻ vượt ngưỡng cảnh báo mạnh trong kỳ này")

        rows.append({
            "Kỳ": _period_name(cur),
            "Kỳ so sánh": f"{_period_name(prev)} → {_period_name(cur)}",
            "M-Score": round(mscore, 3) if mscore is not None else None,
            "Ngưỡng cảnh báo": -2.22,
            "Mức cảnh báo": risk,
            "Tín hiệu": signal,
            "Điểm nhiệt": heat,
            "DSRI": round(dsri, 3) if dsri is not None else None,
            "GMI": round(gmi, 3) if gmi is not None else None,
            "AQI": round(aqi, 3) if aqi is not None else None,
            "SGI": round(sgi, 3) if sgi is not None else None,
            "DEPI": round(depi, 3) if depi is not None else None,
            "SGAI": round(sgai, 3) if sgai is not None else None,
            "TATA": round(tata, 3) if tata is not None else None,
            "LVGI": round(lvgi, 3) if lvgi is not None else None,
            "Biến nổi bật/cần kiểm tra": "; ".join(variable_flags),
            "Biến thiếu/cần kiểm tra": "; ".join(missing_unique) if missing_unique else "Đủ biến lõi",
            "Cách tính TATA": tata_method,
            "Nguồn/logic": BENEISH_SOURCE_NOTE,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        latest = out.iloc[-1].to_dict()
        out.attrs["latest_score"] = _to_float(latest.get("M-Score"))
        out.attrs["latest_risk"] = latest.get("Mức cảnh báo", "N/A")
        out.attrs["latest_note"] = latest.get("Tín hiệu", "N/A")
        out.attrs["latest_period"] = latest.get("Kỳ", "N/A")
    return out


# ===== V23.55: Financial manipulation diagnostics - 4 analytical layers =====
FINANCIAL_MANIPULATION_SOURCE_NOTE = (
    "4 lớp cảnh báo thao túng tài chính: (1) Beneish M-Score; (2) Accrual Quality/Sloan; "
    "(3) Modified Jones/Kothari discretionary accruals; (4) Roychowdhury Real Earnings Management. "
    "Các mô hình là công cụ cảnh báo định lượng, không phải kết luận pháp lý về gian lận."
)


def _avg2(a: Any, b: Any) -> Optional[float]:
    x = _to_float(a)
    y = _to_float(b)
    if x is None and y is None:
        return None
    if x is None:
        return y
    if y is None:
        return x
    return (x + y) / 2.0


def _round_or_none(value: Any, digits: int = 3) -> Optional[float]:
    v = _to_float(value)
    if v is None or math.isnan(v) or math.isinf(v):
        return None
    return round(v, digits)


def _pct_text(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{value * 100:.1f}%"
    except Exception:
        return "N/A"


def _free_cash_flow_from_row(row: Dict[str, Any]) -> Optional[float]:
    fcf = _to_float(row.get("free_cash_flow_bil"))
    if fcf is not None:
        return fcf
    cfo = _to_float(row.get("cfo_bil"))
    capex = _to_float(row.get("capex_bil"))
    if cfo is None or capex is None:
        return None
    # Capex from Vietnamese cash-flow statements is often a negative cash outflow.
    return cfo + capex if capex < 0 else cfo - capex


def _delta(cur: Dict[str, Any], prev: Dict[str, Any], *cols: str) -> Optional[float]:
    cur_val = _first_available(cur, *cols)
    prev_val = _first_available(prev, *cols)
    if cur_val is None or prev_val is None:
        return None
    return cur_val - prev_val


def _short_term_debt_like(row: Dict[str, Any]) -> Optional[float]:
    return _row_sum(row, "short_term_debt_bil", "current_portion_long_term_debt_bil", abs_value=True)


def _balance_sheet_total_accruals(cur: Dict[str, Any], prev: Dict[str, Any]) -> tuple[Optional[float], str]:
    """Balance-sheet accruals: ΔCA - ΔCash - ΔCL + ΔSTD - Dep.

    If some balance-sheet components are missing, fallback to the cash-flow based proxy:
        Net profit - CFO
    """
    d_ca = _delta(cur, prev, "current_assets_bil", "short_term_assets_bil")
    d_cash = _delta(cur, prev, "cash_equivalents_bil", "cash_and_short_investments_bil")
    d_cl = _delta(cur, prev, "current_liabilities_bil")
    std_t = _short_term_debt_like(cur)
    std_p = _short_term_debt_like(prev)
    d_std = (std_t - std_p) if std_t is not None and std_p is not None else None
    dep = _first_available(cur, "depreciation_bil", "noncash_adjustments_bil")
    dep = abs(dep) if dep is not None else None
    if all(x is not None for x in [d_ca, d_cash, d_cl, d_std, dep]):
        return float(d_ca) - float(d_cash) - float(d_cl) + float(d_std) - float(dep), "Balance-sheet accruals = ΔCA - ΔCash - ΔCL + ΔNợ vay ngắn hạn - Khấu hao"
    ni = _to_float(cur.get("net_profit_bil"))
    cfo = _to_float(cur.get("cfo_bil"))
    if ni is not None and cfo is not None:
        return ni - cfo, "Cash-flow accrual proxy = LNST - CFO do thiếu một số thành phần ΔCA/ΔCL/ΔCash/ΔSTD/Dep"
    return None, "Thiếu dữ liệu accruals"


def _accrual_risk(sloan: Optional[float], cfo_to_np: Optional[float], fcf_to_np: Optional[float]) -> tuple[str, str, float]:
    score = 0.0
    reasons: List[str] = []
    if sloan is not None:
        if sloan > 0.12:
            score += 45; reasons.append("Sloan accrual ratio > 12% tài sản bình quân")
        elif sloan > 0.07:
            score += 28; reasons.append("Sloan accrual ratio > 7% tài sản bình quân")
        elif sloan > 0.03:
            score += 12; reasons.append("Accruals dương cần theo dõi")
        elif sloan < -0.10:
            score += 12; reasons.append("Accruals âm lớn, cần kiểm tra hoàn nhập/ghi nhận một lần")
    else:
        score += 18; reasons.append("Thiếu Sloan accrual ratio")
    if cfo_to_np is not None:
        if cfo_to_np < 0:
            score += 32; reasons.append("CFO âm trong khi LNST dương hoặc lợi nhuận không chuyển hóa thành tiền")
        elif cfo_to_np < 0.5:
            score += 24; reasons.append("CFO/LNST < 0.5")
        elif cfo_to_np < 0.8:
            score += 10; reasons.append("CFO/LNST < 0.8")
    else:
        score += 12; reasons.append("Thiếu CFO/LNST")
    if fcf_to_np is not None:
        if fcf_to_np < -0.25:
            score += 20; reasons.append("FCF/LNST âm sâu")
        elif fcf_to_np < 0:
            score += 12; reasons.append("FCF âm so với lợi nhuận")
    else:
        score += 8; reasons.append("Thiếu FCF/LNST")
    if score >= 75:
        return "Rủi ro rất cao", "; ".join(reasons), min(score, 100.0)
    if score >= 55:
        return "Rủi ro cao", "; ".join(reasons), score
    if score >= 35:
        return "Theo dõi", "; ".join(reasons), score
    return "Thấp", "; ".join(reasons) or "Lợi nhuận tương đối được hỗ trợ bởi dòng tiền", max(score, 20.0)


def build_accrual_quality_table(company: CompanyOverview, annual_df: pd.DataFrame) -> pd.DataFrame:
    """Layer 2 - Sloan/accrual quality diagnostics.

    Core formulas:
    - Total accruals (cash-flow proxy) = Net profit - CFO.
    - Sloan accrual ratio = Total accruals / Average total assets.
    - CFO/LNST = CFO / Net profit.
    - FCF/LNST = Free cash flow / Net profit.
    - Balance-sheet accruals = ΔCA - ΔCash - ΔCL + ΔShort-term debt - Depreciation, if enough data.
    """
    df = _beneish_input_rows(annual_df)
    if df.empty or len(df) < 2:
        return pd.DataFrame([{
            "Lớp": "2. Accrual Quality/Sloan",
            "Kỳ": "N/A",
            "Mức cảnh báo": "Thiếu dữ liệu",
            "Tín hiệu": "Cần tối thiểu 2 năm dữ liệu để tính accruals và tài sản bình quân.",
            "Điểm nhiệt": 35.0,
            "Công thức/logic": "Sloan accrual ratio = (LNST - CFO) / Tổng tài sản bình quân.",
            "Cần kiểm tra": "Cần BCTC năm có LNST, CFO, tổng tài sản.",
        }])
    rows: List[Dict[str, Any]] = []
    for idx in range(1, len(df)):
        prev = df.iloc[idx - 1].to_dict()
        cur = df.iloc[idx].to_dict()
        period = _period_name(cur)
        ta_avg = _avg2(_first_available(cur, "total_assets_bil", "assets_bil"), _first_available(prev, "total_assets_bil", "assets_bil"))
        ni = _to_float(cur.get("net_profit_bil"))
        cfo = _to_float(cur.get("cfo_bil"))
        fcf = _free_cash_flow_from_row(cur)
        cash_accruals = (ni - cfo) if ni is not None and cfo is not None else None
        bs_accruals, bs_method = _balance_sheet_total_accruals(cur, prev)
        sloan = _safe_div(cash_accruals, ta_avg)
        bs_ratio = _safe_div(bs_accruals, ta_avg)
        cfo_to_np = _safe_div(cfo, ni)
        fcf_to_np = _safe_div(fcf, ni)
        risk, signal, heat = _accrual_risk(sloan, cfo_to_np, fcf_to_np)
        check_items: List[str] = []
        if sloan is not None and sloan > 0.07:
            check_items.append("Accruals cao: đọc thuyết minh phải thu, tồn kho, chi phí trả trước, dự phòng và khoản mục một lần")
        if cfo_to_np is not None and cfo_to_np < 0.8:
            check_items.append("CFO/LNST thấp: kiểm tra tiền thu khách hàng, thay đổi vốn lưu động, phải thu tăng")
        if fcf_to_np is not None and fcf_to_np < 0:
            check_items.append("FCF âm: phân biệt capex mở rộng hợp lý hay mô hình kinh doanh hút tiền")
        if not check_items:
            check_items.append("Không có cờ đỏ mạnh trong lớp dòng tiền-accruals")
        rows.append({
            "Lớp": "2. Accrual Quality/Sloan",
            "Kỳ": period,
            "Sloan accrual ratio": _round_or_none(sloan, 3),
            "CFO/LNST": _round_or_none(cfo_to_np, 3),
            "FCF/LNST": _round_or_none(fcf_to_np, 3),
            "Balance-sheet accrual ratio": _round_or_none(bs_ratio, 3),
            "Accruals (tỷ đồng)": _round_or_none(cash_accruals, 0),
            "Mức cảnh báo": risk,
            "Tín hiệu": signal,
            "Điểm nhiệt": round(heat, 1),
            "Công thức/logic": "Sloan = (LNST - CFO) / Tổng tài sản bình quân; CFO/LNST = CFO/LNST; FCF/LNST = FCF/LNST; BS Accruals = ΔCA - ΔCash - ΔCL + ΔSTD - Dep.",
            "Dữ liệu/cách tính": f"Tổng tài sản bình quân={_round_or_none(ta_avg,0)} tỷ; LNST={_round_or_none(ni,0)} tỷ; CFO={_round_or_none(cfo,0)} tỷ; FCF={_round_or_none(fcf,0)} tỷ; {bs_method}",
            "Cần kiểm tra": "; ".join(check_items),
            "Nguồn/logic": FINANCIAL_MANIPULATION_SOURCE_NOTE,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        latest = out.iloc[-1]
        out.attrs["latest_risk"] = latest.get("Mức cảnh báo", "N/A")
        out.attrs["latest_score"] = _to_float(latest.get("Sloan accrual ratio"))
        out.attrs["latest_note"] = latest.get("Tín hiệu", "N/A")
    return out


def _ols_fit_values(records: List[Dict[str, Any]], y_col: str, x_cols: List[str], label: str) -> tuple[Dict[int, tuple[Optional[float], Optional[float]]], str]:
    """Return fitted/residual by record index. Falls back to median baseline when OLS has too few observations."""
    valid: List[tuple[int, float, List[float]]] = []
    for i, rec in enumerate(records):
        y = _to_float(rec.get(y_col))
        xs = [_to_float(rec.get(c)) for c in x_cols]
        if y is not None and all(x is not None for x in xs):
            valid.append((i, float(y), [float(x) for x in xs]))
    result: Dict[int, tuple[Optional[float], Optional[float]]] = {i: (None, None) for i in range(len(records))}
    min_obs = len(x_cols) + 2
    if len(valid) >= min_obs:
        X = np.array([[1.0] + xs for _, _, xs in valid], dtype=float)
        Y = np.array([y for _, y, _ in valid], dtype=float)
        try:
            beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
            for i, y, xs in valid:
                fitted = float(np.dot(np.array([1.0] + xs), beta))
                result[i] = (fitted, float(y - fitted))
            return result, f"OLS {label}: đủ {len(valid)} quan sát; hồi quy y trên {', '.join(x_cols)}."
        except Exception as exc:
            pass
    ys = [y for _, y, _ in valid]
    if ys:
        med = float(pd.Series(ys).median())
        for i, y, _ in valid:
            result[i] = (med, float(y - med))
        return result, f"Proxy median {label}: chỉ có {len(valid)} quan sát hợp lệ, chưa đủ để OLS ổn định; residual = y - median(y)."
    return result, f"Thiếu dữ liệu {label}: không đủ y và biến giải thích."


def _mj_risk(da_mj: Optional[float], da_k: Optional[float]) -> tuple[str, str, float]:
    vals = [abs(x) for x in [da_mj, da_k] if x is not None]
    main_val = max(vals) if vals else None
    reasons: List[str] = []
    if da_mj is not None:
        if da_mj > 0.08:
            reasons.append("DA Modified Jones dương cao: accruals làm tăng lợi nhuận")
        elif da_mj < -0.08:
            reasons.append("DA Modified Jones âm sâu: khả năng big-bath/ghi nhận chi phí trước")
    if da_k is not None:
        if da_k > 0.08:
            reasons.append("DA Kothari dương cao sau khi kiểm soát ROA")
        elif da_k < -0.08:
            reasons.append("DA Kothari âm sâu sau khi kiểm soát ROA")
    if main_val is None:
        return "Thiếu dữ liệu", "Không đủ biến để ước lượng discretionary accruals", 35.0
    if main_val >= 0.12:
        return "Rủi ro cao", "; ".join(reasons) or "Discretionary accruals lớn", 82.0
    if main_val >= 0.07:
        return "Theo dõi", "; ".join(reasons) or "Discretionary accruals ở vùng cần theo dõi", 58.0
    return "Thấp", "; ".join(reasons) or "Discretionary accruals không lớn so với tài sản", 25.0


def build_modified_jones_kothari_table(company: CompanyOverview, annual_df: pd.DataFrame) -> pd.DataFrame:
    """Layer 3 - Modified Jones and Kothari discretionary accrual diagnostics.

    Modified Jones:
        TA_t/A_{t-1} = α0 + α1(1/A_{t-1}) + α2((ΔREV_t - ΔREC_t)/A_{t-1}) + α3(PPE_t/A_{t-1}) + ε_t
        DA_MJ = ε_t
    Kothari performance-matched version:
        Add ROA_t as an extra control variable. DA_Kothari = residual after controlling ROA.
    """
    df = _beneish_input_rows(annual_df)
    if df.empty or len(df) < 2:
        return pd.DataFrame([{
            "Lớp": "3. Modified Jones/Kothari",
            "Kỳ": "N/A",
            "Mức cảnh báo": "Thiếu dữ liệu",
            "Tín hiệu": "Cần tối thiểu 2 năm BCTC để tạo biến accruals; muốn hồi quy ổn định cần chuỗi dài hơn.",
            "Điểm nhiệt": 35.0,
            "Công thức/logic": "TA/A(t-1) = α0 + α1(1/A(t-1)) + α2((ΔREV-ΔREC)/A(t-1)) + α3(PPE/A(t-1)) + ε; Kothari thêm ROA.",
            "Cần kiểm tra": "Cần doanh thu, phải thu, tổng tài sản, PPE/TSCĐ, LNST, CFO.",
        }])
    records: List[Dict[str, Any]] = []
    for idx in range(1, len(df)):
        prev = df.iloc[idx - 1].to_dict()
        cur = df.iloc[idx].to_dict()
        a_lag = _first_available(prev, "total_assets_bil", "assets_bil")
        total_accruals, acc_method = _balance_sheet_total_accruals(cur, prev)
        sales_t = _first_available(cur, "revenue_bil", "gross_revenue_bil")
        sales_p = _first_available(prev, "revenue_bil", "gross_revenue_bil")
        ar_t = _to_float(cur.get("accounts_receivable_bil"))
        ar_p = _to_float(prev.get("accounts_receivable_bil"))
        ppe_t = _first_available(cur, "ppe_bil", "net_ppe_bil", "property_plant_equipment_bil", "fixed_assets_net_bil", "tangible_fixed_assets_bil", "fixed_assets_bil")
        if ppe_t is None:
            ppe_t = _first_available(cur, "long_term_assets_bil", "non_current_assets_bil")
        ni = _to_float(cur.get("net_profit_bil"))
        d_rev = (sales_t - sales_p) if sales_t is not None and sales_p is not None else None
        d_rec = (ar_t - ar_p) if ar_t is not None and ar_p is not None else None
        rec = {
            "Lớp": "3. Modified Jones/Kothari",
            "Kỳ": _period_name(cur),
            "TA_scaled": _safe_div(total_accruals, a_lag),
            "inv_assets_lag": _safe_div(1.0, a_lag),
            "adj_sales_scaled": _safe_div((d_rev - d_rec) if d_rev is not None and d_rec is not None else None, a_lag),
            "ppe_scaled": _safe_div(ppe_t, a_lag),
            "roa_scaled": _safe_div(ni, a_lag),
            "acc_method": acc_method,
        }
        records.append(rec)
    mj_fit, mj_method = _ols_fit_values(records, "TA_scaled", ["inv_assets_lag", "adj_sales_scaled", "ppe_scaled"], "Modified Jones")
    k_fit, k_method = _ols_fit_values(records, "TA_scaled", ["inv_assets_lag", "adj_sales_scaled", "ppe_scaled", "roa_scaled"], "Kothari")
    rows: List[Dict[str, Any]] = []
    for i, rec in enumerate(records):
        mj_expected, da_mj = mj_fit.get(i, (None, None))
        k_expected, da_k = k_fit.get(i, (None, None))
        risk, signal, heat = _mj_risk(da_mj, da_k)
        checks: List[str] = []
        if da_mj is not None and da_mj > 0.07:
            checks.append("DA dương: kiểm tra doanh thu, phải thu, chi phí vốn hóa, dự phòng/hoàn nhập")
        if da_mj is not None and da_mj < -0.07:
            checks.append("DA âm sâu: kiểm tra big-bath, trích lập dự phòng lớn, ghi nhận chi phí sớm")
        if rec.get("ppe_scaled") is None:
            checks.append("Thiếu PPE/TSCĐ thuần; kết quả hồi quy có thể kém ổn định")
        if not checks:
            checks.append("Không có discretionary accruals vượt ngưỡng mạnh")
        rows.append({
            "Lớp": "3. Modified Jones/Kothari",
            "Kỳ": rec.get("Kỳ"),
            "TA/A(t-1)": _round_or_none(rec.get("TA_scaled"), 3),
            "(ΔREV-ΔREC)/A(t-1)": _round_or_none(rec.get("adj_sales_scaled"), 3),
            "PPE/A(t-1)": _round_or_none(rec.get("ppe_scaled"), 3),
            "ROA": _round_or_none(rec.get("roa_scaled"), 3),
            "NDA Modified Jones": _round_or_none(mj_expected, 3),
            "DA Modified Jones": _round_or_none(da_mj, 3),
            "NDA Kothari": _round_or_none(k_expected, 3),
            "DA Kothari": _round_or_none(da_k, 3),
            "Mức cảnh báo": risk,
            "Tín hiệu": signal,
            "Điểm nhiệt": round(heat, 1),
            "Công thức/logic": "Modified Jones: TA/A(t-1)=α0+α1(1/A(t-1))+α2((ΔREV-ΔREC)/A(t-1))+α3(PPE/A(t-1))+ε. Kothari thêm ROA. DA=residual ε.",
            "Phương pháp ước lượng": f"{mj_method} | {k_method}; {rec.get('acc_method')}",
            "Cần kiểm tra": "; ".join(checks),
            "Nguồn/logic": FINANCIAL_MANIPULATION_SOURCE_NOTE,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        latest = out.iloc[-1]
        out.attrs["latest_risk"] = latest.get("Mức cảnh báo", "N/A")
        out.attrs["latest_score"] = _to_float(latest.get("DA Modified Jones"))
        out.attrs["latest_note"] = latest.get("Tín hiệu", "N/A")
    return out


def _rem_risk(abn_cfo: Optional[float], abn_prod: Optional[float], abn_disexp: Optional[float]) -> tuple[str, str, float, Optional[float]]:
    score = 0.0
    reasons: List[str] = []
    if abn_cfo is not None and abn_cfo < -0.04:
        score += min(abs(abn_cfo) * 450, 35); reasons.append("Abnormal CFO âm: doanh thu có thể được kéo bằng giảm giá/nới tín dụng")
    if abn_prod is not None and abn_prod > 0.05:
        score += min(abn_prod * 420, 35); reasons.append("Abnormal PROD dương: sản xuất/tồn kho cao bất thường")
    if abn_disexp is not None and abn_disexp < -0.03:
        score += min(abs(abn_disexp) * 360, 30); reasons.append("Abnormal DISEXP âm: cắt chi phí tùy ý để nâng lợi nhuận")
    if abn_cfo is None and abn_prod is None and abn_disexp is None:
        return "Thiếu dữ liệu", "Không đủ dữ liệu để ước lượng REM", 35.0, None
    if score >= 70:
        return "Rủi ro cao", "; ".join(reasons), min(score, 100.0), score / 100.0
    if score >= 40:
        return "Theo dõi", "; ".join(reasons), score, score / 100.0
    return "Thấp", "; ".join(reasons) or "Chưa thấy dấu hiệu REM mạnh từ CFO/production/chi phí tùy ý", max(score, 20.0), score / 100.0


def build_real_earnings_management_table(company: CompanyOverview, annual_df: pd.DataFrame) -> pd.DataFrame:
    """Layer 4 - Roychowdhury real earnings management diagnostics.

    CFO model:
        CFO/A_{t-1} = α0 + α1(1/A_{t-1}) + β1(Sales/A_{t-1}) + β2(ΔSales/A_{t-1}) + ε
    Production model:
        PROD/A_{t-1} = α0 + α1(1/A_{t-1}) + β1(Sales/A_{t-1}) + β2(ΔSales/A_{t-1}) + β3(ΔSales_{t-1}/A_{t-1}) + ε
        PROD = COGS + ΔInventory
    Discretionary expense model:
        DISEXP/A_{t-1} = α0 + α1(1/A_{t-1}) + β1(Sales_{t-1}/A_{t-1}) + ε
        DISEXP proxy = selling expense + admin expense, or SG&A proxy when details are unavailable.
    """
    df = _beneish_input_rows(annual_df)
    if df.empty or len(df) < 2:
        return pd.DataFrame([{
            "Lớp": "4. Real Earnings Management",
            "Kỳ": "N/A",
            "Mức cảnh báo": "Thiếu dữ liệu",
            "Tín hiệu": "Cần chuỗi BCTC năm để tính CFO bất thường, sản xuất bất thường và chi phí tùy ý bất thường.",
            "Điểm nhiệt": 35.0,
            "Công thức/logic": "REM theo Roychowdhury: Abnormal CFO, Abnormal PROD và Abnormal DISEXP là residual từ mô hình doanh thu/tài sản.",
            "Cần kiểm tra": "Cần doanh thu, CFO, giá vốn, tồn kho, SG&A, tổng tài sản.",
        }])
    records: List[Dict[str, Any]] = []
    prev_delta_sales: Optional[float] = None
    for idx in range(1, len(df)):
        prev = df.iloc[idx - 1].to_dict()
        cur = df.iloc[idx].to_dict()
        a_lag = _first_available(prev, "total_assets_bil", "assets_bil")
        sales_t = _first_available(cur, "revenue_bil", "gross_revenue_bil")
        sales_p = _first_available(prev, "revenue_bil", "gross_revenue_bil")
        d_sales = (sales_t - sales_p) if sales_t is not None and sales_p is not None else None
        cfo = _to_float(cur.get("cfo_bil"))
        cogs = _cogs_from_row(cur)
        inv_delta = _delta(cur, prev, "inventory_bil")
        prod = (cogs + inv_delta) if cogs is not None and inv_delta is not None else None
        sga, sga_method = _sga_from_row(cur)
        rec = {
            "Lớp": "4. Real Earnings Management",
            "Kỳ": _period_name(cur),
            "cfo_scaled": _safe_div(cfo, a_lag),
            "prod_scaled": _safe_div(prod, a_lag),
            "disexp_scaled": _safe_div(sga, a_lag),
            "inv_assets_lag": _safe_div(1.0, a_lag),
            "sales_scaled": _safe_div(sales_t, a_lag),
            "delta_sales_scaled": _safe_div(d_sales, a_lag),
            "lag_delta_sales_scaled": _safe_div(prev_delta_sales, a_lag),
            "lag_sales_scaled": _safe_div(sales_p, a_lag),
            "sga_method": sga_method,
        }
        records.append(rec)
        prev_delta_sales = d_sales
    cfo_fit, cfo_method = _ols_fit_values(records, "cfo_scaled", ["inv_assets_lag", "sales_scaled", "delta_sales_scaled"], "CFO bất thường")
    prod_fit, prod_method = _ols_fit_values(records, "prod_scaled", ["inv_assets_lag", "sales_scaled", "delta_sales_scaled", "lag_delta_sales_scaled"], "PROD bất thường")
    dis_fit, dis_method = _ols_fit_values(records, "disexp_scaled", ["inv_assets_lag", "lag_sales_scaled"], "DISEXP bất thường")
    rows: List[Dict[str, Any]] = []
    for i, rec in enumerate(records):
        cfo_expected, abn_cfo = cfo_fit.get(i, (None, None))
        prod_expected, abn_prod = prod_fit.get(i, (None, None))
        dis_expected, abn_dis = dis_fit.get(i, (None, None))
        risk, signal, heat, rem_score = _rem_risk(abn_cfo, abn_prod, abn_dis)
        checks: List[str] = []
        if abn_cfo is not None and abn_cfo < -0.04:
            checks.append("Đối chiếu doanh thu cuối kỳ, khoản phải thu, chính sách chiết khấu và tiền thu khách hàng")
        if abn_prod is not None and abn_prod > 0.05:
            checks.append("Kiểm tra tồn kho, công suất, giá vốn đơn vị, hàng chậm luân chuyển và dự phòng giảm giá tồn kho")
        if abn_dis is not None and abn_dis < -0.03:
            checks.append("Kiểm tra có cắt giảm quảng cáo/R&D/bảo trì/nhân sự để nâng lợi nhuận ngắn hạn không")
        if "proxy" in str(rec.get("sga_method", "")):
            checks.append(f"DISEXP dùng proxy SG&A: {rec.get('sga_method')}")
        if not checks:
            checks.append("Không có dấu hiệu REM mạnh từ ba biến bất thường")
        rows.append({
            "Lớp": "4. Real Earnings Management",
            "Kỳ": rec.get("Kỳ"),
            "Abnormal CFO": _round_or_none(abn_cfo, 3),
            "Abnormal PROD": _round_or_none(abn_prod, 3),
            "Abnormal DISEXP": _round_or_none(abn_dis, 3),
            "REM Score": _round_or_none(rem_score, 3),
            "CFO/A(t-1)": _round_or_none(rec.get("cfo_scaled"), 3),
            "PROD/A(t-1)": _round_or_none(rec.get("prod_scaled"), 3),
            "DISEXP/A(t-1)": _round_or_none(rec.get("disexp_scaled"), 3),
            "Mức cảnh báo": risk,
            "Tín hiệu": signal,
            "Điểm nhiệt": round(heat, 1),
            "Công thức/logic": "CFO/A(t-1), PROD/A(t-1)=COGS+ΔInventory, DISEXP/A(t-1) được hồi quy theo Sales/ΔSales; residual bất thường là cảnh báo REM.",
            "Phương pháp ước lượng": f"{cfo_method} | {prod_method} | {dis_method}",
            "Cần kiểm tra": "; ".join(checks),
            "Nguồn/logic": FINANCIAL_MANIPULATION_SOURCE_NOTE,
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        latest = out.iloc[-1]
        out.attrs["latest_risk"] = latest.get("Mức cảnh báo", "N/A")
        out.attrs["latest_score"] = _to_float(latest.get("REM Score"))
        out.attrs["latest_note"] = latest.get("Tín hiệu", "N/A")
    return out

def build_module2_summary(company: CompanyOverview, annual_df: pd.DataFrame, valuation_df: pd.DataFrame, moat_df: pd.DataFrame) -> str:
    cls = classify_company(company, annual_df)
    current_price = _to_float(getattr(company, "current_price", None))
    target_mos_pct = _to_float(valuation_df.get("MOS chọn %", pd.Series([30])).dropna().iloc[0]) if isinstance(valuation_df, pd.DataFrame) and "MOS chọn %" in valuation_df.columns and not valuation_df.empty else 30
    rng = build_valuation_range(valuation_df, current_price, target_mos_pct)
    moat_score = moat_df.attrs.get("total_score", None) if moat_df is not None else None
    moat_level = moat_df.attrs.get("level", "Chưa chấm") if moat_df is not None else "Chưa chấm"
    parts = [
        f"Doanh nghiệp được phân loại sơ bộ là **{cls.company_type}** với độ tin cậy {cls.confidence:.0f}/100.",
        f"Phương pháp ưu tiên: {', '.join(cls.preferred_methods)}.",
    ]
    if rng.weighted_vnd is not None:
        parts.append(f"Giá trị nội tại trung bình trọng số khoảng **{rng.weighted_vnd:,.0f} đồng/cp**; khuyến nghị trạng thái: **{rng.recommendation}**.")
    else:
        parts.append("Chưa đủ dữ liệu để tính giá trị nội tại trung bình trọng số.")
    if moat_score is not None:
        parts.append(f"Điểm Porter Moat sơ bộ: **{moat_score:.1f}/100** - {moat_level}.")
    if cls.reasons:
        parts.append("Lý do chính: " + "; ".join(cls.reasons[:4]))
    return " ".join(parts)


def format_module2_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return a display copy; Streamlit styling is handled by dashboard._style_financial_table."""
    return df.copy() if df is not None else pd.DataFrame()


def export_module2_report_markdown(company: CompanyOverview, valuation_df: pd.DataFrame, moat_df: pd.DataFrame,
                                   value_chain_df: pd.DataFrame, scenario_df: pd.DataFrame, output_path: str | Path,
                                   annual_df: pd.DataFrame | None = None) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    current_price = _to_float(getattr(company, "current_price", None))
    target_mos_pct = _to_float(valuation_df.get("MOS chọn %", pd.Series([30])).dropna().iloc[0]) if isinstance(valuation_df, pd.DataFrame) and "MOS chọn %" in valuation_df.columns and not valuation_df.empty else 30
    rng = build_valuation_range(valuation_df, current_price, target_mos_pct)
    lines = [
        f"# Báo cáo Định giá chuyên sâu: {getattr(company, 'ticker', '')}",
        "",
        build_module2_summary(company, annual_df if isinstance(annual_df, pd.DataFrame) else pd.DataFrame(), valuation_df, moat_df),
        "",
        "## 1. Dải định giá",
        f"- Low: {rng.low_vnd:,.0f} đồng/cp" if rng.low_vnd is not None else "- Low: N/A",
        f"- Base: {rng.base_vnd:,.0f} đồng/cp" if rng.base_vnd is not None else "- Base: N/A",
        f"- High: {rng.high_vnd:,.0f} đồng/cp" if rng.high_vnd is not None else "- High: N/A",
        f"- Weighted: {rng.weighted_vnd:,.0f} đồng/cp" if rng.weighted_vnd is not None else "- Weighted: N/A",
        f"- Khuyến nghị trạng thái: {rng.recommendation}",
        "",
        "## 2. Bảng định giá chi tiết",
        valuation_df.to_markdown(index=False) if valuation_df is not None and not valuation_df.empty else "Chưa có dữ liệu.",
        "",
        "## 3. Bảng điểm lợi thế cạnh tranh theo Porter",
        moat_df.to_markdown(index=False) if moat_df is not None and not moat_df.empty else "Chưa có dữ liệu.",
        "",
        "## 4. Chuỗi giá trị",
        value_chain_df.to_markdown(index=False) if value_chain_df is not None and not value_chain_df.empty else "Chưa có dữ liệu.",
        "",
        "## 5. Kịch bản/rủi ro",
        scenario_df.to_markdown(index=False) if scenario_df is not None and not scenario_df.empty else "Chưa có dữ liệu.",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path
