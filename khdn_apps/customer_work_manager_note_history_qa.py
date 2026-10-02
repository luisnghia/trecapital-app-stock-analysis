from __future__ import annotations

import sqlite3
from pathlib import Path

from khdn_apps import customer_work_manager_note_history_patch as patch


class ConnFactory:
    def __init__(self, c):
        self.c = c
    def __call__(self):
        return _ConnCtx(self.c)


class _ConnCtx:
    def __init__(self, c):
        self.c = c
    def __enter__(self):
        return self.c
    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.c.rollback()
        else:
            self.c.commit()
        return False


c = sqlite3.connect(":memory:")
c.row_factory = sqlite3.Row
c.executescript(
    """
CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER);
CREATE TABLE customer_work_cases(
 id INTEGER PRIMARY KEY,note TEXT,updated_at TEXT,
 plan_approval_status TEXT,plan_approved_by INTEGER,plan_approved_at TEXT,
 plan_rejected_by INTEGER,plan_rejected_at TEXT,approval_note TEXT
);
CREATE TABLE case_actions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER,actor_user_id INTEGER,
 action TEXT,detail TEXT,created_at TEXT
);
"""
)
c.execute("INSERT INTO users VALUES(1,'Lãnh đạo A','Lãnh đạo phòng',0,1)")
c.execute("INSERT INTO users VALUES(2,'Admin B','Cán bộ QLKH',1,1)")
c.execute("INSERT INTO users VALUES(3,'QLKH C','Cán bộ QLKH',0,1)")
c.execute("INSERT INTO customer_work_cases VALUES(10,'Ghi chú cũ',NULL,'APPROVED',1,'2026-10-01 08:00:00',NULL,NULL,'Đồng ý triển khai')")
c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(10,1,'PLAN_APPROVE','Đồng ý triển khai','2026-10-01 08:00:00')")
c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(10,2,'RESCHEDULE_DECISION','{\"status\":\"APPROVED\",\"note\":\"Gia hạn theo đề nghị KH\"}','2026-10-02 09:00:00')")
c.commit()
get_conn = ConnFactory(c)

assert patch.update_case_note(get_conn, 10, 1, "Ghi chú lãnh đạo mới") is True
r = c.execute("SELECT note FROM customer_work_cases WHERE id=10").fetchone()
assert r[0] == "Ghi chú lãnh đạo mới"
a = c.execute("SELECT action,detail FROM case_actions WHERE case_id=10 ORDER BY id DESC LIMIT 1").fetchone()
assert a[0] == "NOTE_EDIT"
assert "Ghi chú cũ" in a[1] and "Ghi chú lãnh đạo mới" in a[1]

assert patch.update_case_note(get_conn, 10, 2, "Ghi chú Admin") is True
try:
    patch.update_case_note(get_conn, 10, 3, "Không được phép")
    raise AssertionError("QLKH must not edit manager note")
except PermissionError:
    pass

hist = patch.approval_history(c, 10)
assert any(x["action"] == "Phê duyệt công việc" and x["comment"] == "Đồng ý triển khai" for x in hist)
assert any(x["action"] == "Phê duyệt dời thời gian" and x["comment"] == "Gia hạn theo đề nghị KH" for x in hist)
assert any(x["action"] == "Chỉnh sửa Ghi chú công việc" and x["comment"] == "Ghi chú Admin" for x in hist)

src = Path(patch.__file__).read_text(encoding="utf-8")
for token in [
    "Chỉ Lãnh đạo phòng/Admin được chỉnh sửa Ghi chú công việc khách hàng",
    "NOTE_EDIT",
    "Ý kiến / Ghi chú của Lãnh đạo/Admin",
    "Lịch sử phê duyệt / thay đổi",
    "approval_comment_history=1",
    "data_migration=0",
]:
    assert token in src, token

print(
    "CUSTOMER_WORK_MANAGER_NOTE_HISTORY_QA_PASS "
    "leader_edit=1 admin_edit=1 qlkh_blocked=1 note_audit=1 "
    "plan_comment_history=1 reschedule_comment_history=1 data_migration=0"
)
