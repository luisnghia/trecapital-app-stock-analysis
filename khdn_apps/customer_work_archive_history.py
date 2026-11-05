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
    st.html(
        '<div class="cwarch-wrap"><table class="cwarch-table"><thead><tr>'
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

    if st.button("← Danh sách công việc", key="cw_back_list"):
        st.session_state.pop("cw_case_id", None)
        st.rerun()
        return

    st.subheader(f"📚 Lịch sử công việc · {status_label(case)}")
    st.caption("Hồ sơ đã kết thúc: chỉ xem thông tin và lịch sử, không chỉnh sửa, không phê duyệt.")
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
            "CUSTOMER_WORK_ARCHIVE_READ user_id=%s case_id=%s status=%s stage_rows=%s issues=%s",
            user.get("id"), case_id, case.get("status"), len(history), len(issues),
        )
