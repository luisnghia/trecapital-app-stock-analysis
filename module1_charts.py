from __future__ import annotations

from typing import Iterable

import pandas as pd
import plotly.graph_objects as go

from module1_engine import chart_frame

LABELS = {
    "revenue_bil": "Doanh thu",
    "gross_revenue_bil": "Tổng doanh thu",
    "gross_profit_bil": "Lợi nhuận gộp",
    "net_profit_bil": "LNST",
    "operating_profit_bil": "Operating Profit",
    "core_operating_profit_bil": "Core Operating Profit",
    "financial_income_bil": "Doanh thu tài chính",
    "financial_expense_bil": "Chi phí tài chính",
    "selling_expense_bil": "Chi phí bán hàng",
    "admin_expense_bil": "Chi phí QLDN",
    "tax_expense_bil": "Chi phí thuế TNDN",
    "nopat_bil": "NOPAT",
    "maintenance_capex_bil": "Maintenance Capex",
    "capital_employed_bil": "Capital Employed",
    "avg_capital_employed_bil": "Avg Capital Employed",
    "deployed_capital_bil": "Deployed Capital Li Lu",
    "avg_deployed_capital_bil": "Avg Deployed Capital Li Lu",
    "current_assets_bil": "Current Assets",
    "current_liabilities_bil": "Current Liabilities",
    "working_capital_bil": "Working Capital",
    "roic_working_capital_bil": "Working Capital ROIC MOS/Li Lu",
    "fixed_assets_bil": "Fixed Assets",
    "cash_equivalents_bil": "Tiền & TĐT",
    "short_term_investments_bil": "Đầu tư tài chính ngắn hạn",
    "inventory_change_bil": "Tăng/giảm hàng tồn kho",
    "investment_subsidiary_bil": "Đầu tư vào công ty con/LK",
    "expansion_investment_bil": "Đầu tư mở rộng",
    "total_investment_bil": "Tổng đầu tư",
    "roic_fireant_pct": "ROIC dữ liệu",
    "wacc_pct": "WACC",
    "pretax_profit_bil": "LNTT",
    "cfo_bil": "CFO",
    "cfi_bil": "CFI",
    "cff_bil": "CFF",
    "capex_bil": "Capex",
    "cash_dividend_bil": "Cổ tức tiền mặt đã trả",

    "pretax_profit_bil": "LNTT / NIBT",
    "noncash_adjustments_bil": "Điều chỉnh phi tiền mặt/D&A",
    "working_capital_change_bil": "Thay đổi VLĐ",
    "receivables_change_bil": "Tăng/giảm phải thu",
    "payables_change_bil": "Tăng/giảm phải trả",
    "prepaid_change_bil": "Tăng/giảm trả trước",
    "tax_paid_bil": "Thuế TNDN đã nộp",
    "net_debt_cashflow_bil": "Vay/trả nợ ròng",
    "debt_raised_bil": "Vay nhận được",
    "debt_repaid_bil": "Trả nợ gốc vay",
    "buyback_bil": "Mua cổ phiếu quỹ",
    "cash_and_short_investments_bil": "Tiền + ĐTTC ngắn hạn",
    "cash_and_short_investments_change_bil": "Tăng/giảm tiền + ĐTTC ngắn hạn",
    "fcf_to_net_profit": "FCF/LNST",
    "fcf_to_pretax": "FCF/LNTT",
    "cfo_to_net_profit": "CFO/LNST",
    "cash_dividend_yield_pct": "Tỷ suất cổ tức tiền mặt",
    "year_end_price": "Giá cuối năm",
    "shares_outstanding_mil": "CPLH",
    "free_cash_flow_bil": "Free Cash Flow",
    "owner_earnings_bil": "Owner Earnings",
    "eps_vnd": "EPS",
    "oeps_vnd": "OEPS",
    "roe_pct": "ROE",
    "roe_actual_pct": "ROE thực tế",
    "roa_pct": "ROA",
    "roic_pct": "ROIC chuẩn",
    "roic_operating_profit_pct": "ROIC Operating Profit",
    "roic_owner_earnings_pct": "ROIC Owner Earnings",
    "roic_standard_pct": "ROIC NOPAT/Capital Employed",
    "roic_lilu_pct": "ROIC Li Lu / Deployed",
    "gross_margin_pct": "Gross Margin",
    "core_operating_margin_pct": "Core Operating Margin",
    "net_margin_pct": "Net Margin",
    "ebitda_margin_pct": "EBITDA Margin",
    "financial_income_to_revenue_pct": "Thu nhập tài chính/Doanh thu",
    "asset_turnover": "Asset Turnover",
    "equity_multiplier": "Equity Multiplier",
    "roe_dupont_pct": "ROE DuPont",
    "cfo_to_net_profit": "CFO/LNST",
    "fcf_to_net_profit": "FCF/LNST",
}

