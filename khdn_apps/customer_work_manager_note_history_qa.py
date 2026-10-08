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
CREATE TABLE case_reschedule_requests(
 id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER,old_due_at TEXT,proposed_due_at TEXT,
 reason TEXT,status TEXT,decided_by INTEGER,decided_at TEXT,decision_note TEXT
);
"""
)
c.execute("INSERT INTO users VALUES(1,'Lãnh đạo A','Lãnh đạo phòng',0,1)")
c.execute("INSERT INTO users VALUES(2,'Admin B','Cán bộ QLKH',1,1)")
c.execute("INSERT INTO users VALUES(3,'QLKH C','Cán bộ QLKH',0,1)")
c.execute("INSERT INTO customer_work_cases VALUES(10,'Ghi chú cũ',NULL,'APPROVED',1,'2026-10-01 08:00:00',NULL,NULL,'Đồng ý triển khai')")
c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(10,1,'PLAN_APPROVE','Đồng ý triển khai','2026-10-01 08:00:00')")
# Both request row + legacy action exist: rendered history must use request as authoritative and not duplicate it.
c.execute("""INSERT INTO case_reschedule_requests(case_id,old_due_at,proposed_due_at,reason,status,decided_by,decided_at,decision_note)
             VALUES(10,'2026-10-05 17:00:00','2026-10-08 17:00:00','Khách hàng bổ sung hồ sơ','APPROVED',2,'2026-10-02 09:00:00','Gia hạn theo đề nghị KH')""")
c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(10,2,'RESCHEDULE_DECISION','{\"status\":\"APPROVED\",\"note\":\"Gia hạn theo đề nghị KH\"}','2026-10-02 09:00:00')")
c.commit()
get_conn = ConnFactory(c)

assert patch.VERSION == "1.2.0"
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
reschedule = [x for x in hist if x["action"] == "Phê duyệt dời thời gian"]
assert len(reschedule) == 1, reschedule
assert reschedule[0]["comment"] == "Gia hạn theo đề nghị KH"
assert "05/10/2026 17:00" in reschedule[0]["change"]
assert "08/10/2026 17:00" in reschedule[0]["change"]
assert "Khách hàng bổ sung hồ sơ" in reschedule[0]["change"]
assert any(x["action"] == "Chỉnh sửa Ghi chú công việc" and x["comment"] == "Ghi chú Admin" for x in hist)
assert any("Ghi chú lãnh đạo mới → Ghi chú Admin" in x["change"] for x in hist if x["action"] == "Chỉnh sửa Ghi chú công việc")

# The history block must be injected immediately after the existing stage-history table.
events = []
class FakeSt:
    def subheader(self, label, *args, **kwargs):
        events.append(("subheader", label))
    def html(self, body, *args, **kwargs):
        events.append(("html", str(body)))
    def markdown(self, body, *args, **kwargs):
        events.append(("markdown", str(body)))
    def caption(self, body, *args, **kwargs):
        events.append(("caption", str(body)))


def fake_table(st, heads, rows, widths=None):
    events.append(("approval_table", tuple(heads), len(rows), tuple(widths or [])))

fake = FakeSt()
proxy = patch._HistoryInlineProxy(fake, get_conn, 10, fake_table)
proxy.subheader("Lịch sử mục công việc")
proxy.html("<div><table><tr><td>stage history</td></tr></table></div>")
assert proxy.inserted is True
html_idx = next(i for i, e in enumerate(events) if e[0] == "html")
approval_idx = next(i for i, e in enumerate(events) if e[0] == "approval_table")
assert approval_idx > html_idx
assert any(e[0] == "markdown" and "Phê duyệt / thay đổi của Lãnh đạo/Admin" in e[1] for e in events)
assert any(e[0] == "approval_table" and "Ý kiến / Ghi chú" in e[1] for e in events)

src = Path(patch.__file__).read_text(encoding="utf-8")
for token in [
    "Chỉ Lãnh đạo phòng/Admin được chỉnh sửa Ghi chú công việc khách hàng",
    "NOTE_EDIT",
    "Ý kiến / Ghi chú của Lãnh đạo/Admin",
    "💬 Phê duyệt / thay đổi của Lãnh đạo/Admin",
    "_HistoryInlineProxy",
    "decision_note",
    "approval_comment_inline_history=1",
    "data_migration=0",
]:
    assert token in src, token

print(
    "CUSTOMER_WORK_MANAGER_NOTE_HISTORY_QA_PASS "
    "leader_edit=1 admin_edit=1 qlkh_blocked=1 note_audit=1 "
    "plan_comment_history=1 reschedule_comment_history=1 inline_after_stage_history=1 "
    "reschedule_old_new_reason=1 no_duplicate_decision=1 data_migration=0"
)
