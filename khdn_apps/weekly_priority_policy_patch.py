"""Weekly Plan focus-priority governance (Q2-first) and weekly lifecycle.

Implements the approved specification:
- Q2 Focus is decided only by a leader-issued focus catalog, scoped by leader/year.
- If not Q2: due within 7 days + KPI/material risk => Q1; due within 7 days
  without KPI/material risk => Q3; otherwise Q4.
- Weekly plan lifecycle NHAP -> DA_NOP -> TRA_LAI/NHAP -> DA_DUYET ->
  DA_CHOT -> DA_DANH_GIA.
- Manager override is audited; classification locks at DA_CHOT and Admin can
  unlock with a reason.
- Controls: minimum 3 distinct Q2 focus categories to submit, Q4 hour warning, Q2 carry-over watch,
  manager-removal drift warning, stale focus-catalog reminder, emergent work,
  and carry-forward.
"""
from __future__ import annotations

import html
import json
import logging
from datetime import date, datetime, time, timedelta

from khdn_apps import planning_ui_v4_patch as nav4
from khdn_apps import planning_usability_v2_patch as priority_v2
from khdn_apps import catalog_edit_state_patch as catalog_state
from khdn_apps import weekly_push

NOTIFICATION_LOGGER = logging.getLogger("khdn_weekly_push")

VERSION = "1.0.1"

PRIORITY = {
    2: "🟠 Q2 · Trọng tâm",
    1: "🔴 Q1 · Cấp thiết",
    3: "🟡 Q3 · Phân tâm",
    4: "🟢 Q4 · Giá trị thấp",
}
PRIORITY_SHORT = {2: "Q2 · Trọng tâm", 1: "Q1 · Cấp thiết", 3: "Q3 · Phân tâm", 4: "Q4 · Giá trị thấp"}
PRIORITY_ORDER = (2, 1, 3, 4)
PLAN_STATUS = {
    "NHAP": "Đang soạn",
    "DA_NOP": "Đã nộp · chờ duyệt",
    "TRA_LAI": "Trả lại · cần điều chỉnh",
    "DA_DUYET": "Đã duyệt · đang thực hiện",
    "DA_CHOT": "Đã chốt tuần",
    "DA_DANH_GIA": "Đã đánh giá",
}


def _cols(c, table):
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _add(c, table, name, ddl):
    if name not in _cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _is_admin(u):
    return bool(_uget(u, "is_admin", False))


def _is_leader(u):
    return str(_uget(u, "role", "")) == "Lãnh đạo phòng"


