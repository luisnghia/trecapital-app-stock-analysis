from __future__ import annotations

"""Phase 3A Industry & Moat UI. No network, AI, or assessment writes."""

from typing import Any

import pandas as pd
import streamlit as st

from module1_engine import CompanyOverview, ensure_derived_metrics
from module2_engine import build_porter_moat_scorecard, build_value_chain_table

from ..industry_overlay import (
    FINANCIAL_TYPES,
    QUESTION_MAP,
    build_driver_coverage,
    build_industry_kpi_table,
    build_metric_coverage,
    canonical_annual_df,
)
from .book_guidance import render_book_guidance
from .peer_snapshot import render_peer_snapshot


_PCT = {
    "Biên gộp", "Biên HĐ cốt lõi", "Biên ròng", "ROIC", "ROE", "ROA", "NIM", "CASA", "LDR", "NPL",
    "Nợ nhóm 2", "LLR", "CAR", "CIR", "Credit cost", "Tăng trưởng tín dụng", "Tăng trưởng tiền gửi",
    "Tăng trưởng phí BH", "Loss ratio", "Combined ratio", "Lợi suất đầu tư", "Biên khả năng thanh toán",
    "Biên môi giới", "Tỷ trọng tự doanh", "Tài sản thanh khoản", "Tỷ lệ đạt %", "Trọng số %",
}
_RATIO = {"CFO/LNST", "Net Debt/EBITDA", "Dư nợ margin/VCSH"}
_MONEY = {"Doanh thu", "FCF", "Doanh thu môi giới", "Điểm đạt"}
_DAYS = {"CCC"}


def _display(df: pd.DataFrame) -> pd.DataFrame:
    shown = df.copy()
    for col in shown.columns:
        def fmt(value: Any, *, name=str(col)) -> str:
            if value is None or pd.isna(value):
                return "—"
            if name in _PCT:
                return f"{float(value):,.1f}%"
            if name in _RATIO:
                return f"{float(value):,.1f}x"
            if name in _MONEY:
                return f"{float(value):,.0f}"
            if name in _DAYS:
                return f"{float(value):,.0f} ngày"
            return str(value)
        shown[col] = shown[col].map(fmt)
    return shown


def _overview(host, integration, annual_df: pd.DataFrame) -> CompanyOverview:
    pre = integration.get_inventory_prefill()
    latest = annual_df.iloc[-1] if not annual_df.empty else {}
    get = latest.get if hasattr(latest, "get") else lambda _key, default=None: default
    return CompanyOverview(
        ticker=host.company.ticker,
        company_name=host.company.company_name,
        exchange=host.company.exchange,
        industry=host.company.industry_name,
        sub_industry="",
        market_cap_bil=getattr(pre, "market_cap", None),
        shares_outstanding_mil=getattr(pre, "shares_outstanding_mil", None),
        current_price=getattr(pre, "market_price", None),
        eps=get("eps_vnd"),
        pe=get("pe"),
        pb=get("pb"),
        ps=get("ps"),
        roe=get("roe_actual_pct", get("roe_pct")),
        roa=get("roa_actual_pct", get("roa_pct")),
        roic=get("roic_standard_pct", get("roic_pct")),
        updated_at=str(get("period", get("year", "")) or ""),
    )


