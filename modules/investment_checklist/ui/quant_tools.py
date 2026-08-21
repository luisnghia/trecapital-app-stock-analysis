from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from ..phase2_formula_assumptions import PHASE2_FORMULA_ROWS
from ..quantitative_tools import (
    ToolResult,
    accounting_quality_proxy,
    balance_sheet_leverage,
    buyback_dilution,
    maintenance_capex_context,
    operating_driver_eps,
    operating_leverage,
    operating_leverage_stress,
    roic_quality,
    working_capital,
)


TOOL_OPTIONS = [
    "5.1–5.2 · Balance Sheet & Leverage",
    "5.3–5.4 · ROIC Quality",
    "6.1–6.2 · Accounting Reserve Quality",
    "6.3–6.5 · Operating Leverage & Cost Structure",
    "6.6 · Working Capital / CCC",
    "Ch.6 Key Point · Maintenance Capex Context",
    "8.2–8.3 · Buyback & Dilution",
    "10.1 · Operating Driver → EPS",
]

_FINANCIAL_TYPES = {"bank", "insurance", "securities"}


def _annual_df(provider) -> pd.DataFrame:
    df = getattr(provider, "annual_df", None)
    if isinstance(df, pd.DataFrame):
        return df.copy()
    inner = getattr(provider, "inner", None)
    df = getattr(inner, "annual_df", None)
    return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _heat(value: Any) -> str:
    try:
        if value is None or pd.isna(value) or float(value) == 0:
            return ""
        if float(value) < 0:
            return "color:#B91C1C;background-color:rgba(220,38,38,.10);font-weight:700"
        return "color:#047857;background-color:rgba(16,185,129,.10);font-weight:700"
    except Exception:
        return ""


def _latest_first(df: pd.DataFrame) -> pd.DataFrame:
    """Display TTM first, then newest annual periods; calculations remain chronological upstream."""
    if df.empty or "Kỳ" not in df.columns:
        return df
    out = df.copy()
    def key(value):
        text = str(value or "").strip().upper()
        if "TTM" in text or "T12M" in text:
            return 999999
        try:
            return int(float(text[:4]))
        except Exception:
            return -1
    out["_sort"] = out["Kỳ"].map(key)
    return out.sort_values("_sort", ascending=False, kind="stable").drop(columns="_sort")


def _styled(df: pd.DataFrame):
    if df.empty:
        return df.style
    formats: dict[str, Any] = {}
    pct_hints = (
        "growth", "ROIC", "PP&E /", "SG&A /", "D&A /", "ΔWC /", "Share count change",
        "EPS uplift", "Revenue shock", "EBIT change", "Capex / Revenue",
    )
    ratio_cols = {
        "Debt/EBITDA", "EBIT/Interest", "CFO / Net income", "Provision / charge-off",
        "DOL", "DOL used", "Current Ratio", "Capex / D&A",
    }
    day_cols = {"DSO", "DIO", "DPO", "CCC"}
    for col in df.columns:
        if col in day_cols:
            formats[col] = lambda v: "—" if pd.isna(v) else f"{v:,.0f} ngày"
        elif any(h in str(col) for h in pct_hints):
            formats[col] = lambda v: "—" if pd.isna(v) else f"{v:,.1f}%"
        elif col in ratio_cols:
            formats[col] = lambda v: "—" if pd.isna(v) else f"{v:,.1f}x"
        elif pd.api.types.is_numeric_dtype(df[col]):
            formats[col] = lambda v: "—" if pd.isna(v) else f"{v:,.0f}"
    nums = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return df.style.format(formats, na_rep="—").map(_heat, subset=nums)


def _render_result(result: ToolResult, *, height: int | None = None) -> None:
    st.markdown(f"#### {result.name}")
    st.caption(
        f"Bảng/nguồn gốc: {', '.join(result.source_tables)} · Hỗ trợ checklist: {', '.join(result.checklist_questions)} · "
        "Dữ liệu tài chính chỉ consume từ Trecapital Data Layer."
    )
    if result.rows:
        df = _latest_first(pd.DataFrame(result.rows))
        st.dataframe(_styled(df), use_container_width=True, hide_index=True, height=height)
    else:
        st.info("Chưa có đủ dữ liệu Trecapital để dựng tool này. App không tự bịa số liệu.")
    for note in result.notes:
        st.caption("• " + note)


def _driver_candidates(df: pd.DataFrame) -> list[tuple[str, str]]:
    preferred = [
        ("revenue_bil", "Revenue"),
        ("sales_volume", "Sales volume"),
        ("volume", "Volume"),
        ("capacity_utilization_pct", "Capacity utilization"),
        ("same_store_sales_growth_pct", "Same-store sales"),
        ("store_count", "Store count"),
        ("customer_count", "Customer count"),
        ("transactions", "Transactions"),
        ("loan_growth_pct", "Loan growth"),
        ("nim_pct", "NIM"),
    ]
    out = [(field, label) for field, label in preferred if field in df.columns and pd.to_numeric(df[field], errors="coerce").notna().any()]
    if not out and "revenue_bil" in df.columns:
        out = [("revenue_bil", "Revenue")]
    return out


def _formula_audit(tool_prefix: str | None = None) -> None:
    rows = PHASE2_FORMULA_ROWS
    if tool_prefix:
        matches = [r for r in rows if str(r.get("Tool", "")).startswith(tool_prefix)]
        if matches:
            rows = matches
    with st.expander("📐 Công thức & giả định của Analytical Tools", expanded=False):
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=min(520, 38 * len(rows) + 75))
        st.caption("SOURCE / Trecapital implementation / extension được ghi tách biệt; thay đổi công thức phải đi cùng regression test.")