# Màu cố định cho các biểu đồ DuPont để dòng tiêu chuẩn trùng màu với cột tương ứng.
DUPONT_COLORS = {
    "roe_pct": "#76B852",
    "roa_pct": "#2E75B6",
    "net_margin_pct": "#C65A11",
    "gross_margin_pct": "#BFBFBF",
}

# Đường giá trị 0: dùng màu đỏ để người xem nhận biết nhanh vùng âm/dương.
ZERO_LINE_COLOR = "#EF4444"
ZERO_LINE_STYLE = {"zeroline": True, "zerolinecolor": ZERO_LINE_COLOR, "zerolinewidth": 2}


def _hover_format_for_unit(unit: str) -> str:
    u = (unit or "").lower()
    if "tỷ" in u:
        return ",.0f"
    if "%" in u:
        return ",.1f"
    if "lần" in u or "hệ số" in u:
        return ",.1f"
    if "đồng" in u or "cp" in u:
        return ",.0f"
    return ",.1f"


def _tick_format_for_unit(unit: str) -> str:
    return _hover_format_for_unit(unit)


def _clean_period_label(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _base_layout(fig: go.Figure, title: str, subtitle: str = "", y_title: str = "") -> go.Figure:
    full_title = title if not subtitle else f"{title}<br><sup>{subtitle}</sup>"
    fig.update_layout(
        title={"text": full_title, "x": 0.02, "xanchor": "left"},
        height=430,
        margin={"l": 20, "r": 20, "t": 76, "b": 36},
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, Arial, sans-serif", "size": 13},
        xaxis={"title": "Kỳ dữ liệu", "type": "category", "showgrid": False, "tickangle": -25},
        yaxis={"title": y_title, "showgrid": True, "gridcolor": "rgba(148,163,184,0.25)", "tickformat": _tick_format_for_unit(y_title), **ZERO_LINE_STYLE},
    )
    return fig


def make_line_fig(df: pd.DataFrame, columns: Iterable[str], title: str, unit: str = "", subtitle: str = "") -> go.Figure:
    """Create an interactive line chart with value tooltips on hover.

    The function uses the already-normalized period order from module1_engine.chart_frame, so annual
    labels remain 2016, 2017, ... and quarters remain Q4/2023, Q1/2024, ... without decimal artifacts.
    """
    plot_df = chart_frame(df, list(columns))
    if plot_df.empty:
        return go.Figure()
    plot_df = plot_df.reset_index().rename(columns={"period": "Kỳ"})
    plot_df["Kỳ"] = plot_df["Kỳ"].map(_clean_period_label)
    fig = go.Figure()
    fmt = _hover_format_for_unit(unit)
    for col in [c for c in columns if c in plot_df.columns]:
        name = LABELS.get(col, col)
        fig.add_trace(
            go.Scatter(
                x=plot_df["Kỳ"],
                y=pd.to_numeric(plot_df[col], errors="coerce"),
                mode="lines+markers",
                name=name,
                line={"width": 2.4},
                marker={"size": 7},
                hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:{fmt}}} {unit}<extra></extra>",
            )
        )
    return _base_layout(fig, title, subtitle=subtitle, y_title=unit)


def make_bar_fig(df: pd.DataFrame, x_col: str, y_col: str, title: str, unit: str = "", subtitle: str = "") -> go.Figure:
    plot_df = df[[x_col, y_col]].dropna().copy() if not df.empty and {x_col, y_col}.issubset(df.columns) else pd.DataFrame()
    if plot_df.empty:
        return go.Figure()
    plot_df[x_col] = plot_df[x_col].map(_clean_period_label)
    label = LABELS.get(y_col, y_col)
    fmt = _hover_format_for_unit(unit)
    fig = go.Figure(
        go.Bar(
            x=plot_df[x_col],
            y=pd.to_numeric(plot_df[y_col], errors="coerce"),
            name=label,
            hovertemplate=f"<b>{label}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:{fmt}}} {unit}<extra></extra>",
        )
    )
    return _base_layout(fig, title, subtitle=subtitle, y_title=unit)


