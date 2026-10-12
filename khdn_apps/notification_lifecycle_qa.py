"""Regressions for native dialog dismissal and 24-hour read-inbox retention.

Uses isolated databases and Streamlit's real widget-dismissal event; no Push is sent.
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from khdn_apps import notifications as notify, weekly_push

NOW = "2026-10-12 16:00:00"
EXPIRED = "2026-10-11 15:59:59"
BOUNDARY = "2026-10-11 16:00:00"
RECENT = "2026-10-11 16:00:01"
ROLES = ("Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng", "Admin")


class NotificationLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="khdn-notification-lifecycle-")
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "qa.db"
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,role TEXT,active INTEGER,is_admin INTEGER);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY);
                CREATE TABLE task_actions(id INTEGER PRIMARY KEY,task_id INTEGER);
                INSERT INTO tasks VALUES(1);
                INSERT INTO task_actions VALUES(1,1);
            """)
            c.executemany("INSERT INTO users VALUES(?,?,1,?)",
                          [(uid, role, int(role == "Admin")) for uid, role in enumerate(ROLES, 1)])
        notify.ensure_schema(self.db)
        self.clock = patch.object(notify, "_now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def add_notification(self, uid=1, read_at=None, created_at="2026-01-01 08:00:00"):
        with notify._connect(self.db) as c:
            cur = c.execute("""INSERT INTO notifications
                (user_id,task_id,event_key,title,body,created_at,read_at,push_status)
                VALUES(?,1,'update','Thông báo QA','Nội dung QA',?,?,'SENT')""",
                (uid, created_at, read_at))
            return int(cur.lastrowid)

    def ids(self):
        with notify._connect(self.db) as c:
            return {int(row[0]) for row in c.execute("SELECT id FROM notifications")}

    def test_exact_24_hours_all_roles_preserves_unread_and_recently_read(self):
        deleted, kept = set(), set()
        for uid in range(1, 5):
            deleted.update((self.add_notification(uid, EXPIRED), self.add_notification(uid, BOUNDARY)))
            kept.update((self.add_notification(uid, RECENT), self.add_notification(uid, NOW),
                         self.add_notification(uid)))
        self.assertEqual(notify.cleanup_read_notifications(self.db), len(deleted))
        self.assertEqual(self.ids(), kept)
        self.assertEqual(notify.cleanup_read_notifications(self.db), 0)
        for uid in range(1, 5):
            self.assertEqual(notify.unread_count(self.db, uid), 1)

    def test_scoped_cleanup_and_read_cannot_affect_other_users(self):
        mine = self.add_notification(1, EXPIRED)
        other = self.add_notification(2, EXPIRED)
        unread_other = self.add_notification(2)
        notify.mark_read(self.db, unread_other, 1)
        self.assertEqual(notify.cleanup_read_notifications(self.db, user_id=1), 1)
        self.assertNotIn(mine, self.ids())
        self.assertIn(other, self.ids())
        self.assertEqual(notify.unread_count(self.db, 2), 1)

    def test_reopening_or_mark_all_does_not_restart_retention(self):
        old = self.add_notification(1, EXPIRED)
        fresh = self.add_notification(1)
        notify.mark_read(self.db, old, 1)
        notify.mark_all_read(self.db, 1)
        with notify._connect(self.db) as c:
            rows = dict(c.execute("SELECT id,read_at FROM notifications"))
        self.assertEqual(rows[old], EXPIRED)
        self.assertEqual(rows[fresh], NOW)
        self.assertEqual(notify.cleanup_read_notifications(self.db), 1)
        self.assertEqual(self.ids(), {fresh})

    def test_list_prunes_offline_and_expired_deep_links_do_not_reopen(self):
        old = self.add_notification(1, BOUNDARY)
        fresh = self.add_notification(1, NOW)
        other = self.add_notification(2, EXPIRED)
        self.assertIsNone(notify.get_notification(self.db, old, 1))
        self.assertIsNone(notify.get_notification(self.db, fresh, 2))
        self.assertEqual([row["id"] for row in notify.list_notifications(self.db, 1)], [fresh])
        self.assertEqual(self.ids(), {fresh, other})

    def test_cleanup_cascades_push_queue_preserves_delivery_and_work_journals(self):
        old = self.add_notification(1, EXPIRED)
        with notify._connect(self.db) as c:
            weekly_push.ensure_tables(c)
            c.execute("""INSERT INTO weekly_push_queue(notification_id,event_code,state,expires_at,updated_at)
                         VALUES(?,'QA','SENT',0,?)""", (old, EXPIRED))
            weekly_push._audit(c, old, 1, "QA", "DELIVERED")
            c.execute("INSERT INTO notification_sla_events VALUES(1,1,'SLA_OVERDUE',?)", (EXPIRED,))
        self.assertEqual(notify.cleanup_read_notifications(self.db), 1)
        with notify._connect(self.db) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM weekly_push_queue").fetchone()[0], 0)
            for table in ("task_actions", "notification_sla_events", "weekly_push_audit"):
                self.assertEqual(c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 1)
            self.assertEqual(notify._state_get(c, "last_action_id"), "1")
            self.assertEqual(c.execute("PRAGMA foreign_key_check").fetchall(), [])
            index = c.execute("SELECT name FROM sqlite_master WHERE name='idx_notifications_read_at'").fetchone()
            self.assertIsNotNone(index)

    def test_worker_cleans_without_any_open_page_and_delivery_errors_do_not_block_it(self):
        self.add_notification(4, EXPIRED)
        from khdn_apps import customer_work_notifications, planning_work_notifications

        class StopAfterThreePolls:
            polls = 0
            def is_set(self):
                return self.polls >= 3
            def wait(self, timeout):
                self.polls += 1

        with (patch.object(customer_work_notifications, "ensure_schema"),
              patch.object(planning_work_notifications, "ensure_schema"),
              patch.object(notify, "process_task_actions", side_effect=RuntimeError("QA delivery failure")),
              patch.object(notify.time, "monotonic", side_effect=(100.0, 130.0, 161.0)),
              patch.object(notify, "cleanup_read_notifications", wraps=notify.cleanup_read_notifications) as cleanup,
              self.assertLogs(notify.LOGGER, level="INFO") as logs):
            notify.worker_loop(self.db, StopAfterThreePolls())
        self.assertEqual(cleanup.call_count, 2)
        self.assertEqual(self.ids(), set())
        self.assertTrue(any("NOTIFICATION_RETENTION_READY" in entry for entry in logs.output))
        self.assertTrue(any("NOTIFICATION_READ_CLEANUP deleted=1" in entry for entry in logs.output))

    def test_realtime_token_changes_when_older_read_rows_are_deleted(self):
        from khdn_apps import notification_ui_patch as ui
        self.add_notification(1, EXPIRED)
        self.add_notification(1)  # Highest ID and unread count remain unchanged.
        ns = dict(st=None, DB_PATH=self.db, sidebar_user=lambda user: None,
                  get_conn=lambda: notify._connect(self.db),
                  _visible_task_change_token=lambda user: "qa-base")
        ui.install(ns)
        token = ns["_visible_task_change_token"]
        before = token({"id": 1})
        notify.cleanup_read_notifications(self.db)
        self.assertNotEqual(token({"id": 1}), before)

    def test_streamlit_native_dismissal_stays_closed_across_navigation_all_roles(self):
        from streamlit.testing.v1 import AppTest
        for uid, role in enumerate(ROLES, 1):
            with self.subTest(role=role):
                user = {"id": uid, "role": role, "is_admin": role == "Admin"}
                script = f"""
import streamlit as st
from khdn_apps import notification_ui_patch as ui
ns = dict(st=st, DB_PATH={str(self.db)!r}, CLOUD_MODE=False,
          sidebar_user=lambda user: None, fmt_dt=lambda value: value)
ui.install(ns)
if st.button('Chuyển trang', key='qa_change_page'):
    st.session_state['qa_page'] = st.session_state.get('qa_page', 0) + 1
ns['sidebar_user']({user!r})
st.write('Trang', st.session_state.get('qa_page', 0))
"""
                page = AppTest.from_string(script, default_timeout=20).run()
                self.assertFalse(page.exception)
                page.button(key="khdn_notification_center_btn").click().run()
                self.assertFalse(page.exception)
                self.assertTrue(page.session_state["_khdn_notification_dialog_open"])
                # Native X / Escape / backdrop all dispatch this same dialog trigger.
                dialogs = page.get("dialog")
                self.assertEqual(len(dialogs), 1)
                dialog_id = dialogs[0].proto.dialog.id
                self.assertTrue(dialog_id, "Dismissal was not registered with Streamlit")
                page.session_state["_khdn_notification_selected"] = 987
                states = page._tree.get_widget_states()
                states.widgets.add(id=dialog_id, trigger_value=True)
                page._run(widget_state=states)
                self.assertFalse(page.exception)
                self.assertFalse(page.session_state["_khdn_notification_dialog_open"])
                self.assertNotIn("_khdn_notification_selected", page.session_state)
                for _ in range(3):
                    page.button(key="qa_change_page").click().run()
                    self.assertFalse(page.exception)
                    self.assertFalse(page.get("dialog"))
                # Opening remains explicit and the bottom Close uses the same reset.
                page.button(key="khdn_notification_center_btn").click().run()
                self.assertEqual(len(page.get("dialog")), 1)
                page.button(key="close_notification_dialog").click().run()
                self.assertFalse(page.exception)
                self.assertFalse(page.session_state["_khdn_notification_dialog_open"])
                page.button(key="qa_change_page").click().run()
                self.assertFalse(page.get("dialog"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