def render_quantitative_tools(
    data_provider,
    *,
    company_type: str = "normal",
    auxiliary_table_renderer: Callable[[str, pd.DataFrame], None] | None = None,
) -> None:
    st.markdown("### 🧮 Analytical Tools — Phase 2")
    st.caption(
        "Chuyển các bảng định lượng 5.1–5.4, 6.1–6.6, 8.2–8.3 và 10.1 của Michael Shearn thành tool; "
        "bổ sung Maintenance Capex Context từ Key Points Chương 6 để hỗ trợ Q32. Tool cung cấp evidence; analyst vẫn tự kết luận."
    )
    st.markdown(
        "<div class='principle'><b>Single Source of Truth:</b> các tool không gọi nguồn tài chính riêng. "
        "Chúng dùng cùng annual/TTM đã chuẩn hóa của Trecapital; proxy/variant luôn được ghi nhãn.</div>",
        unsafe_allow_html=True,
    )

    df = _annual_df(data_provider)
    if df.empty:
        st.warning("Không có annual/TTM Data Layer để chạy Analytical Tools.")
        _formula_audit()
        return

    company_type = str(company_type or "normal").lower()
    if company_type in _FINANCIAL_TYPES:
        st.warning(
            "Doanh nghiệp tài chính: ROIC/CCC/operating leverage kiểu công nghiệp có thể không phù hợp. "
            "Phase 3 Industry Overlay sẽ thay supporting metrics bằng ROE/ROA/NIM/CASA/LDR/NPL/LLR/CAR... "
            "Không dùng các tool công nghiệp dưới đây làm kết luận chính."
        )

    selected = st.selectbox("Analytical tool", TOOL_OPTIONS, key="checklist_phase2_tool")
    formula_prefix = None

    if selected.startswith("5.1"):
        formula_prefix = "Balance Sheet"
        _render_result(balance_sheet_leverage(df), height=470)
        st.info("Q25: đánh giá sức mạnh bảng cân đối qua chu kỳ, không chỉ nhìn Debt/EBITDA của một kỳ.")

    elif selected.startswith("5.3"):
        formula_prefix = "ROIC Quality"
        _render_result(roic_quality(df), height=470)
        st.info(
            "Q26: 'ROIC Trecapital' là metric chuẩn của app. Các ROIC Shearn chỉ là analytical views để nhìn distortion do cash/goodwill; "
            "không tự động thay assessment analyst."
        )

    elif selected.startswith("6.1"):
        formula_prefix = "Accounting Reserve"
        _render_result(accounting_quality_proxy(df), height=470)
        st.warning(
            "Tool này không chạy lại Beneish/M-Score. Module Manipulation hiện có vẫn là nơi thực hiện manipulation tests; "
            "Phase 2 chỉ đặt reserve/charge-off, CFO vs NI, AR và Inventory vào context của Q27."
        )

    elif selected.startswith("6.3"):
        formula_prefix = "Operating Leverage"
        _render_result(operating_leverage(df), height=470)
        st.markdown("##### Stress test — phần mở rộng Trecapital")
        stress = operating_leverage_stress(df)
        if stress:
            stress_df = pd.DataFrame(stress)
            if callable(auxiliary_table_renderer):
                auxiliary_table_renderer("Operating Leverage Stress", stress_df)
            else:
                st.dataframe(_styled(stress_df), use_container_width=True, hide_index=True)
            st.caption("Stress test dùng median DOL của tối đa 5 quan sát hợp lệ gần nhất. Đây là scenario extension, không phải bảng gốc của Shearn.")
        else:
            st.info("Chưa đủ DOL lịch sử để chạy stress -5% / -10% / -20% revenue.")
        st.warning(
            "Cost structure không được tự gắn nhãn Fixed/Variable chỉ từ BCTC. PP&E/Assets, SG&A/Revenue, D&A/Revenue là evidence; "
            "analyst vẫn phải đọc MD&A để phân loại fixed / variable / semi-variable."
        )

    elif selected.startswith("6.6"):
        formula_prefix = "Working Capital"
        _render_result(working_capital(df), height=500)
        st.info("Q31: CCC giảm có thể do vận hành tốt hơn hoặc do kéo dài DPO. App không tự chấm 'CCC thấp = tốt'.")

    elif selected.startswith("Ch.6"):
        formula_prefix = "Maintenance Capex"
        _render_result(maintenance_capex_context(df), height=470)
        st.info(
            "Q32: nếu chưa có thuyết minh tách maintenance/growth capex, app chỉ đưa Capex/D&A/FCF context. "
            "Depreciation là rough approximation theo Shearn, không được ghi thành maintenance capex thực tế."
        )

    elif selected.startswith("8.2"):
        formula_prefix = "Buyback"
        _render_result(buyback_dilution(df), height=500)
        st.info(
            "Q46–Q47: Net share reduction và EPS uplift có thể tính tự động. Gross buyback trừ ESOP/options chỉ hiện khi Data Layer có line-item; "
            "thiếu thì để trống chứ không giả định bằng 0."
        )

    else:
        formula_prefix = "Operating Driver"
        candidates = _driver_candidates(df)
        if candidates:
            labels = [label for _, label in candidates]
            label = st.selectbox("Operating driver", labels, key="checklist_phase2_driver")
            field = next(field for field, lbl in candidates if lbl == label)
            _render_result(operating_driver_eps(df, driver_field=field, driver_label=label), height=500)
        else:
            _render_result(operating_driver_eps(df), height=500)
        st.caption(
            "Table 10.1 đặt EPS cạnh operating metric. Phase 2 dùng driver Trecapital hiện có; Phase 3 sẽ đưa driver theo ngành "
            "(ví dụ volume/ASP/spread, store/SSS, loan growth/NIM...)."
        )

    _formula_audit(formula_prefix)
