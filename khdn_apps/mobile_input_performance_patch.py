"""Final mobile-input performance guard for KHDN Apps.

Installed after all planning/operations overlays so later UI patches cannot bypass
the earlier V2.14 input optimisations.

Goals:
- keep the 6-second workflow watcher off input-heavy/custom planning routes;
- restore the browser-local submit-only input for System Admin task types;
- batch the inline focus-catalog form so it never reruns while typing;
- keep catalog tables lightweight HTML instead of a React dataframe grid.
"""
from __future__ import annotations

import html
import sqlite3

from khdn_apps.fast_catalog_input import fast_catalog_input
from khdn_apps import planning_ui_admin_hotfix as admin_hotfix

VERSION = "1.0.0"
_FLAG = "_MOBILE_INPUT_PERFORMANCE_VERSION"

_LIVE_ROUTES = {"support", "qlkh", "leader", "dashboard", "work_dashboard", "work_today"}
_INPUT_HEAVY_ROUTES = {
    "admin", "profile", "guide", "customer_work", "weekly_plan", "work_catalogs",
    "work_approvals",
}


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


def _static_task_type_table(st, rows):
    if not rows:
        return
    head = ("ID", "Tên công việc", "Phân hệ", "Trạng thái", "Ngày tạo", "Cập nhật")
    body = []
    for r in rows:
        values = (
            int(r["id"]),
            str(r.get("name") or ""),
            _scope_label(r.get("module_scope")),
            "Đang sử dụng" if r.get("active") else "Ngưng",
            str(r.get("created_at") or ""),
            str(r.get("updated_at") or ""),
        )
        body.append(
            "<tr>" + "".join(
                f"<td>{html.escape(str(v))}</td>" for v in values
            ) + "</tr>"
        )
    table = f"""
    <style>
      .khdn-fast-admin-table{{width:100%;overflow:auto;border:1px solid rgba(127,127,127,.55);
        border-radius:10px;margin:.35rem 0 .85rem}}
      .khdn-fast-admin-table table{{width:100%;border-collapse:collapse;table-layout:auto;font-size:.88rem}}
      .khdn-fast-admin-table th,.khdn-fast-admin-table td{{border:1px solid rgba(127,127,127,.45);
        padding:8px 9px;text-align:left;vertical-align:top;white-space:normal;overflow-wrap:anywhere}}
      .khdn-fast-admin-table th{{font-weight:850;background:rgba(15,118,110,.10);white-space:nowrap}}
      @media(max-width:760px){{
        .khdn-fast-admin-table table{{font-size:.78rem}}
        .khdn-fast-admin-table th,.khdn-fast-admin-table td{{padding:7px 6px}}
      }}
    </style>
    <div class="khdn-fast-admin-table"><table>
      <thead><tr>{''.join(f'<th>{html.escape(x)}</th>' for x in head)}</tr></thead>
      <tbody>{''.join(body)}</tbody>
    </table></div>
    """
    if hasattr(st, "html"):
        st.html(table)
    else:
        st.markdown(table, unsafe_allow_html=True)


