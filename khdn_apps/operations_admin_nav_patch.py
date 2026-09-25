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
        # The Admin-only utility is the system scope. The operational tab uses a
        # different synthetic route and therefore cannot accidentally inherit it.
        if st.session_state.get("main_page")=="admin":
            st.session_state["admin_scope"]="system"
        return original_sidebar(u)

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
        return original_dashboard(u)

    ns["sidebar_navigation"]=sidebar_navigation
    ns["dashboard_page"]=dashboard_page
    nav_module._OPS_ADMIN_NAV_INSTALLED=True
    logger=ns.get("LOGGER")
    if logger:
        logger.info("OPS_ADMIN_NAV_PATCH_INSTALLED route=ops_admin")
