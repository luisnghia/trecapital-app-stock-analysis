"""Standalone online entrypoint for KHDN Ops.
Use this entrypoint on Railway/Render; the Trecapital embedded page continues to use pages/KHDNApps.py.
"""
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("KHDN_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("KHDN_CLOUD_MODE", "1")
os.environ.setdefault("KHDN_DB_PATH", str(DATA_DIR / "khdn_ops.db"))

import khdn_apps.app as _app_module
import khdn_apps.cbht_workload_patch as _workload_patch_module
import khdn_apps.full_task_edit_patch as _full_task_edit_module
import khdn_apps.weekly_plan as _weekly_plan_module
import khdn_apps.weekly_plan_ui as _weekly_plan_ui_module
import khdn_apps.customer_work as _customer_work_module
import khdn_apps.customer_work_patch as _customer_work_patch_module
import khdn_apps.customer_work_ui as _customer_work_ui_module
from khdn_apps.cbht_workload_patch import install as _install_v231
from khdn_apps.leader_workload_match_patch import install as _install_v2311
from khdn_apps.amount_decimal_patch import install as _install_v2312
from khdn_apps.full_task_edit_patch import install as _install_v2313
from khdn_apps.direct_task_edit_button_patch import install as _install_v2314
from khdn_apps.catalog_sync_patch import install as _install_v2316
from khdn_apps.notification_ui_patch import install as _install_v2320
from khdn_apps.weekly_plan_governance_patch import install as _install_weekly_governance
from khdn_apps.weekly_plan_patch import install as _install_weekly_plan
from khdn_apps.customer_work_patch import install as _install_customer_work
from khdn_apps.operations_admin_nav_patch import install as _install_ops_admin_nav
from khdn_apps.priority_today_patch import install as _install_priority_today
from khdn_apps.potential_customer_patch import install as _install_potential_customer, _label as _potential_customer_label
from khdn_apps.planning_priority_patch import install as _install_planning_priority_v2
from khdn_apps.priority_workflow_patch import install as _install_priority_workflow_bridge
from khdn_apps.catalog_edit_state_patch import install as _install_catalog_edit_state_fix

_install_v231(_app_module.__dict__)
_install_v2311(_app_module.__dict__, _workload_patch_module)
_install_v2312(_app_module.__dict__)
_install_v2313(_app_module.__dict__)
_install_v2314(_app_module.__dict__, _full_task_edit_module)
_install_v2316(_app_module.__dict__)
_install_v2320(_app_module.__dict__)
_install_weekly_governance(_weekly_plan_module, _app_module.__dict__.get("LOGGER"))
# Install before Weekly Plan/Customer Work navigation. Priority Today captures the
# prospect-aware customer-work create form installed here.
_install_potential_customer(
    _app_module.__dict__,
    _customer_work_module,
    _customer_work_ui_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
_weekly_plan_ui_module._customer_label = _potential_customer_label
_install_weekly_plan(_app_module.__dict__)
_install_customer_work(_app_module.__dict__)
_install_ops_admin_nav(_customer_work_patch_module, _app_module.__dict__)
_install_priority_today(
    _customer_work_ui_module,
    _customer_work_patch_module,
    _weekly_plan_module,
    _app_module.__dict__.get("LOGGER"),
)
# Priority V2 owns heat dashboard, per-item persisted priority and leader approval editing.
_install_planning_priority_v2(
    _customer_work_module,
    _customer_work_ui_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# Final UX bridge adds the always-visible QLKH selector and Q1..Q4 quick-input override.
_install_priority_workflow_bridge(
    _customer_work_ui_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# Install last so the catalog renderer keeps the final priority semantics while
# fixing select-to-edit state synchronization for both catalog tabs.
_install_catalog_edit_state_fix(
    _customer_work_ui_module,
    _customer_work_module,
    _app_module.__dict__.get("LOGGER"),
)
_app_module.app()
