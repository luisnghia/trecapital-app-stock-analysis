"""Operational planning Phase 7 corrections.

User-facing fixes:
- restore the original large six-card System Admin navigation and make every card route;
- weekly-plan cancellation requested by staff only becomes effective after the
  selected controlling leader (or Admin) approves it;
- translate weekly progress-history status codes to Vietnamese.
"""
from __future__ import annotations

from datetime import datetime
import html
import json

from khdn_apps import backup_management_patch as backup
from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase3_weekly as p3week
from khdn_apps import planning_operational_phase4_patch as p4
from khdn_apps import planning_operational_phase5_patch as p5
from khdn_apps import planning_operational_phase6_patch as p6

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE7_VERSION"

_ADMIN_OPTIONS = [
    ("users", "👥 Người dùng"),
    ("customers", "🏢 Khách hàng CIF"),
    ("types", "🧩 Loại công việc"),
    ("reasons", "🧩 Nhóm nguyên nhân tác nghiệp"),
    ("audit", "🧾 Audit"),
    ("backup", "💾 Sao lưu"),
]

_STATUS_VI = {
    "PLANNED": "Chưa làm",
    "IN_PROGRESS": "Đang làm",
    "DONE": "Hoàn thành",
    "CANCELLED": "Đã hủy",
}

_ACTION_VI = {
    "EXEC_UPDATE_PHASE3": "Cập nhật tiến độ",
    "EXEC_UPDATE_PHASE2": "Cập nhật tiến độ",
    "EXEC_UPDATE": "Cập nhật tiến độ",
    "RESCHEDULE_APPROVE": "Dời lịch được duyệt",
    "RESCHEDULE_REJECT": "Dời lịch bị từ chối",
    "PHAT_SINH": "Công việc phát sinh",
    "CLASSIFICATION_CHANGE": "Điều chỉnh phân loại",
    "DRAFT_REMOVE": "Bỏ khỏi bản nháp",
    "DRAFT_EDIT": "Sửa công việc bản nháp",
    "CANCEL_REQUEST": "Đề nghị hủy công việc",
    "CANCEL_APPROVE": "Hủy công việc được phê duyệt",
    "CANCEL_REJECT": "Đề nghị hủy bị từ chối",
}

_BASE_P6_FMT = p6._fmt_action


def _uget(u, key, default=None):
    try:
        return u.get(key, default)
    except Exception:
        try:
            return u[key]
        except Exception:
            return default


def _status_vi(value):
    raw = str(value or "").strip()
    return _STATUS_VI.get(raw, raw or "—")


