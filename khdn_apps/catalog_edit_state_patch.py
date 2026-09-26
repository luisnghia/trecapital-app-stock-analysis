"""Fix Streamlit state synchronization for Customer Work catalog editors.

Changing the selected Stage/Important Category must load that row into the form,
while normal widget reruns must not overwrite edits the user is currently typing.
"""
from __future__ import annotations

VERSION = "1.0.0"


def _marker(edit):
    return "NEW" if edit is None else f"ID:{int(edit['id'])}"


def _stage_defaults(edit, count):
    if edit is None:
        return {
            "name": "",
            "order": int(count) + 1,
            "sla": 48.0,
            "done": False,
            "active": True,
        }
    return {
        "name": str(edit.get("name") or ""),
        "order": int(edit.get("sort_order") or 1),
        "sla": float(edit.get("sla_hours") or 0.0),
        "done": bool(edit.get("is_completion")),
        "active": bool(edit.get("active")),
    }


def _category_defaults(edit, count):
    if edit is None:
        return {
            "name": "",
            "description": "",
            "order": int(count) + 1,
            "active": True,
        }
    return {
        "name": str(edit.get("name") or ""),
        "description": str(edit.get("description") or ""),
        "order": int(edit.get("sort_order") or 1),
        "active": bool(edit.get("active")),
    }


def _sync(state, marker_key, widget_map, edit, defaults):
    """Load DB values only when the selected record changes.

    This is deliberately marker-based.  It prevents later reruns from resetting
    fields after the user has started editing them.
    """
    current = _marker(edit)
    if state.get(marker_key) == current:
        return False
    state[marker_key] = current
    for field, key in widget_map.items():
        state[key] = defaults[field]
    return True


def install(customer_ui, core, logger=None):
    def render_catalog_page(st, u, get_conn, page_title=None, logger=None):
        core.ensure_schema(get_conn, logger)
        uid = int(u["id"])
        if not customer_ui._manager(u):
            st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục.")
            return

        if page_title:
            page_title("Danh mục quy trình", "Mục công việc, SLA và danh mục công việc quan trọng")
        else:
            st.title("⚙️ Danh mục quy trình")

        # Deferred resets happen before the related selectbox is instantiated.
        if st.session_state.pop("_cw_stage_reset", False):
            st.session_state["cw_stage_edit"] = None
            st.session_state.pop("_cw_stage_loaded", None)
        if st.session_state.pop("_cw_cat_reset", False):
            st.session_state["cw_cat_edit"] = None
            st.session_state.pop("_cw_cat_loaded", None)

        tab1, tab2 = st.tabs(["Mục công việc / SLA", "Danh mục công việc quan trọng"])

        with tab1:
            with get_conn() as c:
                stages = core.active_stages(c, include_inactive=True)

            customer_ui._html_table(
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

            _sync(
                st.session_state,
                "_cw_stage_loaded",
                {
                    "name": "cw_stage_name_field",
                    "order": "cw_stage_order_field",
                    "sla": "cw_stage_sla_field",
                    "done": "cw_stage_done_field",
                    "active": "cw_stage_active_field",
                },
                edit,
                _stage_defaults(edit, len(stages)),
            )

            with st.form("cw_stage_form"):
                name = st.text_input("Tên mục công việc", key="cw_stage_name_field")
                order = st.number_input("Thứ tự", min_value=1, step=1, key="cw_stage_order_field")
                sla = st.number_input("SLA cảnh báo (giờ)", min_value=0.0, step=1.0, key="cw_stage_sla_field")
                done = st.checkbox("Đây là mục hoàn thành", key="cw_stage_done_field")
                active = st.checkbox("Đang sử dụng", key="cw_stage_active_field")
                save = st.form_submit_button("Lưu danh mục", type="primary")

            if save:
                try:
                    core.save_stage_catalog(
                        get_conn, uid, edit["id"] if edit else None,
                        name, order, sla, done, active, logger,
                    )
                    st.toast("Đã cập nhật mục công việc." if edit else "Đã tạo mục công việc.", icon="✅")
                    st.session_state["_cw_stage_reset"] = True
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            if edit and st.button("Xóa/Ngưng sử dụng mục này", key="cw_stage_del"):
                mode = core.delete_stage_catalog(get_conn, uid, edit["id"], logger)
                st.toast("Đã xóa." if mode == "DELETE" else "Mục đã có lịch sử nên được ngưng sử dụng thay vì xóa dữ liệu cũ.")
                st.session_state["_cw_stage_reset"] = True
                st.rerun()

        with tab2:
            with get_conn() as c:
                cats = core.active_important_categories(c, include_inactive=True)

            st.caption("Danh mục này mặc định là **Q2 · Quan trọng & Chưa khẩn cấp**. Tại đây chỉ quản lý danh mục; mức ưu tiên cụ thể được chọn trong Kế hoạch và có thể được Lãnh đạo/Admin chỉnh khi phê duyệt.")
            customer_ui._html_table(
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

            _sync(
                st.session_state,
                "_cw_cat_loaded",
                {
                    "name": "cw_cat_name_field",
                    "description": "cw_cat_desc_field",
                    "order": "cw_cat_order_field",
                    "active": "cw_cat_active_field",
                },
                edit,
                _category_defaults(edit, len(cats)),
            )

            with st.form("cw_cat_form"):
                name = st.text_input("Tên danh mục", key="cw_cat_name_field")
                desc = st.text_area("Diễn giải", key="cw_cat_desc_field")
                order = st.number_input("Thứ tự", min_value=1, step=1, key="cw_cat_order_field")
                active = st.checkbox("Đang sử dụng", key="cw_cat_active_field")
                save = st.form_submit_button("Lưu danh mục", type="primary")

            if save:
                try:
                    core.save_important_category(
                        get_conn, uid, edit["id"] if edit else None,
                        name, desc, order, active, logger,
                    )
                    st.toast("Đã cập nhật danh mục quan trọng." if edit else "Đã tạo danh mục quan trọng.", icon="✅")
                    st.session_state["_cw_cat_reset"] = True
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            if edit and st.button("Xóa/Ngưng sử dụng danh mục", key="cw_cat_del"):
                mode = core.delete_important_category(get_conn, uid, edit["id"], logger)
                st.toast("Đã xóa." if mode == "DELETE" else "Danh mục đã được dùng nên được ngưng sử dụng để giữ lịch sử.")
                st.session_state["_cw_cat_reset"] = True
                st.rerun()

        customer_ui._glossary(st)

    customer_ui.render_catalog_page = render_catalog_page
    customer_ui.CATALOG_EDIT_STATE_VERSION = VERSION
    if logger:
        logger.info("CATALOG_EDIT_STATE_PATCH_INSTALLED version=%s", VERSION)
