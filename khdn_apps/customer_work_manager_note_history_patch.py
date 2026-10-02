"""Manager/Admin note editing and approval-comment history for Customer Work.

Business rules:
- only active Lãnh đạo phòng/Admin may edit the persisted customer_work_cases.note;
- note edits never change Customer ID, workflow state, stage, due date or priority;
- every note edit is appended to case_actions for auditability;
- Customer Work detail shows approval/change decisions directly under the existing
  "Lịch sử mục công việc" table, together with the exact Lãnh đạo/Admin comment;
- reschedule decisions read the authoritative request row so old/new date, reason
  and decision_note remain visible even when legacy case_actions detail is sparse;
- approval inputs are labelled explicitly as the leader/admin comment.
"""
from __future__ import annotations

import json
from datetime import datetime

VERSION = "1.1.0"
_FLAG = "_CUSTOMER_WORK_MANAGER_NOTE_HISTORY_VERSION"
_STAGE_HISTORY_TITLE = "Lịch sử mục công việc"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _manager_row(c, uid):
    row = c.execute(
        "SELECT id,full_name,role,is_admin,active FROM users WHERE id=?",
        (int(uid),),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    if not int(d.get("active") or 0):
        return None
    if str(d.get("role") or "") == "Lãnh đạo phòng" or int(d.get("is_admin") or 0) == 1:
        return d
    return None


def update_case_note(get_conn, case_id, actor_uid, note, logger=None):
    """Manager/Admin-only update of the canonical Customer Work note."""
    ts = _now()
    text = str(note or "").strip()
    with get_conn() as c:
        actor = _manager_row(c, actor_uid)
        if not actor:
            raise PermissionError("Chỉ Lãnh đạo phòng/Admin được chỉnh sửa Ghi chú công việc khách hàng")
        row = c.execute(
            "SELECT id,note FROM customer_work_cases WHERE id=?", (int(case_id),)
        ).fetchone()
        if not row:
            raise ValueError("Không tìm thấy công việc khách hàng")
        old = str(row["note"] or "")
        if old.strip() == text:
            return False
        c.execute(
            "UPDATE customer_work_cases SET note=?,updated_at=? WHERE id=?",
            (text or None, ts, int(case_id)),
        )
        detail = json.dumps(
            {
                "old_note": old or None,
                "new_note": text or None,
                "manager_comment": text or None,
            },
            ensure_ascii=False,
        )
        c.execute(
            "INSERT INTO case_actions(case_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
            (int(case_id), int(actor_uid), "NOTE_EDIT", detail, ts),
        )
    if logger:
        logger.info("CUSTOMER_WORK_MANAGER_NOTE_EDIT case=%s actor=%s", case_id, actor_uid)
    return True


def _dt_text(v):
    if not v:
        return "—"
    try:
        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(v)


def _short_text(v):
    return str(v or "").strip()


def _comment(v):
    text = _short_text(v)
    return text if text else "Không có ý kiến ghi chú"


def _decode_action(action, detail):
    """Return (label, change detail, leader comment) for case_actions rows."""
    raw = "" if detail is None else str(detail)
    payload = None
    try:
        payload = json.loads(raw) if raw.strip() else None
    except Exception:
        payload = None

    action = str(action or "")
    if action == "PLAN_APPROVE":
        note = payload.get("note") if isinstance(payload, dict) else raw
        return "Phê duyệt công việc", "Phê duyệt kế hoạch công việc khách hàng", _comment(note)
    if action == "PLAN_REJECT":
        note = payload.get("note") if isinstance(payload, dict) else raw
        return "Từ chối công việc", "Từ chối kế hoạch công việc khách hàng", _comment(note)
    if action == "RESCHEDULE_DECISION":
        if isinstance(payload, dict):
            status = str(payload.get("status") or "").upper()
            note = payload.get("note")
        else:
            status, note = "", raw
        label = "Phê duyệt dời thời gian" if status == "APPROVED" else (
            "Từ chối dời thời gian" if status == "REJECTED" else "Quyết định dời thời gian"
        )
        return label, label, _comment(note)
    if action == "NOTE_EDIT":
        if isinstance(payload, dict):
            old_note = _short_text(payload.get("old_note")) or "(trống)"
            new_note = _short_text(payload.get("new_note")) or "(trống)"
            manager_comment = payload.get("manager_comment")
            detail_text = f"Ghi chú công việc: {old_note} → {new_note}"
            return "Chỉnh sửa Ghi chú công việc", detail_text, _comment(manager_comment or new_note)
        return "Chỉnh sửa Ghi chú công việc", "Cập nhật Ghi chú công việc", _comment(raw)
    return action, action, _comment(raw)


def _reschedule_rows(c, case_id):
    """Authoritative reschedule decision rows, including exact decision_note."""
    try:
        rows = [dict(r) for r in c.execute(
            """SELECT r.id,r.old_due_at,r.proposed_due_at,r.reason,r.status,
                      r.decided_at,r.decision_note,u.full_name AS actor_name
               FROM case_reschedule_requests r
               LEFT JOIN users u ON u.id=r.decided_by
               WHERE r.case_id=? AND r.status IN ('APPROVED','REJECTED')
                     AND r.decided_at IS NOT NULL
               ORDER BY r.decided_at DESC,r.id DESC""",
            (int(case_id),),
        ).fetchall()]
    except Exception:
        return []
    out = []
    for r in rows:
        approved = str(r.get("status") or "").upper() == "APPROVED"
        action = "Phê duyệt dời thời gian" if approved else "Từ chối dời thời gian"
        change = f"{_dt_text(r.get('old_due_at'))} → {_dt_text(r.get('proposed_due_at'))}"
        reason = _short_text(r.get("reason"))
        if reason:
            change += f" · Lý do đề nghị: {reason}"
        out.append(
            {
                "time": r.get("decided_at"),
                "action": action,
                "actor": r.get("actor_name") or "—",
                "change": change,
                "comment": _comment(r.get("decision_note")),
                "source": "reschedule_request",
            }
        )
    return out


def approval_history(c, case_id):
    """Decision/audit rows including exact leader/admin approval comments."""
    try:
        actions = [dict(r) for r in c.execute(
            """SELECT a.id,a.action,a.detail,a.created_at,u.full_name AS actor_name
               FROM case_actions a LEFT JOIN users u ON u.id=a.actor_user_id
               WHERE a.case_id=? AND a.action IN ('PLAN_APPROVE','PLAN_REJECT','RESCHEDULE_DECISION','NOTE_EDIT')
               ORDER BY a.created_at DESC,a.id DESC""",
            (int(case_id),),
        ).fetchall()]
    except Exception:
        actions = []

    reschedules = _reschedule_rows(c, case_id)
    has_authoritative_reschedules = bool(reschedules)
    out = list(reschedules)
    seen_plan = False

    for a in actions:
        if a.get("action") == "RESCHEDULE_DECISION" and has_authoritative_reschedules:
            # Avoid duplicate rows: request table is authoritative and contains old/new date + reason.
            continue
        label, change, note = _decode_action(a.get("action"), a.get("detail"))
        if a.get("action") in {"PLAN_APPROVE", "PLAN_REJECT"}:
            seen_plan = True
        out.append(
            {
                "time": a.get("created_at"),
                "action": label,
                "actor": a.get("actor_name") or "—",
                "change": change,
                "comment": note,
                "source": "case_actions",
            }
        )

    # Fallback for old databases if a plan decision predates case_actions history.
    if not seen_plan:
        try:
            row = c.execute(
                """SELECT plan_approval_status,plan_approved_at,plan_rejected_at,approval_note,
                          au.full_name AS approved_name,ru.full_name AS rejected_name
                   FROM customer_work_cases w
                   LEFT JOIN users au ON au.id=w.plan_approved_by
                   LEFT JOIN users ru ON ru.id=w.plan_rejected_by
                   WHERE w.id=?""",
                (int(case_id),),
            ).fetchone()
        except Exception:
            row = None
        if row:
            r = dict(row)
            status = str(r.get("plan_approval_status") or "")
            if status == "APPROVED" and r.get("plan_approved_at"):
                out.append({
                    "time": r.get("plan_approved_at"),
                    "action": "Phê duyệt công việc",
                    "actor": r.get("approved_name") or "—",
                    "change": "Phê duyệt kế hoạch công việc khách hàng",
                    "comment": _comment(r.get("approval_note")),
                    "source": "case_fallback",
                })
            elif status == "REJECTED" and r.get("plan_rejected_at"):
                out.append({
                    "time": r.get("plan_rejected_at"),
                    "action": "Từ chối công việc",
                    "actor": r.get("rejected_name") or "—",
                    "change": "Từ chối kế hoạch công việc khách hàng",
                    "comment": _comment(r.get("approval_note")),
                    "source": "case_fallback",
                })

    out.sort(key=lambda x: str(x.get("time") or ""), reverse=True)
    return out


def _approval_table_rows(get_conn, case_id):
    with get_conn() as c:
        rows = approval_history(c, int(case_id))
    return [
        [
            _dt_text(r.get("time")),
            f"{r.get('action') or '—'} · {r.get('change') or '—'}",
            r.get("actor") or "—",
            r.get("comment") or "Không có ý kiến ghi chú",
        ]
        for r in rows
    ]


def _render_approval_history_inline(st, get_conn, case_id, table_renderer=None):
    """Render directly below the existing stage-history table so comments are not buried."""
    rows = _approval_table_rows(get_conn, case_id)
    if not rows:
        return False
    st.markdown("#### 💬 Phê duyệt / thay đổi của Lãnh đạo/Admin")
    st.caption("Hiển thị đúng ý kiến/Ghi chú được nhập tại thời điểm Lãnh đạo phòng/Admin phê duyệt hoặc từ chối thay đổi.")
    heads = ["Thời điểm", "Nội dung phê duyệt / thay đổi", "Lãnh đạo/Admin", "Ý kiến / Ghi chú"]
    widths = ["16%", "38%", "18%", "28%"]
    if callable(table_renderer):
        table_renderer(st, heads, rows, widths)
    else:
        import pandas as pd
        st.dataframe(
            pd.DataFrame(rows, columns=heads),
            use_container_width=True,
            hide_index=True,
        )
    return True


def _render_manager_note_editor(st, u, get_conn, case_id, logger=None):
    is_manager = str(u.get("role") or "") == "Lãnh đạo phòng" or bool(u.get("is_admin"))
    if not is_manager:
        return
    with get_conn() as c:
        row = c.execute("SELECT note FROM customer_work_cases WHERE id=?", (int(case_id),)).fetchone()
    if not row:
        return
    current = str(row[0] or "")
    st.subheader("Ghi chú công việc")
    st.caption("Lãnh đạo phòng/Admin có thể chỉnh sửa Ghi chú. Mỗi lần lưu đều được ghi vào lịch sử.")
    with st.form(f"cw_manager_note_form_{int(case_id)}", clear_on_submit=False):
        note = st.text_area(
            "Ghi chú",
            value=current,
            height=110,
            key=f"cw_manager_note_value_{int(case_id)}",
        )
        save = st.form_submit_button("💾 Lưu Ghi chú", type="primary", use_container_width=True)
    if save:
        try:
            changed = update_case_note(get_conn, int(case_id), int(u["id"]), note, logger)
            if changed:
                st.toast("Đã cập nhật Ghi chú công việc.", icon="✅")
            else:
                st.toast("Ghi chú không thay đổi.", icon="ℹ️")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


class _HistoryInlineProxy:
    """Insert leader approval comments immediately after the stage history table."""
    def __init__(self, st, get_conn, case_id, table_renderer=None):
        self._st = st
        self._get_conn = get_conn
        self._case_id = int(case_id)
        self._table_renderer = table_renderer
        self._await_stage_table = False
        self.inserted = False

    def __getattr__(self, name):
        return getattr(self._st, name)

    def subheader(self, label, *args, **kwargs):
        result = self._st.subheader(label, *args, **kwargs)
        if str(label).strip() == _STAGE_HISTORY_TITLE:
            self._await_stage_table = True
        return result

    def html(self, body, *args, **kwargs):
        result = self._st.html(body, *args, **kwargs)
        if self._await_stage_table and not self.inserted and "<table" in str(body).lower():
            self._await_stage_table = False
            self.inserted = _render_approval_history_inline(
                self._st,
                self._get_conn,
                self._case_id,
                self._table_renderer,
            )
        return result


class _ApprovalLabelProxy:
    """Keep existing approval renderer but make the comment purpose explicit."""
    def __init__(self, st):
        self._st = st

    def __getattr__(self, name):
        return getattr(self._st, name)

    def text_input(self, label, *args, **kwargs):
        if str(label).strip() == "Ý kiến":
            label = "Ý kiến / Ghi chú của Lãnh đạo/Admin"
        return self._st.text_input(label, *args, **kwargs)


def install(customer_ui, customer_core, logger=None):
    # Deliberately reassert on every call; this patch is installed after all Customer Work render overlays.
    if not hasattr(customer_ui, "_CW_MANAGER_NOTE_BASE_DETAIL"):
        customer_ui._CW_MANAGER_NOTE_BASE_DETAIL = customer_ui._case_detail
    base_detail = customer_ui._CW_MANAGER_NOTE_BASE_DETAIL
    table_renderer = getattr(customer_ui, "_html_table", None)

    def case_detail(st, u, get_conn, case_id, logger=None):
        history_proxy = _HistoryInlineProxy(st, get_conn, case_id, table_renderer)
        result = base_detail(history_proxy, u, get_conn, case_id, logger)
        # Defensive fallback for future renderer changes: still show the approval history once.
        if not history_proxy.inserted:
            _render_approval_history_inline(st, get_conn, case_id, table_renderer)
        _render_manager_note_editor(st, u, get_conn, case_id, logger)
        return result

    customer_ui._case_detail = case_detail

    if not hasattr(customer_ui, "_CW_MANAGER_NOTE_BASE_APPROVALS"):
        customer_ui._CW_MANAGER_NOTE_BASE_APPROVALS = customer_ui.render_approvals_page
    base_approvals = customer_ui._CW_MANAGER_NOTE_BASE_APPROVALS

    def render_approvals_page(st, *args, **kwargs):
        return base_approvals(_ApprovalLabelProxy(st), *args, **kwargs)

    customer_ui.render_approvals_page = render_approvals_page
    customer_core.update_case_note_by_manager = update_case_note
    customer_core.customer_work_approval_history = approval_history
    customer_ui._CUSTOMER_WORK_MANAGER_NOTE_HISTORY_VERSION = VERSION
    if logger:
        logger.info(
            "CUSTOMER_WORK_MANAGER_NOTE_HISTORY_INSTALLED version=%s manager_note_edit=1 note_audit=1 approval_comment_inline_history=1 reschedule_detail=1 approval_label=1 data_migration=0",
            VERSION,
        )
