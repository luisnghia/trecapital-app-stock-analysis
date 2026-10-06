"""Operational phase 12: weekly quick-add UX, customer-work cancellation, and attention cues.

Installed after phase 11. This overlay addresses five operational refinements:
- backup UI renders only on the dedicated System Admin Backup route;
- Weekly Plan keeps one weekday/date header row and adds per-day task counts;
- weekday quick-add preselects the clicked day and successful saves close/reset the form;
- Customer Work cancellation is a reason-required request/approval lifecycle;
- the leader waiting center pulses when actionable items are pending.

Runtime logs contain identifiers/counts only; cancellation reasons and customer/contact
values are never written to logs.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import html
from khdn_apps.legacy_fast_form import legacy_fast_form

from khdn_apps import backup_management_patch as backup
from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase4_patch as p4
from khdn_apps import planning_operational_phase11_patch as phase11
from khdn_apps import planning_week_board_focus_patch as weekfocus

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE12_VERSION"
_CANCEL_TABLE = "customer_work_cancel_requests"


def _table_exists(c, table):
    return bool(c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (str(table),)
    ).fetchone())


def _cols(c, table):
    if not _table_exists(c, table):
        return set()
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _install_backup_route_guard(logger=None):
    """Keep all backup sections exclusively inside System Admin -> Backup."""
    if getattr(backup, "_P12_BACKUP_ROUTE_GUARD", False):
        return
    original = backup.render_backup_admin

    def render_backup_admin(st, u, app_ns, logger_arg=None):
        if str(st.session_state.get("admin_scope") or "system") != "system":
            return None
        if str(st.session_state.get("admin_view") or "") != "backup":
            return None
        return original(st, u, app_ns, logger_arg or logger)

    backup.render_backup_admin = render_backup_admin
    backup._P12_BACKUP_ROUTE_GUARD = True
    if logger:
        logger.info("P12_BACKUP_ROUTE_GUARD_INSTALLED backup_view_only=1")


def _day_counts(ws, items):
    counts = []
    live = [dict(x) for x in (items or []) if str(x.get("status") or "") != "CANCELLED"]
    for idx in range(5):
        d = ws + timedelta(days=idx)
        counts.append(sum(1 for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()))
    return counts


def _weekday_strip(ws, items):
    today = date.today()
    counts = _day_counts(ws, items)
    cells = []
    for idx, label in enumerate(("THỨ 2", "THỨ 3", "THỨ 4", "THỨ 5", "THỨ 6")):
        d = ws + timedelta(days=idx)
        current = d == today
        cls = " p12-day-current" if current else ""
        badge = "<em>HÔM NAY</em>" if current else ""
        cells.append(
            f"<div class='p12-day{cls}'><b>{label}</b><span>{d:%d/%m}</span>"
            f"<small>{counts[idx]} việc</small>{badge}</div>"
        )
    return (
        "<div class='p12-day-strip'>" + "".join(cells) + "</div>"
        "<style>"
        ".p12-day-strip{display:grid;grid-template-columns:repeat(5,minmax(125px,1fr));gap:8px;margin:.25rem 0 .8rem 0;overflow-x:auto}"
        ".p12-day{min-width:0;border:1px solid rgba(244,180,26,.82);border-radius:12px;padding:9px 10px;text-align:center;background:linear-gradient(135deg,rgba(7,92,87,.94),rgba(15,116,107,.78));box-shadow:0 4px 12px rgba(0,0,0,.14)}"
        ".p12-day b{display:block;color:#FFD45A;font-size:.84rem;letter-spacing:.04em}.p12-day span{display:block;color:#fff;font-size:1.05rem;font-weight:950;margin-top:2px}.p12-day small{display:block;color:#fff;font-size:.70rem;font-weight:850;opacity:.90;margin-top:3px}.p12-day em{display:inline-block;margin-top:4px;padding:2px 7px;border-radius:999px;background:#2B2410;color:#FFD45A;font-size:.64rem;font-style:normal;font-weight:950}"
        ".p12-day-current{background:linear-gradient(135deg,#F4B41A,#FFD45A);border-color:#FFE589}.p12-day-current b,.p12-day-current span,.p12-day-current small{color:#2B2410}"
        "@media(max-width:760px){.p12-day-strip{grid-template-columns:repeat(5,135px)}}"
        "</style>"
    )


class _SingleHeaderBoardProxy:
    """Suppress phase-11 and phase-3 duplicate headers, inject one count-aware row."""
    def __init__(self, st, ws, items):
        self._st = st
        self._ws = ws
        self._items = items
        self._injected = False

    def __getattr__(self, name):
        return getattr(self._st, name)

    def markdown(self, body, *args, **kwargs):
        result = self._st.markdown(body, *args, **kwargs)
        if not self._injected and str(body or "").strip() == "### 🗓 Kế hoạch Thứ 2 → Thứ 6":
            self._st.html(_weekday_strip(self._ws, self._items))
            self._injected = True
        return result

    def html(self, body, *args, **kwargs):
        text = str(body or "")
        if "p11-day-strip" in text or "p3-day-head" in text:
            return None
        return self._st.html(body, *args, **kwargs)


def _install_week_board_single_header(logger=None):
    if getattr(weekfocus, "_P12_SINGLE_DAY_HEADER", False):
        return
    original = weekfocus._render_week_board

    def render_week_board(st, policy_arg, get_conn, uid, ws, items, status):
        return original(
            _SingleHeaderBoardProxy(st, ws, items),
            policy_arg, get_conn, uid, ws, items, status,
        )

    weekfocus._render_week_board = render_week_board
    weekfocus._P12_SINGLE_DAY_HEADER = True
    if logger:
        logger.info("P12_WEEK_BOARD_SINGLE_HEADER_INSTALLED upper_counts=1 lower_header_removed=1")


class _QuickAddFormProxy:
    """Prefill clicked weekday and clear all add gates after a successful save."""
    def __init__(self, st, ws):
        self._st = st
        self._ws = ws
        self._saved = False

    def __getattr__(self, name):
        return getattr(self._st, name)

    def date_input(self, label, *args, **kwargs):
        if str(label or "").strip().startswith("Ngày thực hiện"):
            key = f"wp_quick_day_{self._ws.isoformat()}"
            raw = self._st.session_state.get(key)
            if raw:
                try:
                    picked = date.fromisoformat(str(raw)[:10])
                    if self._ws <= picked <= self._ws + timedelta(days=6):
                        kwargs["value"] = picked
                except Exception:
                    self._st.session_state.pop(key, None)
        return self._st.date_input(label, *args, **kwargs)

    def toast(self, body, *args, **kwargs):
        if str(body or "").strip().startswith("Đã thêm công việc"):
            self._saved = True
        return self._st.toast(body, *args, **kwargs)

    def rerun(self, *args, **kwargs):
        if self._saved:
            ws_key = self._ws.isoformat()
            self._st.session_state.pop(f"wp_add_open_{ws_key}", None)
            self._st.session_state.pop(f"wp_quick_day_{ws_key}", None)
            self._st.session_state.pop(f"p3_emergent_open_{ws_key}", None)
        return self._st.rerun(*args, **kwargs)


def _install_weekly_quick_add_close(policy, logger=None):
    if getattr(policy, "_P12_QUICK_ADD_CLOSE", False):
        return
    original = policy._add_item_form

    def add_item_form(st, u, core, get_conn, ws, focus_rows, emergent=False,
                      logger=None, logger_arg=None, **kwargs):
        active_logger = logger_arg or logger
        return original(
            _QuickAddFormProxy(st, ws), u, core, get_conn, ws, focus_rows,
            emergent=emergent, logger=active_logger, **kwargs,
        )

    policy._add_item_form = add_item_form
    policy._P12_QUICK_ADD_CLOSE = True
    if logger:
        logger.info("P12_WEEKLY_QUICK_ADD_INSTALLED clicked_day_prefill=1 auto_close=1 session_clear=1")


def _ensure_cancel_schema(get_conn, customer_core=None, logger=None):
    if customer_core is not None:
        customer_core.ensure_schema(get_conn, logger)
    with get_conn() as c:
        if not _table_exists(c, "customer_work_cases"):
            return
        cols = _cols(c, "customer_work_cases")
        for name, ddl in (
            ("cancelled_at", "TEXT"),
            ("cancelled_by", "INTEGER"),
            ("cancel_reason", "TEXT"),
        ):
            if name not in cols:
                c.execute(f"ALTER TABLE customer_work_cases ADD COLUMN {name} {ddl}")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_work_cancel_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                requested_by INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL,
                decided_by INTEGER,
                decided_at TEXT,
                decision_note TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cw_cancel_one_pending
                ON customer_work_cancel_requests(case_id) WHERE status='PENDING';
            CREATE INDEX IF NOT EXISTS idx_cw_cancel_status
                ON customer_work_cancel_requests(status,requested_at);
            """
        )
    if logger:
        logger.info("P12_CUSTOMER_CANCEL_SCHEMA_READY pending_unique=1")


