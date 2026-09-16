"""KHDN Ops V2.31.5 - reliable inline full-edit from task detail.

Root cause fixed from V2.31.4:
The previous button routed Leader/Admin to synthetic ``full_edit`` navigation states.
The compact/mobile navigation patch intentionally normalizes Leader to active/history
and Admin to its fixed administration choices, so those synthetic states were reset
on rerun and the button appeared to do nothing.

V2.31.5 no longer routes through navigation at all. For Leader/Admin the button
opens the existing audited full-record editor inline, immediately below the selected
task history and before reassignment controls. This works for active, CLOSED and
CANCELLED tasks and is independent of mobile/sidebar navigation state.
"""
from __future__ import annotations

import logging
from typing import Any

PATCH_VERSION = "2.31.5"
_INSTALL_FLAG = "_KHDN_DIRECT_TASK_EDIT_V2315"
_TARGET_KEY = "direct_inline_full_edit_task_id"


def _authorized(user: dict[str, Any] | None) -> bool:
    user = user or {}
    return bool(user.get("is_admin")) or user.get("role") == "Lãnh đạo phòng"


def _set_inline_target(st, task_id: int) -> None:
    """Open exactly one task editor without changing any navigation state."""
    st.session_state[_TARGET_KEY] = int(task_id)


def _clear_inline_target(st) -> None:
    st.session_state.pop(_TARGET_KEY, None)


def install(ns: dict[str, Any], full_edit_module) -> None:
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True

    st = ns["st"]
    original_task_history = ns["task_history"]

    def task_history_with_direct_edit(task_id):
        task_id = int(task_id)
        result = original_task_history(task_id)
        user = st.session_state.get("user") or {}
        if not _authorized(user):
            return result

        st.markdown("#### Chỉnh sửa hồ sơ")
        st.caption(
            "Admin/Lãnh đạo có thể sửa toàn bộ thông tin của hồ sơ này, kể cả hồ sơ đã kết thúc hoặc đã hủy. "
            "Mọi thay đổi đều được ghi audit."
        )

        if st.button(
            "✏️ SỬA TOÀN BỘ THÔNG TIN HỒ SƠ",
            type="primary",
            use_container_width=True,
            key=f"direct_full_edit_task_{task_id}",
        ):
            # Do not rerun or route to another tab. Keeping this in the same script
            # run preserves the selected dataframe row and opens the form instantly.
            _set_inline_target(st, task_id)

        target = st.session_state.get(_TARGET_KEY)
        if target is not None and int(target) == task_id:
            st.divider()
            header_left, header_right = st.columns([4, 1])
            with header_left:
                st.markdown("### ✏️ Sửa toàn bộ thông tin hồ sơ đang chọn")
                st.caption("Form bên dưới đang sửa đúng hồ sơ hiện tại. Không cần tìm/chọn lại hồ sơ.")
            with header_right:
                if st.button(
                    "✖ Đóng form sửa",
                    use_container_width=True,
                    key=f"close_direct_full_edit_{task_id}",
                ):
                    _clear_inline_target(st)
                    st.rerun()

            # Reuse the exact audited editor introduced in V2.31.3 so validation,
            # decimal amounts, timestamps, evaluation edits and audit logging remain
            # identical between the global editor and this direct inline editor.
            full_edit_module._render_task_form(ns, user, task_id)

        return result

    ns["task_history"] = task_history_with_direct_edit
    ns["APP_VERSION"] = PATCH_VERSION
    logging.getLogger("khdn_ops").info(
        "PATCH_INSTALL version=%s direct_full_edit=inline task_history leader_admin",
        PATCH_VERSION,
    )
