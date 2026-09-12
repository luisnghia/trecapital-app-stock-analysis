import base64
from contextlib import closing
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from khdn_apps.storage import (daily_backup, prepare_storage, read_status,
                               restore_once, snapshot_database, sqlite_backup_bytes)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "khdn_ops.db"
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA wal_autocheckpoint=0")
        self.conn.executescript("""
            CREATE TABLE users(id INTEGER PRIMARY KEY, avatar BLOB);
            CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE tasks(id INTEGER PRIMARY KEY, amount INTEGER);
            INSERT INTO users VALUES(1, X'010203');
            INSERT INTO customers VALUES(1, 'Khách hàng kiểm thử');
            INSERT INTO tasks VALUES(1, 100);
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def payload(self):
        raw = sqlite_backup_bytes(self.db)
        return base64.b64encode(gzip.compress(raw)).decode(), hashlib.sha256(raw).hexdigest()

    def test_snapshot_includes_committed_wal_and_avatar(self):
        self.conn.execute("INSERT INTO tasks VALUES(2, 900)")
        self.conn.commit()
        self.assertGreater(Path(str(self.db) + "-wal").stat().st_size, 32)
        target = snapshot_database(self.db, self.root / "copy.db")
        with closing(sqlite3.connect(target)) as copy:
            self.assertEqual(copy.execute("SELECT SUM(amount) FROM tasks").fetchone()[0], 1000)
            self.assertEqual(copy.execute("SELECT avatar FROM users").fetchone()[0], b"\x01\x02\x03")
            self.assertEqual(copy.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_restore_is_verified_and_never_overwrites_subsequent_work(self):
        payload, digest = self.payload()
        target_dir = self.root / "volume"
        target_dir.mkdir()
        target = target_dir / "khdn_ops.db"
        self.assertTrue(restore_once(target_dir, target, payload, digest))
        with closing(sqlite3.connect(target)) as conn:
            conn.execute("INSERT INTO tasks VALUES(2, 800)")
            conn.commit()
        self.assertFalse(restore_once(target_dir, target, payload, digest))
        with closing(sqlite3.connect(target)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 2)

    def test_restore_rejects_bad_hash_without_installing_database(self):
        payload, _ = self.payload()
        folder = self.root / "bad"
        folder.mkdir()
        with self.assertRaises(ValueError):
            restore_once(folder, folder / "khdn_ops.db", payload, "0" * 64)
        self.assertFalse((folder / "khdn_ops.db").exists())

    def test_restore_refuses_unrelated_existing_database(self):
        payload, digest = self.payload()
        self.conn.execute("INSERT INTO tasks VALUES(2, 200)")
        self.conn.commit()
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        with self.assertRaises(RuntimeError):
            restore_once(self.root, self.db, payload, digest)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 2)

    def test_mount_guard_and_path_guard(self):
        with patch("khdn_apps.storage.is_volume_mount", return_value=False):
            with self.assertRaises(RuntimeError):
                prepare_storage(self.root, self.db, require_volume=True)
        with self.assertRaises(RuntimeError):
            prepare_storage(self.root / "other", self.db, require_volume=False)

    def test_restart_preserves_storage_identity_and_rows(self):
        with patch.dict(os.environ, {"KHDN_MIGRATION_DB_GZIP_BASE64": ""}):
            first = prepare_storage(self.root, self.db, require_volume=False)
            self.conn.execute("INSERT INTO tasks VALUES(2, 300)")
            self.conn.commit()
            second = prepare_storage(self.root, self.db, require_volume=False)
        self.assertEqual(first["storage_id"], second["storage_id"])
        self.assertEqual(second["counts_at_start"]["tasks"], 2)
        for folder in ("logs", "annual_archive", "backups"):
            self.assertTrue((self.root / folder).is_dir())

    def test_daily_retention_and_gzip_integrity(self):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        for offset in range(18):
            latest = daily_backup(self.root, self.db, now=start + timedelta(days=offset))
        files = list((self.root / "backups").glob("*.db.gz"))
        self.assertEqual(len(files), 14)
        restored = self.root / "restored.db"
        restored.write_bytes(gzip.decompress(latest.read_bytes()))
        with closing(sqlite3.connect(restored)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        self.assertEqual(read_status(self.root / "backup_status.json")["location"], "same_volume")

    def test_failed_backup_keeps_existing_copy_and_live_data(self):
        today = datetime(2026, 9, 1, tzinfo=timezone.utc)
        first = daily_backup(self.root, self.db, now=today)
        original = first.read_bytes()
        with self.assertRaises(OSError):
            daily_backup(self.root, self.db, now=today + timedelta(days=1), budget_bytes=1)
        self.assertEqual(first.read_bytes(), original)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
        self.assertEqual(len(list((self.root / "backups").glob("*.db.gz"))), 1)


if __name__ == "__main__":
    unittest.main()
