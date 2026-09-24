"""Runtime integration for the Weekly Plan module.

The legacy app dispatcher does not know a `weekly_plan` route.  To keep the
production engine unchanged, this patch adds the sidebar choice and dispatches
it through the existing dashboard branch, while preserving the real Dashboard.
"""
from khdn_apps import weekly_plan


def install(ns):
    st=ns["st"]
    original_dashboard=ns["dashboard_page"]

    def sidebar_navigation(u):
        options=[]
        if u["role"]=="Cán bộ hỗ trợ": options.append(("support","🧾  Tác nghiệp"))
        if u["role"]=="Cán bộ QLKH": options.append(("qlkh","🧾  Tác nghiệp QLKH"))
        if u["role"]=="Lãnh đạo phòng": options.append(("leader","🗂️  Quản lý công việc"))
        options += [("weekly_plan","📅  Kế hoạch"),("dashboard","📊  Dashboard"),("profile","👤  Tài khoản"),("guide","📘  Hướng dẫn sử dụng")]
        if u["is_admin"]: options.append(("admin","⚙️  Quản trị"))
        values=[x[0] for x in options]
        current=st.session_state.get("main_page")
        if current not in values:
            current=values[0]; st.session_state["main_page"]=current
        st.sidebar.markdown("#### Chức năng")
        for value,label in options:
            if st.sidebar.button(label,key=f"mainnav_{value}",use_container_width=True,type="primary" if current==value else "secondary"):
                st.session_state["main_page"]=value; st.rerun()
        current=st.session_state.get("main_page",current)
        return "dashboard" if current=="weekly_plan" else current

    def dashboard_page(u):
        if st.session_state.get("main_page")=="weekly_plan":
            return weekly_plan.render_page(st,u,ns["get_conn"],page_title=ns.get("page_title"),logger=ns.get("LOGGER"))
        return original_dashboard(u)

    ns["sidebar_navigation"]=sidebar_navigation
    ns["dashboard_page"]=dashboard_page
    logger=ns.get("LOGGER")
    if logger: logger.info("WEEKLY_PLAN_PATCH_INSTALLED version=%s",weekly_plan.VERSION)
