"""Offline entrypoint for KHDN Ops V2.31.

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
from khdn_apps.cbht_workload_patch import install as _install_v231

_install_v231(_app_module.__dict__)
_app_module.app()
