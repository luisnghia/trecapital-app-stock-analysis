"""Runtime integration for Customer Work Pipeline.

Navigation rule for every role:
  1) Sidebar exposes only the two primary business areas: Tác nghiệp / Kế hoạch.
  2) The active area's secondary screens are rendered as a horizontal command-tab
     bar at the top of the main content, inspired by Trecapital.
  3) Account/help/admin utilities stay collapsed at the bottom of the sidebar.

This keeps the sidebar quiet while all business destinations remain one click away.
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


def _ops_options(role,admin=False):
    if role=="Cán bộ hỗ trợ":
        return [("support","Tác nghiệp hồ sơ"),("dashboard","Dashboard tác nghiệp")]
    if role=="Cán bộ QLKH":
        return [("qlkh","Tác nghiệp QLKH"),("dashboard","Dashboard tác nghiệp")]
    if role=="Lãnh đạo phòng" or bool(admin):
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


def _render_command_tabs(st,section,current,options,role,admin):
    """Render level-2 navigation in the main canvas, not the sidebar.

    Native Streamlit buttons are intentionally used instead of HTML links so the
    navigation remains keyboard accessible and preserves session state. The
    surrounding keyed container lets us style the row like Trecapital without
    leaking the style into business-action buttons elsewhere in the app.
    """
    if not options:
        return

    st.markdown(
        """
        <style>
        /* Trecapital-style level-2 command tabs. Scoped to this navigation only. */
        div[class*="st-key-khdn_subnav_bar"]{
          margin:.10rem 0 1.00rem 0!important;
          padding:.42rem .48rem!important;
          border:1px solid rgba(218,190,99,.48)!important;
          border-radius:9px!important;
          background:rgba(244,241,223,.055)!important;
          box-shadow:0 7px 18px rgba(0,0,0,.10)!important;
        }
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stHorizontalBlock"]{
          gap:.42rem!important;
          align-items:stretch!important;
        }
        div[class*="st-key-khdn_subnav_bar"] [data-testid="column"]{
          min-width:0!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button{
          min-height:43px!important;
          height:100%!important;
          padding:.42rem .65rem!important;
          border-radius:5px!important;
          font-size:.88rem!important;
          font-weight:800!important;
          line-height:1.16!important;
          white-space:normal!important;
          overflow-wrap:anywhere!important;
          transition:transform .10s ease,box-shadow .10s ease,background .10s ease!important;
        }
        /* Inactive tabs: warm light tile, close to Trecapital's command strip. */
        div[class*="st-key-khdn_subnav_bar"] button[kind="secondary"],
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-secondary"]{
          background:#F3F1E3!important;
          color:#173B38!important;
          -webkit-text-fill-color:#173B38!important;
          border:1px solid #D8C77E!important;
          box-shadow:0 3px 0 #9AAE98!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button[kind="secondary"] *,
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-secondary"] *{
          color:#173B38!important;-webkit-text-fill-color:#173B38!important;font-weight:800!important;
        }
        /* Active tab: BIDV/Trecapital teal with the thin gold focus edge. */
        div[class*="st-key-khdn_subnav_bar"] button[kind="primary"],
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-primary"]{
          background:linear-gradient(135deg,#075C57 0%,#0F746B 100%)!important;
          color:#FFFFFF!important;
          -webkit-text-fill-color:#FFFFFF!important;
          border:2px solid #F4B41A!important;
          box-shadow:0 3px 0 #C7900D,0 5px 12px rgba(0,0,0,.20)!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button[kind="primary"] *,
        div[class*="st-key-khdn_subnav_bar"] [data-testid="stBaseButton-primary"] *{
          color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;font-weight:900!important;
        }
        div[class*="st-key-khdn_subnav_bar"] button:hover{
          transform:translateY(-1px)!important;
          filter:brightness(1.035)!important;
        }
        @media (max-width:900px){
          div[class*="st-key-khdn_subnav_bar"]{padding:.34rem!important;}
          div[class*="st-key-khdn_subnav_bar"] [data-testid="stHorizontalBlock"]{gap:.26rem!important;}
          div[class*="st-key-khdn_subnav_bar"] button{font-size:.72rem!important;padding:.34rem .30rem!important;min-height:42px!important;}
        }
        @media (max-width:620px){
          div[class*="st-key-khdn_subnav_bar"] button{font-size:.64rem!important;padding:.28rem .18rem!important;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Give long labels a little more horizontal space while preserving a single
    # compact row on desktop/iPad landscape.
    widths=[max(1.0,min(2.7,len(label)/11.0)) for _,label in options]
    with st.container(key="khdn_subnav_bar"):
        cols=st.columns(widths,gap="small")
        for idx,(col,(route,label)) in enumerate(zip(cols,options)):
            with col:
                if st.button(
                    label,
                    key=f"khdn_subtab_{section}_{role}_{int(bool(admin))}_{idx}_{route}",
                    use_container_width=True,
                    type="primary" if route==current else "secondary",
                ):
                    st.session_state["main_page"]=route
                    st.session_state["main_section"]=section
                    st.rerun()


def install(ns):
    st=ns["st"]
    previous_dashboard=ns["dashboard_page"]

    def sidebar_navigation(u):
        role=str(_uget(u,"role") or "")
        admin=bool(_uget(u,"is_admin"))
        uid=int(_uget(u,"id") or 0)
        ops_options=_ops_options(role,admin)
        plan_options=_plan_options(role,admin)
        ops_values=_route_values(ops_options)
        plan_values=_route_values(plan_options)
        plan_landing=_landing_for(role,admin)

        # Every fresh login lands in Kế hoạch as requested:
        # CB -> Hôm nay; Lãnh đạo/Admin -> Điều hành kế hoạch phòng.
        login_token=f"{uid}:{_uget(u,'last_login_at','')}"
        if st.session_state.get("cw_landing_token")!=login_token:
            st.session_state["cw_landing_token"]=login_token
            st.session_state["main_section"]="plan"
            st.session_state["main_page"]=plan_landing

        current=st.session_state.get("main_page",plan_landing)
        section=st.session_state.get("main_section","plan")

        # Keep the primary section synchronized with an existing route. Utility
        # pages preserve the most recently selected business section.
        if current in ops_values or current=="dashboard":
            section="ops"
        elif current in plan_values or current in PLAN_PAGES:
            section="plan"
        st.session_state["main_section"]=section

        # Sidebar: exactly two business-area buttons for every role.
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

        st.sidebar.divider()
        with st.sidebar.expander("⋯  Tiện ích",expanded=False):
            if st.button("👤 Tài khoản",key="cwutil_profile",use_container_width=True):
                st.session_state["main_page"]="profile";st.rerun()
            if st.button("📘 Hướng dẫn sử dụng",key="cwutil_guide",use_container_width=True):
                st.session_state["main_page"]="guide";st.rerun()
            if admin and st.button("🛠️ Quản trị hệ thống",key="cwutil_admin",use_container_width=True):
                st.session_state["main_page"]="admin";st.rerun()

        # Main canvas: level-2 navigation is a visible command-tab strip, not a
        # selectbox/dropdown. It is rendered before the selected page content, so
        # it works for both legacy Tác nghiệp pages and new Kế hoạch pages.
        current=st.session_state.get("main_page",current)
        section=st.session_state.get("main_section",section)
        if current not in UTILITY_PAGES:
            choices=ops_options if section=="ops" else plan_options
            values=_route_values(choices)
            if current not in values:
                current=values[0] if section=="ops" else plan_landing
                st.session_state["main_page"]=current
            _render_command_tabs(st,section,current,choices,role,admin)

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
    if logger: logger.info("CUSTOMER_WORK_PATCH_INSTALLED core=%s ui=%s nav=two-sections-top-tabs",customer_work.VERSION,customer_work_ui.VERSION)
