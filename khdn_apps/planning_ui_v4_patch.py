"""Planning UI V4 final runtime patch.

Goals:
- force Catalog child navigation to render as actual BIDV/Trecapital command buttons,
  never as the legacy underline/tab control;
- keep the final dispatcher routed through that renderer;
- expose the current work owner's role in Customer Work cards so leaders can see
  whether the person doing the work is CBQLKH or CBHT.
"""
from __future__ import annotations

from khdn_apps import planning_usability_v2_patch as v2

VERSION = "4.1.0"


def _escape_key(value):
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(value))


def _button_css(st, key, active):
    # Style the widget key itself instead of relying on a parent container class.
    # This is intentionally stronger than the previous child-tab CSS because the
    # app has legacy global rules that can make secondary buttons look like tabs.
    root = f"div[class*='st-key-{_escape_key(key)}']"
    if active:
        body = """
          background:linear-gradient(135deg,#075C57 0%,#0F746B 100%)!important;
          color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
          border:2px solid #F4B41A!important;
          box-shadow:0 3px 0 #C7900D,0 5px 12px rgba(0,0,0,.20)!important;
        """
        text = "#FFFFFF"
    else:
        body = """
          background:#F3F1E3!important;
          color:#173B38!important;-webkit-text-fill-color:#173B38!important;
          border:1px solid #D8C77E!important;
          box-shadow:0 3px 0 #9AAE98!important;
        """
        text = "#173B38"
    st.markdown(
        f"""
        <style>
        {root} button{{
          {body}
          min-height:43px!important;height:43px!important;width:100%!important;
          padding:.42rem .65rem!important;border-radius:5px!important;
          font-size:.88rem!important;font-weight:900!important;line-height:1.16!important;
          white-space:normal!important;overflow-wrap:anywhere!important;
          transition:transform .10s ease,box-shadow .10s ease,filter .10s ease!important;
        }}
        {root} button *, {root} p{{
          color:{text}!important;-webkit-text-fill-color:{text}!important;font-weight:900!important;
          text-decoration:none!important;border-bottom:none!important;
        }}
        {root} button:hover{{transform:translateY(-1px)!important;filter:brightness(1.035)!important;}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hard_command_nav(st, state_key, options, default=None, prefix="subnav"):
    """Render child navigation as true command buttons with per-widget CSS."""
    options = list(options or [])
    if not options:
        return None
    values = [v for v, _ in options]
    current = st.session_state.get(state_key)
    if current not in values:
        current = default if default in values else values[0]
        st.session_state[state_key] = current

    # Visible frame matches the main Kế hoạch command strip.
    frame_key = f"cmdv4_frame_{_escape_key(prefix)}"
    st.markdown(
        f"""
        <style>
        div[class*='st-key-{frame_key}']{{
          margin:.10rem 0 1.00rem 0!important;padding:.42rem .48rem!important;
          border:1px solid rgba(218,190,99,.48)!important;border-radius:9px!important;
          background:rgba(244,241,223,.055)!important;box-shadow:0 7px 18px rgba(0,0,0,.10)!important;
        }}
        div[class*='st-key-{frame_key}'] [data-testid='stHorizontalBlock']{{gap:.42rem!important;align-items:stretch!important;}}
        @media(max-width:900px){{div[class*='st-key-{frame_key}']{{padding:.34rem!important;}}}}
        </style>
        """,
        unsafe_allow_html=True,
    )
    widths = [max(1.0, min(2.7, len(str(label)) / 11.0)) for _, label in options]
    with st.container(key=frame_key):
        cols = st.columns(widths, gap="small")
        for idx, (col, (value, label)) in enumerate(zip(cols, options)):
            button_key = f"cmdv4_{_escape_key(prefix)}_{idx}_{_escape_key(value)}"
            active = value == current
            _button_css(st, button_key, active)
            with col:
                if st.button(
                    str(label),
                    key=button_key,
                    use_container_width=True,
                    type="primary" if active else "secondary",
                ):
                    st.session_state[state_key] = value
                    st.rerun()
    return current


def _bound_nav(st):
    def nav(state_key, options, default=None, prefix="subnav"):
        return _hard_command_nav(st, state_key, options, default=default, prefix=prefix)
    return nav


def _install_owner_role_select(customer_core):
    if getattr(customer_core, "_PLANNING_UI_V4_OWNER_ROLE_SQL", False):
        return
    original = customer_core._case_select_sql

    def case_select_sql():
        sql = original()
        if "owner_role" not in sql:
            sql = sql.replace(
                "u.full_name AS owner_name,",
                "u.full_name AS owner_name,u.role AS owner_role,",
            )
        return sql

    customer_core._case_select_sql = case_select_sql
    customer_core._PLANNING_UI_V4_OWNER_ROLE_SQL = True


def install(ns, customer_core, customer_ui, refinement, worktype, logger=None):
    if getattr(customer_ui, "_PLANNING_UI_V4_INSTALLED", False):
        return
    st = ns["st"]
    app_logger = logger or ns.get("LOGGER")
    _install_owner_role_select(customer_core)

    # Preserve the existing V3 card and enrich only the owner text shown to leaders.
    previous_card = customer_ui._case_card

    def case_card(st_arg, x, get_conn_arg, uid, manager, logger_arg=None, compact=False):
        x2 = dict(x)
        owner_name = str(x2.get("owner_name") or "—")
        owner_role = str(x2.get("owner_role") or "").strip()
        if owner_role and owner_role.casefold() not in owner_name.casefold():
            x2["owner_name"] = f"{owner_name} · {owner_role}"
        return previous_card(
            st_arg, x2, get_conn_arg, uid, manager, logger_arg or app_logger, compact
        )

    customer_ui._case_card = case_card

    def render_catalog_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return v2._render_catalog(
            st_arg,
            u,
            conn_fn,
            customer_core,
            customer_ui,
            _bound_nav(st_arg),
            page_title,
            logger or app_logger,
        )

    customer_ui.render_catalog_page = render_catalog_page

    # Force the live app dispatcher through the V4 Catalog renderer. This avoids
    # any earlier patch that captured a legacy render_catalog_page reference.
    previous_dashboard = ns["dashboard_page"]

    def dashboard_page(u):
        if st.session_state.get("main_page") == "work_catalogs":
            return render_catalog_page(
                st=st,
                u=u,
                get_conn=ns["get_conn"],
                page_title=ns.get("page_title"),
                logger=app_logger,
            )
        return previous_dashboard(u)

    ns["dashboard_page"] = dashboard_page
    customer_ui._PLANNING_UI_V4_INSTALLED = True
    if app_logger:
        app_logger.info("PLANNING_UI_V4_INSTALLED version=%s", VERSION)
