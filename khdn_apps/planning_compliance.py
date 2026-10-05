"""Durable planning evidence and department statistics; no scoring/notification changes.

Only observed rosters or existing plan/reminder evidence establish an obligation.
Absent old records are unknown, never silently classified as missed submissions.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
import math
import re
import sqlite3

from khdn_apps import weekly_push

LOGGER = logging.getLogger("khdn_weekly_phase2_notifications")
STAFF_ROLES = {"Cán bộ QLKH", "Cán bộ hỗ trợ"}
EXECUTABLE = {"DA_DUYET", "DA_CHOT", "DA_DANH_GIA"}
CLOSED = {"DONE", "CANCELLED", "DELETED"}
SUBMISSION_LABELS = {
    "ON_TIME": "Nộp đúng hạn", "LATE": "Nộp chậm", "MISSING": "Không nộp trong tuần",
    "PENDING_OVERDUE": "Chưa nộp · đang quá hạn", "NOT_DUE": "Chưa đến hạn nộp",
    "UNKNOWN": "Chưa đủ dữ liệu", "NOT_REQUIRED": "Không thuộc diện nộp",
}
STATUS_LABELS = {"PLANNED": "Chưa làm", "IN_PROGRESS": "Đang làm", "DONE": "Hoàn thành",
                 "CANCELLED": "Hủy", "DELETED": "Đã xóa"}


def parse_dt(value):
    if not value:
        return None
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(weekly_push.LOCAL_TZ).replace(tzinfo=None) if result.tzinfo else result
    except (ValueError, TypeError):
        return None


def parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except (ValueError, TypeError):
        return None


def monday(day):
    return day - timedelta(days=day.weekday())


def _stamp(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _tables(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def authorize(c, actor):
    """Statistics/export are Admin-only; recheck the current DB account."""
    uid = int(actor["id"])
    row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    u = dict(row) if row else {}
    if not u.get("active") or not u.get("is_admin"):
        raise PermissionError("Chỉ Admin đang hoạt động được xem và xuất thống kê cán bộ.")
    return u


def _meta(c, key, default=None):
    row = c.execute("SELECT value FROM planning_compliance_meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def _set_meta(c, key, value):
    c.execute("""INSERT INTO planning_compliance_meta(key,value) VALUES(?,?)
                 ON CONFLICT(key) DO UPDATE SET value=excluded.value WHERE value<>excluded.value""", (key, str(value)))


def _week_bounds(c, ws):
    closing = time(17, 30)
    if "system_settings" in _tables(c):
        row = c.execute("SELECT value FROM system_settings WHERE key='workday_end'").fetchone()
        try:
            if row:
                closing = time.fromisoformat(str(row[0]))
        except ValueError:
            pass
    return datetime.combine(ws, time(9, 30)), datetime.combine(ws + timedelta(days=4), closing)


def ensure_schema(c, now=None):
    now = parse_dt(now) if now else weekly_push.local_now()
    if not {"users", "weekly_plans", "weekly_plan_items", "weekly_plan_actions"} <= _tables(c):
        return False
    cols = {r[1] for r in c.execute("PRAGMA table_info(weekly_plan_items)")}
    if not {"expected_complete_date", "completed_at", "controller_user_id"} <= cols:
        return False
    statements = [
        "CREATE TABLE IF NOT EXISTS planning_compliance_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
        """CREATE TABLE IF NOT EXISTS planning_compliance_roster(
            user_id INTEGER NOT NULL,week_start TEXT NOT NULL,staff_name TEXT NOT NULL,role TEXT NOT NULL,
            required INTEGER NOT NULL,deadline_at TEXT NOT NULL,week_close_at TEXT NOT NULL,
            source TEXT NOT NULL,observed_at TEXT NOT NULL,PRIMARY KEY(user_id,week_start))""",
        """CREATE TABLE IF NOT EXISTS planning_submission_history(
            event_key TEXT PRIMARY KEY,user_id INTEGER NOT NULL,week_start TEXT NOT NULL,
            plan_id INTEGER,submitted_at TEXT NOT NULL,source TEXT NOT NULL,recorded_at TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS idx_pch_submit_week ON planning_submission_history(week_start,user_id)",
        """CREATE TABLE IF NOT EXISTS planning_work_changes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,item_id INTEGER NOT NULL,user_id INTEGER NOT NULL,
            plan_id INTEGER,week_start TEXT,workflow_status TEXT,old_user_id INTEGER,
            old_status TEXT,new_status TEXT,old_due TEXT,new_due TEXT,old_work_date TEXT,new_work_date TEXT,
            completed_at TEXT,title TEXT,customer_text TEXT,focus_name TEXT,changed_at TEXT NOT NULL,source TEXT NOT NULL)""",
        "CREATE INDEX IF NOT EXISTS idx_pch_work_item ON planning_work_changes(item_id,id)",
        """CREATE TABLE IF NOT EXISTS planning_work_incidents(
            item_id INTEGER NOT NULL,user_id INTEGER NOT NULL,due_date TEXT NOT NULL,week_start TEXT NOT NULL,
            title TEXT,customer_text TEXT,opened_at TEXT NOT NULL,detected_at TEXT NOT NULL,
            resolved_at TEXT,resolution TEXT,source TEXT NOT NULL,
            PRIMARY KEY(item_id,user_id,due_date))""",
        "CREATE INDEX IF NOT EXISTS idx_pch_incident_week ON planning_work_incidents(week_start,user_id)",
        """CREATE TABLE IF NOT EXISTS planning_submission_incidents(
            user_id INTEGER NOT NULL,week_start TEXT NOT NULL,kind TEXT NOT NULL,deadline_at TEXT NOT NULL,
            occurred_at TEXT NOT NULL,actual_at TEXT,source TEXT NOT NULL,PRIMARY KEY(user_id,week_start,kind))""",
    ]
    for sql in statements:
        c.execute(sql)
    if not _meta(c, "started_at"):
        ws = monday(now.date())
        deadline, _ = _week_bounds(c, ws)
        _set_meta(c, "started_at", _stamp(now))
        _set_meta(c, "roster_from", (ws if now <= deadline else ws + timedelta(days=7)).isoformat())
        LOGGER.info("PLANNING_COMPLIANCE_MONITORING_STARTED roster_from=%s", _meta(c, "roster_from"))
    _install_work_triggers(c)
    return True


