"""Runtime integration for Customer Work Pipeline.

Adds role-specific landing pages without changing the legacy dispatcher.
Custom pages are routed through the existing dashboard slot, preserving all
legacy operational pages and the Weekly Plan module.
"""
from khdn_apps import customer_work
from khdn_apps import customer_work_ui


CUSTOM_PAGES={"work_today","customer_work","work_dashboard","work_approvals","work_catalogs"}


def _uget(u,key,default=None):
    try:
        return u.get(key,default)
    except Exception:
        try:return u[key]
        except Exception:return default


def install(ns):
    st=ns["st"]
    previous_dashboard=ns["dashboard_page"]

    def sidebar_navigation(u):
        role=str(_uget(u,"role") or "")
        admin=bool(_uget(u,"is_admin"))
        manager=role=="Lãnh đạo phòng" or admin
        uid=int(_uget(u,"id") or 0)
        if manager:
            options=[
                ("work_dashboard","📊  Điều hành phòng"),
                ("work_approvals","✅  Phê duyệt"),
                ("customer_work","👥  Công việc khách hàng"),
                ("weekly_plan","📅  Kế hoạch"),
            ]
            if role=="Lãnh đạo phòng": options.append(("leader","🗂️  Quản lý công việc"))
            options += [("work_catalogs","⚙️  Danh mục quy trình"),("dashboard","📈  Dashboard tác nghiệp"),("profile","👤  Tài khoản"),("guide","📘  Hướng dẫn sử dụng")]
            if admin: options.append(("admin","🛠️  Quản trị hệ thống"))
            landing="work_dashboard"
        else:
            options=[("work_today","🏠  Hôm nay"),("customer_work","👥  Công việc khách hàng")]
            if role=="Cán bộ hỗ trợ": options.append(("support","🧾  Tác nghiệp"))
            if role=="Cán bộ QLKH": options.append(("qlkh","🧾  Tác nghiệp QLKH"))
            options += [("weekly_plan","📅  Kế hoạch"),("dashboard","📊  Dashboard"),("profile","👤  Tài khoản"),("guide","📘  Hướng dẫn sử dụng")]
            landing="work_today"

        values=[v for v,_ in options]
        login_token=f"{uid}:{_uget(u,'last_login_at','')}"
        if st.session_state.get("cw_landing_token")!=login_token:
            st.session_state["cw_landing_token"]=login_token
            st.session_state["main_page"]=landing
        current=st.session_state.get("main_page")
        if current not in values:
            current=landing;st.session_state["main_page"]=current
        st.sidebar.markdown("#### Chức năng")
        for value,label in options:
            if st.sidebar.button(label,key=f"mainnav_{value}",use_container_width=True,type="primary" if current==value else "secondary"):
                st.session_state["main_page"]=value;st.rerun()
        current=st.session_state.get("main_page",current)
        return "dashboard" if current in CUSTOM_PAGES or current=="weekly_plan" else current

    def dashboard_page(u):
        page=st.session_state.get("main_page")
        kwargs=dict(st=st,u=u,get_conn=ns["get_conn"],page_title=ns.get("page_title"),logger=ns.get("LOGGER"))
        if page=="work_today": return customer_work_ui.render_today_page(**kwargs)
        if page=="customer_work": return customer_work_ui.render_cases_page(**kwargs)
        if page=="work_dashboard": return customer_work_ui.render_leader_dashboard(**kwargs)
        if page=="work_approvals": return customer_work_ui.render_approvals_page(**kwargs)
        if page=="work_catalogs": return customer_work_ui.render_catalog_page(**kwargs)
        return previous_dashboard(u)

    # Do not touch the database during patch installation. The legacy app owns
    # init_db(); each Customer Work page calls ensure_schema only after login,
    # when users/customers already exist. This also keeps runtime_page_qa clean.
    ns["sidebar_navigation"]=sidebar_navigation
    ns["dashboard_page"]=dashboard_page
    logger=ns.get("LOGGER")
    if logger: logger.info("CUSTOMER_WORK_PATCH_INSTALLED core=%s ui=%s",customer_work.VERSION,customer_work_ui.VERSION)