def _manager(u):
    return _is_leader(u) or _is_admin(u)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _leader_for_staff(c, uid):
    """Best available direct-leader mapping without breaking legacy user schema."""
    ucols = _cols(c, "users")
    row = c.execute("SELECT * FROM users WHERE id=?", (int(uid),)).fetchone()
    if not row:
        return None
    d = dict(row)
    if str(d.get("role") or "") == "Lãnh đạo phòng":
        return int(uid)
    for name in ("manager_user_id", "leader_user_id", "supervisor_user_id"):
        if name in ucols and d.get(name):
            return int(d[name])
    # Customer Work already stores the leader/controller selected for each case.
    if "customer_work_cases" in {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
        ccols = _cols(c, "customer_work_cases")
        if "controller_user_id" in ccols:
            hit = c.execute(
                "SELECT controller_user_id,COUNT(*) n FROM customer_work_cases "
                "WHERE owner_user_id=? AND controller_user_id IS NOT NULL "
                "GROUP BY controller_user_id ORDER BY n DESC,MAX(id) DESC LIMIT 1",
                (int(uid),),
            ).fetchone()
            if hit and hit[0]:
                return int(hit[0])
    leaders = c.execute("SELECT id FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY id").fetchall()
    if len(leaders) == 1:
        return int(leaders[0][0])
    return None


def _scope_key(c, uid):
    leader = _leader_for_staff(c, uid)
    return f"LEADER:{leader}" if leader else "DEFAULT"


def _direct_scope_ok(c, leader_uid, staff_uid, admin=False):
    if admin:
        return True
    target = _leader_for_staff(c, staff_uid)
    return target is None or int(target) == int(leader_uid)


def _notify(c, user_id, title, body):
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='notifications'").fetchone():
        NOTIFICATION_LOGGER.warning("WEEKLY_NOTIFICATION_SCHEMA_NOT_READY user_id=%s", user_id)
        return
    c.execute("SAVEPOINT khdn_plan_notification")
    try:
        nid = weekly_push.enqueue(c, int(user_id), title, body)
        c.execute("RELEASE SAVEPOINT khdn_plan_notification")
        return nid
    except Exception:
        c.execute("ROLLBACK TO SAVEPOINT khdn_plan_notification")
        c.execute("RELEASE SAVEPOINT khdn_plan_notification")
        NOTIFICATION_LOGGER.exception("WEEKLY_NOTIFICATION_ENQUEUE_FAILED user_id=%s", user_id)
        return None


def _ensure_schema(core, get_conn, logger=None):
    core.ensure_schema(get_conn, logger)
    with get_conn() as c:
        for name, ddl in (
            ("workflow_status", "TEXT NOT NULL DEFAULT 'NHAP'"),
            ("submitted_at", "TEXT"), ("returned_at", "TEXT"), ("returned_by", "INTEGER"),
            ("return_note", "TEXT"), ("approved_at", "TEXT"), ("approved_by", "INTEGER"),
            ("self_score", "REAL"), ("self_strengths", "TEXT"), ("self_issues", "TEXT"),
            ("self_causes", "TEXT"), ("self_proposals", "TEXT"), ("closed_at", "TEXT"),
            ("leader_score", "REAL"), ("leader_comment", "TEXT"), ("evaluated_at", "TEXT"),
            ("evaluated_by", "INTEGER"), ("classification_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("unlocked_at", "TEXT"), ("unlocked_by", "INTEGER"), ("unlock_reason", "TEXT"),
        ):
            _add(c, "weekly_plans", name, ddl)
        for name, ddl in (
            ("focus_category_id", "INTEGER"), ("focus_code_snapshot", "TEXT"),
            ("focus_name_snapshot", "TEXT"), ("focus_desc_snapshot", "TEXT"),
            ("deadline_within_7d", "INTEGER"), ("kpi_risk_flag", "INTEGER"),
            ("priority_basis", "TEXT"), ("estimated_hours", "REAL NOT NULL DEFAULT 1.0"),
            ("actual_hours", "REAL NOT NULL DEFAULT 0.0"), ("expected_output", "TEXT"),
            ("is_emergent", "INTEGER NOT NULL DEFAULT 0"), ("carryover_count", "INTEGER NOT NULL DEFAULT 0"),
            ("carried_from_item_id", "INTEGER"), ("classification_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("q2_watch_flag", "INTEGER NOT NULL DEFAULT 0"),
        ):
            _add(c, "weekly_plan_items", name, ddl)
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS weekly_focus_categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_key TEXT NOT NULL,
                apply_year INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER,
                updated_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(department_key,apply_year,code)
            );
            CREATE INDEX IF NOT EXISTS idx_wfc_scope_year ON weekly_focus_categories(department_key,apply_year,active,sort_order);
            CREATE TABLE IF NOT EXISTS weekly_classification_audit(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                actor_user_id INTEGER NOT NULL,
                old_focus_category_id INTEGER,
                new_focus_category_id INTEGER,
                old_quadrant INTEGER,
                new_quadrant INTEGER,
                old_basis TEXT,
                new_basis TEXT,
                reason TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_wca_item ON weekly_classification_audit(item_id,created_at);
            """
        )
        # Existing plans/items become editable drafts only if they have never been governed.
        c.execute("UPDATE weekly_plans SET workflow_status='NHAP' WHERE workflow_status IS NULL OR workflow_status='' OR workflow_status='ACTIVE'")
    if logger:
        logger.info("WEEKLY_PRIORITY_POLICY_SCHEMA_READY version=%s", VERSION)


def _focus_categories(c, scope, year, include_inactive=False):
    sql = "SELECT * FROM weekly_focus_categories WHERE department_key=? AND apply_year=?"
    params = [str(scope), int(year)]
    if not include_inactive:
        sql += " AND active=1"
    sql += " ORDER BY sort_order,id"
    return [dict(r) for r in c.execute(sql, params).fetchall()]


def _classify(focus, due7, risk):
    if focus:
        return 2, "FOCUS_CATALOG"
    if due7 is False:
        return 4, "NOT_DUE_7D"
    if due7 is True:
        if risk is True:
            return 1, "DUE_7D_KPI_RISK"
        if risk is False:
            return 3, "DUE_7D_NO_KPI_RISK"
    return None, None


def _focus_snapshot(c, focus_id):
    if not focus_id:
        return None
    r = c.execute("SELECT * FROM weekly_focus_categories WHERE id=?", (int(focus_id),)).fetchone()
    return dict(r) if r else None


def _set_classification(c, item_id, actor_uid, focus_id, due7, risk, reason="", allow_locked=False):
    row = c.execute(
        "SELECT w.*,p.workflow_status,p.classification_locked AS plan_locked FROM weekly_plan_items w "
        "JOIN weekly_plans p ON p.id=w.plan_id WHERE w.id=?", (int(item_id),)
    ).fetchone()
    if not row:
        return False
    old = dict(row)
    if (int(old.get("classification_locked") or 0) or int(old.get("plan_locked") or 0)) and not allow_locked:
        raise ValueError("Phân loại đã bị khóa sau khi kế hoạch chốt.")
    focus = _focus_snapshot(c, focus_id)
    q, basis = _classify(focus, due7, risk)
    if q is None:
        raise ValueError("Chưa đủ căn cứ để xác định góc phần tư.")
    ts = _now()
    c.execute(
        """UPDATE weekly_plan_items SET focus_category_id=?,focus_code_snapshot=?,focus_name_snapshot=?,focus_desc_snapshot=?,
           deadline_within_7d=?,kpi_risk_flag=?,priority_quadrant=?,priority_basis=?,updated_at=? WHERE id=?""",
        (
            int(focus_id) if focus else None,
            focus.get("code") if focus else None,
            focus.get("name") if focus else None,
            focus.get("description") if focus else None,
            None if focus else (1 if due7 is True else 0 if due7 is False else None),
            None if focus or due7 is False else (1 if risk is True else 0 if risk is False else None),
            int(q), basis, ts, int(item_id),
        ),
    )
    changed = (
        old.get("focus_category_id") != (int(focus_id) if focus else None)
        or int(old.get("priority_quadrant") or 0) != int(q)
    )
    if changed:
        c.execute(
            """INSERT INTO weekly_classification_audit(item_id,actor_user_id,old_focus_category_id,new_focus_category_id,
               old_quadrant,new_quadrant,old_basis,new_basis,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                int(item_id), int(actor_uid), old.get("focus_category_id"), int(focus_id) if focus else None,
                old.get("priority_quadrant"), int(q), old.get("priority_basis"), basis, str(reason or ""), ts,
            ),
        )
        c.execute(
            "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'CLASSIFICATION_CHANGE',?,?)",
            (int(item_id), int(actor_uid), json.dumps({"old_q": old.get("priority_quadrant"), "new_q": q, "old_focus": old.get("focus_category_id"), "new_focus": int(focus_id) if focus else None, "reason": reason}, ensure_ascii=False), ts),
        )
        if int(actor_uid) != int(old.get("user_id") or 0):
            _notify(c, int(old.get("user_id")), "🎯 Phân loại kế hoạch được điều chỉnh", f"{old.get('title')}: {PRIORITY_SHORT.get(int(q), q)}. {reason or ''}".strip())
    return True


def _plan_row(c, uid, ws, core):
    pid = core.ensure_plan(c, int(uid), ws)
    r = c.execute("SELECT * FROM weekly_plans WHERE id=?", (pid,)).fetchone()
    return dict(r)


def _status_badge(st, status):
    label = PLAN_STATUS.get(status, status)
    colors = {
        "NHAP": ("#0F746B", "rgba(15,116,107,.14)"), "TRA_LAI": ("#D92D20", "rgba(217,45,32,.12)"),
        "DA_NOP": ("#F79009", "rgba(247,144,9,.13)"), "DA_DUYET": ("#12B76A", "rgba(18,183,106,.12)"),
        "DA_CHOT": ("#7F56D9", "rgba(127,86,217,.12)"), "DA_DANH_GIA": ("#1570EF", "rgba(21,112,239,.12)"),
    }
    fg, bg = colors.get(status, ("#667085", "rgba(102,112,133,.12)"))
    st.markdown(f"<span style='display:inline-block;padding:5px 10px;border-radius:999px;font-weight:900;color:{fg};background:{bg};border:1px solid {fg}'>● {html.escape(label)}</span>", unsafe_allow_html=True)


def _cmd_nav(st, key, options, default):
    return nav4._hard_command_nav(st, key, options, default=default, prefix=key)


def _classification_form(st, focus_rows, prefix, initial=None):
    initial = initial or {}
    selected_focus = None
    focus_options = [None, "NONE"] + list(focus_rows)
    def fmt(x):
        if x is None: return "— Chọn —"
        if x == "NONE": return "Không thuộc mục trọng tâm nào"
        return f"{x.get('code')} · {x.get('name')}"
    current_focus = initial.get("focus_category_id")
    idx = 0
    if current_focus:
        for i, x in enumerate(focus_options):
            if isinstance(x, dict) and int(x.get("id") or 0) == int(current_focus):
                idx = i; break
    elif initial.get("priority_quadrant"):
        idx = 1
    choice = st.selectbox("1. Việc này thuộc danh mục công việc trọng tâm nào của phòng? *", focus_options, index=idx, format_func=fmt, key=f"{prefix}_focus")
    if isinstance(choice, dict):
        selected_focus = choice
        st.success("→ Tự động phân loại: **Q2 · Trọng tâm**. Không cần trả lời thêm.")
        return selected_focus, None, None, 2
    if choice == "NONE":
        due_init = initial.get("deadline_within_7d")
        due_opts = [None, True, False]
        due_idx = 0 if due_init is None else (1 if int(due_init) else 2)
        due7 = st.selectbox("2. Việc này có hạn hoàn thành trong 7 ngày tới không? *", due_opts, index=due_idx, format_func=lambda x: "— Chọn —" if x is None else "Có" if x else "Không", key=f"{prefix}_due7")
        if due7 is False:
            st.info("→ Tự động phân loại: **Q4 · Giá trị thấp**.")
            return None, False, None, 4
        if due7 is True:
            risk_init = initial.get("kpi_risk_flag")
            risk_opts = [None, True, False]
            risk_idx = 0 if risk_init is None else (1 if int(risk_init) else 2)
            risk = st.selectbox("3. Việc này có gắn với chỉ tiêu được giao hoặc rủi ro trọng yếu không? *", risk_opts, index=risk_idx, format_func=lambda x: "— Chọn —" if x is None else "Có" if x else "Không", key=f"{prefix}_risk")
            if risk is True:
                st.error("→ Tự động phân loại: **Q1 · Cấp thiết**.")
                return None, True, True, 1
            if risk is False:
                st.warning("→ Tự động phân loại: **Q3 · Phân tâm**.")
                return None, True, False, 3
    return None, None, None, None


def _q2_focus_count(items):
    """Count catalog categories once, regardless of task title/customer/day."""
    return len({
        int(x["focus_category_id"])
        for x in items
        if x.get("status") != "CANCELLED"
        and int(x.get("priority_quadrant") or 4) == 2
        and int(x.get("focus_category_id") or 0) > 0
    })


def _summary(st, items):
    live = [x for x in items if x.get("status") != "CANCELLED"]
    total_hours = sum(float(x.get("estimated_hours") or 0) for x in live)
    counts = {q: sum(int(x.get("priority_quadrant") or 4) == q for x in live) for q in PRIORITY_ORDER}
    hours = {q: sum(float(x.get("estimated_hours") or 0) for x in live if int(x.get("priority_quadrant") or 4) == q) for q in PRIORITY_ORDER}
    targets = {2: "≥ 60%", 1: "≤ 20%", 3: "≤ 15%", 4: "≤ 5%"}
    cols = st.columns(4)
    for col, q in zip(cols, PRIORITY_ORDER):
        pct = hours[q] / total_hours * 100 if total_hours else 0
        value = f"{_q2_focus_count(live)} mục" if q == 2 else counts[q]
        detail = f"{counts[q]} việc · " if q == 2 else ""
        col.metric(PRIORITY_SHORT[q], value, f"{detail}{hours[q]:.1f}h · {pct:.0f}% · MT {targets[q]}")
    st.caption("Mỗi mục công việc trọng tâm Q2 chỉ tính một lần trong tuần, kể cả khi có nhiều đầu việc cùng mục.")
    return counts, hours, total_hours


def _item_card(st, x, editable=False):
    q = int(x.get("priority_quadrant") or 4)
    focus = str(x.get("focus_name_snapshot") or "")
    emergent = " · ⚡ PHÁT SINH" if int(x.get("is_emergent") or 0) else ""
    carry = f" · ↪ Chuyển tiếp {int(x.get('carryover_count') or 0)} lần" if int(x.get("carryover_count") or 0) else ""
    watch = " · 🚩 Q2 lùi ≥2 tuần" if int(x.get("q2_watch_flag") or 0) else ""
    with st.container(border=True):
        st.markdown(f"**{html.escape(str(x.get('title') or ''))}**  \n{PRIORITY.get(q, q)}{emergent}{carry}{watch}")
        meta = [str(x.get("work_date") or "")[:10], f"Ước lượng {float(x.get('estimated_hours') or 0):.1f}h", str(x.get("customer_text") or "")]
        st.caption(" · ".join(v for v in meta if v))
        if focus:
            st.caption(f"🎯 Trọng tâm: {x.get('focus_code_snapshot') or ''} · {focus}")
        if x.get("expected_output"):
            st.caption(f"Kết quả đầu ra: {x.get('expected_output')}")
        if editable:
            return st.button("✏️ Sửa", key=f"policy_edit_{x['id']}")
    return False


def _planning_window(ws):
    start = datetime.combine(ws - timedelta(days=3), time(16, 0))
    end = datetime.combine(ws, time(9, 0))
    return start, end


def _default_week(core):
    now = datetime.now()
    ws = core.week_start(now)
    # From Friday 16:00 through Sunday, the relevant planning week is next week.
    if now.weekday() > 4 or (now.weekday() == 4 and now.time() >= time(16, 0)):
        ws += timedelta(days=7)
    return ws


def _save_extended_item(core, get_conn, uid, ws, item, logger=None):
    with get_conn() as c:
        before = int(c.execute("SELECT COALESCE(MAX(id),0) FROM weekly_plan_items").fetchone()[0] or 0)
    n, errs = core.save_items(get_conn, uid, ws, [item], logger)
    if not n:
        return None, errs
    with get_conn() as c:
        row = c.execute("SELECT id FROM weekly_plan_items WHERE user_id=? AND id>? ORDER BY id LIMIT 1", (int(uid), before)).fetchone()
        if not row:
            return None, ["Không xác định được công việc vừa tạo"]
        iid = int(row[0])
        c.execute(
            "UPDATE weekly_plan_items SET estimated_hours=?,actual_hours=?,expected_output=?,is_emergent=?,carryover_count=?,carried_from_item_id=? WHERE id=?",
            (float(item.get("estimated_hours") or 1), float(item.get("actual_hours") or 0), str(item.get("expected_output") or ""), int(bool(item.get("is_emergent"))), int(item.get("carryover_count") or 0), item.get("carried_from_item_id"), iid),
        )
        _set_classification(c, iid, uid, item.get("focus_category_id"), item.get("deadline_within_7d"), item.get("kpi_risk_flag"), reason="Phân loại khi tạo kế hoạch")
        if int(item.get("is_emergent") or 0):
            c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE id=?", (int(uid), _now(), iid))
            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PHAT_SINH','Công việc phát sinh trong tuần',?)", (iid, int(uid), _now()))
    return iid, errs


def _add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False, logger=None):
    uid = int(_uget(u, "id"))
    prefix = f"wp_policy_add_{ws.isoformat()}_{'ps' if emergent else 'plan'}"
    st.markdown("#### ⚡ Công việc phát sinh" if emergent else "#### ＋ Thêm công việc kế hoạch")
    title = st.text_input("Công việc *", key=f"{prefix}_title", placeholder="Ví dụ: Gặp Công ty A – tiếp thị tiền gửi")
    with get_conn() as c:
        cs = core.customers(c, uid)
    customer = st.selectbox("Khách hàng", [None] + cs, index=0, format_func=lambda x: "— Không gắn khách hàng —" if x is None else f"{x.get('customer_name')} · {'CIF '+str(x.get('cif')) if x.get('cif') else 'Chưa có CIF'}", key=f"{prefix}_customer")
    c1, c2 = st.columns(2)
    day = c1.date_input("Ngày thực hiện *", value=max(ws, date.today()) if ws <= max(ws, date.today()) <= ws + timedelta(days=6) else ws, min_value=ws, max_value=ws + timedelta(days=6), key=f"{prefix}_day")
    est = c2.number_input("Giờ dự kiến *", min_value=0.25, max_value=40.0, value=1.0, step=0.25, key=f"{prefix}_hours")
    output = st.text_input("Kết quả đầu ra *", key=f"{prefix}_output", placeholder="Ví dụ: Hoàn thành hồ sơ trình / biên bản gặp KH / báo cáo...")
    focus, due7, risk, q = _classification_form(st, focus_rows, prefix)
    ok = st.button("Lưu công việc phát sinh" if emergent else "Thêm vào kế hoạch", key=f"{prefix}_save", type="primary", use_container_width=True)
    if ok:
        if not str(title).strip() or not str(output).strip() or q is None:
            st.error("Vui lòng nhập Công việc, Kết quả đầu ra và trả lời đủ câu hỏi phân loại.")
            return
        item = {
            "work_date": day.isoformat(), "start_time": None, "daypart": None,
            "title": str(title).strip(), "customer_id": int(customer["id"]) if customer else None,
            "customer_text": str(customer.get("customer_name") or "") if customer else "",
            "category": "Công việc phát sinh" if emergent else "Kế hoạch tuần",
            "purposes": [], "source_text": str(title).strip(), "linked_task_id": None,
            "note": None, "estimated_hours": float(est), "expected_output": str(output).strip(),
            "is_emergent": 1 if emergent else 0,
            "focus_category_id": int(focus["id"]) if focus else None,
            "deadline_within_7d": due7, "kpi_risk_flag": risk,
        }
        iid, errs = _save_extended_item(core, get_conn, uid, ws, item, logger)
        if iid:
            st.toast("Đã thêm công việc.", icon="✅"); st.rerun()
        else:
            st.error("; ".join(errs or ["Không thể tạo công việc"]))


def _carry_forward_ui(st, u, core, get_conn, ws, focus_rows, current_count, logger=None):
    uid = int(_uget(u, "id"))
    prev = ws - timedelta(days=7)
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM weekly_plan_items WHERE user_id=? AND work_date>=? AND work_date<? AND status NOT IN ('DONE','CANCELLED') ORDER BY id",
            (uid, prev.isoformat(), ws.isoformat()),
        ).fetchall()]
    if not rows:
        return
    with st.expander(f"↪ Công việc tuần trước chưa hoàn thành · {len(rows)}", expanded=False):
        for x in rows:
            q = int(x.get("priority_quadrant") or 4)
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{x.get('title')}** · {PRIORITY_SHORT.get(q, q)} · đã chuyển {int(x.get('carryover_count') or 0)} lần")
            if c2.button("Chuyển tiếp", key=f"carry_{x['id']}", use_container_width=True, disabled=current_count >= 7):
                item = {
                    "work_date": ws.isoformat(), "title": x.get("title"), "customer_id": x.get("customer_id"),
                    "customer_text": x.get("customer_text") or "", "category": x.get("category") or "Kế hoạch tuần",
                    "purposes": [], "source_text": x.get("source_text") or x.get("title"), "linked_task_id": x.get("linked_task_id"),
                    "estimated_hours": float(x.get("estimated_hours") or 1), "expected_output": x.get("expected_output") or "",
                    "carryover_count": int(x.get("carryover_count") or 0) + 1, "carried_from_item_id": int(x["id"]),
                    "focus_category_id": x.get("focus_category_id"),
                    "deadline_within_7d": None if x.get("focus_category_id") else bool(x.get("deadline_within_7d")) if x.get("deadline_within_7d") is not None else False,
                    "kpi_risk_flag": None if x.get("focus_category_id") else bool(x.get("kpi_risk_flag")) if x.get("kpi_risk_flag") is not None else None,
                }
                iid, _ = _save_extended_item(core, get_conn, uid, ws, item, logger)
                if iid:
                    with get_conn() as c:
                        if q == 2 and int(item["carryover_count"]) >= 2:
                            c.execute("UPDATE weekly_plan_items SET q2_watch_flag=1 WHERE id=?", (iid,))
                    st.toast("Đã chuyển tiếp công việc và giữ nguyên lịch sử phân loại.", icon="✅"); st.rerun()


