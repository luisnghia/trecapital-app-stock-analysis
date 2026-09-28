"""Final Weekly Plan runtime unification.

- Accept both legacy ``logger_arg`` and live ``logger=`` calls for the create form.
- Remove the Hôm nay/Phát sinh child views.
- Keep new in-week work on the Kế hoạch tuần screen and mark it as emergent.
- Preserve Kế hoạch phòng for leaders/admins.
"""
from __future__ import annotations

from datetime import timedelta

VERSION = "1.0.0"
_FLAG = "_WEEKLY_PLAN_UNIFIED_PATCH_VERSION"


def install(policy, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    # The refinement form historically exposed logger_arg while the approved
    # policy calls it with logger=. Normalize both directions once, at the edge.
    original_add = policy._add_item_form

    def add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False,
                      logger=None, logger_arg=None, **kwargs):
        active_logger = logger or logger_arg
        try:
            return original_add(
                st, u, core, get_conn, ws, focus_rows,
                emergent=emergent, logger_arg=active_logger,
            )
        except TypeError as exc:
            # Keep compatibility if a future form switches back to logger=.
            if "logger_arg" not in str(exc):
                raise
            return original_add(
                st, u, core, get_conn, ws, focus_rows,
                emergent=emergent, logger=active_logger,
            )

    policy._add_item_form = add_item_form

    original_staff = policy._render_staff_week

    def render_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows,
                          logger=None, logger_arg=None, **kwargs):
        active_logger = logger or logger_arg
        status = str(plan.get("workflow_status") or "NHAP")

        # Replace the now-obsolete guidance text without modifying the historical
        # lifecycle renderer itself.
        old_success = st.success

        def success_proxy(body, *args, **kw):
            text = str(body)
            if "việc mới trong tuần ghi tại mục Phát sinh" in text:
                body = "Kế hoạch đã duyệt. Cán bộ cập nhật tiến độ tại đây; công việc mới trong tuần cũng thêm ngay tại màn hình Kế hoạch tuần."
            return old_success(body, *args, **kw)

        st.success = success_proxy
        try:
            result = original_staff(
                st, u, core, get_conn, ws, plan, items, focus_rows,
                active_logger,
            )
        finally:
            st.success = old_success

        # Once approved, the same screen remains the single place for in-week
        # additions. They are persisted as emergent work so room metrics/history
        # continue to distinguish planned vs. added-during-week work.
        if status == "DA_DUYET":
            st.divider()
            st.markdown("### ＋ Thêm công việc mới trong tuần")
            st.caption("Công việc thêm sau khi kế hoạch đã được duyệt sẽ tự ghi nhận là công việc phát sinh.")
            policy._add_item_form(
                st, u, core, get_conn, ws, focus_rows,
                emergent=True, logger=active_logger,
            )
        return result

    policy._render_staff_week = render_staff_week

    def render_weekly(st, u, core, get_conn, page_title=None, logger=None):
        policy._ensure_schema(core, get_conn, logger)
        uid = int(policy._uget(u, "id"))
        if page_title:
            page_title(
                "Kế hoạch tuần",
                "Trọng tâm trước · phân loại tự động Q2/Q1/Q3/Q4 · quản trị theo vòng đời tuần",
            )
        else:
            st.title("📅 Kế hoạch tuần")

        base = policy._default_week(core)
        if "policy_week_offset" not in st.session_state:
            st.session_state["policy_week_offset"] = 0
        a, b, c, d = st.columns([1, 1, 1, 4])
        if a.button("← Tuần trước", key="policy_prev", use_container_width=True):
            st.session_state["policy_week_offset"] -= 1
            st.rerun()
        if b.button("Tuần mục tiêu", key="policy_now", use_container_width=True):
            st.session_state["policy_week_offset"] = 0
            st.rerun()
        if c.button("Tuần sau →", key="policy_next", use_container_width=True):
            st.session_state["policy_week_offset"] += 1
            st.rerun()

        ws = base + timedelta(days=7 * int(st.session_state["policy_week_offset"]))
        d.markdown(f"**{ws:%d/%m} – {(ws + timedelta(days=6)):%d/%m/%Y}**")
        with get_conn() as conn:
            plan = policy._plan_row(conn, uid, ws, core)
            items = core.load_items(conn, uid, ws)
            scope = policy._scope_key(conn, uid)
            focus = policy._focus_categories(conn, scope, ws.year, False)
        policy._status_badge(st, str(plan.get("workflow_status") or "NHAP"))

        # Staff has one unified screen. Leaders/admins retain the room overview.
        if policy._manager(u):
            view = policy._cmd_nav(
                st,
                "policy_week_view",
                [("plan", "Kế hoạch tuần"), ("room", "Kế hoạch phòng")],
                "room",
            )
        else:
            view = "plan"

        if view == "room":
            return policy._room_dashboard(st, u, core, get_conn, ws, logger)
        return policy._render_staff_week(
            st, u, core, get_conn, ws, plan, items, focus, logger=logger,
        )

    policy._render_weekly = render_weekly
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "WEEKLY_PLAN_UNIFIED_PATCH_INSTALLED version=%s no_today=1 no_emergent_tab=1 single_add_screen=1",
            VERSION,
        )
