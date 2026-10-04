"""Operational phase 9: full-room leader visibility, approval scope unchanged.

Requirements implemented:
- A normal ``Lãnh đạo phòng`` can VIEW the same room-wide Customer Work and
  Weekly Plan workload that Admin can view.
- Approval/write authorization is intentionally NOT widened. Existing
  controller/direct-scope checks remain the source of truth for approvals.
- Admin assignment candidates explicitly include active ``Lãnh đạo phòng``
  users, so Admin can assign Customer Work to a leader as the owner.

The patch is a read-visibility overlay installed after phase 8. It does not
change any approval function or mutate historical business data.
"""
from __future__ import annotations

from datetime import date

from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase3_weekly as p3week
from khdn_apps import planning_room_dashboard_detail_patch as room_dashboard
from khdn_apps import weekly_performance_phase2_patch as phase2

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE9_VERSION"


def _leader_read_all(u, policy):
    return policy._is_admin(u) or policy._is_leader(u)


def _install_admin_assignable_leaders(customer_core, logger=None):
    """Harden the shared owner list so active leaders can always be assigned."""
    if getattr(customer_core, "_P9_ASSIGNABLE_LEADERS", False):
        return
    original = customer_core.staff_users

    def staff_users(c):
        rows = [dict(x) for x in original(c)]
        seen = {int(x.get("id") or 0) for x in rows}
        leaders = [dict(r) for r in c.execute(
            "SELECT id,full_name,role,is_admin FROM users "
            "WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name"
        ).fetchall()]
        for row in leaders:
            if int(row.get("id") or 0) not in seen:
                rows.append(row)
                seen.add(int(row.get("id") or 0))
        rows.sort(key=lambda x: (0 if str(x.get("role") or "") == "Lãnh đạo phòng" else 1, str(x.get("full_name") or "").casefold(), int(x.get("id") or 0)))
        return rows

    customer_core.staff_users = staff_users
    customer_core._P9_ASSIGNABLE_LEADERS = True
    if logger:
        logger.info("P9_ADMIN_ASSIGNABLE_LEADERS_INSTALLED active_leaders_in_owner_list=1")


