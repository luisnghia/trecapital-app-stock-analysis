"""KHDN Ops V2.31.4 - direct full-edit button from task detail.

For Leader/Admin, append a prominent 'Edit all task information' button immediately
under task history/evaluation history. Clicking it opens the existing audited full
editor with the currently viewed task preselected, including CLOSED/CANCELLED tasks.
"""
from __future__ import annotations

import logging
from typing import Any

PATCH_VERSION = "2.31.4"
_INSTALL_FLAG = "_KHDN_DIRECT_TASK_EDIT_V2314"
_TARGET_KEY = "full_edit_target_task_id"


def _authorized(user: dict[str, Any] | None) -> bool:
    user = user or {}
    return bool(user.get("is_admin")) or user.get("role") == "Lãnh đạo phòng"


def _route_to_editor(ns: dict[str, Any], user: dict[str, Any], task_id: int) -> None:
    st = ns["st"]
    task_id = int(task_id)
    st.session_state[_TARGET_KEY] = task_id
    # Existing editor selectbox uses this key; presetting it opens exactly this task.
    st.session_state["full_edit_task_select"] = task_id

    if user.get("role") == "Lãnh đạo phòng":
        st.session_state["main_page"] = "leader"
        st.session_state["leader_view"] = "full_edit"
    else:
        # Admin accounts whose operational role is not Leader use the Admin route.
        st.session_state["main_page"] = "admin"
        st.session_state["admin_view"] = "full_edit"
    st.rerun()


def install(ns: dict[str, Any], full_edit_module) -> None:
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True

    st = ns["st"]

    # Wrap the existing full editor so a direct-route target is always preselected.
    original_render_full_editor = full_edit_module.render_full_task_editor

    def render_full_task_editor_direct(ns_arg, user):
        target = st.session_state.pop(_TARGET_KEY, None)
        if target is not None:
            try:
                st.session_state["full_edit_task_select"] = int(target)
            except Exception:
                pass
        return original_render_full_editor(ns_arg, user)

    full_edit_module.render_full_task_editor = render_full_task_editor_direct

    # task_history() is called immediately before the existing Leader reassignment /
    # rework controls, so this places the direct-edit action exactly where users look.
    original_task_history = ns["task_history"]

    def task_history_with_direct_edit(task_id):
        result = original_task_history(task_id)
        user = st.session_state.get("user") or {}
        if _authorized(user):
            st.markdown("#### Chỉnh sửa hồ sơ")
            st.caption("Admin/Lãnh đạo có thể sửa toàn bộ thông tin của hồ sơ này, kể cả hồ sơ đã kết thúc hoặc đã hủy. Mọi thay đổi đều được ghi audit.")
            if st.button(
                "✏️ SỬA TOÀN BỘ THÔNG TIN HỒ SƠ",
                type="primary",
                use_container_width=True,
                key=f"direct_full_edit_task_{int(task_id)}",
            ):
                _route_to_editor(ns, user, int(task_id))
        return result

    ns["task_history"] = task_history_with_direct_edit
    ns["APP_VERSION"] = PATCH_VERSION
    logging.getLogger("khdn_ops").info(
        "PATCH_INSTALL version=%s direct_full_edit=task_history leader_admin", PATCH_VERSION
    )
