"""Compatibility shim for Customer Work dispatcher keyword arguments.

The central dispatcher calls custom pages with ``st=...``.  The final UX patch
used the equivalent positional name ``st_arg`` which is valid positionally but
rejects the dispatcher keyword.  Keep the final renderer intact and expose the
canonical keyword signature expected by the app.
"""
from __future__ import annotations

VERSION = "1.0.0"


def install(customer_ui, logger=None):
    if getattr(customer_ui, "_CUSTOMER_WORK_SIGNATURE_FIX_INSTALLED", False):
        return

    original = customer_ui.render_cases_page

    def render_cases_page(st, u, get_conn, page_title=None, logger=None, **_kwargs):
        # Call positionally because the wrapped final renderer may name its first
        # parameter ``st_arg`` and its logger parameter ``logger_arg``.
        return original(st, u, get_conn, page_title, logger)

    customer_ui.render_cases_page = render_cases_page
    customer_ui._CUSTOMER_WORK_SIGNATURE_FIX_INSTALLED = True
    if logger:
        logger.info("CUSTOMER_WORK_SIGNATURE_FIX_INSTALLED version=%s", VERSION)
