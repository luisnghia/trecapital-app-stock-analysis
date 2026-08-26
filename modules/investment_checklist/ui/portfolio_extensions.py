from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable

import pandas as pd
import streamlit as st

from ..phase2_formula_assumptions import PHASE2_FORMULA_ROWS
from ..services.formulas import inventory_metrics
from ..services.portfolio_extensions import (
    is_watchlisted,
    latest_table_overrides,
    list_watchlist_rows,
    override_value,
    refresh_watchlist_cagrs,
    save_table_override,
    set_watchlist,
    table_override_history,
)
from . import page as _page
from . import quant_tools as _qt
from .present import THESIS_SYMBOL


APRICOT_YELLOW = "#F6C344"
APRICOT_TEXT = "#4A3100"


def render_wrapped_table(df: pd.DataFrame, *, css_class: str = "checklist-wrapped-table") -> None:
    """Render long formula/assumption text with real wrapping instead of clipped dataframe cells."""
    if df is None or df.empty:
        st.caption("Chưa có dữ liệu.")
        return
    html = df.to_html(index=False, escape=True, border=0, classes=[css_class])
    st.markdown(
        f"""
        <style>
        .{css_class}-wrap{{width:100%;overflow-x:auto;margin:.35rem 0 1rem}}
        table.{css_class}{{width:100%;table-layout:fixed;border-collapse:collapse;font-size:.86rem}}
        table.{css_class} th{{background:#F6F2E8;color:#173F38;font-weight:800;padding:.55rem;border:1px solid #DDD4C2;white-space:normal;overflow-wrap:anywhere}}
        table.{css_class} td{{padding:.52rem;vertical-align:top;border:1px solid #E5DED0;white-space:normal!important;word-break:break-word;overflow-wrap:anywhere;line-height:1.38}}
        table.{css_class} th:nth-child(1),table.{css_class} td:nth-child(1){{width:17%}}
        table.{css_class} th:nth-child(2),table.{css_class} td:nth-child(2){{width:18%}}
        table.{css_class} th:nth-child(3),table.{css_class} td:nth-child(3){{width:31%}}
        table.{css_class} th:nth-child(4),table.{css_class} td:nth-child(4){{width:22%}}
        table.{css_class} th:nth-child(5),table.{css_class} td:nth-child(5){{width:12%}}
        </style>
        <div class="{css_class}-wrap">{html}</div>
        """,
        unsafe_allow_html=True,
    )


def _override_period_key(row: pd.Series | dict, period_col: str = "Kỳ", source_col: str | None = None) -> str:
    get = row.get if hasattr(row, "get") else lambda k, d=None: d
    period = str(get(period_col, "") or "").strip()
    if source_col:
        source = str(get(source_col, "") or "").strip()
        if source and ("review" in source.lower() or "snapshot" in source.lower()):
            return f"{period} | {source}"
    return period


def apply_table_overrides(
    repo,
    company_ref_id: int,
    table_key: str,
    df: pd.DataFrame,
    *,
    period_col: str = "Kỳ",
    source_col: str | None = None,
) -> tuple[pd.DataFrame, set[tuple[int, str]]]:
    if df is None or df.empty:
        return df, set()
    latest = latest_table_overrides(repo, company_ref_id, table_key)
    out = df.copy()
    adjusted: set[tuple[int, str]] = set()
    for idx, row in out.iterrows():
        period_key = _override_period_key(row, period_col, source_col)
        for col in out.columns:
            ov = latest.get((period_key, str(col)))
            if ov is None:
                continue
            out.at[idx, col] = override_value(ov)
            adjusted.add((idx, str(col)))
    return out, adjusted


def _highlight_adjusted(styler, adjusted: set[tuple[int, str]]):
    if not adjusted:
        return styler

    def paint(data):
        styles = pd.DataFrame("", index=data.index, columns=data.columns)
        for idx, col in adjusted:
            if idx in styles.index and col in styles.columns:
                styles.at[idx, col] = f"background-color:{APRICOT_YELLOW}!important;color:{APRICOT_TEXT}!important;font-weight:900"
        return styles

    return styler.apply(paint, axis=None)


