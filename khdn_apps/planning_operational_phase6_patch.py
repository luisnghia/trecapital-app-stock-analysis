"""Operational planning Phase 6 final corrections.

Fixes:
- final six-tab Admin-only System Admin navigation;
- strict Customer Work approval scope by the selected controlling leader;
- compact yellow in-card Detail / Progress actions;
- human-readable weekly classification history;
- unique weekday quick-add keys across staff plans in the room dashboard.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import html
import json
import sqlite3

from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase3_weekly as p3week
from khdn_apps import planning_operational_phase4_patch as p4
from khdn_apps import planning_operational_phase5_patch as p5
from khdn_apps import planning_room_dashboard_detail_patch as room_dashboard
from khdn_apps import planning_ui_admin_hotfix as admin_hotfix
from khdn_apps import worktype_contact_card_patch as worktype

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE6_VERSION"

_ADMIN_OPTIONS = [
    ("users", "👥 Người dùng"),
    ("customers", "🏢 Khách hàng CIF"),
    ("types", "🧩 Loại công việc"),
    ("reasons", "🧩 Nhóm nguyên nhân tác nghiệp"),
    ("audit", "🧾 Audit"),
    ("backup", "💾 Sao lưu"),
]

_Q_LABEL = {
    1: "Q1 · Cấp thiết",
    2: "Q2 · Trọng tâm",
    3: "Q3 · Phân tâm",
    4: "Q4 · Giá trị thấp",
}


def _fmt_action(action, detail):
    """Never expose raw JSON in the weekly progress history."""
    action = str(action or "")
    labels = {
        "EXEC_UPDATE_PHASE3": "Cập nhật tiến độ",
        "EXEC_UPDATE_PHASE2": "Cập nhật tiến độ",
        "EXEC_UPDATE": "Cập nhật tiến độ",
        "RESCHEDULE_APPROVE": "Dời lịch được duyệt",
        "RESCHEDULE_REJECT": "Dời lịch bị từ chối",
        "PHAT_SINH": "Công việc phát sinh",
        "CLASSIFICATION_CHANGE": "Điều chỉnh phân loại",
        "DRAFT_REMOVE": "Bỏ khỏi bản nháp",
    }
    label = labels.get(action, action or "Cập nhật")
    raw = str(detail or "").strip()
    try:
        obj = json.loads(raw)
    except Exception:
        return label, raw or "—"
    if not isinstance(obj, dict):
        return label, raw or "—"

    if action == "CLASSIFICATION_CHANGE":
        parts = []
        old_q = obj.get("old_q")
        new_q = obj.get("new_q")
        try:
            old_label = _Q_LABEL.get(int(old_q)) if old_q is not None else None
        except Exception:
            old_label = None
        try:
            new_label = _Q_LABEL.get(int(new_q)) if new_q is not None else None
        except Exception:
            new_label = None
        if old_label or new_label:
            parts.append(f"{old_label or 'Chưa phân loại'} → {new_label or 'Chưa phân loại'}")
        old_focus = obj.get("old_focus")
        new_focus = obj.get("new_focus")
        if old_focus != new_focus:
            if old_focus and new_focus:
                parts.append(f"Mục trọng tâm #{old_focus} → #{new_focus}")
            elif new_focus:
                parts.append(f"Chuyển vào mục trọng tâm #{new_focus}")
            elif old_focus:
                parts.append(f"Bỏ mục trọng tâm #{old_focus}")
        reason = str(obj.get("reason") or "").strip()
        if reason:
            parts.append(f"Lý do: {reason}")
        return label, " · ".join(parts) or "Đã điều chỉnh phân loại"

    old_status = obj.get("old_status")
    new_status = obj.get("new_status") or obj.get("status")
    note = obj.get("actual_result") or obj.get("note") or obj.get("text") or ""
    parts = []
    if old_status or new_status:
        parts.append(f"{old_status or '—'} → {new_status or '—'}")
    if note:
        parts.append(str(note))
    if parts:
        return label, " · ".join(parts)
    return label, "Đã cập nhật"


def _is_admin_row(row):
    try:
        return bool(int(row["is_admin"] or 0))
    except Exception:
        return False


def _controller_allows(c, actor_uid, case_id):
    """Admin sees all; a normal leader may act only on cases assigned to them."""
    actor = c.execute(
        "SELECT id,role,is_admin,active FROM users WHERE id=?", (int(actor_uid),)
    ).fetchone()
    if not actor or not int(actor["active"] or 0):
        return False
    if _is_admin_row(actor):
        return True
    if str(actor["role"] or "") != "Lãnh đạo phòng":
        return False
    cols = {str(r[1]) for r in c.execute("PRAGMA table_info(customer_work_cases)").fetchall()}
    if "controller_user_id" not in cols:
        return False
    case = c.execute(
        "SELECT controller_user_id FROM customer_work_cases WHERE id=?", (int(case_id),)
    ).fetchone()
    if not case or not case["controller_user_id"]:
        return False
    return int(case["controller_user_id"]) == int(actor_uid)


def _install_customer_approval_scope(customer_core, logger=None):
    if getattr(customer_core, "_P6_CONTROLLER_APPROVAL_SCOPE", False):
        return
    original_approve = customer_core.approve_case_plan
    original_reschedule = customer_core.decide_reschedule

    def approve_case_plan(get_conn, case_id, actor_uid, approve=True, note=None, logger=None):
        with get_conn() as c:
            allowed = _controller_allows(c, actor_uid, case_id)
        if not allowed:
            raise PermissionError(
                "Bạn chỉ được phê duyệt công việc do mình là Lãnh đạo kiểm soát; Admin được duyệt toàn bộ."
            )
        return original_approve(
            get_conn, case_id, actor_uid, approve=approve, note=note, logger=logger
        )

    def decide_reschedule(get_conn, request_id, actor_uid, approve=True, note=None, logger=None):
        with get_conn() as c:
            req = c.execute(
                "SELECT case_id FROM case_reschedule_requests WHERE id=?", (int(request_id),)
            ).fetchone()
            allowed = bool(req and _controller_allows(c, actor_uid, int(req["case_id"])))
        if not allowed:
            raise PermissionError(
                "Bạn chỉ được xử lý đề nghị dời hạn của công việc do mình là Lãnh đạo kiểm soát; Admin được xử lý toàn bộ."
            )
        return original_reschedule(
            get_conn, request_id, actor_uid, approve=approve, note=note, logger=logger
        )

    customer_core.approve_case_plan = approve_case_plan
    customer_core.decide_reschedule = decide_reschedule
    customer_core._P6_CONTROLLER_APPROVAL_SCOPE = True
    if logger:
        logger.info("P6_CUSTOMER_APPROVAL_SCOPE_INSTALLED controller_exact=1 admin_all=1")


def _pending_approval_data(u, policy, weekly_core, customer_core, get_conn):
    """UI filtering mirrors the core permission check for Customer Work."""
    uid = int(policy._uget(u, "id"))
    admin = policy._is_admin(u)
    with get_conn() as c:
        cases, moves = customer_core.pending_case_approvals(c)
        if not admin:
            scoped_cases = []
            for x in cases:
                cid = int(x.get("id") or 0)
                if cid and _controller_allows(c, uid, cid):
                    scoped_cases.append(x)
            cases = scoped_cases

        plans = [dict(r) for r in c.execute(
            "SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id "
            "WHERE p.workflow_status='DA_NOP' ORDER BY p.week_start,u.full_name"
        ).fetchall()]
        plans = [
            p for p in plans
            if policy._direct_scope_ok(c, uid, int(p["user_id"]), admin)
        ]

        wmoves = [dict(r) for r in c.execute(
            "SELECT r.*,w.user_id,u.full_name requester_name FROM weekly_plan_reschedule_requests r "
            "JOIN weekly_plan_items w ON w.id=r.item_id JOIN users u ON u.id=r.requested_by "
            "WHERE r.status='PENDING' ORDER BY r.requested_at,r.id"
        ).fetchall()]
        wmoves = [
            r for r in wmoves
            if policy._direct_scope_ok(
                c, uid, int(r.get("user_id") or r.get("requested_by") or 0), admin
            )
        ]

        if not admin:
            scoped_moves = []
            for r in moves:
                cid = int(r.get("case_id") or 0)
                if cid and _controller_allows(c, uid, cid):
                    scoped_moves.append(r)
            moves = scoped_moves
    return uid, cases, moves, plans, wmoves


def _install_pending_scope(policy, weekly_core, customer_core, logger=None):
    def pending(u, policy_arg, weekly_core_arg, customer_core_arg, get_conn):
        return _pending_approval_data(u, policy, weekly_core, customer_core, get_conn)
    p4._pending_approval_data = pending
    if logger:
        logger.info("P6_PENDING_APPROVAL_UI_SCOPE_INSTALLED controller_exact=1")


def _yellow_button_css(key):
    return f"""
    <style>
    div[class*='st-key-{key}'] button{{
      background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
      border:2px solid #FFE589!important;font-weight:950!important;
      min-height:2.25rem!important;padding:.30rem .72rem!important;
    }}
    div[class*='st-key-{key}'] button *{{
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important;
    }}
    </style>
    """


def _room_case_card(st, customer_ui, x):
    """Same compact action placement as the Customer Work processing card."""
    q = p4.priority_today._quadrant(x)
    heat = p4.priority_today._HEAT[q]
    status_text, status_color, status_bg = p4._status_meta(x)
    cid = int(x.get("id") or 0)
    key = f"p6_room_case_{cid}_{q}"
    button_key = f"p6_room_case_detail_{cid}_{q}"

    customer = p3dash.esc(x.get("customer_name") or "—")
    case_type = p3dash.esc(x.get("case_type") or x.get("title") or "Công việc")
    title = p3dash.esc(x.get("title") or "")
    code = p3dash.esc(x.get("case_code") or "")
    owner = p3dash.esc(x.get("owner_name") or "—")
    controller = p3dash.esc(x.get("controller_name") or "—")
    stage = p3dash.esc(x.get("stage_name") or "—")
    elapsed = p3dash.esc(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    created = p3dash.esc(customer_ui._dt_text(x.get("created_at")))
    due = p3dash.esc(customer_ui._date_text(x.get("expected_complete_at")))
    issues = int(x.get("open_issue_count") or 0)
    contact = p3dash.esc(x.get("contact_name") or "")
    phone = p3dash.esc(x.get("contact_phone") or "")
    role = p3dash.esc(x.get("contact_role") or "")
    priority = p3dash.esc(customer_ui.core.quadrant_label(q))

    with st.container(key=key, border=True):
        h1, h2, h3 = st.columns([5.7, 1.6, 2.7], vertical_alignment="top")
        with h1:
            st.html(
                f"<div class='p6cw-title'>{customer} <span>·</span> {case_type}</div>"
                + (f"<div class='p6cw-work'>📌 {title}</div>" if title and title.casefold()!=case_type.casefold() else "")
            )
        with h2:
            st.html(f"<div class='p6cw-code'>{code}</div>")
        with h3:
            if st.button("🔎 Chi tiết", key=button_key, use_container_width=True):
                st.session_state["cw_case_id"] = cid
                st.session_state["cw_view"] = "processing"
                st.session_state["main_section"] = "plan"
                st.session_state["main_page"] = "customer_work"
                st.rerun()

        st.html(
            f"""
            <div class='p6cw-row'><span>🕒 <b>Tạo lúc:</b> {created}</span><span>👤 <b>Phụ trách:</b> {owner}</span><span>🛡️ <b>Kiểm soát:</b> {controller}</span></div>
            <div class='p6cw-row'><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span><span class='p6cw-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>
            <div class='p6cw-row'><span>🎯 <b>Dự kiến:</b> {due}</span><span>⚠ <b>Vướng mắc:</b> {issues}</span><span class='p6cw-pill' style='color:{heat['accent']};background:{heat['bg']};border:1px solid {heat['border']}'>{heat['icon']} {priority}</span></div>
            {f"<div class='p6cw-contact'>☎ <b>{contact}</b> · {role} · {phone}</div>" if contact or phone else ''}
            <style>
            div[class*='st-key-{key}']{{border-left:6px solid {heat['accent']}!important;background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;box-shadow:0 6px 16px rgba(0,0,0,.09)}}
            .p6cw-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}.p6cw-title span{{opacity:.7}}
            .p6cw-work{{font-size:.82rem;font-weight:750;margin-top:3px}}.p6cw-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .p6cw-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px;white-space:normal;overflow-wrap:anywhere}}
            .p6cw-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}.p6cw-contact{{font-size:.80rem;margin-top:7px;opacity:.94;white-space:normal;overflow-wrap:anywhere}}
            </style>
            """
        )
        st.html(_yellow_button_css(button_key))


def _compact_weekly_card(st, policy, weekly_core, item, prefix, can_update=False, can_edit=False):
    iid = int(item.get("id") or 0)
    q = int(item.get("priority_quadrant") or 4)
    heat = p3week.weekboard._HEAT.get(q, p3week.weekboard._HEAT[4])
    key = f"p6_wcard_{prefix}_{iid}"
    customer = item.get("customer_text") or item.get("master_customer_name") or "Công việc nội bộ"
    owner = item.get("owner_name_snapshot") or item.get("owner_name") or "—"
    controller = item.get("controller_name_snapshot") or item.get("controller_name") or "—"
    focus = item.get("focus_name_snapshot") or "Không thuộc trọng tâm"
    actual = item.get("actual_result") or ""
    status = str(item.get("status") or "PLANNED")
    due = p5._parse_day(item.get("expected_complete_date")) or p5._parse_day(item.get("work_date"))
    overdue = bool(due and due < date.today() and status not in {"DONE", "CANCELLED"})
    changed = bool(
        status not in {"PLANNED", "CANCELLED"}
        or actual
        or int(item.get("reschedule_count") or 0)
        or int(item.get("carryover_count") or 0)
        or int(item.get("q2_watch_flag") or 0)
    )
    accent = "#F04438" if overdue else "#F79009" if changed else heat["accent"]
    flags = []
    if overdue:
        flags.append("🔴 QUÁ HẠN")
    if status == "IN_PROGRESS":
        flags.append("🔄 ĐANG LÀM")
    if status == "DONE":
        flags.append("✅ HOÀN THÀNH")
    if int(item.get("reschedule_count") or 0):
        flags.append(f"↪ DỜI {int(item.get('reschedule_count') or 0)} LẦN")
    if int(item.get("carryover_count") or 0):
        flags.append(f"⏩ CHUYỂN TIẾP {int(item.get('carryover_count') or 0)} LẦN")
    if int(item.get("q2_watch_flag") or 0):
        flags.append("🚩 Q2 CẦN CHÚ Ý")

    update_key = f"p6_update_btn_{prefix}_{iid}"
    edit_key = f"p6_edit_btn_{prefix}_{iid}"
    with st.container(key=key, border=True):
        h1, h2 = st.columns([7.4, 2.6], vertical_alignment="top")
        with h1:
            st.html(
                f"<div class='p6w-title'>{p3dash.esc(item.get('title') or 'Công việc')}</div>"
                f"<div class='p6w-customer'>🏢 {p3dash.esc(customer)}</div>"
            )
        with h2:
            if can_update:
                if st.button("🔄 Cập nhật tiến độ", key=update_key, use_container_width=True):
                    st.session_state["p3_update_week_item"] = iid
                    st.rerun()
                st.html(_yellow_button_css(update_key))
            elif can_edit:
                if st.button("✏️ Điều chỉnh", key=edit_key, use_container_width=True):
                    st.session_state["p3_manager_edit_week_item"] = iid
                    st.rerun()
                st.html(_yellow_button_css(edit_key))

        st.html(
            f"""
            <div class='p6w-row'><span style='color:{heat['accent']};font-weight:950'>{p3dash.esc(heat['label'])}</span><span>📅 {p3dash.esc(p3dash.dmy(item.get('work_date')))}</span><span>🎯 Hạn {p3dash.esc(p3dash.dmy(item.get('expected_complete_date')))}</span></div>
            <div class='p6w-row'><span>👤 {p3dash.esc(owner)}</span><span>🛡️ {p3dash.esc(controller)}</span></div>
            <div class='p6w-row'><span>📌 {p3dash.esc(focus)}</span><span>📍 {p3dash.esc(p3week._status_label(weekly_core,status))}</span></div>
            {f"<div class='p6w-flags'>{p3dash.esc(' · '.join(flags))}</div>" if flags else ''}
            {f"<div class='p6w-result'>📝 {p3dash.esc(actual)}</div>" if actual else ''}
            <style>
            div[class*='st-key-{key}']{{border-left:6px solid {accent}!important;background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;box-shadow:0 5px 14px rgba(0,0,0,.08)}}
            .p6w-title{{font-weight:950;font-size:.92rem;line-height:1.25}}.p6w-customer{{font-size:.78rem;color:#63DCCB;font-weight:850;margin-top:4px}}
            .p6w-row{{display:flex;gap:7px 12px;flex-wrap:wrap;font-size:.74rem;margin-top:6px;white-space:normal;overflow-wrap:anywhere}}
            .p6w-flags{{font-size:.73rem;margin-top:6px;color:#FFD166;font-weight:950;white-space:normal;overflow-wrap:anywhere}}
            .p6w-result{{font-size:.73rem;margin-top:6px;color:#63DCCB;font-weight:850;white-space:normal;overflow-wrap:anywhere}}
            </style>
            """
        )


def _render_week_board(st, policy, weekly_core, get_conn, uid, ws, items, status, manager_edit=False):
    """Include user id in every day/add context so room plans never collide."""
    st.markdown("### 🗓 Kế hoạch Thứ 2 → Thứ 6")
    uid = int(uid)
    live = [dict(x) for x in items if str(x.get("status") or "") != "CANCELLED"]
    cols = st.columns(5, gap="small")
    for idx, (col, label) in enumerate(zip(cols, ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"])):
        d = ws + timedelta(days=idx)
        arr = [x for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()]
        arr.sort(
            key=lambda x: (
                policy.PRIORITY_ORDER.index(int(x.get("priority_quadrant") or 4))
                if int(x.get("priority_quadrant") or 4) in policy.PRIORITY_ORDER else 9,
                int(x.get("id") or 0),
            )
        )
        with col:
            st.html(
                f"<div class='p6-day-head'><b>{label}</b><span>{d:%d/%m}</span><em>{len(arr)} việc</em></div>"
            )
            if not manager_edit and status in {"NHAP", "DA_DUYET"}:
                add_key = f"p3_quick_add_{uid}_{ws.isoformat()}_{idx}_{status}"
                if st.button("＋ Thêm công việc", key=add_key, use_container_width=True):
                    st.session_state[f"wp_add_open_{ws.isoformat()}"] = True
                    st.session_state[f"wp_quick_day_{ws.isoformat()}"] = d.isoformat()
                    if status == "DA_DUYET":
                        st.session_state[f"p3_emergent_open_{ws.isoformat()}"] = True
                    st.rerun()
            if not arr:
                st.caption("Chưa có công việc")
            for x in arr:
                _compact_weekly_card(
                    st, policy, weekly_core, x,
                    f"{uid}_{ws.isoformat()}_{idx}_{'mgr' if manager_edit else 'staff'}",
                    can_update=(status == "DA_DUYET" and not manager_edit),
                    can_edit=manager_edit,
                )
                if not manager_edit and status == "NHAP" and not int(x.get("is_emergent") or 0):
                    if st.button("🗑 Bỏ", key=f"p6_remove_{uid}_{x['id']}", use_container_width=True):
                        with get_conn() as c:
                            c.execute(
                                "UPDATE weekly_plan_items SET status='CANCELLED',updated_at=? WHERE id=? AND user_id=?",
                                (policy._now(), int(x["id"]), uid),
                            )
                            c.execute(
                                "INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'DRAFT_REMOVE','Bỏ khỏi bản nháp',?)",
                                (int(x["id"]), uid, policy._now()),
                            )
                        st.rerun()
    st.html(
        """<style>.p6-day-head{display:flex;flex-direction:column;gap:2px;padding:9px 10px;margin-bottom:7px;border-radius:12px;background:linear-gradient(135deg,#075C57,#0F746B);border:1px solid #F4B41A;color:#fff}.p6-day-head b{font-size:.96rem}.p6-day-head span{font-size:.78rem}.p6-day-head em{font-size:.70rem;opacity:.84;font-style:normal}</style>"""
    )


def _install_cards_and_week_keys(logger=None):
    room_dashboard._room_case_card = _room_case_card
    p3week.weekly_card = _compact_weekly_card
    p3week.render_week_board = _render_week_board
    p3week.render_week_update_form = p5._enhanced_update_form
    # Phase 3 imported these symbols by value; rebind its module globals as well.
    p3dash.weekly_card = _compact_weekly_card
    p3dash.render_week_board = _render_week_board
    p3dash.render_week_update_form = p5._enhanced_update_form
    p5._fmt_action = _fmt_action
    if logger:
        logger.info("P6_CARD_UX_INSTALLED compact_actions=1 yellow=1 unique_week_keys=1 history_json=0")


def _scope_label(value):
    return "Kế hoạch" if str(value or "OPS") == "PLAN" else "Tác nghiệp"


def _render_type_table(st, rows):
    if not rows:
        st.info("Chưa có Loại công việc.")
        return
    body = []
    for r in rows:
        body.append(
            "<tr>"
            f"<td>{int(r['id'])}</td>"
            f"<td>{html.escape(str(r.get('name') or ''))}</td>"
            f"<td>{html.escape(_scope_label(r.get('module_scope')))}</td>"
            f"<td>{'Đang sử dụng' if r.get('active') else 'Ngưng'}</td>"
            f"<td>{html.escape(str(r.get('updated_at') or r.get('created_at') or '—'))}</td>"
            "</tr>"
        )
    st.html(
        """
        <div class='p6-admin-table'><table><thead><tr>
        <th>ID</th><th>Tên công việc</th><th>Phân hệ</th><th>Trạng thái</th><th>Cập nhật</th>
        </tr></thead><tbody>""" + "".join(body) + """</tbody></table></div>
        <style>
        .p6-admin-table{width:100%;overflow-x:auto}.p6-admin-table table{width:100%;table-layout:fixed;border-collapse:collapse}
        .p6-admin-table th,.p6-admin-table td{padding:8px 9px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere;font-size:.78rem}
        .p6-admin-table th{font-weight:950;color:#63DCCB;background:rgba(15,116,107,.14)}
        </style>
        """
    )


def _render_system_types(app_ns, policy, u, logger=None):
    st = app_ns["st"]
    get_conn = app_ns["get_conn"]
    page_title = app_ns.get("page_title")
    if page_title:
        page_title(
            "Quản trị hệ thống",
            "Quản lý người dùng, khách hàng CIF, loại công việc, nhóm nguyên nhân tác nghiệp, audit và sao lưu dữ liệu.",
        )
    else:
        st.title("Quản trị hệ thống")

    app_ns["pill_nav"](
        "admin_view", _ADMIN_OPTIONS, default="types", prefix="system_admin_phase6"
    )
    worktype.ensure_worktype_scope(get_conn, logger or app_ns.get("LOGGER"))
    st.subheader("Loại công việc")
    st.caption(
        "Danh mục dùng chung toàn hệ thống. Mỗi loại được gán đúng một phân hệ: Tác nghiệp hoặc Kế hoạch; loại thuộc phân hệ nào chỉ xuất hiện tại phân hệ đó."
    )
    with get_conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT id,name,module_scope,active,created_at,updated_at FROM task_types ORDER BY id"
        ).fetchall()]
    _render_type_table(st, rows)

    st.markdown("#### Tạo loại công việc")
    with st.form("p6_system_task_type_create", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        new_name = c1.text_input("Tên công việc mới *")
        new_scope = c2.selectbox("Thuộc phân hệ *", ["OPS", "PLAN"], format_func=_scope_label)
        create = st.form_submit_button("Thêm loại công việc", type="primary")
    if create:
        clean = str(new_name or "").strip()
        if not clean:
            st.error("Bắt buộc nhập tên Loại công việc.")
        else:
            try:
                ts = app_ns["now_str"]() if "now_str" in app_ns else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with get_conn() as c:
                    exists = c.execute(
                        "SELECT id FROM task_types WHERE lower(trim(name))=lower(trim(?))", (clean,)
                    ).fetchone()
                    if exists:
                        raise ValueError("Tên Loại công việc đã tồn tại.")
                    cur = c.execute(
                        "INSERT INTO task_types(name,sla_hours,active,module_scope,created_at,updated_at) VALUES(?,8,1,?,?,?)",
                        (clean, str(new_scope), ts, ts),
                    )
                    new_id = int(cur.lastrowid)
                audit = app_ns.get("audit")
                if audit:
                    audit(
                        int(policy._uget(u, "id")), "CREATE_TASK_TYPE", "task_type", new_id,
                        f"name={clean}; module_scope={new_scope}",
                    )
                st.toast("Đã thêm Loại công việc.", icon="✅")
                st.rerun()
            except (sqlite3.IntegrityError, ValueError) as exc:
                st.error(str(exc))

    if rows:
        st.markdown("#### Sửa loại công việc")
        by_id = {int(r["id"]): r for r in rows}
        selected = st.selectbox(
            "Chọn loại công việc để sửa",
            list(by_id),
            format_func=lambda x: f"{by_id[int(x)]['name']} · {_scope_label(by_id[int(x)].get('module_scope'))}",
            key="p6_task_type_edit_pick",
        )
        cur = by_id[int(selected)]
        with st.form(f"p6_task_type_edit_{int(selected)}"):
            e1, e2 = st.columns([2, 1])
            edit_name = e1.text_input("Tên công việc", value=str(cur.get("name") or ""))
            scopes = ["OPS", "PLAN"]
            current_scope = str(cur.get("module_scope") or "OPS")
            edit_scope = e2.selectbox(
                "Thuộc phân hệ", scopes,
                index=scopes.index(current_scope if current_scope in scopes else "OPS"),
                format_func=_scope_label,
            )
            edit_active = st.checkbox("Đang sử dụng", value=bool(cur.get("active")))
            save = st.form_submit_button("Lưu thay đổi", type="primary")
        if save:
            clean = str(edit_name or "").strip()
            if not clean:
                st.error("Tên Loại công việc không được để trống.")
            else:
                try:
                    ts = app_ns["now_str"]() if "now_str" in app_ns else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with get_conn() as c:
                        clash = c.execute(
                            "SELECT id FROM task_types WHERE lower(trim(name))=lower(trim(?)) AND id<>?",
                            (clean, int(selected)),
                        ).fetchone()
                        if clash:
                            raise ValueError("Tên Loại công việc đã tồn tại.")
                        c.execute(
                            "UPDATE task_types SET name=?,module_scope=?,active=?,updated_at=? WHERE id=?",
                            (clean, str(edit_scope), int(bool(edit_active)), ts, int(selected)),
                        )
                    audit = app_ns.get("audit")
                    if audit:
                        audit(
                            int(policy._uget(u, "id")), "UPDATE_TASK_TYPE", "task_type", int(selected),
                            f"name={clean}; module_scope={edit_scope}; active={bool(edit_active)}",
                        )
                    st.toast("Đã cập nhật Loại công việc.", icon="✅")
                    st.rerun()
                except (sqlite3.IntegrityError, ValueError) as exc:
                    st.error(str(exc))


def _install_admin_navigation(app_ns, policy, logger=None):
    st = app_ns["st"]
    previous_pill = app_ns["pill_nav"]

    def pill_nav(state_key, options, default=None, prefix="subnav"):
        if state_key == "admin_view" and st.session_state.get("main_page") == "admin":
            values = {x[0] for x in _ADMIN_OPTIONS}
            current = st.session_state.get("admin_view")
            if current not in values:
                current = "users"
            st.session_state["admin_view"] = current
            st.session_state["system_admin_view_v2"] = current
            st.session_state["system_admin_view_v3"] = current
            return admin_hotfix._local_command_tabs(
                st, "admin_view", _ADMIN_OPTIONS, default=current, prefix="system_admin_phase6"
            )
        return previous_pill(state_key, options, default=default, prefix=prefix)

    app_ns["pill_nav"] = pill_nav
    previous_admin = app_ns["admin_page"]

    def admin_page(u):
        if st.session_state.get("main_page") != "admin":
            return previous_admin(u)
        if not policy._is_admin(u):
            st.error("Chỉ Admin mới có quyền truy cập Quản trị hệ thống.")
            return
        st.session_state["admin_scope"] = "system"
        view = str(st.session_state.get("admin_view") or "users")
        if view not in {x[0] for x in _ADMIN_OPTIONS}:
            view = "users"
            st.session_state["admin_view"] = view
        st.session_state["system_admin_view_v2"] = view
        st.session_state["system_admin_view_v3"] = view
        if view == "types":
            return _render_system_types(app_ns, policy, u, logger)
        return previous_admin(u)

    app_ns["admin_page"] = admin_page
    if logger:
        logger.info("P6_SYSTEM_ADMIN_NAV_INSTALLED tabs=6 admin_only=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    _install_customer_approval_scope(customer_core, logger)
    _install_pending_scope(policy, weekly_core, customer_core, logger)
    _install_cards_and_week_keys(logger)
    _install_admin_navigation(app_ns, policy, logger)
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE6_INSTALLED version=%s admin_tabs=6 controller_scope=1 "
            "compact_yellow_actions=1 readable_history=1 unique_quick_add=1",
            VERSION,
        )
