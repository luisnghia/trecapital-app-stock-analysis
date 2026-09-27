"""Runtime hotfix for Planning Usability V3 child command navigation.

Fixes the V3 callback signature and then installs the V4 hard UI layer so Catalog
child navigation cannot fall back to the legacy underline-tab appearance.  V4
also exposes the executing officer role on Customer Work cards.
"""
from __future__ import annotations

from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_ui_admin_hotfix as ui_hotfix
from khdn_apps import planning_ui_v4_patch as v4

VERSION = "4.1.0"


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

    # First normalize V3 signatures.
    customer_ui.render_cases_page = render_cases_page
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui._PLANNING_USABILITY_V3_HOTFIX_INSTALLED = True

    # Then install the stronger final layer. It styles the individual child button
    # widget keys directly (immune to legacy global tab CSS), forces the live
    # work_catalogs dispatcher through that renderer, and enriches card owner role.
    v4.install(ns, customer_core, customer_ui, refinement, worktype, app_logger)

    if app_logger:
        app_logger.info("PLANNING_USABILITY_V3_HOTFIX_INSTALLED version=%s", VERSION)
