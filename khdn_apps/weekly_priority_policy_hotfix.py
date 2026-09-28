"""Runtime corrections for weekly_priority_policy_patch."""
from __future__ import annotations

from khdn_apps import weekly_plan_form_refinement_patch as _form_refinement
from khdn_apps import weekly_plan_unified_patch as _unified
from khdn_apps import planning_final_defaults_patch as _final_defaults
from khdn_apps import planning_final_ux_patch as _final_ux
from khdn_apps import planning_week_board_focus_patch as _week_board_focus
from khdn_apps import planning_followup_ux_patch as _followup_ux
from khdn_apps import planning_dashboard_consolidation_patch as _dashboard_consolidation
from khdn_apps import planning_navigation_approval_parity_patch as _nav_approval_parity
from khdn_apps import planning_room_dashboard_detail_patch as _room_dashboard
from khdn_apps import weekly_plan as _weekly_core
from khdn_apps import customer_work as _customer_core
from khdn_apps import customer_work_ui as _customer_ui
from khdn_apps import customer_work_refinement_patch as _refinement
from khdn_apps import worktype_contact_card_patch as _worktype

VERSION = "2.0.0"
_FLAG = "_WEEKLY_PRIORITY_POLICY_HOTFIX_VERSION"


def install(policy, logger=None):
    # Streamlit reruns execute online_entry repeatedly inside the same process.
    # Never stack lifecycle wrappers across reruns.
    if getattr(policy, _FLAG, None) == VERSION:
        return

    # Harden the schema independently of older priority patches and keep the Q2
    # delay watch current for both weekly reschedules and carry-forwards.
    original_ensure = policy._ensure_schema

    def ensure_schema(core, get_conn, logger_arg=None):
        original_ensure(core, get_conn, logger_arg or logger)
        with get_conn() as c:
            cols = policy._cols(c, "weekly_plan_items")
            if "priority_quadrant" not in cols:
                c.execute("ALTER TABLE weekly_plan_items ADD COLUMN priority_quadrant INTEGER")
            c.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS trg_weekly_q2_reschedule_watch
                AFTER UPDATE OF reschedule_count ON weekly_plan_items
                WHEN NEW.priority_quadrant=2 AND COALESCE(NEW.reschedule_count,0)>=2
                BEGIN
                    UPDATE weekly_plan_items SET q2_watch_flag=1 WHERE id=NEW.id;
                END;
                CREATE TRIGGER IF NOT EXISTS trg_weekly_q2_carry_watch
                AFTER UPDATE OF carryover_count ON weekly_plan_items
                WHEN NEW.priority_quadrant=2 AND COALESCE(NEW.carryover_count,0)>=2
                BEGIN
                    UPDATE weekly_plan_items SET q2_watch_flag=1 WHERE id=NEW.id;
                END;
                """
            )

    policy._ensure_schema = ensure_schema

    # The formal lifecycle is TRA_LAI -> NHAP. Do not let the user edit while the
    # plan is still labeled TRA_LAI; one explicit action starts the new draft.
    original_staff_week = policy._render_staff_week

    def render_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows, logger_arg=None):
        if str(plan.get("workflow_status") or "") == "TRA_LAI":
            policy._drift_warning(st, get_conn, int(policy._uget(u, "id")), ws)
            policy._summary(st, items)
            st.error("↩ Kế hoạch đã được Trưởng phòng trả lại và đang khóa cho đến khi cán bộ bắt đầu vòng điều chỉnh mới.")
            if plan.get("return_note"):
                st.write(f"**Lý do:** {plan.get('return_note')}")
            for item in [x for x in items if x.get("status") != "CANCELLED"]:
                policy._item_card(st, item)
            if st.button("✏️ Bắt đầu điều chỉnh kế hoạch", key=f"return_to_draft_{plan['id']}", type="primary", use_container_width=True):
                uid = int(policy._uget(u, "id"))
                ts = policy._now()
                with get_conn() as c:
                    c.execute(
                        "UPDATE weekly_plans SET workflow_status='NHAP',updated_at=? WHERE id=? AND user_id=?",
                        (ts, int(plan["id"]), uid),
                    )
                    c.execute(
                        "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'RETURN_TO_DRAFT',?,?)",
                        (uid, f"week={ws.isoformat()}", ts),
                    )
                st.rerun()
            return
        return original_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows, logger_arg or logger)

    policy._render_staff_week = render_staff_week

    def inline_focus_create(st, u, get_conn, year, logger_arg=None):
        uid = int(policy._uget(u, "id"))
        with get_conn() as c:
            leaders = [dict(r) for r in c.execute(
                "SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name"
            ).fetchall()]
        leader_id = uid
        if policy._is_admin(u) and leaders:
            leader_id = int(st.selectbox(
                "Phòng/Trưởng phòng áp dụng",
                leaders,
                format_func=lambda x: x["full_name"],
                key=f"inline_focus_leader_{year}",
            )["id"])
        scope = f"LEADER:{leader_id}"
        with st.expander("＋ Bổ sung mục trọng tâm ngay tại màn hình duyệt", expanded=False):
            a, b = st.columns([1, 3])
            code = a.text_input("Mã *", key=f"inline_focus_code_{year}", placeholder="TT06")
            name = b.text_input("Tên ngắn gọn *", key=f"inline_focus_name_{year}")
            desc = st.text_area("Mô tả phạm vi (1–2 câu) *", key=f"inline_focus_desc_{year}")
            order = st.number_input("Thứ tự", min_value=1, value=6, step=1, key=f"inline_focus_order_{year}")
            if st.button("Thêm vào danh mục trọng tâm", key=f"inline_focus_save_{year}", type="primary"):
                if not code.strip() or not name.strip() or not desc.strip():
                    st.error("Vui lòng nhập đủ mã, tên và mô tả phạm vi.")
                    return
                ts = policy._now()
                try:
                    with get_conn() as c:
                        c.execute(
                            """INSERT INTO weekly_focus_categories(
                               department_key,apply_year,code,name,description,sort_order,active,
                               created_by,updated_by,created_at,updated_at)
                               VALUES(?,?,?,?,?,?,1,?,?,?,?)""",
                            (
                                scope, int(year), code.strip().upper(), name.strip(), desc.strip(),
                                int(order), uid, uid, ts, ts,
                            ),
                        )
                    st.toast("Đã bổ sung mục trọng tâm.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    policy._inline_focus_create = inline_focus_create

    # Final layers. The room-dashboard layer is deliberately last because it
    # consumes the final Customer Work card renderer and the final approval card
    # parity layer, then replaces only the leader dashboard presentation.
    _form_refinement.install(policy, None, None, logger)
    _unified.install(policy, logger)
    _final_defaults.install(policy, logger)
    _final_ux.install(policy, logger)
    _week_board_focus.install(policy, _customer_core, _customer_ui, _refinement, _worktype, logger)
    _followup_ux.install(policy, _customer_core, _customer_ui, _refinement, _worktype, logger)
    _dashboard_consolidation.install(policy, _weekly_core, _customer_core, _customer_ui, logger)
    _nav_approval_parity.install(policy, _customer_core, _customer_ui, logger)
    _room_dashboard.install(policy, _weekly_core, _customer_core, _customer_ui, logger)

    setattr(policy, _FLAG, VERSION)
    policy.VERSION = VERSION
    if logger:
        logger.info(
            "WEEKLY_PRIORITY_POLICY_HOTFIX_INSTALLED version=%s lifecycle_return=1 q2_watch=1 form_refinement=1 unified=1 final_defaults=1 final_ux=1 week_board_focus=1 followup_ux=1 dashboard_consolidation=1 nav_approval_parity=1 room_dashboard_detail=1",
            VERSION,
        )
