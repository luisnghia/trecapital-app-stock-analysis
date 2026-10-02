"""Manager/Admin note editing and approval-comment history for Customer Work.

Business rules:
- only active Lãnh đạo phòng/Admin may edit the persisted customer_work_cases.note;
- note edits never change Customer ID, workflow state, stage, due date or priority;
- every note edit is appended to case_actions for auditability;
- Customer Work detail shows approval/change decisions together with the
  Lãnh đạo/Admin comment that was recorded at approval time;
- approval inputs are labelled explicitly as the leader/admin comment.
"""
from __future__ import annotations

import json
from datetime import datetime

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_WORK_MANAGER_NOTE_HISTORY_VERSION"


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


def _decode_detail(action, detail):
    """Return (status/description, leader comment) for legacy and JSON actions."""
    raw = "" if detail is None else str(detail)
    payload = None
    try:
        payload = json.loads(raw) if raw.strip() else None
    except Exception:
        payload = None

    action = str(action or "")
    if action == "PLAN_APPROVE":
        note = payload.get("note") if isinstance(payload, dict) else raw
        return "Phê duyệt công việc", str(note or "").strip()
    if action == "PLAN_REJECT":
        note = payload.get("note") if isinstance(payload, dict) else raw
        return "Từ chối công việc", str(note or "").strip()
    if action == "RESCHEDULE_DECISION":
        if isinstance(payload, dict):
            status = str(payload.get("status") or "").upper()
            note = payload.get("note")
        else:
            status, note = "", raw
        label = "Phê duyệt dời thời gian" if status == "APPROVED" else (
            "Từ chối dời thời gian" if status == "REJECTED" else "Quyết định dời thời gian"
        )
        return label, str(note or "").strip()
    if action == "NOTE_EDIT":
        if isinstance(payload, dict):
            note = payload.get("new_note")
        else:
            note = raw
        return "Chỉnh sửa Ghi chú công việc", str(note or "").strip()
    return action, raw.strip()


def approval_history(c, case_id):
    """Decision/audit rows including the leader/admin comment recorded at the time."""
    actions = [dict(r) for r in c.execute(
        """SELECT a.id,a.action,a.detail,a.created_at,u.full_name AS actor_name
           FROM case_actions a LEFT JOIN users u ON u.id=a.actor_user_id
           WHERE a.case_id=? AND a.action IN ('PLAN_APPROVE','PLAN_REJECT','RESCHEDULE_DECISION','NOTE_EDIT')
           ORDER BY a.created_at DESC,a.id DESC""",
        (int(case_id),),
    ).fetchall()]
    out = []
    seen_plan = False
    for a in actions:
        label, note = _decode_detail(a.get("action"), a.get("detail"))
        if a.get("action") in {"PLAN_APPROVE", "PLAN_REJECT"}:
            seen_plan = True
        out.append(
            {
                "time": a.get("created_at"),
                "action": label,
                "actor": a.get("actor_name") or "—",
                "comment": note or "—",
            }
        )

    # Fallback for old databases if a plan decision predates case_actions history.
    if not seen_plan:
        row = c.execute(
            """SELECT plan_approval_status,plan_approved_at,plan_rejected_at,approval_note,
                      au.full_name AS approved_name,ru.full_name AS rejected_name
               FROM customer_work_cases w
               LEFT JOIN users au ON au.id=w.plan_approved_by
               LEFT JOIN users ru ON ru.id=w.plan_rejected_by
               WHERE w.id=?""",
            (int(case_id),),
        ).fetchone()
        if row:
            r = dict(row)
            status = str(r.get("plan_approval_status") or "")
            if status == "APPROVED" and r.get("plan_approved_at"):
                out.append({
                    "time": r.get("plan_approved_at"), "action": "Phê duyệt công việc",
                    "actor": r.get("approved_name") or "—", "comment": r.get("approval_note") or "—",
                })
            elif status == "REJECTED" and r.get("plan_rejected_at"):
                out.append({
                    "time": r.get("plan_rejected_at"), "action": "Từ chối công việc",
                    "actor": r.get("rejected_name") or "—", "comment": r.get("approval_note") or "—",
                })

    out.sort(key=lambda x: str(x.get("time") or ""), reverse=True)
    return out


def _dt_text(v):
    if not v:
        return "—"
    try:
        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(v)


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


def _render_approval_history(st, get_conn, case_id):
    with get_conn() as c:
        rows = approval_history(c, int(case_id))
    st.subheader("Lịch sử phê duyệt / thay đổi")
    if not rows:
        st.caption("Chưa có lịch sử phê duyệt hoặc chỉnh sửa Ghi chú.")
        return
    table = [
        [_dt_text(r.get("time")), r.get("action") or "—", r.get("actor") or "—", r.get("comment") or "—"]
        for r in rows
    ]
    # Use static HTML table helper from canonical UI when available; caller falls back otherwise.
    return table


class _ApprovalLabelProxy:
    """Keep the existing approval renderer but make the comment purpose explicit."""
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

    def case_detail(st, u, get_conn, case_id, logger=None):
        result = base_detail(st, u, get_conn, case_id, logger)
        _render_manager_note_editor(st, u, get_conn, case_id, logger)
        rows = _render_approval_history(st, get_conn, case_id)
        if rows:
            if hasattr(customer_ui, "_html_table"):
                customer_ui._html_table(
                    st,
                    ["Thời điểm", "Nội dung", "Lãnh đạo/Admin", "Ý kiến / Ghi chú phê duyệt"],
                    rows,
                    ["18%", "24%", "20%", "38%"],
                )
            else:
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(rows, columns=["Thời điểm", "Nội dung", "Lãnh đạo/Admin", "Ý kiến / Ghi chú phê duyệt"]),
                    use_container_width=True,
                    hide_index=True,
                )
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
            "CUSTOMER_WORK_MANAGER_NOTE_HISTORY_INSTALLED version=%s manager_note_edit=1 note_audit=1 approval_comment_history=1 approval_label=1 data_migration=0",
            VERSION,
        )
