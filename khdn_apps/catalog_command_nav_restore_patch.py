"""Restore the original command-button navigation for Customer Work catalogs.

The zero-keystroke mobile performance layer replaced the original two command
buttons with ``st.tabs``.  That changed the visual language and also caused both
catalog panels to be built eagerly.  This patch restores the original cream
inactive / teal+gold active command buttons while keeping the submit-only fast
forms and isolated HTML tables introduced for iOS typing performance.

No business data or schema is modified here.
"""
from __future__ import annotations

from khdn_apps.legacy_fast_form import legacy_fast_form
from khdn_apps import planning_ui_admin_hotfix as admin_hotfix

VERSION = "1.0.0"


def _install_customer_catalog_command_nav(legacy_ui, customer_core, customer_ui, logger=None):
    """Install the fast catalog renderer with the legacy command-button nav."""

    def render_catalog_page(st, u, get_conn, page_title=None, logger=None):
        customer_core.ensure_schema(get_conn, logger)
        uid = int(legacy_ui._uget(u, "id"))
        if not customer_ui._manager(u):
            st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục.")
            return

        if page_title:
            page_title("Danh mục quy trình", "Mục công việc, SLA và danh mục công việc quan trọng")
        else:
            st.title("⚙️ Danh mục quy trình")

        view = admin_hotfix._local_command_tabs(
            st,
            "cw_catalog_view_v2",
            [
                ("stages", "Mục công việc / SLA"),
                ("important", "Danh mục công việc quan trọng"),
            ],
            default="stages",
            prefix="cw_catalog_v2",
        )

        if view == "stages":
            with get_conn() as c:
                stages = customer_core.active_stages(c, include_inactive=True)
            legacy_ui._optimized_html_table(
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

        elif view == "important":
            with get_conn() as c:
                cats = customer_core.active_important_categories(c, include_inactive=True)
            st.caption(
                "Danh mục này mặc định là **Q2 · Quan trọng & Chưa khẩn cấp**. Tại đây chỉ quản lý danh mục; "
                "mức ưu tiên cụ thể được chọn trong Kế hoạch và có thể được Lãnh đạo/Admin chỉnh khi phê duyệt."
            )
            legacy_ui._optimized_html_table(
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

    customer_ui._html_table = legacy_ui._optimized_html_table
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui.MOBILE_LEGACY_CATALOG_VERSION = f"{legacy_ui.VERSION}+cmdnav-{VERSION}"


def patch_legacy_installer(legacy_ui, logger=None):
    """Patch the final zero-keystroke installer once; safe across reruns."""
    if getattr(legacy_ui, "_CATALOG_COMMAND_NAV_RESTORE_PATCHED", False):
        return

    def install_customer_catalog(customer_core, customer_ui, logger=None):
        return _install_customer_catalog_command_nav(
            legacy_ui, customer_core, customer_ui, logger
        )

    legacy_ui._install_customer_catalog = install_customer_catalog
    legacy_ui._CATALOG_COMMAND_NAV_RESTORE_PATCHED = True
    if logger:
        logger.info(
            "CATALOG_COMMAND_NAV_RESTORE_PATCHED version=%s command_buttons=1 st_tabs=0 active_only=1 data_migration=0",
            VERSION,
        )
