"""Scheduled Phase-2 Weekly Plan reminders and 5-business-day score fallback.

This worker only creates durable in-app/Web Push notifications. Email transport is
intentionally not coupled to business transactions; it can be added later as an
optional delivery channel without changing plan state.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from pathlib import Path
import sqlite3
import threading
import time

from khdn_apps import notifications as notify
from khdn_apps import weekly_push
from khdn_apps.weekly_performance_phase2_patch import _metrics, _quality, _week_score, _grade

LOGGER = logging.getLogger("khdn_weekly_phase2_notifications")


def _connect(db_path):
    c = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _now():
    return weekly_push.local_now().strftime("%Y-%m-%d %H:%M:%S")


def _table(c, name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _cols(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_schema(db_path):
    weekly_push.ensure_schema(db_path)
    with _connect(db_path) as c:
        if not _table(c, "weekly_plans") or not _table(c, "weekly_plan_items") or not _table(c, "users"):
            return False
        c.execute(
            """CREATE TABLE IF NOT EXISTS weekly_cycle_notification_events(
                event_code TEXT NOT NULL,
                subject_key TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(event_code,subject_key,user_id)
            )"""
        )
        # Phase-2 score columns may arrive after this worker starts on a new DB.
        pcols = _cols(c, "weekly_plans")
        for name, ddl in (
            ("progress_score", "REAL"), ("quality_score", "REAL"), ("week_score", "REAL"),
            ("week_grade", "TEXT"), ("quality_fallback", "INTEGER NOT NULL DEFAULT 0"),
        ):
            if name not in pcols:
                c.execute(f"ALTER TABLE weekly_plans ADD COLUMN {name} {ddl}")
                pcols.add(name)
        c.commit()
    return True


def _insert(c, uid, title, body, event_key="weekly_reminder", event_code="PLAN_REMINDER"):
    return weekly_push.enqueue(c, uid, title, body,
                               event_key=event_key, event_code=event_code)


def _emit_once(c, code, subject, uid, title, body, event_key="weekly_reminder"):
    cur = c.execute(
        "INSERT OR IGNORE INTO weekly_cycle_notification_events(event_code,subject_key,user_id,created_at) VALUES(?,?,?,?)",
        (str(code), str(subject), int(uid), _now()),
    )
    if not cur.rowcount:
        return False
    if code in {"PLAN_WAITING_APPROVAL", "QUALITY_FALLBACK", "MANAGER_REVIEW_PENDING"}:
        event_key = "weekly_update"
    return bool(_insert(c, uid, title, body, event_key, event_code=code))


def _monday(d):
    return d - timedelta(days=d.weekday())


def _staff(c):
    ucols = _cols(c, "users")
    where = ["active=1", "role IN ('Cán bộ QLKH','Cán bộ hỗ trợ')"]
    if "is_admin" in ucols:
        where.append("COALESCE(is_admin,0)=0")
    return [dict(r) for r in c.execute("SELECT id,full_name,role FROM users WHERE " + " AND ".join(where) + " ORDER BY full_name").fetchall()]


def _leader_for_staff(c, uid):
    ucols = _cols(c, "users")
    row = c.execute("SELECT * FROM users WHERE id=?", (int(uid),)).fetchone()
    if row:
        d = dict(row)
        for name in ("manager_user_id", "leader_user_id", "supervisor_user_id"):
            if name in ucols and d.get(name):
                return int(d[name])
    if _table(c, "customer_work_cases") and "controller_user_id" in _cols(c, "customer_work_cases"):
        hit = c.execute(
            """SELECT controller_user_id,COUNT(*) n FROM customer_work_cases
               WHERE owner_user_id=? AND controller_user_id IS NOT NULL
               GROUP BY controller_user_id ORDER BY n DESC,MAX(id) DESC LIMIT 1""",
            (int(uid),),
        ).fetchone()
        if hit and hit[0]:
            return int(hit[0])
    leaders = c.execute("SELECT id FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY id").fetchall()
    return int(leaders[0][0]) if len(leaders) == 1 else None


def _manager_recipients(c, direct_leader=None):
    """Direct controller plus active room leaders with existing admin scope.

    Approval UI grants admin leaders access to every pending plan. Include that
    same oversight scope in business alerts, while excluding technical admins.
    """
    recipients = set()
    if direct_leader:
        row = c.execute("SELECT id FROM users WHERE id=? AND active=1 AND role='Lãnh đạo phòng'", (int(direct_leader),)).fetchone()
        if row:
            recipients.add(int(row[0]))
    if "is_admin" in _cols(c, "users"):
        recipients.update(int(r[0]) for r in c.execute("SELECT id FROM users WHERE active=1 AND role='Lãnh đạo phòng' AND COALESCE(is_admin,0)=1"))
    return sorted(recipients)


def _plan(c, uid, ws):
    row = c.execute("SELECT * FROM weekly_plans WHERE user_id=? AND week_start=? ORDER BY id DESC LIMIT 1", (int(uid), ws.isoformat())).fetchone()
    return dict(row) if row else None


def _business_days_since(start_date, end_date):
    if not start_date or end_date <= start_date:
        return 0
    d = start_date + timedelta(days=1)
    n = 0
    while d <= end_date:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def process_cycle_reminders(db_path, now=None):
    if not ensure_schema(db_path):
        return 0
    now = now or weekly_push.local_now()
    today = now.date(); created = 0
    current_ws = _monday(today)
    with _connect(db_path) as c:
        staff = _staff(c)

        # Friday 16:00 -> next week's planning reminder.
        if now.weekday() == 4 and (now.hour, now.minute) >= (16, 0):
            target_ws = current_ws + timedelta(days=7)
            for person in staff:
                p = _plan(c, person["id"], target_ws)
                if not p or str(p.get("workflow_status") or "NHAP") in {"NHAP", "TRA_LAI"}:
                    created += int(_emit_once(c, "PLAN_REMINDER_FRI", target_ws.isoformat(), person["id"], "📅 Lập kế hoạch tuần", f"Mời lập kế hoạch tuần {target_ws:%d/%m/%Y} – {(target_ws+timedelta(days=4)):%d/%m/%Y}."))

        # Monday 08:00 reminder; 09:30 overdue reminder to staff + direct leader.
        if now.weekday() == 0 and (now.hour, now.minute) >= (8, 0):
            for person in staff:
                p = _plan(c, person["id"], current_ws)
                status = str((p or {}).get("workflow_status") or "NHAP")
                if not p or status in {"NHAP", "TRA_LAI"}:
                    created += int(_emit_once(c, "PLAN_REMINDER_MON", current_ws.isoformat(), person["id"], "📅 Nhắc nộp kế hoạch tuần", f"Kế hoạch tuần {current_ws:%d/%m/%Y} chưa được nộp."))
                    if (now.hour, now.minute) >= (9, 30):
                        created += int(_emit_once(c, "PLAN_OVERDUE", current_ws.isoformat(), person["id"], "🔴 Chưa nộp kế hoạch tuần", "Đã quá 09:30 Thứ 2 nhưng kế hoạch tuần vẫn chưa được nộp."))
                        leader = _leader_for_staff(c, person["id"])
                        for leader in _manager_recipients(c, leader):
                            created += int(_emit_once(c, "PLAN_OVERDUE_LEADER", f"{current_ws.isoformat()}:{person['id']}", leader, "🔴 Cán bộ chưa nộp kế hoạch", f"{person.get('full_name') or 'Cán bộ'} chưa nộp kế hoạch tuần {current_ws:%d/%m/%Y}."))

        # Match approval visibility: direct leader and admin room oversight.
        pending = [dict(r) for r in c.execute("SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.workflow_status='DA_NOP'").fetchall()]
        for p in pending:
            leader = _leader_for_staff(c, p["user_id"])
            for leader in _manager_recipients(c, leader):
                subject = f"{p['id']}:{p.get('submitted_at') or 'initial'}"
                # Carry the old dedupe marker forward once. A later resubmission
                # uses its own timestamp and can alert the leader again.
                c.execute("""INSERT OR IGNORE INTO weekly_cycle_notification_events
                    (event_code,subject_key,user_id,created_at)
                    SELECT event_code,?,user_id,created_at FROM weekly_cycle_notification_events
                    WHERE event_code='PLAN_WAITING_APPROVAL' AND subject_key=? AND user_id=?""",
                    (subject, str(p["id"]), int(leader)))
                c.execute("""DELETE FROM weekly_cycle_notification_events
                    WHERE event_code='PLAN_WAITING_APPROVAL' AND subject_key=? AND user_id=?""",
                    (str(p["id"]), int(leader)))
                created += int(_emit_once(c, "PLAN_WAITING_APPROVAL", subject, leader, "✅ Có kế hoạch tuần chờ duyệt", f"{p.get('full_name') or 'Cán bộ'} đã nộp kế hoạch tuần {_dmy(p.get('week_start'))}."))

        # Friday 14:00 close-week reminder.
        if now.weekday() == 4 and (now.hour, now.minute) >= (14, 0):
            plans = [dict(r) for r in c.execute("SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.week_start=? AND p.workflow_status='DA_DUYET'", (current_ws.isoformat(),)).fetchall()]
            for p in plans:
                created += int(_emit_once(c, "CLOSE_WEEK", str(p["id"]), p["user_id"], "📝 Nhắc chốt tuần", "Hãy cập nhật kết quả công việc, tự đánh giá và chốt tuần trước khi kết thúc ngày làm việc."))

        # Monday 08:00: leader sees any self-closed plans still pending review.
        if now.weekday() == 0 and (now.hour, now.minute) >= (8, 0):
            closed = [dict(r) for r in c.execute("SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.workflow_status='DA_CHOT'").fetchall()]
            for p in closed:
                leader = _leader_for_staff(c, p["user_id"])
                for leader in _manager_recipients(c, leader):
                    created += int(_emit_once(c, "MANAGER_REVIEW_PENDING", str(p["id"]), leader, "⭐ Tuần chờ nhận xét", f"{p.get('full_name') or 'Cán bộ'} đang chờ nhận xét/chấm điểm tuần {_dmy(p.get('week_start'))}."))

        c.commit()
    return created


def _dmy(v):
    if not v:
        return "—"
    try:
        return date.fromisoformat(str(v)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return str(v)


def process_quality_fallback(db_path, now=None):
    """After 5 business days without leader review, compute using self score and flag it.

    The result remains replaceable later: manager UI includes fallback rows so a late
    leader review can overwrite the provisional quality score.
    """
    if not ensure_schema(db_path):
        return 0
    now = now or weekly_push.local_now(); changed = 0
    with _connect(db_path) as c:
        rows = [dict(r) for r in c.execute(
            """SELECT * FROM weekly_plans WHERE workflow_status='DA_CHOT'
               AND self_score IS NOT NULL AND closed_at IS NOT NULL"""
        ).fetchall()]
        for p in rows:
            try:
                closed = datetime.fromisoformat(str(p["closed_at"]).replace("Z", "+00:00")).date()
            except Exception:
                continue
            if _business_days_since(closed, now.date()) < 5:
                continue
            items = [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE plan_id=? ORDER BY id", (int(p["id"]),)).fetchall()]
            m = _metrics(items)
            quality = _quality(p.get("self_score"), fallback=True)
            score = _week_score(m["progress"], quality)
            grade = _grade(score)
            c.execute(
                """UPDATE weekly_plans SET workflow_status='DA_DANH_GIA',progress_score=?,quality_score=?,week_score=?,week_grade=?,quality_fallback=1,evaluated_at=?,updated_at=? WHERE id=?""",
                (m["progress"], quality, score, grade, _now(), _now(), int(p["id"])),
            )
            _emit_once(c, "QUALITY_FALLBACK", str(p["id"]), int(p["user_id"]), "🏁 Kết quả tuần tạm tính", f"Sau 5 ngày làm việc chưa có nhận xét lãnh đạo, hệ thống tạm tính {score:.2f}/100 · {grade} theo điểm tự chấm.")
            changed += 1
        c.commit()
    return changed


def process_once(db_path):
    return process_cycle_reminders(db_path) + process_quality_fallback(db_path)


def worker_loop(db_path: str | Path, stop_event: threading.Event, poll_seconds: float = 60.0):
    LOGGER.info("WEEKLY_PHASE2_NOTIFICATION_WORKER_START timezone=Asia/Ho_Chi_Minh")
    schema_ready = False
    last_schema_notice = 0.0
    while not stop_event.is_set():
        try:
            if not ensure_schema(db_path):
                if time.monotonic() - last_schema_notice >= 60:
                    LOGGER.info("WEEKLY_PHASE2_NOTIFICATION_WAIT_SCHEMA")
                    last_schema_notice = time.monotonic()
            else:
                if not schema_ready:
                    LOGGER.info("WEEKLY_PHASE2_NOTIFICATION_SCHEMA_READY")
                    schema_ready = True
                process_once(db_path)
        except sqlite3.Error:
            LOGGER.debug("WEEKLY_PHASE2_SCHEMA_WAIT", exc_info=True)
        except Exception:
            LOGGER.exception("WEEKLY_PHASE2_NOTIFICATION_WORKER_FAILED")
        stop_event.wait(max(10.0, float(poll_seconds)))
    LOGGER.info("WEEKLY_PHASE2_NOTIFICATION_WORKER_STOP")
