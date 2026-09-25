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
import khdn_apps.customer_work_patch as _customer_work_patch_module
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

_install_v231(_app_module.__dict__)
_install_v2311(_app_module.__dict__, _workload_patch_module)
_install_v2312(_app_module.__dict__)
_install_v2313(_app_module.__dict__)
_install_v2314(_app_module.__dict__, _full_task_edit_module)
_install_v2316(_app_module.__dict__)
_install_v2320(_app_module.__dict__)
_install_weekly_governance(_weekly_plan_module, _app_module.__dict__.get("LOGGER"))
_install_weekly_plan(_app_module.__dict__)
_install_customer_work(_app_module.__dict__)
_install_ops_admin_nav(_customer_work_patch_module, _app_module.__dict__)
_app_module.app()
