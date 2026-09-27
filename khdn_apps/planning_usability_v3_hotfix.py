"""Final rerun-safe hotfix for Planning child command navigation.

Root cause fixed here:
``catalog_edit_state_patch.install`` is intentionally called on every Streamlit
rerun and reassigns ``customer_ui.render_catalog_page`` to its legacy ``st.tabs``
renderer.  Earlier V3/V4 installers are version-guarded, so after the first
interaction the legacy underline tabs could silently win again.

This hotfix therefore ALWAYS rebinds the final Customer Work/Catalog renderers on
every script run.  One-time V4 schema/card work stays guarded inside V4, while the
live renderer binding is deliberately rerun-safe.
"""
from __future__ import annotations

from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_ui_admin_hotfix as ui_hotfix
from khdn_apps import planning_ui_v4_patch as v4

VERSION = "4.3.0"


def _bound_child_nav(st):
    """Use the exact same command-button component as Customer Work."""
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

    # V4 owns one-time owner-role SQL/card enrichment and first-run route hardening.
    # Its own version guard makes repeated calls cheap and safe.
    v4.install(ns, customer_core, customer_ui, refinement, worktype, app_logger)

    # IMPORTANT: DO NOT RETURN EARLY HERE.
    # catalog_edit_state_patch runs before this installer on every Streamlit rerun
    # and can put render_catalog_page back to legacy st.tabs.  These bindings must
    # therefore be restored on every script execution, not only once per process.
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

    customer_ui.render_cases_page = render_cases_page
    customer_ui.render_catalog_page = render_catalog_page
    customer_ui._PLANNING_USABILITY_V3_HOTFIX_INSTALLED = True
    customer_ui._PLANNING_USABILITY_V3_HOTFIX_VERSION = VERSION

    # customer_work_patch is also reinstalled on reruns and its dashboard dispatcher
    # resolves customer_ui.render_catalog_page dynamically.  Rebinding the module
    # renderer here, after catalog_edit_state_patch, is therefore the authoritative
    # and rerun-safe fix; no extra dashboard wrapper is required.
    if app_logger:
        app_logger.info(
            "PLANNING_USABILITY_V3_HOTFIX_REBOUND version=%s catalog=command_buttons customer=command_buttons",
            VERSION,
        )
