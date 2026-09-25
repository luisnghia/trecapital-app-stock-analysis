from __future__ import annotations

import json
from datetime import date, datetime, timedelta

VERSION = "2.0.0"

DEFAULT_STAGES = [
    "Đang tiếp cận khách hàng",
    "Đã đề nghị KH cung cấp hồ sơ",
    "KH đã cung cấp hồ sơ",
    "Đã bàn giao bộ phận định giá",
    "CBKH đang làm hồ sơ",
    "Đã trình lãnh đạo",
    "Đang công chứng/ĐKTC TSBĐ",
    "Đã hoàn thành",
]

APPROVAL_LABEL = {
    "PENDING": "Chờ phê duyệt",
    "APPROVED": "Đã phê duyệt",
    "REJECTED": "Từ chối",
}

SEVERITY_LABEL = {"LOW": "Thấp", "MEDIUM": "Trung bình", "HIGH": "Cao"}


def now_dt():
    return datetime.now()


def now_str():
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def _columns(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_col(c, table, name, ddl):
    if name not in _columns(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def ensure_schema(get_conn, logger=None):
    sql = '''
    CREATE TABLE IF NOT EXISTS work_stage_catalog(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        sla_hours REAL NOT NULL DEFAULT 48,
        active INTEGER NOT NULL DEFAULT 1,
        is_completion INTEGER NOT NULL DEFAULT 0,
        created_by INTEGER,
        updated_by INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(created_by) REFERENCES users(id),
        FOREIGN KEY(updated_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS important_categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_by INTEGER,
        updated_by INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(created_by) REFERENCES users(id),
        FOREIGN KEY(updated_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS customer_work_cases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_code TEXT UNIQUE,
        customer_id INTEGER NOT NULL,
        owner_user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        case_type TEXT,
        current_stage_id INTEGER,
        stage_started_at TEXT,
        expected_complete_at TEXT,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        plan_approval_status TEXT NOT NULL DEFAULT 'PENDING',
        plan_requested_by INTEGER,
        plan_requested_at TEXT,
        plan_approved_by INTEGER,
        plan_approved_at TEXT,
        plan_rejected_by INTEGER,
        plan_rejected_at TEXT,
        approval_note TEXT,
        important_category_id INTEGER,
        is_important INTEGER NOT NULL DEFAULT 0,
        urgent_override INTEGER,
        note TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(owner_user_id) REFERENCES users(id),
        FOREIGN KEY(current_stage_id) REFERENCES work_stage_catalog(id),
        FOREIGN KEY(plan_requested_by) REFERENCES users(id),
        FOREIGN KEY(plan_approved_by) REFERENCES users(id),
        FOREIGN KEY(plan_rejected_by) REFERENCES users(id),
        FOREIGN KEY(important_category_id) REFERENCES important_categories(id)
    );
    CREATE TABLE IF NOT EXISTS case_stage_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        stage_id INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        actor_user_id INTEGER NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(case_id) REFERENCES customer_work_cases(id) ON DELETE CASCADE,
        FOREIGN KEY(stage_id) REFERENCES work_stage_catalog(id),
        FOREIGN KEY(actor_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS case_issues(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        stage_id INTEGER,
        issue_text TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'MEDIUM',
        opened_by INTEGER NOT NULL,
        opened_at TEXT NOT NULL,
        resolved_by INTEGER,
        resolved_at TEXT,
        resolution_text TEXT,
        FOREIGN KEY(case_id) REFERENCES customer_work_cases(id) ON DELETE CASCADE,
        FOREIGN KEY(stage_id) REFERENCES work_stage_catalog(id),
        FOREIGN KEY(opened_by) REFERENCES users(id),
        FOREIGN KEY(resolved_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS case_reschedule_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        old_due_at TEXT,
        proposed_due_at TEXT NOT NULL,
        reason TEXT NOT NULL,
        requested_by INTEGER NOT NULL,
        requested_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        decided_by INTEGER,
        decided_at TEXT,
        decision_note TEXT,
        FOREIGN KEY(case_id) REFERENCES customer_work_cases(id) ON DELETE CASCADE,
        FOREIGN KEY(requested_by) REFERENCES users(id),
        FOREIGN KEY(decided_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS case_actions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        actor_user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        detail TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(case_id) REFERENCES customer_work_cases(id) ON DELETE CASCADE,
        FOREIGN KEY(actor_user_id) REFERENCES users(id)
    );
    CREATE INDEX IF NOT EXISTS idx_cw_owner_status ON customer_work_cases(owner_user_id,status);
    CREATE INDEX IF NOT EXISTS idx_cw_stage ON customer_work_cases(current_stage_id);
    CREATE INDEX IF NOT EXISTS idx_cw_due ON customer_work_cases(expected_complete_at);
    CREATE INDEX IF NOT EXISTS idx_cw_approval ON customer_work_cases(plan_approval_status);
    CREATE INDEX IF NOT EXISTS idx_cw_customer ON customer_work_cases(customer_id);
    CREATE INDEX IF NOT EXISTS idx_cw_hist_case ON case_stage_history(case_id,started_at);
    CREATE INDEX IF NOT EXISTS idx_cw_issue_case ON case_issues(case_id,resolved_at);
    CREATE INDEX IF NOT EXISTS idx_cw_resched_status ON case_reschedule_requests(status,requested_at);
    '''
    try:
        with get_conn() as c:
            c.executescript(sql)
            count = int(c.execute("SELECT COUNT(*) FROM work_stage_catalog").fetchone()[0])
            if count == 0:
                ts = now_str()
                for idx, name in enumerate(DEFAULT_STAGES, 1):
                    c.execute(
                        "INSERT INTO work_stage_catalog(name,sort_order,sla_hours,active,is_completion,created_at,updated_at) VALUES(?,?,48,1,?,?,?)",
                        (name, idx, 1 if idx == len(DEFAULT_STAGES) else 0, ts, ts),
                    )
        if logger:
            logger.info("CUSTOMER_WORK_SCHEMA_READY version=%s", VERSION)
    except Exception:
        if logger:
            logger.exception("CUSTOMER_WORK_SCHEMA_FAILED")
        raise


def user_info(c, uid):
    r = c.execute("SELECT id,full_name,role,is_admin,active FROM users WHERE id=?", (uid,)).fetchone()
    return dict(r) if r else None


def is_manager(c, uid):
    u = user_info(c, uid)
    return bool(u and (u.get("role") == "Lãnh đạo phòng" or int(u.get("is_admin") or 0) == 1))


def active_stages(c, include_inactive=False):
    q = "SELECT * FROM work_stage_catalog"
    if not include_inactive:
        q += " WHERE active=1"
    q += " ORDER BY sort_order,id"
    return [dict(r) for r in c.execute(q).fetchall()]


def active_important_categories(c, include_inactive=False):
    q = "SELECT * FROM important_categories"
    if not include_inactive:
        q += " WHERE active=1"
    q += " ORDER BY sort_order,id"
    return [dict(r) for r in c.execute(q).fetchall()]


def customers(c, uid=None):
    if uid is None:
        rows = c.execute("SELECT id,cif,customer_name,qlkh_user_id FROM customers WHERE active=1 ORDER BY customer_name").fetchall()
    else:
        rows = c.execute(
            "SELECT id,cif,customer_name,qlkh_user_id FROM customers WHERE active=1 ORDER BY CASE WHEN qlkh_user_id=? THEN 0 ELSE 1 END,customer_name",
            (uid,),
        ).fetchall()
    return [dict(r) for r in rows]


def staff_users(c):
    return [dict(r) for r in c.execute("SELECT id,full_name,role,is_admin FROM users WHERE active=1 ORDER BY full_name").fetchall()]


def next_case_code(c):
    year = date.today().year
    prefix = f"CVKH-{year}-"
    row = c.execute("SELECT case_code FROM customer_work_cases WHERE case_code LIKE ? ORDER BY id DESC LIMIT 1", (prefix + "%",)).fetchone()
    n = 1
    if row and row[0]:
        try:
            n = int(str(row[0]).split("-")[-1]) + 1
        except Exception:
            pass
    return f"{prefix}{n:04d}"


def _first_stage(c):
    return c.execute("SELECT * FROM work_stage_catalog WHERE active=1 ORDER BY sort_order,id LIMIT 1").fetchone()


def create_case(get_conn, actor_uid, customer_id, title, expected_complete_at=None, owner_uid=None, case_type=None, note=None, stage_id=None, logger=None):
    title = str(title or "").strip()
    if not title:
        raise ValueError("Tên công việc không được để trống")
    ts = now_str()
    with get_conn() as c:
        manager = is_manager(c, actor_uid)
        owner_uid = int(owner_uid or actor_uid)
        if stage_id:
            stage = c.execute("SELECT * FROM work_stage_catalog WHERE id=? AND active=1", (int(stage_id),)).fetchone()
        else:
            stage = _first_stage(c)
        if not stage:
            raise ValueError("Chưa có mục công việc đang hoạt động")
        approval = "APPROVED" if manager else "PENDING"
        approved_by = actor_uid if manager else None
        approved_at = ts if manager else None
        stage_started = ts if manager else None
        code = next_case_code(c)
        cur = c.execute(
            """INSERT INTO customer_work_cases(case_code,customer_id,owner_user_id,title,case_type,current_stage_id,stage_started_at,expected_complete_at,status,plan_approval_status,plan_requested_by,plan_requested_at,plan_approved_by,plan_approved_at,note,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,'ACTIVE',?,?,?,?,?,?,?,?)""",
            (code, int(customer_id), owner_uid, title, case_type, int(stage["id"]), stage_started, expected_complete_at, approval, actor_uid, ts, approved_by, approved_at, note, ts, ts),
        )
        case_id = int(cur.lastrowid)
        if manager:
            c.execute(
                "INSERT INTO case_stage_history(case_id,stage_id,started_at,actor_user_id,note,created_at) VALUES(?,?,?,?,?,?)",
                (case_id, int(stage["id"]), ts, actor_uid, "Khởi tạo công việc", ts),
            )
        c.execute(
            "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
            (case_id, actor_uid, "CREATE", json.dumps({"approval": approval}, ensure_ascii=False), ts),
        )
    if logger:
        logger.info("CUSTOMER_WORK_CREATE id=%s actor=%s approval=%s", case_id, actor_uid, approval)
    return case_id, approval


def approve_case_plan(get_conn, case_id, actor_uid, approve=True, note=None, logger=None):
    ts = now_str()
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được phê duyệt")
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return False
        if approve:
            c.execute(
                "UPDATE customer_work_cases SET plan_approval_status='APPROVED',plan_approved_by=?,plan_approved_at=?,plan_rejected_by=NULL,plan_rejected_at=NULL,approval_note=?,stage_started_at=COALESCE(stage_started_at,?),updated_at=? WHERE id=?",
                (actor_uid, ts, note, ts, ts, case_id),
            )
            exists = c.execute("SELECT 1 FROM case_stage_history WHERE case_id=? AND ended_at IS NULL", (case_id,)).fetchone()
            if not exists and row["current_stage_id"]:
                c.execute(
                    "INSERT INTO case_stage_history(case_id,stage_id,started_at,actor_user_id,note,created_at) VALUES(?,?,?,?,?,?)",
                    (case_id, int(row["current_stage_id"]), ts, actor_uid, "Bắt đầu sau phê duyệt kế hoạch", ts),
                )
            action = "PLAN_APPROVE"
        else:
            c.execute(
                "UPDATE customer_work_cases SET plan_approval_status='REJECTED',plan_rejected_by=?,plan_rejected_at=?,approval_note=?,updated_at=? WHERE id=?",
                (actor_uid, ts, note, ts, case_id),
            )
            action = "PLAN_REJECT"
        c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (case_id, actor_uid, action, note, ts))
    if logger:
        logger.info("CUSTOMER_WORK_PLAN_DECISION case=%s actor=%s approve=%s", case_id, actor_uid, approve)
    return True


def change_stage(get_conn, case_id, actor_uid, new_stage_id, note=None, logger=None):
    ts = now_str()
    with get_conn() as c:
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (case_id,)).fetchone()
        stage = c.execute("SELECT * FROM work_stage_catalog WHERE id=? AND active=1", (new_stage_id,)).fetchone()
        if not row or not stage:
            return False
        if row["plan_approval_status"] != "APPROVED":
            raise ValueError("Kế hoạch chưa được phê duyệt")
        if row["status"] == "COMPLETED":
            raise ValueError("Công việc đã hoàn thành")
        c.execute("UPDATE case_stage_history SET ended_at=? WHERE case_id=? AND ended_at IS NULL", (ts, case_id))
        c.execute(
            "INSERT INTO case_stage_history(case_id,stage_id,started_at,actor_user_id,note,created_at) VALUES(?,?,?,?,?,?)",
            (case_id, int(new_stage_id), ts, actor_uid, note, ts),
        )
        status = "COMPLETED" if int(stage["is_completion"] or 0) else "ACTIVE"
        completed = ts if status == "COMPLETED" else None
        c.execute(
            "UPDATE customer_work_cases SET current_stage_id=?,stage_started_at=?,status=?,completed_at=?,updated_at=? WHERE id=?",
            (int(new_stage_id), ts, status, completed, ts, case_id),
        )
        c.execute(
            "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
            (case_id, actor_uid, "STAGE_CHANGE", json.dumps({"stage_id": int(new_stage_id), "note": note}, ensure_ascii=False), ts),
        )
    if logger:
        logger.info("CUSTOMER_WORK_STAGE case=%s actor=%s stage=%s", case_id, actor_uid, new_stage_id)
    return True