def _user_row(c, uid):
    if not _table_exists(c, "users"):
        return {}
    row = c.execute("SELECT * FROM users WHERE id=?", (int(uid),)).fetchone()
    return dict(row) if row else {}


def _request_case_cancel(get_conn, case_id, actor_uid, reason, logger=None):
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Phải nhập Lý do đề nghị hủy công việc.")
    ts = _now()
    with get_conn() as c:
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy công việc khách hàng.")
        case = dict(row)
        if str(case.get("status") or "") != "ACTIVE":
            raise ValueError("Chỉ công việc đang hoạt động mới được đề nghị hủy.")
        actor = _user_row(c, actor_uid)
        admin = bool(int(actor.get("is_admin") or 0))
        owner = int(case.get("owner_user_id") or 0) == int(actor_uid)
        if not (owner or admin):
            raise PermissionError("Chỉ cán bộ phụ trách hoặc Admin được gửi đề nghị hủy công việc này.")
        pending = c.execute(
            "SELECT id FROM customer_work_cancel_requests WHERE case_id=? AND status='PENDING'",
            (int(case_id),),
        ).fetchone()
        if pending:
            return int(pending[0])
        cur = c.execute(
            """INSERT INTO customer_work_cancel_requests(
               case_id,requested_by,reason,status,requested_at)
               VALUES(?,?,?,'PENDING',?)""",
            (int(case_id), int(actor_uid), reason, ts),
        )
        req_id = int(cur.lastrowid)
        if _table_exists(c, "case_actions"):
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (int(case_id), int(actor_uid), "CANCEL_REQUEST_P12", f"request_id={req_id}", ts),
            )
    if logger:
        logger.info("P12_CASE_CANCEL_REQUEST case=%s request=%s actor=%s", int(case_id), req_id, int(actor_uid))
    return req_id


