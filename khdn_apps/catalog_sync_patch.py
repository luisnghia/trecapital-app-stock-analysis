"""KHDN Ops V2.31.6 - synchronize Admin catalogs with operational users.

Root cause addressed:
- Task types are read through a cached helper.
- CBHT/CBQLKH realtime refresh watches task rows only, so a catalog-only change made
  by Admin/Leader does not force existing operational sessions to rerun.
- Reason categories are queried live when rendered, but without a catalog-triggered
  rerun an already-open operational screen can still keep the old options until some
  unrelated interaction occurs.

This runtime patch makes the tiny master-data catalogs authoritative directly from
SQLite and appends a deterministic catalog revision to the realtime change token.
Any create/rename/activate/deactivate of task types or reason categories therefore
refreshes open CBHT/CBQLKH sessions automatically on the normal polling cycle.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

PATCH_VERSION = "2.31.6"
_INSTALL_FLAG = "_KHDN_CATALOG_SYNC_V2316"


def _catalog_rows(ns: dict[str, Any], table: str) -> list[dict[str, Any]]:
    if table == "task_types":
        sql = "SELECT id,name,active,updated_at FROM task_types ORDER BY id"
    elif table == "reason_categories":
        sql = "SELECT id,reason_type,name,active,updated_at FROM reason_categories ORDER BY id"
    else:
        raise ValueError(table)
    try:
        with ns["get_conn"]() as c:
            rows = c.execute(sql).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        # During a very early bootstrap the reason table may not exist yet. Do not
        # prevent app startup; init_db() will create it before operational pages run.
        return []


def catalog_revision(ns: dict[str, Any]) -> str:
    """Content digest for both master catalogs, independent of timestamp precision."""
    payload = {
        "task_types": _catalog_rows(ns, "task_types"),
        "reason_categories": _catalog_rows(ns, "reason_categories"),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _active_task_types_live(ns: dict[str, Any]):
    # The catalog is tiny; a direct read is safer than retaining a cross-session
    # st.cache_data value for an operational dropdown.
    return ns["qdf"](
        "SELECT name,sla_hours FROM task_types WHERE active=1 ORDER BY id"
    ).copy()


def _active_reason_categories_live(ns: dict[str, Any], reason_type):
    kind = str(reason_type or "").upper().strip()
    if kind not in {"RETURN", "CANCEL"}:
        # Preserve the expected dataframe columns without requiring pandas import.
        return ns["qdf"]("SELECT id,name FROM reason_categories WHERE 1=0")
    return ns["qdf"](
        "SELECT id,name FROM reason_categories WHERE reason_type=? AND active=1 ORDER BY id",
        (kind,),
    ).copy()


def install(ns: dict[str, Any]) -> None:
    if ns.get(_INSTALL_FLAG):
        return
    ns[_INSTALL_FLAG] = True

    # Always read active task types from the database currently used by the app.
    ns["active_task_types"] = lambda: _active_task_types_live(ns)

    # Reason-categories support is introduced by the build-time reason patch. If it
    # exists, replace it with the same direct-database rule.
    if "active_reason_categories" in ns:
        ns["active_reason_categories"] = lambda reason_type: _active_reason_categories_live(ns, reason_type)

    # Existing realtime polling is task-based. Extend the token rather than adding
    # a second timer/fragment, so current performance characteristics are preserved.
    original_visible_token = ns.get("_visible_task_change_token")
    if callable(original_visible_token):
        def visible_task_and_catalog_change_token(user):
            task_token = original_visible_token(user)
            return f"{task_token}|catalog:{catalog_revision(ns)}"
        ns["_visible_task_change_token"] = visible_task_and_catalog_change_token

    ns["APP_VERSION"] = PATCH_VERSION
    logging.getLogger("khdn_ops").info(
        "PATCH_INSTALL version=%s catalog_sync=task_types+reason_categories realtime_revision",
        PATCH_VERSION,
    )
