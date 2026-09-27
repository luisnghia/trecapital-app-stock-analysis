"""Runtime hotfix for Planning Usability V3 child command navigation.

Fixes a signature mismatch introduced by V3: the V2 page renderers call their
``pill_nav`` callback as ``pill_nav(state_key, options, ...)`` while V3 passed a
function whose first argument was ``st``.  The mismatch caused Customer Work to
crash and prevented the Catalog child tabs from using the requested command-tab
visual language.

This hotfix binds the active Streamlit object in a closure and then delegates to
the exact command-tab renderer used by the planning navigation theme.
"""
from __future__ import annotations

from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_ui_admin_hotfix as ui_hotfix

VERSION = "4.0.1"


def _bound_child_nav(st):
    """Return the callback signature expected by V2, with ``st`` already bound."""

    def nav(state_key, options, default=None, prefix="subnav"):
        return ui_hotfix._local_command_tabs(
            st,
            state_key,
            options,
            default=default,
            prefix=prefix,
        )

    return nav


def install(ns, customer_core, customer_ui, refinement, worktype, logger=None):
    if getattr(customer_ui, "_PLANNING_USABILITY_V3_HOTFIX_INSTALLED", False):
        return

    app_logger = logger or ns.get("LOGGER")

    def render_cases_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return v2._render_cases_page(
            st_arg,
            u,
            conn_fn,
            customer_core,
            customer_ui,
            refinement,
            worktype,
            _bound_child_nav(st_arg),
            page_title,
            logger or app_logger,
        )

    def render_catalog_page(st=None, u=None, get_conn=None, page_title=None, logger=None, **kwargs):
        st_arg = st or ns["st"]
        conn_fn = get_conn or ns["get_conn"]
        return v2._render_catalog(
            st_arg,
            u,
            conn_fn,
            customer_core,
            customer_ui,
            _bound_child_nav(st_arg),
            page_title,
            logger or app_logger,
        )

    # Install last so the live dispatcher always resolves these fixed renderers.
    customer_ui.render_cases_page = render_cases_page
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui._PLANNING_USABILITY_V3_HOTFIX_INSTALLED = True

    if app_logger:
        app_logger.info("PLANNING_USABILITY_V3_HOTFIX_INSTALLED version=%s", VERSION)
