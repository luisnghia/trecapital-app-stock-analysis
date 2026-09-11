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

from khdn_apps.app import app

app()