def add_issue(get_conn, case_id, actor_uid, issue_text, severity="MEDIUM", logger=None):
    issue_text = str(issue_text or "").strip()
    if not issue_text:
        raise ValueError("Nội dung vướng mắc không được để trống")
    severity = severity if severity in SEVERITY_LABEL else "MEDIUM"
    ts = now_str()
    with get_conn() as c:
        row = c.execute("SELECT current_stage_id FROM customer_work_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return None
        cur = c.execute(
            "INSERT INTO case_issues(case_id,stage_id,issue_text,severity,opened_by,opened_at) VALUES(?,?,?,?,?,?)",
            (case_id, row[0], issue_text, severity, actor_uid, ts),
        )
        issue_id = int(cur.lastrowid)
        c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (case_id, actor_uid, "ISSUE_OPEN", issue_text, ts))
    if logger:
        logger.info("CUSTOMER_WORK_ISSUE_OPEN case=%s issue=%s", case_id, issue_id)
    return issue_id


def resolve_issue(get_conn, issue_id, actor_uid, resolution_text=None, logger=None):
    ts = now_str()
    with get_conn() as c:
        row = c.execute("SELECT case_id FROM case_issues WHERE id=? AND resolved_at IS NULL", (issue_id,)).fetchone()
        if not row:
            return False
        c.execute("UPDATE case_issues SET resolved_by=?,resolved_at=?,resolution_text=? WHERE id=?", (actor_uid, ts, resolution_text, issue_id))
        c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (int(row[0]), actor_uid, "ISSUE_RESOLVE", resolution_text, ts))
    if logger:
        logger.info("CUSTOMER_WORK_ISSUE_RESOLVE issue=%s actor=%s", issue_id, actor_uid)
    return True


