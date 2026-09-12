"""Deterministic tests for Weekly Plan V10 30-second autosave persistence."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import date
from pathlib import Path

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v10 as v10


def main():
    tmp = tempfile.TemporaryDirectory()
    db = Path(tmp.name) / "weekly-v10.db"

    def get_conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    with get_conn() as c:
        c.execute("""CREATE TABLE users(
            id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, role TEXT,
            active INTEGER DEFAULT 1, is_admin INTEGER DEFAULT 0)""")
        c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(1,'cb01','Cán bộ Test','Cán bộ QLKH',1,0)")
        c.commit()

    v6._init_v6_schema(get_conn)
    v10._init_autosave_schema(get_conn)
    year, week, monday, sunday = wp._iso_week()
    plan = wp._get_or_create_plan(get_conn, 1, year, week, monday, sunday)

    empty_saved = v10._persist_new_task_buffer(
        get_conn, 1, int(plan["id"]), "planned:0",
        {"title": "", "expected": "", "due": date.today(), "hours": 2.0, "focus": 0, "kpi": False},
    )
    assert empty_saved is False
    assert v10._buffer_row(get_conn, 1, int(plan["id"]), "planned:0") is None

    payload = {
        "title": "Rà soát hồ sơ khách hàng tuần",
        "expected": "Danh sách hồ sơ cần xử lý",
        "due": date.today(),
        "hours": 3.5,
        "focus": 0,
        "kpi": True,
    }
    assert v10._persist_new_task_buffer(get_conn, 1, int(plan["id"]), "planned:0", payload)
    loaded = v10._load_buffer_payload(get_conn, 1, int(plan["id"]), "planned:0")
    assert loaded is not None
    assert loaded["title"] == payload["title"]
    assert loaded["expected"] == payload["expected"]
    assert loaded["due"] == date.today().isoformat()
    assert abs(float(loaded["hours"]) - 3.5) < 1e-9
    assert bool(loaded["kpi"]) is True

    updated = dict(payload)
    updated["expected"] = "Danh sách hồ sơ đã phân loại ưu tiên"
    updated["hours"] = 4.0
    assert v10._persist_new_task_buffer(get_conn, 1, int(plan["id"]), "planned:0", updated)
    loaded2 = v10._load_buffer_payload(get_conn, 1, int(plan["id"]), "planned:0")
    assert loaded2["expected"] == updated["expected"]
    assert abs(float(loaded2["hours"]) - 4.0) < 1e-9

    v10._delete_buffer(get_conn, 1, int(plan["id"]), "planned:0")
    assert v10._load_buffer_payload(get_conn, 1, int(plan["id"]), "planned:0") is None

    print("KHDN Weekly Plan V10 autosave tests: OK")


if __name__ == "__main__":
    main()
