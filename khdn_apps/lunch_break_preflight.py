"""Build-time QA for lunch-break settings and overlap math."""
from pathlib import Path
import ast
import base64
import gzip
import math
import sqlite3
import sys
import tempfile
from datetime import time

import pandas as pd

_app_root = str(Path(__file__).resolve().parent.parent)
if _app_root not in sys.path:
    sys.path.insert(0, _app_root)

from khdn_apps.lunch_break_patch import patch_source


def _load_elapsed(source):
    tree = ast.parse(source)
    wanted = {
        "_elapsed_minutes_excluding_lunch",
        "_elapsed_series_excluding_lunch",
        "_clock_to_minutes",
        "save_lunch_break_settings",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if len(nodes) != len(wanted):
        raise RuntimeError("Lunch elapsed helpers are incomplete")
    ns = {"pd": pd, "math": math}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<lunch-break-helpers>", "exec"), ns, ns)
    return ns


def main():
    root = Path(__file__).resolve().parent
    payload = "".join(p.read_text(encoding="ascii") for p in sorted((root / "_src").glob("*.txt")))
    raw = gzip.decompress(base64.b64decode(payload)).decode("utf-8")
    source = patch_source(raw)
    compile(source, "<khdn-lunch-break-preflight>", "exec")
    ns = _load_elapsed(source)
    elapsed = ns["_elapsed_minutes_excluding_lunch"]
    with tempfile.TemporaryDirectory(prefix="khdn_lunch_qa_") as td:
        db_path = Path(td) / "lunch.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE system_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL,updated_by INTEGER)")
            conn.execute("CREATE TABLE system_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor_user_id INTEGER,action TEXT,object_type TEXT,object_id TEXT,detail TEXT,created_at TEXT)")
            conn.commit()

        def get_conn():
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn

        def now_str():
            return "2026-09-14 09:00:00"

        audit_calls = []

        def audit(*args):
            audit_calls.append(args)

        ns.update({"get_conn": get_conn, "now_str": now_str, "audit": audit, "ValueError": ValueError, "int": int, "str": str, "bool": bool})
        ns["save_lunch_break_settings"](7, True, time(11, 45), time(13, 15))
        with sqlite3.connect(db_path) as conn:
            saved = dict(conn.execute("SELECT key,value FROM system_settings ORDER BY key").fetchall())
        persisted = saved == {
            "lunch_break_enabled": "1",
            "lunch_break_end": "13:15",
            "lunch_break_start": "11:45",
        } and len(audit_calls) == 1
    checks = {
        "same_day_overlap": elapsed("2026-09-14 11:30", "2026-09-14 14:00", (720, 810)) == 60.0,
        "inside_break_zero": elapsed("2026-09-14 12:30", "2026-09-14 13:00", (720, 810)) == 0.0,
        "multi_day_overlap": elapsed("2026-09-14 11:30", "2026-09-15 14:00", (720, 810)) == 1410.0,
        "outside_break_unchanged": elapsed("2026-09-14 09:00", "2026-09-14 11:00", (720, 810)) == 120.0,
        "settings_schema": "CREATE TABLE IF NOT EXISTS system_settings" in source,
        "settings_ui_helpers": "def lunch_break_settings()" in source and "def save_lunch_break_settings" in source,
        "settings_persist": persisted,
        "calendar_aware_enrich": "_duration = _elapsed_series_excluding_lunch" in source,
        "calendar_aware_live_wait": "elapsed=_elapsed_minutes_excluding_lunch(start, now_dt(), lunch_break_interval())" in source,
    }
    print("KHDN_LUNCH_BREAK_PREFLIGHT", checks, flush=True)
    failed = [key for key, value in checks.items() if not value]
    if failed:
        raise RuntimeError("Lunch-break preflight failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
