"""Offline entrypoint for KHDN Ops V2.31.6.

Run from the repository/package root with:
    streamlit run khdn_apps/offline_entry.py
"""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("KHDN_CLOUD_MODE", "0")
os.environ.setdefault("KHDN_DB_PATH", str(DATA_DIR / "khdn_ops.db"))
os.environ.setdefault("KHDN_DATA_DIR", str(DATA_DIR))

import khdn_apps.app as _app_module
import khdn_apps.cbht_workload_patch as _workload_patch_module
import khdn_apps.full_task_edit_patch as _full_task_edit_module
from khdn_apps.cbht_workload_patch import install as _install_v231
from khdn_apps.leader_workload_match_patch import install as _install_v2311
from khdn_apps.amount_decimal_patch import install as _install_v2312
from khdn_apps.full_task_edit_patch import install as _install_v2313
from khdn_apps.direct_task_edit_button_patch import install as _install_v2314
from khdn_apps.catalog_sync_patch import install as _install_v2316

_install_v231(_app_module.__dict__)
_install_v2311(_app_module.__dict__, _workload_patch_module)
_install_v2312(_app_module.__dict__)
_install_v2313(_app_module.__dict__)
_install_v2314(_app_module.__dict__, _full_task_edit_module)
_install_v2316(_app_module.__dict__)
_app_module.app()