def request_reschedule(get_conn, case_id, actor_uid, proposed_due_at, reason, logger=None):
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Phải nhập lý do dời thời gian")
    ts = now_str()
    with get_conn() as c:
        row = c.execute("SELECT expected_complete_at FROM customer_work_cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return None, "NOT_FOUND"
        manager = is_manager(c, actor_uid)
        status = "APPROVED" if manager else "PENDING"
        cur = c.execute(
            """INSERT INTO case_reschedule_requests(case_id,old_due_at,proposed_due_at,reason,requested_by,requested_at,status,decided_by,decided_at,decision_note)
            VALUES(?,?,?,?,?,?,?, ?,?,?)""",
            (case_id, row[0], proposed_due_at, reason, actor_uid, ts, status, actor_uid if manager else None, ts if manager else None, "Tự phê duyệt bởi Lãnh đạo/Admin" if manager else None),
        )
        req_id = int(cur.lastrowid)
        if manager:
            c.execute("UPDATE customer_work_cases SET expected_complete_at=?,updated_at=? WHERE id=?", (proposed_due_at, ts, case_id))
        c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (case_id, actor_uid, "RESCHEDULE_REQUEST", json.dumps({"proposed": proposed_due_at, "status": status, "reason": reason}, ensure_ascii=False), ts))
    if logger:
        logger.info("CUSTOMER_WORK_RESCHEDULE_REQUEST case=%s actor=%s status=%s", case_id, actor_uid, status)
    return req_id, status


