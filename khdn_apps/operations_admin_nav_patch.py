"""Move operational administration under Tác nghiệp without changing rights."""
from __future__ import annotations


def install(nav_module, ns):
    st=ns["st"]
    if getattr(nav_module,"_OPS_ADMIN_NAV_INSTALLED",False):
        return

    original_ops_options=nav_module._ops_options

    def _ops_options(role,admin=False):
        options=list(original_ops_options(role,admin))
        if role=="Lãnh đạo phòng" or bool(admin):
            if not any(route=="ops_admin" for route,_ in options):
                options.append(("ops_admin","Quản trị"))
        return options

    nav_module._ops_options=_ops_options
    nav_module.CUSTOM_PAGES.add("ops_admin")

    original_sidebar=ns["sidebar_navigation"]
    def sidebar_navigation(u):
        # `Quản trị hệ thống` and `Tác nghiệp > Quản trị` deliberately share the
        # legacy admin_page renderer but MUST NOT share scope. Streamlit's
        # st.rerun() interrupts the current render immediately after a button
        # click, so resetting scope only before original_sidebar() is not enough:
        # if the user clicks System Admin while currently in ops_admin, the old
        # `ops` scope can survive into the next render. The finally block runs
        # even when Streamlit raises its internal rerun exception and therefore
        # guarantees route=admin => scope=system.
        if st.session_state.get("main_page")=="admin":
            st.session_state["admin_scope"]="system"
        try:
            return original_sidebar(u)
        finally:
            if st.session_state.get("main_page")=="admin":
                st.session_state["admin_scope"]="system"

    original_dashboard=ns["dashboard_page"]
    def dashboard_page(u):
        if st.session_state.get("main_page")=="ops_admin":
            role=str(u["role"])
            admin=bool(u["is_admin"])
            if role!="Lãnh đạo phòng" and not admin:
                st.error("Bạn không có quyền quản trị tác nghiệp.")
                return
            st.session_state["admin_scope"]="ops"
            return ns["admin_page"](u)
        if st.session_state.get("main_page")=="admin":
            # Defense in depth: direct/legacy navigation to the system route must
            # always render Người dùng + Khách hàng CIF, regardless of previous
            # session state from operational administration.
            st.session_state["admin_scope"]="system"
        return original_dashboard(u)

    ns["sidebar_navigation"]=sidebar_navigation
    ns["dashboard_page"]=dashboard_page
    nav_module._OPS_ADMIN_NAV_INSTALLED=True
    logger=ns.get("LOGGER")
    if logger:
        logger.info("OPS_ADMIN_NAV_PATCH_INSTALLED route=ops_admin system_route=admin")
