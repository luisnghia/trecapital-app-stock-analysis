"""Trecapital multipage entrypoint for KHDN Ops.

Route on a Streamlit custom domain: /KHDNApps
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "khdn_apps"
DATA_DIR = PKG / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("KHDN_CLOUD_MODE", "1")
os.environ.setdefault("KHDN_DB_PATH", str(DATA_DIR / "khdn_ops.db"))

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import khdn_apps.app as _app_module  # noqa: E402
from khdn_apps.cbht_workload_patch import install as _install_v231  # noqa: E402

_install_v231(_app_module.__dict__)
_app_module.app()
