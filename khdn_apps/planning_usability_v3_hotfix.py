"""Runtime hotfix for Planning Usability V3 child command navigation.

V4 is always installed first so the live Catalog route cannot fall back to the
legacy underline-tab renderer even when an older V3 hotfix marker is already set.
"""
from __future__ import annotations

from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_ui_admin_hotfix as ui_hotfix
from khdn_apps import planning_ui_v4_patch as v4

VERSION = "4.2.0"


def _bound_child_nav(st):
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
    app_logger = logger or ns.get("LOGGER")

    # IMPORTANT: install the final V4 live-route interception before consulting
    # the older V3 marker. This makes the fix version-aware and guarantees that
    # work_catalogs is routed through real Streamlit command buttons.
    v4.install(ns, customer_core, customer_ui, refinement, worktype, app_logger)

    if getattr(customer_ui, "_PLANNING_USABILITY_V3_HOTFIX_VERSION", None) == VERSION:
        return

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
        # Use the V4 hard command-button callback here as well; this keeps the
        # module-level renderer consistent if it is called directly elsewhere.
        return v2._render_catalog(
            st_arg,
            u,
            conn_fn,
            customer_core,
            customer_ui,
            v4._bound_nav(st_arg),
            page_title,
            logger or app_logger,
        )

    customer_ui.render_cases_page = render_cases_page
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui._PLANNING_USABILITY_V3_HOTFIX_INSTALLED = True
    customer_ui._PLANNING_USABILITY_V3_HOTFIX_VERSION = VERSION

    # Re-apply V4 after the renderer normalization. The version guard keeps this
    # cheap, while its dashboard/app-globals interception remains authoritative.
    v4.install(ns, customer_core, customer_ui, refinement, worktype, app_logger)

    if app_logger:
        app_logger.info(
            "PLANNING_USABILITY_V3_HOTFIX_INSTALLED version=%s final_catalog_route=1",
            VERSION,
        )