def _metric_candidates(df: pd.DataFrame, excluded: Iterable[str]) -> list[str]:
    excluded = set(excluded)
    out = []
    for col in df.columns:
        if col in excluded:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            out.append(str(col))
    return out


def render_numeric_override_editor(
    repo,
    company_ref_id: int,
    actor: str,
    *,
    table_key: str,
    df: pd.DataFrame,
    period_col: str = "Kỳ",
    source_col: str | None = None,
    excluded_metrics: Iterable[str] = (),
) -> None:
    if df is None or df.empty or period_col not in df.columns:
        return
    metric_cols = _metric_candidates(df, {period_col, *(excluded_metrics or ())})
    if not metric_cols:
        return
    period_options = []
    period_to_row: dict[str, pd.Series] = {}
    for _, row in df.iterrows():
        key = _override_period_key(row, period_col, source_col)
        if key and key not in period_to_row:
            period_options.append(key)
            period_to_row[key] = row
    if not period_options:
        return
    with st.expander("✏️ Điều chỉnh nhà phân tích — hỗ trợ TTM và các năm lịch sử", expanded=False):
        st.caption(
            "Điều chỉnh là lớp overlay của analyst, không sửa dữ liệu gốc Trecapital. Mỗi thay đổi tạo version mới, bắt buộc ghi lý do. "
            f"Ô đã điều chỉnh được tô vàng hoa mai {APRICOT_YELLOW}."
        )
        with st.form(f"override_{company_ref_id}_{abs(hash(table_key))}"):
            c1, c2 = st.columns(2)
            period_key = c1.selectbox("Kỳ cần điều chỉnh", period_options)
            metric = c2.selectbox("Chỉ tiêu", metric_cols)
            row = period_to_row[period_key]
            current = row.get(metric)
            try:
                current_num = None if current is None or pd.isna(current) else float(current)
            except Exception:
                current_num = None
            value = st.number_input(
                "Giá trị analyst điều chỉnh",
                value=None,
                step=0.1,
                format="%.4f",
                placeholder=f"Hiện tại: {'—' if current_num is None else f'{current_num:,.4f}'}",
            )
            reason = st.text_input("Lý do điều chỉnh *", help="Bắt buộc để audit được vì sao analyst thay số tự động/lịch sử.")
            if st.form_submit_button("Lưu version điều chỉnh", type="primary", use_container_width=True):
                if value is None:
                    st.error("Phải nhập giá trị điều chỉnh.")
                elif not reason.strip():
                    st.error("Bắt buộc nhập lý do điều chỉnh.")
                else:
                    save_table_override(
                        repo,
                        company_ref_id,
                        table_key=table_key,
                        period_key=period_key,
                        metric_key=metric,
                        value=value,
                        reason=reason,
                        actor=actor,
                    )
                    st.rerun()
        history = table_override_history(repo, company_ref_id, table_key, limit=80)
        if history:
            h = pd.DataFrame(history)
            st.caption("Lịch sử version điều chỉnh")
            st.dataframe(h, use_container_width=True, hide_index=True, height=min(300, 38 * len(h) + 75))


