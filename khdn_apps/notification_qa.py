"""Semantic QA for KHDN Ops V2.32 notification engine."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from khdn_apps import notifications as n


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "notif.db"
        c = sqlite3.connect(db)
        try:
            c.executescript(
                """
                CREATE TABLE users(
                    id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, role TEXT,
                    active INTEGER DEFAULT 1, deleted_at TEXT
                );
                CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT);
                CREATE TABLE task_types(id INTEGER PRIMARY KEY,name TEXT,sla_hours REAL,active INTEGER,created_at TEXT,updated_at TEXT);
                CREATE TABLE tasks(
                    id INTEGER PRIMARY KEY,task_code TEXT,customer_id INTEGER,support_user_id INTEGER,
                    qlkh_user_id INTEGER,task_type TEXT,status TEXT,amount REAL,currency TEXT,
                    start_time TEXT,updated_at TEXT
                );
                CREATE TABLE task_actions(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,task_id INTEGER,actor_user_id INTEGER,
                    action TEXT,detail TEXT,created_at TEXT
                );
                INSERT INTO users VALUES(1,'sup','CBHT A','Cán bộ hỗ trợ',1,NULL);
                INSERT INTO users VALUES(2,'ql','QLKH B','Cán bộ QLKH',1,NULL);
                INSERT INTO users VALUES(3,'lead','Lãnh đạo C','Lãnh đạo phòng',1,NULL);
                INSERT INTO customers VALUES(1,'7609338','CÔNG TY TEST');
                INSERT INTO task_types VALUES(1,'Giải ngân',8,1,'2026-09-22 08:00:00','2026-09-22 08:00:00');
                INSERT INTO tasks VALUES(10,'TN-000010',1,1,2,'Giải ngân','PENDING_ACCEPTANCE',23834.18,'EUR','2026-09-22 08:00:00','2026-09-22 08:00:00');
                INSERT INTO task_actions(task_id,actor_user_id,action,detail,created_at)
                VALUES(10,2,'ASSIGN','old action before notification feature','2026-09-22 08:00:00');
                """
            )
            c.commit()
        finally:
            c.close()

        # Existing history must not blast users when the feature is first deployed.
        n.ensure_schema(db)
        assert n.process_task_actions(db) == 0
        assert n.unread_count(db, 1) == 0

        def action(actor: int, name: str, detail: str) -> None:
            with n._connect(db) as cx:
                cx.execute(
                    "INSERT INTO task_actions(task_id,actor_user_id,action,detail,created_at) VALUES(10,?,?,?,?,?)".replace("VALUES(10,?,?,?,?,?)", "VALUES(10,?,?,?,?)"),
                    (actor, name, detail, datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                )
                cx.commit()

        action(2, "ASSIGN", "QLKH giao hồ sơ mới")
        assert n.process_task_actions(db) == 1
        assert n.unread_count(db, 1) == 1
        assert n.unread_count(db, 2) == 0

        action(1, "ACCEPT", "CBHT tiếp nhận")
        action(1, "SUBMIT_REVIEW", "CBHT báo hoàn thành")
        assert n.process_task_actions(db) == 2
        assert n.unread_count(db, 2) == 2

        action(3, "REWORK", "Lãnh đạo yêu cầu làm lại")
        assert n.process_task_actions(db) == 2
        assert n.unread_count(db, 1) == 2
        assert n.unread_count(db, 2) == 3

        # Per-user preference must suppress only that category.
        n.set_preference(db, 2, "completion", False)
        action(1, "SUBMIT_REVIEW", "Lần hoàn thành tiếp theo")
        assert n.process_task_actions(db) == 0
        assert n.unread_count(db, 2) == 3

        # Read/unread center semantics.
        rows = n.list_notifications(db, 1)
        assert rows and rows[0]["task_id"] == 10
        n.mark_read(db, rows[0]["id"], 1)
        assert n.unread_count(db, 1) == 1
        n.mark_all_read(db, 1)
        assert n.unread_count(db, 1) == 0

        # Secure setup tickets bind subscription setup to an authenticated user.
        old_secret = os.environ.get("KHDN_PUSH_TOKEN_SECRET")
        os.environ["KHDN_PUSH_TOKEN_SECRET"] = "qa-secret-not-for-production-0123456789"
        try:
            ticket = n.issue_setup_ticket(2, ttl_seconds=120)
            assert n.verify_setup_ticket(ticket) == 2
            assert n.verify_setup_ticket(ticket + "tamper") is None
        finally:
            if old_secret is None:
                os.environ.pop("KHDN_PUSH_TOKEN_SECRET", None)
            else:
                os.environ["KHDN_PUSH_TOKEN_SECRET"] = old_secret

        # Subscription storage is per device and idempotent by endpoint.
        sub = {"endpoint": "https://push.example.test/abc", "keys": {"p256dh": "p-key", "auth": "a-key"}}
        n.save_subscription(db, 2, sub, "QA Browser")
        n.save_subscription(db, 2, sub, "QA Browser 2")
        assert n.subscription_count(db, 2) == 1
        n.deactivate_subscription(db, 2, sub["endpoint"])
        assert n.subscription_count(db, 2) == 0

        # SLA warning/overdue alerts are emitted once per threshold/user.
        old_start = (datetime.now() - timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
        with n._connect(db) as cx:
            cx.execute("UPDATE tasks SET status='OPEN',start_time=? WHERE id=10", (old_start,))
            cx.commit()
        before1 = n.unread_count(db, 1)
        before2 = n.unread_count(db, 2)
        generated = n.process_sla_alerts(db)
        assert generated == 2, generated
        assert n.unread_count(db, 1) == before1 + 1
        assert n.unread_count(db, 2) == before2 + 1
        assert n.process_sla_alerts(db) == 0

        print("KHDN_NOTIFICATION_QA PASS", {
            "no_retroactive_blast": True,
            "assignment_to_cbht": True,
            "accept_complete_to_qlkh": True,
            "leader_rework_both": True,
            "preferences": True,
            "read_unread": True,
            "signed_setup_ticket": True,
            "subscription_idempotent": True,
            "sla_once_per_threshold": True,
        })


if __name__ == "__main__":
    main()