def _controller_can_decide(policy, c, case, actor_uid):
    actor = _user_row(c, actor_uid)
    try:
        admin = bool(policy._is_admin(actor))
    except Exception:
        admin = bool(int(actor.get("is_admin") or 0))
    if admin:
        return True
    return int(case.get("controller_user_id") or 0) == int(actor_uid)


def _decide_case_cancel(get_conn, policy, request_id, actor_uid, approve=True, note="", logger=None):
    ts = _now()
    with get_conn() as c:
        req = c.execute(
            "SELECT * FROM customer_work_cancel_requests WHERE id=? AND status='PENDING'",
            (int(request_id),),
        ).fetchone()
        if not req:
            return False
        req = dict(req)
        case_row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (int(req["case_id"]),)).fetchone()
        if not case_row:
            return False
        case = dict(case_row)
        if not _controller_can_decide(policy, c, case, actor_uid):
            raise PermissionError("Chỉ Lãnh đạo kiểm soát của công việc hoặc Admin mới được phê duyệt đề nghị hủy.")
        status = "APPROVED" if approve else "REJECTED"
        c.execute(
            "UPDATE customer_work_cancel_requests SET status=?,decided_by=?,decided_at=?,decision_note=? WHERE id=?",
            (status, int(actor_uid), ts, str(note or "").strip() or None, int(request_id)),
        )
        if approve:
            cols = _cols(c, "customer_work_cases")
            approval_sql = ",plan_approval_status='CANCELLED'" if "plan_approval_status" in cols else ""
            c.execute(
                f"""UPDATE customer_work_cases SET status='CANCELLED',cancelled_at=?,cancelled_by=?,
                    cancel_reason=?,updated_at=?{approval_sql} WHERE id=?""",
                (ts, int(actor_uid), str(req.get("reason") or ""), ts, int(req["case_id"])),
            )
            if _table_exists(c, "case_reschedule_requests"):
                c.execute(
                    """UPDATE case_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,
                       decision_note=COALESCE(decision_note,'Công việc đã được phê duyệt hủy')
                       WHERE case_id=? AND status='PENDING'""",
                    (int(actor_uid), ts, int(req["case_id"])),
                )
        if _table_exists(c, "case_actions"):
            c.execute(
                "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
                (
                    int(req["case_id"]), int(actor_uid),
                    "CANCEL_APPROVE_P12" if approve else "CANCEL_REJECT_P12",
                    f"request_id={int(request_id)}", ts,
                ),
            )
        try:
            policy._notify(
                c, int(req.get("requested_by") or 0),
                "✅ Đề nghị hủy công việc đã được duyệt" if approve else "↩ Đề nghị hủy công việc bị từ chối",
                "Đề nghị hủy Công việc khách hàng đã được xử lý.",
            )
        except Exception:
            pass
    if logger:
        logger.info("P12_CASE_CANCEL_DECISION request=%s actor=%s approve=%s", int(request_id), int(actor_uid), int(bool(approve)))
    return True


