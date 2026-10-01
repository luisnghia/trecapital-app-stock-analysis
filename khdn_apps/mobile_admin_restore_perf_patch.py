"""Final System Admin restore + mobile render-load reduction.

Installed after mobile_input_performance_patch so it owns the final System Admin
renderers without undoing the zero-keystroke forms.  It restores all six original
Admin destinations and renders only one edit/create client form at a time on the
heaviest admin pages, reducing iOS DOM/iframe work while the keyboard is open.
"""
from __future__ import annotations

import sqlite3

from khdn_apps import mobile_input_performance_patch as mobile
from khdn_apps import planning_operational_phase7_patch as phase7

VERSION = "1.0.0"
_FLAG = "_MOBILE_ADMIN_RESTORE_PERF_VERSION"


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _scope_label(v):
    return "Kế hoạch" if str(v or "OPS") == "PLAN" else "Tác nghiệp"


def _admin_title(ns):
    page_title = ns.get("page_title")
    if page_title:
        page_title(
            "Quản trị hệ thống",
            "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân tác nghiệp, audit và sao lưu dữ liệu.",
        )
    else:
        ns["st"].title("Quản trị hệ thống")


def _render_six_admin_nav(ns, current):
    st = ns["st"]
    allowed = {value for value, _ in phase7._ADMIN_OPTIONS}
    if current in allowed:
        st.session_state["admin_view"] = current
        for key in ("system_admin_view_v2", "system_admin_view_v3", "system_admin_view_v4"):
            st.session_state[key] = current
    return phase7._admin_cards(st, current if current in allowed else "users")


def _mode_buttons(st, state_key, create_label, manage_label):
    mode = str(st.session_state.get(state_key) or "create")
    if mode not in {"create", "manage"}:
        mode = "create"
        st.session_state[state_key] = mode
    c1, c2 = st.columns(2, gap="small")
    if c1.button(
        create_label,
        key=f"{state_key}_create",
        type="primary" if mode == "create" else "secondary",
        use_container_width=True,
    ):
        st.session_state[state_key] = "create"
        st.rerun()
    if c2.button(
        manage_label,
        key=f"{state_key}_manage",
        type="primary" if mode == "manage" else "secondary",
        use_container_width=True,
    ):
        st.session_state[state_key] = "manage"
        st.rerun()
    return mode


