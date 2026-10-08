"""Final mobile catalog/UI performance layer with legacy visual structure.

Goals:
- keep all six System Admin destinations in a deterministic 2-column mobile grid;
- restore the old Task Type page order: current table -> create -> edit;
- keep Customer Work catalog tables/selectors/labels while moving only draft input
  state into a submit-only browser component, eliminating iOS keystroke bridge work;
- never migrate or rewrite business data during installation.
"""
from __future__ import annotations

import html
import sqlite3

from khdn_apps.legacy_fast_form import legacy_fast_form
from khdn_apps import mobile_input_performance_patch as mobile
from khdn_apps import mobile_admin_restore_perf_patch as mobile_admin
from khdn_apps import planning_operational_phase7_patch as phase7
from khdn_apps import planning_ui_admin_hotfix as admin_hotfix

VERSION = "1.0.0"
_FLAG = "_MOBILE_LEGACY_UI_PERF_VERSION"


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


def _admin_cards_2x3(st, default="users"):
    """Six original Admin routes, always rendered as three rows x two cards."""
    options = list(phase7._ADMIN_OPTIONS)
    allowed = {value for value, _ in options}
    current = str(st.session_state.get("admin_view") or default)
    if current not in allowed:
        current = default if default in allowed else options[0][0]
        st.session_state["admin_view"] = current

    st.html(
        """<style>
        div[class*='st-key-p16_system_admin_grid'] [data-testid='stHorizontalBlock']{
          display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
          gap:.72rem!important;width:100%!important;align-items:stretch!important;
        }
        div[class*='st-key-p16_system_admin_grid'] [data-testid='stColumn']{
          width:100%!important;min-width:0!important;max-width:none!important;flex:none!important;
        }
        div[class*='st-key-p16_admin_card_'] button{
          width:100%!important;min-height:7.0rem!important;border-radius:18px!important;
          background:linear-gradient(145deg,#145C56,#176C64)!important;
          color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
          font-weight:900!important;padding:.68rem .42rem!important;white-space:normal!important;
          line-height:1.22!important;border:1px solid rgba(99,220,203,.62)!important;
          box-shadow:none!important;transform:none!important;
        }
        div[class*='st-key-p16_admin_card_'] button *{
          color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;font-weight:900!important;
          white-space:normal!important;overflow-wrap:anywhere!important;
        }
        div[class*='st-key-p16_admin_active_'] button{
          border:2px solid #F4B41A!important;box-shadow:0 0 0 1px rgba(244,180,26,.22)!important;
        }
        @media(max-width:700px){
          div[class*='st-key-p16_system_admin_grid'] [data-testid='stHorizontalBlock']{gap:.62rem!important}
          div[class*='st-key-p16_admin_card_'] button{min-height:6.15rem!important;border-radius:16px!important;padding:.52rem .30rem!important}
          div[class*='st-key-p16_admin_card_'] button p{font-size:.82rem!important;line-height:1.18!important}
        }
        </style>"""
    )
    with st.container(key="p16_system_admin_grid"):
        for row_start in range(0, len(options), 2):
            cols = st.columns(2, gap="small")
            for col, (value, label) in zip(cols, options[row_start:row_start + 2]):
                with col:
                    key = f"p16_admin_card_{value}"
                    wrap_key = f"p16_admin_active_{value}" if value == current else f"p16_admin_idle_{value}"
                    with st.container(key=wrap_key):
                        if st.button(label, key=key, use_container_width=True):
                            st.session_state["admin_view"] = value
                            for state_key in ("system_admin_view_v2", "system_admin_view_v3", "system_admin_view_v4"):
                                st.session_state[state_key] = value
                            st.rerun()
    return current


def _render_admin_nav(ns, current):
    st = ns["st"]
    allowed = {value for value, _ in phase7._ADMIN_OPTIONS}
    if current in allowed:
        st.session_state["admin_view"] = current
        for key in ("system_admin_view_v2", "system_admin_view_v3", "system_admin_view_v4"):
            st.session_state[key] = current
    return _admin_cards_2x3(st, current if current in allowed else "users")


