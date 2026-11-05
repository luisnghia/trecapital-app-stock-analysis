"""Search all Customer Work statuses, with a safe read-only archive detail.

Only the Customer Work list is inclusive of closed records. Operational
dashboards, SLA alerts, Q1-Q4 counts and approval queues remain active-only.
An archived case can never be rendered through the editable case-detail UI.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from html import escape
from pathlib import Path
import json
import re
import sqlite3


CLOSED = frozenset({"COMPLETED", "CANCELLED", "CANCELED"})
STATUS_LABELS = {
    "COMPLETED": "✅ Đã hoàn thành",
    "CANCELLED": "⚫ Đã hủy",
    "CANCELED": "⚫ Đã hủy",
    "ACTIVE": "🟢 Đang thực hiện",
}


def is_closed(case):
    return str((case or {}).get("status") or "").upper() in CLOSED


def status_label(case):
    status = str((case or {}).get("status") or "").upper()
    return STATUS_LABELS.get(status, status or "—")


def _dt(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def _stamp(value):
    try:
        value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (value.year * 10000000000 + value.month * 100000000
                + value.day * 1000000 + value.hour * 10000
                + value.minute * 100 + value.second)
    except (TypeError, ValueError):
        return 0


def sort_cases(rows, core):
    """Current work before completed/cancelled; preserve existing active priority.

    Historical items display newest close/update first, rather than being
    promoted to the urgent queue by an old, already expired due date.
    """
    def due_key(x):
        return core.parse_dt(x.get("expected_complete_at")) or datetime.max

    def key(x):
        if is_closed(x):
            return (1, -_stamp(x.get("completed_at") or x.get("updated_at")
                               or x.get("created_at")), -int(x.get("id") or 0))
        try:
            quadrant = int(x.get("quadrant") or 4)
        except (TypeError, ValueError):
            quadrant = 4
        return (
            0, quadrant, 0 if x.get("is_overdue") else 1,
            0 if x.get("is_stage_delayed") else 1,
            -int(x.get("open_issue_count") or 0), due_key(x),
            int(x.get("id") or 0),
        )
    return sorted(rows, key=key)


def _html_table(st, headers, rows):
    h = "".join(f"<th>{escape(str(x), quote=True)}</th>" for x in headers)
    if not rows:
        st.caption("Chưa có dữ liệu lịch sử.")
        return
    b = "".join("<tr>" + "".join(
        f"<td>{escape(str('—' if x is None or x == '' else x), quote=True)}</td>"
        for x in row
    ) + "</tr>" for row in rows)
    min_width = max(690, len(headers) * 148)
    st.html(
        f'<div class="cwarch-wrap"><table class="cwarch-table" style="min-width:{min_width}px"><thead><tr>'
        + h + '</tr></thead><tbody>' + b + '</tbody></table></div>'
        + """<style>
        .cwarch-wrap{overflow-x:auto;max-width:100%;margin:6px 0 18px}
        .cwarch-table{border-collapse:collapse;width:100%;min-width:690px;table-layout:fixed}
        .cwarch-table th,.cwarch-table td{border:1px solid rgba(148,200,189,.3);
          padding:9px 10px;text-align:left;vertical-align:top;white-space:pre-wrap;
          overflow-wrap:anywhere;line-height:1.42;font-size:.81rem}
        .cwarch-table th{color:#63DCCB;background:#173C37;font-weight:800}
        .cwarch-table td{background:#112B29;color:#E1F4ED}
        </style>"""
    )


def _read_only_connection(get_conn):
    """Open an independent SQLite read-only handle without changing pool flags."""
    with get_conn() as source:
        row = source.execute("PRAGMA database_list").fetchone()
        filename = str(row[2] or "") if row else ""
    if not filename:
        raise RuntimeError("Không xác định được đường dẫn dữ liệu lịch sử.")
    uri = Path(filename).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def load_archive(get_conn, core, case_id, user, manager):
    """Check case ownership before reading any private notes or history."""
    uid = int(user["id"])
    cid = int(case_id)
    with closing(_read_only_connection(get_conn)) as c:
        item = core.get_case(c, cid)
        if not item or not is_closed(item):
            raise PermissionError("Công việc này không thuộc lịch sử đã kết thúc.")
        if not manager and int(item.get("owner_user_id") or 0) != uid:
            raise PermissionError("Bạn không có quyền xem lịch sử công việc này.")
        history = core.case_history(c, cid)
        issues = core.case_issues(c, cid, include_resolved=True)
        from khdn_apps.customer_work_manager_note_history_patch import approval_history
        approvals = approval_history(c, cid)
        reschedules = [dict(r) for r in c.execute(
            """SELECT r.*,u.full_name AS requested_by_name
               FROM case_reschedule_requests r
               LEFT JOIN users u ON u.id=r.requested_by
               WHERE r.case_id=? ORDER BY r.requested_at DESC,r.id DESC""",
            (cid,),
        ).fetchall()]
    return item, history, issues, approvals, reschedules



def _present_user(name, user_id):
    """Historical users may have been renamed/deactivated/deleted."""
    value = str(name or "").strip()
    return value or (f"Người dùng #{user_id} (không còn tên hiển thị)" if user_id else "Chưa ghi nhận")


def _cancel_status(status):
    return {
        "PENDING": "Đang chờ phê duyệt",
        "APPROVED": "Đã phê duyệt hủy",
        "REJECTED": "Đã từ chối hủy",
    }.get(str(status or "").upper(), str(status or "—"))


def _closure_summary(case, cancel_requests, actor_name):
    """Prefer canonical cancellation fields; use an APPROVED request only as fallback."""
    approved = next(
        (x for x in reversed(cancel_requests)
         if str(x.get("status") or "").upper() == "APPROVED"), None
    ) or {}
    reason = str(case.get("cancel_reason") or "").strip() or str(approved.get("reason") or "").strip()
    approver = actor_name or _present_user(approved.get("decider_name"), approved.get("decided_by"))
    cancelled_at = case.get("cancelled_at") or approved.get("decided_at")
    return [
        ("Lý do hủy", reason or "Chưa có dữ liệu lý do hủy trong hồ sơ"),
        ("Người đề nghị hủy",
         _present_user(approved.get("requester_name"), approved.get("requested_by"))
         if approved else "Chưa ghi nhận"),
        ("Ngày đề nghị hủy", _dt(approved.get("requested_at"))),
        ("Người phê duyệt hủy", approver),
        ("Ngày phê duyệt hủy", _dt(cancelled_at)),
        ("Ý kiến khi phê duyệt", approved.get("decision_note") or "Không có ý kiến ghi chú"),
    ]


def _event_description(row, request_by_id, stages):
    """Decode persisted case_actions without inventing missing approval comments."""
    action = str(row.get("action") or "")
    raw = str(row.get("detail") or "")
    parsed = None
    try:
        parsed = json.loads(raw) if raw.strip() else None
    except (ValueError, TypeError):
        pass
    if action == "CASE_ASSIGNMENT_UPDATE" and isinstance(parsed, dict):
        old_owner = parsed.get("old_owner_name") or "—"
        new_owner = parsed.get("new_owner_name") or "—"
        old_leader = parsed.get("old_controller_name") or "Chưa gán"
        new_leader = parsed.get("new_controller_name") or "—"
        why = parsed.get("reason") or "Không có lý do"
        return (
            "Điều chỉnh phân công công việc",
            f"Cán bộ phụ trách: {old_owner} → {new_owner} · "
            f"Lãnh đạo kiểm soát: {old_leader} → {new_leader} · Lý do: {why}",
        )
    if action.startswith("CANCEL_") and action.endswith("_P12"):
        m = re.fullmatch(r"request_id=(\d+)", raw.strip())
        req = request_by_id.get(int(m.group(1))) if m else None
        names = {
            "CANCEL_REQUEST_P12": "Gửi đề nghị hủy",
            "CANCEL_APPROVE_P12": "Phê duyệt hủy công việc",
            "CANCEL_REJECT_P12": "Từ chối đề nghị hủy",
        }
        details = []
        if req:
            if req.get("reason"):
                details.append(f"Lý do đề nghị: {req['reason']}")
            if action != "CANCEL_REQUEST_P12" and req.get("decision_note"):
                details.append(f"Ý kiến quyết định: {req['decision_note']}")
        else:
            details.append("Chưa tìm thấy bản ghi đề nghị hủy liên quan")
        return names.get(action, action), " · ".join(details)

    labels = {
        "CREATE": "Tạo công việc",
        "CREATE_METADATA": "Bổ sung thông tin công việc",
        "PLAN_APPROVE": "Phê duyệt kế hoạch công việc",
        "PLAN_REJECT": "Từ chối kế hoạch công việc",
        "STAGE_CHANGE": "Chuyển mục xử lý",
        "ISSUE_OPEN": "Ghi nhận vướng mắc",
        "ISSUE_RESOLVE": "Xử lý vướng mắc",
        "RESCHEDULE_REQUEST": "Đề nghị dời thời gian",
        "RESCHEDULE_DECISION": "Quyết định dời thời gian",
        "PRIORITY_SET": "Điều chỉnh mức ưu tiên",
        "NOTE_EDIT": "Chỉnh sửa ghi chú",
    }
    label = labels.get(action, action or "Thao tác")
    if action in {"PLAN_APPROVE", "PLAN_REJECT", "ISSUE_OPEN", "ISSUE_RESOLVE"}:
        return label, str(parsed.get("note") or "") if isinstance(parsed, dict) else raw
    if isinstance(parsed, dict):
        descriptions = []
        fields = {
            "stage_id": "Mục công việc",
            "note": "Ghi chú",
            "reason": "Lý do",
            "resolution": "Kết quả xử lý",
            "status": "Trạng thái",
            "proposed": "Thời hạn đề xuất",
            "new_note": "Ghi chú mới",
            "old_note": "Ghi chú trước",
            "manager_comment": "Ý kiến Lãnh đạo",
            "contact_name": "Người liên hệ",
            "contact_phone": "Số điện thoại",
            "contact_role": "Chức vụ",
            "priority_quadrant": "Góc phần tư",
            "category_id": "Danh mục ưu tiên",
            "urgent_override": "Khẩn cấp",
            "owner_user_id": "Mã cán bộ phụ trách",
            "approval": "Trạng thái phê duyệt",
        }
        for k,v in parsed.items():
            if v is None or v == "":
                continue
            if k == "stage_id":
                v = stages.get(str(v), v)
            descriptions.append(f"{fields.get(k, str(k))}: {v}")
        return label, " · ".join(descriptions)
    return label, raw


def load_archived_audit(get_conn, core, case_id, user, manager):
    """Read cancellation decisions + full actions only after rechecking access.

    Existing load_archive() five-tuple API is unchanged. A second SQLite RO
    connection is used only for the two additional history sections.
    """
    cid = int(case_id)
    uid = int(user["id"])
    with closing(_read_only_connection(get_conn)) as c:
        case = core.get_case(c, cid)
        if not case or not is_closed(case):
            raise PermissionError("Công việc không còn thuộc danh sách lịch sử.")
        if not manager and int(case.get("owner_user_id") or 0) != uid:
            raise PermissionError("Bạn không có quyền xem lịch sử công việc này.")
        has_cancel = bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='customer_work_cancel_requests'"
        ).fetchone())
        requests = []
        if has_cancel:
            requests = [dict(r) for r in c.execute(
                """SELECT r.*,req.full_name AS requester_name,
                          dec.full_name AS decider_name
                   FROM customer_work_cancel_requests r
                   LEFT JOIN users req ON req.id=r.requested_by
                   LEFT JOIN users dec ON dec.id=r.decided_by
                   WHERE r.case_id=?
                   ORDER BY r.requested_at,r.id""",
                (cid,),
            ).fetchall()]
        actor = None
        if case.get("cancelled_by"):
            record = c.execute("SELECT full_name FROM users WHERE id=?", (case["cancelled_by"],)).fetchone()
            actor = str(record[0] or "") if record else None
        actor_name = _present_user(actor, case.get("cancelled_by")) if case.get("cancelled_by") else None
        has_actions = bool(c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='case_actions'"
        ).fetchone())
        action_rows = []
        if has_actions:
            action_rows = [dict(r) for r in c.execute(
                """SELECT a.*,u.full_name AS actor_name
                   FROM case_actions a
                   LEFT JOIN users u ON u.id=a.actor_user_id
                   WHERE a.case_id=?
                   ORDER BY a.created_at,a.id""",
                (cid,),
            ).fetchall()]
        stages = {str(r[0]):r[1] for r in c.execute(
            "SELECT id,name FROM work_stage_catalog"
        ).fetchall()}
    indexed = {int(r["id"]):r for r in requests}
    actions = []
    for row in action_rows:
        label, detail = _event_description(row, indexed, stages)
        actions.append({
            "time": row.get("created_at"),
            "actor": _present_user(row.get("actor_name"),row.get("actor_user_id")),
            "label":label,
            "detail":detail,
        })
    return case, requests, actor_name, actions


def render_archive(st, user, get_conn, core, case_id, manager, logger=None):
    """Archived cases use no mutation widgets, regardless of user privileges."""
    try:
        case, history, issues, approvals, reschedules = load_archive(
            get_conn, core, case_id, user, manager
        )
    except PermissionError as exc:
        st.error(str(exc))
        st.session_state.pop("cw_case_id", None)
        return
    except (sqlite3.Error, ValueError) as exc:
        st.error(f"Không thể đọc lịch sử công việc: {exc}")
        return

    # Cancellation history exists in a separate P12 table: it is not part of
    # the generic case approval history shown below.
    try:
        archive_case, cancel_requests, cancelled_by_name, full_actions = load_archived_audit(
            get_conn, core, case_id, user, manager
        )
    except PermissionError as exc:
        st.error(str(exc))
        st.session_state.pop("cw_case_id", None)
        return
    except (sqlite3.Error, ValueError) as exc:
        st.error(f"Không thể đọc nhật ký công việc: {exc}")
        return

    if st.button("← Danh sách công việc", key="cw_back_list"):
        st.session_state.pop("cw_case_id", None)
        st.rerun()
        return

    st.subheader(f"📚 Lịch sử công việc · {status_label(case)}")
    st.caption("Hồ sơ đã kết thúc: chỉ xem thông tin và lịch sử, không chỉnh sửa, không phê duyệt.")
    if str(case.get("status") or "").upper() in {"CANCELLED", "CANCELED"}:
        st.subheader("🗑 Nguyên nhân và quyết định hủy công việc")
        summary = _closure_summary(archive_case, cancel_requests, cancelled_by_name)
        _html_table(st, ["Thông tin hủy", "Nội dung"], summary)
        if not archive_case.get("cancel_reason") and not any(
            r.get("reason") for r in cancel_requests if str(r.get("status") or "").upper() == "APPROVED"
        ):
            st.warning("Chưa có dữ liệu lý do hủy được lưu cho hồ sơ này; hệ thống không tự suy đoán.")
        st.subheader("📑 Toàn bộ đề nghị hủy và kết quả xử lý")
        _html_table(st, ["Đề nghị lúc", "Người đề nghị", "Lý do đề nghị",
                          "Kết quả", "Người quyết định", "Quyết định lúc", "Ý kiến"], [
            (_dt(r.get("requested_at")), _present_user(r.get("requester_name"), r.get("requested_by")),
             r.get("reason"), _cancel_status(r.get("status")),
             _present_user(r.get("decider_name"), r.get("decided_by")),
             _dt(r.get("decided_at")), r.get("decision_note") or "Không có ý kiến ghi chú")
            for r in cancel_requests
        ])
    elif str(case.get("status") or "").upper() == "COMPLETED":
        st.subheader("✅ Kết quả kết thúc công việc")
        _html_table(st, ["Thông tin", "Nội dung"], [
            ("Thời gian hoàn thành", _dt(case.get("completed_at"))),
            ("Mục công việc cuối cùng", case.get("stage_name")),
        ])
    st.subheader("🧾 Nhật ký toàn bộ thao tác")
    st.caption("Diễn biến từ lúc tạo công việc đến khi kết thúc, theo trình tự thời gian.")
    _html_table(st, ["Thời điểm", "Người thực hiện", "Hành động", "Nội dung / ghi chú"], [
        (_dt(r.get("time")), r.get("actor"), r.get("label"), r.get("detail"))
        for r in full_actions
    ])
    st.subheader("📌 Thông tin hồ sơ")
    _html_table(st, ["Thông tin", "Nội dung"], [
        ("Khách hàng", case.get("customer_name")),
        ("CIF", case.get("cif")),
        ("Mã công việc", case.get("case_code")),
        ("Nhóm công việc", case.get("case_type")),
        ("Công việc", case.get("title")),
        ("Trạng thái", status_label(case)),
        ("Cán bộ phụ trách", case.get("owner_name")),
        ("Mục cuối cùng", case.get("stage_name")),
        ("Ngày tạo", _dt(case.get("created_at"))),
        ("Dự kiến hoàn thành", _dt(case.get("expected_complete_at"))),
        ("Hoàn thành / Cập nhật cuối", _dt(case.get("completed_at") or case.get("updated_at"))),
        ("Ghi chú công việc", case.get("note")),
        ("Ghi chú phê duyệt", case.get("approval_note")),
    ])
    contacts = []
    for prefix in ("contact", "contact2", "contact3"):
        name = case.get(prefix + "_name")
        role = case.get(prefix + "_role")
        phone = case.get(prefix + "_phone")
        if name or role or phone:
            contacts.append((name, role, phone))
    if contacts:
        st.subheader("☎ Liên hệ khách hàng")
        _html_table(st, ["Họ tên", "Chức vụ", "Số điện thoại"], contacts)

    st.subheader("📋 Lịch sử mục công việc")
    _html_table(st, ["Mục", "Bắt đầu", "Kết thúc", "Người cập nhật", "Ghi chú"], [
        (x.get("stage_name"), _dt(x.get("started_at")), _dt(x.get("ended_at")),
         x.get("actor_name"), x.get("note"))
        for x in history
    ])

    st.subheader("⚠ Lịch sử vướng mắc")
    _html_table(st, ["Vướng mắc", "Mức độ", "Thời điểm", "Trạng thái", "Kết quả xử lý"], [
        (x.get("issue_text"), core.SEVERITY_LABEL.get(x.get("severity"), x.get("severity")),
         _dt(x.get("opened_at")), "Đã xử lý" if x.get("resolved_at") else "Chưa xử lý",
         x.get("resolution_text"))
        for x in issues
    ])

    st.subheader("💬 Phê duyệt / thay đổi của Lãnh đạo/Admin")
    _html_table(st, ["Thời điểm", "Nội dung", "Người thực hiện", "Ý kiến / Ghi chú"], [
        (x.get("time"), f"{x.get('action') or '—'} · {x.get('change') or '—'}",
         x.get("actor"), x.get("comment"))
        for x in approvals
    ])

    if reschedules:
        st.subheader("🕒 Lịch sử đề nghị dời hạn")
        _html_table(st, ["Thời gian đề nghị", "Hạn cũ", "Hạn đề nghị",
                         "Người đề nghị", "Lý do", "Kết quả", "Ý kiến"], [
            (_dt(x.get("requested_at")), _dt(x.get("old_due_at")),
             _dt(x.get("proposed_due_at")), x.get("requested_by_name"),
             x.get("reason"), x.get("status"), x.get("decision_note"))
            for x in reschedules
        ])

    if logger:
        logger.info(
            "CUSTOMER_WORK_ARCHIVE_READ user_id=%s case_id=%s status=%s stage_rows=%s issues=%s cancel_requests=%s audit_actions=%s",
            user.get("id"), case_id, case.get("status"), len(history), len(issues), len(cancel_requests), len(full_actions),
        )
