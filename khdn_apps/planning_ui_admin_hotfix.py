"""Planning UI/Admin hotfix.

Installed around planning_usability_v2:
- local child navigation uses the exact same command-tab visual language as the
  main Kế hoạch bar (cream inactive buttons, teal+gold active button);
- System Admin reliably exposes and renders Loại công việc with module scope;
- approval renderer accepts the dispatcher's ``get_conn=`` keyword.
"""
from __future__ import annotations

import sqlite3

VERSION = "3.0.0"


def _command_tabs_css(st):
    st.markdown(
        """
        <style>
        div[class*="st-key-khdn_subnav_bar"]{
          margin:.10rem 0 1.00rem 0!important;
          padding:.42rem .48rem!important;
          border:1px solid rgba(218,190,99,.48)!important;
          border-radius:9px!important;
          background:rgba(244,241,223,.055)!important;
          box-shadow:0 7px 18px rgba(0,0,0,.10)!important;
        }
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stHorizontalBlock"]{
          gap:.42rem!important;align-items:stretch!important;
        }
        div[class*="st-key-khdn_subnav_bar"] [data-testid="column"]{min-width:0!important;}
        div[class*="st-key-khdn_subnav_bar"] button{
          min-height:43px!important;height:100%!important;padding:.42rem .65rem!important;
          border-radius:5px!important;font-size:.88rem!important;font-weight:800!important;
          line-height:1.16!important;white-space:normal!important;overflow-wrap:anywhere!important;
          transition:transform .10s ease,box-shadow .10s ease,background .10s ease!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button[kind="secondary"],
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-secondary"]{
          background:#F3F1E3!important;color:#173B38!important;-webkit-text-fill-color:#173B38!important;
          border:1px solid #D8C77E!important;box-shadow:0 3px 0 #9AAE98!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button[kind="secondary"] *,
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-secondary"] *{
          color:#173B38!important;-webkit-text-fill-color:#173B38!important;font-weight:800!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button[kind="primary"],
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-primary"]{
          background:linear-gradient(135deg,#075C57 0%,#0F746B 100%)!important;
          color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
          border:2px solid #F4B41A!important;
          box-shadow:0 3px 0 #C7900D,0 5px 12px rgba(0,0,0,.20)!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button[kind="primary"] *,
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-primary"] *{
          color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;font-weight:900!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button:hover{transform:translateY(-1px)!important;filter:brightness(1.035)!important;}
        @media (max-width:900px){
          div[class*="st-key-khdn_subnav_bar"]{padding:.34rem!important;}
          div[class*="st-key-khdn_subnav_bar"] [data-testid="stHorizontalBlock"]{gap:.26rem!important;}
          div[class*="st-key-khdn_subnav_bar"] button{font-size:.72rem!important;padding:.34rem .30rem!important;min-height:42px!important;}
        }
        @media (max-width:620px){
          div[class*="st-key-khdn_subnav_bar"] button{font-size:.64rem!important;padding:.28rem .18rem!important;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _local_command_tabs(st, state_key, options, default=None, prefix="subnav"):
    options = list(options or [])
    if not options:
        return None
    values = [x[0] for x in options]
    current = st.session_state.get(state_key)
    if current not in values:
        current = default if default in values else values[0]
        st.session_state[state_key] = current
    _command_tabs_css(st)
    widths = [max(1.0, min(2.7, len(str(label))/11.0)) for _, label in options]
    with st.container(key=f"khdn_subnav_bar_{prefix}"):
        cols = st.columns(widths, gap="small")
        for idx, (col, (value, label)) in enumerate(zip(cols, options)):
            with col:
                if st.button(
                    str(label),
                    key=f"local_cmd_{prefix}_{idx}_{value}",
                    use_container_width=True,
                    type="primary" if value == current else "secondary",
                ):
                    st.session_state[state_key] = value
                    st.rerun()
    return current


def install_pre(ns, logger=None):
    """Run immediately before planning_usability_v2 so its captured pill_nav
    delegates Customer Work/Catalog child navigation to our command tabs."""
    if ns.get("_PLANNING_UI_ADMIN_HOTFIX_PRE"):
        return
    st = ns["st"]
    original = ns["pill_nav"]

    def pill_nav(state_key, options, default=None, prefix="subnav"):
        if state_key in {"cw_view", "cw_catalog_view_v2"}:
            return _local_command_tabs(st, state_key, options, default=default, prefix=prefix)
        return original(state_key, options, default=default, prefix=prefix)

    ns["pill_nav"] = pill_nav
    ns["_PLANNING_UI_ADMIN_HOTFIX_PRE"] = True
    log = logger or ns.get("LOGGER")
    if log:
        log.info("PLANNING_UI_ADMIN_HOTFIX_PRE version=%s", VERSION)


def _scope_label(v):
    return "Kế hoạch" if str(v or "OPS") == "PLAN" else "Tác nghiệp"


def _render_system_task_types(ns, u, worktype, logger=None):
    st = ns["st"]
    get_conn = ns["get_conn"]
    page_title = ns.get("page_title")
    if page_title:
        page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF và loại công việc.")
    else:
        st.title("Quản trị hệ thống")

    # Exact command-tab format, including navigation back to Users / Customers.
    st.session_state["system_admin_view_v3"] = "types"
    _command_tabs_css(st)
    options = [("users", "👥 Người dùng"), ("customers", "🏢 Khách hàng CIF"), ("types", "🧩 Loại công việc")]
    widths = [max(1.0, min(2.7, len(label)/11.0)) for _, label in options]
    with st.container(key="khdn_subnav_bar_system_admin_v3"):
        cols = st.columns(widths, gap="small")
        for idx, (col, (value, label)) in enumerate(zip(cols, options)):
            with col:
                if st.button(
                    label,
                    key=f"system_admin_v3_{idx}_{value}",
                    use_container_width=True,
                    type="primary" if value == "types" else "secondary",
                ):
                    st.session_state["admin_scope"] = "system"
                    st.session_state["admin_view"] = value
                    st.session_state["system_admin_view_v2"] = value
                    st.session_state["system_admin_view_v3"] = value
                    st.rerun()

    worktype.ensure_worktype_scope(get_conn, logger or ns.get("LOGGER"))
    st.subheader("Loại công việc")
    st.caption("Danh mục dùng chung toàn hệ thống. Mỗi loại được gán đúng một phân hệ: **Tác nghiệp** hoặc **Kế hoạch**; loại thuộc phân hệ nào chỉ xuất hiện tại phân hệ đó.")

    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,name,module_scope,active,created_at,updated_at FROM task_types ORDER BY id"
        ).fetchall()]
    if rows:
        show = []
        for r in rows:
            show.append({
                "ID": int(r["id"]),
                "Tên công việc": r["name"],
                "Phân hệ": _scope_label(r.get("module_scope")),
                "Trạng thái": "Đang sử dụng" if r.get("active") else "Ngưng",
                "Ngày tạo": r.get("created_at"),
                "Cập nhật": r.get("updated_at"),
            })
        st.dataframe(show, use_container_width=True, hide_index=True)
    else:
        st.info("Chưa có Loại công việc.")

    st.markdown("#### Tạo loại công việc")
    with st.form("system_task_type_create_v3", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        new_name = c1.text_input("Tên công việc mới *")
        new_scope = c2.selectbox("Thuộc phân hệ *", ["OPS", "PLAN"], format_func=_scope_label)
        create = st.form_submit_button("Thêm loại công việc", type="primary")
    if create:
        clean = str(new_name or "").strip()
        if not clean:
            st.error("Bắt buộc nhập tên Loại công việc.")
        else:
            try:
                ts = ns["now_str"]() if "now_str" in ns else __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with get_conn() as c:
                    exists = c.execute("SELECT id FROM task_types WHERE lower(trim(name))=lower(trim(?))", (clean,)).fetchone()
                    if exists:
                        raise ValueError("Tên Loại công việc đã tồn tại.")
                    cur = c.execute(
                        "INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) VALUES(?,8,1,?,?,?)",
                        (clean, str(new_scope), ts, ts),
                    )
                    new_id = int(cur.lastrowid)
                audit = ns.get("audit")
                if audit:
                    audit(int(u["id"]), "CREATE_TASK_TYPE", "task_type", new_id, f"name={clean}; module_scope={new_scope}")
                st.toast("Đã thêm Loại công việc.", icon="✅"); st.rerun()
            except (sqlite3.IntegrityError, ValueError) as exc:
                st.error(str(exc))

    if rows:
        st.markdown("#### Sửa loại công việc")
        by_id = {int(r["id"]): r for r in rows}
        selected = st.selectbox(
            "Chọn loại công việc để sửa",
            list(by_id),
            format_func=lambda x: f"{by_id[int(x)]['name']} · {_scope_label(by_id[int(x)].get('module_scope'))}",
            key="system_task_type_edit_pick_v3",
        )
        cur = by_id[int(selected)]
        with st.form(f"system_task_type_edit_v3_{int(selected)}"):
            e1, e2 = st.columns([2, 1])
            edit_name = e1.text_input("Tên công việc", value=str(cur.get("name") or ""))
            scope_options = ["OPS", "PLAN"]
            current_scope = str(cur.get("module_scope") or "OPS")
            edit_scope = e2.selectbox("Thuộc phân hệ", scope_options, index=scope_options.index(current_scope if current_scope in scope_options else "OPS"), format_func=_scope_label)
            edit_active = st.checkbox("Đang sử dụng", value=bool(cur.get("active")))
            save = st.form_submit_button("Lưu thay đổi", type="primary")
        if save:
            clean = str(edit_name or "").strip()
            if not clean:
                st.error("Tên Loại công việc không được để trống.")
            else:
                try:
                    ts = ns["now_str"]() if "now_str" in ns else __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with get_conn() as c:
                        clash = c.execute(
                            "SELECT id FROM task_types WHERE lower(trim(name))=lower(trim(?)) AND id<>?",
                            (clean, int(selected)),
                        ).fetchone()
                        if clash:
                            raise ValueError("Tên Loại công việc đã tồn tại.")
                        c.execute(
                            "UPDATE task_types SET name=?,module_scope=?,active=?,updated_at=? WHERE id=?",
                            (clean, str(edit_scope), int(bool(edit_active)), ts, int(selected)),
                        )
                    audit = ns.get("audit")
                    if audit:
                        audit(int(u["id"]), "UPDATE_TASK_TYPE", "task_type", int(selected), f"name={clean}; module_scope={edit_scope}; active={bool(edit_active)}")
                    st.toast("Đã cập nhật Loại công việc.", icon="✅"); st.rerun()
                except (sqlite3.IntegrityError, ValueError) as exc:
                    st.error(str(exc))


def install_post(ns, customer_ui, worktype, logger=None):
    """Run after planning_usability_v2. Own final System Admin type page and fix
    the approval dispatch signature."""
    if ns.get("_PLANNING_UI_ADMIN_HOTFIX_POST"):
        return
    st = ns["st"]
    app_logger = logger or ns.get("LOGGER")

    # System Admin navigation: force the requested three destinations regardless
    # of any earlier operational-admin wrapper state.
    previous_pill = ns["pill_nav"]
    def pill_nav(state_key, options, default=None, prefix="subnav"):
        if state_key == "admin_view" and st.session_state.get("main_page") == "admin":
            desired = [("users", "👥 Người dùng"), ("customers", "🏢 Khách hàng CIF"), ("types", "🧩 Loại công việc")]
            current = st.session_state.get("admin_view")
            if current not in {"users", "customers", "types"}:
                current = st.session_state.get("system_admin_view_v2", "users")
            if current not in {"users", "customers", "types"}:
                current = "users"
            st.session_state["admin_view"] = current
            st.session_state["system_admin_view_v2"] = current
            return _local_command_tabs(st, "admin_view", desired, default=current, prefix="system_admin_final")
        return previous_pill(state_key, options, default=default, prefix=prefix)
    ns["pill_nav"] = pill_nav

    previous_admin = ns["admin_page"]
    def admin_page(u):
        if st.session_state.get("main_page") == "admin":
            st.session_state["admin_scope"] = "system"
            if st.session_state.get("admin_view") == "types" or st.session_state.get("system_admin_view_v2") == "types":
                st.session_state["admin_view"] = "types"
                st.session_state["system_admin_view_v2"] = "types"
                return _render_system_task_types(ns, u, worktype, app_logger)
        return previous_admin(u)
    ns["admin_page"] = admin_page

    previous_approval = customer_ui.render_approvals_page
    def render_approvals_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        # v2's renderer uses a positional third parameter named get_conn_arg;
        # pass it positionally so the dashboard dispatcher can keep get_conn=.
        return previous_approval(st_arg, u, conn_fn, page_title=page_title, logger=logger or app_logger)
    customer_ui.render_approvals_page = render_approvals_page

    ns["_PLANNING_UI_ADMIN_HOTFIX_POST"] = True
    if app_logger:
        app_logger.info("PLANNING_UI_ADMIN_HOTFIX_POST version=%s", VERSION)