def _render_system_users_fast(ns, u, logger=None):
    st, get_conn = ns["st"], ns["get_conn"]
    _admin_title(ns)
    _render_six_admin_nav(ns, "users")
    roles = list(ns.get("ROLES") or ["Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng"])
    mode = _mode_buttons(st, "system_users_perf_mode_v3", "➕ Tạo người dùng", "🛠 Quản lý người dùng")

    if mode == "create":
        st.subheader("Tạo người dùng")
        payload = mobile.fast_client_form(
            [
                {"name":"username","label":"Username","type":"text","required":True,"placeholder":"Tên đăng nhập"},
                {"name":"full_name","label":"Họ tên","type":"text","required":True,"placeholder":"Họ và tên"},
                {"name":"role","label":"Nhóm quyền","type":"select","options":[{"value":x,"label":x} for x in roles],"default":roles[0]},
                {"name":"password","label":"Mật khẩu khởi tạo","type":"password","required":True,"default":"Bidv@123"},
                {"name":"is_admin","label":"Quyền Admin","type":"checkbox","default":False},
            ],
            "Tạo user",
            key="system_user_create_fast_v3",
            reset_token=str(st.session_state.get("_system_user_create_epoch_v3", 0)),
            help_text="Biểu mẫu được xử lý cục bộ trên điện thoại; dữ liệu chỉ gửi lên máy chủ khi bấm Tạo user.",
        )
        if payload is None:
            return
        username = str(payload.get("username") or "").strip()
        full_name = str(payload.get("full_name") or "").strip()
        role = str(payload.get("role") or roles[0])
        password = str(payload.get("password") or "")
        is_admin = bool(payload.get("is_admin"))
        if not username or not full_name or not ns["password_ok"](password):
            st.error("Nhập đủ thông tin. Mật khẩu tối thiểu 8 ký tự, gồm chữ và số.")
            return
        try:
            ts = ns["now_str"]()
            uid = ns["execute"](
                "INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at) VALUES(?,?,?,?,?,1,1,?,?)",
                (username, full_name, ns["hash_password"](password), role, int(is_admin), ts, ts),
            )
            ns["audit"](int(_uget(u,"id")), "CREATE_USER", "user", uid, f"{username} - {full_name} - {role}")
            st.session_state["_system_user_create_epoch_v3"] = int(st.session_state.get("_system_user_create_epoch_v3",0))+1
            st.toast("Đã tạo user. Người dùng sẽ phải đổi mật khẩu khi đăng nhập lần đầu.", icon="✅")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Username đã tồn tại.")
        return

    st.subheader("Quản lý người dùng hiện có")
    with get_conn() as c:
        users = [dict(r) for r in c.execute(
            "SELECT id,username,full_name,role,is_admin,active,last_login_at,created_at FROM users ORDER BY id"
        ).fetchall()]
    if not users:
        st.info("Chưa có người dùng.")
        return
    by_id = {int(r["id"]): r for r in users}
    selected = st.selectbox(
        "Chọn user để cập nhật",
        list(by_id),
        format_func=lambda x: f"{by_id[int(x)]['full_name']} ({by_id[int(x)]['username']})",
        key="admin_selected_user_fast_v3",
    )
    cur = by_id[int(selected)]
    edit = mobile.fast_client_form(
        [
            {"name":"username","label":"Username","type":"text","required":True,"default":str(cur.get("username") or "")},
            {"name":"role","label":"Nhóm quyền","type":"select","options":[{"value":x,"label":x} for x in roles],"default":str(cur.get("role") or roles[0])},
            {"name":"active","label":"Đang hoạt động","type":"checkbox","default":bool(cur.get("active"))},
            {"name":"is_admin","label":"Quyền Admin","type":"checkbox","default":bool(cur.get("is_admin"))},
            {"name":"password","label":"Reset mật khẩu (để trống nếu không đổi)","type":"password","default":"","full":True},
        ],
        "Lưu thay đổi user",
        key=f"system_user_edit_fast_v3_{int(selected)}",
        reset_token=f"{int(selected)}|{cur.get('username')}|{cur.get('role')}|{cur.get('active')}|{cur.get('is_admin')}",
    )
    if edit is not None:
        new_username = str(edit.get("username") or "").strip()
        nr = str(edit.get("role") or cur.get("role") or roles[0])
        active = bool(edit.get("active"))
        adminflag = bool(edit.get("is_admin"))
        np = str(edit.get("password") or "")
        if int(selected) == int(_uget(u,"id")) and not active:
            st.error("Không thể tự khóa tài khoản đang đăng nhập.")
        elif np and not ns["password_ok"](np):
            st.error("Mật khẩu reset tối thiểu 8 ký tự, gồm chữ và số.")
        else:
            try:
                effective = str(cur.get("username") or "")
                if new_username != effective:
                    effective = ns["rename_username"](u, int(selected), new_username)
                ns["execute"](
                    "UPDATE users SET role=?,active=?,is_admin=?,updated_at=? WHERE id=?",
                    (nr, int(active), int(adminflag), ns["now_str"](), int(selected)),
                )
                if np:
                    ns["execute"](
                        "UPDATE users SET password_hash=?,must_change_password=1,updated_at=? WHERE id=?",
                        (ns["hash_password"](np), ns["now_str"](), int(selected)),
                    )
                ns["audit"](
                    int(_uget(u,"id")), "UPDATE_USER", "user", int(selected),
                    f"username={effective}; role={nr}; active={active}; admin={adminflag}; reset_pw={bool(np)}",
                )
                if int(selected) == int(_uget(u,"id")):
                    fresh = ns["user_by_username"](effective, active_only=False)
                    if fresh:
                        st.session_state.user = dict(fresh)
                st.toast("Đã cập nhật user.", icon="✅")
                st.rerun()
            except (ValueError, sqlite3.IntegrityError) as exc:
                st.error(str(exc) or "Không thể cập nhật username.")
    if int(selected) != int(_uget(u,"id")) and st.button(
        "Xóa user", key=f"delete_user_fast_v3_{int(selected)}", type="secondary"
    ):
        try:
            deleted = ns["delete_user_account"](u, int(selected))
            st.toast(f"Đã xóa user {deleted} khỏi hệ thống đăng nhập.", icon="✅")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
    mobile._static_table(
        st,
        ["ID","Username","Họ tên","Nhóm quyền","Admin","Trạng thái","Đăng nhập gần nhất"],
        [[r["id"],r["username"],r["full_name"],r["role"],"Có" if r.get("is_admin") else "Không","Đang hoạt động" if r.get("active") else "Đã khóa",r.get("last_login_at") or "—"] for r in users],
        "khdn-fast-user-table-v3",
    )


