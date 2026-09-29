"""Retire the separate Tác nghiệp > Quản trị route.

Operational administration has moved into Admin-only Quản trị hệ thống. This
runtime patch keeps stale sessions safe without exposing the old route.
"""
from __future__ import annotations


def install(nav_module, ns):
    st=ns["st"]
    if getattr(nav_module,"_OPS_ADMIN_NAV_INSTALLED",False):
        return

    original_ops_options=nav_module._ops_options

    def _ops_options(role,admin=False):
        return [(route,label) for route,label in original_ops_options(role,admin) if route!="ops_admin"]

    nav_module._ops_options=_ops_options
    try:
        nav_module.CUSTOM_PAGES.discard("ops_admin")
    except Exception:
        pass

    original_sidebar=ns["sidebar_navigation"]
    def sidebar_navigation(u):
        if st.session_state.get("main_page")=="ops_admin":
            if bool(u["is_admin"]):
                st.session_state["main_page"]="admin"
                st.session_state["admin_scope"]="system"
            else:
                st.session_state["main_section"]="plan"
                st.session_state["main_page"]="work_dashboard" if str(u["role"])=="Lãnh đạo phòng" else "work_today"
        if st.session_state.get("main_page")=="admin":
            st.session_state["admin_scope"]="system"
        return original_sidebar(u)

    original_dashboard=ns["dashboard_page"]
    def dashboard_page(u):
        if st.session_state.get("main_page")=="ops_admin":
            if not bool(u["is_admin"]):
                st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")
                return
            st.session_state["main_page"]="admin"
            st.session_state["admin_scope"]="system"
            return ns["admin_page"](u)
        if st.session_state.get("main_page")=="admin":
            st.session_state["admin_scope"]="system"
        return original_dashboard(u)

    ns["sidebar_navigation"]=sidebar_navigation
    ns["dashboard_page"]=dashboard_page
    nav_module._OPS_ADMIN_NAV_INSTALLED=True
    logger=ns.get("LOGGER")
    if logger:
        logger.info("OPS_ADMIN_NAV_PATCH_INSTALLED legacy_route_retired=1 system_admin_only=1")