def _fmt_action_vi(action, detail):
    """Human-readable Vietnamese history, including legacy JSON actions."""
    action = str(action or "")
    if action == "CLASSIFICATION_CHANGE":
        return _BASE_P6_FMT(action, detail)

    label = _ACTION_VI.get(action, action or "Cập nhật")
    raw = str(detail or "").strip()
    try:
        obj = json.loads(raw)
    except Exception:
        return label, raw or "—"
    if not isinstance(obj, dict):
        return label, raw or "—"

    if action == "DRAFT_EDIT":
        before, after = obj.get("before") or {}, obj.get("after") or {}
        fields = {"title": "Công việc", "work_date": "Ngày thực hiện", "expected_complete_date": "Ngày hoàn thành",
                  "customer_text": "Khách hàng", "controller_name_snapshot": "Lãnh đạo phụ trách",
                  "focus_name_snapshot": "Mục trọng tâm", "note": "Ghi chú"}
        parts = []
        for field, caption in fields.items():
            old, new = before.get(field), after.get(field)
            if old != new:
                if field in {"work_date", "expected_complete_date"}:
                    old, new = p3dash.dmy(old), p3dash.dmy(new)
                parts.append(f"{caption}: {old or '—'} → {new or '—'}")
        if before.get("priority_quadrant") != after.get("priority_quadrant"):
            parts.append(f"Ưu tiên: Q{before.get('priority_quadrant') or '—'} → Q{after.get('priority_quadrant') or '—'}")
        return label, " · ".join(parts) or "Đã lưu nội dung bản nháp"

    if action == "CANCEL_REQUEST":
        before = _status_vi(obj.get("status_before") or obj.get("old_status"))
        reason = str(obj.get("reason") or "").strip()
        parts = [f"Trạng thái hiện tại: {before}"]
        if reason:
            parts.append(f"Lý do hủy: {reason}")
        return label, " · ".join(parts)

    if action in {"CANCEL_APPROVE", "CANCEL_REJECT"}:
        reason = str(obj.get("reason") or "").strip()
        decision = str(obj.get("decision_note") or obj.get("note") or "").strip()
        parts = []
        if action == "CANCEL_APPROVE":
            parts.append(f"{_status_vi(obj.get('status_before'))} → Đã hủy")
        else:
            parts.append("Giữ nguyên công việc")
        if reason:
            parts.append(f"Lý do đề nghị: {reason}")
        if decision:
            parts.append(f"Ý kiến lãnh đạo: {decision}")
        return label, " · ".join(parts)

    old_status = obj.get("old_status")
    new_status = obj.get("new_status") or obj.get("status")
    note = obj.get("actual_result") or obj.get("note") or obj.get("text") or ""
    parts = []
    if old_status or new_status:
        parts.append(f"{_status_vi(old_status)} → {_status_vi(new_status)}")
    if note:
        parts.append(str(note))
    return label, " · ".join(parts) if parts else "Đã cập nhật"


# ---------------------------------------------------------------------------
# System Admin: restore the original large-card visual language and real routes.
# ---------------------------------------------------------------------------
def _admin_cards(st, default="users"):
    allowed = {value for value, _ in _ADMIN_OPTIONS}
    current = str(st.session_state.get("admin_view") or default)
    if current not in allowed:
        current = default
        st.session_state["admin_view"] = current

    with st.container(key="p7_system_admin_cards"):
        cols = st.columns(6, gap="small")
        for col, (value, label) in zip(cols, _ADMIN_OPTIONS):
            with col:
                key = f"p7_admin_card_{value}"
                if st.button(label, key=key, use_container_width=True):
                    st.session_state["admin_view"] = value
                    st.session_state["system_admin_view_v2"] = value
                    st.session_state["system_admin_view_v3"] = value
                    st.session_state["system_admin_view_v4"] = value
                    st.rerun()
                active_css = (
                    "border:2px solid #F4B41A!important;box-shadow:0 0 0 1px rgba(244,180,26,.28)!important;"
                    if value == current else
                    "border:1px solid rgba(99,220,203,.62)!important;"
                )
                st.html(
                    f"""<style>
                    div[class*='st-key-{key}'] button{{
                      min-height:7.25rem!important;border-radius:18px!important;
                      background:linear-gradient(145deg,#145C56,#176C64)!important;
                      color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
                      font-weight:900!important;padding:.75rem .45rem!important;
                      white-space:normal!important;line-height:1.25!important;{active_css}
                    }}
                    div[class*='st-key-{key}'] button *{{
                      color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
                      font-weight:900!important;white-space:normal!important;
                    }}
                    </style>"""
                )
    return current


def _admin_title(app_ns):
    page_title = app_ns.get("page_title")
    if page_title:
        page_title(
            "Quản trị hệ thống",
            "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân tác nghiệp, audit và sao lưu dữ liệu.",
        )
    else:
        app_ns["st"].title("Quản trị hệ thống")


def _render_reasons(app_ns, u):
    st = app_ns["st"]
    _admin_title(app_ns)
    _admin_cards(st, "reasons")
    renderer = app_ns.get("_render_reason_category_manager")
    if callable(renderer):
        renderer(u)
    else:
        st.error("Không tìm thấy bộ quản lý Nhóm nguyên nhân tác nghiệp.")