def _install_work_triggers(c):
    fields = """item_id,user_id,plan_id,week_start,workflow_status,old_user_id,old_status,new_status,
        old_due,new_due,old_work_date,new_work_date,completed_at,title,customer_text,focus_name,changed_at,source"""
    for name, operation, prefix, old, new, source in (
        ("insert", "AFTER INSERT", "NEW", "NULL,NULL,NULL,NULL", "NEW.status,NEW.expected_complete_date,NEW.work_date", "NEW"),
        ("update", "AFTER UPDATE", "NEW", "OLD.user_id,OLD.status,OLD.expected_complete_date,OLD.work_date", "NEW.status,NEW.expected_complete_date,NEW.work_date", "CHANGE"),
        ("delete", "BEFORE DELETE", "OLD", "OLD.user_id,OLD.status,OLD.expected_complete_date,OLD.work_date", "'DELETED',OLD.expected_complete_date,OLD.work_date", "DELETE"),
    ):
        # Keep the values in the explicit schema order; no core transaction is committed here.
        old_user, old_status, old_due, old_day = old.split(",")
        new_status, new_due, new_day = new.split(",")
        condition = ""
        if name == "update":
            condition = """WHEN OLD.status IS NOT NEW.status OR OLD.expected_complete_date IS NOT NEW.expected_complete_date
                OR OLD.completed_at IS NOT NEW.completed_at OR OLD.work_date IS NOT NEW.work_date
                OR OLD.user_id IS NOT NEW.user_id"""
        at = f"COALESCE(NULLIF({prefix}.updated_at,''),strftime('%Y-%m-%d %H:%M:%S','now','+7 hours'))"
        if name == "update":
            at = "CASE WHEN NEW.updated_at IS NOT OLD.updated_at THEN NEW.updated_at ELSE strftime('%Y-%m-%d %H:%M:%S','now','+7 hours') END"
        if name == "delete":
            at = "strftime('%Y-%m-%d %H:%M:%S','now','+7 hours')"
        c.execute(f"""CREATE TRIGGER IF NOT EXISTS planning_compliance_work_{name}_v1
            {operation} ON weekly_plan_items {condition} BEGIN
            INSERT INTO planning_work_changes({fields}) VALUES(
                {prefix}.id,{prefix}.user_id,{prefix}.plan_id,
                (SELECT week_start FROM weekly_plans WHERE id={prefix}.plan_id),
                (SELECT workflow_status FROM weekly_plans WHERE id={prefix}.plan_id),
                {old_user},{old_status},{new_status},{old_due},{new_due},{old_day},{new_day},
                {prefix}.completed_at,{prefix}.title,{prefix}.customer_text,{prefix}.focus_name_snapshot,{at},'{source}'); END""")