def _drift_warning(st, get_conn, uid, ws):
    prev = ws - timedelta(days=7)
    with get_conn() as c:
        n = int(c.execute(
            """SELECT COUNT(*) FROM weekly_classification_audit a JOIN weekly_plan_items w ON w.id=a.item_id
               WHERE w.user_id=? AND a.old_focus_category_id IS NOT NULL AND a.new_focus_category_id IS NULL
                 AND a.actor_user_id<>? AND a.created_at>=? AND a.created_at<?""",
            (int(uid), int(uid), prev.isoformat(), ws.isoformat()),
        ).fetchone()[0] or 0)
    if n >= 3:
        st.warning(f"⚠ Tuần trước có {n} công việc được Trưởng phòng gỡ khỏi danh mục trọng tâm. Cách hiểu về trọng tâm của anh/chị đang lệch với phòng; cần trao đổi trực tiếp với Trưởng phòng.")


def _render_staff_week(st, u, core, get_conn, ws, plan, items, focus_rows, logger=None):
    uid = int(_uget(u, "id"))
    status = str(plan.get("workflow_status") or "NHAP")
    regular = [x for x in items if not int(x.get("is_emergent") or 0) and x.get("status") != "CANCELLED"]
    _drift_warning(st, get_conn, uid, ws)
    counts, hours, total_hours = _summary(st, items)
    if total_hours and hours[4] / total_hours > .20:
        st.warning("⚠ Giờ dự kiến Q4 vượt 20% tổng giờ. Hãy rà soát xem có việc nào thực chất thuộc danh mục trọng tâm không. Đây là cảnh báo mềm, không chặn nộp kế hoạch.")

    if plan.get("return_note") and status == "TRA_LAI":
        st.error(f"↩ Trưởng phòng trả lại: {plan.get('return_note')}")

    for x in sorted([z for z in items if z.get("status") != "CANCELLED"], key=lambda z: (str(z.get("work_date")), PRIORITY_ORDER.index(int(z.get("priority_quadrant") or 4)) if int(z.get("priority_quadrant") or 4) in PRIORITY_ORDER else 9, int(z.get("id") or 0))):
        _item_card(st, x)
        if status in ("NHAP", "TRA_LAI") and not int(x.get("is_emergent") or 0):
            if st.button("🗑 Bỏ khỏi bản nháp", key=f"draft_del_{x['id']}"):
                with get_conn() as c:
                    c.execute("UPDATE weekly_plan_items SET status='CANCELLED',updated_at=? WHERE id=? AND user_id=?", (_now(), int(x["id"]), uid))
                    c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'DRAFT_REMOVE','Bỏ khỏi bản nháp',?)", (int(x["id"]), uid, _now()))
                st.rerun()

    start, end = _planning_window(ws)
    in_window = start <= datetime.now() <= end
    if status in ("NHAP", "TRA_LAI"):
        st.caption(f"Khung lập kế hoạch chuẩn: {start:%d/%m %H:%M} → {end:%d/%m %H:%M}. Hiện {'đang trong' if in_window else 'ngoài'} khung chuẩn.")
        if len(regular) < 7:
            _add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False, logger=logger)
            _carry_forward_ui(st, u, core, get_conn, ws, focus_rows, len(regular), logger)
        else:
            st.info("Đã đủ 7 công việc kế hoạch. Công việc phát sinh trong tuần không bị giới hạn 7 việc.")
        q2_focus_count = _q2_focus_count(items)
        can_submit = len(regular) <= 7 and q2_focus_count >= 3 and len(regular) > 0
        if q2_focus_count < 3:
            st.error(f"Chưa thể nộp kế hoạch: cần tối thiểu 3 mục công việc trọng tâm Q2 khác nhau; hiện có {q2_focus_count} mục.")
        if st.button("📤 Nộp kế hoạch", type="primary", use_container_width=True, disabled=not can_submit, key=f"submit_{plan['id']}") and can_submit:
            ts = _now()
            with get_conn() as c:
                c.execute("UPDATE weekly_plans SET workflow_status='DA_NOP',submitted_at=?,return_note=NULL,updated_at=? WHERE id=?", (ts, ts, int(plan["id"])))
                c.execute("UPDATE weekly_plan_items SET approval_status='PENDING' WHERE plan_id=? AND status<>'CANCELLED'", (int(plan["id"]),))
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'PLAN_SUBMIT',?,?)", (uid, f"week={ws.isoformat()}", ts))
            if logger:
                logger.info("WEEKLY_PLAN_SUBMIT user=%s plan=%s q2_focus_categories=%s q2_items=%s", uid, plan["id"], q2_focus_count, counts[2])
            st.toast("Đã nộp kế hoạch cho Trưởng phòng.", icon="✅"); st.rerun()
    elif status == "DA_NOP":
        st.info("Kế hoạch đã nộp và đang khóa chỉnh sửa trong khi chờ duyệt.")
        if st.button("↩ Thu hồi kế hoạch", use_container_width=True, key=f"withdraw_{plan['id']}"):
            ts = _now()
            with get_conn() as c:
                c.execute("UPDATE weekly_plans SET workflow_status='NHAP',updated_at=? WHERE id=?", (ts, int(plan["id"])))
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'PLAN_WITHDRAW',?,?)", (uid, f"week={ws.isoformat()}", ts))
            st.rerun()
    elif status == "DA_DUYET":
        st.success("Kế hoạch đã duyệt. Cán bộ chỉ cập nhật trạng thái và giờ thực tế; việc mới trong tuần ghi tại mục Phát sinh.")
        for x in [z for z in items if z.get("status") != "CANCELLED"]:
            with st.expander(f"Cập nhật · {x.get('title')}", expanded=False):
                stat_opts = ["PLANNED", "IN_PROGRESS", "DONE"]
                cur = str(x.get("status") or "PLANNED")
                stat = st.selectbox("Trạng thái", stat_opts, index=stat_opts.index(cur) if cur in stat_opts else 0, format_func=lambda s: core.STAT.get(s, s), key=f"exec_status_{x['id']}")
                actual = st.number_input("Giờ thực tế", min_value=0.0, max_value=100.0, step=0.25, value=float(x.get("actual_hours") or 0), key=f"exec_hours_{x['id']}")
                if st.button("Lưu cập nhật", key=f"exec_save_{x['id']}", type="primary"):
                    with get_conn() as c:
                        c.execute("UPDATE weekly_plan_items SET status=?,actual_hours=?,updated_at=? WHERE id=? AND user_id=?", (stat, float(actual), _now(), int(x["id"]), uid))
                        c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'EXEC_UPDATE',?,?)", (int(x["id"]), uid, json.dumps({"status": stat, "actual_hours": actual}, ensure_ascii=False), _now()))
                    st.rerun()
        now = datetime.now()
        close_window = now.weekday() == 4 and time(14, 0) <= now.time() <= time(17, 0)
        with st.expander("✅ Chốt tuần · tự đánh giá", expanded=False):
            score = st.slider("Tự chấm điểm chất lượng", 1, 10, 8, key=f"self_score_{plan['id']}")
            strengths = st.text_area("Mặt được", key=f"self_strength_{plan['id']}")
            issues = st.text_area("Tồn tại", key=f"self_issues_{plan['id']}")
            causes = st.text_area("Nguyên nhân", key=f"self_causes_{plan['id']}")
            proposals = st.text_area("Đề xuất", key=f"self_prop_{plan['id']}")
            st.caption("Khung chuẩn chốt tuần: Thứ 6 14:00–17:00." + (" Đang trong khung." if close_window else " Hiện ngoài khung; nút vẫn hiển thị để xử lý ngoại lệ có kiểm soát."))
            if st.button("Chốt tuần", key=f"close_{plan['id']}", type="primary", use_container_width=True):
                ts = _now()
                with get_conn() as c:
                    c.execute("""UPDATE weekly_plans SET workflow_status='DA_CHOT',self_score=?,self_strengths=?,self_issues=?,self_causes=?,self_proposals=?,closed_at=?,classification_locked=1,updated_at=? WHERE id=?""", (score, strengths, issues, causes, proposals, ts, ts, int(plan["id"])))
                    c.execute("UPDATE weekly_plan_items SET classification_locked=1 WHERE plan_id=?", (int(plan["id"]),))
                    c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'PLAN_CLOSE',?,?)", (uid, f"week={ws.isoformat()}", ts))
                st.rerun()
    elif status == "DA_CHOT":
        st.info("Kế hoạch đã chốt. Phân loại bị khóa; chờ Trưởng phòng nhận xét và đánh giá.")
    elif status == "DA_DANH_GIA":
        st.success(f"Tuần đã đánh giá · Điểm Trưởng phòng: {plan.get('leader_score') if plan.get('leader_score') is not None else '—'}")
        if plan.get("leader_comment"):
            st.write(plan.get("leader_comment"))


