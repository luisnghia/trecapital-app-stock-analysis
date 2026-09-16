"""KHDN Ops V2.31.1 – make Leader/Admin CBHT workload identical to QLKH.

V2.31 introduced a separate Leader/Admin workload renderer.  The QLKH screen
already has the preferred mobile layout, filters and stacked chart, so this
patch deliberately reuses that exact renderer instead of maintaining two UI
implementations.  If a non-production/offline build does not contain the QLKH
renderer, the V2.31 renderer remains as a safe fallback.
"""
from __future__ import annotations

import logging
from typing import Any

PATCH_VERSION = "2.31.1"
_INSTALL_FLAG = "_KHDN_LEADER_WORKLOAD_MATCH_QLKH_V2311"


def install(app_ns: dict[str, Any], workload_module: Any) -> None:
    if app_ns.get(_INSTALL_FLAG):
        return
    app_ns[_INSTALL_FLAG] = True

    original = workload_module._render_cbht_workload_today

    def _render_cbht_workload_today_identical_to_qlkh(ns: dict[str, Any]) -> None:
        renderer = ns.get("_render_qlkh_workload")
        if callable(renderer):
            # _render_qlkh_workload only uses role for the access guard; the
            # workload itself is whole-room aggregate data.  Passing a tiny
            # role proxy therefore renders the exact same expander/widgets/chart
            # on the Leader/Admin management screen without exposing QLKH detail.
            renderer({"role": "Cán bộ QLKH"})
            return

        logging.getLogger("khdn_ops").warning(
            "QLKH_WORKLOAD_RENDERER_MISSING fallback_to_v231"
        )
        original(ns)

    # The V2.31 page_title wrapper resolves this module global at call time, so
    # replacing it here changes only the Leader/Admin workload block and does not
    # duplicate the component.
    workload_module._render_cbht_workload_today = _render_cbht_workload_today_identical_to_qlkh
    app_ns["APP_VERSION"] = PATCH_VERSION
    logging.getLogger("khdn_ops").info(
        "PATCH_INSTALL version=%s leader_workload=qlkh_exact", PATCH_VERSION
    )