def make_metric_bar(labels: list[str], values: list[float], title: str, unit: str = "%") -> go.Figure:
    df = pd.DataFrame({"Chỉ số": labels, "Giá trị": values}).dropna()
    fmt = _hover_format_for_unit(unit)
    fig = go.Figure(
        go.Bar(
            x=df["Chỉ số"],
            y=pd.to_numeric(df["Giá trị"], errors="coerce"),
            hovertemplate=f"<b>%{{x}}</b><br>Giá trị: %{{y:{fmt}}} {unit}<extra></extra>",
        )
    )
    return _base_layout(fig, title, y_title=unit)


def _plot_df(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    plot_df = chart_frame(df, columns)
    if plot_df.empty:
        return pd.DataFrame()
    plot_df = plot_df.reset_index().rename(columns={"period": "Kỳ"})
    plot_df["Kỳ"] = plot_df["Kỳ"].map(_clean_period_label)
    return plot_df


def make_dupont_profitability_fig(df: pd.DataFrame, title: str = "DUPONT: ROE - ROA - BIÊN LỢI NHUẬN RÒNG") -> go.Figure:
    """Chart like the user's first DuPont screenshot: ROE/ROA/NPM/GPM + benchmark lines."""
    cols = ["roe_pct", "roa_pct", "net_margin_pct", "gross_margin_pct"]
    plot_df = _plot_df(df, cols)
    if plot_df.empty:
        return go.Figure()
    fig = go.Figure()
    for col in cols:
        if col in plot_df.columns:
            name = LABELS.get(col, col)
            fig.add_trace(go.Bar(
                x=plot_df["Kỳ"], y=pd.to_numeric(plot_df[col], errors="coerce"), name=name,
                marker_color=DUPONT_COLORS.get(col),
                hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.1f}}%<extra></extra>",
            ))
    # Benchmark lines: same color as the related bar series, per user request.
    benchmarks = [
        ("Tiêu chuẩn ROE", 20, "roe_pct"),
        ("Tiêu chuẩn Net profit Margin", 10, "net_margin_pct"),
        ("Tiêu chuẩn Gross margin", 30, "gross_margin_pct"),
    ]
    for name, y, color_key in benchmarks:
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=[y] * len(plot_df), mode="lines", name=name,
            line={"width": 3.2, "color": DUPONT_COLORS.get(color_key)},
            hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Chuẩn: {y:,.0f}%<extra></extra>",
        ))
    fig.update_layout(barmode="group")
    return _base_layout(fig, title, subtitle="Dòng tiêu chuẩn dùng cùng màu với cột tương ứng; hover để xem số liệu.", y_title="%")

def make_dupont_driver_fig(df: pd.DataFrame, title: str = "DUPONT: NHÂN TỐ ĐÓNG GÓP VÀO ROE") -> go.Figure:
    """DuPont factor chart: percentage factors on secondary axis, turnover/leverage on primary axis."""
    cols = ["asset_turnover", "equity_multiplier", "roe_pct", "net_margin_pct"]
    plot_df = _plot_df(df, cols)
    if plot_df.empty:
        return go.Figure()
    fig = go.Figure()
    for col in ["asset_turnover", "equity_multiplier"]:
        if col in plot_df.columns:
            name = LABELS.get(col, col)
            fig.add_trace(go.Bar(
                x=plot_df["Kỳ"], y=pd.to_numeric(plot_df[col], errors="coerce"), name=name,
                yaxis="y", hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.1f}} lần<extra></extra>",
            ))
    for col in ["roe_pct", "net_margin_pct"]:
        if col in plot_df.columns:
            name = LABELS.get(col, col)
            fig.add_trace(go.Scatter(
                x=plot_df["Kỳ"], y=pd.to_numeric(plot_df[col], errors="coerce"), mode="lines+markers", name=name,
                yaxis="y2", line={"width": 2.6, "color": DUPONT_COLORS.get(col)}, marker={"size": 7, "color": DUPONT_COLORS.get(col)},
                hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.1f}}%<extra></extra>",
            ))
    fig.update_layout(
        barmode="group",
        yaxis={"title": "Lần", "showgrid": True, "gridcolor": "rgba(148,163,184,0.25)", "tickformat": ",.1f", **ZERO_LINE_STYLE},
        yaxis2={"title": "%", "overlaying": "y", "side": "right", "showgrid": False, "tickformat": ",.1f", **ZERO_LINE_STYLE},
    )
    return _base_layout(fig, title, subtitle="Tách ROE thành biên lợi nhuận, vòng quay tài sản và đòn bẩy tài chính.", y_title="Lần")