def _room_dashboard(st, u, core, get_conn, ws, logger=None):
    leader_uid = int(_uget(u, "id")); admin = _is_admin(u)
    with get_conn() as c:
        plans = [dict(r) for r in c.execute(
            """SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id
               WHERE p.week_start=? AND u.active=1 ORDER BY u.full_name""", (ws.isoformat(),)
        ).fetchall()]
        plans = [p for p in plans if _direct_scope_ok(c, leader_uid, p["user_id"], admin)]
        cats = _focus_categories(c, _scope_key(c, leader_uid), ws.year, False)
    st.subheader("👥 Kế hoạch phòng")
    if not plans:
        st.info("Chưa có kế hoạch của cán bộ trong tuần này.")
    total_items = emergent = 0
    for p in plans:
        with get_conn() as c:
            items = [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id", (int(p["id"]),)).fetchall()]
        total_items += len(items); emergent += sum(int(x.get("is_emergent") or 0) for x in items)
        with st.expander(f"{p.get('full_name')} · {PLAN_STATUS.get(p.get('workflow_status'), p.get('workflow_status'))} · {len(items)} việc", expanded=False):
            _summary(st, items)
            for x in items:
                _item_card(st, x)
            can_adjust = str(p.get("workflow_status")) in ("DA_NOP", "DA_DUYET") or (str(p.get("workflow_status")) == "DA_CHOT" and not int(p.get("classification_locked") or 0))
            if can_adjust:
                st.caption("Trưởng phòng có thể điều chỉnh phân loại trong suốt tuần; mọi thay đổi đều ghi nhật ký và thông báo cho cán bộ.")
                for x in items:
                    _manager_classification_editor(st, u, core, get_conn, p, x, cats, logger)
            if str(p.get("workflow_status")) == "DA_CHOT":
                if admin and int(p.get("classification_locked") or 0):
                    reason = st.text_input("Lý do mở khóa phân loại", key=f"unlock_reason_{p['id']}")
                    if st.button("🔓 Admin mở khóa phân loại", key=f"unlock_{p['id']}", disabled=not reason.strip()):
                        ts = _now()
                        with get_conn() as c:
                            c.execute("UPDATE weekly_plans SET classification_locked=0,unlocked_at=?,unlocked_by=?,unlock_reason=?,updated_at=? WHERE id=?", (ts, leader_uid, reason.strip(), ts, int(p["id"])))
                            c.execute("UPDATE weekly_plan_items SET classification_locked=0 WHERE plan_id=?", (int(p["id"]),))
                            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'CLASSIFICATION_UNLOCK',?,?)", (leader_uid, reason.strip(), ts))
                        st.rerun()
                score = st.slider("Điểm chất lượng Trưởng phòng", 1, 10, int(p.get("leader_score") or 8), key=f"leader_score_{p['id']}")
                comment = st.text_area("Nhận xét Trưởng phòng", value=str(p.get("leader_comment") or ""), key=f"leader_comment_{p['id']}")
                if st.button("⭐ Xác nhận kết quả tuần", key=f"eval_{p['id']}", type="primary", use_container_width=True):
                    ts = _now()
                    with get_conn() as c:
                        c.execute("UPDATE weekly_plans SET workflow_status='DA_DANH_GIA',leader_score=?,leader_comment=?,evaluated_at=?,evaluated_by=?,classification_locked=1,updated_at=? WHERE id=?", (score, comment, ts, leader_uid, ts, int(p["id"])))
                        c.execute("UPDATE weekly_plan_items SET classification_locked=1 WHERE plan_id=?", (int(p["id"]),))
                    st.rerun()
    pct = emergent / total_items * 100 if total_items else 0
    st.metric("Tỷ lệ công việc phát sinh / tổng công việc", f"{pct:.1f}%", f"{emergent}/{total_items}")
    # 8-week stale catalog reminder.
    cutoff = (date.today() - timedelta(weeks=8)).isoformat()
    with get_conn() as c:
        stale = []
        for cat in cats:
            hit = c.execute("SELECT 1 FROM weekly_plan_items WHERE focus_category_id=? AND work_date>=? LIMIT 1", (int(cat["id"]), cutoff)).fetchone()
            if not hit:
                stale.append(cat)
    if stale:
        st.warning("📌 Danh mục trọng tâm không có công việc trong 8 tuần: " + ", ".join(f"{x['code']} · {x['name']}" for x in stale) + ". Hãy xem lại danh mục hoặc việc triển khai trọng tâm.")
    with get_conn() as c:
        watch = [dict(r) for r in c.execute("""SELECT w.title,u.full_name,w.carryover_count FROM weekly_plan_items w JOIN users u ON u.id=w.user_id WHERE w.q2_watch_flag=1 AND w.status NOT IN ('DONE','CANCELLED') ORDER BY w.carryover_count DESC,w.id DESC LIMIT 50""").fetchall()]
    if watch:
        st.error("🚩 Q2 bị lùi quá 2 tuần liên tiếp: " + "; ".join(f"{x['full_name']} – {x['title']} ({x['carryover_count']} lần)" for x in watch))


