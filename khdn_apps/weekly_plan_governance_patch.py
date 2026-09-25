"""Approval governance for Weekly Plan.

Staff-created plans and reschedule requests are routed to Leader/Admin approval.
Leader/Admin actions are applied immediately and still audited.
"""
from __future__ import annotations

import json
from datetime import date


def install(core, logger=None):
    original_ensure = core.ensure_schema
    original_save = core.save_items
    original_move = core.move_item
    original_copy = core.copy_prev
    original_add_task = core.add_task
    original_card = core.card

    def _cols(c, table):
        return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}

    def _add(c, table, name, ddl):
        if name not in _cols(c, table):
            c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def ensure_schema(get_conn, logger_arg=None):
        original_ensure(get_conn, logger_arg or logger)
        with get_conn() as c:
            _add(c, "weekly_plan_items", "approval_status", "TEXT NOT NULL DEFAULT 'APPROVED'")
            _add(c, "weekly_plan_items", "approved_by_user_id", "INTEGER")
            _add(c, "weekly_plan_items", "approved_at", "TEXT")
            _add(c, "weekly_plan_items", "rejected_by_user_id", "INTEGER")
            _add(c, "weekly_plan_items", "rejected_at", "TEXT")
            _add(c, "weekly_plan_items", "approval_note", "TEXT")
            c.execute('''CREATE TABLE IF NOT EXISTS weekly_plan_reschedule_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                old_work_date TEXT NOT NULL,
                proposed_work_date TEXT NOT NULL,
                reason TEXT,
                requested_by INTEGER NOT NULL,
                requested_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                decided_by INTEGER,
                decided_at TEXT,
                decision_note TEXT,
                FOREIGN KEY(item_id) REFERENCES weekly_plan_items(id) ON DELETE CASCADE,
                FOREIGN KEY(requested_by) REFERENCES users(id),
                FOREIGN KEY(decided_by) REFERENCES users(id)
            )''')
            c.execute("CREATE INDEX IF NOT EXISTS idx_wp_approval ON weekly_plan_items(approval_status,work_date)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_wp_resched_approval ON weekly_plan_reschedule_requests(status,requested_at)")
        if logger_arg or logger:
            (logger_arg or logger).info("WEEKLY_PLAN_GOVERNANCE_SCHEMA_READY")

    def _manager(c, uid):
        r=c.execute("SELECT role,is_admin FROM users WHERE id=?",(uid,)).fetchone()
        return bool(r and (r[0]=="Lãnh đạo phòng" or int(r[1] or 0)==1))

    def _mark_new(get_conn, uid, min_id):
        with get_conn() as c:
            if _manager(c, uid):
                ts=core.now()
                c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=COALESCE(approved_at,?) WHERE user_id=? AND id>?",(uid,ts,uid,min_id))
                return "APPROVED"
            c.execute("UPDATE weekly_plan_items SET approval_status='PENDING',approved_by_user_id=NULL,approved_at=NULL,rejected_by_user_id=NULL,rejected_at=NULL,approval_note=NULL WHERE user_id=? AND id>?",(uid,min_id))
            return "PENDING"

    def _max_id(get_conn):
        with get_conn() as c:
            return int(c.execute("SELECT COALESCE(MAX(id),0) FROM weekly_plan_items").fetchone()[0])

    def save_items(get_conn, uid, ws, items, logger_arg=None):
        ensure_schema(get_conn, logger_arg)
        m=_max_id(get_conn)
        n,e=original_save(get_conn,uid,ws,items,logger_arg or logger)
        if n:
            state=_mark_new(get_conn,uid,m)
            if logger_arg or logger: (logger_arg or logger).info("WEEKLY_PLAN_APPROVAL_NEW user=%s count=%s state=%s",uid,n,state)
        return n,e

    def copy_prev(get_conn, uid, ws, logger_arg=None):
        ensure_schema(get_conn, logger_arg)
        m=_max_id(get_conn)
        n=original_copy(get_conn,uid,ws,logger_arg or logger)
        if n: _mark_new(get_conn,uid,m)
        return n

    def add_task(get_conn, uid, ws, task, target_date, logger_arg=None):
        ensure_schema(get_conn, logger_arg)
        m=_max_id(get_conn)
        ok=original_add_task(get_conn,uid,ws,task,target_date,logger_arg or logger)
        if ok: _mark_new(get_conn,uid,m)
        return ok

    def move_item(get_conn, iid, uid, new_date, logger_arg=None, reason=None):
        ensure_schema(get_conn, logger_arg)
        with get_conn() as c:
            row=c.execute("SELECT work_date FROM weekly_plan_items WHERE id=?",(iid,)).fetchone()
            if not row: return "NOT_FOUND"
            if _manager(c,uid):
                original_move(get_conn,iid,uid,new_date,logger_arg or logger)
                return "MOVED"
            pending=c.execute("SELECT 1 FROM weekly_plan_reschedule_requests WHERE item_id=? AND status='PENDING'",(iid,)).fetchone()
            if pending: return "ALREADY_PENDING"
            ts=core.now()
            c.execute("INSERT INTO weekly_plan_reschedule_requests(item_id,old_work_date,proposed_work_date,reason,requested_by,requested_at,status) VALUES(?,?,?,?,?,?,'PENDING')",(iid,str(row[0])[:10],new_date.isoformat(),reason or "Dời kế hoạch",uid,ts))
            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_REQUEST',?,?)",(iid,uid,json.dumps({"from":str(row[0])[:10],"to":new_date.isoformat(),"reason":reason},ensure_ascii=False),ts))
        if logger_arg or logger: (logger_arg or logger).info("WEEKLY_PLAN_RESCHEDULE_PENDING item=%s actor=%s date=%s",iid,uid,new_date)
        return "PENDING"

    def card(st,x,ws,get_conn,uid,logger_arg=None):
        approval=str(x.get("approval_status") or "APPROVED")
        if approval=="APPROVED":
            return original_card(st,x,ws,get_conn,uid,logger_arg or logger)
        # Keep pending/rejected entries visible but prevent execution before approval.
        import html
        import json as _json
        icon=core.ICONS.get(x.get("category"),"🗒️")
        st.markdown(f"**{icon} {html.escape(str(x.get('title') or ''))}**")
        meta=" · ".join(v for v in (str(x.get("start_time") or x.get("daypart") or ""),str(x.get("customer_text") or "")," · ".join(_json.loads(x.get("purposes_json") or "[]"))) if v)
        if meta: st.caption(meta)
        if approval=="PENDING":
            st.warning("⏳ Kế hoạch đang chờ Lãnh đạo/Admin phê duyệt.")
        else:
            st.error("✕ Kế hoạch đã bị từ chối." + (f" {x.get('approval_note')}" if x.get("approval_note") else ""))

    core.ensure_schema=ensure_schema
    core.save_items=save_items
    core.copy_prev=copy_prev
    core.add_task=add_task
    core.move_item=move_item
    core.card=card
    core.GOVERNANCE_VERSION="1.0.0"
    if logger: logger.info("WEEKLY_PLAN_GOVERNANCE_PATCH_INSTALLED version=1.0.0")