def make_roic_investment_fig(df: pd.DataFrame, title: str = "ĐẦU TƯ VÀ HIỆU QUẢ ĐẦU TƯ ROIC") -> go.Figure:
    """Investment/ROIC chart: bars for investment, lines only for ROIC Operating Profit and WACC."""
    cols = ["investment_subsidiary_bil", "expansion_investment_bil", "inventory_change_bil", "total_investment_bil", "roic_operating_profit_pct", "wacc_pct"]
    plot_df = _plot_df(df, cols)
    if plot_df.empty:
        return go.Figure()
    fig = go.Figure()
    bar_cols = ["investment_subsidiary_bil", "expansion_investment_bil", "inventory_change_bil"]
    for col in bar_cols:
        if col in plot_df.columns:
            name = LABELS.get(col, col)
            fig.add_trace(go.Bar(
                x=plot_df["Kỳ"], y=pd.to_numeric(plot_df[col], errors="coerce"), name=name,
                yaxis="y", hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.0f}} tỷ đồng<extra></extra>",
            ))
    if "total_investment_bil" in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=pd.to_numeric(plot_df["total_investment_bil"], errors="coerce"),
            mode="lines+markers", name="Tổng đầu tư", yaxis="y",
            line={"width": 3}, marker={"size": 8},
            hovertemplate="<b>Tổng đầu tư</b><br>Kỳ: %{x}<br>Giá trị: %{y:,.0f} tỷ đồng<extra></extra>",
        ))
    if "roic_operating_profit_pct" in plot_df.columns and pd.to_numeric(plot_df["roic_operating_profit_pct"], errors="coerce").notna().any():
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=pd.to_numeric(plot_df["roic_operating_profit_pct"], errors="coerce"),
            mode="lines+markers", name="ROIC Operating Profit", yaxis="y2",
            line={"width": 3.4}, marker={"size": 8},
            hovertemplate="<b>ROIC Operating Profit</b><br>Kỳ: %{x}<br>Giá trị: %{y:,.1f}%<extra></extra>",
        ))
    if "wacc_pct" in plot_df.columns and pd.to_numeric(plot_df["wacc_pct"], errors="coerce").notna().any():
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=pd.to_numeric(plot_df["wacc_pct"], errors="coerce"),
            mode="lines+markers", name="WACC", yaxis="y2",
            line={"width": 3.0, "dash": "dash"}, marker={"size": 7},
            hovertemplate="<b>WACC</b><br>Kỳ: %{x}<br>Giá trị: %{y:,.1f}%<extra></extra>",
        ))
    fig.update_layout(
        barmode="relative",
        yaxis={"title": "Tỷ đồng", "showgrid": True, "gridcolor": "rgba(148,163,184,0.25)", "tickformat": ",.0f", **ZERO_LINE_STYLE},
        yaxis2={"title": "%", "overlaying": "y", "side": "right", "showgrid": False, "tickformat": ",.1f", **ZERO_LINE_STYLE},
    )
    return _base_layout(fig, title, subtitle="Đường chính: ROIC Operating Profit. Đường đối chiếu: WACC doanh nghiệp tự tính. ROIC > WACC cho thấy doanh nghiệp có thể tạo giá trị trên vốn sử dụng.", y_title="Tỷ đồng")


def make_fcf_generation_fig(df: pd.DataFrame, title: str = "FCF: QUY TRÌNH SINH TIỀN TỪ LNTT ĐẾN FCF") -> go.Figure:
    """FCF-Years/Quarters style bridge: NIBT + D&A + working capital + capex -> FCF."""
    cols = ["pretax_profit_bil", "noncash_adjustments_bil", "working_capital_change_bil", "capex_bil", "free_cash_flow_bil"]
    plot_df = _plot_df(df, cols)
    if plot_df.empty:
        return go.Figure()
    fig = go.Figure()
    for col in ["pretax_profit_bil", "noncash_adjustments_bil", "working_capital_change_bil", "capex_bil"]:
        if col in plot_df.columns:
            name = LABELS.get(col, col)
            fig.add_trace(go.Bar(
                x=plot_df["Kỳ"], y=pd.to_numeric(plot_df[col], errors="coerce"), name=name,
                yaxis="y", hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.0f}} tỷ đồng<extra></extra>",
            ))
    if "free_cash_flow_bil" in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=pd.to_numeric(plot_df["free_cash_flow_bil"], errors="coerce"),
            mode="lines+markers", name="Free Cash Flow", line={"width": 3.2}, marker={"size": 8},
            hovertemplate="<b>Free Cash Flow</b><br>Kỳ: %{x}<br>Giá trị: %{y:,.0f} tỷ đồng<extra></extra>",
        ))
    fig.update_layout(barmode="relative")
    return _base_layout(fig, title, subtitle="LNTT + điều chỉnh phi tiền mặt + thay đổi VLĐ + Capex = FCF. Đường 0 màu đỏ để nhận diện âm/dương.", y_title="Tỷ đồng")


