from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from khdn_apps import weekly_plan as core
from khdn_apps import weekly_priority_policy_patch as policy


def main():
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "weekly_policy.db"

        def get_conn():
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            return c

        with get_conn() as c:
            c.executescript(
                """
                CREATE TABLE users(
                    id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    role TEXT,
                    is_admin INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1
                );
                CREATE TABLE customers(
                    id INTEGER PRIMARY KEY,
                    cif TEXT,
                    customer_name TEXT,
                    qlkh_user_id INTEGER,
                    active INTEGER DEFAULT 1
                );
                CREATE TABLE tasks(
                    id INTEGER PRIMARY KEY,
                    task_code TEXT,
                    task_type TEXT,
                    customer_id INTEGER,
                    qlkh_user_id INTEGER,
                    support_user_id INTEGER,
                    status TEXT,
                    due_time TEXT
                );
                INSERT INTO users(id,full_name,role,is_admin,active) VALUES
                    (1,'Trưởng phòng A','Lãnh đạo phòng',0,1),
                    (2,'CBQLKH A','Cán bộ QLKH',0,1),
                    (3,'Admin','Admin',1,1);
                """
            )
        policy._ensure_schema(core, get_conn)
        # In production this column is already introduced by planning_priority_patch.
        # Keep the isolated semantic fixture equivalent to the installed runtime stack.
        with get_conn() as c:
            cols = {str(r[1]) for r in c.execute("PRAGMA table_info(weekly_plan_items)").fetchall()}
            if "priority_quadrant" not in cols:
                c.execute("ALTER TABLE weekly_plan_items ADD COLUMN priority_quadrant INTEGER")

        # Rule table from the approved specification.
        assert policy._classify({"id": 1}, None, None)[0] == 2
        assert policy._classify(None, True, True)[0] == 1
        assert policy._classify(None, True, False)[0] == 3
        assert policy._classify(None, False, None)[0] == 4

        with get_conn() as c:
            ts = policy._now()
            c.execute(
                """INSERT INTO weekly_focus_categories(
                   department_key,apply_year,code,name,description,sort_order,active,
                   created_by,updated_by,created_at,updated_at)
                   VALUES('LEADER:1',2026,'TT01','Phát triển khách hàng mới','Tiếp cận khách hàng chưa có quan hệ',1,1,1,1,?,?)""",
                (ts, ts),
            )
            cat_id = int(c.execute("SELECT id FROM weekly_focus_categories WHERE code='TT01'").fetchone()[0])
            pid = core.ensure_plan(c, 2, policy._default_week(core))
            c.execute(
                """INSERT INTO weekly_plan_items(
                   plan_id,user_id,work_date,title,category,purposes_json,status,reschedule_count,
                   created_at,updated_at,estimated_hours,expected_output)
                   VALUES(?,?,?,?,?,'[]','PLANNED',0,?,?,2.0,'Biên bản gặp KH')""",
                (pid, 2, policy._default_week(core).isoformat(), 'Gặp KH mới', 'Kế hoạch tuần', ts, ts),
            )
            iid = int(c.execute("SELECT id FROM weekly_plan_items ORDER BY id DESC LIMIT 1").fetchone()[0])
            policy._set_classification(c, iid, 2, cat_id, None, None, "QA")
            row = dict(c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (iid,)).fetchone())
            assert int(row["priority_quadrant"]) == 2
            assert row["focus_code_snapshot"] == "TT01"
            assert row["priority_basis"] == "FOCUS_CATALOG"

            # Manager removal -> Q1 is audited.
            policy._set_classification(c, iid, 1, None, True, True, "Không đúng trọng tâm")
            row2 = dict(c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (iid,)).fetchone())
            assert int(row2["priority_quadrant"]) == 1
            assert row2["focus_category_id"] is None
            assert c.execute("SELECT COUNT(*) FROM weekly_classification_audit WHERE item_id=?", (iid,)).fetchone()[0] >= 2

            # Locked plan blocks classification edits.
            c.execute("UPDATE weekly_plans SET workflow_status='DA_CHOT',classification_locked=1 WHERE id=?", (pid,))
            c.execute("UPDATE weekly_plan_items SET classification_locked=1 WHERE id=?", (iid,))
            blocked = False
            try:
                policy._set_classification(c, iid, 1, None, False, None, "must fail")
            except ValueError:
                blocked = True
            assert blocked

        print("WEEKLY_PRIORITY_POLICY_QA_PASS", {
            "q2_first": True,
            "q1_rule": True,
            "q3_rule": True,
            "q4_rule": True,
            "focus_snapshot": True,
            "manager_audit": True,
            "locked_after_close": True,
        })


if __name__ == "__main__":
    main()