def _put_roster(c, user, ws, required, source, now):
    deadline, close = _week_bounds(c, ws)
    c.execute("""INSERT OR IGNORE INTO planning_compliance_roster
        (user_id,week_start,staff_name,role,required,deadline_at,week_close_at,source,observed_at)
        VALUES(?,?,?,?,?,?,?,?,?)""", (user["id"],ws.isoformat(),user.get("full_name") or f"Cán bộ #{user['id']}",
        user.get("role") or "",int(required),_stamp(deadline),_stamp(close),source,_stamp(now)))


def _capture_roster(c, users, now):
    current = monday(now.date())
    start = parse_date(_meta(c, "roster_from"))
    targets = {max(current, start)}
    if now.weekday() >= 5:
        targets.add(current + timedelta(days=7))
    for ws in targets:
        deadline, _ = _week_bounds(c, ws)
        if ws < start or now > deadline:
            continue
        for u in users.values():
            required = bool(u.get("active") and u.get("role") in STAFF_ROLES and not u.get("is_admin"))
            if required:
                _put_roster(c, u, ws, True, "LIVE", now)
            c.execute("""UPDATE planning_compliance_roster SET required=?,staff_name=?,role=?
                WHERE user_id=? AND week_start=? AND source='LIVE'
                AND (required<>? OR staff_name<>? OR role<>?)""",
                (int(required),u.get("full_name") or "",u.get("role") or "",u["id"],ws.isoformat(),
                 int(required),u.get("full_name") or "",u.get("role") or ""))


def _sync_submissions(c, users, plans, now):
    cursor = int(_meta(c, "last_submission_action", "0"))
    rows = c.execute("SELECT * FROM weekly_plan_actions WHERE id>? AND action='PLAN_SUBMIT' ORDER BY id", (cursor,)).fetchall()
    for raw in rows:
        r = dict(raw)
        match = re.search(r"\bweek=(\d{4}-\d{2}-\d{2})\b", str(r.get("detail") or ""))
        ws = parse_date(match[1]) if match else None
        actual = parse_dt(r.get("created_at"))
        if ws and actual:
            p = plans.get((int(r["actor_user_id"]), ws.isoformat()))
            c.execute("""INSERT OR IGNORE INTO planning_submission_history VALUES(?,?,?,?,?,?,?)""",
                (f"action:{r['id']}",r["actor_user_id"],ws.isoformat(),p["id"] if p else None,_stamp(actual),"ACTION",_stamp(now)))
        cursor = max(cursor, int(r["id"]))
    _set_meta(c, "last_submission_action", cursor)
    for (uid, week), p in plans.items():
        ws = parse_date(week)
        if not ws or ws.weekday() != 0:
            continue
        u = users.get(uid, {"id":uid,"full_name":f"Cán bộ #{uid}"})
        created = parse_dt(u.get("created_at"))
        deadline, _ = _week_bounds(c, ws)
        required = u.get("role") in STAFF_ROLES and not u.get("is_admin") and (not created or created <= deadline)
        # Opening a past week creates an empty draft. That alone must not invent
        # a historical missed-submission obligation after the week has ended.
        plan_created = parse_dt(p.get("created_at"))
        _, close = _week_bounds(c, ws)
        if plan_created and plan_created <= close:
            _put_roster(c, u, ws, required, "PLAN", now)
        actual = parse_dt(p.get("submitted_at"))
        if actual and not c.execute("SELECT 1 FROM planning_submission_history WHERE user_id=? AND week_start=? AND submitted_at=?",
                                   (uid, week, _stamp(actual))).fetchone():
            c.execute("INSERT OR IGNORE INTO planning_submission_history VALUES(?,?,?,?,?,?,?)",
                      (f"snapshot:{p['id']}:{_stamp(actual)}",uid,week,p["id"],_stamp(actual),"PLAN_TIMESTAMP",_stamp(now)))
    if "weekly_cycle_notification_events" in _tables(c):
        for r in c.execute("SELECT * FROM weekly_cycle_notification_events WHERE event_code='PLAN_OVERDUE'").fetchall():
            ws = parse_date(r["subject_key"])
            if ws and ws.weekday() == 0:
                u = users.get(int(r["user_id"]), {"id":int(r["user_id"]),"full_name":f"Cán bộ #{r['user_id']}","role":"Cán bộ"})
                _put_roster(c, u, ws, True, "REMINDER", now)