def render_industry_overlay(
    integration,
    host,
    data_provider,
    *,
    repo=None,
    company_ref_id: int | None = None,
    review: dict[str, Any] | None = None,
    actor: str = "analyst",
) -> None:
    company_type = str(host.company.company_type or "normal").lower()
    st.markdown("### 🏭 Industry & Moat — Phase 3A")
    st.caption(
        "Checkpoint tiếp theo: ghép KPI theo ngành, operating drivers và Porter/Value Chain vào Checklist. "
        "Toàn bộ số tài chính chỉ đọc từ Trecapital Data Layer; bảng này không gọi AI, không tự ghi assessment."
    )
    render_book_guidance("Industry & Moat Overlay", expanded=False)

    raw = canonical_annual_df(data_provider)
    if raw.empty:
        st.warning("Không có annual/TTM Data Layer để dựng Industry Overlay. App giữ trạng thái Research gap, không tự điền 0.")
        st.dataframe(QUESTION_MAP, use_container_width=True, hide_index=True)
        return

    st.markdown(f"**Overlay hiệu lực:** `{company_type}` · **Ngành:** {host.company.industry_name or 'Chưa gán ngành'}")
    kpi = build_industry_kpi_table(raw, company_type)
    st.markdown("#### KPI theo ngành — tối đa 10 kỳ")
    if kpi.empty or len(kpi.columns) <= 1:
        st.info("Chưa có KPI ngành nào trong Data Layer hiện tại.")
    else:
        st.dataframe(_display(kpi.iloc[::-1].reset_index(drop=True)), use_container_width=True, hide_index=True, height=min(500, 38 * len(kpi) + 90))
    with st.expander("Coverage KPI & Research gaps", expanded=False):
        st.dataframe(build_metric_coverage(raw, company_type), use_container_width=True, hide_index=True)

    st.markdown("#### Operating Driver → EPS bridge")
    drivers = build_driver_coverage(raw, company_type)
    st.dataframe(drivers, use_container_width=True, hide_index=True)
    missing = drivers[drivers["Trạng thái"].eq("Research gap")]
    if not missing.empty:
        st.caption("Field còn thiếu được giữ là Research gap cho Q22/Q55–Q57; app không thay bằng doanh thu một cách âm thầm.")

    if company_type in FINANCIAL_TYPES:
        st.warning(
            "Doanh nghiệp tài chính: khóa score Porter công nghiệp (FCF/CCC/TEV-EBITDA không phải trục chính). "
            "Moat cần đánh giá bằng franchise, funding, underwriting/risk, vốn và KPI ngành ở trên."
        )
    else:
        annual = ensure_derived_metrics(raw)
        company = _overview(host, integration, annual)
        moat = build_porter_moat_scorecard(company, annual)
        total = moat.attrs.get("total_score")
        level = moat.attrs.get("level", "Chưa đủ dữ liệu")
        st.markdown("#### Porter / Moat scorecard — evidence, không phải kết luận")
        if total is not None:
            st.metric("Moat evidence score", f"{float(total):.1f}/100", help="Điểm định lượng định hướng kiểm tra; analyst vẫn phải xác minh bằng chứng định tính.")
            st.caption(f"Tín hiệu máy: {level}. Trường hợp LNST âm, CFO/LNST và FCF/LNST bị khóa N/A; âm/âm không nhận điểm.")
        st.dataframe(_display(moat), use_container_width=True, hide_index=True, height=440)

        st.markdown("#### Porter Value Chain")
        value_chain = build_value_chain_table(company, annual)
        st.dataframe(_display(value_chain), use_container_width=True, hide_index=True, height=430)

    if repo is not None and company_ref_id is not None:
        render_peer_snapshot(
            repo,
            company_ref_id=int(company_ref_id),
            review=review,
            base_ticker=host.company.ticker,
            actor=actor,
        )
    else:
        st.markdown("#### ⚖️ Peer Snapshot & Ranking — Phase 3B")
        st.caption("Chưa có repository/review context; peer ranking vẫn có thể chạy tại trang So sánh doanh nghiệp.")

    st.markdown("#### Bridge sang Checklist")
    st.dataframe(QUESTION_MAP, use_container_width=True, hide_index=True)
    st.info("Peer ranking dùng trang So sánh doanh nghiệp hiện có; Phase 3B chỉ lưu khi analyst xác nhận và không tải peer trong mỗi lần đổi Question.")
    try:
        st.page_link("pages/03_So_sanh_doanh_nghiep.py", label="Mở So sánh doanh nghiệp", icon="⚖️")
    except Exception:
        pass


__all__ = ["render_industry_overlay"]