def _render_system_task_types_fast(ns, u, worktype, logger=None):
    st, get_conn = ns["st"], ns["get_conn"]
    log = logger or ns.get("LOGGER")
    _admin_title(ns)
    _render_six_admin_nav(ns, "types")
    worktype.ensure_worktype_scope(get_conn, log)
    st.subheader("Loại công việc")
    st.caption("Tên Loại công việc được phép trùng giữa **Tác nghiệp** và **Kế hoạch**; trong cùng một phân hệ thì tên vẫn phải duy nhất.")
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,name,module_scope,active,created_at,updated_at FROM task_types ORDER BY id"
        ).fetchall()]
    mode = _mode_buttons(st, "system_task_types_perf_mode_v3", "➕ Thêm loại công việc", "🛠 Quản lý loại công việc")

    if mode == "create":
        latest = max((str(r.get("updated_at") or "") for r in rows), default="")
        payload = mobile.fast_client_form(
            [
                {"name":"name","label":"Tên công việc mới","type":"text","required":True,"placeholder":"Nhập tên loại công việc"},
                {"name":"module_scope","label":"Thuộc phân hệ","type":"select","options":[{"value":"OPS","label":"Tác nghiệp"},{"value":"PLAN","label":"Kế hoạch"}],"default":"OPS"},
            ],
            "Thêm loại công việc",
            key="system_task_type_create_fast_v6",
            reset_token=f"{len(rows)}|{latest}",
        )
        if payload is None:
            return
        clean = str(payload.get("name") or "").strip()
        scope = str(payload.get("module_scope") or "OPS")
        if not clean:
            st.error("Bắt buộc nhập tên Loại công việc.")
            return
        try:
            ts = ns["now_str"]()
            with get_conn() as c:
                exists = c.execute(
                    "SELECT id FROM task_types WHERE module_scope=? AND lower(trim(name))=lower(trim(?))",
                    (scope, clean),
                ).fetchone()
                if exists:
                    raise ValueError(f"Tên Loại công việc đã tồn tại trong phân hệ {_scope_label(scope)}.")
                cur = c.execute(
                    "INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) VALUES(?,8,1,?,?,?)",
                    (clean, scope, ts, ts),
                )
                new_id = int(cur.lastrowid)
            if ns.get("audit"):
                ns["audit"](int(_uget(u,"id")), "CREATE_TASK_TYPE", "task_type", new_id, f"name={clean}; module_scope={scope}")
            st.toast("Đã thêm Loại công việc.", icon="✅")
            st.rerun()
        except (sqlite3.IntegrityError, ValueError) as exc:
            st.error(str(exc))
        return

    if not rows:
        st.info("Chưa có Loại công việc.")
        return
    by_id = {int(r["id"]): r for r in rows}
    selected = st.selectbox(
        "Chọn loại công việc để sửa",
        list(by_id),
        format_func=lambda x: f"{by_id[int(x)]['name']} · {_scope_label(by_id[int(x)].get('module_scope'))}",
        key="system_task_type_edit_pick_fast_v6",
    )
    cur = by_id[int(selected)]
    edit = mobile.fast_client_form(
        [
            {"name":"name","label":"Tên công việc","type":"text","required":True,"default":str(cur.get("name") or "")},
            {"name":"module_scope","label":"Thuộc phân hệ","type":"select","options":[{"value":"OPS","label":"Tác nghiệp"},{"value":"PLAN","label":"Kế hoạch"}],"default":str(cur.get("module_scope") or "OPS")},
            {"name":"active","label":"Đang sử dụng","type":"checkbox","default":bool(cur.get("active"))},
        ],
        "Lưu thay đổi",
        key=f"system_task_type_edit_fast_v6_{int(selected)}",
        reset_token=f"{int(selected)}|{cur.get('updated_at') or ''}",
    )
    if edit is not None:
        clean = str(edit.get("name") or "").strip()
        scope = str(edit.get("module_scope") or "OPS")
        active = bool(edit.get("active"))
        if not clean:
            st.error("Tên Loại công việc không được để trống.")
        else:
            try:
                with get_conn() as c:
                    clash = c.execute(
                        "SELECT id FROM task_types WHERE module_scope=? AND lower(trim(name))=lower(trim(?)) AND id<>?",
                        (scope, clean, int(selected)),
                    ).fetchone()
                    if clash:
                        raise ValueError(f"Tên Loại công việc đã tồn tại trong phân hệ {_scope_label(scope)}.")
                    c.execute(
                        "UPDATE task_types SET name=?,module_scope=?,active=?,updated_at=? WHERE id=?",
                        (clean, scope, int(active), ns["now_str"](), int(selected)),
                    )
                if ns.get("audit"):
                    ns["audit"](int(_uget(u,"id")), "UPDATE_TASK_TYPE", "task_type", int(selected), f"name={clean}; module_scope={scope}; active={active}")
                st.toast("Đã cập nhật Loại công việc.", icon="✅")
                st.rerun()
            except (sqlite3.IntegrityError, ValueError) as exc:
                st.error(str(exc))
    mobile._static_table(
        st,
        ["ID","Tên công việc","Phân hệ","Trạng thái","Ngày tạo","Cập nhật"],
        [[r["id"],r["name"],_scope_label(r.get("module_scope")),"Đang sử dụng" if r.get("active") else "Ngưng",r.get("created_at") or "",r.get("updated_at") or ""] for r in rows],
        "khdn-fast-task-type-table-v3",
    )


def install(app_ns, policy, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return
    mobile._render_system_admin_nav = _render_six_admin_nav
    mobile._render_system_users_fast = _render_system_users_fast
    mobile._render_system_task_types_fast = _render_system_task_types_fast
    app_ns[_FLAG] = VERSION
    log = logger or app_ns.get("LOGGER")
    if log:
        log.info("MOBILE_ADMIN_RESTORE_PERF_INSTALLED version=%s admin_routes=6 lazy_users=1 lazy_task_types=1", VERSION)