def _pending_cancel_rows(get_conn, policy, u):
    uid = int(policy._uget(u, "id"))
    admin = bool(policy._is_admin(u))
    with get_conn() as c:
        if not _table_exists(c, _CANCEL_TABLE):
            return []
        sql = """
            SELECT r.*,w.case_code,w.title,w.owner_user_id,w.controller_user_id,
                   cu.customer_name,owner.full_name AS owner_name,req.full_name AS requester_name
            FROM customer_work_cancel_requests r
            JOIN customer_work_cases w ON w.id=r.case_id
            LEFT JOIN customers cu ON cu.id=w.customer_id
            LEFT JOIN users owner ON owner.id=w.owner_user_id
            LEFT JOIN users req ON req.id=r.requested_by
            WHERE r.status='PENDING'
        """
        params = []
        if not admin:
            sql += " AND w.controller_user_id=?"
            params.append(uid)
        sql += " ORDER BY r.requested_at,r.id"
        return [dict(r) for r in c.execute(sql, params).fetchall()]


_CANCEL_REASON_CSS = """
<style>
div[class*='st-key-p12_case_cancel_reason_'] textarea:placeholder-shown {
  border:2px solid #FF4B4B !important;
  box-shadow:0 0 0 1px rgba(255,75,75,.25) !important;
  background:rgba(255,75,75,.08) !important;
}
div[class*='st-key-p12_case_cancel_reason_']:has(textarea:placeholder-shown) label,
div[class*='st-key-p12_case_cancel_reason_']:has(textarea:placeholder-shown) label * {
  color:#FF4B4B !important;
  -webkit-text-fill-color:#FF4B4B !important;
  font-weight:900 !important;
}
</style>
"""


