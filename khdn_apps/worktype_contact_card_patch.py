"""Planning/tác nghiệp work-type partition + Customer Work contact/card UX.

Installed after the existing Customer Work refinements so it can safely own:
- task_types.module_scope (OPS/PLAN), defaulting legacy rows to OPS;
- operational task pickers => OPS only; Customer Work picker => PLAN only;
- required contact name/phone/role on new Customer Work cases;
- clean form epoch after creation to avoid accidental duplicate submissions;
- compact in-card detail action instead of a full-width button below the card.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import html
import json

VERSION = "1.0.0"
SCOPE_LABEL = {"OPS": "Tác nghiệp", "PLAN": "Kế hoạch"}
CONTACT_ROLES = ["Giám đốc", "Chủ doanh nghiệp", "Kế toán trưởng/GĐ Tài chính", "Khác"]


def _columns(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_worktype_scope(get_conn, logger=None):
    with get_conn() as c:
        if "module_scope" not in _columns(c, "task_types"):
            c.execute("ALTER TABLE task_types ADD COLUMN module_scope TEXT NOT NULL DEFAULT 'OPS'")
        c.execute("UPDATE task_types SET module_scope='OPS' WHERE module_scope IS NULL OR trim(module_scope)='' OR module_scope NOT IN ('OPS','PLAN')")
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_types_scope_active ON task_types(module_scope,active,id)")
    if logger:
        logger.info("WORKTYPE_SCOPE_READY version=%s", VERSION)


def ensure_case_contacts(get_conn, logger=None):
    with get_conn() as c:
        cols = _columns(c, "customer_work_cases")
        if "contact_name" not in cols:
            c.execute("ALTER TABLE customer_work_cases ADD COLUMN contact_name TEXT")
        if "contact_phone" not in cols:
            c.execute("ALTER TABLE customer_work_cases ADD COLUMN contact_phone TEXT")
        if "contact_role" not in cols:
            c.execute("ALTER TABLE customer_work_cases ADD COLUMN contact_role TEXT")
    if logger:
        logger.info("CUSTOMER_WORK_CONTACT_SCHEMA_READY version=%s", VERSION)


def planning_task_types(c):
    rows = c.execute(
        """SELECT id,name,sla_hours,active,module_scope FROM task_types
           WHERE active=1 AND module_scope='PLAN'
           ORDER BY name COLLATE NOCASE,id"""
    ).fetchall()
    return [dict(r) for r in rows]


def _scope_label(v):
    return SCOPE_LABEL.get(str(v or "OPS"), "Tác nghiệp")


def _install_admin_type_scope(ns, logger=None):
    """Extend the legacy Loại công việc page without replacing its other controls.

    The original page contains working-hour controls and audit behavior we want to
    preserve.  We therefore intercept only its task-type SQL/widgets while that
    specific child page is rendering.
    """
    st = ns["st"]
    get_conn = ns["get_conn"]
    original_admin = ns["admin_page"]

    def active_task_types_ops():
        ensure_worktype_scope(get_conn, logger or ns.get("LOGGER"))
        return ns["qdf"](
            "SELECT name,sla_hours FROM task_types WHERE active=1 AND module_scope='OPS' ORDER BY id"
        )
    ns["active_task_types"] = active_task_types_ops

    def admin_page(u):
        is_type_page = (
            st.session_state.get("main_page") == "ops_admin"
            and st.session_state.get("admin_view") == "types"
        )
        if not is_type_page:
            return original_admin(u)

        ensure_worktype_scope(get_conn, logger or ns.get("LOGGER"))
        original_qdf = ns["qdf"]
        original_execute = ns["execute"]
        original_selectbox = st.selectbox
        original_form_submit = st.form_submit_button

        def qdf(sql, params=()):
            normalized = " ".join(str(sql).split()).lower()
            if normalized == "select id,name,active,created_at,updated_at from task_types order by id":
                sql = """SELECT id,name,
                         CASE module_scope WHEN 'PLAN' THEN 'Kế hoạch' ELSE 'Tác nghiệp' END AS \"Phân hệ\",
                         active,created_at,updated_at FROM task_types ORDER BY id"""
            return original_qdf(sql, params)

        def execute(sql, params=()):
            normalized = " ".join(str(sql).split()).lower()
            if normalized.startswith("insert into task_types(name,sla_hours,active,created_at,updated_at) values"):
                scope = str(st.session_state.get("_task_type_new_scope") or "OPS")
                return original_execute(
                    "INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) VALUES(?,8,1,?,?,?)",
                    (params[0], scope, params[1], params[2]),
                )
            if normalized == "update task_types set active=?,updated_at=? where id=?":
                scope = str(st.session_state.get("_task_type_edit_scope_current") or "OPS")
                return original_execute(
                    "UPDATE task_types SET active=?,module_scope=?,updated_at=? WHERE id=?",
                    (params[0], scope, params[1], params[2]),
                )
            return original_execute(sql, params)

        def selectbox(label, options, *args, **kwargs):
            value = original_selectbox(label, options, *args, **kwargs)
            if label == "Chọn loại công việc để sửa":
                with get_conn() as c:
                    row = c.execute("SELECT module_scope FROM task_types WHERE id=?", (int(value),)).fetchone()
                current = str(row[0] if row else "OPS")
                key = f"task_type_scope_edit_{int(value)}"
                if key not in st.session_state:
                    st.session_state[key] = current if current in SCOPE_LABEL else "OPS"
                scope = original_selectbox(
                    "Phân hệ áp dụng",
                    ["OPS", "PLAN"],
                    format_func=_scope_label,
                    key=key,
                    help="Tác nghiệp chỉ hiện ở phân hệ Tác nghiệp; Kế hoạch chỉ hiện ở phần Kế hoạch/Công việc khách hàng.",
                )
                st.session_state["_task_type_edit_scope_current"] = scope
            return value

        def form_submit_button(label, *args, **kwargs):
            if label == "Thêm loại công việc":
                original_selectbox(
                    "Thuộc phân hệ",
                    ["OPS", "PLAN"],
                    format_func=_scope_label,
                    key="_task_type_new_scope",
                    help="Loại công việc chỉ xuất hiện trong đúng phân hệ được chọn.",
                )
            return original_form_submit(label, *args, **kwargs)

        ns["qdf"] = qdf
        ns["execute"] = execute
        st.selectbox = selectbox
        st.form_submit_button = form_submit_button
        try:
            return original_admin(u)
        finally:
            ns["qdf"] = original_qdf
            ns["execute"] = original_execute
            st.selectbox = original_selectbox
            st.form_submit_button = original_form_submit

    ns["admin_page"] = admin_page


def _create_form(st, u, get_conn, customer_core, ui, refinement, logger=None):
    prospects = refinement.prospects
    ensure_worktype_scope(get_conn, logger)
    ensure_case_contacts(get_conn, logger)
    prospects.ensure_customer_master(get_conn, logger)

    prospects.render_quick_add(
        st, u, get_conn, "cw_new_customer", logger, select_state_key="cw_customer_pick"
    )
    uid = int(u["id"])
    manager = ui._manager(u)
    with get_conn() as c:
        cs = prospects.planning_customers(c, uid)
        stages = customer_core.active_stages(c)
        users = customer_core.staff_users(c) if manager else []
        types = planning_task_types(c)

    if not cs:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error(
            "Chưa có Loại công việc thuộc **Kế hoạch**. Lãnh đạo/Admin hãy tạo tại "
            "Tác nghiệp → Quản trị → Loại công việc và chọn phân hệ **Kế hoạch**."
        )
        return

    st.caption(
        f"Nhóm công việc chỉ lấy danh mục **Loại công việc · Kế hoạch** · {len(types)} loại đang sử dụng."
    )
    preferred = st.session_state.get("cw_customer_pick")
    idx = next((i for i, x in enumerate(cs) if int(x["id"]) == int(preferred or -1)), 0)
    epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)
    p = f"cwcf_{epoch}_"

    with st.form(f"cw_create_case_{epoch}", clear_on_submit=False):
        customer = st.selectbox("Khách hàng", cs, index=idx, format_func=prospects._label, key=p+"customer")
        case_type = st.selectbox("Nhóm công việc / Loại công việc", types, format_func=lambda x: x["name"], key=p+"type")
        title = st.text_input(
            "Công việc",
            placeholder="Ví dụ: Hạn mức tín dụng 2026 / Tiếp thị tiền gửi / Dự án A",
            key=p+"title",
        )

        st.markdown("**Thông tin liên hệ bắt buộc**")
        c0, c1, c2 = st.columns([1.35, 1, 1.15])
        contact_name = c0.text_input("Người liên hệ *", key=p+"contact_name")
        contact_phone = c1.text_input("SĐT liên hệ *", key=p+"contact_phone")
        contact_role = c2.selectbox("Chức vụ *", CONTACT_ROLES, key=p+"contact_role")

        c3, c4 = st.columns(2)
        due_date = c3.date_input("Dự kiến hoàn thành", value=date.today()+timedelta(days=7), key=p+"due_date")
        due_time = c4.time_input("Giờ dự kiến", value=time(17, 0), key=p+"due_time")
        stage = st.selectbox("Mục công việc bắt đầu", stages, format_func=lambda x: x["name"], key=p+"stage")
        owner = (
            st.selectbox(
                "Cán bộ phụ trách", users,
                format_func=lambda x: f"{x['full_name']} · {x['role']}", key=p+"owner"
            ) if manager else None
        )
        note = st.text_area("Ghi chú", height=80, key=p+"note")
        ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

    if not ok:
        return

    contact_name = str(contact_name or "").strip()
    contact_phone = str(contact_phone or "").strip()
    if not contact_name:
        st.error("Người liên hệ là thông tin bắt buộc.")
        return
    if not contact_phone:
        st.error("SĐT liên hệ là thông tin bắt buộc.")
        return

    try:
        due = datetime.combine(due_date, due_time).strftime("%Y-%m-%d %H:%M:%S")
        cid, state = customer_core.create_case(
            get_conn, uid, customer["id"], title, due,
            owner_uid=owner["id"] if owner else uid,
            case_type=case_type["name"], note=note, stage_id=stage["id"], logger=logger,
        )
        ts = customer_core.now_str()
        with get_conn() as c:
            c.execute(
                "UPDATE customer_work_cases SET contact_name=?,contact_phone=?,contact_role=?,updated_at=? WHERE id=?",
                (contact_name, contact_phone, str(contact_role), ts, int(cid)),
            )
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (
                    int(cid), uid, "CONTACT_SET",
                    json.dumps({"name": contact_name, "phone": contact_phone, "role": contact_role}, ensure_ascii=False),
                    ts,
                ),
            )

        # Force an entirely fresh widget identity for the next create operation.
        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        for key in list(st.session_state.keys()):
            if str(key).startswith(p) or str(key).startswith("cw_new_customer_"):
                st.session_state.pop(key, None)

        # Open the just-created case; when the user returns to New Work, the form
        # is a new epoch and therefore contains no stale values from this case.
        st.session_state["cw_case_id"] = int(cid)
        st.toast(
            "Đã tạo công việc." if state == "APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.",
            icon="✅",
        )
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def _card(st, ui, x, get_conn, uid, manager, logger=None, compact=False):
    refinement = __import__("khdn_apps.customer_work_refinement_patch", fromlist=["_HEAT"])
    q = refinement._q(x.get("quadrant"))
    heat = refinement._HEAT[q]
    status_text, status_color, status_bg = refinement._status_meta(x)
    customer = html.escape(str(x.get("customer_name") or "—"))
    case_type = html.escape(str(x.get("case_type") or x.get("title") or "Công việc"))
    title = html.escape(str(x.get("title") or ""))
    code = html.escape(str(x.get("case_code") or ""))
    owner = html.escape(str(x.get("owner_name") or "—"))
    stage = html.escape(str(x.get("stage_name") or "—"))
    elapsed = html.escape(ui.core.duration_text(x.get("stage_elapsed_hours")))
    due = html.escape(ui._dt_text(x.get("expected_complete_at")))
    issues = int(x.get("open_issue_count") or 0)
    priority = html.escape(ui.core.quadrant_label(q))
    contact = html.escape(str(x.get("contact_name") or ""))
    contact_phone = html.escape(str(x.get("contact_phone") or ""))
    contact_role = html.escape(str(x.get("contact_role") or ""))
    approval = str(x.get("plan_approval_status") or "PENDING")
    cid = int(x["id"])

    with st.container(key=f"cw_case_card_{cid}", border=True):
        h1, h2 = st.columns([8.5, 1.5], vertical_alignment="top")
        with h1:
            st.markdown(
                f"<div class='cw-inline-title'>{customer} <span>·</span> {case_type}</div>"
                + (f"<div class='cw-inline-work'>📌 {title}</div>" if title and title.casefold()!=case_type.casefold() else ""),
                unsafe_allow_html=True,
            )
        with h2:
            if not compact and st.button("Chi tiết", key=f"cw_open_{cid}", help="Mở chi tiết công việc"):
                st.session_state["cw_case_id"] = cid
                st.rerun()
        st.markdown(
            f"<div class='cw-inline-code'>{code}</div>"
            f"<div class='cw-inline-row'>"
            f"<span>👤 <b>{owner}</b></span><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span>"
            f"<span class='cw-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>"
            f"<div class='cw-inline-row'><span>🎯 <b>Dự kiến:</b> {due}</span>"
            f"<span>⚠ <b>Vướng mắc:</b> {issues}</span>"
            f"<span class='cw-pill' style='color:{heat['accent']};background:{heat['bg']};border:1px solid {heat['border']}'>{heat['icon']} {priority}</span></div>"
            + (f"<div class='cw-contact'>☎ <b>{contact}</b> · {contact_role} · {contact_phone}</div>" if contact or contact_phone else "")
            + f"""<style>
            div[class*='st-key-cw_case_card_{cid}']{{border-left:6px solid {heat['accent']}!important;background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;box-shadow:0 6px 16px rgba(0,0,0,.09)}}
            div[class*='st-key-cw_case_card_{cid}'] button{{min-height:2rem!important;padding:.18rem .55rem!important;font-size:.78rem!important}}
            .cw-inline-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}.cw-inline-title span{{opacity:.7}}
            .cw-inline-work{{font-size:.82rem;font-weight:750;margin-top:3px}}.cw-inline-code{{font-size:.76rem;font-weight:900;color:#F4B41A;margin:.05rem 0 .35rem 0}}
            .cw-inline-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:6px}}.cw-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}
            .cw-contact{{font-size:.80rem;margin-top:7px;opacity:.94}}
            @media(max-width:760px){{.cw-inline-title{{font-size:.96rem}}.cw-inline-row,.cw-contact{{font-size:.76rem}}}}
            </style>""",
            unsafe_allow_html=True,
        )
        if approval == "PENDING":
            st.warning("Kế hoạch công việc đang chờ phê duyệt.")
        elif approval == "REJECTED":
            st.error("Kế hoạch đã bị từ chối." + (f" {x.get('approval_note')}" if x.get("approval_note") else ""))


def install(ns, customer_core, customer_ui, refinement_module, logger=None):
    if getattr(customer_core, "_WORKTYPE_CONTACT_CARD_INSTALLED", False):
        return
    get_conn = ns["get_conn"]
    app_logger = logger or ns.get("LOGGER")

    # Core schema must exist before contact columns are added.
    customer_core.ensure_schema(get_conn, app_logger)
    ensure_worktype_scope(get_conn, app_logger)
    ensure_case_contacts(get_conn, app_logger)

    # Keep future schema calls migration-safe.
    original_ensure = customer_core.ensure_schema
    def ensure_schema(get_conn_arg, logger_arg=None):
        original_ensure(get_conn_arg, logger_arg or app_logger)
        ensure_case_contacts(get_conn_arg, logger_arg or app_logger)
    customer_core.ensure_schema = ensure_schema

    _install_admin_type_scope(ns, app_logger)

    # Final Customer Work renderer references these module-level helpers at run time.
    refinement_module._task_types = planning_task_types
    refinement_module._create_form = lambda st,u,get_conn,customer_core_arg,ui,logger=None: _create_form(
        st,u,get_conn,customer_core_arg,ui,refinement_module,logger or app_logger
    )
    refinement_module._card = _card

    customer_core._WORKTYPE_CONTACT_CARD_INSTALLED = True
    if app_logger:
        app_logger.info("WORKTYPE_CONTACT_CARD_PATCH_INSTALLED version=%s", VERSION)