def _render_system_task_types_legacy_fast(ns, u, worktype, logger=None):
    """Old page structure with a permanently visible current catalog table."""
    st, get_conn = ns["st"], ns["get_conn"]
    log = logger or ns.get("LOGGER")
    mobile_admin._admin_title(ns)
    _render_admin_nav(ns, "types")
    worktype.ensure_worktype_scope(get_conn, log)

    st.subheader("Loại công việc")
    st.caption(
        "Tên Loại công việc được phép trùng giữa **Tác nghiệp** và **Kế hoạch**; "
        "trong cùng một phân hệ thì tên vẫn phải duy nhất."
    )
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,name,module_scope,active,created_at,updated_at FROM task_types ORDER BY id"
        ).fetchall()]

    st.markdown("#### Danh sách loại công việc")
    if rows:
        mobile._static_table(
            st,
            ["ID", "Tên công việc", "Phân hệ", "Trạng thái", "Ngày tạo", "Cập nhật"],
            [[
                r["id"], r["name"], _scope_label(r.get("module_scope")),
                "Đang sử dụng" if r.get("active") else "Ngưng",
                r.get("created_at") or "", r.get("updated_at") or "",
            ] for r in rows],
            "khdn-fast-task-type-table-p16",
        )
    else:
        st.info("Chưa có Loại công việc.")

    st.markdown("### Tạo loại công việc")
    latest = max((str(r.get("updated_at") or "") for r in rows), default="")
    create = legacy_fast_form(
        [
            {"name":"name","label":"Tên công việc mới","type":"text","required":True,"placeholder":"Nhập tên loại công việc"},
            {"name":"module_scope","label":"Thuộc phân hệ","type":"select","options":[
                {"value":"OPS","label":"Tác nghiệp"},{"value":"PLAN","label":"Kế hoạch"}],"default":"OPS"},
        ],
        "Thêm loại công việc",
        key="system_task_type_create_legacy_p16",
        reset_token=f"{len(rows)}|{latest}",
    )
    if create is not None:
        clean = str(create.get("name") or "").strip()
        scope = str(create.get("module_scope") or "OPS")
        if not clean:
            st.error("Bắt buộc nhập tên Loại công việc.")
        else:
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
                    ns["audit"](
                        int(_uget(u,"id")), "CREATE_TASK_TYPE", "task_type", new_id,
                        f"name={clean}; module_scope={scope}",
                    )
                st.toast("Đã thêm Loại công việc.", icon="✅")
                st.rerun()
            except (sqlite3.IntegrityError, ValueError) as exc:
                st.error(str(exc))

    st.markdown("### Sửa loại công việc")
    if not rows:
        st.caption("Chưa có loại công việc để sửa.")
        return
    by_id = {int(r["id"]): r for r in rows}
    selected = st.selectbox(
        "Chọn loại công việc để sửa",
        list(by_id),
        format_func=lambda x: f"{by_id[int(x)]['name']} · {_scope_label(by_id[int(x)].get('module_scope'))}",
        key="system_task_type_edit_pick_legacy_p16",
    )
    cur = by_id[int(selected)]
    edit = legacy_fast_form(
        [
            {"name":"name","label":"Tên công việc","type":"text","required":True,"default":str(cur.get("name") or "")},
            {"name":"module_scope","label":"Thuộc phân hệ","type":"select","options":[
                {"value":"OPS","label":"Tác nghiệp"},{"value":"PLAN","label":"Kế hoạch"}],"default":str(cur.get("module_scope") or "OPS")},
            {"name":"active","label":"Đang sử dụng","type":"checkbox","default":bool(cur.get("active"))},
        ],
        "Lưu thay đổi",
        key=f"system_task_type_edit_legacy_p16_{int(selected)}",
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
                    ns["audit"](
                        int(_uget(u,"id")), "UPDATE_TASK_TYPE", "task_type", int(selected),
                        f"name={clean}; module_scope={scope}; active={active}",
                    )
                st.toast("Đã cập nhật Loại công việc.", icon="✅")
                st.rerun()
            except (sqlite3.IntegrityError, ValueError) as exc:
                st.error(str(exc))


def _optimized_html_table(st, heads, rows, widths=None):
    """Same visual table as before, isolated from keyboard-time layout work."""
    esc = lambda v: html.escape("" if v is None else str(v))
    colgroup = "<colgroup>" + "".join(f'<col style="width:{w}">' for w in widths) + "</colgroup>" if widths else ""
    h = "".join(f"<th>{esc(x)}</th>" for x in heads)
    b = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in r) + "</tr>" for r in rows)
    st.html(
        f'''<div class="cw-table-wrap khdn-keyboard-isolated-table"><table>{colgroup}<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>
        <style>
        .cw-table-wrap{{overflow-x:auto;width:100%;contain:layout paint style;content-visibility:auto;contain-intrinsic-size:auto 360px;}}
        .cw-table-wrap table{{width:100%;table-layout:fixed;border-collapse:collapse;}}
        .cw-table-wrap th,.cw-table-wrap td{{padding:8px 9px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere;}}
        .cw-table-wrap th{{font-weight:800;}}
        </style>'''
    )