def _manager_classification_editor(st, u, core, get_conn, plan, item, focus_rows, logger=None):
    uid = int(_uget(u, "id")); iid = int(item["id"])
    with st.expander(f"🎯 Điều chỉnh · {item.get('title')}", expanded=False):
        options = [None] + focus_rows
        current_focus = item.get("focus_category_id")
        idx = 0
        if current_focus:
            for i, x in enumerate(options):
                if x and int(x["id"]) == int(current_focus): idx = i; break
        focus = st.selectbox("Danh mục trọng tâm", options, index=idx, format_func=lambda x: "Không thuộc danh mục trọng tâm" if x is None else f"{x['code']} · {x['name']}", key=f"mgr_focus_{iid}")
        if focus:
            st.success("Kết quả: Q2 · Trọng tâm")
            due7 = risk = None
        else:
            current_q = int(item.get("priority_quadrant") or 4)
            q = st.selectbox("Phân loại khi không thuộc trọng tâm", [1, 3, 4], index=[1,3,4].index(current_q) if current_q in (1,3,4) else 2, format_func=lambda z: PRIORITY_SHORT[z], key=f"mgr_q_{iid}")
            due7 = q in (1, 3); risk = True if q == 1 else False if q == 3 else None
        reason = st.text_input("Căn cứ điều chỉnh", key=f"mgr_reason_{iid}")
        if st.button("Lưu phân loại", key=f"mgr_save_{iid}", type="primary", use_container_width=True):
            with get_conn() as c:
                if not _direct_scope_ok(c, uid, int(plan["user_id"]), _is_admin(u)):
                    st.error("Chỉ Trưởng phòng trực tiếp quản lý cán bộ mới được điều chỉnh."); return
                _set_classification(c, iid, uid, int(focus["id"]) if focus else None, due7, risk, reason=reason or "Trưởng phòng điều chỉnh", allow_locked=_is_admin(u) and not int(plan.get("classification_locked") or 0))
            st.toast("Đã cập nhật phân loại và ghi nhật ký.", icon="✅"); st.rerun()