def render_table11_historical_corrections(repo, company_ref_id: int, actor: str) -> None:
    history = repo.screening_history_matrix(company_ref_id)
    if not history:
        return
    df = pd.DataFrame(history)
    # Historical corrections preserve immutable reviews: they are an overlay, not a mutation.
    table_key = "Table 1.1"
    latest = latest_table_overrides(repo, company_ref_id, table_key)
    adjusted: set[tuple[int, str]] = set()
    criteria_cols = [c for c in df.columns if c not in {"Review #", "As of", "Type", "Status", "Total ✓"}]
    for idx, row in df.iterrows():
        period_key = f"{row['As of']} | Review #{row['Review #']}"
        for col in criteria_cols:
            ov = latest.get((period_key, str(col)))
            if ov is not None:
                df.at[idx, col] = str(override_value(ov))
                adjusted.add((idx, str(col)))
    symbol = {"yes": "✓", "no": "X", "unknown": "—", "na": "N/A"}
    shown = df.copy()
    for col in criteria_cols:
        shown[col] = shown[col].map(lambda x: symbol.get(str(x), str(x)))
    st.markdown("##### Table 1.1 — lịch sử hiệu lực sau correction overlay")
    st.caption("Completed review vẫn bất biến. Historical correction được lưu thành overlay riêng và tô vàng hoa mai.")
    st.dataframe(_highlight_adjusted(shown.style, adjusted), use_container_width=True, hide_index=True)

    with st.expander("✏️ Điều chỉnh Table 1.1 lịch sử", expanded=False):
        reviews = [f"{r['As of']} | Review #{r['Review #']}" for r in history]
        criteria = repo.list_screening_criteria()
        names = [c["criterion_name_vi"] for c in criteria]
        with st.form(f"screening_hist_override_{company_ref_id}"):
            c1, c2 = st.columns(2)
            period_key = c1.selectbox("Review lịch sử", reviews)
            metric = c2.selectbox("Tiêu chí", names)
            val = st.selectbox("Điều chỉnh analyst", ["yes", "no", "unknown", "na"], format_func=lambda x: symbol[x])
            reason = st.text_input("Lý do điều chỉnh *")
            if st.form_submit_button("Lưu correction Table 1.1", type="primary", use_container_width=True):
                if not reason.strip():
                    st.error("Bắt buộc nhập lý do điều chỉnh.")
                else:
                    save_table_override(repo, company_ref_id, table_key=table_key, period_key=period_key, metric_key=metric, value=val, reason=reason, actor=actor)
                    st.rerun()


def _parse_snapshot_manual_adjustments(row: dict[str, Any], display_index: int) -> set[tuple[int, str]]:
    if str(row.get("data_origin") or "") not in {"manual", "mixed"}:
        return set()
    note = str(row.get("note") or "")
    marker = "Manual overrides:"
    if marker not in note:
        return set()
    raw = note.split(marker, 1)[1].split("|", 1)[0]
    keys = {x.strip() for x in raw.split(",") if x.strip()}
    mapping = {
        "tev": "TEV", "ebit": "EBIT", "ebitda": "EBITDA", "normalized_earnings": "Normalized earnings",
        "total_debt": "Total Debt", "interest_expense": "EBIT/Interest", "fcf_current": "FCF", "market_cap": "Market cap",
        "market_price": "Giá", "fcf_estimate": "FCF est./share", "target_price": "Target", "ccc_days": "CCC", "mos": "MOS",
    }
    return {(display_index, mapping[k]) for k in keys if k in mapping}


def render_table12_trend_with_overrides(repo, integration, company_ref_id: int, actor: str, current_as_of=None) -> None:
    provider = integration.data_provider
    proxy = []
    getter = getattr(provider, "get_inventory_proxy_history", None)
    if callable(getter):
        try:
            proxy = getter(10) or []
        except Exception as exc:
            st.caption(f"Chưa dựng được proxy lịch sử 10 năm: {exc}")
    rows: list[dict[str, Any]] = []
    manual_cells: set[tuple[int, str]] = set()
    for x in proxy:
        row = _page._inventory_display_row(x, period_key="period", source=x.get("source_type", "10Y proxy"))
        row["_sort_date"] = _page._period_sort_date(x.get("period"), current_as_of)
        row["_sort_kind"] = 0
        row["_sort_version"] = 0
        rows.append(row)
    for x in repo.inventory_history(company_ref_id):
        row = _page._inventory_display_row(x, source=f"Review/snapshot #{x.get('last_review_id') or '—'} · {x.get('data_origin','snapshot')} · v{x.get('version_no') or 1}")
        row["_sort_date"] = _page._period_sort_date(x.get("as_of_date"), current_as_of)
        row["_sort_kind"] = 1
        row["_sort_version"] = int(x.get("version_no") or 0)
        rows.append(row)
    if not rows:
        st.info("Chưa có đủ chuỗi 10 năm/review để dựng lịch sử Table 1.2.")
        return

    st.markdown("##### Proxy 10 năm gần nhất + TTM + lịch sử review")
    st.caption("TTM luôn ở trên cùng; sau đó review/snapshot mới nhất và FY mới → cũ. Historical analyst corrections không sửa Data Layer.")
    raw = pd.DataFrame(rows).sort_values(["_sort_date", "_sort_kind", "_sort_version"], ascending=[False, False, False], kind="stable").drop(columns=["_sort_date", "_sort_kind", "_sort_version"]).reset_index(drop=True)

    # Highlight manual overrides already embedded in saved Table 1.2 snapshots.
    inv_by_source = {f"Review/snapshot #{x.get('last_review_id') or '—'} · {x.get('data_origin','snapshot')} · v{x.get('version_no') or 1}": x for x in repo.inventory_history(company_ref_id)}
    for idx, row in raw.iterrows():
        source = str(row.get("Nguồn") or "")
        if source in inv_by_source:
            manual_cells |= _parse_snapshot_manual_adjustments(inv_by_source[source], idx)

    adjusted_df, generic_cells = apply_table_overrides(repo, company_ref_id, "Table 1.2", raw, period_col="Kỳ", source_col="Nguồn")
    all_adjusted = manual_cells | generic_cells
    styler = _highlight_adjusted(_page._style_inventory(adjusted_df), all_adjusted)
    st.dataframe(styler, use_container_width=True, hide_index=True, height=min(590, 38 * len(adjusted_df) + 75))
    render_numeric_override_editor(repo, company_ref_id, actor, table_key="Table 1.2", df=adjusted_df, period_col="Kỳ", source_col="Nguồn", excluded_metrics={"Nguồn"})


