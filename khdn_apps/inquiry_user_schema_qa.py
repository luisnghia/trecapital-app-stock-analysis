"""Regression QA: role CHECK migration preserves user IDs, history and FK references."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from khdn_apps.inquiry_user_schema import ensure_inquiry_user_schema


_OLD_DDL = """CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('Cán bộ hỗ trợ','Cán bộ QLKH','Lãnh đạo phòng')),
    is_admin INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT,
    deleted_at TEXT
)"""


def initialize(path, with_index=True):
    with sqlite3.connect(path) as c:
        c.execute("PRAGMA foreign_keys=ON")
        c.execute(_OLD_DDL)
        c.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY, qlkh_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE)")
        c.execute("CREATE TABLE tasks(id INTEGER PRIMARY KEY, support_user_id INTEGER REFERENCES users(id), qlkh_user_id INTEGER REFERENCES users(id))")
        c.execute("CREATE TABLE weekly_plan_items(id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id))")
        c.execute("CREATE TABLE audit_events(id INTEGER PRIMARY KEY, actor_user_id INTEGER REFERENCES users(id))")
        if with_index:
            c.execute("CREATE INDEX idx_users_role_active ON users(role,active)")
            c.execute("""CREATE TRIGGER trg_users_change AFTER UPDATE OF full_name ON users
                         BEGIN INSERT INTO audit_events(actor_user_id) VALUES(NEW.id); END""")
        for id, username, role in [(1,"admin","Lãnh đạo phòng"),(4,"hoalq","Cán bộ QLKH"),(12,"support","Cán bộ hỗ trợ")]:
            c.execute("""INSERT INTO users(id,username,full_name,password_hash,role,created_at,updated_at)
                         VALUES(?,?,?,?,?,'2026-10-27','2026-10-27')""", (id,username,username,"existing-password-hash",role))
        c.execute("INSERT INTO customers VALUES(100,4)")
        c.execute("INSERT INTO tasks VALUES(200,12,4)")
        c.execute("INSERT INTO weekly_plan_items VALUES(300,4)")
        c.execute("INSERT INTO audit_events VALUES(400,1)")
        c.execute("UPDATE sqlite_sequence SET seq=1000 WHERE name='users'")


def qa_preserve_full_database():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"users.db"
        initialize(p)
        with sqlite3.connect(p) as c:
            before=c.execute("SELECT * FROM users ORDER BY id").fetchall()
            refs=[c.execute("SELECT * FROM "+t).fetchall() for t in
                  ("customers","tasks","weekly_plan_items","audit_events")]
            before_schema={r[0]:r[1] for r in c.execute(
                "SELECT name,sql FROM sqlite_master WHERE tbl_name='users' AND type IN ('index','trigger') AND sql IS NOT NULL")}
            before_seq=c.execute("SELECT seq FROM sqlite_sequence WHERE name='users'").fetchone()[0]
            try:
                c.execute("""INSERT INTO users(username,full_name,password_hash,role,created_at,updated_at)
                  VALUES('newviewer','viewer','hash','Vấn tin','now','now')""")
            except sqlite3.IntegrityError as e:
                assert "CHECK constraint failed" in str(e), e
            else:
                raise AssertionError("Original 3-role check unexpectedly accepts Vấn tin")
        assert ensure_inquiry_user_schema(p) is True
        with sqlite3.connect(p) as c:
            c.execute("PRAGMA foreign_keys=ON")
            assert c.execute("SELECT * FROM users ORDER BY id").fetchall() == before
            assert [c.execute("SELECT * FROM "+t).fetchall() for t in
                    ("customers","tasks","weekly_plan_items","audit_events")] == refs
            assert c.execute("PRAGMA foreign_key_check").fetchall() == []
            actual_schema={r[0]:r[1] for r in c.execute(
                "SELECT name,sql FROM sqlite_master WHERE tbl_name='users' AND type IN ('index','trigger') AND sql IS NOT NULL")}
            assert actual_schema==before_schema, (actual_schema,before_schema)
            assert c.execute("SELECT seq FROM sqlite_sequence WHERE name='users'").fetchone()[0]==before_seq
            # Existing users still authenticate with the very same saved hashes;
            # no passwords/IDs or cross-table references have been rewritten.
            assert c.execute("SELECT password_hash FROM users WHERE id=4").fetchone()[0]=="existing-password-hash"
            c.execute("""INSERT INTO users(username,full_name,password_hash,role,created_at,updated_at)
                      VALUES('hoangnx','NGUYEN XUAN HOANG','new-hash','Vấn tin','now','now')""")
            new_id=c.execute("SELECT id FROM users WHERE username='hoangnx'").fetchone()[0]
            assert new_id>1000
            assert c.execute("SELECT role FROM users WHERE id=?", (new_id,)).fetchone()[0]=="Vấn tin"
            c.execute("UPDATE users SET full_name='new name' WHERE id=4")
            assert c.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]==2
            try:
                c.execute("""INSERT INTO users(username,full_name,password_hash,role,created_at,updated_at)
                         VALUES('BAD','BAD','hash','unknown','now','now')""")
            except sqlite3.IntegrityError: pass
            else: raise AssertionError("Invalid role accepted")
            try:
                c.execute("""INSERT INTO users(username,full_name,password_hash,role,created_at,updated_at)
                         VALUES('hoangnx','BAD','hash','Vấn tin','now','now')""")
            except sqlite3.IntegrityError: pass
            else: raise AssertionError("Duplicate username accepted")
        assert ensure_inquiry_user_schema(p) is False
        with sqlite3.connect(p) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
            assert c.execute("PRAGMA foreign_key_check").fetchall()==[]
            assert c.execute("SELECT COUNT(*) FROM users").fetchone()[0]==4


def qa_reject_unknown_schema_without_changes():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"different.db"
        with sqlite3.connect(p) as c:
            c.execute("CREATE TABLE users (id INTEGER PRIMARY KEY,username TEXT,role TEXT)")
            c.execute("INSERT INTO users VALUES(1,'admin','Lãnh đạo phòng')")
        try: ensure_inquiry_user_schema(p)
        except RuntimeError as e: assert "không khớp" in str(e)
        else: raise AssertionError("Unknown schema should fail closed")
        with sqlite3.connect(p) as c:
            assert c.execute("SELECT * FROM users").fetchall()==[(1,"admin","Lãnh đạo phòng")]
            assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='__users_inquiry_role_upgrade_v1'").fetchone()


def qa_app_hook_and_error_messages():
    root=Path(__file__).parent
    app=(root/"app.py").read_text(encoding="utf-8")
    admin=(root/"mobile_admin_restore_perf_patch.py").read_text(encoding="utf-8")
    assert "ensure_inquiry_user_schema(DB_PATH, LOGGER)" in app
    assert '_inquiry_user_schema_checked_v1' in app
    assert "if role not in roles:" in admin
    assert "Cơ sở dữ liệu chưa chấp nhận nhóm quyền này." in admin
    assert "unique constraint failed: users.username" in admin
    assert "Tên đăng nhập đã tồn tại. Vui lòng chọn tên khác." in admin
    assert 'st.error("Username đã tồn tại.")' not in admin


if __name__=="__main__":
    qa_preserve_full_database()
    qa_reject_unknown_schema_without_changes()
    qa_app_hook_and_error_messages()
    print("INQUIRY_USER_SCHEMA_QA_PASS existing_ids_passwords_accounts_unchanged FK child_tables audit_indexes_triggers sequence preserved viewer_insert login_role unknown_role_rejected idempotent fail_closed accurate_errors")