def decide_reschedule(get_conn, request_id, actor_uid, approve=True, note=None, logger=None):
    ts = now_str()
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được phê duyệt")
        r = c.execute("SELECT * FROM case_reschedule_requests WHERE id=? AND status='PENDING'", (request_id,)).fetchone()
        if not r:
            return False
        status = "APPROVED" if approve else "REJECTED"
        c.execute("UPDATE case_reschedule_requests SET status=?,decided_by=?,decided_at=?,decision_note=? WHERE id=?", (status, actor_uid, ts, note, request_id))
        if approve:
            c.execute("UPDATE customer_work_cases SET expected_complete_at=?,updated_at=? WHERE id=?", (r["proposed_due_at"], ts, r["case_id"]))
        c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (r["case_id"], actor_uid, "RESCHEDULE_DECISION", json.dumps({"status": status, "note": note}, ensure_ascii=False), ts))
    if logger:
        logger.info("CUSTOMER_WORK_RESCHEDULE_DECISION request=%s actor=%s approve=%s", request_id, actor_uid, approve)
    return True


def set_importance(get_conn, case_id, actor_uid, category_id=None, urgent_override=None, logger=None):
    ts = now_str()
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được gán công việc quan trọng")
        important = 1 if category_id else 0
        c.execute(
            "UPDATE customer_work_cases SET important_category_id=?,is_important=?,urgent_override=?,updated_at=? WHERE id=?",
            (int(category_id) if category_id else None, important, urgent_override, ts, case_id),
        )
        c.execute("INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)", (case_id, actor_uid, "PRIORITY_SET", json.dumps({"category_id": category_id, "urgent_override": urgent_override}, ensure_ascii=False), ts))
    if logger:
        logger.info("CUSTOMER_WORK_PRIORITY case=%s actor=%s category=%s", case_id, actor_uid, category_id)
    return True


