"""KHDN Ops entrypoint with the integrated Weekly Plan module."""
from __future__ import annotations

from khdn_apps import app as base
from khdn_apps.weekly_plan_v11 import weekly_plan_page


WEEKLY_PLAN_ROLES = {"Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng"}


def weekly_access_allowed(u) -> bool:
    """Server-side navigation guard for the Weekly Plan module.

    The user explicitly requested no Ban Giám đốc view. Only the two officer
    roles and room leaders may enter this module, regardless of admin flag.
    """
    return str((u or {}).get("role") or "") in WEEKLY_PLAN_ROLES


def sidebar_navigation(u):
    """Keep the existing KHDN_APP navigation format and add Weekly Plan safely."""
    options = []
    role = str((u or {}).get("role") or "")
    if role == "Cán bộ hỗ trợ":
        options.append(("support", "🧾  Tác nghiệp"))
    if role == "Cán bộ QLKH":
        options.append(("qlkh", "🧾  Tác nghiệp QLKH"))
    if role == "Lãnh đạo phòng":
        options.append(("leader", "🗂️  Quản lý công việc"))

    if weekly_access_allowed(u):
        options.append(("weekly", "📅  Kế hoạch tuần"))

    options += [
        ("dashboard", "📊  Dashboard"),
        ("profile", "👤  Tài khoản"),
        ("guide", "📘  Hướng dẫn sử dụng"),
    ]
    if bool((u or {}).get("is_admin")):
        options.append(("admin", "⚙️  Quản trị"))

    values = [x[0] for x in options]
    current = base.st.session_state.get("main_page")
    if current not in values:
        current = values[0]
        base.st.session_state["main_page"] = current

    base.st.sidebar.markdown("#### Chức năng")
    for value, label in options:
        if base.st.sidebar.button(
            label,
            key=f"mainnav_{value}",
            use_container_width=True,
            type="primary" if current == value else "secondary",
        ):
            base.st.session_state["main_page"] = value
            base.st.rerun()
    return base.st.session_state.get("main_page", current)


def app():
    """Mirror the production KHDN_APP lifecycle, with Weekly Plan added to routing."""
    base.st.set_page_config(
        page_title=base.APP_TITLE,
        page_icon=str(base.APP_ICON_PNG_PATH),
        layout="wide",
        initial_sidebar_state="auto" if base.CLOUD_MODE else "expanded",
    )
    base.ensure_bidv_logo()
    base.inject_css()
    base._runtime_maintenance_once_per_session()
    base.device_login.sync(base.DB_PATH)

    if "user" not in base.st.session_state:
        base.login_ui()
        return

    fresh = base.user_by_username(base.st.session_state.user["username"])
    if not fresh:
        base.st.session_state.pop("user", None)
        base.st.rerun()

    base.st.session_state.user = dict(fresh)
    u = base.st.session_state.user
    if u.get("must_change_password"):
        base.force_password_change(u)
        return

    base.sidebar_user(u)
    base.realtime_refresh_watch(u)
    notice = base.st.session_state.pop("_auto_refresh_notice", None)
    if notice:
        base.st.toast(notice, icon="🔄")

    page = sidebar_navigation(u)
    if page == "support":
        base.support_page(u)
    elif page == "qlkh":
        base.qlkh_page(u)
    elif page == "leader":
        base.leader_page(u)
    elif page == "weekly":
        if not weekly_access_allowed(u):
            base.st.session_state["main_page"] = "dashboard"
            base.st.error("Bạn không có quyền truy cập Kế hoạch tuần.")
            base.dashboard_page(u)
        else:
            weekly_plan_page(u, base.get_conn, base.page_title, base.pill_nav)
    elif page == "dashboard":
        base.dashboard_page(u)
    elif page == "profile":
        base.profile_page(u)
    elif page == "guide":
        base.guide_page(u)
    elif page == "admin":
        base.admin_page(u)


if __name__ == "__main__":
    app()