def _install_customer_catalog(customer_core, customer_ui, logger=None):
    """Replace only catalog draft widgets; preserve page structure and data calls."""
    def render_catalog_page(st, u, get_conn, page_title=None, logger=None):
        customer_core.ensure_schema(get_conn, logger)
        uid = int(_uget(u, "id"))
        if not customer_ui._manager(u):
            st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục.")
            return
        if page_title:
            page_title("Danh mục quy trình", "Mục công việc, SLA và danh mục công việc quan trọng")
        else:
            st.title("⚙️ Danh mục quy trình")

        tab1, tab2 = st.tabs(["Mục công việc / SLA", "Danh mục công việc quan trọng"])
        with tab1:
            with get_conn() as c:
                stages = customer_core.active_stages(c, include_inactive=True)
            _optimized_html_table(
                st,
                ["Thứ tự", "Mục công việc", "SLA (giờ)", "Hoàn tất", "Trạng thái"],
                [[
                    s["sort_order"], s["name"], f"{float(s['sla_hours']):.1f}",
                    "Có" if s["is_completion"] else "Không",
                    "Đang dùng" if s["active"] else "Ngưng",
                ] for s in stages],
            )
            opts = [None] + stages
            edit = st.selectbox(
                "Chọn mục công việc để sửa",
                opts,
                format_func=lambda x: "＋ Tạo mới" if x is None else x["name"],
                key="cw_stage_edit",
            )
            default_name = str(edit.get("name") or "") if edit else ""
            default_order = int(edit.get("sort_order") or 1) if edit else len(stages) + 1
            default_sla = float(edit.get("sla_hours") or 0.0) if edit else 48.0
            default_done = bool(edit.get("is_completion")) if edit else False
            default_active = bool(edit.get("active")) if edit else True
            marker = f"{int(edit['id'])}|{edit.get('updated_at') or ''}" if edit else f"NEW|{len(stages)}"
            payload = legacy_fast_form(
                [
                    {"name":"name","label":"Tên mục công việc","type":"text","required":True,"default":default_name},
                    {"name":"order","label":"Thứ tự","type":"number","min":1,"step":1,"default":default_order},
                    {"name":"sla","label":"SLA cảnh báo (giờ)","type":"number","min":0,"step":1,"default":default_sla},
                    {"name":"done","label":"Đây là bước kết thúc quy trình","type":"checkbox","default":default_done},
                    {"name":"active","label":"Đang sử dụng","type":"checkbox","default":default_active},
                ],
                "Lưu danh mục",
                key=f"cw_stage_legacy_fast_p16_{int(edit['id']) if edit else 'new'}",
                reset_token=marker,
            )
            if payload is not None:
                try:
                    customer_core.save_stage_catalog(
                        get_conn, uid, edit["id"] if edit else None,
                        str(payload.get("name") or ""),
                        max(1, int(payload.get("order") or 1)),
                        max(0.0, float(payload.get("sla") or 0.0)),
                        bool(payload.get("done")), bool(payload.get("active")), logger,
                    )
                    st.toast("Đã cập nhật mục công việc." if edit else "Đã tạo mục công việc.", icon="✅")
                    st.session_state["cw_stage_edit"] = None
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if edit and st.button("Xóa/Ngưng sử dụng mục này", key="cw_stage_del"):
                mode = customer_core.delete_stage_catalog(get_conn, uid, edit["id"], logger)
                st.toast("Đã xóa." if mode == "DELETE" else "Mục đã có lịch sử nên được ngưng sử dụng thay vì xóa dữ liệu cũ.")
                st.session_state["cw_stage_edit"] = None
                st.rerun()

        with tab2:
            with get_conn() as c:
                cats = customer_core.active_important_categories(c, include_inactive=True)
            st.caption(
                "Danh mục này mặc định là **Q2 · Quan trọng & Chưa khẩn cấp**. Tại đây chỉ quản lý danh mục; "
                "mức ưu tiên cụ thể được chọn trong Kế hoạch và có thể được Lãnh đạo/Admin chỉnh khi phê duyệt."
            )
            _optimized_html_table(
                st,
                ["Thứ tự", "Danh mục quan trọng", "Diễn giải", "Trạng thái"],
                [[
                    x["sort_order"], x["name"], x.get("description") or "—",
                    "Đang dùng" if x["active"] else "Ngưng",
                ] for x in cats],
            )
            opts = [None] + cats
            edit = st.selectbox(
                "Chọn danh mục để sửa",
                opts,
                format_func=lambda x: "＋ Tạo mới" if x is None else x["name"],
                key="cw_cat_edit",
            )
            default_name = str(edit.get("name") or "") if edit else ""
            default_desc = str(edit.get("description") or "") if edit else ""
            default_order = int(edit.get("sort_order") or 1) if edit else len(cats) + 1
            default_active = bool(edit.get("active")) if edit else True
            marker = f"{int(edit['id'])}|{edit.get('updated_at') or ''}" if edit else f"NEW|{len(cats)}"
            payload = legacy_fast_form(
                [
                    {"name":"name","label":"Tên danh mục","type":"text","required":True,"default":default_name},
                    {"name":"description","label":"Diễn giải","type":"textarea","default":default_desc},
                    {"name":"order","label":"Thứ tự","type":"number","min":1,"step":1,"default":default_order},
                    {"name":"active","label":"Đang sử dụng","type":"checkbox","default":default_active},
                ],
                "Lưu danh mục",
                key=f"cw_cat_legacy_fast_p16_{int(edit['id']) if edit else 'new'}",
                reset_token=marker,
            )
            if payload is not None:
                try:
                    customer_core.save_important_category(
                        get_conn, uid, edit["id"] if edit else None,
                        str(payload.get("name") or ""), str(payload.get("description") or ""),
                        max(1, int(payload.get("order") or 1)), bool(payload.get("active")), logger,
                    )
                    st.toast("Đã cập nhật danh mục quan trọng." if edit else "Đã tạo danh mục quan trọng.", icon="✅")
                    st.session_state["cw_cat_edit"] = None
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if edit and st.button("Xóa/Ngừng áp dụng danh mục", key="cw_cat_del"):
                mode = customer_core.delete_important_category(get_conn, uid, edit["id"], logger)
                st.toast("Đã xóa." if mode == "DELETE" else "Danh mục đã được dùng nên được ngưng sử dụng để giữ lịch sử.")
                st.session_state["cw_cat_edit"] = None
                st.rerun()
        customer_ui._glossary(st)

    customer_ui._html_table = _optimized_html_table
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui.MOBILE_LEGACY_CATALOG_VERSION = VERSION


def install(app_ns, policy, customer_core, customer_ui, worktype, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return
    # All Admin pages (including reason/audit/backup renderers in Phase 7) resolve
    # this global at render time, so one replacement fixes every route.
    phase7._admin_cards = _admin_cards_2x3
    mobile_admin._render_six_admin_nav = _render_admin_nav
    mobile_admin._render_system_task_types_fast = _render_system_task_types_legacy_fast
    mobile._render_system_admin_nav = _render_admin_nav
    mobile._render_system_task_types_fast = _render_system_task_types_legacy_fast
    admin_hotfix._render_system_task_types = lambda ns, u, worktype_arg, logger=None: _render_system_task_types_legacy_fast(ns, u, worktype_arg, logger)
    _install_customer_catalog(customer_core, customer_ui, logger)
    app_ns[_FLAG] = VERSION
    log = logger or app_ns.get("LOGGER")
    if log:
        log.info(
            "MOBILE_LEGACY_UI_PERF_INSTALLED version=%s admin_grid=2x3 task_type_table_always=1 customer_catalog_submit_only=1 data_migration=0",
            VERSION,
        )
