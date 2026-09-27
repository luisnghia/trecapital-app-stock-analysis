"""Final hard patch for Planning child navigation and Customer Work owner role."""
from __future__ import annotations

from khdn_apps import planning_usability_v2_patch as v2

VERSION = "4.2.0"


def _escape_key(value):
    return "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(value))


def _button_css(st, key, active):
    root = f"div[class*='st-key-{_escape_key(key)}']"
    if active:
        body = "background:linear-gradient(135deg,#075C57 0%,#0F746B 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:2px solid #F4B41A!important;box-shadow:0 3px 0 #C7900D,0 5px 12px rgba(0,0,0,.20)!important;"
        text = "#FFFFFF"
    else:
        body = "background:#F3F1E3!important;color:#173B38!important;-webkit-text-fill-color:#173B38!important;border:1px solid #D8C77E!important;box-shadow:0 3px 0 #9AAE98!important;"
        text = "#173B38"
    st.markdown(
        f"""<style>
        {root} button{{{body}min-height:43px!important;height:43px!important;width:100%!important;padding:.42rem .65rem!important;border-radius:5px!important;font-size:.88rem!important;font-weight:900!important;line-height:1.16!important;white-space:normal!important;overflow-wrap:anywhere!important;}}
        {root} button *,{root} p{{color:{text}!important;-webkit-text-fill-color:{text}!important;font-weight:900!important;text-decoration:none!important;border-bottom:none!important;}}
        </style>""",
        unsafe_allow_html=True,
    )


def _hard_command_nav(st, state_key, options, default=None, prefix="subnav"):
    options = list(options or [])
    if not options:
        return None
    values = [v for v, _ in options]
    current = st.session_state.get(state_key)
    if current not in values:
        current = default if default in values else values[0]
        st.session_state[state_key] = current
    frame_key = f"cmdv4_frame_{_escape_key(prefix)}"
    st.markdown(
        f"""<style>
        div[class*='st-key-{frame_key}']{{margin:.10rem 0 1rem!important;padding:.42rem .48rem!important;border:1px solid rgba(218,190,99,.48)!important;border-radius:9px!important;background:rgba(244,241,223,.055)!important;box-shadow:0 7px 18px rgba(0,0,0,.10)!important;}}
        div[class*='st-key-{frame_key}'] [data-testid='stHorizontalBlock']{{gap:.42rem!important;align-items:stretch!important;}}
        </style>""",
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
                if st.button(str(label), key=button_key, use_container_width=True,
                             type="primary" if active else "secondary"):
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
            sql = sql.replace("u.full_name AS owner_name,", "u.full_name AS owner_name,u.role AS owner_role,")
        return sql
    customer_core._case_select_sql = case_select_sql
    customer_core._PLANNING_UI_V4_OWNER_ROLE_SQL = True


def install(ns, customer_core, customer_ui, refinement, worktype, logger=None):
    # Re-apply when this patch version changes; do not let an older runtime marker
    # suppress the final catalog route.
    if getattr(customer_ui, "_PLANNING_UI_V4_VERSION", None) == VERSION:
        return
    st = ns["st"]
    app_logger = logger or ns.get("LOGGER")
    _install_owner_role_select(customer_core)

    # Enrich the existing card without replacing its business rendering.
    if not getattr(customer_ui, "_PLANNING_UI_V4_OWNER_CARD", False):
        previous_card = customer_ui._case_card
        def case_card(st_arg, x, get_conn_arg, uid, manager, logger_arg=None, compact=False):
            x2 = dict(x)
            owner_name = str(x2.get("owner_name") or "—")
            owner_role = str(x2.get("owner_role") or "").strip()
            if owner_role and owner_role.casefold() not in owner_name.casefold():
                x2["owner_name"] = f"{owner_name} · {owner_role}"
            return previous_card(st_arg, x2, get_conn_arg, uid, manager, logger_arg or app_logger, compact)
        customer_ui._case_card = case_card
        customer_ui._PLANNING_UI_V4_OWNER_CARD = True

    def render_catalog_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return v2._render_catalog(
            st_arg, u, conn_fn, customer_core, customer_ui,
            _bound_nav(st_arg), page_title, logger or app_logger,
        )

    customer_ui.render_catalog_page = render_catalog_page

    # Intercept the live dashboard route. Also write through app.__globals__ in case
    # the production loader's app function resolves globals from a different dict.
    previous_dashboard = ns["dashboard_page"]
    def dashboard_page(u):
        if st.session_state.get("main_page") == "work_catalogs":
            return render_catalog_page(
                st=st, u=u, get_conn=ns["get_conn"],
                page_title=ns.get("page_title"), logger=app_logger,
            )
        return previous_dashboard(u)

    ns["dashboard_page"] = dashboard_page
    app_fn = ns.get("app")
    if callable(app_fn):
        app_fn.__globals__["dashboard_page"] = dashboard_page

    customer_ui._PLANNING_UI_V4_INSTALLED = True
    customer_ui._PLANNING_UI_V4_VERSION = VERSION
    if app_logger:
        app_logger.info("PLANNING_UI_V4_INSTALLED version=%s direct_catalog_route=1 owner_role=1", VERSION)
