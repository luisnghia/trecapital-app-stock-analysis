"""Server-enforced, read-only room workload view for the Vấn tin role.

The route intercepts the authenticated app() *after* password reset and *before*
sidebar/navigation/action widgets. It is not the leader dashboard: only the two
room matrices can render. Data is loaded with an SQLite read-only connection.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

ROLE = "Vấn tin"

_VIEWER_ROUTE = '''    if str(u.get("role") or "") == "Vấn tin":
        from khdn_apps.inquiry_readonly_role import render_inquiry
        return render_inquiry(st, u, DB_PATH, LOGGER)
'''


def patch_source(source: str) -> str:
    """Insert a fail-closed viewer branch at the authenticated dispatch boundary."""
    marker = '    if u.get("must_change_password"):\n        force_password_change(u); return\n'
    if source.count(marker) != 1 or source.count("def app():") != 1:
        raise RuntimeError("INQUIRY_ROLE_PATCH_REJECTED: login/forced-password boundary changed")
    if _VIEWER_ROUTE in source:
        raise RuntimeError("INQUIRY_ROLE_PATCH_REJECTED: viewer dispatch already injected")
    source = source.replace(marker, marker + _VIEWER_ROUTE, 1)
    compile(source, "<khdn-inquiry-dispatch>", "exec")
    return source


def _is_inquiry(user) -> bool:
    try:
        return str(user.get("role") or "") == ROLE
    except AttributeError:
        return False


def _room_cases(db_path, *, loader=None):
    """No mutations, even if a future data-loader accidentally attempts to write."""
    from khdn_apps import customer_work
    loader = loader or customer_work.list_cases
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=15)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        return loader(conn, manager=True, include_completed=False)


def _tables(data):
    """Reuse the leader's exact, mutually exclusive case status buckets."""
    from khdn_apps import planning_operational_phase3_dashboard as dashboard
    priority = ("PROCESSING", "DELAYED", "OVERDUE", "ISSUES")
    by_stage = []
    for name in sorted({str(x.get("stage_name")) for x in data if x.get("stage_name")}):
        group = [x for x in data if str(x.get("stage_name") or "") == name]
        by_stage.append([name, *dashboard._workload_lists(group, priority)])
    by_staff = []
    for name in sorted({str(x.get("owner_name") or "—") for x in data}):
        group = [x for x in data if str(x.get("owner_name") or "—") == name]
        by_staff.append([name, *dashboard._workload_lists(group, priority, include_owner=False)])
    return by_stage, by_staff


def render_inquiry(st, user, db_path, logger=None):
    """Render exactly two read-only tables and a safe sign-out control."""
    if not _is_inquiry(user):
        raise PermissionError("Chỉ tài khoản thuộc nhóm Vấn tin được mở trang này.")
    st.session_state.pop("cw_case_id", None)
    st.session_state.pop("main_page", None)
    st.session_state.pop("main_section", None)
    st.sidebar.markdown("### 🔎 Vấn tin")
    st.sidebar.caption("Quyền chỉ xem · Không được cập nhật hoặc phê duyệt công việc.")
    if st.sidebar.button("Đăng xuất", key="khdn_inquiry_logout", use_container_width=True):
        from khdn_apps import device_login
        device_login.forget(db_path)
        for key in list(st.session_state):
            if key != "_device_command":
                st.session_state.pop(key, None)
        if logger:
            logger.info("INQUIRY_LOGOUT user_id=%s", user.get("id"))
        st.rerun()
        return

    st.title("🔎 Vấn tin · toàn phòng")
    st.caption("Chỉ xem các công việc khách hàng chưa hoàn thành của toàn phòng; không có chức năng tạo, sửa, xuất dữ liệu hoặc phê duyệt.")
    from khdn_apps import planning_operational_phase3_dashboard as dashboard
    data = _room_cases(db_path)
    by_stage, by_staff = _tables(data)
    st.caption(dashboard.WORKLOAD_GROUP_NOTE)
    heads = ["Đang xử lý", "Bị chậm", "Quá hạn", "Có vướng mắc"]
    st.subheader("Theo mục công việc · toàn phòng")
    dashboard._matrix_table(st, ["Mục công việc", *heads], by_stage)
    st.subheader("Theo cán bộ · toàn phòng")
    dashboard._matrix_table(st, ["Cán bộ", *heads], by_staff)
    if logger:
        logger.info("INQUIRY_ROOM_READONLY user_id=%s cases=%s stage_groups=%s staff_groups=%s",
                    user.get("id"), len(data), len(by_stage), len(by_staff))
