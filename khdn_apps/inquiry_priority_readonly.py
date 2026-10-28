"""Read-only quadrant cards and case details for the isolated Vấn tin route.

The standard manager detail page includes write widgets and must NEVER be used
by inquiry accounts. All detail reads are opened with SQLite mode=ro and
PRAGMA query_only=ON, and case IDs are checked against the currently authorized
room list before any data is loaded. No calls to normal case-detail or case
mutation handlers exist here.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from html import escape
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from khdn_apps import customer_work as core
from khdn_apps import priority_today_patch as priority


SELECTED_KEY = "_inquiry_priority_case_id"


def _esc(value):
    return escape("—" if value is None or value == "" else str(value), quote=True)


def _date(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return str(value)


def _valid_id(value, cases):
    """Fail closed on forged/stale selections and completed or vanished cases."""
    try:
        case_id = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return case_id if case_id > 0 and case_id in {
        int(x["id"]) for x in cases if x.get("id") is not None
    } else None


def _load_detail(db_path, case_id, cases):
    """Read a selected *current* room case and related history; never mutate."""
    selected = _valid_id(case_id, cases)
    if selected is None:
        raise PermissionError("Công việc này không thuộc danh sách được xem.")
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=15)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        item = core.get_case(conn, selected)
        if not item or str(item.get("status") or "") == "COMPLETED":
            raise PermissionError("Công việc không còn trong danh sách được xem.")
        history = core.case_history(conn, selected)
        issues = core.case_issues(conn, selected, include_resolved=True)

        # Shared customer contact directory, when the installed schema has it.
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='customer_contact_master'"
        ).fetchone()
        contacts = []
        if exists and item.get("customer_id") is not None:
            contacts = [dict(r) for r in conn.execute(
                """SELECT slot,contact_name,contact_phone,contact_role
                   FROM customer_contact_master WHERE customer_id=?
                   ORDER BY slot""", (int(item["customer_id"]),)
            ).fetchall()]
        if not contacts:
            # Older installations may only have contact snapshots on cases.
            for prefix in ("contact", "contact2", "contact3"):
                name = str(item.get(prefix + "_name") or "").strip()
                phone = str(item.get(prefix + "_phone") or "").strip()
                role = str(item.get(prefix + "_role") or "").strip()
                if name or phone or role:
                    contacts.append({
                        "contact_name": name, "contact_phone": phone,
                        "contact_role": role,
                    })

        moves = [dict(r) for r in conn.execute(
            """SELECT r.old_due_at,r.proposed_due_at,r.reason,r.requested_at,
                      r.status,r.decided_at,r.decision_note,
                      u.full_name AS requester_name
               FROM case_reschedule_requests r
               LEFT JOIN users u ON u.id=r.requested_by
               WHERE r.case_id=? ORDER BY r.requested_at DESC,r.id DESC""",
            (selected,)
        ).fetchall()]
    return item, history, issues, contacts, moves


def _status(case):
    if case.get("is_overdue"):
        return "🔴 Quá hạn"
    if case.get("is_stage_delayed"):
        return "🔴 Mục bị chậm"
    if case.get("is_stage_warning"):
        return "🟠 Sắp chậm"
    if int(case.get("open_issue_count") or 0):
        return "⚠ Có vướng mắc"
    return "🟢 Trong hạn"


def _readable_card(case):
    """Escape all data-bearing text before placing it in HTML."""
    q = priority._quadrant(case)
    theme = priority._HEAT[q]
    ctype = str(case.get("case_type") or "Công việc")
    title = str(case.get("title") or "")
    subtitle = "" if not title or title.casefold() == ctype.casefold() else (
        f"<div class='iq-work'>📌 {_esc(title)}</div>"
    )
    note = str(case.get("note") or "").strip()
    note_html = f"<div class='iq-note'>📝 <b>Ghi chú:</b> {_esc(note)}</div>" if note else ""
    return f"""<article class="iq-card" style="--iq-accent:{theme['accent']};--iq-bg:{theme['bg']};">
      <div class="iq-top"><strong>{_esc(case.get('customer_name'))} · {_esc(ctype)}</strong>
        <small>{_esc(case.get('case_code'))}</small></div>
      {subtitle}
      <div class="iq-meta">👤 {_esc(case.get('owner_name'))} · 📍 {_esc(case.get('stage_name'))}
         · ⏱ {_esc(core.duration_text(case.get('stage_elapsed_hours')))}</div>
      <div class="iq-meta">🎯 Dự kiến: {_esc(_date(case.get('expected_complete_at')))}
         · {_esc(_status(case))} · ⚠ Vướng mắc: {int(case.get('open_issue_count') or 0)}</div>
      {note_html}
    </article>
    <style>
    .iq-card{{border:1px solid rgba(127,180,170,.40);border-left:6px solid var(--iq-accent);
      border-radius:12px;background:var(--iq-bg);padding:10px 12px;margin:7px 0 5px;
      white-space:normal;overflow-wrap:anywhere}}
    .iq-top{{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}
    .iq-top strong{{font-size:.90rem;line-height:1.35;color:#63DCCB}}
    .iq-top small{{font-size:.75rem;font-weight:850;color:#F4B41A}}
    .iq-work,.iq-meta,.iq-note{{font-size:.82rem;line-height:1.5;margin-top:5px}}
    .iq-note{{padding:6px 9px;border-left:3px solid #63DCCB;background:rgba(99,220,203,.07);
      white-space:pre-wrap;overflow-wrap:anywhere}}
    </style>"""


def _readonly_table(st, headers, rows):
    head = "".join(f"<th>{_esc(v)}</th>" for v in headers)
    body = "".join("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    st.html(f"""<div class="iq-table-wrap"><table class="iq-table"><thead><tr>{head}</tr></thead>
        <tbody>{body}</tbody></table></div>
      <style>.iq-table-wrap{{overflow-x:auto;max-width:100%;margin:8px 0 16px}}
      .iq-table{{border-collapse:collapse;min-width:630px;width:100%;table-layout:auto}}
      .iq-table td,.iq-table th{{border:1px solid rgba(120,160,150,.35);padding:8px 10px;
          vertical-align:top;overflow-wrap:anywhere;white-space:pre-wrap;font-size:.78rem}}
      .iq-table th{{color:#63DCCB;font-weight:800}}</style>""")


def render_detail(st, db_path, case_id, cases, logger=None):
    """Dedicated read-only detail UI. No standard editable case screen is used."""
    item, history, issues, contacts, moves = _load_detail(db_path, case_id, cases)
    st.subheader("🔎 Chi tiết công việc · chỉ xem")
    st.caption("Thông tin mới nhất của công việc và lịch sử xử lý. Không có quyền chỉnh sửa hoặc phê duyệt.")
    st.html(_readable_card(item))
    _readonly_table(st, ["Thông tin", "Nội dung"], [
        ("Khách hàng", item.get("customer_name")),
        ("CIF", item.get("cif")),
        ("Công việc", item.get("title")),
        ("Loại công việc", item.get("case_type")),
        ("Cán bộ phụ trách", item.get("owner_name")),
        ("Mục hiện tại", item.get("stage_name")),
        ("Trạng thái", item.get("status")),
        ("Phê duyệt kế hoạch", item.get("plan_approval_status")),
        ("Ưu tiên", core.quadrant_label(priority._quadrant(item))),
        ("Danh mục công việc quan trọng", item.get("important_category")),
        ("Tạo lúc", _date(item.get("created_at"))),
        ("Dự kiến hoàn thành", _date(item.get("expected_complete_at"))),
        ("Bắt đầu mục hiện tại", _date(item.get("stage_started_at"))),
        ("Hoàn thành lúc", _date(item.get("completed_at"))),
        ("Ghi chú công việc", item.get("note")),
    ])
    if contacts:
        st.subheader("📞 Liên hệ khách hàng")
        _readonly_table(st, ["Họ tên", "Chức vụ", "Số điện thoại"], [
            (x.get("contact_name"), x.get("contact_role"), x.get("contact_phone"))
            for x in contacts
        ])
    st.subheader("📋 Lịch sử mục công việc")
    if history:
        _readonly_table(st, ["Mục công việc", "Bắt đầu", "Kết thúc", "Người cập nhật", "Ghi chú"], [
            (x.get("stage_name"), _date(x.get("started_at")), _date(x.get("ended_at")),
             x.get("actor_name"), x.get("note"))
            for x in history
        ])
    else:
        st.caption("Chưa có lịch sử chuyển mục công việc.")
    st.subheader("⚠ Lịch sử vướng mắc")
    if issues:
        _readonly_table(st, ["Nội dung", "Mức độ", "Thời điểm", "Trạng thái / Xử lý"], [
            (x.get("issue_text"),
             core.SEVERITY_LABEL.get(x.get("severity"), x.get("severity")),
             _date(x.get("opened_at")),
             ("Đã xử lý " + _date(x.get("resolved_at")) + " · " + str(x.get("resolution_text") or ""))
             if x.get("resolved_at") else "Đang mở")
            for x in issues
        ])
    else:
        st.caption("Không có vướng mắc.")
    if moves:
        st.subheader("🕒 Lịch sử đề nghị dời hạn")
        _readonly_table(st, ["Đề nghị", "Từ ngày", "Đến ngày", "Lý do", "Trạng thái"], [
            (_date(x.get("requested_at")), _date(x.get("old_due_at")),
             _date(x.get("proposed_due_at")), x.get("reason"), x.get("status"))
            for x in moves
        ])
    if logger:
        logger.info("INQUIRY_PRIORITY_DETAIL_READONLY case_id=%s history=%s issues=%s",
                    item.get("id"), len(history), len(issues))


def render_quadrants(st, cases, logger=None):
    """Same four quadrants, order and work counts as the manager dashboard."""
    st.subheader("🔥 Góc phần tư ưu tiên · toàn phòng")
    st.caption("Chọn 🔎 Chi tiết để xem công việc, lịch sử xử lý và vướng mắc. Chỉ được xem.")
    ordered = sorted(cases, key=lambda x: priority._priority_sort_key(core, x))
    priority._heat_summary(st, SimpleNamespace(core=core), ordered)
    from khdn_apps.interaction_performance import page_rows
    for q in range(1, 5):
        info = priority._HEAT[q]
        matches = [x for x in ordered if priority._quadrant(x) == q]
        with st.expander(
            f"{info['icon']} {core.quadrant_label(q)} · {len(matches)} công việc",
            expanded=(q in (1, 2) and bool(matches)),
        ):
            if not matches:
                st.caption("Không có công việc trong nhóm ưu tiên này.")
                continue
            for x in page_rows(st, matches, f"inquiry_room_priority_{q}"):
                st.html(_readable_card(x))
                if st.button("🔎 Chi tiết", key=f"inquiry_priority_open_{int(x['id'])}",
                             use_container_width=True):
                    st.session_state[SELECTED_KEY] = int(x["id"])
                    if logger:
                        logger.info("INQUIRY_PRIORITY_OPEN case_id=%s", x["id"])
                    st.rerun()
                    return
