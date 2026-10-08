from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from khdn_apps import planning_operational_phase7_patch as p7

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase7_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "large_admin_cards": "min-height:7.25rem" in src and "p7_system_admin_cards" in src,
    "six_admin_routes": all(x in src for x in [
        '("users", "👥 Người dùng")', '("customers", "🏢 Khách hàng CIF")',
        '("types", "🧩 Loại công việc")', '("reasons", "🧩 Nhóm nguyên nhân tác nghiệp")',
        '("audit", "🧾 Audit")', '("backup", "💾 Sao lưu")',
    ]),
    "reason_route": '_render_reason_category_manager' in src,
    "audit_route": 'Audit hệ thống' in src and 'FROM system_audit' in src,
    "backup_route": 'backup.render_backup_admin' in src,
    "cancel_request_schema": 'weekly_plan_cancel_requests' in src and 'idx_week_cancel_one_pending' in src,
    "cancel_not_immediate": 'Gửi đề nghị hủy' in src and 'công việc chưa bị hủy' in src,
    "controller_approval": '_weekly_controller_allows' in src and 'Lãnh đạo kiểm soát' in src,
    "admin_approval": 'is_admin' in src and 'return True' in src,
    "cancel_approval_effect": "SET status='CANCELLED'" in src and 'CANCEL_APPROVE' in src,
    "cancel_reject": 'CANCEL_REJECT' in src and 'Từ chối hủy' in src,
    "vietnamese_status": all(x in src for x in ['"PLANNED": "Chưa làm"', '"IN_PROGRESS": "Đang làm"', '"DONE": "Hoàn thành"']),
    "phase7_last": '_operational_phase7.install' in hotfix,
}

bad = [name for name, ok in checks.items() if not ok]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE7_QA_FAIL {bad} {checks}")

# History must never expose weekly enum values to users.
label, detail = p7._fmt_action_vi(
    "EXEC_UPDATE_PHASE3",
    '{"old_status":"IN_PROGRESS","new_status":"DONE","actual_result":"Đã hoàn tất hồ sơ"}',
)
assert label == "Cập nhật tiến độ", (label, detail)
assert detail == "Đang làm → Hoàn thành · Đã hoàn tất hồ sơ", detail

label2, detail2 = p7._fmt_action_vi(
    "CANCEL_REQUEST",
    '{"status_before":"PLANNED","reason":"Khách hàng dừng nhu cầu"}',
)
assert label2 == "Đề nghị hủy công việc", (label2, detail2)
assert "Chưa làm" in detail2 and "Khách hàng dừng nhu cầu" in detail2, detail2

# Semantic lifecycle QA: requesting cancellation must NOT change item status;
# only the exact controlling leader or Admin may make cancellation effective.
class _Policy:
    @staticmethod
    def _notify(conn, user_id, title, body, **kwargs):
        return None

with tempfile.TemporaryDirectory(prefix="p7-cancel-qa-") as td:
    db = Path(td) / "qa.db"

    def get_conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c

    with get_conn() as c:
        c.executescript(
            """
            CREATE TABLE users(
                id INTEGER PRIMARY KEY, full_name TEXT, role TEXT, is_admin INTEGER, active INTEGER
            );
            CREATE TABLE weekly_plans(id INTEGER PRIMARY KEY, user_id INTEGER);
            CREATE TABLE weekly_plan_items(
                id INTEGER PRIMARY KEY, plan_id INTEGER, user_id INTEGER, status TEXT,
                controller_user_id INTEGER, title TEXT, completed_at TEXT, updated_at TEXT
            );
            CREATE TABLE weekly_plan_actions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, actor_user_id INTEGER,
                action TEXT, detail TEXT, created_at TEXT
            );
            INSERT INTO users VALUES(1,'Cán bộ A','Cán bộ QLKH',0,1);
            INSERT INTO users VALUES(2,'Lãnh đạo A','Lãnh đạo phòng',0,1);
            INSERT INTO users VALUES(3,'Lãnh đạo B','Lãnh đạo phòng',0,1);
            INSERT INTO users VALUES(4,'Admin','Lãnh đạo phòng',1,1);
            INSERT INTO weekly_plans VALUES(10,1);
            INSERT INTO weekly_plan_items VALUES(101,10,1,'IN_PROGRESS',2,'Việc 1',NULL,NULL);
            INSERT INTO weekly_plan_items VALUES(102,10,1,'PLANNED',2,'Việc 2',NULL,NULL);
            INSERT INTO weekly_plan_items VALUES(103,10,1,'PLANNED',2,'Việc 3',NULL,NULL);
            """
        )

    p7._ensure_cancel_schema(get_conn)
    req1 = p7._request_cancel(get_conn, 101, 1, "Không còn nhu cầu")
    with get_conn() as c:
        assert c.execute("SELECT status FROM weekly_plan_items WHERE id=101").fetchone()[0] == "IN_PROGRESS"
        assert c.execute("SELECT status FROM weekly_plan_cancel_requests WHERE id=?", (req1,)).fetchone()[0] == "PENDING"

    try:
        p7._decide_cancel(get_conn, _Policy(), req1, 3, True, "")
        raise AssertionError("Wrong leader unexpectedly approved cancellation")
    except PermissionError:
        pass

    p7._decide_cancel(get_conn, _Policy(), req1, 2, True, "Đồng ý")
    with get_conn() as c:
        assert c.execute("SELECT status FROM weekly_plan_items WHERE id=101").fetchone()[0] == "CANCELLED"
        assert c.execute("SELECT status FROM weekly_plan_cancel_requests WHERE id=?", (req1,)).fetchone()[0] == "APPROVED"

    req2 = p7._request_cancel(get_conn, 102, 1, "Dừng công việc")
    p7._decide_cancel(get_conn, _Policy(), req2, 4, True, "Admin duyệt")
    with get_conn() as c:
        assert c.execute("SELECT status FROM weekly_plan_items WHERE id=102").fetchone()[0] == "CANCELLED"

    req3 = p7._request_cancel(get_conn, 103, 1, "Muốn hủy")
    p7._decide_cancel(get_conn, _Policy(), req3, 2, False, "Tiếp tục thực hiện")
    with get_conn() as c:
        assert c.execute("SELECT status FROM weekly_plan_items WHERE id=103").fetchone()[0] == "PLANNED"
        assert c.execute("SELECT status FROM weekly_plan_cancel_requests WHERE id=?", (req3,)).fetchone()[0] == "REJECTED"

print(
    "PLANNING_OPERATIONAL_PHASE7_QA_PASS",
    checks,
    "semantic_cancel_lifecycle=PASS",
    detail,
    detail2,
)
