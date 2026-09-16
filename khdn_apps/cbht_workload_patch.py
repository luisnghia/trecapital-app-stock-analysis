"""KHDN Ops V2.31 runtime patch.

Adds two production behaviors without rewriting the compressed core engine:
1) Refresh BIDV USD/EUR rates automatically when an authenticated app session
   opens (including remembered-device auto-login), at most once per calendar day.
2) Show today's CBHT workload on the Leader/Admin work-management screen.

The workload view counts only the two operational states requested for dispatch:
- PENDING_ACCEPTANCE -> Chờ tiếp nhận
- OPEN / REWORK -> Đang xử lý

By default it includes only tasks assigned today. A checkbox expands the scope to
all unfinished carry-over tasks. The active CBHT roster is left-joined so staff
with zero tasks remain visible.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import plotly.graph_objects as go

PATCH_VERSION = "2.31.0"
_INSTALL_FLAG = "_KHDN_CBHT_WORKLOAD_V231_INSTALLED"
_FX_DAY_KEY = "_fx_auto_open_date_v231"


def _logger(ns: dict[str, Any]):
    return ns.get("LOGGER") or logging.getLogger("khdn_ops")


def _ensure_fx_on_authenticated_open(ns: dict[str, Any], user: dict[str, Any]) -> None:
    """Guarantee one BIDV FX refresh per authenticated session/day.

    A normal username/password login already fetches FX in the core engine. In
    that case we simply mark the day as satisfied. Remembered-device login skips
    login_ui(), so this wrapper performs the missing fetch before the sidebar is
    rendered.
    """
    st = ns["st"]
    today = ns["now_dt"]().date().isoformat()
    rates = st.session_state.get("fx_rates") or {}
    fx_time = st.session_state.get("fx_time")

    # Explicit login already fetched rates today: do not make a duplicate HTTP call.
    if rates.get("USD") and rates.get("EUR") and fx_time:
        try:
            parsed = ns["parse_dt"](fx_time)
            if parsed is not None and parsed.date().isoformat() == today:
                st.session_state[_FX_DAY_KEY] = today
                return
        except Exception:
            pass

    # Avoid repeated calls on every Streamlit rerun after one open-attempt today.
    if st.session_state.get(_FX_DAY_KEY) == today:
        return
    st.session_state[_FX_DAY_KEY] = today

    try:
        rates, source, fetched_at, error = ns["fetch_bidv_fx_rates"]()
        st.session_state.fx_rates = rates
        st.session_state.fx_source = source
        st.session_state.fx_time = fetched_at
        st.session_state.fx_error = error
        _logger(ns).info(
            "FX_AUTO_OPEN user_id=%s source=%s live_error=%s",
            user.get("id"), source, bool(error),
        )
    except Exception as exc:  # defensive: core fetch normally returns fallback data
        st.session_state.fx_rates = {"VND": 1.0}
        st.session_state.fx_source = "Chưa có dữ liệu tỷ giá"
        st.session_state.fx_time = ns["now_str"]()
        st.session_state.fx_error = str(exc)
        _logger(ns).exception("FX_AUTO_OPEN_FAILED user_id=%s", user.get("id"))


def _task_type_options(ns: dict[str, Any], tasks: pd.DataFrame) -> list[str]:
    names: set[str] = set()
    try:
        catalog = ns["active_task_types"]()
        if catalog is not None and not catalog.empty and "name" in catalog.columns:
            names.update(str(x).strip() for x in catalog["name"].dropna().tolist() if str(x).strip())
    except Exception:
        _logger(ns).exception("CBHT_LOAD_TASK_TYPE_CATALOG_FAILED")
    if tasks is not None and not tasks.empty and "task_type" in tasks.columns:
        names.update(str(x).strip() for x in tasks["task_type"].dropna().tolist() if str(x).strip())
    return sorted(names, key=lambda x: x.casefold())


def _load_cbht_workload_data(ns: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    roster = ns["all_users"]("Cán bộ hỗ trợ", active_only=True)
    if roster is None:
        roster = pd.DataFrame()
    tasks = ns["qdf"](
        """SELECT t.id,t.support_user_id,s.full_name AS support_name,
                  t.task_type,t.status,t.assigned_at
           FROM tasks t
           JOIN users s ON s.id=t.support_user_id
           WHERE t.status IN ('PENDING_ACCEPTANCE','OPEN','REWORK')"""
    )
    return roster, tasks


def _workload_summary(roster: pd.DataFrame, tasks: pd.DataFrame) -> pd.DataFrame:
    base = roster[["id", "full_name"]].copy() if not roster.empty else pd.DataFrame(columns=["id", "full_name"])
    base = base.rename(columns={"id": "support_user_id", "full_name": "CBHT"})

    if tasks is None or tasks.empty:
        counts = pd.DataFrame(columns=["support_user_id", "Đang xử lý", "Chờ tiếp nhận"])
    else:
        x = tasks.copy()
        x["_bucket"] = x["status"].map(
            lambda s: "Chờ tiếp nhận" if str(s) == "PENDING_ACCEPTANCE" else "Đang xử lý"
        )
        counts = (
            x.groupby(["support_user_id", "_bucket"], dropna=False)
            .size()
            .unstack(fill_value=0)
            .reset_index()
        )
        counts.columns.name = None

    out = base.merge(counts, on="support_user_id", how="left")
    for col in ("Đang xử lý", "Chờ tiếp nhận"):
        if col not in out.columns:
            out[col] = 0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    out["Tổng tải"] = out["Đang xử lý"] + out["Chờ tiếp nhận"]
    # Free/low-load staff first to make dispatch decisions faster.
    out = out.sort_values(["Tổng tải", "CBHT"], ascending=[True, True], kind="stable").reset_index(drop=True)
    return out[["CBHT", "Đang xử lý", "Chờ tiếp nhận", "Tổng tải"]]


def _render_workload_chart(ns: dict[str, Any], summary: pd.DataFrame) -> None:
    st = ns["st"]
    if summary.empty:
        st.info("Chưa có Cán bộ hỗ trợ đang hoạt động.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=summary["CBHT"], x=summary["Đang xử lý"],
            name="Đang xử lý", orientation="h",
            text=summary["Đang xử lý"], textposition="auto",
            hovertemplate="%{y}<br>Đang xử lý: %{x}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=summary["CBHT"], x=summary["Chờ tiếp nhận"],
            name="Chờ tiếp nhận", orientation="h",
            text=summary["Chờ tiếp nhận"], textposition="auto",
            hovertemplate="%{y}<br>Chờ tiếp nhận: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        title=dict(text="Tải hồ sơ theo từng CBHT", x=0, xanchor="left", font=dict(size=15)),
        height=max(340, 64 * len(summary) + 130),
        margin=dict(l=24, r=30, t=56, b=52),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.28,
    )
    fig.update_xaxes(title="Số hồ sơ", rangemode="tozero", dtick=1, automargin=True)
    fig.update_yaxes(title=None, automargin=True, autorange="reversed")
    config = ns.get("_plotly_config")
    st.plotly_chart(fig, use_container_width=True, config=config() if callable(config) else {"displayModeBar": False})


def _render_cbht_workload_today(ns: dict[str, Any]) -> None:
    """Render the requested workload block directly under the management title."""
    st = ns["st"]
    try:
        roster, tasks = _load_cbht_workload_data(ns)
    except Exception:
        _logger(ns).exception("CBHT_LOAD_QUERY_FAILED")
        st.error("Không tải được dữ liệu tải công việc CBHT. Chi tiết đã được ghi vào log.")
        return

    st.markdown("### 📊 Tải công việc CBHT hôm nay")
    st.caption(
        "Mặc định chỉ tính hồ sơ **được giao hôm nay**. Bật tùy chọn tồn để tính thêm hồ sơ từ ngày trước "
        "vẫn đang xử lý/chờ tiếp nhận. CBHT không có hồ sơ vẫn được hiển thị với giá trị 0."
    )

    c1, c2 = st.columns([2.2, 1.3])
    options = _task_type_options(ns, tasks)
    selected_types = c1.multiselect(
        "Loại công việc",
        options,
        default=[],
        key="leader_cbht_load_task_types_v231",
        placeholder="Tất cả loại công việc",
        help="Để trống = tất cả loại công việc.",
    )
    include_backlog = c2.checkbox(
        "Tính cả hồ sơ tồn từ ngày trước",
        value=False,
        key="leader_cbht_load_include_backlog_v231",
    )

    filtered = tasks.copy() if tasks is not None else pd.DataFrame()
    if not filtered.empty:
        if selected_types:
            filtered = filtered[filtered["task_type"].astype(str).isin(selected_types)].copy()
        if not include_backlog:
            today = ns["now_dt"]().date()
            assigned = pd.to_datetime(filtered["assigned_at"], errors="coerce")
            filtered = filtered[assigned.dt.date == today].copy()

    summary = _workload_summary(roster, filtered)
    scope_text = "Hôm nay + hồ sơ tồn trước đó" if include_backlog else f"Hồ sơ giao ngày {ns['now_dt']():%d/%m/%Y}"
    type_text = ", ".join(selected_types) if selected_types else "Tất cả loại công việc"

    total_processing = int(summary["Đang xử lý"].sum()) if not summary.empty else 0
    total_waiting = int(summary["Chờ tiếp nhận"].sum()) if not summary.empty else 0
    zero_staff = int((summary["Tổng tải"] == 0).sum()) if not summary.empty else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("Đang xử lý", total_processing)
    m2.metric("Chờ tiếp nhận", total_waiting)
    m3.metric("CBHT đang 0 hồ sơ", zero_staff)
    st.caption(f"Phạm vi: **{scope_text}** · Lọc: **{type_text}**")

    _render_workload_chart(ns, summary)

    # Use the app's canonical st.html()-based read-only table renderer.
    table = summary.copy()
    ns["_html_table"](table, max_height=max(260, min(620, 92 + 42 * max(len(table), 1))))


def install(ns: dict[str, Any]) -> None:
    """Install the V2.31 patch into an already-loaded khdn_apps.app module."""
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True
    ns["APP_VERSION"] = PATCH_VERSION

    original_sidebar_user = ns["sidebar_user"]

    def sidebar_user_with_fx(user):
        _ensure_fx_on_authenticated_open(ns, user)
        return original_sidebar_user(user)

    ns["sidebar_user"] = sidebar_user_with_fx

    original_page_title = ns["page_title"]

    def page_title_with_workload(*args, **kwargs):
        result = original_page_title(*args, **kwargs)
        title = str(args[0] if args else kwargs.get("title", ""))
        if title.startswith("Quản lý công việc"):
            _render_cbht_workload_today(ns)
        return result

    ns["page_title"] = page_title_with_workload
    _logger(ns).info("PATCH_INSTALL version=%s", PATCH_VERSION)