def _submission_status(roster, first, now):
    deadline, close = parse_dt(roster["deadline_at"]), parse_dt(roster["week_close_at"])
    if not roster["required"]:
        return "NOT_REQUIRED", None
    if first and first <= deadline:
        return "ON_TIME", 0
    if first and first <= close:
        return "LATE", math.ceil((first-deadline).total_seconds()/60)
    if now > close:
        return "MISSING", None
    return ("PENDING_OVERDUE", math.ceil((now-deadline).total_seconds()/60)) if now > deadline else ("NOT_DUE", None)


def _submission_groups(c):
    groups = {}
    for raw in c.execute("SELECT * FROM planning_submission_history ORDER BY submitted_at,event_key"):
        r = dict(raw)
        groups.setdefault((int(r["user_id"]),r["week_start"]), []).append(r)
    return groups


def _record_submission_incidents(c, now):
    groups = _submission_groups(c)
    for raw in c.execute("SELECT * FROM planning_compliance_roster").fetchall():
        r = dict(raw)
        entries = [x for x in groups.get((r["user_id"],r["week_start"]),[]) if parse_dt(x["submitted_at"]) <= now]
        first = parse_dt(entries[0]["submitted_at"]) if entries else None
        status, _ = _submission_status(r, first, now)
        if status not in {"LATE", "MISSING"}:
            continue
        occurred = first if status == "LATE" else parse_dt(r["week_close_at"])
        c.execute("INSERT OR IGNORE INTO planning_submission_incidents VALUES(?,?,?,?,?,?,?)",
                  (r["user_id"],r["week_start"],status,r["deadline_at"],_stamp(occurred),_stamp(first) if first else None,r["source"]))