@contextmanager
def _patched_table12_trend(repo, integration, company_ref_id: int, actor: str):
    original = _page._render_table12_trend
    _page._render_table12_trend = lambda _repo, _integration, _cid, current_as_of=None: render_table12_trend_with_overrides(_repo, _integration, _cid, actor, current_as_of)
    try:
        yield
    finally:
        _page._render_table12_trend = original


def _wrapped_phase2_formula_audit(tool_prefix: str | None = None) -> None:
    rows = PHASE2_FORMULA_ROWS
    if tool_prefix:
        matches = [r for r in rows if str(r.get("Tool", "")).startswith(tool_prefix)]
        if matches:
            rows = matches
    with st.expander("📐 Công thức & giả định của Analytical Tools", expanded=False):
        render_wrapped_table(pd.DataFrame(rows), css_class="phase2-formula-wrap")
        st.caption("SOURCE / Trecapital implementation / extension được tách rõ; thay đổi công thức phải đi cùng regression test.")


@contextmanager
def _patched_quant_render(repo, company_ref_id: int, actor: str):
    original_result = _qt._render_result
    original_formula = _qt._formula_audit

    def render_result(result, *, height=None):
        st.markdown(f"#### {result.name}")
        st.caption(
            f"Bảng/nguồn gốc: {', '.join(result.source_tables)} · Hỗ trợ checklist: {', '.join(result.checklist_questions)} · "
            "Dữ liệu tài chính chỉ consume từ Trecapital Data Layer."
        )
        if result.rows:
            raw = _qt._latest_first(pd.DataFrame(result.rows)).reset_index(drop=True)
            table_key = f"Analytical · {result.name}"
            df, adjusted = apply_table_overrides(repo, company_ref_id, table_key, raw, period_col="Kỳ")
            st.dataframe(_highlight_adjusted(_qt._styled(df), adjusted), use_container_width=True, hide_index=True, height=height)
            render_numeric_override_editor(repo, company_ref_id, actor, table_key=table_key, df=df, period_col="Kỳ")
        else:
            st.info("Chưa có đủ dữ liệu Trecapital để dựng tool này. App không tự bịa số liệu.")
        for note in result.notes:
            st.caption("• " + note)

    _qt._render_result = render_result
    _qt._formula_audit = _wrapped_phase2_formula_audit
    try:
        yield
    finally:
        _qt._render_result = original_result
        _qt._formula_audit = original_formula


