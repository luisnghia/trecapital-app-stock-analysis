from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services.portfolio_extensions import is_watchlisted, set_watchlist
from ..services.watchlist_v2 import (
    has_watchlist_financial_cache,
    list_watchlist_rows_v2,
    refresh_watchlist_cagrs_if_changed,
)
from . import page as _page
from .portfolio_extensions import APRICOT_TEXT, APRICOT_YELLOW


_DISPLAY_COLUMNS = {
    "TEV", "EBIT", "EBITDA", "Normalized earnings", "TEV/EBIT", "TEV/EBITDA", "TEV/Norm.E",
    "Pre-tax yield", "Total Debt", "Debt/EBITDA", "EBIT/Interest", "FCF", "FCF Yield EV",
    "FCF Yield Mkt", "CCC", "Market cap", "Giá", "FCF est./share", "Target", "MOS",
}


def _display_dataframe(rows):
    out = []
    adjusted_by_row: dict[int, set[str]] = {}
    for idx, x in enumerate(rows):
        inv = _page._inventory_display_row(x, period_key="financial_as_of_date", source="Trecapital latest")
        adjusted = {str(v) for v in (x.get("analyst_adjusted_metrics") or [])}
        adjusted_by_row[idx] = adjusted
        out.append({
            "Mã CP": x.get("ticker"),
            "Doanh nghiệp": x.get("company_name"),
            "Kỳ dữ liệu": x.get("financial_as_of_date"),
            "CAGR DT 5Y": None if x.get("revenue_cagr_5y") is None else float(x.get("revenue_cagr_5y")) * 100,
            "CAGR LN 5Y": None if x.get("profit_cagr_5y") is None else float(x.get("profit_cagr_5y")) * 100,
            "CAGR kỳ": x.get("cagr_source_period"),
            **inv,
        })
    return pd.DataFrame(out), adjusted_by_row


def _style(df: pd.DataFrame, adjusted_by_row: dict[int, set[str]]):
    if df.empty:
        return df.style
    styler = _page._style_inventory(df)
    pct = {c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}%") for c in ["CAGR DT 5Y", "CAGR LN 5Y"] if c in df.columns}
    styler = styler.format(pct, na_rep="—")

    def paint(data):
        styles = pd.DataFrame("", index=data.index, columns=data.columns)
        for idx, metrics in adjusted_by_row.items():
            if idx not in styles.index:
                continue
            for metric in metrics:
                if metric in styles.columns and metric in _DISPLAY_COLUMNS:
                    styles.at[idx, metric] = (
                        f"background-color:{APRICOT_YELLOW}!important;"
                        f"color:{APRICOT_TEXT}!important;font-weight:900"
                    )
        return styles

    return styler.apply(paint, axis=None)


def _open_ticker(ticker: str, current_ticker: str) -> None:
    ticker = str(ticker or "").strip().upper()
    if not ticker or ticker == str(current_ticker or "").strip().upper():
        return
    # Clear the old active bundle so the normal Trecapital live pipeline fetches the selected ticker.
    for key in (
        "active_ticker", "active_overview_csv", "active_year_csv", "active_quarter_csv", "active_source_label",
        "_last_auto_sync_attempt", "checklist_live_load_diagnostics",
    ):
        st.session_state.pop(key, None)
    for key in ("shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker"):
        st.session_state[key] = ticker
    st.session_state["checklist_section_global"] = "🏠 Research Home"
    st.rerun()


def render_watchlist_toggle_v2(repo, company_ref_id: int, ticker: str, *, actor: str, data_provider) -> None:
    active = is_watchlisted(repo, company_ref_id)
    label = "★ Đang trong Watchlist — bấm để bỏ" if active else "☆ Đưa doanh nghiệp vào Watchlist"
    if st.button(label, key=f"watchlist_toggle_v2_{company_ref_id}", use_container_width=True):
        set_watchlist(repo, company_ref_id, active=not active, actor=actor, provider=data_provider)
        if not active:
            refresh_watchlist_cagrs_if_changed(repo, company_ref_id, provider=data_provider, actor=actor)
        st.session_state["checklist_last_admin_message"] = f"{'Đã thêm' if not active else 'Đã bỏ'} {ticker} {'vào' if not active else 'khỏi'} Watchlist."
        st.rerun()


