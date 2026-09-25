"""Runtime integration for Customer Work Pipeline.

The app has exactly two primary business areas for every role:
  1) Tác nghiệp
  2) Kế hoạch

Secondary screens are intentionally hidden inside one compact selector for the
active area. Account/help/admin utilities are collapsed at the bottom of the
sidebar so they do not compete with the two core business areas.
"""
from khdn_apps import customer_work
from khdn_apps import customer_work_ui


CUSTOM_PAGES={"work_today","customer_work","work_dashboard","work_approvals","work_catalogs"}
PLAN_PAGES=CUSTOM_PAGES|{"weekly_plan"}
UTILITY_PAGES={"profile","guide","admin"}


def _uget(u,key,default=None):
    try:
        return u.get(key,default)
    except Exception:
        try:return u[key]
        except Exception:return default


def _ops_options(role):
    if role=="Cán bộ hỗ trợ":
        return [("support","Tác nghiệp hồ sơ"),("dashboard","Dashboard tác nghiệp")]
    if role=="Cán bộ QLKH":
        return [("qlkh","Tác nghiệp QLKH"),("dashboard","Dashboard tác nghiệp")]
    if role=="Lãnh đạo phòng":
        return [("leader","Quản lý tác nghiệp"),("dashboard","Dashboard tác nghiệp")]
    # Defensive fallback for any future role: never expose a broken route.
    return [("dashboard","Dashboard tác nghiệp")]


def _plan_options(role,admin):
    manager=role=="Lãnh đạo phòng" or bool(admin)
    if manager:
        return [
            ("work_dashboard","Điều hành kế hoạch phòng"),
            ("work_approvals","Phê duyệt kế hoạch / dời hạn"),
            ("customer_work","Công việc khách hàng"),
            ("weekly_plan","Kế hoạch tuần"),
            ("work_catalogs","Danh mục quy trình & ưu tiên"),
        ]
    return [
        ("work_today","Công việc hôm nay"),
        ("customer_work","Công việc khách hàng"),
        ("weekly_plan","Kế hoạch tuần"),
    ]


def _landing_for(role,admin):
    return "work_dashboard" if role=="Lãnh đạo phòng" or bool(admin) else "work_today"


def _route_values(options):
    return [v for v,_ in options]


def install(ns):
    st=ns["st"]
    previous_dashboard=ns["dashboard_page"]

    def sidebar_navigation(u):
        role=str(_uget(u,"role") or "")
        admin=bool(_uget(u,"is_admin"))
        uid=int(_uget(u,"id") or 0)
        ops_options=_ops_options(role)
        plan_options=_plan_options(role,admin)
        ops_values=_route_values(ops_options)
        plan_values=_route_values(plan_options)
        plan_landing=_landing_for(role,admin)

        # Every fresh login lands in Kế hoạch as previously requested:
        # CB -> Hôm nay; Lãnh đạo/Admin -> Điều hành phòng.
        login_token=f"{uid}:{_uget(u,'last_login_at','')}"
        if st.session_state.get("cw_landing_token")!=login_token:
            st.session_state["cw_landing_token"]=login_token
            st.session_state["main_section"]="plan"
            st.session_state["main_page"]=plan_landing

        current=st.session_state.get("main_page",plan_landing)
        section=st.session_state.get("main_section","plan")

        # Keep the section in sync when an existing deep link/session points to a
        # known business page. Utility pages intentionally preserve last section.
        if current in ops_values or current=="dashboard":
            section="ops"
        elif current in plan_values or current in PLAN_PAGES:
            section="plan"
        st.session_state["main_section"]=section

        st.sidebar.markdown("#### Chức năng chính")
        if st.sidebar.button(
            "🧾  TÁC NGHIỆP",
            key="mainsection_ops",
            use_container_width=True,
            type="primary" if section=="ops" else "secondary",
        ):
            st.session_state["main_section"]="ops"
            st.session_state["main_page"]=ops_values[0]
            st.rerun()

        if st.sidebar.button(
            "📅  KẾ HOẠCH",
            key="mainsection_plan",
            use_container_width=True,
            type="primary" if section=="plan" else "secondary",
        ):
            st.session_state["main_section"]="plan"
            st.session_state["main_page"]=plan_landing
            st.rerun()

        # Only one compact level-2 selector is visible at a time. This replaces
        # the previous 8-10 stacked sidebar buttons.
        section=st.session_state.get("main_section",section)
        current=st.session_state.get("main_page",current)
        if section=="ops":
            choices=ops_options
            values=ops_values
            if current not in values:
                current=values[0]
                st.session_state["main_page"]=current
            labels=dict(choices)
            selected=st.sidebar.selectbox(
                "Trong Tác nghiệp",
                values,
                index=values.index(current),
                format_func=lambda v: labels[v],
                key=f"cw_ops_selector_{role}",
            )
        else:
            choices=plan_options
            values=plan_values
            if current not in values:
                current=plan_landing
                st.session_state["main_page"]=current
            labels=dict(choices)
            selected=st.sidebar.selectbox(
                "Trong Kế hoạch",
                values,
                index=values.index(current),
                format_func=lambda v: labels[v],
                key=f"cw_plan_selector_{role}_{int(admin)}",
            )
        if selected!=st.session_state.get("main_page"):
            st.session_state["main_page"]=selected
            st.rerun()

        st.sidebar.divider()
        with st.sidebar.expander("⋯  Tiện ích",expanded=False):
            if st.button("👤 Tài khoản",key="cwutil_profile",use_container_width=True):
                st.session_state["main_page"]="profile";st.rerun()
            if st.button("📘 Hướng dẫn sử dụng",key="cwutil_guide",use_container_width=True):
                st.session_state["main_page"]="guide";st.rerun()
            if admin and st.button("🛠️ Quản trị hệ thống",key="cwutil_admin",use_container_width=True):
                st.session_state["main_page"]="admin";st.rerun()

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
    # init_db(); each Customer Work page calls ensure_schema only after login.
    ns["sidebar_navigation"]=sidebar_navigation
    ns["dashboard_page"]=dashboard_page
    logger=ns.get("LOGGER")
    if logger: logger.info("CUSTOMER_WORK_PATCH_INSTALLED core=%s ui=%s nav=two-sections",customer_work.VERSION,customer_work_ui.VERSION)