def make_fcf_usage_fig(df: pd.DataFrame, title: str = "FCF: PHÂN TÍCH SỬ DỤNG DÒNG TIỀN") -> go.Figure:
    """Cash-use chart: FCF versus debt, dividend, capex, investments and cash/STI change."""
    cols = ["free_cash_flow_bil", "net_debt_cashflow_bil", "cash_dividend_bil", "capex_bil", "investment_subsidiary_bil", "buyback_bil", "cash_and_short_investments_change_bil"]
    plot_df = _plot_df(df, cols)
    if plot_df.empty:
        return go.Figure()
    fig = go.Figure()
    for col in ["net_debt_cashflow_bil", "cash_dividend_bil", "capex_bil", "investment_subsidiary_bil", "buyback_bil"]:
        if col in plot_df.columns and pd.to_numeric(plot_df[col], errors="coerce").notna().any():
            name = LABELS.get(col, col)
            fig.add_trace(go.Bar(
                x=plot_df["Kỳ"], y=pd.to_numeric(plot_df[col], errors="coerce"), name=name,
                hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.0f}} tỷ đồng<extra></extra>",
            ))
    if "free_cash_flow_bil" in plot_df.columns:
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=pd.to_numeric(plot_df["free_cash_flow_bil"], errors="coerce"),
            mode="lines+markers", name="FCF", line={"width": 3.0}, marker={"size": 8},
            hovertemplate="<b>FCF</b><br>Kỳ: %{x}<br>Giá trị: %{y:,.0f} tỷ đồng<extra></extra>",
        ))
    if "cash_and_short_investments_change_bil" in plot_df.columns and pd.to_numeric(plot_df["cash_and_short_investments_change_bil"], errors="coerce").notna().any():
        fig.add_trace(go.Scatter(
            x=plot_df["Kỳ"], y=pd.to_numeric(plot_df["cash_and_short_investments_change_bil"], errors="coerce"),
            mode="lines+markers", name="Tăng/giảm tiền + ĐTTC ngắn hạn", line={"width": 2.6, "dash": "dot"}, marker={"size": 7},
            hovertemplate="<b>Tăng/giảm tiền + ĐTTC ngắn hạn</b><br>Kỳ: %{x}<br>Giá trị: %{y:,.0f} tỷ đồng<extra></extra>",
        ))
    fig.update_layout(barmode="relative")
    return _base_layout(fig, title, subtitle="So sánh FCF với vay/trả nợ, cổ tức, capex, đầu tư và tăng/giảm tiền + ĐTTC trong kỳ.", y_title="Tỷ đồng")


def make_fcf_conversion_fig(df: pd.DataFrame, title: str = "FCF CONVERSION: CHẤT LƯỢNG CHUYỂN HÓA LỢI NHUẬN THÀNH TIỀN") -> go.Figure:
    cols = ["fcf_to_net_profit", "fcf_to_pretax", "cfo_to_net_profit"]
    plot_df = _plot_df(df, cols)
    if plot_df.empty:
        return go.Figure()
    fig = go.Figure()
    for col in cols:
        if col in plot_df.columns and pd.to_numeric(plot_df[col], errors="coerce").notna().any():
            name = LABELS.get(col, col)
            y = pd.to_numeric(plot_df[col], errors="coerce") * 100
            fig.add_trace(go.Scatter(
                x=plot_df["Kỳ"], y=y, mode="lines+markers", name=name,
                line={"width": 2.8}, marker={"size": 7},
                hovertemplate=f"<b>{name}</b><br>Kỳ: %{{x}}<br>Giá trị: %{{y:,.1f}}%<extra></extra>",
            ))
    fig.add_trace(go.Scatter(
        x=plot_df["Kỳ"], y=[100] * len(plot_df), mode="lines", name="Mốc 100%",
        line={"width": 2, "dash": "dash"}, hovertemplate="<b>Mốc 100%</b><br>Kỳ: %{x}<extra></extra>",
    ))
    return _base_layout(fig, title, subtitle="FCF/LNST, FCF/LNTT và CFO/LNST càng bền vững trên 100% càng thể hiện lợi nhuận chuyển hóa tốt thành tiền.", y_title="%")
