from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from khdn_apps import planning_operational_phase12_patch as p12

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase12_patch.py").read_text(encoding="utf-8")
shim = (ROOT / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")

checks = {
    "phase12_installed_after_phase11": "phase12.install" in shim and shim.find("phase12.install") > shim.find("phase11.install"),
    "backup_dedicated_route": 'admin_view' in src and '!= "backup"' in src and "P12_BACKUP_ROUTE_GUARD_INSTALLED" in src,
    "single_weekday_header": '"p11-day-strip" in text' in src and '"p3-day-head" in text' in src,
    "weekday_task_count": "{counts[idx]} việc" in src,
    "quick_day_prefill": "wp_quick_day_" in src and "Ngày thực hiện" in src,
    "auto_close_regular": "wp_add_open_" in src and ".pop(" in src,
    "auto_close_emergent": "p3_emergent_open_" in src,
    "quick_day_clear": "wp_quick_day_" in src and "session_state.pop" in src,
    "cancel_schema": "customer_work_cancel_requests" in src and "idx_cw_cancel_one_pending" in src,
    "cancel_reason_required": "Phải nhập Lý do đề nghị hủy" in src,
    "cancel_empty_red": "p12_case_cancel_reason_" in src and "textarea:placeholder-shown" in src and "#FF4B4B" in src,
    "cancel_not_immediate": "status='PENDING'" in src and "CANCEL_REQUEST_P12" in src,
    "controller_exact": "controller_user_id" in src and "== int(actor_uid)" in src,
    "cancel_approval_effect": "status='CANCELLED'" in src and "CANCEL_APPROVE_P12" in src,
    "waiting_center_pulse": "p12_leader_waiting_center" in src and "p12AttentionPulse" in src,
    "reduced_motion": "prefers-reduced-motion" in src,
    "cancel_in_full_export": "phase11._EXPORT_TABLES" in src and "customer_work_cancel_requests" in src,
    "runtime_logs": all(x in src for x in [
        "P12_WEEK_BOARD_SINGLE_HEADER_INSTALLED", "P12_WEEKLY_QUICK_ADD_INSTALLED",
        "P12_CASE_CANCEL_REQUEST", "P12_CASE_CANCEL_DECISION", "P12_WAITING_CENTER_INSTALLED",
    ]),
}

bad = [name for name, ok in checks.items() if not ok]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE12_QA_FAIL {bad} {checks}")

# Semantic lifecycle: request never cancels immediately; only controlling leader
# (or Admin) can make cancellation effective. Rejection keeps the case active.
class _Policy:
    @staticmethod
    def _is_admin(u):
        try:
            return bool(int(u.get("is_admin") or 0))
        except Exception:
            return False

    @staticmethod
    def _notify(conn, user_id, title, body, **kwargs):
        return None


with tempfile.TemporaryDirectory(prefix="p12-cancel-qa-") as td:
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
            CREATE TABLE customer_work_cases(
                id INTEGER PRIMARY KEY, customer_id INTEGER, owner_user_id INTEGER,
                controller_user_id INTEGER, status TEXT, plan_approval_status TEXT,
                updated_at TEXT
            );
            CREATE TABLE case_actions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, actor_user_id INTEGER,
                action TEXT, detail TEXT, created_at TEXT
            );
            CREATE TABLE case_reschedule_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT, case_id INTEGER, status TEXT,
                decided_by INTEGER, decided_at TEXT, decision_note TEXT
            );
            INSERT INTO users VALUES(1,'Cán bộ A','Cán bộ QLKH',0,1);
            INSERT INTO users VALUES(2,'Lãnh đạo kiểm soát','Lãnh đạo phòng',0,1);
            INSERT INTO users VALUES(3,'Lãnh đạo khác','Lãnh đạo phòng',0,1);
            INSERT INTO users VALUES(4,'Admin','Lãnh đạo phòng',1,1);
            INSERT INTO customer_work_cases VALUES(101,10,1,2,'ACTIVE','APPROVED','2026-09-30 10:00:00');
            INSERT INTO customer_work_cases VALUES(102,11,1,2,'ACTIVE','APPROVED','2026-09-30 10:00:00');
            INSERT INTO customer_work_cases VALUES(103,12,1,2,'ACTIVE','APPROVED','2026-09-30 10:00:00');
            """
        )

    p12._ensure_cancel_schema(get_conn)

    try:
        p12._request_case_cancel(get_conn, 101, 1, "")
        raise AssertionError("Blank cancellation reason unexpectedly accepted")
    except ValueError:
        pass

    req1 = p12._request_case_cancel(get_conn, 101, 1, "Khách hàng dừng nhu cầu")
    with get_conn() as c:
        assert c.execute("SELECT status FROM customer_work_cases WHERE id=101").fetchone()[0] == "ACTIVE"
        assert c.execute("SELECT status FROM customer_work_cancel_requests WHERE id=?", (req1,)).fetchone()[0] == "PENDING"

    try:
        p12._decide_case_cancel(get_conn, _Policy(), req1, 3, True, "")
        raise AssertionError("Wrong leader unexpectedly approved customer-work cancellation")
    except PermissionError:
        pass

    p12._decide_case_cancel(get_conn, _Policy(), req1, 2, True, "Đồng ý")
    with get_conn() as c:
        row = c.execute("SELECT status,cancel_reason,plan_approval_status FROM customer_work_cases WHERE id=101").fetchone()
        assert row[0] == "CANCELLED"
        assert row[1] == "Khách hàng dừng nhu cầu"
        assert row[2] == "CANCELLED"
        assert c.execute("SELECT status FROM customer_work_cancel_requests WHERE id=?", (req1,)).fetchone()[0] == "APPROVED"

    req2 = p12._request_case_cancel(get_conn, 102, 1, "Không tiếp tục hồ sơ")
    p12._decide_case_cancel(get_conn, _Policy(), req2, 2, False, "Tiếp tục xử lý")
    with get_conn() as c:
        assert c.execute("SELECT status FROM customer_work_cases WHERE id=102").fetchone()[0] == "ACTIVE"
        assert c.execute("SELECT status FROM customer_work_cancel_requests WHERE id=?", (req2,)).fetchone()[0] == "REJECTED"

    req3 = p12._request_case_cancel(get_conn, 103, 1, "Dừng theo yêu cầu")
    p12._decide_case_cancel(get_conn, _Policy(), req3, 4, True, "Admin duyệt")
    with get_conn() as c:
        assert c.execute("SELECT status FROM customer_work_cases WHERE id=103").fetchone()[0] == "CANCELLED"

# Weekday count semantic check.
ws = __import__("datetime").date(2026, 9, 28)
counts = p12._day_counts(ws, [
    {"work_date":"2026-09-28", "status":"PLANNED"},
    {"work_date":"2026-09-28", "status":"DONE"},
    {"work_date":"2026-09-29", "status":"PLANNED"},
    {"work_date":"2026-09-30", "status":"CANCELLED"},
])
assert counts == [2, 1, 0, 0, 0], counts
strip = p12._weekday_strip(ws, [{"work_date":"2026-09-28", "status":"PLANNED"}])
assert "1 việc" in strip and "p12-day-strip" in strip

print(
    "PLANNING_OPERATIONAL_PHASE12_QA_PASS",
    checks,
    "cancel_lifecycle=PASS weekday_counts=PASS",
)