def _case_select_sql():
    return '''SELECT w.*,c.cif,c.customer_name,u.full_name AS owner_name,
                     s.name AS stage_name,s.sla_hours,s.sort_order,s.is_completion,
                     ic.name AS important_category,
                     (SELECT COUNT(*) FROM case_issues i WHERE i.case_id=w.id AND i.resolved_at IS NULL) AS open_issue_count
              FROM customer_work_cases w
              JOIN customers c ON c.id=w.customer_id
              JOIN users u ON u.id=w.owner_user_id
              LEFT JOIN work_stage_catalog s ON s.id=w.current_stage_id
              LEFT JOIN important_categories ic ON ic.id=w.important_category_id'''


def list_cases(c, uid=None, manager=False, include_completed=False):
    sql = _case_select_sql() + " WHERE 1=1"
    args = []
    if not manager and uid is not None:
        sql += " AND w.owner_user_id=?"
        args.append(int(uid))
    if not include_completed:
        sql += " AND w.status<>'COMPLETED'"
    sql += " ORDER BY CASE WHEN w.expected_complete_at IS NULL THEN 1 ELSE 0 END,w.expected_complete_at,w.id DESC"
    return [enrich_case(dict(r)) for r in c.execute(sql, args).fetchall()]


def get_case(c, case_id):
    r = c.execute(_case_select_sql() + " WHERE w.id=?", (case_id,)).fetchone()
    return enrich_case(dict(r)) if r else None


