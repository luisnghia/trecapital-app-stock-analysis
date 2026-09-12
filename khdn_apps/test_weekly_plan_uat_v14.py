"""Pre-production UAT simulation for KHDN Weekly Plan V14.

Covers the concrete room scenarios used before merge:
- Officer A: 7 planned tasks + 2 emergent tasks; valid because emergent work does
  not count toward the planned-task cap and the plan has at least 3 Q2 items.
- Officer B: insufficient Q2 work; submission must be blocked.
- Officer C: a late completed Q2 task receives the documented 0.6 factor.
- Basic submitted -> approved -> closed -> reviewed lifecycle and audit rows.
"""
from __future__ import annotations

import sqlite3
import tempfile
from datetime import timedelta
from pathlib import Path

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v12 as v12


def main():
    tmp = tempfile.TemporaryDirectory()
    db = Path(tmp.name) / "uat.db"

    def get_conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    with get_conn() as c:
        c.execute("""CREATE TABLE users(
            id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, role TEXT,
            active INTEGER DEFAULT 1, is_admin INTEGER DEFAULT 0)""")
        c.executemany(
            "INSERT INTO users(id,username,full_name,role,active,is_admin) VALUES(?,?,?,?,1,?)",
            [
                (1, "cb_a", "Cán bộ A", "Cán bộ QLKH", 0),
                (2, "cb_b", "Cán bộ B", "Cán bộ hỗ trợ", 0),
                (3, "cb_c", "Cán bộ C", "Cán bộ QLKH", 0),
                (9, "leader", "Lãnh đạo phòng", "Lãnh đạo phòng", 1),
            ],
        )
        c.commit()

    v6._init_v6_schema(get_conn)
    v12._init_v12_schema(get_conn)
    year, week, monday, sunday = wp._iso_week()
    focus = wp._focus_df(get_conn, year, True)
    assert not focus.empty
    focus_id = int(focus.iloc[0]["id"])

    def create_plan(uid: int):
        return wp._get_or_create_plan(get_conn, uid, year, week, monday, sunday)

    def add_task(plan_id: int, title: str, quadrant: str, hours: float, *, emergent=False,
                 due_offset=4, status="NOT_STARTED", completed_offset=None):
        due = monday + timedelta(days=due_offset)
        completed_at = None
        if completed_offset is not None:
            completed_at = (monday + timedelta(days=completed_offset)).strftime("%Y-%m-%d 10:00:00")
        fid = focus_id if quadrant == "Q2" else None
        urgent = 1 if quadrant in {"Q1", "Q3"} else 0
        has_kpi = 1 if quadrant == "Q1" else 0
        return wp._execute(
            get_conn,
            """INSERT INTO weekly_tasks(
                plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,
                quadrant,due_date,planned_hours,actual_hours,status,completed_at,is_emergent,
                defer_count,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)""",
            (
                int(plan_id), title, f"Đầu ra {title}", fid, urgent, has_kpi, quadrant,
                due.isoformat(), float(hours), float(hours if status == "COMPLETED" else 0),
                status, completed_at, int(bool(emergent)), wp._now(), wp._now(),
            ),
        )

    # Scenario A: 7 planned tasks, at least 3 Q2, plus 2 emergent tasks.
    plan_a = create_plan(1)
    specs_a = [
        ("A-Q2-1", "Q2", 6), ("A-Q2-2", "Q2", 6), ("A-Q2-3", "Q2", 6),
        ("A-Q1-1", "Q1", 5), ("A-Q1-2", "Q1", 5),
        ("A-Q3-1", "Q3", 4), ("A-Q4-1", "Q4", 4),
    ]
    for title, quadrant, hours in specs_a:
        add_task(plan_a["id"], title, quadrant, hours)
    add_task(plan_a["id"], "A-PS-1", "Q1", 2, emergent=True)
    add_task(plan_a["id"], "A-PS-2", "Q3", 2, emergent=True)
    tasks_a = wp._tasks_df(get_conn, int(plan_a["id"]))
    assert len(tasks_a) == 9
    assert int((tasks_a["is_emergent"] == 0).sum()) == 7
    assert int(((tasks_a["is_emergent"] == 0) & (tasks_a["quadrant"] == "Q2")).sum()) == 3
    assert v12._validate_submit_configured(get_conn, tasks_a) == []

    # Simulate the valid lifecycle and make sure every transition/audit write is durable.
    ts = wp._now()
    with get_conn() as c:
        c.execute("UPDATE weekly_plans SET status='SUBMITTED',submitted_at=?,updated_at=? WHERE id=?", (ts, ts, int(plan_a["id"])))
        c.commit()
    wp._log(get_conn, 1, "SUBMIT_PLAN", "weekly_plan", plan_a["id"], "UAT")
    with get_conn() as c:
        c.execute("UPDATE weekly_plans SET status='APPROVED',approved_at=?,reviewer_user_id=9,updated_at=? WHERE id=?", (ts, ts, int(plan_a["id"])))
        c.execute("UPDATE weekly_tasks SET classification_locked=1,updated_at=? WHERE plan_id=?", (ts, int(plan_a["id"])))
        c.commit()
    wp._log(get_conn, 9, "APPROVE_PLAN", "weekly_plan", plan_a["id"], "UAT")
    with get_conn() as c:
        c.execute("UPDATE weekly_plans SET status='CLOSED',closed_at=?,updated_at=? WHERE id=?", (ts, ts, int(plan_a["id"])))
        c.execute("""INSERT INTO weekly_reviews(
            plan_id,self_score,strengths,limitations,causes,next_actions,created_at,updated_at)
            VALUES(?,4,'Đạt','Theo dõi','Không','Duy trì',?,?)""", (int(plan_a["id"]), ts, ts))
        c.commit()
    wp._log(get_conn, 1, "CLOSE_PLAN", "weekly_plan", plan_a["id"], "UAT")
    with get_conn() as c:
        c.execute("""UPDATE weekly_reviews SET leader_score=4,leader_comment='Đạt yêu cầu',
            progress_score=80,quality_score=80,week_score=80,grade='B',updated_at=? WHERE plan_id=?""",
            (ts, int(plan_a["id"])))
        c.execute("UPDATE weekly_plans SET status='REVIEWED',reviewed_at=?,reviewer_user_id=9,updated_at=? WHERE id=?",
                  (ts, ts, int(plan_a["id"])))
        c.commit()
    wp._log(get_conn, 9, "REVIEW_PLAN", "weekly_plan", plan_a["id"], "UAT")
    final_a = wp._get_plan(get_conn, 1, year, week)
    assert final_a["status"] == "REVIEWED"
    logs = wp._qdf(get_conn, "SELECT action FROM weekly_plan_logs WHERE object_id=?", (str(plan_a["id"]),))
    for action in ("SUBMIT_PLAN", "APPROVE_PLAN", "CLOSE_PLAN", "REVIEW_PLAN"):
        assert action in set(logs["action"].astype(str))

    # Scenario B: fewer than 3 Q2 tasks blocks submission.
    plan_b = create_plan(2)
    for title, quadrant in [
        ("B-Q2-1", "Q2"), ("B-Q2-2", "Q2"), ("B-Q1", "Q1"),
        ("B-Q3", "Q3"), ("B-Q4", "Q4"),
    ]:
        add_task(plan_b["id"], title, quadrant, 3)
    errors_b = v12._validate_submit_configured(get_conn, wp._tasks_df(get_conn, int(plan_b["id"])))
    assert any("tối thiểu 3" in e and "hiện có 2" in e for e in errors_b)

    # Scenario C: completed one day late => 0.6 completion factor => 60 points.
    plan_c = create_plan(3)
    add_task(plan_c["id"], "C-Q2-late", "Q2", 4, due_offset=2, status="COMPLETED", completed_offset=3)
    score_c = v12._progress_score_configured(get_conn, wp._tasks_df(get_conn, int(plan_c["id"])))
    assert abs(score_c - 60.0) < 1e-9, score_c

    print("KHDN Weekly Plan V14 pre-production UAT simulation: OK")


if __name__ == "__main__":
    main()
