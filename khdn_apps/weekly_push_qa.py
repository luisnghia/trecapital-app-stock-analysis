"""Planning Push integration QA; all network delivery is replaced by a fake provider."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from khdn_apps import notifications as notify
from khdn_apps import weekly_push as push
from khdn_apps import weekly_plan_notifications as work
from khdn_apps import weekly_phase2_notifications as cycle
from khdn_apps import weekly_priority_policy_patch as policy
from khdn_apps.notification_ui_patch import _notification_route


class FakePushException(Exception):
    def __init__(self, status):
        super().__init__(f"Fake provider status {status}")
        self.response = SimpleNamespace(status_code=status)


class PlanningPushQA(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "planning.db"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,
                    active INTEGER,is_admin INTEGER,manager_user_id INTEGER);
                INSERT INTO users VALUES
                    (1,'Leader A','Lãnh đạo phòng',1,0,NULL),
                    (2,'Staff A','Cán bộ QLKH',1,0,1),
                    (3,'Staff B','Cán bộ hỗ trợ',1,0,4),
                    (4,'Leader B','Lãnh đạo phòng',1,0,NULL),
                    (5,'Admin','Admin',1,1,NULL),
                    (6,'Inactive','Cán bộ QLKH',0,0,1);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY);
                INSERT INTO tasks VALUES(99);
                CREATE TABLE weekly_plans(id INTEGER PRIMARY KEY,user_id INTEGER,
                    week_start TEXT,workflow_status TEXT,submitted_at TEXT,self_score REAL,
                    closed_at TEXT,evaluated_at TEXT,updated_at TEXT);
                CREATE TABLE weekly_plan_items(id INTEGER PRIMARY KEY,plan_id INTEGER,
                    user_id INTEGER,controller_user_id INTEGER,title TEXT,customer_text TEXT,
                    work_date TEXT,expected_complete_date TEXT,is_emergent INTEGER,
                    status TEXT,priority_quadrant INTEGER,completed_at TEXT);
            """)
        push.ensure_schema(self.db)
        self.calls = []
        self.provider = ModuleType("pywebpush")
        self.provider.WebPushException = FakePushException
        self.provider.webpush = self.webpush
        provider_patch = patch.dict(sys.modules, {"pywebpush": self.provider})
        provider_patch.start()
        self.addCleanup(provider_patch.stop)
        self.env_patch = patch.dict(os.environ, {
            "KHDN_VAPID_PRIVATE_KEY": "fake-test-private-key",
            "KHDN_VAPID_PUBLIC_KEY": "fake-test-public-key",
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        for uid in (1, 2, 3, 4):
            notify.save_subscription(self.db, uid, {
                "endpoint": f"https://push.example.test/{uid}",
                "keys": {"p256dh": "fake-key", "auth": "fake-auth"},
            })

    def webpush(self, **kwargs):
        self.calls.append((kwargs["subscription_info"]["endpoint"], json.loads(kwargs["data"])))

    def enqueue(self, uid=2, **kwargs):
        with notify._connect(self.db) as c:
            return push.enqueue(c, uid, "Planning title", "Planning body", **kwargs)

    def events(self):
        with notify._connect(self.db) as c:
            return [(r[0], r[1]) for r in c.execute(
                "SELECT event_code,user_id FROM weekly_push_audit WHERE stage='IN_APP_CREATED' ORDER BY id")]

    def plan(self, pid, uid, week, status, submitted=None, closed=None, self_score=None):
        with notify._connect(self.db) as c:
            c.execute("""INSERT INTO weekly_plans
                (id,user_id,week_start,workflow_status,submitted_at,closed_at,self_score)
                VALUES(?,?,?,?,?,?,?)""", (pid, uid, week, status, submitted, closed, self_score))

    def test_policy_decisions_transport_and_operations_isolation(self):
        with notify._connect(self.db) as c:
            nid = policy._notify(c, 2, "✅ Kế hoạch tuần đã được duyệt", "Approved")
            notify._insert_notification(c, user_id=2, task_id=99, event_key="update",
                                        source_action_id=None, title="Operations", body="Existing flow")
        self.assertEqual(push.flush(self.db), 1)
        self.assertEqual(notify.get_notification(self.db, nid, 2)["push_status"], "SENT")
        self.assertEqual(self.calls[0][0], "https://push.example.test/2")
        self.assertEqual(self.calls[0][1]["url"], f"/?khdn_notification={nid}")
        with notify._connect(self.db) as c:
            self.assertEqual(c.execute("SELECT push_status FROM notifications WHERE task_id=99").fetchone()[0], "PENDING")
        self.assertIsNone(notify.get_notification(self.db, nid, 3))
        self.assertEqual(push.flush(self.db), 0)
        self.assertEqual(len(self.calls), 1)
        with notify._connect(self.db) as c:
            other = policy._notify(c, 3, "↩ Kế hoạch tuần được trả lại", "Please adjust")
        self.assertEqual(push.flush(self.db), 1)
        self.assertEqual(self.calls[-1][0], "https://push.example.test/3")
        self.assertEqual(notify.get_notification(self.db, other, 3)["push_status"], "SENT")

    def test_transaction_rollback(self):
        with self.assertRaises(RuntimeError):
            with notify._connect(self.db) as c:
                push.enqueue(c, 2, "Rollback", "Rollback")
                raise RuntimeError("business save rejected")
        self.assertEqual(push.flush(self.db), 0)
        self.assertEqual(self.events(), [])

    def test_retry_after_temporary_failure_and_restart(self):
        nid = self.enqueue()
        def fail(**kwargs):
            raise TimeoutError("Fake timeout")
        self.provider.webpush = fail
        now = time.time()
        self.assertEqual(push.flush(self.db, now_ts=now), 0)
        self.provider.webpush = self.webpush
        notify._SCHEMA_READY.discard(str(self.db))
        self.assertEqual(push.flush(self.db, now_ts=now + 30), 0)
        self.assertEqual(push.flush(self.db, now_ts=now + 61), 1)
        self.assertEqual(notify.get_notification(self.db, nid, 2)["push_status"], "SENT")
        self.assertEqual(push.flush(self.db, now_ts=now + 500), 0)

    def test_missing_configuration_or_device_can_recover(self):
        nid = self.enqueue()
        now = time.time()
        with patch.dict(os.environ, {"KHDN_VAPID_PRIVATE_KEY": ""}):
            self.assertEqual(push.flush(self.db, now_ts=now), 0)
        self.assertEqual(notify.get_notification(self.db, nid, 2)["push_status"], "DISABLED")
        with notify._connect(self.db) as c:
            c.execute("UPDATE push_subscriptions SET active=0 WHERE user_id=2")
        self.assertEqual(push.flush(self.db, now_ts=now + 301), 0)
        self.assertEqual(notify.get_notification(self.db, nid, 2)["push_status"], "NO_DEVICE")
        with notify._connect(self.db) as c:
            c.execute("UPDATE push_subscriptions SET active=1 WHERE user_id=2")
        self.assertEqual(push.flush(self.db, now_ts=now + 602), 1)

    def test_expiry_preferences_and_inactive_accounts(self):
        self.enqueue(expires_at=time.time() - 1)
        notify.set_preference(self.db, 2, "weekly_reminder", False)
        self.assertIsNone(self.enqueue(event_key="weekly_reminder"))
        self.assertIsNone(self.enqueue(uid=6))
        # Disabling Operations updates does not disable Planning updates.
        notify.set_preference(self.db, 2, "update", False)
        self.enqueue()
        self.assertEqual(push.flush(self.db), 1)
        self.assertEqual(len(self.calls), 1)

    def test_expired_subscription_and_bounded_retry(self):
        nid = self.enqueue()
        def expired(**kwargs):
            raise FakePushException(410)
        self.provider.webpush = expired
        now = time.time()
        push.flush(self.db, now_ts=now)
        self.assertEqual(notify.subscription_count(self.db, 2), 0)
        self.assertEqual(notify.get_notification(self.db, nid, 2)["push_status"], "ERROR")
        notify.save_subscription(self.db, 2, {"endpoint": "https://push.example.test/replacement",
                                 "keys": {"p256dh": "fake", "auth": "fake"}})
        def always_fail(**kwargs):
            raise FakePushException(503)
        self.provider.webpush = always_fail
        push.flush(self.db, now_ts=now + 61)
        push.flush(self.db, now_ts=now + 182)
        with notify._connect(self.db) as c:
            self.assertEqual(tuple(c.execute("SELECT state,attempts FROM weekly_push_queue WHERE notification_id=?", (nid,)).fetchone()), ("ERROR", 3))
        self.provider.webpush = self.webpush
        self.assertEqual(push.flush(self.db, now_ts=now + 999), 0)

    def test_concurrent_delivery_claim(self):
        self.enqueue()
        entered, release = threading.Event(), threading.Event()
        def slow(**kwargs):
            entered.set()
            release.wait(5)
            self.webpush(**kwargs)
        self.provider.webpush = slow
        results = []
        def run():
            results.append(push.flush(self.db))
        thread = threading.Thread(target=run)
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            self.assertEqual(push.flush(self.db), 0)
        finally:
            release.set()
            thread.join(5)
        self.assertEqual(results, [1])
        self.assertEqual(len(self.calls), 1)

    def test_weekly_cycle_schedule_and_direct_leader(self):
        monday = datetime(2026, 10, 5, 9, 30)
        self.assertEqual(cycle.process_cycle_reminders(self.db, monday), 6)
        self.assertEqual(cycle.process_cycle_reminders(self.db, monday), 0)
        self.assertIn(("PLAN_OVERDUE_LEADER", 1), self.events())
        self.assertIn(("PLAN_OVERDUE_LEADER", 4), self.events())
        self.assertFalse(any(uid in {5, 6} for _, uid in self.events()))
        self.assertEqual(push.flush(self.db), 6)
        self.plan(11, 2, "2026-10-05", "DA_NOP", submitted="2026-10-05 10:00:00")
        self.assertEqual(cycle.process_cycle_reminders(self.db, monday), 1)
        self.assertEqual(self.events()[-1], ("PLAN_WAITING_APPROVAL", 1))
        self.assertEqual(cycle.process_cycle_reminders(self.db, monday), 0)
        with notify._connect(self.db) as c:
            c.execute("UPDATE weekly_plans SET submitted_at='2026-10-05 11:00:00' WHERE id=11")
        self.assertEqual(cycle.process_cycle_reminders(self.db, monday), 1)
        with notify._connect(self.db) as c:
            c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET' WHERE id=11")
        friday = datetime(2026, 10, 9, 16, 0)
        self.assertEqual(cycle.process_cycle_reminders(self.db, friday), 3)
        self.assertIn(("CLOSE_WEEK", 2), self.events())
        self.assertIn(("PLAN_REMINDER_FRI", 2), self.events())
        self.assertEqual(cycle.process_cycle_reminders(self.db, friday), 0)

    def test_work_due_reminders_and_new_work_baseline(self):
        today = push.local_now().date()
        self.plan(11, 2, today.isoformat(), "DA_DUYET")
        def item(iid, delta, status="PLANNED"):
            with notify._connect(self.db) as c:
                c.execute("""INSERT INTO weekly_plan_items
                    (id,plan_id,user_id,controller_user_id,title,work_date,expected_complete_date,is_emergent,status)
                    VALUES(?,11,2,1,'Work',?,?,0,?)""",
                    (iid, today.isoformat(), (today + timedelta(days=delta)).isoformat(), status))
        item(1, 1)
        item(2, 0)
        item(3, -1)
        item(4, -1, "DONE")
        item(5, -1, "CANCELLED")
        self.assertEqual(work.process_new_work(self.db), [])
        self.assertEqual(len(work.process_due_work(self.db)), 4)
        self.assertEqual(work.process_due_work(self.db), [])
        self.assertIn(("OVERDUE", 1), self.events())
        self.assertEqual(push.flush(self.db), 4)
        item(6, 4)
        self.assertEqual(len(work.process_new_work(self.db)), 2)
        self.assertEqual({uid for event, uid in self.events() if event == "NEW_WORK"}, {1, 2})
        self.assertEqual(push.flush(self.db), 2)

    def test_pending_manager_review_and_quality_fallback(self):
        self.plan(11, 2, "2026-09-28", "DA_CHOT", closed="2026-10-02 17:00:00", self_score=4)
        self.assertEqual(cycle.process_cycle_reminders(self.db, datetime(2026, 10, 5, 8)), 3)
        self.assertIn(("MANAGER_REVIEW_PENDING", 1), self.events())
        self.assertEqual(cycle.process_quality_fallback(self.db, datetime(2026, 10, 8, 12)), 0)
        self.assertEqual(cycle.process_quality_fallback(self.db, datetime(2026, 10, 9, 12)), 1)
        self.assertEqual(cycle.process_quality_fallback(self.db, datetime(2026, 10, 9, 12)), 0)
        self.assertIn(("QUALITY_FALLBACK", 2), self.events())
        self.assertEqual(push.flush(self.db), 4)

    def test_plan_deep_link_and_no_test_button(self):
        item = {"event_key": "weekly_update", "task_id": None}
        self.assertEqual(_notification_route({"role": "Cán bộ QLKH"}, item), "weekly_plan")
        self.assertEqual(_notification_route({"role": "Lãnh đạo phòng"}, item), "work_approvals")
        self.assertEqual(_notification_route({"role": "Cán bộ QLKH"}, {"event_key": "update", "task_id": 99}), "qlkh")
        src = Path(__file__).with_name("notification_ui_patch.py").read_text(encoding="utf-8")
        self.assertNotIn("notif_self_test", src)

    def test_legacy_pending_recovery_without_replaying_history(self):
        now = push.local_now()
        with notify._connect(self.db) as c:
            for status, stamp in (("DISABLED", now), ("SENT", now),
                                  ("PENDING", now - timedelta(days=2))):
                c.execute("""INSERT INTO notifications(user_id,event_key,title,body,created_at,push_status)
                    VALUES(2,'update','Legacy plan','Legacy plan',?,?)""",
                    (stamp.strftime("%Y-%m-%d %H:%M:%S"), status))
        self.assertEqual(push.flush(self.db), 1)
        self.assertEqual(push.flush(self.db), 0)
        self.assertEqual(len(self.calls), 1)

    def test_legacy_approval_marker_preserved_until_resubmission(self):
        self.plan(11, 2, "2026-10-05", "DA_NOP", submitted="2026-10-05 10:00:00")
        cycle.ensure_schema(self.db)
        with notify._connect(self.db) as c:
            c.execute("INSERT INTO weekly_cycle_notification_events VALUES('PLAN_WAITING_APPROVAL','11',1,'2026-10-05 10:00:00')")
        tuesday = datetime(2026, 10, 6, 10)
        self.assertEqual(cycle.process_cycle_reminders(self.db, tuesday), 0)
        with notify._connect(self.db) as c:
            c.execute("UPDATE weekly_plans SET submitted_at='2026-10-06 11:00:00' WHERE id=11")
        self.assertEqual(cycle.process_cycle_reminders(self.db, tuesday), 1)
        self.assertEqual(push.flush(self.db), 1)

    def test_runtime_worker_dispatches_the_planning_queue(self):
        self.enqueue()
        stop = threading.Event()
        def delivered(**kwargs):
            self.webpush(**kwargs)
            stop.set()
        self.provider.webpush = delivered
        with self.assertLogs("khdn_weekly_notifications", level="INFO") as logs:
            work.worker_loop(self.db, stop, poll_seconds=10)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(any("WEEKLY_NOTIFICATION_SCHEMA_READY" in line for line in logs.output))

    def test_delivery_health_is_read_only_and_excludes_private_data(self):
        self.plan(21, 2, "2026-10-05", "DA_NOP")
        nid = self.enqueue()
        statements = []
        original_connect = work._connect
        def traced(db):
            conn = original_connect(db)
            conn.set_trace_callback(statements.append)
            return conn
        with patch.object(work, "_connect", side_effect=traced):
            health = work.delivery_health(self.db)
        user = next(u for u in health["users"] if u["user_id"] == 2)
        self.assertEqual((user["devices"], user["inbox_plan"], user["last_plan_push"]), (1, 1, "PENDING"))
        self.assertEqual(health["pending_plans"][0]["leader_id"], 1)
        self.assertFalse(any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER")) for s in statements))
        serialized = json.dumps(health)
        for private in ("Staff A", "Leader A", "Planning title", "Planning body", "push.example", "fake-key", "fake-auth"):
            self.assertNotIn(private, serialized)
        self.assertEqual(notify.get_notification(self.db, nid, 2)["push_status"], "PENDING")
        self.assertEqual(self.calls, [])

    def test_admin_room_leader_receives_pending_plans_without_duplicates(self):
        with notify._connect(self.db) as c:
            c.executemany("INSERT INTO users VALUES(?,?,?,?,?,NULL)", [
                (7, "Room leader", "Lãnh đạo phòng", 1, 1),
                (8, "Inactive room leader", "Lãnh đạo phòng", 0, 1),
                (9, "Technical admin", "Cán bộ QLKH", 1, 1),
            ])
        notify.save_subscription(self.db, 7, {"endpoint": "https://push.example.test/7",
                                             "keys": {"p256dh": "fake-key", "auth": "fake-auth"}})
        self.plan(21, 2, "2026-10-05", "DA_NOP", submitted="2026-10-04 06:50:00")
        sunday = datetime(2026, 10, 4, 7)
        self.assertEqual(cycle.process_cycle_reminders(self.db, sunday), 2)
        self.assertEqual(cycle.process_cycle_reminders(self.db, sunday), 0)
        self.assertEqual(self.events(), [("PLAN_WAITING_APPROVAL", 1), ("PLAN_WAITING_APPROVAL", 7)])
        self.assertEqual(push.flush(self.db), 2)
        self.assertEqual({call[0] for call in self.calls}, {"https://push.example.test/1", "https://push.example.test/7"})
        self.assertEqual(len(notify.list_notifications(self.db, 7)), 1)
        self.assertEqual(notify.list_notifications(self.db, 8), [])
        self.assertEqual(notify.list_notifications(self.db, 9), [])
        self.assertEqual(work.delivery_health(self.db)["pending_plans"][0]["recipient_ids"], [1, 7])
        # Fresh work also follows existing room oversight; the baseline prevents
        # replaying historical new-work alerts on this rollout.
        self.assertEqual(work.process_new_work(self.db), [])
        with notify._connect(self.db) as c:
            c.execute("INSERT INTO weekly_plan_items(id,plan_id,user_id,controller_user_id,title,work_date,is_emergent) VALUES(1,21,2,1,'New work','2026-10-05',0)")
        self.assertEqual(len(work.process_new_work(self.db)), 3)
        self.assertEqual(work.process_new_work(self.db), [])
        self.assertEqual(push.flush(self.db), 3)
        with notify._connect(self.db) as c:
            c.execute("UPDATE weekly_plans SET workflow_status='DA_CHOT' WHERE id=21")
        monday = datetime(2026, 10, 5, 10)
        cycle.process_cycle_reminders(self.db, monday)
        self.assertIn(("PLAN_OVERDUE_LEADER", 7), self.events())
        self.assertIn(("MANAGER_REVIEW_PENDING", 7), self.events())
        self.assertIn(("MANAGER_REVIEW_PENDING", 1), self.events())
        self.assertEqual(cycle.process_cycle_reminders(self.db, monday), 0)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PlanningPushQA))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("WEEKLY_PUSH_QA_PASS: real delivery path, fake provider, no user messages sent")