def render_watchlist_v2(repo, current_company_ref_id: int, current_ticker: str, *, actor: str, data_provider) -> None:
    st.markdown("### ⭐ Watchlist — Opportunity Inventory")
    st.caption(
        "Watchlist lấy dữ liệu tài chính mới nhất từ Trecapital Data Layer, độc lập với kỳ review. "
        "Review chỉ là lịch sử nghiên cứu; không quyết định dòng dữ liệu tài chính hiển thị ở Watchlist. "
        "CAGR 5Y dùng FY canonical của Trecapital và không tính khi endpoint lợi nhuận ≤ 0."
    )

    active = is_watchlisted(repo, current_company_ref_id)
    # One-time bootstrap for watchlist rows created before the latest-financial cache was introduced.
    if active and not has_watchlist_financial_cache(repo, current_company_ref_id):
        refresh_watchlist_cagrs_if_changed(repo, current_company_ref_id, provider=data_provider, actor=actor)

    c1, c2 = st.columns([1.45, 3.55])
    if active:
        if c1.button("↻ Cập nhật dữ liệu tài chính & CAGR", use_container_width=True, key=f"refresh_watch_fin_{current_company_ref_id}"):
            changed = refresh_watchlist_cagrs_if_changed(repo, current_company_ref_id, provider=data_provider, actor=actor)
            st.session_state["checklist_last_admin_message"] = (
                "Đã cập nhật dữ liệu tài chính/CAGR Watchlist." if changed
                else "Watchlist đã dùng dữ liệu tài chính/CAGR mới nhất; không ghi DB lại."
            )
            st.rerun()
    else:
        c1.caption("Mã hiện tại chưa ở Watchlist.")
    c2.caption(
        "Khi thêm mã, app lưu ngay snapshot dữ liệu tài chính mới nhất. Sau này dùng nút cập nhật khi BCTC/giá/định giá thay đổi; "
        "app không ghi DB ở mỗi lần đổi Question hoặc rerun."
    )

    rows = list_watchlist_rows_v2(repo)
    if not rows:
        st.info("Watchlist đang trống. Dùng nút ☆ Đưa doanh nghiệp vào Watchlist ở đầu trang.")
        return
    df, adjusted_by_row = _display_dataframe(rows)
    missing = [str(x.get("ticker") or "") for x in rows if not x.get("has_financial_cache")]
    if missing:
        st.warning("Chưa có snapshot dữ liệu tài chính mới cho: " + ", ".join(missing) + ". Mở mã và bấm cập nhật Watchlist.")
    st.caption("Chọn một dòng/mã để mở Investment Checklist của doanh nghiệp đó. Ô analyst correction được tô vàng hoa mai.")
    try:
        event = st.dataframe(
            _style(df, adjusted_by_row),
            use_container_width=True,
            hide_index=True,
            height=min(610, 38 * len(df) + 90),
            key="investment_watchlist_table_v2",
            on_select="rerun",
            selection_mode="single-row",
        )
        selection = getattr(event, "selection", None)
        selected_rows = list(getattr(selection, "rows", []) or []) if selection is not None else []
        if selected_rows:
            _open_ticker(df.iloc[selected_rows[0]]["Mã CP"], current_ticker)
    except TypeError:
        ticker = st.selectbox("Mở mã từ Watchlist", df["Mã CP"].tolist(), key="watchlist_open_fallback_v2")
        if st.button("Mở Investment Checklist", use_container_width=True, key="watchlist_open_button_v2"):
            _open_ticker(ticker, current_ticker)