def _render_system_task_types_fast(ns, u, worktype, logger=None):
    st = ns["st"]
    get_conn = ns["get_conn"]
    page_title = ns.get("page_title")
    log = logger or ns.get("LOGGER")

    if page_title:
        page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF và loại công việc.")
    else:
        st.title("Quản trị hệ thống")

    st.session_state["system_admin_view_v3"] = "types"
    admin_hotfix._command_tabs_css(st)
    options = [("users", "👥 Người dùng"), ("customers", "🏢 Khách hàng CIF"), ("types", "🧩 Loại công việc")]
    widths = [max(1.0, min(2.7, len(label) / 11.0)) for _, label in options]
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

    worktype.ensure_worktype_scope(get_conn, log)
    st.subheader("Loại công việc")
    st.caption(
        "Danh mục dùng chung toàn hệ thống. Mỗi loại được gán đúng một phân hệ: "
        "**Tác nghiệp** hoặc **Kế hoạch**; loại thuộc phân hệ nào chỉ xuất hiện tại phân hệ đó."
    )
    with get_conn() as c:
        rows = [
            dict(r) for r in c.execute(
                "SELECT id,name,module_scope,active,created_at,updated_at "
                "FROM task_types ORDER BY id"
            ).fetchall()
        ]
    if rows:
        _static_task_type_table(st, rows)
    else:
        st.info("Chưa có Loại công việc.")

    st.markdown("#### Tạo loại công việc")
    new_scope = st.selectbox(
        "Thuộc phân hệ *",
        ["OPS", "PLAN"],
        format_func=_scope_label,
        key="system_task_type_scope_fast_v4",
    )
    latest = max((str(r.get("updated_at") or "") for r in rows), default="")
    create_reset = f"{len(rows)}|{latest}"
    submitted_name = fast_catalog_input(
        "Tên công việc mới *",
        "Thêm loại công việc",
        key="system_task_type_name_fast_v4",
        placeholder="Nhập tên loại công việc",
        reset_token=create_reset,
    )
    if submitted_name is not None:
        clean = str(submitted_name or "").strip()
        if not clean:
            st.error("Bắt buộc nhập tên Loại công việc.")
        else:
            try:
                ts = ns["now_str"]() if "now_str" in ns else __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with get_conn() as c:
                    exists = c.execute(
                        "SELECT id FROM task_types WHERE lower(trim(name))=lower(trim(?))",
                        (clean,),
                    ).fetchone()
                    if exists:
                        raise ValueError("Tên Loại công việc đã tồn tại.")
                    cur = c.execute(
                        "INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) "
                        "VALUES(?,8,1,?,?,?)",
                        (clean, str(new_scope), ts, ts),
                    )
                    new_id = int(cur.lastrowid)
                audit = ns.get("audit")
                if audit:
                    audit(
                        int(_uget(u, "id")),
                        "CREATE_TASK_TYPE",
                        "task_type",
                        new_id,
                        f"name={clean}; module_scope={new_scope}",
                    )
                st.toast("Đã thêm Loại công việc.", icon="✅")
                st.rerun()
            except (sqlite3.IntegrityError, ValueError) as exc:
                st.error(str(exc))

    if rows:
        st.markdown("#### Sửa loại công việc")
        by_id = {int(r["id"]): r for r in rows}
        selected = st.selectbox(
            "Chọn loại công việc để sửa",
            list(by_id),
            format_func=lambda x: f"{by_id[int(x)]['name']} · {_scope_label(by_id[int(x)].get('module_scope'))}",
            key="system_task_type_edit_pick_fast_v4",
        )
        cur = by_id[int(selected)]
        scope_options = ["OPS", "PLAN"]
        current_scope = str(cur.get("module_scope") or "OPS")
        edit_scope = st.selectbox(
            "Thuộc phân hệ",
            scope_options,
            index=scope_options.index(current_scope if current_scope in scope_options else "OPS"),
            format_func=_scope_label,
            key=f"system_task_type_edit_scope_fast_v4_{int(selected)}",
        )
        edit_active = st.checkbox(
            "Đang sử dụng",
            value=bool(cur.get("active")),
            key=f"system_task_type_edit_active_fast_v4_{int(selected)}",
        )
        edit_name = fast_catalog_input(
            "Tên công việc",
            "Lưu thay đổi",
            key=f"system_task_type_edit_name_fast_v4_{int(selected)}",
            default_value=str(cur.get("name") or ""),
            reset_token=f"{int(selected)}|{cur.get('updated_at') or ''}",
        )
        if edit_name is not None:
            clean = str(edit_name or "").strip()
            if not clean:
                st.error("Tên Loại công việc không được để trống.")
            else:
                try:
                    ts = ns["now_str"]() if "now_str" in ns else __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with get_conn() as c:
                        clash = c.execute(
                            "SELECT id FROM task_types "
                            "WHERE lower(trim(name))=lower(trim(?)) AND id<>?",
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
                        audit(
                            int(_uget(u, "id")),
                            "UPDATE_TASK_TYPE",
                            "task_type",
                            int(selected),
                            f"name={clean}; module_scope={edit_scope}; active={bool(edit_active)}",
                        )
                    st.toast("Đã cập nhật Loại công việc.", icon="✅")
                    st.rerun()
                except (sqlite3.IntegrityError, ValueError) as exc:
                    st.error(str(exc))


def _install_inline_focus_form(policy, logger=None):
    """The inline focus editor was added after V2.14 and was outside st.form."""
    def inline_focus_create(st, u, get_conn, year, logger_arg=None):
        uid = int(policy._uget(u, "id"))
        with get_conn() as c:
            leaders = [
                dict(r) for r in c.execute(
                    "SELECT id,full_name FROM users WHERE active=1 "
                    "AND role='Lãnh đạo phòng' ORDER BY full_name"
                ).fetchall()
            ]
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
            with st.form(f"inline_focus_fast_form_{year}_{leader_id}", clear_on_submit=True, enter_to_submit=False):
                a, b = st.columns([1, 3])
                code = a.text_input("Mã *", key=f"inline_focus_code_fast_{year}_{leader_id}", placeholder="TT06")
                name = b.text_input("Tên ngắn gọn *", key=f"inline_focus_name_fast_{year}_{leader_id}")
                desc = st.text_area("Mô tả phạm vi (1–2 câu) *", key=f"inline_focus_desc_fast_{year}_{leader_id}")
                order = st.number_input("Thứ tự", min_value=1, value=6, step=1, key=f"inline_focus_order_fast_{year}_{leader_id}")
                save = st.form_submit_button("Thêm vào danh mục trọng tâm", type="primary")
            if save:
                if not str(code).strip() or not str(name).strip() or not str(desc).strip():
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
                                scope, int(year), str(code).strip().upper(), str(name).strip(),
                                str(desc).strip(), int(order), uid, uid, ts, ts,
                            ),
                        )
                    st.toast("Đã bổ sung mục trọng tâm.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    policy._inline_focus_create = inline_focus_create
    if logger:
        logger.info("MOBILE_INPUT_FOCUS_FORM_INSTALLED batched=1")


def _install_realtime_guard(app_ns, logger=None):
    original = app_ns.get("realtime_refresh_watch")
    if not original or getattr(original, "_khdn_mobile_guard", False):
        return
    st = app_ns["st"]

    def realtime_refresh_watch(u):
        route = str(st.session_state.get("main_page") or "")
        if route in _INPUT_HEAVY_ROUTES:
            return None
        if route and route not in _LIVE_ROUTES:
            return None
        return original(u)

    realtime_refresh_watch._khdn_mobile_guard = True
    app_ns["realtime_refresh_watch"] = realtime_refresh_watch
    if logger:
        logger.info("MOBILE_INPUT_REALTIME_GUARD_INSTALLED live_routes=%s", ",".join(sorted(_LIVE_ROUTES)))


def install(app_ns, policy, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return
    log = logger or app_ns.get("LOGGER")
    _install_realtime_guard(app_ns, log)
    _install_inline_focus_form(policy, log)
    admin_hotfix._render_system_task_types = _render_system_task_types_fast

    app_ns[_FLAG] = VERSION
    if log:
        log.info(
            "MOBILE_INPUT_PERFORMANCE_INSTALLED version=%s task_type_iframe=1 "
            "task_type_static_table=1 inline_focus_form=1 realtime_guard=1",
            VERSION,
        )