def _render_audit(app_ns):
    st = app_ns["st"]
    _admin_title(app_ns)
    _admin_cards(st, "audit")
    aud = app_ns["qdf"](
        """SELECT a.id,a.created_at,u.full_name actor,a.action,a.object_type,a.object_id,a.detail
           FROM system_audit a LEFT JOIN users u ON u.id=a.actor_user_id
           ORDER BY a.id DESC LIMIT 2000"""
    )
    st.subheader("Audit hệ thống")
    if aud is None or aud.empty:
        st.info("Chưa có dữ liệu audit.")
        return
    if "created_at" in aud.columns and callable(app_ns.get("fmt_dt")):
        aud["created_at"] = aud["created_at"].map(app_ns["fmt_dt"])
    show = aud.rename(columns={
        "created_at": "Thời gian", "actor": "Người thực hiện", "action": "Hành động",
        "object_type": "Đối tượng", "object_id": "ID", "detail": "Chi tiết",
    })
    table = show.to_html(index=False, escape=True, border=0, classes="p7-audit-table")
    st.html(
        "<div class='p7-audit-wrap'>" + table + "</div>"
        "<style>.p7-audit-wrap{overflow:auto;max-height:620px;width:100%}"
        ".p7-audit-table{width:100%;table-layout:fixed;border-collapse:collapse}"
        ".p7-audit-table th,.p7-audit-table td{padding:7px 9px;border:1px solid rgba(120,160,150,.28);"
        "white-space:normal;overflow-wrap:anywhere;vertical-align:top;font-size:.78rem}"
        ".p7-audit-table th{font-weight:950;color:#63DCCB;position:sticky;top:0;background:#123C38}</style>"
    )


def _render_backup(app_ns, u, logger=None):
    st = app_ns["st"]
    _admin_title(app_ns)
    _admin_cards(st, "backup")
    backup.render_backup_admin(st, u, app_ns, logger)


def _install_admin_routes(app_ns, policy, logger=None):
    st = app_ns["st"]
    previous_pill = app_ns["pill_nav"]

    def pill_nav(state_key, options, default=None, prefix="subnav"):
        if state_key == "admin_view" and st.session_state.get("main_page") == "admin":
            return _admin_cards(st, default or "users")
        return previous_pill(state_key, options, default=default, prefix=prefix)

    app_ns["pill_nav"] = pill_nav
    previous_admin = app_ns["admin_page"]

    def admin_page(u):
        if st.session_state.get("main_page") != "admin":
            return previous_admin(u)
        if not bool(_uget(u, "is_admin", False)):
            st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")
            return
        st.session_state["admin_scope"] = "system"
        view = str(st.session_state.get("admin_view") or "users")
        if view not in {v for v, _ in _ADMIN_OPTIONS}:
            view = "users"
            st.session_state["admin_view"] = view
        for key in ("system_admin_view_v2", "system_admin_view_v3", "system_admin_view_v4"):
            st.session_state[key] = view

        if view == "types":
            return p6._render_system_types(app_ns, policy, u, logger or app_ns.get("LOGGER"))
        if view == "reasons":
            return _render_reasons(app_ns, u)
        if view == "audit":
            return _render_audit(app_ns)
        if view == "backup":
            return _render_backup(app_ns, u, logger or app_ns.get("LOGGER"))
        # Users and Customer/CIF retain the mature original page/forms; because
        # pill_nav above is a dynamic global in that page, it now renders the
        # same six large cards instead of the temporary compact Phase-6 strip.
        return previous_admin(u)

    app_ns["admin_page"] = admin_page
    if logger:
        logger.info("P7_SYSTEM_ADMIN_ROUTES_INSTALLED large_cards=1 routes=6")


