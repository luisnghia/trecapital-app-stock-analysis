"""Security regression tests with synthetic databases and mocked network only."""
from __future__ import annotations

from datetime import date, timedelta
import gzip
import hashlib
import io
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from cryptography.exceptions import InvalidTag
from khdn_apps import authorization as auth, backup_crypto as crypto
from khdn_apps import customer_work as cases, device_login, device_sessions
from khdn_apps import notifications, password_security as passwords, push_transport as push
from khdn_apps import weekly_plan as weekly, weekly_plan_governance_patch as governance
from khdn_apps.backup_management_patch import create_full_backup_package
from khdn_apps.offline_export_patch import create_offline_package, _source_files
from khdn_apps.security_qa_fixtures import push_keys
from khdn_apps.storage import daily_backup


class State(dict):
    def __getattr__(self, key):
        return self[key]
    def __setattr__(self, key, value):
        self[key] = value


class SecurityQA(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "synthetic.db"
        with self.conn() as c:
            c.executescript("""
                CREATE TABLE users(id INTEGER PRIMARY KEY,username TEXT,full_name TEXT,role TEXT,
                    active INTEGER,is_admin INTEGER,password_hash TEXT,must_change_password INTEGER,deleted_at TEXT);
                INSERT INTO users VALUES
                    (1,'one','Owner','Cán bộ QLKH',1,0,'owner-hash',0,NULL),
                    (2,'two','Other','Cán bộ hỗ trợ',1,0,'other-hash',0,NULL),
                    (3,'leader','Leader','Lãnh đạo phòng',1,0,'leader-hash',0,NULL),
                    (4,'admin','Admin','Lãnh đạo phòng',1,1,'admin-hash',0,NULL);
                CREATE TABLE customers(id INTEGER PRIMARY KEY,cif TEXT,customer_name TEXT,qlkh_user_id INTEGER,active INTEGER);
                INSERT INTO customers VALUES(1,'QA','Synthetic customer',1,1);
                CREATE TABLE tasks(id INTEGER PRIMARY KEY,task_code TEXT,task_type TEXT,due_time TEXT,
                    status TEXT,customer_id INTEGER,qlkh_user_id INTEGER,support_user_id INTEGER);
                INSERT INTO tasks VALUES(1,'QA-1','Synthetic','2026-10-08','OPEN',1,1,1);
            """)
        weekly.ensure_schema(self.conn)
        cases.ensure_schema(self.conn)

    def conn(self):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        return c

    def item(self):
        ws = date(2026, 10, 5)
        weekly.save_items(self.conn, 1, ws, [{"work_date": "2026-10-06", "title": "Synthetic plan"}])
        with self.conn() as c:
            return c.execute("SELECT id FROM weekly_plan_items ORDER BY id DESC").fetchone()[0]

    def user(self, uid=1):
        with self.conn() as c:
            return dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())

    def test_password_version_legacy_migration_and_malformed(self):
        value = passwords.hash_password("QA-password-123")
        self.assertTrue(value.startswith("pbkdf2_sha256$600000$"))
        self.assertTrue(passwords.verify_password("QA-password-123", value))
        self.assertFalse(passwords.verify_password("wrong-password", value))
        salt = "legacy-salt"
        legacy = salt + "$" + hashlib.pbkdf2_hmac("sha256", b"QA-password-123", salt.encode(), 260000).hex()
        self.assertTrue(passwords.verify_password("QA-password-123", legacy))
        self.assertTrue(passwords.needs_upgrade(legacy))
        self.assertFalse(passwords.needs_upgrade(value))
        for malformed in ("", "invalid", "pbkdf2_sha256$99999999999$salt$bad"):
            self.assertFalse(passwords.verify_password("QA-password-123", malformed))

    def test_open_websocket_password_change_revokes_and_clears_drafts(self):
        state = State(user=self.user(), draft="unsaved", khdn_manual_backup_path="old.zip")
        with patch.object(device_login, "st", SimpleNamespace(session_state=state)):
            device_login.begin_session(state.user)
            with self.conn() as c:
                c.execute("UPDATE users SET password_hash='new-hash' WHERE id=1")
            self.assertFalse(device_login._fresh_session_user(self.db))
        self.assertNotIn("user", state)
        self.assertNotIn("draft", state)
        self.assertNotIn("khdn_manual_backup_path", state)
        self.assertEqual(state["_device_command"]["action"], "clear")

    def test_fresh_roles_disable_absolute_expiry_and_remembered_token(self):
        state = State(user=self.user(4))
        with patch.object(device_login, "st", SimpleNamespace(session_state=state)):
            device_login.begin_session(state.user)
            with self.conn() as c:
                c.execute("UPDATE users SET is_admin=0,role='Cán bộ QLKH' WHERE id=4")
            self.assertTrue(device_login._fresh_session_user(self.db))
            self.assertEqual(state.user["is_admin"], 0)
            self.assertEqual(state.user["role"], "Cán bộ QLKH")
            state["_auth_session_expires"] = 1
            self.assertFalse(device_login._fresh_session_user(self.db))
            state.user = self.user()
            device_login.begin_session(state.user)
            with self.conn() as c:
                c.execute("UPDATE users SET active=0 WHERE id=1")
            self.assertFalse(device_login._fresh_session_user(self.db))
        token = device_sessions.redeem(self.db, device_sessions.issue(self.db, self.user(2)))
        self.assertTrue(device_sessions.resolve(self.db, token))
        with self.conn() as c:
            c.execute("UPDATE users SET password_hash='changed' WHERE id=2")
        self.assertIsNone(device_sessions.resolve(self.db, token))

    def test_password_change_preserves_remember_device_preference(self):
        for remembered in (False, True):
            state = State(user=self.user(), _auth_remember_device=remembered)
            with patch.object(device_login, "st", SimpleNamespace(session_state=state)):
                device_login.password_changed(self.db, state.user)
                self.assertTrue(device_login._fresh_session_user(self.db))
            self.assertEqual(state["_device_command"]["action"], "set" if remembered else "clear")

    def test_weekly_ownership_guard_in_core_and_installed_governance(self):
        iid = self.item()
        for action in (
            lambda: weekly.set_status(self.conn, iid, 2, "DONE"),
            lambda: weekly.move_item(self.conn, iid, 2, date(2026, 10, 8)),
            lambda: weekly.add_task(self.conn, 2, date(2026, 10, 5), {"id": 1}, date(2026, 10, 8)),
        ):
            with self.assertRaises(PermissionError): action()
        with self.conn() as c:
            self.assertEqual(c.execute("SELECT status FROM weekly_plan_items WHERE id=?", (iid,)).fetchone()[0], "PLANNED")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM weekly_plan_actions WHERE actor_user_id=2").fetchone()[0], 0)
        # Exercise the actual governance wrapper, then restore the module for other tests.
        names = ("ensure_schema", "save_items", "copy_prev", "add_task", "move_item", "card")
        originals = {name: getattr(weekly, name) for name in names}
        previous = getattr(weekly, "GOVERNANCE_VERSION", None)
        try:
            if previous: del weekly.GOVERNANCE_VERSION
            governance.install(weekly)
            with self.assertRaises(PermissionError):
                weekly.move_item(self.conn, iid, 2, date(2026, 10, 8))
            self.assertEqual(weekly.move_item(self.conn, iid, 1, date(2026, 10, 8)), "PENDING")
        finally:
            for name, value in originals.items(): setattr(weekly, name, value)
            if previous: weekly.GOVERNANCE_VERSION = previous
            elif hasattr(weekly, "GOVERNANCE_VERSION"): del weekly.GOVERNANCE_VERSION

    def test_case_ownership_and_inactive_leader_denied_without_writes(self):
        cid, _ = cases.create_case(self.conn, 3, 1, "Synthetic case", owner_uid=1)
        with self.conn() as c:
            stage = c.execute("SELECT id FROM work_stage_catalog WHERE active=1 LIMIT 1").fetchone()[0]
            before = c.execute("SELECT COUNT(*) FROM case_actions").fetchone()[0]
        for action in (
            lambda: cases.change_stage(self.conn, cid, 2, stage),
            lambda: cases.add_issue(self.conn, cid, 2, "forged"),
            lambda: cases.request_reschedule(self.conn, cid, 2, "2026-10-20", "forged"),
            lambda: cases.create_case(self.conn, 2, 1, "forged owner", owner_uid=1),
        ):
            with self.assertRaises(PermissionError): action()
        issue = cases.add_issue(self.conn, cid, 1, "Synthetic issue")
        with self.assertRaises(PermissionError): cases.resolve_issue(self.conn, issue, 2)
        with self.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM case_actions").fetchone()[0], before + 1)
            c.execute("UPDATE users SET active=0 WHERE id=3")
        with self.assertRaises(PermissionError): cases.approve_case_plan(self.conn, cid, 3)

    def test_export_fresh_admin_gate_ignores_stale_ui_flags(self):
        self.assertEqual(auth.require_admin(self.db, 4)["id"], 4)
        for uid in (1, 2, 3):
            with self.assertRaises(PermissionError): auth.require_admin(self.db, uid)
        with self.conn() as c: c.execute("UPDATE users SET is_admin=0 WHERE id=4")
        with self.assertRaises(PermissionError): auth.require_admin(self.db, 4)

    def test_push_origins_keys_private_dns_and_redirects_blocked(self):
        valid = {"endpoint": "https://fcm.googleapis.com/fcm/send/synthetic", "keys": push_keys()}
        push.validate_subscription(valid)
        for endpoint in ("https://127.0.0.1/x", "https://169.254.169.254/x", "https://evil.example/x",
                         "http://fcm.googleapis.com/x", "https://user@fcm.googleapis.com/x",
                         "https://fcm.googleapis.com:8080/x", "https://fcm.googleapis.com.evil.example/x"):
            with self.assertRaises(ValueError): push.endpoint_parts(endpoint)
        with self.assertRaises(ValueError): push.validate_subscription({"endpoint": valid["endpoint"], "keys": {"p256dh": "bad", "auth": "bad"}})
        private = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch.object(socket, "getaddrinfo", return_value=private), patch.object(socket, "create_connection") as connection:
            with self.assertRaises(ValueError): push.SafePushSession().post(valid["endpoint"], data=b"synthetic")
            connection.assert_not_called()
        response = SimpleNamespace(status=302, getheaders=lambda: [("Location", "https://127.0.0.1/")], read=lambda n: b"")
        connection = SimpleNamespace(request=lambda *a, **k: None, getresponse=lambda: response, close=lambda: None)
        with patch.object(push, "public_addresses", return_value=["8.8.8.8"]), patch.object(push, "_PinnedTLS", return_value=connection) as pinned:
            with self.assertRaises(ValueError): push.SafePushSession().post(valid["endpoint"], data=b"synthetic")
            pinned.assert_called_once_with("fcm.googleapis.com", "8.8.8.8", 10.0)

    def test_setup_ticket_revoked_by_password_change_and_disable(self):
        with patch.dict(os.environ, {"KHDN_PUSH_TOKEN_SECRET": "QA-ticket-secret-never-production"}):
            ticket = notifications.issue_setup_ticket(1, db_path=self.db)
            self.assertEqual(notifications.verify_setup_ticket(ticket, db_path=self.db), 1)
            with self.conn() as c: c.execute("UPDATE users SET password_hash='changed' WHERE id=1")
            self.assertIsNone(notifications.verify_setup_ticket(ticket, db_path=self.db))
            ticket = notifications.issue_setup_ticket(1, db_path=self.db)
            with self.conn() as c: c.execute("UPDATE users SET active=0 WHERE id=1")
            self.assertIsNone(notifications.verify_setup_ticket(ticket, db_path=self.db))

    def test_portable_encryption_wrong_password_tamper_and_recovery(self):
        password = "QA-strong-file-password"
        target = create_full_backup_package(self.db, self.root / "backup.zip", password=password)
        with zipfile.ZipFile(target) as outer:
            self.assertNotIn("khdn_ops.db", outer.namelist())
            self.assertNotIn("tables/users.csv", outer.namelist())
            sealed = outer.read("backup.khdn")
        with self.assertRaises(InvalidTag): crypto.decrypt(sealed, password="wrong-file-password")
        with self.assertRaises(InvalidTag): crypto.decrypt(sealed[:-1] + bytes([sealed[-1] ^ 1]), password=password)
        payload = crypto.decrypt(sealed, password=password, kind="portable-backup")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertIn(b"owner-hash", archive.read("khdn_ops.db"))
            self.assertNotIn("password_hash", archive.read("tables/users.csv").decode("utf-8-sig"))
        restored = crypto.restore_portable(target, self.root / "restored", password)
        with sqlite3.connect(restored / "khdn_ops.db") as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with self.assertRaises(ValueError): crypto.restore_portable(target, restored, password)
        extracted = self.root / "extracted"
        with zipfile.ZipFile(target) as outer:
            outer.extractall(extracted)
            self.assertIn(b'backup.khdn', outer.read("DECRYPT_BACKUP.bat"))
        crypto.restore_portable(extracted / "backup.khdn", self.root / "restored-from-extracted", password)

    def test_actual_pywebpush_encrypts_signs_and_uses_pinned_transport(self):
        from py_vapid import Vapid
        from pywebpush import webpush
        vapid = Vapid()
        vapid.generate_keys()
        response = SimpleNamespace(status=201, getheaders=lambda: [], read=lambda n: b"")
        calls = []
        connection = SimpleNamespace(request=lambda *a, **k: calls.append((a, k)),
                                     getresponse=lambda: response, close=lambda: None)
        subscription = {"endpoint": "https://fcm.googleapis.com/fcm/send/synthetic", "keys": push_keys()}
        with patch.object(push, "public_addresses", return_value=["8.8.8.8"]), patch.object(push, "_PinnedTLS", return_value=connection):
            result = webpush(subscription, data='{"test":"synthetic"}', vapid_private_key=vapid,
                             vapid_claims={"sub": "mailto:qa@example.invalid"}, ttl=60, timeout=10,
                             requests_session=push.SafePushSession())
        self.assertEqual(result.status_code, 201)
        self.assertEqual(calls[0][0][:2], ("POST", "/fcm/send/synthetic"))
        self.assertNotIn(b"synthetic", calls[0][1]["body"])
        self.assertTrue(any(key.lower() == "authorization" for key in calls[0][1]["headers"]))

    def test_automatic_backup_encrypts_committed_wal_and_legacy_migration(self):
        with patch.dict(os.environ, {"KHDN_CLOUD_MODE": "0", "KHDN_BACKUP_ENCRYPTION_KEY": ""}):
            with self.conn() as c:
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("UPDATE customers SET customer_name='Newest committed value' WHERE id=1")
                c.commit()
                target = daily_backup(self.root, self.db)
            key = crypto.server_key(self.root)
            restored = self.root / "restored.db"
            restored.write_bytes(gzip.decompress(crypto.decrypt(target.read_bytes(), key=key, kind="daily-backup")))
            with sqlite3.connect(restored) as c:
                self.assertEqual(c.execute("SELECT customer_name FROM customers WHERE id=1").fetchone()[0], "Newest committed value")
            old = self.root / "backups" / "legacy.db.gz"
            old.write_bytes(b"synthetic-legacy-snapshot")
            self.assertEqual(crypto.migrate_legacy_backups(self.root), 1)
            self.assertFalse(old.exists())
            self.assertEqual(crypto.decrypt(old.with_name(old.name + ".khdn").read_bytes(), key=key), b"synthetic-legacy-snapshot")
            self.assertEqual(crypto.migrate_legacy_backups(self.root), 0)

    def test_offline_unlock_source_secrets_excluded_and_localhost_binding(self):
        source = self.root / "source"
        source.mkdir()
        (source / "requirements.txt").write_text("cryptography\n")
        for name in (".env", "private.pem", "private.key", ".backup-encryption.key", "secrets.toml"):
            (source / name).write_text("SYNTHETIC-SECRET")
        self.assertEqual([str(rel) for _, rel in _source_files(source)], ["requirements.txt"])
        target = create_offline_package(self.root, self.db, self.root / "offline.zip", source_dir=source, password="QA-offline-password")
        offline = self.root / "offline"
        with zipfile.ZipFile(target) as archive:
            self.assertNotIn("data/khdn_ops.db", archive.namelist())
            archive.extractall(offline)
        with self.assertRaises(InvalidTag): crypto.unlock_offline(offline, "wrong-file-password")
        self.assertFalse((offline / "data" / "khdn_ops.db").exists())
        database = crypto.unlock_offline(offline, "QA-offline-password")
        self.assertEqual(crypto.unlock_offline(offline), database)
        with sqlite3.connect(database) as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        runtime = Path(__file__).with_name("runtime.py").read_text()
        self.assertIn('"127.0.0.1" if os.getenv("KHDN_CLOUD_MODE"', runtime)

    def test_installed_source_guards_and_no_extra_login_controls(self):
        app = Path(__file__).with_name("app.py")
        if "_security_patch_source" not in app.read_text():
            self.skipTest("Raw checkout; installed-image gate runs after install_security")
        namespace = {"__file__": str(app), "__name__": "security_source_qa"}
        exec(compile(app.read_text().split("exec(compile(_source, ", 1)[0], str(app), "exec"), namespace)
        source = namespace["_source"]
        self.assertNotIn("_user_last_validated_mono", source[source.index("def app():"):])
        self.assertIn("device_login.begin_session", source)
        self.assertIn("device_login.password_changed", source)
        self.assertIn("encrypted_snapshot", source)
        self.assertIn("require_admin(DB_PATH", source)
        self.assertNotIn("Tải backup SQLite hiện tại", source)
        self.assertNotIn("scheduled_backup_download", source)
        compile(source, "<secured-installed-engine>", "exec")


if __name__ == "__main__":
    unittest.main(verbosity=2)
