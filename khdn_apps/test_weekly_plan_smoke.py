"""Headless smoke tests for KHDN Weekly Plan data/report logic."""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import date, timedelta
from pathlib import Path

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v3 as v3


def main():
    tmp = tempfile.TemporaryDirectory()
    db = Path(tmp.name) / "weekly.db"

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
        c.execute("INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(2,'ld01','Lãnh đạo Test','Lãnh đạo phòng',1,0)")
        c.commit()

    v2._init_v2_schema(get_conn)
    year, week, monday, sunday = wp._iso_week()
    plan = wp._get_or_create_plan(get_conn, 1, year, week, monday, sunday)
    focus = wp._focus_df(get_conn, year, active_only=True)
    assert not focus.empty
    focus_id = int(focus.iloc[0]["id"])
    assert wp._classification(focus_id, False, False) == "Q2"
    assert wp._classification(None, True, True) == "Q1"
    assert wp._classification(None, True, False) == "Q3"
    assert wp._classification(None, False, False) == "Q4"

    with get_conn() as c:
        for i in range(3):
            c.execute("""INSERT INTO weekly_tasks(
                plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,
                due_date,planned_hours,actual_hours,status,is_emergent,defer_count,created_at,updated_at)
                VALUES(?,?,?,?,0,0,'Q2',?,?,0,'NOT_STARTED',0,0,?,?)""",
                (int(plan["id"]), f"Q2 test {i+1}", "Đầu ra", focus_id,
                 (monday + timedelta(days=4)).isoformat(), 2.0, wp._now(), wp._now()))
        c.commit()

    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    assert len(tasks) == 3
    assert wp._validate_submit(tasks) == []

    # Create a prior incomplete task and confirm carry-forward discovery.
    prev_monday = monday - timedelta(days=7)
    prev_iso = prev_monday.isocalendar()
    prev = wp._get_or_create_plan(get_conn, 1, int(prev_iso.year), int(prev_iso.week), prev_monday, prev_monday + timedelta(days=6))
    with get_conn() as c:
        c.execute("""INSERT INTO weekly_tasks(
            plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,
            due_date,planned_hours,actual_hours,status,is_emergent,defer_count,created_at,updated_at)
            VALUES(?,?,?,?,0,0,'Q2',?,?,0,'IN_PROGRESS',0,1,?,?)""",
            (int(prev["id"]), "Việc chuyển tiếp", "Đầu ra", focus_id,
             (prev_monday + timedelta(days=4)).isoformat(), 2.0, wp._now(), wp._now()))
        c.commit()
    cand = v2._carry_candidates(get_conn, 1, year, week, int(plan["id"]))
    assert len(cand) == 1

    # Reports must be non-empty and valid container formats.
    excel = v2._excel_bytes(get_conn, 1)
    assert excel[:2] == b"PK"
    pdf = v3._pdf_bytes(get_conn, {"id": 1, "username": "cb01", "full_name": "Cán bộ Test"})
    assert pdf[:4] == b"%PDF"

    print("KHDN Weekly Plan smoke tests: OK")


if __name__ == "__main__":
    main()