def _open_incident(c, r, uid, due, detected, resolved=None, resolution=None):
    if not due or not detected or detected.date() <= due:
        return
    ws = parse_date(r.get("week_start")) or monday(due)
    c.execute("""INSERT OR IGNORE INTO planning_work_incidents
        (item_id,user_id,due_date,week_start,title,customer_text,opened_at,detected_at,resolved_at,resolution,source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (r["item_id"],uid,due.isoformat(),ws.isoformat(),r.get("title"),r.get("customer_text"),
        _stamp(datetime.combine(due+timedelta(days=1),time())),_stamp(detected),_stamp(resolved) if resolved else None,resolution,r["source"]))
    if resolved:
        c.execute("""UPDATE planning_work_incidents SET resolved_at=?,resolution=?
                     WHERE item_id=? AND user_id=? AND due_date=? AND resolved_at IS NULL""",
                  (_stamp(resolved),resolution,r["item_id"],uid,due.isoformat()))


def _sync_work(c, now):
    # Existing items have a labelled baseline. Triggers capture subsequent edits atomically.
    c.execute("""INSERT INTO planning_work_changes
        (item_id,user_id,plan_id,week_start,workflow_status,new_status,new_due,new_work_date,
         completed_at,title,customer_text,focus_name,changed_at,source)
        SELECT w.id,w.user_id,w.plan_id,p.week_start,p.workflow_status,w.status,w.expected_complete_date,w.work_date,
               w.completed_at,w.title,w.customer_text,w.focus_name_snapshot,?,'BASELINE'
        FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id
        WHERE NOT EXISTS(SELECT 1 FROM planning_work_changes h WHERE h.item_id=w.id)""", (_stamp(now),))
    cursor = int(_meta(c, "last_work_change", "0"))
    first_changes = {r['item_id']: dict(r) for r in c.execute("""SELECT * FROM planning_work_changes
        WHERE id IN (SELECT MIN(id) FROM planning_work_changes GROUP BY item_id)""")}
    for raw in c.execute("SELECT * FROM planning_work_changes WHERE id>? ORDER BY id", (cursor,)).fetchall():
        r = dict(raw); at = parse_dt(r["changed_at"])
        if at and at > now:
            break
        if at and at <= now and r["workflow_status"] in EXECUTABLE:
            old_due = parse_date(r["old_due"]) or parse_date(r["old_work_date"])
            new_due = parse_date(r["new_due"]) or parse_date(r["new_work_date"])
            if not r['old_due'] and r['new_due'] and first_changes[r['item_id']]['source']=='NEW':
                # The normal save transaction inserts the core row, then fills
                # its mandatory completion date. That is initial setup, not a
                # late extension of an agreed deadline.
                earlier = c.execute("SELECT 1 FROM planning_work_changes WHERE item_id=? AND id<? AND new_due IS NOT NULL AND new_due<>'' LIMIT 1", (r['item_id'],r['id'])).fetchone()
                if not earlier: old_due = None
            old_uid = int(r["old_user_id"] or r["user_id"])
            resolution = "Hoàn thành" if r["new_status"] == "DONE" else "Hủy" if r["new_status"] == "CANCELLED" else "Đã xóa" if r["new_status"] == "DELETED" else "Đổi hạn/người phụ trách"
            changed = r["new_status"] in CLOSED or old_due != new_due or old_uid != r["user_id"]
            completed = parse_dt(r["completed_at"]) if r["new_status"] == "DONE" else None
            endpoint = completed if completed and completed <= at else at
            if r["old_status"] and r["old_status"] not in CLOSED:
                _open_incident(c,r,old_uid,old_due,endpoint,endpoint if changed else None,resolution if changed else None)
                if changed and old_due:
                    c.execute("""UPDATE planning_work_incidents SET resolved_at=?,resolution=?
                        WHERE item_id=? AND user_id=? AND due_date=? AND resolved_at IS NULL""",
                        (_stamp(endpoint),resolution,r['item_id'],old_uid,old_due.isoformat()))
            if r["new_status"] == "DONE":
                if completed and completed <= now:
                    _open_incident(c,r,r["user_id"],new_due,completed,completed,"Hoàn thành")
        cursor = max(cursor, int(r["id"]))
    _set_meta(c, "last_work_change", cursor)
    for raw in c.execute("""SELECT w.*,p.week_start,p.workflow_status FROM weekly_plan_items w
                            JOIN weekly_plans p ON p.id=w.plan_id"""):
        r = dict(raw)
        if r["workflow_status"] not in EXECUTABLE:
            continue
        r.update(item_id=r["id"],source="OBSERVED")
        due = parse_date(r.get("expected_complete_date")) or parse_date(r.get("work_date"))
        if r["status"] not in CLOSED:
            _open_incident(c,r,r["user_id"],due,now)
        elif r["status"] == "DONE" and parse_dt(r.get("completed_at")):
            actual = parse_dt(r["completed_at"])
            if actual <= now:
                _open_incident(c,r,r["user_id"],due,actual,actual,"Hoàn thành")


def capture(c, now=None):
    now = parse_dt(now) if now else weekly_push.local_now()
    if not ensure_schema(c, now):
        return False
    before = c.total_changes
    users = {int(r["id"]):dict(r) for r in c.execute("SELECT * FROM users")}
    plans = {(int(r["user_id"]),r["week_start"]):dict(r) for r in c.execute("SELECT * FROM weekly_plans")}
    _capture_roster(c, users, now)
    _sync_submissions(c, users, plans, now)
    _record_submission_incidents(c, now)
    _sync_work(c, now)
    if c.total_changes > before:
        LOGGER.info("PLANNING_COMPLIANCE_CAPTURE changes=%s", c.total_changes-before)
    return True


def capture_db(db_path, now=None):
    with sqlite3.connect(str(db_path), timeout=30) as c:
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA busy_timeout=30000")
        return capture(c, now)


def build_report(get_conn, actor, start, end, selected=None, now=None):
    now = parse_dt(now) if now else weekly_push.local_now()
    start, end = monday(start), monday(end)
    if end < start or (end-start).days > 7*260:
        raise ValueError("Chọn khoảng thời gian hợp lệ, tối đa 5 năm.")
    with get_conn() as c:
        viewer = authorize(c, actor)
        if not capture(c, now):
            raise ValueError("Dữ liệu kế hoạch chưa khởi tạo đầy đủ.")
    with get_conn() as c:
        authorize(c, actor)
        c.execute("BEGIN")  # All exported sheets share one consistent read snapshot.
        users = {int(r["id"]):dict(r) for r in c.execute("SELECT id,full_name,role,active,is_admin FROM users")}
        roster = {(int(r["user_id"]),r["week_start"]):dict(r) for r in c.execute("SELECT * FROM planning_compliance_roster WHERE week_start>=? AND week_start<=?", (start.isoformat(),end.isoformat()))}
        groups = _submission_groups(c)
        changes = [dict(r) for r in c.execute("SELECT * FROM planning_work_changes ORDER BY id")]
        incidents = [dict(r) for r in c.execute("SELECT * FROM planning_work_incidents WHERE week_start>=? AND week_start<=?", (start.isoformat(),end.isoformat()))]
        items = [dict(r) for r in c.execute("""SELECT w.*,p.week_start,p.workflow_status FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id
            WHERE p.week_start>=? AND p.week_start<=?""", (start.isoformat(),end.isoformat()))]
        plans = {(int(r["user_id"]),r["week_start"]):dict(r) for r in c.execute("SELECT * FROM weekly_plans WHERE week_start>=? AND week_start<=?", (start.isoformat(),end.isoformat()))}
        monitoring_from = _meta(c, "roster_from")
    # Former/deleted accounts remain attributable through their roster snapshots.
    for (uid, _), r in roster.items():
        users.setdefault(uid, {"id":uid,"full_name":r["staff_name"],"role":r["role"],"active":0})
    for r in items+incidents:
        uid = int(r['user_id'])
        users.setdefault(uid, {"id":uid,"full_name":f"Cán bộ #{uid}","role":"Chưa đủ dữ liệu","active":0})
    allowed = {uid for uid,u in users.items() if u["role"] in STAFF_ROLES} | {x['user_id'] for x in items+incidents} | {k[0] for k in roster}
    if selected:
        allowed &= {int(x) for x in selected}
    weeks = [start+timedelta(days=7*i) for i in range((end-start).days//7+1)]
    summaries, submissions, work, events = [], [], [], []
    by_item, by_user, incidents_by_user = {}, {}, {}
    for r in changes: by_item.setdefault(r['item_id'],[]).append(r)
    for r in items: by_user.setdefault(r['user_id'],[]).append(r)
    for r in incidents: incidents_by_user.setdefault(r['user_id'],[]).append(r)
    for uid in sorted(allowed, key=lambda x: (users[x]["full_name"].casefold(),x)):
        u = users[uid]
        s = {"user_id":uid,"name":u["full_name"],"role":u["role"],"active":bool(u.get("active")),
             "known_weeks":0,"on_time":0,"late":0,"missing":0,"pending_overdue":0,"unknown_weeks":0,
             "late_minutes":0,"max_late_minutes":0,"work_total":0,"completed":0,"completed_late":0,
             "open_overdue":0,"ever_overdue":0,"completion_unknown":0}
        for ws in weeks:
            week = ws.isoformat(); r = roster.get((uid,week)); p = plans.get((uid,week),{})
            entries = [x for x in groups.get((uid,week),[]) if parse_dt(x["submitted_at"]) <= now]
            first = parse_dt(entries[0]["submitted_at"]) if entries else None
            if not r:
                status, minutes = ("UNKNOWN",None) if u["role"] in STAFF_ROLES else ("NOT_REQUIRED",None)
                deadline, close = _week_bounds_dummy(ws)
            else:
                status, minutes = _submission_status(r,first,now)
                deadline, close = parse_dt(r["deadline_at"]),parse_dt(r["week_close_at"])
            if status == "UNKNOWN": s["unknown_weeks"] += 1
            if status not in {"UNKNOWN","NOT_REQUIRED","NOT_DUE"}: s["known_weeks"] += 1
            if status in {"ON_TIME","LATE","MISSING","PENDING_OVERDUE"}: s[{"ON_TIME":"on_time","LATE":"late","MISSING":"missing","PENDING_OVERDUE":"pending_overdue"}[status]] += 1
            if status == "LATE":
                s["late_minutes"] += minutes; s["max_late_minutes"] = max(s["max_late_minutes"],minutes)
            actual_entries = [x for x in entries if x["source"] == "ACTION"]
            count = len(actual_entries) + len({x["submitted_at"] for x in entries if not any(a["submitted_at"]==x["submitted_at"] for a in actual_entries)})
            row = {"user_id":uid,"name":u["full_name"],"week_start":ws,"deadline_at":deadline,"week_close_at":close,
                   "first_submitted_at":first,"latest_submitted_at":parse_dt(entries[-1]["submitted_at"]) if entries else None,
                   "submit_count":count,"status":status,"late_minutes":minutes,"source":r["source"] if r else "UNKNOWN",
                   "current_status":p.get("workflow_status") or "Chưa có kế hoạch"}
            submissions.append(row)
            if status in {"LATE","MISSING","PENDING_OVERDUE"}:
                events.append({"user_id":uid,"name":u["full_name"],"week_start":ws,"kind":SUBMISSION_LABELS[status],
                    "item_id":None,"title":"Kế hoạch tuần","deadline_at":deadline,"actual_at":first,
                    "detected_at":first if status=="LATE" else close if status=="MISSING" else now,
                    "late_minutes":minutes,"late_days":None,"resolution":"Đã nộp" if first else "Chưa nộp","source":row["source"]})
        own_incidents = incidents_by_user.get(uid,[])
        s["ever_overdue"] = len({x["item_id"] for x in own_incidents})
        for x in own_incidents:
            endpoint = min(parse_dt(x["resolved_at"]) or now, now)
            late_days = max(0,(endpoint.date()-parse_date(x["due_date"])).days)
            events.append({"user_id":uid,"name":u["full_name"],"week_start":parse_date(x["week_start"]),"kind":"Công việc quá hạn",
                "item_id":x["item_id"],"title":x["title"],"deadline_at":datetime.combine(parse_date(x["due_date"]),time(23,59,59)),
                "actual_at":parse_dt(x["resolved_at"]),"detected_at":parse_dt(x["detected_at"]),"late_minutes":None,"late_days":late_days,
                "resolution":x["resolution"] or "Đang quá hạn","source":x["source"]})
        for x in by_user.get(uid,[]):
            history = by_item.get(x['id'],[])
            first_due = next((parse_date(h["new_due"]) for h in history if parse_date(h["new_due"])),None)
            first_due = first_due or (parse_date(history[0]["new_work_date"]) if history else None)
            due = parse_date(x.get("expected_complete_date")) or parse_date(x.get("work_date"))
            actual = parse_dt(x.get("completed_at")); status = x["status"]
            eligible = x["workflow_status"] in EXECUTABLE and status != "CANCELLED"
            late_days = max(0,((actual.date() if status=="DONE" and actual else now.date())-due).days) if due and (status!="DONE" or actual) else None
            if eligible:
                s["work_total"] += 1
                if status=="DONE":
                    s["completed"] += 1
                    if due and actual: s["completed_late"] += int(actual.date()>due)
                    else: s["completion_unknown"] += 1
                elif due and due<now.date(): s["open_overdue"] += 1
            work.append({"user_id":uid,"name":u["full_name"],"week_start":parse_date(x["week_start"]),"item_id":x["id"],"title":x["title"],
                "customer":x.get("customer_text") or "","focus":x.get("focus_name_snapshot") or "","status":status,"workflow_status":x["workflow_status"],
                "first_due":first_due,"due":due,"completed_at":actual,"late_days":late_days if eligible else None,
                "ever_late_days":max([max(0,((parse_dt(i["resolved_at"]) or now).date()-parse_date(i["due_date"])).days) for i in own_incidents if i["item_id"]==x["id"]] or [0]),
                "deadline_changes":sum(bool(h["old_due"] and h["new_due"] and h["old_due"]!=h["new_due"]) for h in history),
                "deadline_source":history[0]["source"] if history else "UNKNOWN","eligible":eligible})
        denominator = s["on_time"]+s["late"]+s["missing"]+s["pending_overdue"]
        s["submission_rate"] = s["on_time"]/denominator if denominator else None
        s["average_late_minutes"] = s["late_minutes"]/s["late"] if s["late"] else None
        known_completed = s["completed"]-s["completion_unknown"]
        s["ontime_work_rate"] = (known_completed-s["completed_late"])/known_completed if known_completed else None
        summaries.append(s)
    return {"viewer_id":int(viewer["id"]),"start":start,"end":end,"as_of":now,"monitoring_from":monitoring_from,
            "summary":summaries,"submissions":submissions,"work":work,"events":events}


def _week_bounds_dummy(ws):
    return datetime.combine(ws,time(9,30)),datetime.combine(ws+timedelta(days=4),time(17,30))