def _install_customer_cancel_detail(customer_ui, customer_core, policy, get_conn, logger=None):
    if getattr(customer_ui, "_P12_CANCEL_DETAIL", False):
        return
    original_detail = customer_ui._case_detail

    def case_detail(st, u, conn_fn, case_id, logger=None):
        active_logger = logger
        result = original_detail(st, u, conn_fn, case_id, active_logger)
        _ensure_cancel_schema(conn_fn, None, active_logger)
        uid = int(policy._uget(u, "id"))
        with conn_fn() as c:
            row = c.execute("SELECT * FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
            pending = c.execute(
                "SELECT * FROM customer_work_cancel_requests WHERE case_id=? AND status='PENDING' ORDER BY id DESC LIMIT 1",
                (int(case_id),),
            ).fetchone()
        if not row:
            return result
        case = dict(row)
        pending = dict(pending) if pending else None
        st.divider()
        st.subheader("🗑 Hủy công việc khách hàng")
        if str(case.get("status") or "") == "CANCELLED":
            st.error("Công việc đã được phê duyệt hủy." + (f" Lý do: {case.get('cancel_reason')}" if case.get("cancel_reason") else ""))
            return result
        if pending:
            st.warning(
                "Đề nghị hủy đang chờ Lãnh đạo kiểm soát phê duyệt. "
                f"Lý do: {pending.get('reason') or '—'}"
            )
            return result
        actor = {}
        with conn_fn() as c:
            actor = _user_row(c, uid)
        admin = bool(int(actor.get("is_admin") or 0))
        owner = int(case.get("owner_user_id") or 0) == uid
        if not (owner or admin):
            st.caption("Chỉ cán bộ phụ trách hoặc Admin được gửi đề nghị hủy; Lãnh đạo kiểm soát sẽ phê duyệt.")
            return result
        st.html(_CANCEL_REASON_CSS)
        payload = legacy_fast_form(
            [{"name":"reason","label":"Lý do đề nghị hủy","type":"textarea",
              "required":True,"placeholder":"Nhập lý do hủy cụ thể...","full":True}],
            "Gửi đề nghị hủy", key=f"p12_case_cancel_fast_{int(case_id)}_{uid}",
            reset_token=str(case.get("status") or ""),
        )
        if payload is not None:
            reason = str(payload.get("reason") or "")
            if not str(reason or "").strip():
                st.error("Vui lòng nhập Lý do đề nghị hủy.")
                return result
            try:
                req_id = _request_case_cancel(conn_fn, int(case_id), uid, reason, active_logger)
                controller = int(case.get("controller_user_id") or 0)
                if controller:
                    try:
                        with conn_fn() as c:
                            policy._notify(c, controller, "🗑 Có đề nghị hủy công việc cần duyệt", f"Công việc #{int(case_id)} đang chờ phê duyệt hủy.")
                    except Exception:
                        pass
                if active_logger:
                    active_logger.info("P12_CANCEL_REQUEST_UI case=%s request=%s actor=%s", int(case_id), int(req_id), uid)
                st.toast("Đã gửi đề nghị hủy cho Lãnh đạo kiểm soát.", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return result

    customer_ui._case_detail = case_detail
    customer_ui._P12_CANCEL_DETAIL = True

    original_list = customer_core.list_cases
    def list_cases(c, uid=None, manager=False, include_completed=False):
        rows = original_list(c, uid=uid, manager=manager, include_completed=include_completed)
        if include_completed:
            return rows
        return [x for x in rows if str(x.get("status") or "") != "CANCELLED"]
    customer_core.list_cases = list_cases

    original_change = customer_core.change_stage
    def change_stage(conn_fn, case_id, actor_uid, new_stage_id, note=None, logger=None):
        with conn_fn() as c:
            row = c.execute("SELECT status FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
            if row and str(row[0] or "") == "CANCELLED":
                raise ValueError("Công việc đã hủy, không thể cập nhật mục công việc.")
        return original_change(conn_fn, case_id, actor_uid, new_stage_id, note, logger)
    customer_core.change_stage = change_stage

    original_reschedule = customer_core.request_reschedule
    def request_reschedule(conn_fn, case_id, actor_uid, proposed_due_at, reason, logger=None):
        with conn_fn() as c:
            row = c.execute("SELECT status FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
            if row and str(row[0] or "") == "CANCELLED":
                raise ValueError("Công việc đã hủy, không thể đề nghị dời hạn.")
        return original_reschedule(conn_fn, case_id, actor_uid, proposed_due_at, reason, logger)
    customer_core.request_reschedule = request_reschedule

    if logger:
        logger.info("P12_CUSTOMER_CANCEL_DETAIL_INSTALLED reason_required=1 pending_approval=1 cancelled_hidden=1")


def _render_cancel_approvals(st, u, policy, get_conn, logger=None):
    rows = _pending_cancel_rows(get_conn, policy, u)
    st.markdown("### 🗑 Đề nghị hủy công việc khách hàng")
    if not rows:
        st.caption("Không có đề nghị hủy công việc khách hàng chờ xử lý.")
        return
    uid = int(policy._uget(u, "id"))
    for x in rows:
        rid = int(x.get("id") or 0)
        with st.container(key=f"p12_cancel_approval_{rid}", border=True):
            customer = html.escape(str(x.get("customer_name") or "—"))
            title = html.escape(str(x.get("title") or "Công việc"))
            code = html.escape(str(x.get("case_code") or f"CVKH-{int(x.get('case_id') or 0)}"))
            owner = html.escape(str(x.get("owner_name") or "—"))
            requester = html.escape(str(x.get("requester_name") or "—"))
            reason = html.escape(str(x.get("reason") or "—"))
            st.html(
                f"<div class='p12-cancel-head'><b>{customer} · {title}</b><span>{code}</span></div>"
                f"<div class='p12-cancel-meta'>👤 Phụ trách: {owner} · Người đề nghị: {requester} · Gửi lúc {html.escape(str(x.get('requested_at') or '—'))}</div>"
                f"<div class='p12-cancel-reason'><b>Lý do đề nghị hủy:</b> {reason}</div>"
                "<style>.p12-cancel-head{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.p12-cancel-head span{color:#FFD45A;font-weight:900}.p12-cancel-meta{font-size:.78rem;opacity:.86;margin-top:6px;white-space:normal;overflow-wrap:anywhere}.p12-cancel-reason{margin-top:8px;padding:9px 11px;border-left:5px solid #FF4B4B;background:rgba(255,75,75,.08);border-radius:8px;white-space:normal;overflow-wrap:anywhere}</style>"
            )
            note = st.text_input("Ý kiến phê duyệt", key=f"p12_cancel_decision_note_{rid}")
            a, b = st.columns(2)
            if a.button("✓ Phê duyệt hủy", key=f"p12_cancel_yes_{rid}", type="primary", use_container_width=True):
                try:
                    _decide_case_cancel(get_conn, policy, rid, uid, True, note, logger)
                    st.toast("Đã phê duyệt hủy công việc.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if b.button("✕ Từ chối", key=f"p12_cancel_no_{rid}", use_container_width=True):
                try:
                    _decide_case_cancel(get_conn, policy, rid, uid, False, note, logger)
                    st.toast("Đã từ chối đề nghị hủy.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _install_waiting_center(policy, weekly_core, customer_core, get_conn, logger=None):
    if getattr(p3dash, "_P12_WAITING_CENTER_PULSE", False):
        return
    original = p3dash._attention_dashboard

    def attention_dashboard(st, u, policy_arg, customer_core_arg, conn_fn, logger=None):
        active_logger = logger
        try:
            _, cases, moves, plans, wmoves = p4._pending_approval_data(
                u, policy, weekly_core, customer_core, conn_fn
            )
            attention = p4._attention_rows(u, policy, conn_fn)
            cancels = _pending_cancel_rows(conn_fn, policy, u)
            total = len(cases) + len(moves) + len(plans) + len(wmoves) + len(attention) + len(cancels)
        except Exception:
            cancels = []
            total = 0
        with st.container(key="p12_leader_waiting_center"):
            if total > 0:
                st.html(
                    "<style>@keyframes p12AttentionPulse{0%{box-shadow:0 0 0 1px rgba(244,180,26,.30)}100%{box-shadow:0 0 0 7px rgba(244,180,26,.10),0 0 28px rgba(244,180,26,.42)}}"
                    "div[class*='st-key-p12_leader_waiting_center']{border:2px solid #F4B41A!important;border-radius:14px!important;padding:8px 12px!important;animation:p12AttentionPulse 1.15s ease-in-out infinite alternate!important}"
                    "@media (prefers-reduced-motion:reduce){div[class*='st-key-p12_leader_waiting_center']{animation:none!important}}</style>"
                )
                st.warning(f"⚠ Có {total} nội dung đang chờ lãnh đạo xử lý.")
            result = original(st, u, policy_arg, customer_core_arg, conn_fn, active_logger)
            _render_cancel_approvals(st, u, policy, conn_fn, active_logger)
            return result

    p3dash._attention_dashboard = attention_dashboard
    p3dash._P12_WAITING_CENTER_PULSE = True
    if logger:
        logger.info("P12_WAITING_CENTER_INSTALLED pending_pulse=1 cancel_queue=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype=None, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    get_conn = app_ns["get_conn"]
    _ensure_cancel_schema(get_conn, customer_core, logger)
    _install_backup_route_guard(logger)
    _install_week_board_single_header(logger)
    _install_weekly_quick_add_close(policy, logger)
    _install_customer_cancel_detail(customer_ui, customer_core, policy, get_conn, logger)
    _install_waiting_center(policy, weekly_core, customer_core, get_conn, logger)

    # Keep Phase 11's full-detail Excel export complete after introducing a new table.
    if "customer_work_cancel_requests" not in phase11._EXPORT_TABLES:
        phase11._EXPORT_TABLES = tuple(phase11._EXPORT_TABLES) + ("customer_work_cancel_requests",)

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE12_INSTALLED version=%s backup_route_only=1 single_week_header=1 quick_add_close=1 customer_cancel=1 waiting_pulse=1",
            VERSION,
        )