def render_analytical_hub(repo, integration, company_ref_id: int, review, actor: str, data_provider, company_type: str) -> None:
    st.markdown("### 🧮 Analytical Tools")
    st.caption("Table 1.1 và Table 1.2 được gom vào Analytical Tools theo kiến trúc nguồn; các quantitative tools dùng cùng Trecapital Data Layer.")
    group = st.selectbox(
        "Nhóm Analytical Tool",
        [
            "1.1 · Quality Criteria Matrix",
            "1.2 · Opportunity Inventory",
            "5.x–10.x · Quantitative Analytical Tools",
        ],
        key=f"analytical_hub_{company_ref_id}",
    )
    if group.startswith("1.1"):
        _page._render_table11(repo, company_ref_id, review, actor)
        render_table11_historical_corrections(repo, company_ref_id, actor)
    elif group.startswith("1.2"):
        with _patched_table12_trend(repo, integration, company_ref_id, actor):
            _page._render_table12(repo, integration, company_ref_id, review, actor)
    else:
        with _patched_quant_render(repo, company_ref_id, actor):
            _qt.render_quantitative_tools(data_provider, company_type=company_type)


def _watchlist_display_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    out = []
    for x in rows:
        inv = _page._inventory_display_row(x, source=f"Review #{x.get('latest_review_id') or '—'}")
        out.append({
            "Mã CP": x.get("ticker"),
            "Doanh nghiệp": x.get("company_name"),
            "Review mới nhất": x.get("latest_review_as_of"),
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


def _style_watchlist(df: pd.DataFrame):
    if df.empty:
        return df.style
    style = _page._style_inventory(df)
    pct = {c: (lambda v: "—" if pd.isna(v) else f"{v:,.1f}%") for c in ["CAGR DT 5Y", "CAGR LN 5Y"] if c in df.columns}
    return style.format(pct, na_rep="—")


def render_watchlist(repo, current_company_ref_id: int, current_ticker: str) -> None:
    st.markdown("### ⭐ Watchlist — Opportunity Inventory")
    st.caption("Bảng lấy Table 1.2 theo review/snapshot mới nhất của từng doanh nghiệp; CAGR 5Y lấy từ annual canonical của Trecapital khi mã được thêm/cập nhật.")
    rows = list_watchlist_rows(repo)
    if not rows:
        st.info("Watchlist đang trống. Dùng nút ⭐ Đưa vào Watchlist ở đầu trang của từng doanh nghiệp.")
        return
    df = _watchlist_display_dataframe(rows)
    st.caption("Chọn một dòng để mở Investment Checklist của mã đó.")
    try:
        event = st.dataframe(
            _style_watchlist(df),
            use_container_width=True,
            hide_index=True,
            height=min(600, 38 * len(df) + 90),
            key="investment_watchlist_table",
            on_select="rerun",
            selection_mode="single-row",
        )
        selected_rows = list(getattr(getattr(event, "selection", None), "rows", []) or [])
        if selected_rows:
            ticker = str(df.iloc[selected_rows[0]]["Mã CP"] or "").strip().upper()
            if ticker and ticker != str(current_ticker).upper():
                for key in ("shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker"):
                    st.session_state[key] = ticker
                st.session_state["checklist_section_global"] = "🏠 Research Home"
                st.rerun()
    except TypeError:
        ticker = st.selectbox("Mở mã từ Watchlist", df["Mã CP"].tolist(), key="watchlist_open_fallback")
        if st.button("Mở Investment Checklist", use_container_width=True):
            for key in ("shared_ticker", "module1_ticker", "module2_ticker", "last_query_ticker"):
                st.session_state[key] = ticker
            st.session_state["checklist_section_global"] = "🏠 Research Home"
            st.rerun()


def render_watchlist_toggle(repo, company_ref_id: int, ticker: str, *, actor: str, data_provider) -> None:
    active = is_watchlisted(repo, company_ref_id)
    if active:
        refresh_watchlist_cagrs(repo, company_ref_id, provider=data_provider, actor=actor)
    label = "★ Đang trong Watchlist — bấm để bỏ" if active else "☆ Đưa doanh nghiệp vào Watchlist"
    if st.button(label, key=f"watchlist_toggle_{company_ref_id}", use_container_width=True):
        set_watchlist(repo, company_ref_id, active=not active, actor=actor, provider=data_provider)
        st.session_state["checklist_last_admin_message"] = f"{'Đã thêm' if not active else 'Đã bỏ'} {ticker} {'vào' if not active else 'khỏi'} Watchlist."
        st.rerun()