def _install_full_room_dashboard(customer_ui, customer_core, policy, weekly_core, logger=None):
    """Room dashboard reads all work; the embedded approval center stays scoped."""
    def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None, **kwargs):
        active_logger = logger
        customer_core.ensure_schema(get_conn, active_logger)
        phase2._ensure_schema(policy, weekly_core, get_conn, active_logger)
        p3dash.ensure_schema(get_conn, active_logger)
        uid = int(policy._uget(u, "id"))
        if not _leader_read_all(u, policy):
            st.error("Chỉ Lãnh đạo/Admin được xem Điều hành công việc phòng.")
            return

        if page_title:
            page_title(
                "Điều hành công việc phòng",
                "Lãnh đạo được xem toàn bộ công việc của phòng; quyền phê duyệt vẫn theo Lãnh đạo kiểm soát/phạm vi được giao",
            )
        else:
            st.title("📊 Điều hành công việc phòng")
        if policy._is_leader(u) and not policy._is_admin(u):
            st.info(
                "👁 Lãnh đạo phòng đang ở quyền xem toàn phòng. Các nút phê duyệt bên dưới vẫn chỉ xuất hiện/hoạt động theo phạm vi kiểm soát hiện hành."
            )

        with get_conn() as c:
            # VIEW scope deliberately equals Admin: no direct-leader filter here.
            data = customer_core.list_cases(c, manager=True, include_completed=False)
            plans, reschedules = customer_core.pending_case_approvals(c)
            today = date.today().isoformat()
            try:
                wp_today = [dict(r) for r in c.execute(
                    "SELECT * FROM weekly_plan_items WHERE work_date=? AND status<>'CANCELLED' "
                    "AND COALESCE(approval_status,'APPROVED')='APPROVED' ORDER BY id",
                    (today,),
                ).fetchall()]
                wp_plan = int(c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE approval_status='PENDING'").fetchone()[0])
                wp_move = int(c.execute("SELECT COUNT(*) FROM weekly_plan_reschedule_requests WHERE status='PENDING'").fetchone()[0])
            except Exception:
                wp_today = []
                wp_plan = wp_move = 0

        delayed = [x for x in data if x.get("is_stage_delayed")]
        overdue = [x for x in data if x.get("is_overdue")]
        blocked = [x for x in data if int(x.get("open_issue_count") or 0) > 0]
        a, b, c, d, e = st.columns(5)
        a.metric("Đang xử lý · toàn phòng", len(data))
        b.metric("Kế hoạch hôm nay · toàn phòng", len(wp_today))
        c.metric("Quá hạn", len(overdue))
        d.metric("Mục bị chậm", len(delayed))
        e.metric("Chờ phê duyệt · toàn phòng", len(plans) + len(reschedules) + wp_plan + wp_move)

        # This is an ACTION queue, so retain its existing direct-scope checks.
        p3dash._attention_dashboard(st, u, policy, customer_core, get_conn, active_logger)

        st.caption(p3dash.WORKLOAD_GROUP_NOTE)
        st.subheader("Theo mục công việc · toàn phòng")
        stage_rows = []
        for name in sorted({x.get("stage_name") for x in data if x.get("stage_name")}):
            arr = [x for x in data if x.get("stage_name") == name]
            stage_rows.append([
                name,
                *p3dash._workload_lists(arr),
            ])
        p3dash._matrix_table(st, ["Mục công việc", "Đang xử lý", "Bị chậm", "Có vướng mắc", "Quá hạn"], stage_rows)

        st.subheader("Theo cán bộ · toàn phòng")
        staff_rows = []
        for name in sorted({x.get("owner_name") or "—" for x in data}):
            arr = [x for x in data if (x.get("owner_name") or "—") == name]
            staff_rows.append([
                name,
                *p3dash._workload_lists(arr, ("PROCESSING", "DELAYED", "OVERDUE", "ISSUES")),
            ])
        p3dash._matrix_table(st, ["Cán bộ", "Đang xử lý", "Bị chậm", "Quá hạn", "Có vướng mắc"], staff_rows)
        room_dashboard._render_room_priority(st, customer_ui, data)
        if overdue or delayed or blocked:
            st.subheader("⚠ Danh sách cần chú ý · toàn phòng")
            p3dash._attention_cards(st, overdue + delayed + blocked)
        customer_ui._glossary(st)

        # IMPORTANT: this renderer keeps the pre-existing approval filtering and
        # core controller checks. Do not replace it with an all-room query.
        room_dashboard._render_approval_center(
            st, u, policy, weekly_core, customer_core, customer_ui, get_conn, active_logger
        )

    customer_ui.render_leader_dashboard = render_leader_dashboard
    if logger:
        logger.info("P9_LEADER_FULL_ROOM_READ_INSTALLED customer_work=all weekly_today=all approval_scope=unchanged exclusive_workload_columns=1 priority=overdue,issues,delayed,processing")


def _install_weekly_room_read_overlay(policy, weekly_core, logger=None):
    """Keep existing actionable room plans, then show other plans read-only."""
    original = policy._room_dashboard

    def room_dashboard_read_all(st, u, core, get_conn, ws, logger=None):
        active_logger = logger
        original(st, u, core, get_conn, ws, active_logger)
        if not policy._is_leader(u) or policy._is_admin(u):
            return

        leader_uid = int(policy._uget(u, "id"))
        with get_conn() as c:
            all_plans = [dict(r) for r in c.execute(
                "SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id "
                "WHERE p.week_start=? AND u.active=1 ORDER BY u.full_name",
                (ws.isoformat(),),
            ).fetchall()]
            readonly = [
                p for p in all_plans
                if not policy._direct_scope_ok(c, leader_uid, int(p["user_id"]), False)
            ]

        if not readonly:
            return
        st.divider()
        st.markdown("### 👁 Kế hoạch ngoài phạm vi kiểm soát · chỉ xem")
        st.caption(
            "Các kế hoạch dưới đây thuộc toàn phòng nên Lãnh đạo được xem. Không mở quyền điều chỉnh, đánh giá hoặc phê duyệt cho các kế hoạch ngoài phạm vi kiểm soát."
        )
        for plan in readonly:
            with get_conn() as c:
                items = [dict(r) for r in c.execute(
                    "SELECT w.*,u.full_name AS owner_name FROM weekly_plan_items w "
                    "JOIN users u ON u.id=w.user_id WHERE w.plan_id=? AND w.status<>'CANCELLED' "
                    "ORDER BY w.work_date,w.id",
                    (int(plan["id"]),),
                ).fetchall()]
            with st.expander(
                f"👁 {plan.get('full_name')} · {len(items)} việc · {policy.PLAN_STATUS.get(str(plan.get('workflow_status') or ''), str(plan.get('workflow_status') or ''))}",
                expanded=False,
            ):
                if not items:
                    st.caption("Chưa có công việc trong kế hoạch này.")
                for item in items:
                    p3week.weekly_card(
                        st, policy, weekly_core, item,
                        f"p9_readonly_{int(plan['id'])}",
                        can_update=False, can_edit=False,
                    )

    policy._room_dashboard = room_dashboard_read_all
    if logger:
        logger.info("P9_WEEKLY_ROOM_READ_OVERLAY_INSTALLED out_of_scope_readonly=1 approval_scope=unchanged")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    _install_admin_assignable_leaders(customer_core, logger)
    _install_full_room_dashboard(customer_ui, customer_core, policy, weekly_core, logger)
    _install_weekly_room_read_overlay(policy, weekly_core, logger)
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE9_INSTALLED version=%s leader_read_all=1 approval_scope_unchanged=1 admin_assign_leader=1",
            VERSION,
        )
