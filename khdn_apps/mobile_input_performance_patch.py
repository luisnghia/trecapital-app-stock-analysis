"""Final mobile-input performance guard for KHDN Apps.

V2 is intentionally installed after every planning/operations overlay. It removes
all periodic server refresh work from the typing path and moves the catalog/admin
forms that were reported slow on iPhone into an isolated browser-local component.
Draft values never cross the Streamlit bridge until the user presses Save.

It also migrates ``task_types`` from legacy UNIQUE(name) to a normalized unique
key per module scope, allowing the same visible name once in OPS and once in PLAN.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import html
import os
import re
import sqlite3

from khdn_apps.fast_client_form import fast_client_form
from khdn_apps import planning_ui_admin_hotfix as admin_hotfix

VERSION = "2.0.0"
_FLAG = "_MOBILE_INPUT_PERFORMANCE_VERSION"


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


def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return int(default)


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)


def _static_table(st, headers, rows, css_class="khdn-fast-admin-table"):
    """Read-only HTML table: no React dataframe grid on input-heavy pages."""
    body = []
    for row in rows or []:
        body.append(
            "<tr>" + "".join(f"<td>{html.escape(str(v if v is not None else ''))}</td>" for v in row) + "</tr>"
        )
    table = f"""
    <style>
      .{css_class}{{width:100%;overflow:auto;border:1px solid rgba(127,127,127,.55);border-radius:10px;margin:.35rem 0 .85rem}}
      .{css_class} table{{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.88rem}}
      .{css_class} th,.{css_class} td{{border:1px solid rgba(127,127,127,.45);padding:8px 9px;text-align:left;vertical-align:top;white-space:normal;overflow-wrap:anywhere}}
      .{css_class} th{{font-weight:850;background:rgba(15,118,110,.10)}}
      @media(max-width:760px){{.{css_class} table{{font-size:.78rem}}.{css_class} th,.{css_class} td{{padding:7px 6px}}}}
    </style>
    <div class="{css_class}"><table><thead><tr>{''.join(f'<th>{html.escape(str(x))}</th>' for x in headers)}</tr></thead><tbody>{''.join(body)}</tbody></table></div>
    """
    if hasattr(st, "html"):
        st.html(table)
    else:
        st.markdown(table, unsafe_allow_html=True)


def _task_type_unique_name_only(c):
    """True when legacy SQLite schema still enforces UNIQUE(name)."""
    for idx in c.execute("PRAGMA index_list(task_types)").fetchall():
        # seq, name, unique, origin, partial
        if not int(idx[2] or 0):
            continue
        name = str(idx[1])
        cols = [str(r[2]) for r in c.execute(f'PRAGMA index_info("{name}")').fetchall() if r[2] is not None]
        if cols == ["name"]:
            return True
    return False


def _backup_before_task_type_migration(app_ns, logger=None):
    source = Path(str(app_ns.get("DB_PATH") or os.getenv("KHDN_DB_PATH") or "")).expanduser()
    if not source.exists() or not source.is_file():
        return None
    data_dir = Path(str(os.getenv("KHDN_DATA_DIR") or source.parent)).expanduser()
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / "pre_task_type_scope_unique_v2.db"
    if dest.exists():
        return dest
    src = sqlite3.connect(str(source), timeout=30)
    dst = sqlite3.connect(str(dest), timeout=30)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    if logger:
        logger.info("MOBILE_INPUT_TASK_TYPE_PREMIGRATION_BACKUP file=%s", dest.name)
    return dest


def _migrate_task_type_scope_uniqueness(app_ns, logger=None):
    """Allow same task-type name in different modules, never within one module."""
    get_conn = app_ns["get_conn"]
    with get_conn() as c:
        cols = {str(r[1]) for r in c.execute("PRAGMA table_info(task_types)").fetchall()}
        if "module_scope" not in cols:
            c.execute("ALTER TABLE task_types ADD COLUMN module_scope TEXT NOT NULL DEFAULT 'OPS'")
        c.execute("UPDATE task_types SET module_scope='OPS' WHERE module_scope IS NULL OR trim(module_scope)='' OR module_scope NOT IN ('OPS','PLAN')")
        legacy = _task_type_unique_name_only(c)

    if legacy:
        _backup_before_task_type_migration(app_ns, logger)
        c = get_conn()
        try:
            c.execute("PRAGMA foreign_keys=OFF")
            c.execute("BEGIN IMMEDIATE")
            info = c.execute("PRAGMA table_info(task_types)").fetchall()
            if not info:
                raise RuntimeError("task_types schema missing")
            names = [str(r[1]) for r in info]
            defs = []
            for r in info:
                name, typ, notnull, default, pk = str(r[1]), str(r[2] or "TEXT"), int(r[3] or 0), r[4], int(r[5] or 0)
                qn = '"' + name.replace('"', '""') + '"'
                if name == "id" and pk:
                    ddl = f"{qn} INTEGER PRIMARY KEY AUTOINCREMENT"
                else:
                    ddl = f"{qn} {typ}"
                    if notnull:
                        ddl += " NOT NULL"
                    if default is not None:
                        ddl += f" DEFAULT {default}"
                    if pk:
                        ddl += " PRIMARY KEY"
                defs.append(ddl)
            c.execute("DROP TABLE IF EXISTS task_types_scope_v2")
            c.execute("CREATE TABLE task_types_scope_v2(" + ",".join(defs) + ")")
            quoted = ",".join('"' + n.replace('"', '""') + '"' for n in names)
            c.execute(f"INSERT INTO task_types_scope_v2({quoted}) SELECT {quoted} FROM task_types")
            c.execute("DROP TABLE task_types")
            c.execute("ALTER TABLE task_types_scope_v2 RENAME TO task_types")
            c.execute("COMMIT")
        except Exception:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
            raise
        finally:
            try:
                c.execute("PRAGMA foreign_keys=ON")
            except Exception:
                pass
            c.close()

    with get_conn() as c:
        # If a hand-created legacy index exists and is droppable, remove it only
        # after the table rebuild/no-legacy check. Autoindexes are gone with rebuild.
        for idx in c.execute("PRAGMA index_list(task_types)").fetchall():
            name, unique, origin = str(idx[1]), int(idx[2] or 0), str(idx[3] or "")
            if not unique or origin != "c":
                continue
            cols = [str(r[2]) for r in c.execute(f'PRAGMA index_info("{name}")').fetchall() if r[2] is not None]
            if cols == ["name"]:
                c.execute(f'DROP INDEX IF EXISTS "{name.replace(chr(34), chr(34)*2)}"')
        c.execute("CREATE INDEX IF NOT EXISTS idx_task_types_scope_active ON task_types(module_scope,active,id)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_task_types_scope_name_norm ON task_types(module_scope, lower(trim(name)))")
    if logger:
        logger.info("MOBILE_INPUT_TASK_TYPE_SCOPE_UNIQUENESS_READY cross_scope_duplicate=1 same_scope_duplicate=0 migrated=%s", int(bool(legacy)))


def _render_system_admin_nav(ns, current):
    st = ns["st"]
    admin_hotfix._command_tabs_css(st)
    options = [("users", "👥 Người dùng"), ("customers", "🏢 Khách hàng CIF"), ("types", "🧩 Loại công việc")]
    widths = [max(1.0, min(2.7, len(label) / 11.0)) for _, label in options]
    with st.container(key=f"khdn_subnav_bar_system_admin_fast_{current}"):
        cols = st.columns(widths, gap="small")
        for idx, (col, (value, label)) in enumerate(zip(cols, options)):
            with col:
                if st.button(label, key=f"system_admin_fast_{current}_{idx}_{value}", use_container_width=True, type="primary" if value == current else "secondary"):
                    st.session_state["admin_scope"] = "system"
                    st.session_state["admin_view"] = value
                    st.session_state["system_admin_view_v2"] = value
                    st.session_state["system_admin_view_v3"] = value
                    st.rerun()


def _render_system_users_fast(ns, u, logger=None):
    st, get_conn = ns["st"], ns["get_conn"]
    page_title = ns.get("page_title")
    if page_title:
        page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF và loại công việc.")
    else:
        st.title("Quản trị hệ thống")
    _render_system_admin_nav(ns, "users")
    st.subheader("Tạo người dùng")
    roles = list(ns.get("ROLES") or ["Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng"])
    payload = fast_client_form(
        [
            {"name":"username","label":"Username","type":"text","required":True,"placeholder":"Tên đăng nhập"},
            {"name":"full_name","label":"Họ tên","type":"text","required":True,"placeholder":"Họ và tên"},
            {"name":"role","label":"Nhóm quyền","type":"select","options":[{"value":x,"label":x} for x in roles],"default":roles[0]},
            {"name":"password","label":"Mật khẩu khởi tạo","type":"password","required":True,"default":"Bidv@123"},
            {"name":"is_admin","label":"Quyền Admin","type":"checkbox","default":False},
        ],
        "Tạo user",
        key="system_user_create_fast_v2",
        reset_token=str(st.session_state.get("_system_user_create_epoch", 0)),
        help_text="Dữ liệu chỉ gửi lên máy chủ khi bấm Tạo user; gõ trên điện thoại không làm Streamlit rerun.",
    )
    if payload is not None:
        username = str(payload.get("username") or "").strip()
        full_name = str(payload.get("full_name") or "").strip()
        role = str(payload.get("role") or roles[0])
        password = str(payload.get("password") or "")
        is_admin = bool(payload.get("is_admin"))
        if not username or not full_name or not ns["password_ok"](password):
            st.error("Nhập đủ thông tin. Mật khẩu tối thiểu 8 ký tự, gồm chữ và số.")
        else:
            try:
                ts = ns["now_str"]()
                uid = ns["execute"](
                    "INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at) VALUES(?,?,?,?,?,1,1,?,?)",
                    (username, full_name, ns["hash_password"](password), role, int(is_admin), ts, ts),
                )
                ns["audit"](int(_uget(u,"id")), "CREATE_USER", "user", uid, f"{username} - {full_name} - {role}")
                st.session_state["_system_user_create_epoch"] = int(st.session_state.get("_system_user_create_epoch",0))+1
                st.toast("Đã tạo user. Người dùng sẽ phải đổi mật khẩu khi đăng nhập lần đầu.", icon="✅")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Username đã tồn tại.")

    with get_conn() as c:
        users = [dict(r) for r in c.execute(
            "SELECT id,username,full_name,role,is_admin,active,last_login_at,created_at FROM users ORDER BY id"
        ).fetchall()]
    st.markdown("#### Danh sách người dùng")
    _static_table(st,["ID","Username","Họ tên","Nhóm quyền","Admin","Trạng thái","Đăng nhập gần nhất"],[
        [r["id"],r["username"],r["full_name"],r["role"],"Có" if r.get("is_admin") else "Không","Đang hoạt động" if r.get("active") else "Đã khóa",r.get("last_login_at") or "—"] for r in users
    ],"khdn-fast-user-table")
    if not users:
        return
    by_id={int(r["id"]):r for r in users}
    selected=st.selectbox("Chọn user để cập nhật",list(by_id),format_func=lambda x:f"{by_id[int(x)]['full_name']} ({by_id[int(x)]['username']})",key="admin_selected_user_fast_v2")
    cur=by_id[int(selected)]
    edit = fast_client_form(
        [
            {"name":"username","label":"Username","type":"text","required":True,"default":str(cur.get("username") or "")},
            {"name":"role","label":"Nhóm quyền","type":"select","options":[{"value":x,"label":x} for x in roles],"default":str(cur.get("role") or roles[0])},
            {"name":"active","label":"Đang hoạt động","type":"checkbox","default":bool(cur.get("active"))},
            {"name":"is_admin","label":"Quyền Admin","type":"checkbox","default":bool(cur.get("is_admin"))},
            {"name":"password","label":"Reset mật khẩu (để trống nếu không đổi)","type":"password","default":"","full":True},
        ],
        "Lưu thay đổi user",
        key=f"system_user_edit_fast_v2_{int(selected)}",
        reset_token=f"{int(selected)}|{cur.get('username')}|{cur.get('role')}|{cur.get('active')}|{cur.get('is_admin')}",
    )
    if edit is not None:
        new_username=str(edit.get("username") or "").strip(); nr=str(edit.get("role") or cur.get("role") or roles[0]); active=bool(edit.get("active")); adminflag=bool(edit.get("is_admin")); np=str(edit.get("password") or "")
        if int(selected)==int(_uget(u,"id")) and not active:
            st.error("Không thể tự khóa tài khoản đang đăng nhập.")
        elif np and not ns["password_ok"](np):
            st.error("Mật khẩu reset tối thiểu 8 ký tự, gồm chữ và số.")
        else:
            try:
                effective=str(cur.get("username") or "")
                if new_username != effective:
                    effective=ns["rename_username"](u,int(selected),new_username)
                ns["execute"]("UPDATE users SET role=?,active=?,is_admin=?,updated_at=? WHERE id=?",(nr,int(active),int(adminflag),ns["now_str"](),int(selected)))
                if np:
                    ns["execute"]("UPDATE users SET password_hash=?,must_change_password=1,updated_at=? WHERE id=?",(ns["hash_password"](np),ns["now_str"](),int(selected)))
                ns["audit"](int(_uget(u,"id")),"UPDATE_USER","user",int(selected),f"username={effective}; role={nr}; active={active}; admin={adminflag}; reset_pw={bool(np)}")
                if int(selected)==int(_uget(u,"id")):
                    fresh=ns["user_by_username"](effective,active_only=False)
                    if fresh: st.session_state.user=dict(fresh)
                st.toast("Đã cập nhật user.",icon="✅"); st.rerun()
            except (ValueError,sqlite3.IntegrityError) as exc:
                st.error(str(exc) or "Không thể cập nhật username.")
    if int(selected)!=int(_uget(u,"id")) and st.button("Xóa user",key=f"delete_user_fast_v2_{int(selected)}"):
        try:
            deleted=ns["delete_user_account"](u,int(selected)); st.toast(f"Đã xóa user {deleted} khỏi hệ thống đăng nhập.",icon="✅"); st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def _render_system_task_types_fast(ns, u, worktype, logger=None):
    st, get_conn = ns["st"], ns["get_conn"]
    page_title=ns.get("page_title"); log=logger or ns.get("LOGGER")
    if page_title: page_title("Quản trị hệ thống","Quản lý người dùng, khách hàng CIF và loại công việc.")
    else: st.title("Quản trị hệ thống")
    _render_system_admin_nav(ns,"types")
    worktype.ensure_worktype_scope(get_conn,log)
    st.subheader("Loại công việc")
    st.caption("Tên Loại công việc được phép trùng giữa **Tác nghiệp** và **Kế hoạch**; trong cùng một phân hệ thì tên vẫn phải duy nhất.")
    with get_conn() as c:
        rows=[dict(r) for r in c.execute("SELECT id,name,module_scope,active,created_at,updated_at FROM task_types ORDER BY id").fetchall()]
    _static_table(st,["ID","Tên công việc","Phân hệ","Trạng thái","Ngày tạo","Cập nhật"],[
        [r["id"],r["name"],_scope_label(r.get("module_scope")),"Đang sử dụng" if r.get("active") else "Ngưng",r.get("created_at") or "",r.get("updated_at") or ""] for r in rows
    ])
    latest=max((str(r.get("updated_at") or "") for r in rows),default="")
    create=fast_client_form(
        [
            {"name":"name","label":"Tên công việc mới","type":"text","required":True,"placeholder":"Nhập tên loại công việc"},
            {"name":"module_scope","label":"Thuộc phân hệ","type":"select","options":[{"value":"OPS","label":"Tác nghiệp"},{"value":"PLAN","label":"Kế hoạch"}],"default":"OPS"},
        ],
        "Thêm loại công việc",key="system_task_type_create_fast_v5",reset_token=f"{len(rows)}|{latest}",
    )
    if create is not None:
        clean=str(create.get("name") or "").strip(); scope=str(create.get("module_scope") or "OPS")
        if not clean: st.error("Bắt buộc nhập tên Loại công việc.")
        else:
            try:
                ts=ns["now_str"]()
                with get_conn() as c:
                    exists=c.execute("SELECT id FROM task_types WHERE module_scope=? AND lower(trim(name))=lower(trim(?))",(scope,clean)).fetchone()
                    if exists: raise ValueError(f"Tên Loại công việc đã tồn tại trong phân hệ {_scope_label(scope)}.")
                    cur=c.execute("INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) VALUES(?,8,1,?,?,?)",(clean,scope,ts,ts)); new_id=int(cur.lastrowid)
                if ns.get("audit"): ns["audit"](int(_uget(u,"id")),"CREATE_TASK_TYPE","task_type",new_id,f"name={clean}; module_scope={scope}")
                st.toast("Đã thêm Loại công việc.",icon="✅"); st.rerun()
            except (sqlite3.IntegrityError,ValueError) as exc: st.error(str(exc))
    if rows:
        st.markdown("#### Sửa loại công việc")
        by_id={int(r["id"]):r for r in rows}; selected=st.selectbox("Chọn loại công việc để sửa",list(by_id),format_func=lambda x:f"{by_id[int(x)]['name']} · {_scope_label(by_id[int(x)].get('module_scope'))}",key="system_task_type_edit_pick_fast_v5"); cur=by_id[int(selected)]
        edit=fast_client_form(
            [
                {"name":"name","label":"Tên công việc","type":"text","required":True,"default":str(cur.get("name") or "")},
                {"name":"module_scope","label":"Thuộc phân hệ","type":"select","options":[{"value":"OPS","label":"Tác nghiệp"},{"value":"PLAN","label":"Kế hoạch"}],"default":str(cur.get("module_scope") or "OPS")},
                {"name":"active","label":"Đang sử dụng","type":"checkbox","default":bool(cur.get("active"))},
            ],
            "Lưu thay đổi",key=f"system_task_type_edit_fast_v5_{int(selected)}",reset_token=f"{int(selected)}|{cur.get('updated_at') or ''}",
        )
        if edit is not None:
            clean=str(edit.get("name") or "").strip(); scope=str(edit.get("module_scope") or "OPS"); active=bool(edit.get("active"))
            if not clean: st.error("Tên Loại công việc không được để trống.")
            else:
                try:
                    with get_conn() as c:
                        clash=c.execute("SELECT id FROM task_types WHERE module_scope=? AND lower(trim(name))=lower(trim(?)) AND id<>?",(scope,clean,int(selected))).fetchone()
                        if clash: raise ValueError(f"Tên Loại công việc đã tồn tại trong phân hệ {_scope_label(scope)}.")
                        c.execute("UPDATE task_types SET name=?,module_scope=?,active=?,updated_at=? WHERE id=?",(clean,scope,int(active),ns["now_str"](),int(selected)))
                    if ns.get("audit"): ns["audit"](int(_uget(u,"id")),"UPDATE_TASK_TYPE","task_type",int(selected),f"name={clean}; module_scope={scope}; active={active}")
                    st.toast("Đã cập nhật Loại công việc.",icon="✅"); st.rerun()
                except (sqlite3.IntegrityError,ValueError) as exc: st.error(str(exc))


def _install_admin_fast_forms(app_ns, worktype, logger=None):
    original=app_ns.get("admin_page")
    if not callable(original): return
    st=app_ns["st"]
    def admin_page(u):
        if st.session_state.get("main_page")=="admin":
            view=str(st.session_state.get("admin_view") or st.session_state.get("system_admin_view_v2") or "users")
            if view=="users": return _render_system_users_fast(app_ns,u,logger)
            if view=="types": return _render_system_task_types_fast(app_ns,u,worktype,logger)
        return original(u)
    app_ns["admin_page"]=admin_page
    # planning_ui_admin_hotfix owns the direct System Admin type route as well.
    admin_hotfix._render_system_task_types=lambda ns,u,worktype_arg,logger=None:_render_system_task_types_fast(ns,u,worktype_arg,logger)
    if logger: logger.info("MOBILE_INPUT_ADMIN_FAST_FORMS_INSTALLED users=1 task_types=1")


def _render_catalog_fast(policy, st, u, core, customer_core, customer_ui, get_conn, page_title=None, logger=None):
    policy._ensure_schema(core,get_conn,logger); customer_core.ensure_schema(get_conn,logger)
    if not policy._manager(u): st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục."); return
    uid=int(policy._uget(u,"id"))
    if page_title: page_title("Danh mục quy trình","Mục công việc/SLA và danh mục công việc trọng tâm Q2")
    else: st.title("⚙️ Danh mục quy trình")
    view=policy._cmd_nav(st,"policy_catalog_view",[("stage","Mục công việc / SLA"),("focus","Danh mục công việc trọng tâm Q2")],"stage")
    if view=="stage":
        with get_conn() as c: stages=customer_core.active_stages(c,include_inactive=True)
        customer_ui._html_table(st,["Thứ tự","Mục công việc","SLA (giờ)","Bước kết thúc quy trình","Trạng thái"],[[s["sort_order"],s["name"],f"{float(s['sla_hours']):.1f}","Có" if s["is_completion"] else "Không","Đang dùng" if s["active"] else "Ngưng"] for s in stages])
        opts=[None]+stages; edit=st.selectbox("Chọn mục công việc để sửa",opts,format_func=lambda x:"＋ Tạo mới" if x is None else x["name"],key="cw_stage_edit_fast_v2")
        default_order=int(edit.get("sort_order") or 1) if edit else len(stages)+1
        payload=fast_client_form(
            [
                {"name":"name","label":"Tên mục công việc","type":"text","required":True,"default":str(edit.get("name") or "") if edit else ""},
                {"name":"order","label":"Thứ tự","type":"number","min":1,"step":1,"default":default_order},
                {"name":"sla","label":"SLA cảnh báo (giờ)","type":"number","min":0,"step":1,"default":_safe_float(edit.get("sla_hours"),0) if edit else 0},
                {"name":"done","label":"Bước kết thúc quy trình","type":"checkbox","default":bool(edit.get("is_completion")) if edit else False},
                {"name":"active","label":"Đang sử dụng","type":"checkbox","default":bool(edit.get("active")) if edit else True},
            ],"Lưu danh mục",key=f"cw_stage_fast_v2_{int(edit['id']) if edit else 'new'}",reset_token=f"{int(edit['id']) if edit else 'new'}|{default_order}|{edit.get('name') if edit else ''}",
        )
        if payload is not None:
            name=str(payload.get("name") or "").strip()
            if not name: st.error("Tên mục công việc không được để trống.")
            else:
                customer_core.save_stage_catalog(get_conn,uid,int(edit["id"]) if edit else None,name,max(1,_safe_int(payload.get("order"),default_order)),max(0.0,_safe_float(payload.get("sla"),0)),bool(payload.get("done")),bool(payload.get("active")),logger); st.toast("Đã lưu danh mục.",icon="✅"); st.rerun()
        if edit and st.button("Xóa/Ngưng sử dụng mục này",key="policy_stage_delete_fast_v2"):
            customer_core.delete_stage_catalog(get_conn,uid,int(edit["id"]),logger); st.rerun()
        return

    years=list(range(2025,2101)); current_year=date.today().year; year=int(st.selectbox("Năm áp dụng",years,index=years.index(current_year) if current_year in years else 0,key="focus_year_fast_v2"))
    with get_conn() as c: leaders=[dict(r) for r in c.execute("SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name").fetchall()]
    leader_id=uid
    if policy._is_admin(u) and leaders:
        leader_id=int(st.selectbox("Phòng/Trưởng phòng",leaders,format_func=lambda x:x["full_name"],key="focus_leader_fast_v2")["id"])
    scope=f"LEADER:{leader_id}"
    with get_conn() as c: cats=policy._focus_categories(c,scope,year,True)
    active_count=sum(int(x.get("active") or 0) for x in cats)
    if active_count<5: st.warning(f"Khuyến nghị 5–8 mục trọng tâm; hiện có {active_count} mục đang áp dụng.")
    elif active_count>10: st.warning(f"Danh mục hiện có {active_count} mục; trên 10 mục dễ làm dữ liệu phân tán.")
    else: st.success(f"Danh mục hiện có {active_count} mục đang áp dụng.")
    customer_ui._html_table(st,["Mã","Tên danh mục","Phạm vi","Thứ tự","Năm","Trạng thái"],[[x["code"],x["name"],x.get("description") or "—",x["sort_order"],x["apply_year"],"Đang dùng" if x["active"] else "Ngưng"] for x in cats])
    if st.button("📋 Sao chép danh mục năm trước",key=f"focus_copy_fast_v2_{year}_{leader_id}"):
        ts=policy._now(); copied=0
        with get_conn() as c:
            prev=policy._focus_categories(c,scope,year-1,True)
            for x in prev:
                try:
                    c.execute("INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(scope,year,x["code"],x["name"],x.get("description"),x["sort_order"],x["active"],uid,uid,ts,ts)); copied+=1
                except Exception: pass
        st.toast(f"Đã sao chép {copied} mục từ năm {year-1}.",icon="✅"); st.rerun()
    opts=[None]+cats; edit=st.selectbox("Chọn danh mục để sửa",opts,format_func=lambda x:"＋ Tạo mới" if x is None else f"{x['code']} · {x['name']}",key="focus_edit_fast_v2")
    payload=fast_client_form(
        [
            {"name":"code","label":"Mã","type":"text","required":True,"default":str(edit.get("code") or "") if edit else "","placeholder":"TT01"},
            {"name":"name","label":"Tên ngắn gọn","type":"text","required":True,"default":str(edit.get("name") or "") if edit else ""},
            {"name":"description","label":"Mô tả phạm vi (1–2 câu)","type":"textarea","required":True,"default":str(edit.get("description") or "") if edit else "","full":True},
            {"name":"order","label":"Thứ tự hiển thị","type":"number","min":1,"step":1,"default":int(edit.get("sort_order") or 1) if edit else len(cats)+1},
            {"name":"active","label":"Đang áp dụng","type":"checkbox","default":bool(edit.get("active")) if edit else True},
        ],"Lưu danh mục",key=f"focus_catalog_fast_v2_{leader_id}_{year}_{int(edit['id']) if edit else 'new'}",reset_token=f"{leader_id}|{year}|{int(edit['id']) if edit else 'new'}|{edit.get('updated_at') if edit else len(cats)}",
    )
    if payload is not None:
        code=str(payload.get("code") or "").strip().upper(); name=str(payload.get("name") or "").strip(); desc=str(payload.get("description") or "").strip(); order=max(1,_safe_int(payload.get("order"),1)); active=bool(payload.get("active"))
        if not code or not name or not desc: st.error("Vui lòng nhập mã, tên và mô tả phạm vi.")
        else:
            ts=policy._now()
            try:
                with get_conn() as c:
                    if edit: c.execute("UPDATE weekly_focus_categories SET code=?,name=?,description=?,sort_order=?,active=?,updated_by=?,updated_at=? WHERE id=?",(code,name,desc,order,int(active),uid,ts,int(edit["id"])))
                    else: c.execute("INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(scope,year,code,name,desc,order,int(active),uid,uid,ts,ts))
                st.toast("Đã lưu danh mục trọng tâm.",icon="✅"); st.rerun()
            except Exception as exc: st.error(str(exc))
    if edit and st.button("Xóa/Ngừng áp dụng",key="focus_delete_fast_v2"):
        try:
            with get_conn() as c: c.execute("UPDATE weekly_focus_categories SET active=0,updated_by=?,updated_at=? WHERE id=?",(uid,policy._now(),int(edit["id"])))
            st.rerun()
        except Exception as exc: st.error(str(exc))


def _install_catalog_fast_forms(policy, logger=None):
    policy._render_catalog=_render_catalog_fast
    if logger: logger.info("MOBILE_INPUT_CATALOG_FAST_FORMS_INSTALLED stage=1 focus=1")


def _install_inline_focus_form(policy, logger=None):
    def inline_focus_create(st,u,get_conn,year,logger_arg=None):
        uid=int(policy._uget(u,"id"))
        with get_conn() as c: leaders=[dict(r) for r in c.execute("SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name").fetchall()]
        leader_id=uid
        if policy._is_admin(u) and leaders: leader_id=int(st.selectbox("Phòng/Trưởng phòng áp dụng",leaders,format_func=lambda x:x["full_name"],key=f"inline_focus_leader_fast_v2_{year}")["id"])
        scope=f"LEADER:{leader_id}"
        with st.expander("＋ Bổ sung mục trọng tâm ngay tại màn hình duyệt",expanded=False):
            payload=fast_client_form([
                {"name":"code","label":"Mã","type":"text","required":True,"placeholder":"TT06"},
                {"name":"name","label":"Tên ngắn gọn","type":"text","required":True},
                {"name":"description","label":"Mô tả phạm vi (1–2 câu)","type":"textarea","required":True,"full":True},
                {"name":"order","label":"Thứ tự","type":"number","min":1,"step":1,"default":6},
            ],"Thêm vào danh mục trọng tâm",key=f"inline_focus_client_v2_{year}_{leader_id}",reset_token=str(st.session_state.get(f"_inline_focus_epoch_{year}_{leader_id}",0)))
            if payload is not None:
                code=str(payload.get("code") or "").strip().upper(); name=str(payload.get("name") or "").strip(); desc=str(payload.get("description") or "").strip(); order=max(1,_safe_int(payload.get("order"),6))
                if not code or not name or not desc: st.error("Vui lòng nhập đủ mã, tên và mô tả phạm vi."); return
                try:
                    ts=policy._now()
                    with get_conn() as c: c.execute("INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?,?)",(scope,int(year),code,name,desc,order,uid,uid,ts,ts))
                    st.session_state[f"_inline_focus_epoch_{year}_{leader_id}"]=int(st.session_state.get(f"_inline_focus_epoch_{year}_{leader_id}",0))+1
                    st.toast("Đã bổ sung mục trọng tâm.",icon="✅"); st.rerun()
                except Exception as exc: st.error(str(exc))
    policy._inline_focus_create=inline_focus_create
    if logger: logger.info("MOBILE_INPUT_INLINE_FOCUS_FAST_INSTALLED submit_only=1")


def _disable_periodic_server_refresh(app_ns, logger=None):
    """Typing correctness wins over a 6-second whole-app refresh on mobile.

    Workflow changes are still visible on navigation/actions/manual reruns and push
    notifications continue independently. No timer is allowed to interrupt a draft.
    """
    def realtime_refresh_watch(_u): return None
    realtime_refresh_watch._khdn_mobile_guard=True
    app_ns["realtime_refresh_watch"]=realtime_refresh_watch
    if logger: logger.info("MOBILE_INPUT_PERIODIC_REFRESH_DISABLED seconds=0")


def install(app_ns, policy, logger=None):
    if app_ns.get(_FLAG)==VERSION: return
    log=logger or app_ns.get("LOGGER")
    from khdn_apps import worktype_contact_card_patch as worktype
    _migrate_task_type_scope_uniqueness(app_ns,log)
    _disable_periodic_server_refresh(app_ns,log)
    _install_admin_fast_forms(app_ns,worktype,log)
    _install_catalog_fast_forms(policy,log)
    _install_inline_focus_form(policy,log)
    app_ns[_FLAG]=VERSION
    if log:
        log.info("MOBILE_INPUT_PERFORMANCE_INSTALLED version=%s zero_keystroke_users=1 zero_keystroke_task_types=1 zero_keystroke_stages=1 zero_keystroke_focus=1 realtime_timer=0 task_type_scope_unique=1",VERSION)