def _inline_focus_create(st, u, get_conn, year, logger=None):
    uid = int(_uget(u, "id"))
    with get_conn() as c:
        leaders = [dict(r) for r in c.execute("SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name").fetchall()]
    leader_id = uid
    if _is_admin(u) and leaders:
        leader_id = int(st.selectbox("Phòng/Trưởng phòng áp dụng", leaders, format_func=lambda x: x["full_name"], key=f"inline_focus_leader_{year}")["id"])
    scope = f"LEADER:{leader_id}"
    with st.expander("＋ Bổ sung mục trọng tâm ngay tại màn hình duyệt", expanded=False):
        a, b = st.columns([1, 3])
        code = a.text_input("Mã *", key=f"inline_focus_code_{year}", placeholder="TT06")
        name = b.text_input("Tên ngắn gọn *", key=f"inline_focus_name_{year}")
        desc = st.text_area("Mô tả phạm vi (1–2 câu) *", key=f"inline_focus_desc_{year}")
        order = st.number_input("Thứ tự", min_value=1, value=6, step=1, key=f"inline_focus_order_{year}")
        if st.button("Thêm vào danh mục trọng tâm", key=f"inline_focus_save_{year}", type="primary"):
            if not code.strip() or not name.strip() or not desc.strip():
                st.error("Vui lòng nhập đủ mã, tên và mô tả phạm vi."); return
            ts = _now()
            try:
                with get_conn() as c:
                    c.execute("INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?,?,?)", (scope, int(year), code.strip().upper(), name.strip(), desc.strip(), int(order), uid, uid, ts, ts))
                st.toast("Đã bổ sung mục trọng tâm.", icon="✅"); st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_approvals(st, u, core, customer_core, customer_ui, get_conn, page_title=None, logger=None):
    _ensure_schema(core, get_conn, logger)
    if not _manager(u):
        st.error("Chỉ Lãnh đạo/Admin được phê duyệt."); return
    uid = int(_uget(u, "id")); admin = _is_admin(u)
    if page_title:
        page_title("Phê duyệt kế hoạch / dời hạn", "Duyệt kế hoạch tuần, điều chỉnh trọng tâm và xử lý đề nghị dời hạn")
    else:
        st.title("✅ Phê duyệt kế hoạch / dời hạn")

    # Customer Work approvals retained.
    customer_core.ensure_schema(get_conn, logger)
    with get_conn() as c:
        cases = [dict(r) for r in c.execute("""SELECT w.*,cu.customer_name,u.full_name AS owner_name,s.name AS stage_name FROM customer_work_cases w JOIN customers cu ON cu.id=w.customer_id JOIN users u ON u.id=w.owner_user_id LEFT JOIN work_stage_catalog s ON s.id=w.current_stage_id WHERE w.plan_approval_status='PENDING' ORDER BY w.plan_requested_at,w.id""").fetchall()]
        moves = [dict(r) for r in c.execute("""SELECT r.*,w.title,cu.customer_name,u.full_name AS requester_name FROM case_reschedule_requests r JOIN customer_work_cases w ON w.id=r.case_id JOIN customers cu ON cu.id=w.customer_id JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
    st.subheader("Công việc khách hàng mới")
    if not cases: st.caption("Không có công việc khách hàng chờ phê duyệt.")
    for x in cases:
        if not _direct_scope_ok(_get_conn_obj(get_conn), uid, int(x.get("owner_user_id") or 0), admin):
            continue
        with st.container(border=True):
            st.markdown(f"**{x.get('customer_name')} · {x.get('title')}**")
            st.caption(f"{x.get('owner_name')} · {x.get('stage_name') or '—'}")
            note = st.text_input("Ý kiến", key=f"policy_case_note_{x['id']}")
            a, b = st.columns(2)
            if a.button("✓ Phê duyệt", key=f"policy_case_yes_{x['id']}", type="primary", use_container_width=True):
                customer_core.approve_case_plan(get_conn, x["id"], uid, True, note, logger); st.rerun()
            if b.button("✕ Từ chối", key=f"policy_case_no_{x['id']}", use_container_width=True):
                customer_core.approve_case_plan(get_conn, x["id"], uid, False, note, logger); st.rerun()

    st.subheader("Kế hoạch tuần đã nộp")
    with get_conn() as c:
        plans = [dict(r) for r in c.execute("""SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.workflow_status='DA_NOP' ORDER BY p.week_start,u.full_name""").fetchall()]
        plans = [p for p in plans if _direct_scope_ok(c, uid, int(p["user_id"]), admin)]
    if not plans: st.caption("Không có kế hoạch tuần chờ duyệt.")
    for p in plans:
        ws = date.fromisoformat(str(p["week_start"])[:10])
        with get_conn() as c:
            items = [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id", (int(p["id"]),)).fetchall()]
            scope = _scope_key(c, int(p["user_id"]))
            cats = _focus_categories(c, scope, ws.year, False)
        with st.expander(f"{p.get('full_name')} · tuần {ws:%d/%m/%Y} · {len(items)} việc", expanded=True):
            _summary(st, items)
            _inline_focus_create(st, u, get_conn, ws.year, logger)
            # Reload after possible inline create on next rerun.
            for x in items:
                _item_card(st, x)
                _manager_classification_editor(st, u, core, get_conn, p, x, cats, logger)
            decision = st.text_area("Ý kiến duyệt / lý do trả lại", key=f"policy_plan_note_{p['id']}")
            a, b = st.columns(2)
            if a.button("✓ Phê duyệt kế hoạch", key=f"policy_plan_yes_{p['id']}", type="primary", use_container_width=True):
                ts = _now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET',approved_at=?,approved_by=?,return_note=NULL,updated_at=? WHERE id=?", (ts, uid, ts, int(p["id"])))
                    c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE plan_id=? AND status<>'CANCELLED'", (uid, ts, int(p["id"])))
                    _notify(c, int(p["user_id"]), "✅ Kế hoạch tuần đã được duyệt", f"Tuần {ws:%d/%m/%Y}. {decision or ''}".strip())
                st.rerun()
            if b.button("↩ Trả lại điều chỉnh", key=f"policy_plan_back_{p['id']}", use_container_width=True, disabled=not decision.strip()):
                ts = _now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='TRA_LAI',returned_at=?,returned_by=?,return_note=?,updated_at=? WHERE id=?", (ts, uid, decision.strip(), ts, int(p["id"])))
                    _notify(c, int(p["user_id"]), "↩ Kế hoạch tuần được trả lại", decision.strip())
                st.rerun()

    st.subheader("Đề nghị dời kế hoạch")
    with get_conn() as c:
        wmoves = [dict(r) for r in c.execute("""SELECT r.*,w.title,w.user_id,u.full_name AS requester_name FROM weekly_plan_reschedule_requests r JOIN weekly_plan_items w ON w.id=r.item_id JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
    if not moves and not wmoves: st.caption("Không có đề nghị dời hạn.")
    for r in moves:
        with st.container(border=True):
            st.markdown(f"**KH: {r.get('customer_name')} · {r.get('title')}**")
            st.caption(f"{r.get('requester_name')} · {r.get('old_due_at')} → {r.get('proposed_due_at')}")
            note = st.text_input("Ý kiến", key=f"policy_cr_note_{r['id']}")
            a,b = st.columns(2)
            if a.button("✓ Duyệt", key=f"policy_cr_yes_{r['id']}", type="primary", use_container_width=True):
                customer_core.decide_reschedule(get_conn, r["id"], uid, True, note, logger); st.rerun()
            if b.button("✕ Từ chối", key=f"policy_cr_no_{r['id']}", use_container_width=True):
                customer_core.decide_reschedule(get_conn, r["id"], uid, False, note, logger); st.rerun()
    for r in wmoves:
        with get_conn() as c:
            if not _direct_scope_ok(c, uid, int(r.get("user_id") or r.get("requested_by") or 0), admin): continue
        with st.container(border=True):
            st.markdown(f"**{r.get('requester_name')} · {r.get('title')}**")
            st.caption(f"{r.get('old_work_date')} → {r.get('proposed_work_date')}")
            note = st.text_input("Ý kiến", key=f"policy_wr_note_{r['id']}")
            a,b = st.columns(2)
            if a.button("✓ Duyệt", key=f"policy_wr_yes_{r['id']}", type="primary", use_container_width=True):
                ts = _now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plan_reschedule_requests SET status='APPROVED',decided_by=?,decided_at=?,decision_note=? WHERE id=?", (uid, ts, note, int(r["id"])))
                    c.execute("UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?", (r["proposed_work_date"], ts, int(r["item_id"])))
                st.rerun()
            if b.button("✕ Từ chối", key=f"policy_wr_no_{r['id']}", use_container_width=True):
                with get_conn() as c:
                    c.execute("UPDATE weekly_plan_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,decision_note=? WHERE id=?", (uid, _now(), note, int(r["id"])))
                st.rerun()


def _get_conn_obj(get_conn):
    """Short-lived connection for scope checks; caller does not keep it."""
    # Used only in a single expression; returning the connection keeps sqlite Row access.
    return get_conn()


def _render_catalog(st, u, core, customer_core, customer_ui, get_conn, page_title=None, logger=None):
    _ensure_schema(core, get_conn, logger)
    customer_core.ensure_schema(get_conn, logger)
    if not _manager(u):
        st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục."); return
    uid = int(_uget(u, "id"))
    if page_title: page_title("Danh mục quy trình", "Mục công việc/SLA và danh mục công việc trọng tâm Q2")
    else: st.title("⚙️ Danh mục quy trình")
    view = _cmd_nav(st, "policy_catalog_view", [("stage", "Mục công việc / SLA"), ("focus", "Danh mục công việc trọng tâm Q2")], "stage")
    if view == "stage":
        if st.session_state.pop("_cw_stage_reset", False):
            st.session_state["cw_stage_edit"] = None; st.session_state.pop("_cw_stage_loaded", None)
        with get_conn() as c: stages = customer_core.active_stages(c, include_inactive=True)
        customer_ui._html_table(st, ["Thứ tự","Mục công việc","SLA (giờ)","Bước kết thúc quy trình","Trạng thái"], [[s["sort_order"],s["name"],f"{float(s['sla_hours']):.1f}","Có" if s["is_completion"] else "Không","Đang dùng" if s["active"] else "Ngưng"] for s in stages])
        opts=[None]+stages
        edit=st.selectbox("Chọn mục công việc để sửa",opts,format_func=lambda x:"＋ Tạo mới" if x is None else x["name"],key="cw_stage_edit")
        catalog_state._sync(st.session_state,"_cw_stage_loaded",{"name":"cw_stage_name_field","order":"cw_stage_order_field","sla":"cw_stage_sla_field","done":"cw_stage_done_field","active":"cw_stage_active_field"},edit,catalog_state._stage_defaults(edit,len(stages)))
        with st.form("cw_stage_form"):
            name=st.text_input("Tên mục công việc",key="cw_stage_name_field");order=st.number_input("Thứ tự",min_value=1,step=1,key="cw_stage_order_field");sla=st.number_input("SLA cảnh báo (giờ)",min_value=0.0,step=1.0,key="cw_stage_sla_field");done=st.checkbox("Bước kết thúc quy trình",key="cw_stage_done_field");active=st.checkbox("Đang sử dụng",key="cw_stage_active_field");save=st.form_submit_button("Lưu danh mục",type="primary")
        if save:
            customer_core.save_stage_catalog(get_conn,uid,edit["id"] if edit else None,name,order,sla,done,active,logger);st.session_state["_cw_stage_reset"]=True;st.rerun()
        if edit and st.button("Xóa/Ngưng sử dụng mục này",key="policy_stage_delete"):
            customer_core.delete_stage_catalog(get_conn,uid,edit["id"],logger);st.session_state["_cw_stage_reset"]=True;st.rerun()
        return

    year = st.number_input("Năm áp dụng", min_value=2025, max_value=2100, value=date.today().year, step=1, key="focus_year")
    with get_conn() as c:
        leaders = [dict(r) for r in c.execute("SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name").fetchall()]
    leader_id = uid
    if _is_admin(u) and leaders:
        leader_id = int(st.selectbox("Phòng/Trưởng phòng", leaders, format_func=lambda x:x["full_name"], key="focus_leader")["id"])
    scope=f"LEADER:{leader_id}"
    with get_conn() as c: cats=_focus_categories(c,scope,int(year),True)
    active_count=sum(int(x.get("active") or 0) for x in cats)
    if active_count < 5: st.warning(f"Khuyến nghị 5–8 mục trọng tâm; hiện có {active_count} mục đang áp dụng.")
    elif active_count > 10: st.warning(f"Danh mục hiện có {active_count} mục; trên 10 mục dễ làm dữ liệu phân tán.")
    else: st.success(f"Danh mục hiện có {active_count} mục đang áp dụng.")
    customer_ui._html_table(st,["Mã","Tên danh mục","Phạm vi","Thứ tự","Năm","Trạng thái"],[[x["code"],x["name"],x.get("description") or "—",x["sort_order"],x["apply_year"],"Đang dùng" if x["active"] else "Ngưng"] for x in cats])
    if st.button("📋 Sao chép danh mục năm trước", key=f"focus_copy_{year}"):
        ts=_now(); copied=0
        with get_conn() as c:
            prev=_focus_categories(c,scope,int(year)-1,True)
            for x in prev:
                try:
                    c.execute("INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(scope,int(year),x["code"],x["name"],x.get("description"),x["sort_order"],x["active"],uid,uid,ts,ts));copied+=1
                except Exception: pass
        st.toast(f"Đã sao chép {copied} mục từ năm {int(year)-1}.",icon="✅");st.rerun()
    opts=[None]+cats;edit=st.selectbox("Chọn danh mục để sửa",opts,format_func=lambda x:"＋ Tạo mới" if x is None else f"{x['code']} · {x['name']}",key="focus_edit")
    marker="NEW" if edit is None else f"ID:{edit['id']}"
    if st.session_state.get("_focus_loaded")!=marker:
        st.session_state["_focus_loaded"]=marker
        st.session_state["focus_code_field"]=str(edit.get("code") or "") if edit else ""
        st.session_state["focus_name_field"]=str(edit.get("name") or "") if edit else ""
        st.session_state["focus_desc_field"]=str(edit.get("description") or "") if edit else ""
        st.session_state["focus_order_field"]=int(edit.get("sort_order") or 1) if edit else len(cats)+1
        st.session_state["focus_active_field"]=bool(edit.get("active")) if edit else True
    with st.form("focus_form"):
        a,b=st.columns([1,3]);code=a.text_input("Mã *",key="focus_code_field",placeholder="TT01");name=b.text_input("Tên ngắn gọn *",key="focus_name_field");desc=st.text_area("Mô tả phạm vi (1–2 câu) *",key="focus_desc_field");order=st.number_input("Thứ tự hiển thị",min_value=1,step=1,key="focus_order_field");active=st.checkbox("Đang áp dụng",key="focus_active_field");save=st.form_submit_button("Lưu danh mục",type="primary")
    if save:
        if not code.strip() or not name.strip() or not desc.strip(): st.error("Vui lòng nhập mã, tên và mô tả phạm vi.")
        else:
            ts=_now()
            try:
                with get_conn() as c:
                    if edit:
                        c.execute("UPDATE weekly_focus_categories SET code=?,name=?,description=?,sort_order=?,active=?,updated_by=?,updated_at=? WHERE id=?",(code.strip().upper(),name.strip(),desc.strip(),int(order),int(active),uid,ts,int(edit["id"])))
                    else:
                        c.execute("INSERT INTO weekly_focus_categories(department_key,apply_year,code,name,description,sort_order,active,created_by,updated_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(scope,int(year),code.strip().upper(),name.strip(),desc.strip(),int(order),int(active),uid,uid,ts,ts))
                st.session_state.pop("_focus_loaded",None);st.toast("Đã lưu danh mục trọng tâm.",icon="✅");st.rerun()
            except Exception as exc: st.error(str(exc))
    if edit and st.button("Xóa/Ngừng áp dụng",key="focus_delete"):
        with get_conn() as c:
            used=c.execute("SELECT 1 FROM weekly_plan_items WHERE focus_category_id=? LIMIT 1",(int(edit["id"]),)).fetchone()
            if used:
                c.execute("UPDATE weekly_focus_categories SET active=0,updated_by=?,updated_at=? WHERE id=?",(uid,_now(),int(edit["id"])));st.toast("Mục đã có công việc gắn vào nên chỉ được chuyển sang Ngừng áp dụng.")
            else:
                c.execute("DELETE FROM weekly_focus_categories WHERE id=?",(int(edit["id"]),));st.toast("Đã xóa mục chưa phát sinh lịch sử.")
        st.session_state.pop("_focus_loaded",None);st.rerun()


def _render_weekly(st, u, core, get_conn, page_title=None, logger=None):
    _ensure_schema(core, get_conn, logger)
    uid=int(_uget(u,"id"))
    if page_title: page_title("Kế hoạch tuần", "Trọng tâm trước · phân loại tự động Q2/Q1/Q3/Q4 · quản trị theo vòng đời tuần")
    else: st.title("📅 Kế hoạch tuần")
    base=_default_week(core)
    if "policy_week_offset" not in st.session_state: st.session_state["policy_week_offset"]=0
    a,b,c,d=st.columns([1,1,1,4])
    if a.button("← Tuần trước",key="policy_prev",use_container_width=True): st.session_state["policy_week_offset"]-=1;st.rerun()
    if b.button("Tuần mục tiêu",key="policy_now",use_container_width=True): st.session_state["policy_week_offset"]=0;st.rerun()
    if c.button("Tuần sau →",key="policy_next",use_container_width=True): st.session_state["policy_week_offset"]+=1;st.rerun()
    ws=base+timedelta(days=7*int(st.session_state["policy_week_offset"]));d.markdown(f"**{ws:%d/%m} – {(ws+timedelta(days=6)):%d/%m/%Y}**")
    with get_conn() as conn:
        plan=_plan_row(conn,uid,ws,core);items=core.load_items(conn,uid,ws);scope=_scope_key(conn,uid);focus=_focus_categories(conn,scope,ws.year,False)
    _status_badge(st,str(plan.get("workflow_status") or "NHAP"))
    options=[("plan","Kế hoạch tuần"),("today","Hôm nay"),("emergent","Phát sinh")]
    if _manager(u): options.append(("room","Kế hoạch phòng"))
    view=_cmd_nav(st,"policy_week_view",options,"room" if _manager(u) else "plan")
    if view=="plan": _render_staff_week(st,u,core,get_conn,ws,plan,items,focus,logger)
    elif view=="emergent":
        if str(plan.get("workflow_status"))!="DA_DUYET": st.info("Chỉ bổ sung công việc phát sinh sau khi kế hoạch tuần đã được duyệt.")
        else:
            _add_item_form(st,u,core,get_conn,ws,focus,emergent=True,logger=logger)
            ps=[x for x in items if int(x.get("is_emergent") or 0) and x.get("status")!="CANCELLED"]
            st.metric("Công việc phát sinh",len(ps))
            for x in ps:_item_card(st,x)
    elif view=="today":
        today=date.today().isoformat();today_items=[x for x in items if str(x.get("work_date") or "")[:10]==today and x.get("status")!="CANCELLED"]
        st.subheader(f"☀️ Hôm nay · {date.today():%d/%m/%Y}")
        if not today_items: st.info("Hôm nay chưa có công việc trong kế hoạch tuần.")
        for x in sorted(today_items,key=lambda z: PRIORITY_ORDER.index(int(z.get("priority_quadrant") or 4)) if int(z.get("priority_quadrant") or 4) in PRIORITY_ORDER else 9):_item_card(st,x)
    else:_room_dashboard(st,u,core,get_conn,ws,logger)


def install(ns, weekly_core, weekly_ui, customer_core, customer_ui, logger=None):
    if getattr(weekly_ui,"_WEEKLY_PRIORITY_POLICY_VERSION",None)==VERSION:
        return
    app_logger=logger or ns.get("LOGGER")
    original_ensure=weekly_core.ensure_schema
    def ensure_schema(get_conn,logger_arg=None):
        # Temporarily restore base ensure inside _ensure_schema to avoid recursion.
        weekly_core.ensure_schema=original_ensure
        try:_ensure_schema(weekly_core,get_conn,logger_arg or app_logger)
        finally:weekly_core.ensure_schema=ensure_schema
    weekly_core.ensure_schema=ensure_schema

    # New terminology everywhere the current heat/card modules ask for a label.
    def quadrant_label(q):
        try:q=int(q or 4)
        except Exception:q=4
        return PRIORITY_SHORT.get(q,PRIORITY_SHORT[4])
    customer_core.quadrant_label=quadrant_label
    priority_v2._priority_label=quadrant_label
    weekly_ui._PRIORITY={q:PRIORITY[q] for q in (1,2,3,4)}

    def render_weekly(st=None,u=None,get_conn=None,page_title=None,logger=None,**kwargs):
        return _render_weekly(st or ns["st"],u,get_conn or ns["get_conn"],page_title,logger or app_logger)
    # Fix closure: pass core explicitly via a tiny inner call.
    def render_weekly(st=None,u=None,get_conn=None,page_title=None,logger=None,**kwargs):
        return _render_weekly(st or ns["st"],u,weekly_core,get_conn or ns["get_conn"],page_title,logger or app_logger)
    weekly_ui.render_page=render_weekly

    def render_catalog_page(st=None,u=None,get_conn=None,page_title=None,logger=None,**kwargs):
        return _render_catalog(st or ns["st"],u,weekly_core,customer_core,customer_ui,get_conn or ns["get_conn"],page_title,logger or app_logger)
    customer_ui.render_catalog_page=render_catalog_page

    def render_approvals_page(st=None,u=None,get_conn=None,page_title=None,logger=None,**kwargs):
        return _render_approvals(st or ns["st"],u,weekly_core,customer_core,customer_ui,get_conn or ns["get_conn"],page_title,logger or app_logger)
    customer_ui.render_approvals_page=render_approvals_page

    # The live dispatcher resolves these module functions at request time, but write
    # through the app globals as well so no earlier captured closure can win.
    previous_dashboard=ns.get("dashboard_page")
    st=ns["st"]
    def dashboard_page(u):
        page=st.session_state.get("main_page")
        kwargs=dict(st=st,u=u,get_conn=ns["get_conn"],page_title=ns.get("page_title"),logger=app_logger)
        if page=="weekly_plan": return weekly_ui.render_page(**kwargs)
        if page=="work_catalogs": return customer_ui.render_catalog_page(**kwargs)
        if page=="work_approvals": return customer_ui.render_approvals_page(**kwargs)
        return previous_dashboard(u)
    if callable(previous_dashboard):
        ns["dashboard_page"]=dashboard_page
        app_fn=ns.get("app")
        if callable(app_fn):app_fn.__globals__["dashboard_page"]=dashboard_page

    weekly_ui._WEEKLY_PRIORITY_POLICY_VERSION=VERSION
    if app_logger:app_logger.info("WEEKLY_PRIORITY_POLICY_INSTALLED version=%s q2_first=1 lifecycle=1",VERSION)
