from __future__ import annotations

import pandas as pd
import streamlit as st

from ..services.portfolio_extensions import is_watchlisted, set_watchlist
from ..services.watchlist_v2 import list_watchlist_rows_v2, refresh_watchlist_cagrs_if_changed
from . import page as _page
from .present import THESIS_SYMBOL


def _display_dataframe(rows):
    out = []
    for x in rows:
        inv = _page._inventory_display_row(x, source=f"Review #{x.get('latest_review_id') or '—'}")
        out.append({
            "Mã CP": x.get("ticker"),
            "Doanh nghiệp": x.get("company_name"),
            "Review mới nhất": x.get("latest_review_as_of"),
            "Có Table 1.2": "✓" if x.get("latest_review_has_inventory") else "—",
            "CAGR DT 5Y": None if x.get("revenue_cagr_5y") is None else float(x.get("revenue_cagr_5y")) * 100,
            "CAGR LN 5Y": None if x.get("profit_cagr_5y") is None else float(x.get("profit_cagr_5y")) * 100,
            "CAGR kỳ": x.get("cagr_source_period"),
            **inv,
            "Quality 1.1": x.get("quality_tally"),
            "Checklist": x.get("checklist_answered"),
            "Critical Unknowns": x.get("critical_unknowns"),
            "Red Flags": x.get("red_flags"),
            "Δ Thesis": THESIS_SYMBOL.get(x.get("thesis_direction"), "?"),
        })
    return pd.DataFrame(out)


def _style(df: pd.DataFrame):
    if df.empty:
        return df.style
    styler = _page._style_inventory(df)
    pct = {c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}%") for c in ["CAGR DT 5Y", "CAGR LN 5Y"] if c in df.columns}
    return styler.format(pct, na_rep="—")


def _open_ticker(ticker: str, current_ticker: str) -> None:
    ticker = str(ticker or "").strip().upper()
    if not ticker or ticker == str(current_ticker or "").strip().upper():
        return
    # Do not relabel the old active CSV bundle as the new ticker. Clear it so the normal Trecapital
    # live pipeline fetches the selected watchlist company on the next rerun.
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
        st.session_state["checklist_last_admin_message"] = f"{'Đã thêm' if not active else 'Đã bỏ'} {ticker} {'vào' if not active else 'khỏi'} Watchlist."
        st.rerun()


def render_watchlist_v2(repo, current_company_ref_id: int, current_ticker: str, *, actor: str, data_provider) -> None:
    st.markdown("### ⭐ Watchlist — Opportunity Inventory")
    st.caption(
        "Mỗi mã dùng Table 1.2 của review mới nhất. Nếu review mới nhất chưa lưu Table 1.2, app để trống thay vì lấy lùi review cũ. "
        "CAGR 5Y dùng FY canonical của Trecapital và không tính khi endpoint lợi nhuận ≤ 0."
    )
    c1, c2 = st.columns([1.2, 3.8])
    if is_watchlisted(repo, current_company_ref_id):
        if c1.button("↻ Cập nhật CAGR mã hiện tại", use_container_width=True, key=f"refresh_watch_cagr_{current_company_ref_id}"):
            changed = refresh_watchlist_cagrs_if_changed(repo, current_company_ref_id, provider=data_provider, actor=actor)
            st.session_state["checklist_last_admin_message"] = "Đã cập nhật CAGR Watchlist." if changed else "CAGR Watchlist đã là dữ liệu mới nhất; không ghi DB lại."
            st.rerun()
    else:
        c1.caption("Mã hiện tại chưa ở Watchlist.")
    c2.caption("Refresh là thao tác chủ động; app không ghi/upsert Watchlist mỗi lần đổi Question hoặc rerun.")

    rows = list_watchlist_rows_v2(repo)
    if not rows:
        st.info("Watchlist đang trống. Dùng nút ☆ Đưa doanh nghiệp vào Watchlist ở đầu trang.")
        return
    df = _display_dataframe(rows)
    st.caption("Chọn một dòng/mã để mở Investment Checklist của doanh nghiệp đó.")
    try:
        event = st.dataframe(
            _style(df),
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
