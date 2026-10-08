"""Final runtime hook for KHDN input performance and task-type ordering.

This module is deliberately installed after every planning/admin overlay.  It makes
all heavy admin/catalog drafts use the same submit-only browser-local input path as
fast task creation, disables the periodic whole-app refresh while users type, and
keeps the legacy visual layout.

It also groups the Task Type list by module for easier scanning:
Kế hoạch -> Tác nghiệp, then alphabetically by task name inside each module.
No business data is migrated or rewritten here.
"""
from __future__ import annotations

import re

from khdn_apps import customer_work as customer_core
from khdn_apps import customer_work_ui as customer_ui
from khdn_apps import mobile_admin_restore_perf_patch as mobile_admin
from khdn_apps import mobile_input_performance_patch as mobile_input
from khdn_apps import mobile_legacy_ui_perf_patch as legacy_ui
from khdn_apps import planning_ui_admin_hotfix as admin_hotfix
from khdn_apps import weekly_priority_policy_patch as policy
from khdn_apps import worktype_contact_card_patch as worktype

VERSION = "1.0.0"
_FLAG = "_APPWIDE_INPUT_PERFORMANCE_RUNTIME_VERSION"

_TASK_TYPE_QUERY_RE = re.compile(
    r"SELECT\s+id,name,module_scope,active,created_at,updated_at\s+"
    r"FROM\s+task_types\s+ORDER\s+BY\s+id\b",
    re.IGNORECASE,
)
_TASK_TYPE_SORTED_SQL = (
    "SELECT id,name,module_scope,active,created_at,updated_at FROM task_types "
    "ORDER BY CASE module_scope "
    "WHEN 'PLAN' THEN 0 WHEN 'OPS' THEN 1 ELSE 2 END, "
    "lower(trim(name)), id"
)


class _ExecuteProxy:
    """Delegate a SQLite connection while rewriting only the Task Type list query."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, *args, **kwargs):
        text = str(sql)
        if _TASK_TYPE_QUERY_RE.search(text):
            sql = _TASK_TYPE_QUERY_RE.sub(_TASK_TYPE_SORTED_SQL, text, count=1)
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _ContextProxy:
    """Preserve the original connection context manager/transaction semantics."""

    def __init__(self, inner):
        self._inner = inner

    def __enter__(self):
        return _ExecuteProxy(self._inner.__enter__())

    def __exit__(self, exc_type, exc, tb):
        return self._inner.__exit__(exc_type, exc, tb)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _install_task_type_scope_sort(app_ns, logger=None):
    """Rewire every final Task Type route to one scope-sorted renderer."""
    base_renderer = legacy_ui._render_system_task_types_legacy_fast
    if getattr(base_renderer, "_khdn_scope_sorted", False):
        return

    def sorted_renderer(ns, u, worktype_arg, logger=None):
        original_get_conn = ns["get_conn"]
        local_ns = dict(ns)

        def sorted_get_conn():
            return _ContextProxy(original_get_conn())

        local_ns["get_conn"] = sorted_get_conn
        return base_renderer(local_ns, u, worktype_arg, logger)

    sorted_renderer._khdn_scope_sorted = True
    sorted_renderer._khdn_base_renderer = base_renderer

    # admin_page from mobile_input resolves mobile_input._render_system_task_types_fast
    # at render time.  The direct System Admin route uses admin_hotfix.
    legacy_ui._render_system_task_types_legacy_fast = sorted_renderer
    mobile_input._render_system_task_types_fast = sorted_renderer
    mobile_admin._render_system_task_types_fast = sorted_renderer
    admin_hotfix._render_system_task_types = (
        lambda ns, u, worktype_arg, logger=None:
        sorted_renderer(ns, u, worktype_arg, logger)
    )

    log = logger or app_ns.get("LOGGER")
    if log:
        log.info(
            "TASK_TYPE_SCOPE_SORT_INSTALLED order=PLAN,OPS name=ASC renderer_routes=all"
        )


def install(app_ns, logger=None):
    """Install the performance stack last, immediately before app()."""
    if app_ns.get(_FLAG) == VERSION:
        return

    log = logger or app_ns.get("LOGGER")

    # Same no-keystroke path used by fast task entry:
    # - browser-local draft state, submit once;
    # - no 6-second whole-app refresh;
    # - fast User / Task Type / Stage / Focus forms.
    mobile_input.install(app_ns, policy, log)

    # Restore all System Admin destinations while retaining submit-only forms.
    mobile_admin.install(app_ns, policy, log)

    # Preserve the familiar catalog UI but move both Mục công việc and
    # Danh mục công việc quan trọng drafts into the submit-only local component.
    legacy_ui.install(
        app_ns, policy, customer_core, customer_ui, worktype, log
    )

    # Apply the requested module grouping after the final legacy renderer is bound.
    _install_task_type_scope_sort(app_ns, log)

    app_ns[_FLAG] = VERSION
    if log:
        log.info(
            "APPWIDE_INPUT_PERFORMANCE_RUNTIME_INSTALLED version=%s "
            "submit_only_users=1 submit_only_task_types=1 "
            "submit_only_stages=1 submit_only_important_categories=1 "
            "submit_only_focus=1 periodic_refresh=0 task_type_scope_sort=PLAN,OPS",
            VERSION,
        )