def case_history(c, case_id):
    return [dict(r) for r in c.execute(
        """SELECT h.*,s.name AS stage_name,u.full_name AS actor_name
           FROM case_stage_history h JOIN work_stage_catalog s ON s.id=h.stage_id JOIN users u ON u.id=h.actor_user_id
           WHERE h.case_id=? ORDER BY h.started_at DESC,h.id DESC""", (case_id,)).fetchall()]


def case_issues(c, case_id, include_resolved=True):
    q = """SELECT i.*,s.name AS stage_name,u.full_name AS opened_by_name,ru.full_name AS resolved_by_name
           FROM case_issues i LEFT JOIN work_stage_catalog s ON s.id=i.stage_id
           JOIN users u ON u.id=i.opened_by LEFT JOIN users ru ON ru.id=i.resolved_by WHERE i.case_id=?"""
    if not include_resolved:
        q += " AND i.resolved_at IS NULL"
    q += " ORDER BY CASE WHEN i.resolved_at IS NULL THEN 0 ELSE 1 END,i.opened_at DESC"
    return [dict(r) for r in c.execute(q, (case_id,)).fetchall()]


def pending_case_approvals(c):
    plans = [dict(r) for r in c.execute(_case_select_sql() + " WHERE w.plan_approval_status='PENDING' ORDER BY w.plan_requested_at,w.id").fetchall()]
    reschedules = [dict(r) for r in c.execute(
        """SELECT r.*,w.case_code,w.title,c.customer_name,u.full_name AS requester_name
           FROM case_reschedule_requests r JOIN customer_work_cases w ON w.id=r.case_id JOIN customers c ON c.id=w.customer_id JOIN users u ON u.id=r.requested_by
           WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
    return plans, reschedules


def enrich_case(x, reference=None):
    reference = reference or now_dt()
    start = parse_dt(x.get("stage_started_at"))
    elapsed = max(0.0, (reference - start).total_seconds() / 3600.0) if start else 0.0
    sla = float(x.get("sla_hours") or 0)
    ratio = (elapsed / sla) if sla > 0 else 0.0
    delayed = bool(sla > 0 and elapsed > sla and x.get("status") != "COMPLETED")
    warning = bool(sla > 0 and 0.8 <= ratio <= 1.0 and x.get("status") != "COMPLETED")
    due = parse_dt(x.get("expected_complete_at"))
    overdue = bool(due and due < reference and x.get("status") != "COMPLETED")
    urgent_auto = bool(overdue or (due and due <= reference + timedelta(hours=24)))
    override = x.get("urgent_override")
    urgent = urgent_auto if override is None else bool(int(override))
    important = bool(int(x.get("is_important") or 0))
    quadrant = 1 if important and urgent else 2 if important else 3 if urgent else 4
    x.update(stage_elapsed_hours=elapsed, stage_delay_ratio=ratio, is_stage_delayed=delayed, is_stage_warning=warning, is_overdue=overdue, is_urgent=urgent, quadrant=quadrant)
    return x


def duration_text(hours):
    hours = max(0.0, float(hours or 0))
    days = int(hours // 24)
    hrs = int(hours % 24)
    mins = int(round((hours - int(hours)) * 60))
    if days:
        return f"{days} ngày {hrs} giờ"
    if hrs:
        return f"{hrs} giờ {mins} phút" if mins else f"{hrs} giờ"
    return f"{mins} phút"


def quadrant_label(q):
    return {
        1: "I · Quan trọng & Khẩn cấp",
        2: "II · Quan trọng & Chưa khẩn cấp",
        3: "III · Khẩn cấp & Không quan trọng",
        4: "IV · Không quan trọng & Chưa khẩn cấp",
    }.get(int(q or 4), "IV · Không quan trọng & Chưa khẩn cấp")


def save_stage_catalog(get_conn, actor_uid, stage_id, name, sort_order, sla_hours, is_completion=False, active=True, logger=None):
    ts = now_str()
    name = str(name or "").strip()
    if not name:
        raise ValueError("Tên mục công việc không được để trống")
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được sửa danh mục")
        if stage_id:
            c.execute("UPDATE work_stage_catalog SET name=?,sort_order=?,sla_hours=?,is_completion=?,active=?,updated_by=?,updated_at=? WHERE id=?", (name, int(sort_order), float(sla_hours), 1 if is_completion else 0, 1 if active else 0, actor_uid, ts, int(stage_id)))
        else:
            c.execute("INSERT INTO work_stage_catalog(name,sort_order,sla_hours,active,is_completion,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (name, int(sort_order), float(sla_hours), 1 if active else 0, 1 if is_completion else 0, actor_uid, actor_uid, ts, ts))
    if logger:
        logger.info("CUSTOMER_WORK_STAGE_CATALOG_SAVE actor=%s id=%s name=%s", actor_uid, stage_id, name)


def delete_stage_catalog(get_conn, actor_uid, stage_id, logger=None):
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được sửa danh mục")
        used = c.execute("SELECT 1 FROM case_stage_history WHERE stage_id=? LIMIT 1", (stage_id,)).fetchone() or c.execute("SELECT 1 FROM customer_work_cases WHERE current_stage_id=? LIMIT 1", (stage_id,)).fetchone()
        if used:
            c.execute("UPDATE work_stage_catalog SET active=0,updated_by=?,updated_at=? WHERE id=?", (actor_uid, now_str(), stage_id))
            mode = "DEACTIVATE"
        else:
            c.execute("DELETE FROM work_stage_catalog WHERE id=?", (stage_id,))
            mode = "DELETE"
    if logger:
        logger.info("CUSTOMER_WORK_STAGE_CATALOG_%s actor=%s id=%s", mode, actor_uid, stage_id)
    return mode


def save_important_category(get_conn, actor_uid, category_id, name, description=None, sort_order=0, active=True, logger=None):
    ts = now_str()
    name = str(name or "").strip()
    if not name:
        raise ValueError("Tên danh mục quan trọng không được để trống")
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được sửa danh mục")
        if category_id:
            c.execute("UPDATE important_categories SET name=?,description=?,sort_order=?,active=?,updated_by=?,updated_at=? WHERE id=?", (name, description, int(sort_order), 1 if active else 0, actor_uid, ts, int(category_id)))
        else:
            c.execute("INSERT INTO important_categories(name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (name, description, int(sort_order), 1 if active else 0, actor_uid, actor_uid, ts, ts))
    if logger:
        logger.info("CUSTOMER_WORK_IMPORTANCE_CATALOG_SAVE actor=%s id=%s name=%s", actor_uid, category_id, name)


def delete_important_category(get_conn, actor_uid, category_id, logger=None):
    with get_conn() as c:
        if not is_manager(c, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo/Admin được sửa danh mục")
        used = c.execute("SELECT 1 FROM customer_work_cases WHERE important_category_id=? LIMIT 1", (category_id,)).fetchone()
        if used:
            c.execute("UPDATE important_categories SET active=0,updated_by=?,updated_at=? WHERE id=?", (actor_uid, now_str(), category_id))
            mode = "DEACTIVATE"
        else:
            c.execute("DELETE FROM important_categories WHERE id=?", (category_id,))
            mode = "DELETE"
    if logger:
        logger.info("CUSTOMER_WORK_IMPORTANCE_CATALOG_%s actor=%s id=%s", mode, actor_uid, category_id)
    return mode
