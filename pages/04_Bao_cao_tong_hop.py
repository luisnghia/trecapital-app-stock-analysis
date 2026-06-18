from __future__ import annotations

import pandas as pd
import streamlit as st
from tre_full_width import apply_full_width

# Import module2_dashboard first: it owns the shared page config, theme CSS, data loaders and sidebar navigation.
import module2_dashboard as md
from module2_engine import (
    build_module2_valuation_table,
    build_valuation_range,
    build_porter_moat_scorecard,
    build_value_chain_table,
    build_risk_scenario_table,
    build_module2_summary,
    load_assumptions,
)
from report_exporter import build_report_package, render_report_package_as_app_page


APP_VERSION = "secure-ui-current"
SOURCE_DISPLAY_TO_INTERNAL = {
    "Tự động": "Tự động từ dữ liệu tổng quan",
    "Dữ liệu ưu tiên 1": "FireAnt + Vietstock",
    "Dữ liệu ưu tiên 2": "FireAnt",
    "Dữ liệu ưu tiên 3": "Vietstock",
    "Dữ liệu tích hợp": "Financial tích hợp",
    "Dữ liệu mẫu": "CSV mẫu tích hợp",
}
SOURCE_OPTIONS = list(SOURCE_DISPLAY_TO_INTERNAL.keys())


def _default_ticker() -> str:
    for key in ["active_ticker", "module2_ticker", "module1_ticker", "shared_ticker", "last_query_ticker"]:
        value = md._safe_ticker(str(st.session_state.get(key, "")))
        if value:
            return value
    return "DCM"


def render_consolidated_report_page() -> None:
    md._inject_runtime_ui_css()
    md._render_brand_page_header(
        "📄 Báo cáo tổng hợp toàn bộ nội dung",
        "Render toàn bộ từng tab của Tổng quan doanh nghiệp + Định giá chuyên sâu + So sánh doanh nghiệp trên một trang dài để in/Save as PDF, giữ format giống app nhất có thể.",
    )

    available_tickers = md._available_financial_tickers_cached(str(md.BUNDLED_XLSM)) if md.BUNDLED_XLSM.exists() else []

    with st.sidebar:
        md._render_tre_sidebar_nav()
        st.header("Thiết lập báo cáo tổng hợp")
        source_display = st.selectbox("Chế độ dữ liệu tài chính", SOURCE_OPTIONS, index=0, key="full_report_source")
        source = SOURCE_DISPLAY_TO_INTERNAL.get(source_display, source_display)
        ticker = st.text_input("Mã cổ phiếu", value=_default_ticker(), max_chars=12, key="full_report_ticker").upper().strip()
        if source == "Financial tích hợp" and available_tickers:
            chosen = st.selectbox("Mã có đủ BCTC trong dữ liệu tích hợp", ["-- Giữ mã đang nhập --"] + available_tickers, index=0, key="full_report_financial_ticker")
            if chosen != "-- Giữ mã đang nhập --":
                ticker = chosen
        target_mos_pct = st.selectbox(
            "Mức MOS yêu cầu (%)",
            md.MOS_OPTIONS_GLOBAL,
            index=md.MOS_OPTIONS_GLOBAL.index(md._normalize_mos_value(st.session_state.get("target_mos_pct", 50))),
            key="full_report_mos",
            help="MOS dùng chung để tính dải định giá và khuyến nghị trong báo cáo.",
        )
        st.session_state["target_mos_pct"] = float(target_mos_pct)
        table_mode = st.radio(
            "Độ dài bảng khi in PDF",
            ["Đầy đủ", "Gọn để in nhanh"],
            index=0,
            help="Đầy đủ giữ toàn bộ dòng; Gọn chỉ hiển thị tối đa 40 dòng mỗi bảng để PDF nhẹ hơn.",
        )
        reload_report = st.button("🔄 Cập nhật dữ liệu báo cáo", use_container_width=True)
        st.caption("PDF đẹp nhất: bấm nút in trong trang báo cáo, chọn A4 ngang và bật Background graphics.")

    if reload_report:
        md._load_overview_cached.clear()
        md._load_timeseries_cached.clear()
        st.toast("Đã làm mới cache đọc dữ liệu báo cáo.")

    ticker = md._safe_ticker(ticker) or _default_ticker()
    st.session_state["module2_ticker"] = ticker
    st.session_state["shared_ticker"] = ticker

    try:
        company, annual_df, quarterly_df, source_label, paths = md._load_data(ticker, source)
    except Exception as exc:
        st.error(f"Không tải được dữ liệu để dựng báo cáo tổng hợp cho {ticker}: {exc}")
        st.stop()

    assumptions = load_assumptions(md.ASSUMPTIONS_PATH)
    valuation_df = build_module2_valuation_table(company, annual_df, assumptions) if annual_df is not None and not annual_df.empty else pd.DataFrame()
    moat_df = build_porter_moat_scorecard(company, annual_df) if annual_df is not None else pd.DataFrame()
    value_chain_df = build_value_chain_table(company, annual_df) if annual_df is not None else pd.DataFrame()
    value_range = build_valuation_range(valuation_df, getattr(company, "current_price", None), float(target_mos_pct)) if not valuation_df.empty else None
    scenario_df = build_risk_scenario_table(company, annual_df, value_range) if value_range is not None and annual_df is not None and not annual_df.empty else pd.DataFrame()
    module2_summary = build_module2_summary(company, annual_df, valuation_df, moat_df) if annual_df is not None and not annual_df.empty else "Chưa đủ dữ liệu để tạo tóm tắt Định giá chuyên sâu."

    peer_df = st.session_state.get("peer_compare_result", pd.DataFrame())
    if not isinstance(peer_df, pd.DataFrame):
        peer_df = pd.DataFrame()
    web_df = st.session_state.get("module2_web_table", pd.DataFrame())
    if not isinstance(web_df, pd.DataFrame):
        web_df = pd.DataFrame()

    package = build_report_package(
        company,
        annual_df,
        quarterly_df,
        valuation_df=valuation_df,
        moat_df=moat_df,
        value_chain_df=value_chain_df,
        scenario_df=scenario_df,
        peer_df=peer_df,
        web_df=web_df,
        assumptions=assumptions,
        source_label="Dữ liệu nội bộ",
        paths=[],
        target_mos_pct=float(target_mos_pct),
        module2_summary=module2_summary,
    )

    max_rows = None if table_mode == "Đầy đủ" else 40
    render_report_package_as_app_page(package, show_export_hint=True, table_height=420, max_rows_per_table=max_rows)


render_consolidated_report_page()
apply_full_width()