# ---------------------------------------------------------------------------
# Weekly cancellation request/approval lifecycle.
# ---------------------------------------------------------------------------
def _ensure_cancel_schema(get_conn, logger=None):
    with get_conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS weekly_plan_cancel_requests(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                plan_id INTEGER,
                requested_by INTEGER NOT NULL,
                controller_user_id INTEGER,
                status_before TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                requested_at TEXT NOT NULL,
                decided_by INTEGER,
                decided_at TEXT,
                decision_note TEXT,
                FOREIGN KEY(item_id) REFERENCES weekly_plan_items(id),
                FOREIGN KEY(plan_id) REFERENCES weekly_plans(id),
                FOREIGN KEY(requested_by) REFERENCES users(id),
                FOREIGN KEY(controller_user_id) REFERENCES users(id),
                FOREIGN KEY(decided_by) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_week_cancel_status
                ON weekly_plan_cancel_requests(status,controller_user_id,requested_at,id);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_week_cancel_one_pending
                ON weekly_plan_cancel_requests(item_id) WHERE status='PENDING';
            """
        )
    if logger:
        logger.info("P7_WEEK_CANCEL_SCHEMA_READY")


def _pending_cancel(c, item_id):
    row = c.execute(
        "SELECT * FROM weekly_plan_cancel_requests WHERE item_id=? AND status='PENDING' ORDER BY id DESC LIMIT 1",
        (int(item_id),),
    ).fetchone()
    return dict(row) if row else None


def _weekly_controller_allows(c, actor_uid, item_id):
    actor = c.execute(
        "SELECT id,role,is_admin,active FROM users WHERE id=?", (int(actor_uid),)
    ).fetchone()
    if not actor or not int(actor["active"] or 0):
        return False
    if bool(int(actor["is_admin"] or 0)):
        return True
    if str(actor["role"] or "") != "Lãnh đạo phòng":
        return False
    cols = {str(r[1]) for r in c.execute("PRAGMA table_info(weekly_plan_items)").fetchall()}
    if "controller_user_id" not in cols:
        return False
    row = c.execute(
        "SELECT controller_user_id FROM weekly_plan_items WHERE id=?", (int(item_id),)
    ).fetchone()
    return bool(row and row["controller_user_id"] and int(row["controller_user_id"]) == int(actor_uid))


def _request_cancel(get_conn, item_id, actor_uid, reason, logger=None):
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("Bắt buộc nhập lý do hủy công việc.")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        item = c.execute(
            "SELECT id,plan_id,user_id,status,controller_user_id,title FROM weekly_plan_items WHERE id=?",
            (int(item_id),),
        ).fetchone()
        if not item or int(item["user_id"] or 0) != int(actor_uid):
            raise PermissionError("Bạn chỉ được đề nghị hủy công việc kế hoạch tuần của chính mình.")
        if str(item["status"] or "") == "CANCELLED":
            raise ValueError("Công việc đã được hủy trước đó.")
        if _pending_cancel(c, item_id):
            raise ValueError("Công việc này đã có đề nghị hủy đang chờ phê duyệt.")
        cur = c.execute(
            """INSERT INTO weekly_plan_cancel_requests(
               item_id,plan_id,requested_by,controller_user_id,status_before,reason,status,requested_at)
               VALUES(?,?,?,?,?,?,'PENDING',?)""",
            (
                int(item_id), int(item["plan_id"] or 0), int(actor_uid), item["controller_user_id"],
                str(item["status"] or "PLANNED"), reason, ts,
            ),
        )
        req_id = int(cur.lastrowid)
        detail = json.dumps(
            {"request_id": req_id, "status_before": str(item["status"] or "PLANNED"), "reason": reason},
            ensure_ascii=False,
        )
        c.execute(
            "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'CANCEL_REQUEST',?,?)",
            (int(item_id), int(actor_uid), detail, ts),
        )
        if item["controller_user_id"] and int(item["controller_user_id"]) != int(actor_uid):
            try:
                # Keep the same notification channel as the rest of Planning.
                p = c.execute("SELECT full_name FROM users WHERE id=?", (int(actor_uid),)).fetchone()
                title = str(item["title"] or "Công việc")
                # Notification helper is installed on policy, therefore emitted by caller below.
                _ = p, title
            except Exception:
                pass
    if logger:
        logger.info("P7_WEEK_CANCEL_REQUEST item=%s actor=%s", item_id, actor_uid)
    return req_id


def _decide_cancel(get_conn, policy, request_id, actor_uid, approve, decision_note="", logger=None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as c:
        req = c.execute(
            "SELECT * FROM weekly_plan_cancel_requests WHERE id=? AND status='PENDING'",
            (int(request_id),),
        ).fetchone()
        if not req:
            raise ValueError("Đề nghị hủy không còn ở trạng thái chờ phê duyệt.")
        if not _weekly_controller_allows(c, actor_uid, int(req["item_id"])):
            raise PermissionError(
                "Chỉ Lãnh đạo kiểm soát của công việc này hoặc Admin mới được phê duyệt đề nghị hủy."
            )
        if not approve and not str(decision_note or "").strip():
            raise ValueError("Khi từ chối, bắt buộc nhập ý kiến/lý do từ chối.")
        status = "APPROVED" if approve else "REJECTED"
        c.execute(
            """UPDATE weekly_plan_cancel_requests
               SET status=?,decided_by=?,decided_at=?,decision_note=? WHERE id=? AND status='PENDING'""",
            (status, int(actor_uid), ts, str(decision_note or "").strip(), int(request_id)),
        )
        if approve:
            c.execute(
                "UPDATE weekly_plan_items SET status='CANCELLED',completed_at=NULL,updated_at=? WHERE id=?",
                (ts, int(req["item_id"])),
            )
        detail = json.dumps(
            {
                "request_id": int(request_id), "status_before": req["status_before"],
                "reason": req["reason"], "decision_note": str(decision_note or "").strip(),
            },
            ensure_ascii=False,
        )
        action = "CANCEL_APPROVE" if approve else "CANCEL_REJECT"
        c.execute(
            "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
            (int(req["item_id"]), int(actor_uid), action, detail, ts),
        )
        try:
            policy._notify(
                c, int(req["requested_by"]),
                "✅ Đề nghị hủy công việc đã được duyệt" if approve else "↩ Đề nghị hủy công việc bị từ chối",
                (str(decision_note or "").strip() or str(req["reason"] or "")).strip(),
            )
        except Exception:
            pass
    if logger:
        logger.info(
            "P7_WEEK_CANCEL_DECISION request=%s actor=%s approve=%s", request_id, actor_uid, int(bool(approve))
        )
    return True


def _render_update_form(st, u, policy, weekly_core, get_conn, item, logger=None):
    iid = int(item["id"])
    uid = int(policy._uget(u, "id"))
    if int(item.get("user_id") or 0) != uid:
        return
    _ensure_cancel_schema(get_conn, logger)
    history = p5._history_rows(get_conn, iid)
    with get_conn() as c:
        pending = _pending_cancel(c, iid)

    with st.container(border=True):
        st.markdown(f"#### 🔄 Cập nhật tiến độ · {item.get('title')}")
        st.markdown("##### 🕘 Lịch sử thay đổi / cập nhật tiến độ")
        if not history:
            st.caption("Chưa có lịch sử cập nhật.")
        else:
            for row in history[:6]:
                label, detail = _fmt_action_vi(row.get("action"), row.get("detail"))
                st.html(
                    f"""<div class='p7hist'><b>{p3dash.esc(label)}</b> · {p3dash.esc(row.get('actor_name') or '—')} · {p3dash.esc(p3dash.dt(row.get('created_at')))}
                    <br><span>{p3dash.esc(detail)}</span></div>
                    <style>.p7hist{{padding:7px 9px;margin:5px 0;border-left:4px solid #F4B41A;border-radius:7px;background:rgba(244,180,26,.08);font-size:.76rem;white-space:normal;overflow-wrap:anywhere}}.p7hist span{{color:#63DCCB;font-weight:800}}</style>"""
                )

        if pending:
            st.warning(
                "Đề nghị hủy công việc đang chờ Lãnh đạo kiểm soát/Admin phê duyệt. "
                "Công việc vẫn giữ nguyên trạng thái cho đến khi được duyệt."
            )
            st.caption(f"Lý do hủy: {pending.get('reason') or '—'}")

        labels = {"PLANNED": "Chưa làm", "IN_PROGRESS": "Đang làm", "DONE": "Hoàn thành", "CANCELLED": "Hủy"}
        options = list(labels)
        cur = str(item.get("status") or "PLANNED")
        stat = st.selectbox(
            "Trạng thái", options, index=options.index(cur) if cur in options else 0,
            format_func=lambda z: labels[z], key=f"p7_status_{iid}",
        )
        result = st.text_area(
            "Kết quả thực tế / ghi chú", value=str(item.get("actual_result") or ""),
            max_chars=1000, key=f"p7_result_{iid}",
        )
        cancel_reason = ""
        if stat == "CANCELLED" and cur != "CANCELLED":
            st.info("Hủy công việc không có hiệu lực ngay. Hệ thống sẽ gửi đề nghị để Lãnh đạo kiểm soát/Admin phê duyệt.")
            cancel_reason = st.text_area(
                "Lý do đề nghị hủy *", max_chars=1000, key=f"p7_cancel_reason_{iid}",
                placeholder="Nêu rõ nguyên nhân cần hủy công việc trong kế hoạch tuần.",
            )

        a, b = st.columns(2)
        save_label = "Gửi đề nghị hủy" if stat == "CANCELLED" and cur != "CANCELLED" else "Lưu cập nhật"
        disabled = bool(pending and stat == "CANCELLED" and cur != "CANCELLED")
        if a.button(save_label, key=f"p7_update_save_{iid}", type="primary", use_container_width=True, disabled=disabled):
            if stat == "CANCELLED" and cur != "CANCELLED":
                if not str(cancel_reason or "").strip():
                    st.error("Bắt buộc nhập lý do đề nghị hủy.")
                    return
                try:
                    _request_cancel(get_conn, iid, uid, cancel_reason, logger)
                    with get_conn() as c:
                        row = c.execute("SELECT controller_user_id FROM weekly_plan_items WHERE id=?", (iid,)).fetchone()
                        controller = int(row["controller_user_id"] or 0) if row else 0
                        if controller and controller != uid:
                            try:
                                policy._notify(
                                    c, controller, "🗑 Có đề nghị hủy công việc kế hoạch tuần",
                                    f"{item.get('title') or 'Công việc'} · {str(cancel_reason).strip()}",
                                )
                            except Exception:
                                pass
                    st.toast("Đã gửi đề nghị hủy; công việc chưa bị hủy cho đến khi được phê duyệt.", icon="✅")
                    st.session_state.pop("p3_update_week_item", None)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
                return

            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            completed = item.get("completed_at")
            if stat == "DONE" and not completed:
                completed = ts
            if stat != "DONE":
                completed = None
            detail = json.dumps(
                {"old_status": cur, "new_status": stat, "actual_result": str(result or "").strip()},
                ensure_ascii=False,
            )
            with get_conn() as c:
                c.execute(
                    "UPDATE weekly_plan_items SET status=?,actual_result=?,completed_at=?,updated_at=? WHERE id=? AND user_id=?",
                    (stat, str(result or "").strip(), completed, ts, iid, uid),
                )
                c.execute(
                    "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'EXEC_UPDATE_PHASE3',?,?)",
                    (iid, uid, detail, ts),
                )
            if logger:
                logger.info("P7_WEEK_PROGRESS_UPDATE item=%s actor=%s status=%s", iid, uid, stat)
            st.session_state.pop("p3_update_week_item", None)
            st.rerun()
        if b.button("Đóng", key=f"p7_update_close_{iid}", use_container_width=True):
            st.session_state.pop("p3_update_week_item", None)
            st.rerun()


def _render_cancel_approvals(st, u, policy, get_conn, logger=None):
    _ensure_cancel_schema(get_conn, logger)
    uid = int(policy._uget(u, "id"))
    admin = bool(policy._is_admin(u))
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            """SELECT r.*,w.title,w.customer_text,w.user_id,w.work_date,w.expected_complete_date,
                      req.full_name requester_name,ctrl.full_name controller_name
               FROM weekly_plan_cancel_requests r
               JOIN weekly_plan_items w ON w.id=r.item_id
               LEFT JOIN users req ON req.id=r.requested_by
               LEFT JOIN users ctrl ON ctrl.id=w.controller_user_id
               WHERE r.status='PENDING' ORDER BY r.requested_at,r.id"""
        ).fetchall()]
        if not admin:
            rows = [r for r in rows if _weekly_controller_allows(c, uid, int(r["item_id"]))]

    st.markdown("### 🗑 Đề nghị hủy công việc kế hoạch tuần")
    if not rows:
        st.caption("Không có đề nghị hủy công việc đang chờ phê duyệt.")
        return

    for row in rows:
        rid = int(row["id"])
        with st.container(key=f"p7_cancel_approval_{rid}", border=True):
            st.html(
                f"""<div class='p7ca-title'>{p3dash.esc(row.get('title') or 'Công việc')}</div>
                <div class='p7ca-row'><span>👤 <b>Đề nghị:</b> {p3dash.esc(row.get('requester_name') or '—')}</span>
                <span>🛡️ <b>Kiểm soát:</b> {p3dash.esc(row.get('controller_name') or '—')}</span>
                <span>📍 <b>Trạng thái:</b> {p3dash.esc(_status_vi(row.get('status_before')))}</span></div>
                <div class='p7ca-reason'>📝 <b>Lý do hủy:</b> {p3dash.esc(row.get('reason') or '—')}</div>
                <style>.p7ca-title{{font-weight:950;color:#63DCCB;font-size:.96rem}}.p7ca-row{{display:flex;flex-wrap:wrap;gap:7px 14px;font-size:.78rem;margin-top:6px}}.p7ca-reason{{font-size:.80rem;margin-top:7px;color:#FFD166;white-space:normal;overflow-wrap:anywhere}}</style>"""
            )
            note = st.text_input("Ý kiến phê duyệt / lý do từ chối", key=f"p7_cancel_decision_note_{rid}")
            yes, no = st.columns(2)
            if yes.button("✓ Phê duyệt hủy", key=f"p7_cancel_yes_{rid}", type="primary", use_container_width=True):
                try:
                    _decide_cancel(get_conn, policy, rid, uid, True, note, logger)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if no.button("↩ Từ chối hủy", key=f"p7_cancel_no_{rid}", use_container_width=True):
                try:
                    _decide_cancel(get_conn, policy, rid, uid, False, note, logger)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def _install_cancel_approval_center(policy, get_conn, logger=None):
    original = p4._render_approval_items

    def render(st, u, policy_arg, weekly_core, customer_core, customer_ui, conn_fn, logger_arg=None):
        original(st, u, policy_arg, weekly_core, customer_core, customer_ui, conn_fn, logger_arg)
        st.divider()
        _render_cancel_approvals(st, u, policy_arg, conn_fn, logger_arg or logger)

    p4._render_approval_items = render
    if logger:
        logger.info("P7_WEEK_CANCEL_APPROVAL_CENTER_INSTALLED")


def _install_weekly_progress(policy, get_conn, logger=None):
    _ensure_cancel_schema(get_conn, logger)
    p5._fmt_action = _fmt_action_vi
    p6._fmt_action = _fmt_action_vi
    p3week.render_week_update_form = _render_update_form
    p3dash.render_week_update_form = _render_update_form
    if logger:
        logger.info("P7_WEEK_PROGRESS_INSTALLED cancel_requires_approval=1 vietnamese_history=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    app_logger = logger or app_ns.get("LOGGER")
    get_conn = app_ns["get_conn"]

    _install_admin_routes(app_ns, policy, app_logger)
    _install_weekly_progress(policy, get_conn, app_logger)
    _install_cancel_approval_center(policy, get_conn, app_logger)

    setattr(policy, _FLAG, VERSION)
    if app_logger:
        app_logger.info(
            "PLANNING_OPERATIONAL_PHASE7_INSTALLED version=%s admin_routes=6 large_cards=1 cancel_approval=1 vi_history=1",
            VERSION,
        )
