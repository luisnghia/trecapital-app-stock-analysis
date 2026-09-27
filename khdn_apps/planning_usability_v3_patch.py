"""Final planning usability V3.

Business UX additions:
- required fields turn red after an incomplete submit;
- non-manager staff own their newly-created customer work by default;
- every customer-work item has a controlling leader;
- Customer Work always re-enters on "Đang xử lý";
- cards show original creation time;
- child command tabs use the exact same visual component as the main Kế hoạch bar.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import html
import json

from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_ui_admin_hotfix as ui_hotfix

VERSION = "4.0.0"


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _columns(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _ensure_controller_schema(get_conn, customer_core, logger=None):
    customer_core.ensure_schema(get_conn, logger)
    with get_conn() as c:
        cols = _columns(c, "customer_work_cases")
        if "controller_user_id" not in cols:
            c.execute("ALTER TABLE customer_work_cases ADD COLUMN controller_user_id INTEGER")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_cw_controller "
            "ON customer_work_cases(controller_user_id,status)"
        )


def _install_controller_core(customer_core, get_conn, logger=None):
    if getattr(customer_core, "_PLANNING_USABILITY_V3_CONTROLLER", False):
        return

    original_ensure = customer_core.ensure_schema
    original_select = customer_core._case_select_sql

    def ensure_schema(conn_fn, logger_arg=None):
        original_ensure(conn_fn, logger_arg or logger)
        with conn_fn() as c:
            if "controller_user_id" not in _columns(c, "customer_work_cases"):
                c.execute("ALTER TABLE customer_work_cases ADD COLUMN controller_user_id INTEGER")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_cw_controller "
                "ON customer_work_cases(controller_user_id,status)"
            )

    def case_select_sql():
        sql = original_select()
        if "controller_name" in sql:
            return sql
        needle = "LEFT JOIN important_categories ic ON ic.id=w.important_category_id"
        replacement = (
            "LEFT JOIN important_categories ic ON ic.id=w.important_category_id\n"
            "              LEFT JOIN users ctrl ON ctrl.id=w.controller_user_id"
        )
        sql = sql.replace(needle, replacement)
        sql = sql.replace(
            "ic.name AS important_category,",
            "ic.name AS important_category,ctrl.full_name AS controller_name,"
        )
        return sql

    customer_core.ensure_schema = ensure_schema
    customer_core._case_select_sql = case_select_sql
    customer_core._PLANNING_USABILITY_V3_CONTROLLER = True
    _ensure_controller_schema(get_conn, customer_core, logger)


def _missing_css(st, keys):
    """Highlight only invalid required fields after submit."""
    keys = [str(k) for k in keys if k]
    if not keys:
        return
    rules = []
    for key in keys:
        root = f'div[class*="st-key-{key}"]'
        rules.append(
            f"""
            {root} [data-baseweb="input"] > div,
            {root} [data-baseweb="select"] > div,
            {root} textarea,
            {root} input {{
                border:2px solid #FF4B4B!important;
                box-shadow:0 0 0 2px rgba(255,75,75,.18)!important;
                background:rgba(255,75,75,.055)!important;
            }}
            {root} label, {root} label p {{
                color:#FF6B6B!important;
                font-weight:900!important;
            }}
            """
        )
    st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)


def _leader_users(c):
    return [
        dict(r)
        for r in c.execute(
            """SELECT id,full_name,role,is_admin
               FROM users
               WHERE active=1 AND role='Lãnh đạo phòng'
               ORDER BY full_name,id"""
        ).fetchall()
    ]


def _create_form(st, u, get_conn, customer_core, customer_ui, refinement, worktype, logger=None):
    prospects = refinement.prospects
    worktype.ensure_worktype_scope(get_conn, logger)
    worktype.ensure_case_contacts(get_conn, logger)
    _ensure_controller_schema(get_conn, customer_core, logger)
    prospects.ensure_customer_master(get_conn, logger)

    uid = int(_uget(u, "id") or 0)
    manager = customer_ui._manager(u)
    epoch = int(st.session_state.get("cw_create_epoch", 0) or 0)
    prospects.render_quick_add(
        st,
        u,
        get_conn,
        f"cw_new_customer_{epoch}",
        logger,
        select_state_key="cw_customer_pick",
    )

    with get_conn() as c:
        customers = prospects.planning_customers(c, uid)
        stages = customer_core.active_stages(c)
        users = customer_core.staff_users(c) if manager else []
        types = worktype.planning_task_types(c)
        leaders = _leader_users(c)

    if not customers:
        st.warning("Chưa có khách hàng. Có thể thêm khách hàng mới/chưa có CIF ngay phía trên.")
        return
    if not types:
        st.error("Chưa có Loại công việc thuộc **Kế hoạch**. Admin hãy tạo tại **Quản trị hệ thống → Loại công việc**.")
        return
    if not leaders:
        st.error("Chưa có **Lãnh đạo phòng** đang hoạt động để chọn Lãnh đạo kiểm soát. Vui lòng cấu hình người dùng trước.")
        return

    st.caption(
        f"Nhóm công việc lấy từ **Quản trị hệ thống → Loại công việc → Kế hoạch** · "
        f"{len(types)} loại đang sử dụng."
    )
    preferred = st.session_state.get("cw_customer_pick")
    preferred_index = next(
        (i for i, x in enumerate(customers) if int(x["id"]) == int(preferred or -1)),
        None,
    )
    p = f"cwuv3_{epoch}_"

    # Re-render invalid widgets in red on the run immediately following validation.
    invalid_keys = st.session_state.get(f"cwuv3_invalid_{epoch}") or []
    _missing_css(st, invalid_keys)

    with st.form(f"cwuv3_create_{epoch}", clear_on_submit=False):
        customer = st.selectbox(
            "Khách hàng *",
            customers,
            index=preferred_index,
            placeholder="— Chọn khách hàng —",
            format_func=prospects._label,
            key=p + "customer",
        )
        case_type = st.selectbox(
            "Nhóm công việc / Loại công việc *",
            types,
            index=None,
            placeholder="— Chọn loại công việc —",
            format_func=lambda x: x["name"],
            key=p + "type",
        )
        title = st.text_input(
            "Công việc *",
            placeholder="Ví dụ: Cấp hạn mức tín dụng / Tiếp thị tiền gửi / Dự án A",
            key=p + "title",
        )

        st.markdown("**Thông tin liên hệ bắt buộc**")
        c0, c1, c2 = st.columns([1.35, 1, 1.15])
        contact_name = c0.text_input("Người liên hệ *", key=p + "contact_name")
        contact_phone = c1.text_input("SĐT liên hệ *", key=p + "contact_phone")
        contact_role = c2.selectbox(
            "Chức vụ *",
            v2.CONTACT_ROLES,
            index=None,
            placeholder="— Chọn chức vụ —",
            key=p + "contact_role",
        )

        priority = st.selectbox(
            "Ưu tiên góc phần tư *",
            [1, 2, 3, 4],
            index=None,
            placeholder="— Chọn Q1 / Q2 / Q3 / Q4 —",
            format_func=v2._priority_label,
            key=p + "priority",
            help="CBKH đề xuất mức ưu tiên khi tạo công việc; Lãnh đạo/Admin có thể điều chỉnh khi phê duyệt.",
        )
        c3, c4 = st.columns(2)
        due_date = c3.date_input(
            "Dự kiến hoàn thành",
            value=date.today() + timedelta(days=7),
            key=p + "due_date",
        )
        due_time = c4.time_input(
            "Giờ dự kiến",
            value=time(17, 0),
            key=p + "due_time",
        )
        stage = st.selectbox(
            "Mục công việc bắt đầu *",
            stages,
            index=None,
            placeholder="— Chọn mục công việc —",
            format_func=lambda x: x["name"],
            key=p + "stage",
        )

        # Staff own their own newly-created work by default; managers can assign.
        if manager:
            owner = st.selectbox(
                "Cán bộ phụ trách *",
                users,
                index=None,
                placeholder="— Chọn cán bộ phụ trách —",
                format_func=lambda x: f"{x['full_name']} · {x['role']}",
                key=p + "owner",
            )
        else:
            current_owner = {
                "id": uid,
                "full_name": str(_uget(u, "full_name") or _uget(u, "username") or f"CB {uid}"),
                "role": str(_uget(u, "role") or ""),
            }
            owner = st.selectbox(
                "Cán bộ phụ trách *",
                [current_owner],
                index=0,
                format_func=lambda x: f"{x['full_name']} · {x['role']}",
                key=p + "owner",
                disabled=True,
            )

        current_is_leader = str(_uget(u, "role") or "") == "Lãnh đạo phòng"
        own_leader_index = next(
            (i for i, x in enumerate(leaders) if int(x["id"]) == uid),
            None,
        )
        controller = st.selectbox(
            "Lãnh đạo kiểm soát *",
            leaders,
            index=own_leader_index if current_is_leader else None,
            placeholder="— Chọn lãnh đạo kiểm soát —",
            format_func=lambda x: x["full_name"],
            key=p + "controller",
            help="Lãnh đạo theo dõi/kiểm soát tiến độ của công việc này.",
        )

        note = st.text_area("Ghi chú", height=80, key=p + "note")
        ok = st.form_submit_button("Tạo công việc", type="primary", use_container_width=True)

    if not ok:
        return

    checks = [
        ("Khách hàng", customer is None, p + "customer"),
        ("Loại công việc", case_type is None, p + "type"),
        ("Công việc", not str(title or "").strip(), p + "title"),
        ("Người liên hệ", not str(contact_name or "").strip(), p + "contact_name"),
        ("SĐT liên hệ", not str(contact_phone or "").strip(), p + "contact_phone"),
        ("Chức vụ", contact_role is None, p + "contact_role"),
        ("Ưu tiên góc phần tư", priority is None, p + "priority"),
        ("Mục công việc bắt đầu", stage is None, p + "stage"),
        ("Cán bộ phụ trách", owner is None, p + "owner"),
        ("Lãnh đạo kiểm soát", controller is None, p + "controller"),
    ]
    missing = [label for label, failed, _ in checks if failed]
    missing_keys = [key for _, failed, key in checks if failed]
    if missing:
        st.session_state[f"cwuv3_invalid_{epoch}"] = missing_keys
        _missing_css(st, missing_keys)
        st.error("Vui lòng nhập/chọn đầy đủ các ô viền đỏ: " + ", ".join(missing) + ".")
        return
    st.session_state.pop(f"cwuv3_invalid_{epoch}", None)

    try:
        due = datetime.combine(due_date, due_time).strftime("%Y-%m-%d %H:%M:%S")
        cid, state = customer_core.create_case(
            get_conn,
            uid,
            customer["id"],
            str(title).strip(),
            due,
            owner_uid=int(owner["id"]),
            case_type=case_type["name"],
            note=note,
            stage_id=stage["id"],
            logger=logger,
        )
        ts = customer_core.now_str()
        with get_conn() as c:
            c.execute(
                """UPDATE customer_work_cases
                   SET contact_name=?,contact_phone=?,contact_role=?,
                       controller_user_id=?,updated_at=?
                   WHERE id=?""",
                (
                    str(contact_name).strip(),
                    str(contact_phone).strip(),
                    str(contact_role),
                    int(controller["id"]),
                    ts,
                    int(cid),
                ),
            )
            v2._set_case_priority(c, cid, int(priority), ts)
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (
                    int(cid),
                    uid,
                    "CREATE_METADATA_V3",
                    json.dumps(
                        {
                            "contact_name": str(contact_name).strip(),
                            "contact_phone": str(contact_phone).strip(),
                            "contact_role": contact_role,
                            "priority_quadrant": int(priority),
                            "owner_user_id": int(owner["id"]),
                            "controller_user_id": int(controller["id"]),
                            "controller_name": str(controller.get("full_name") or ""),
                        },
                        ensure_ascii=False,
                    ),
                    ts,
                ),
            )

        st.session_state["cw_create_epoch"] = epoch + 1
        st.session_state.pop("cw_customer_pick", None)
        st.session_state.pop("cw_case_id", None)
        st.session_state["cw_view"] = "processing"
        st.toast(
            "Đã tạo công việc."
            if state == "APPROVED"
            else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.",
            icon="✅",
        )
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def _card(st, customer_ui, refinement, x, get_conn, uid, manager, logger=None, compact=False):
    q = v2._q(x.get("quadrant")) or 4
    heat = refinement._HEAT[q]
    status_text, status_color, status_bg = refinement._status_meta(x)
    customer = html.escape(str(x.get("customer_name") or "—"))
    case_type = html.escape(str(x.get("case_type") or x.get("title") or "Công việc"))
    title = html.escape(str(x.get("title") or ""))
    code = html.escape(str(x.get("case_code") or ""))
    owner = html.escape(str(x.get("owner_name") or "—"))
    controller = html.escape(str(x.get("controller_name") or "—"))
    stage = html.escape(str(x.get("stage_name") or "—"))
    elapsed = html.escape(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    created = html.escape(customer_ui._dt_text(x.get("created_at")))
    due = html.escape(customer_ui._dt_text(x.get("expected_complete_at")))
    issues = int(x.get("open_issue_count") or 0)
    contact = html.escape(str(x.get("contact_name") or ""))
    contact_phone = html.escape(str(x.get("contact_phone") or ""))
    contact_role = html.escape(str(x.get("contact_role") or ""))
    approval = str(x.get("plan_approval_status") or "PENDING")
    cid = int(x["id"])

    with st.container(key=f"cwuv3_card_{cid}", border=True):
        c1, c2, c3 = st.columns([5.5, 1.5, 3.0], vertical_alignment="top")
        with c1:
            st.markdown(
                f"<div class='cwuv3-title'>{customer} <span>·</span> {case_type}</div>"
                + (
                    f"<div class='cwuv3-work'>📌 {title}</div>"
                    if title and title.casefold() != case_type.casefold()
                    else ""
                ),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"<div class='cwuv3-code'>{code}</div>", unsafe_allow_html=True)
        with c3:
            if not compact and st.button(
                "🔎 Chi tiết", key=f"cwuv3_open_{cid}", use_container_width=True
            ):
                st.session_state["cw_case_id"] = cid
                st.rerun()

        st.markdown(
            f"<div class='cwuv3-row'><span>🕒 <b>Tạo lúc:</b> {created}</span>"
            f"<span>👤 <b>Phụ trách:</b> {owner}</span>"
            f"<span>🛡️ <b>Kiểm soát:</b> {controller}</span></div>"
            f"<div class='cwuv3-row'><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span>"
            f"<span class='cwuv3-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>"
            f"<div class='cwuv3-row'><span>🎯 <b>Dự kiến:</b> {due}</span>"
            f"<span>⚠ <b>Vướng mắc:</b> {issues}</span>"
            f"<span class='cwuv3-pill' style='color:{heat['accent']};background:{heat['bg']};"
            f"border:1px solid {heat['border']}'>{v2._priority_label(q)}</span></div>"
            + (
                f"<div class='cwuv3-contact'>☎ <b>{contact}</b> · {contact_role} · {contact_phone}</div>"
                if contact or contact_phone
                else ""
            )
            + f"""
            <style>
            div[class*='st-key-cwuv3_card_{cid}']{{
                border-left:6px solid {heat['accent']}!important;
                background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;
                box-shadow:0 6px 16px rgba(0,0,0,.09)
            }}
            div[class*='st-key-cwuv3_card_{cid}'] button{{
                background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
                color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
                border:2px solid #FFE589!important;font-weight:950!important;
                min-height:2.25rem!important
            }}
            div[class*='st-key-cwuv3_card_{cid}'] button *{{
                color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important
            }}
            .cwuv3-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}
            .cwuv3-title span{{opacity:.7}}
            .cwuv3-work{{font-size:.82rem;font-weight:750;margin-top:3px}}
            .cwuv3-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .cwuv3-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px}}
            .cwuv3-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}
            .cwuv3-contact{{font-size:.80rem;margin-top:7px;opacity:.94}}
            @media(max-width:760px){{
                .cwuv3-title{{font-size:.96rem}}
                .cwuv3-row,.cwuv3-contact{{font-size:.76rem}}
                .cwuv3-code{{text-align:left}}
            }}
            </style>""",
            unsafe_allow_html=True,
        )
        if approval == "PENDING":
            st.warning("Kế hoạch công việc đang chờ phê duyệt.")
        elif approval == "REJECTED":
            st.error(
                "Kế hoạch đã bị từ chối."
                + (f" {x.get('approval_note')}" if x.get("approval_note") else "")
            )


def _exact_child_nav(st, state_key, options, default=None, prefix="subnav"):
    # Always use the same native-button renderer and CSS as the main Kế hoạch bar.
    return ui_hotfix._local_command_tabs(
        st, state_key, options, default=default, prefix=prefix
    )


def _install_main_customer_reset(nav_module, ns, logger=None):
    """Clicking the main Customer Work command always lands on Processing."""
    if getattr(nav_module, "_CW_ALWAYS_PROCESSING_V3", False):
        return
    original_tabs = nav_module._render_command_tabs

    def render_command_tabs(st_arg, section, current, options, role, admin):
        original_button = st_arg.button

        def button(label, *args, **kwargs):
            clicked = original_button(label, *args, **kwargs)
            if clicked and str(label).strip() == "Công việc khách hàng":
                st_arg.session_state["cw_view"] = "processing"
                st_arg.session_state.pop("cw_case_id", None)
            return clicked

        st_arg.button = button
        try:
            return original_tabs(st_arg, section, current, options, role, admin)
        finally:
            st_arg.button = original_button

    nav_module._render_command_tabs = render_command_tabs
    nav_module._CW_ALWAYS_PROCESSING_V3 = True
    if logger:
        logger.info("CUSTOMER_WORK_MAIN_RESET_V3_INSTALLED")


def install(ns, customer_core, customer_ui, refinement, worktype, nav_module, logger=None):
    if getattr(customer_ui, "_PLANNING_USABILITY_V3_INSTALLED", False):
        return
    app_logger = logger or ns.get("LOGGER")
    get_conn = ns["get_conn"]

    _install_controller_core(customer_core, get_conn, app_logger)
    _install_main_customer_reset(nav_module, ns, app_logger)

    # v2 renderers resolve these globals at call time; replace them once, finally.
    v2._create_form = _create_form
    v2._card = _card

    def case_card(st_arg, x, get_conn_arg, uid, manager, logger_arg=None, compact=False):
        return _card(
            st_arg,
            customer_ui,
            refinement,
            x,
            get_conn_arg,
            uid,
            manager,
            logger_arg or app_logger,
            compact,
        )

    def create_case_form(st_arg, u, get_conn_arg, logger_arg=None):
        return _create_form(
            st_arg,
            u,
            get_conn_arg,
            customer_core,
            customer_ui,
            refinement,
            worktype,
            logger_arg or app_logger,
        )

    def render_cases_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return v2._render_cases_page(
            st_arg,
            u,
            conn_fn,
            customer_core,
            customer_ui,
            refinement,
            worktype,
            _exact_child_nav,
            page_title,
            logger or app_logger,
        )

    def render_catalog_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return v2._render_catalog(
            st_arg,
            u,
            conn_fn,
            customer_core,
            customer_ui,
            _exact_child_nav,
            page_title,
            logger or app_logger,
        )

    customer_ui._case_card = case_card
    customer_ui._create_case_form = create_case_form
    customer_ui.render_cases_page = render_cases_page
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui._PLANNING_USABILITY_V3_INSTALLED = True

    if app_logger:
        app_logger.info("PLANNING_USABILITY_V3_INSTALLED version=%s", VERSION)
