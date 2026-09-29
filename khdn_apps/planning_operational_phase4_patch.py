"""Operational planning Phase 4 refinements.

Requested behavior:
- combine approvals/reschedules with progress/issues at the top of room control;
- room priority cards mirror the Today card information/action layout;
- restore weekday quick-add for every role that owns a weekly plan;
- expose complete automatic/manual backup management in System Admin.
"""
from __future__ import annotations

from datetime import date, datetime
import json

from khdn_apps import backup_management_patch as backup
from khdn_apps import planning_dashboard_consolidation_patch as consolidation
from khdn_apps import planning_operational_phase3_dashboard as p3dash
from khdn_apps import planning_operational_phase3_weekly as p3week
from khdn_apps import planning_room_dashboard_detail_patch as room_dashboard
from khdn_apps import priority_today_patch as priority_today
from khdn_apps import weekly_performance_phase2_patch as phase2

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE4_VERSION"


class _WeekAddGateProxy:
    """Open the consolidated add-form gate when Phase-3 weekday buttons are clicked."""
    def __init__(self, st, ws):
        self._st = st
        self._ws = ws

    def __getattr__(self, name):
        return getattr(self._st, name)

    def button(self, label, *args, **kwargs):
        clicked = self._st.button(label, *args, **kwargs)
        key = str(kwargs.get("key") or "")
        if clicked and key.startswith("p3_quick_add_"):
            self._st.session_state[f"wp_add_open_{self._ws.isoformat()}"] = True
        return clicked


def _install_week_add_gate(policy, weekly_core, logger=None):
    original = p3week.render_week_board

    def render_week_board(st, policy_arg, weekly_core_arg, get_conn, uid, ws, items, status, manager_edit=False):
        return original(
            _WeekAddGateProxy(st, ws), policy_arg, weekly_core_arg, get_conn,
            uid, ws, items, status, manager_edit=manager_edit,
        )

    p3week.render_week_board = render_week_board
    if logger:
        logger.info("P4_WEEK_ADD_GATE_INSTALLED keys=p3_quick_add roles=all-plan-owners")


def _status_meta(x):
    if x.get("is_overdue"):
        return "🔴 Quá hạn", "#F04438", "rgba(240,68,56,.14)"
    if x.get("is_stage_delayed"):
        return "🔴 Mục bị chậm", "#F04438", "rgba(240,68,56,.14)"
    if x.get("is_stage_warning"):
        return "🟠 Sắp chậm", "#F79009", "rgba(247,144,9,.14)"
    return "🟢 Trong hạn", "#12B76A", "rgba(18,183,106,.12)"


def _room_case_card_today_parity(st, customer_ui, x):
    """Room priority card with the same information hierarchy as Today cards."""
    q = priority_today._quadrant(x)
    heat = priority_today._HEAT[q]
    status_text, status_color, status_bg = _status_meta(x)
    cid = int(x.get("id") or 0)
    key = f"p4_room_case_{cid}_{q}"
    button_key = f"p4_room_case_detail_{cid}_{q}"

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
        st.html(
            f"""
            <div class='p4cw-head'>
              <div><div class='p4cw-title'>{customer} <span>·</span> {case_type}</div>
              {f"<div class='p4cw-work'>📌 {title}</div>" if title and title.casefold()!=case_type.casefold() else ''}</div>
              <div class='p4cw-code'>{code}</div>
            </div>
            <div class='p4cw-row'><span>🕒 <b>Tạo lúc:</b> {created}</span><span>👤 <b>Phụ trách:</b> {owner}</span><span>🛡️ <b>Kiểm soát:</b> {controller}</span></div>
            <div class='p4cw-row'><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span><span class='p4cw-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>
            <div class='p4cw-row'><span>🎯 <b>Dự kiến:</b> {due}</span><span>⚠ <b>Vướng mắc:</b> {issues}</span><span class='p4cw-pill' style='color:{heat['accent']};background:{heat['bg']};border:1px solid {heat['border']}'>{heat['icon']} {priority}</span></div>
            {f"<div class='p4cw-contact'>☎ <b>{contact}</b> · {role} · {phone}</div>" if contact or phone else ''}
            <style>
            div[class*='st-key-{key}']{{border-left:6px solid {heat['accent']}!important;background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;box-shadow:0 6px 16px rgba(0,0,0,.09)}}
            .p4cw-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}
            .p4cw-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}.p4cw-title span{{opacity:.7}}
            .p4cw-work{{font-size:.82rem;font-weight:750;margin-top:3px}}.p4cw-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .p4cw-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px;white-space:normal;overflow-wrap:anywhere}}
            .p4cw-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}.p4cw-contact{{font-size:.80rem;margin-top:7px;opacity:.94;white-space:normal;overflow-wrap:anywhere}}
            div[class*='st-key-{button_key}'] button{{background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #FFE589!important;font-weight:950!important}}
            div[class*='st-key-{button_key}'] button *{{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:950!important}}
            </style>
            """
        )
        if st.button("🔎 Chi tiết", key=button_key, use_container_width=True):
            st.session_state["cw_case_id"] = cid
            st.session_state["cw_view"] = "processing"
            st.session_state["main_section"] = "plan"
            st.session_state["main_page"] = "customer_work"
            st.rerun()


def _install_room_card_parity(logger=None):
    room_dashboard._room_case_card = _room_case_card_today_parity
    if logger:
        logger.info("P4_ROOM_CARD_TODAY_PARITY_INSTALLED")


def _pending_approval_data(u, policy, weekly_core, customer_core, get_conn):
    uid = int(policy._uget(u, "id")); admin = policy._is_admin(u)
    with get_conn() as c:
        cases, moves = customer_core.pending_case_approvals(c)
        cases = [x for x in cases if policy._direct_scope_ok(c, uid, int(x.get("owner_user_id") or 0), admin)]
        plans = [dict(r) for r in c.execute(
            "SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id "
            "WHERE p.workflow_status='DA_NOP' ORDER BY p.week_start,u.full_name"
        ).fetchall()]
        plans = [p for p in plans if policy._direct_scope_ok(c, uid, int(p["user_id"]), admin)]
        wmoves = [dict(r) for r in c.execute(
            "SELECT r.*,w.user_id,u.full_name requester_name FROM weekly_plan_reschedule_requests r "
            "JOIN weekly_plan_items w ON w.id=r.item_id JOIN users u ON u.id=r.requested_by "
            "WHERE r.status='PENDING' ORDER BY r.requested_at,r.id"
        ).fetchall()]
        wmoves = [r for r in wmoves if policy._direct_scope_ok(c, uid, int(r.get("user_id") or r.get("requested_by") or 0), admin)]
        scoped = []
        for r in moves:
            owner = c.execute("SELECT owner_user_id FROM customer_work_cases WHERE id=?", (int(r.get("case_id") or 0),)).fetchone()
            if owner and policy._direct_scope_ok(c, uid, int(owner[0]), admin):
                scoped.append(r)
        moves = scoped
    return uid, cases, moves, plans, wmoves


def _render_approval_items(st, u, policy, weekly_core, customer_core, customer_ui, get_conn, logger=None):
    uid, cases, moves, plans, wmoves = _pending_approval_data(u, policy, weekly_core, customer_core, get_conn)
    total = len(cases) + len(moves) + len(plans) + len(wmoves)
    if total == 0:
        st.success("Không có kế hoạch hoặc đề nghị dời hạn đang chờ phê duyệt.")
        return

    st.markdown("### Công việc khách hàng mới")
    if not cases: st.caption("Không có công việc khách hàng chờ phê duyệt.")
    for x in cases:
        consolidation._render_case_approval_card(st, policy, customer_core, get_conn, x, uid, logger)

    st.markdown("### Kế hoạch tuần đã nộp")
    if not plans: st.caption("Không có kế hoạch tuần chờ duyệt.")
    for p in plans:
        ws = date.fromisoformat(str(p["week_start"])[:10])
        with get_conn() as c:
            items = [dict(r) for r in c.execute(
                "SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id",
                (int(p["id"]),),
            ).fetchall()]
            focus = policy._focus_categories(c, policy._scope_key(c, int(p["user_id"])), ws.year, False)
        with st.expander(f"{p.get('full_name')} · tuần {ws:%d/%m/%Y} · {len(items)} việc", expanded=True):
            policy._summary(st, items)
            p3week.render_week_board(st, policy, weekly_core, get_conn, int(p["user_id"]), ws, items, "DA_NOP", manager_edit=True)
            selected = st.session_state.get("p3_manager_edit_week_item")
            if selected:
                item = next((x for x in items if int(x.get("id") or 0) == int(selected)), None)
                if item:
                    p3week.manager_edit_item(st, u, policy, weekly_core, get_conn, p, item, focus, logger)
            decision = st.text_area("Ý kiến duyệt / lý do trả lại", key=f"p4_plan_note_{p['id']}")
            a,b = st.columns(2)
            if a.button("✓ Phê duyệt kế hoạch", key=f"p4_plan_yes_{p['id']}", type="primary", use_container_width=True):
                ts = policy._now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET',approved_at=?,approved_by=?,return_note=NULL,updated_at=? WHERE id=?", (ts,uid,ts,int(p["id"])))
                    c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE plan_id=? AND status<>'CANCELLED'", (uid,ts,int(p["id"])))
                    policy._notify(c, int(p["user_id"]), "✅ Kế hoạch tuần đã được duyệt", f"Tuần {ws:%d/%m/%Y}. {decision or ''}".strip())
                st.rerun()
            if b.button("↩ Trả lại điều chỉnh", key=f"p4_plan_back_{p['id']}", use_container_width=True, disabled=not decision.strip()):
                ts = policy._now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='TRA_LAI',returned_at=?,returned_by=?,return_note=?,updated_at=? WHERE id=?", (ts,uid,decision.strip(),ts,int(p["id"])))
                    policy._notify(c, int(p["user_id"]), "↩ Kế hoạch tuần được trả lại", decision.strip())
                st.rerun()

    st.markdown("### Đề nghị dời công việc khách hàng")
    if not moves: st.caption("Không có đề nghị dời ngày công việc khách hàng.")
    for r in moves:
        room_dashboard._render_case_move_card(st, customer_core, customer_ui, get_conn, r, uid, logger)

    st.markdown("### Đề nghị dời kế hoạch tuần")
    if not wmoves: st.caption("Không có đề nghị dời kế hoạch tuần.")
    for r in wmoves:
        room_dashboard._weekly_move_card(st, policy, get_conn, r, uid)


def _attention_rows(u, policy, get_conn):
    uid = int(policy._uget(u, "id")); admin = policy._is_admin(u)
    with get_conn() as c:
        rows = [dict(r) for r in c.execute("""SELECT e.*,cw.owner_user_id,c.customer_name,u.full_name actor_name,
            s.name stage_name,i.resolved_at,i.resolution_text FROM planning_attention_events e
            JOIN customer_work_cases cw ON cw.id=e.case_id JOIN customers c ON c.id=cw.customer_id
            LEFT JOIN users u ON u.id=e.actor_user_id LEFT JOIN work_stage_catalog s ON s.id=cw.current_stage_id
            LEFT JOIN case_issues i ON e.event_type='ISSUE_OPEN' AND i.id=e.source_id
            WHERE e.status='OPEN' ORDER BY e.created_at DESC,e.id DESC""").fetchall()]
        return [r for r in rows if policy._direct_scope_ok(c, uid, int(r.get("owner_user_id") or 0), admin)]


def _render_attention_items(st, u, policy, customer_core, get_conn, logger=None):
    uid = int(policy._uget(u, "id")); rows = _attention_rows(u, policy, get_conn)
    if not rows:
        st.success("Không có cập nhật tiến độ hoặc vướng mắc mới đang chờ xác nhận.")
        return
    for r in rows:
        eid = int(r["id"]); issue = str(r.get("event_type")) == "ISSUE_OPEN"
        try: detail = json.loads(r.get("detail") or "{}")
        except Exception: detail = {"text": r.get("detail")}
        headline = "⚠ VƯỚNG MẮC" if issue else "🔄 CẬP NHẬT TIẾN ĐỘ"
        body = detail.get("issue") if issue else f"{detail.get('from_stage','—')} → {detail.get('to_stage','—')}"
        note = detail.get("stage") if issue else detail.get("note")
        cls = "p4-attn-issue" if issue else "p4-attn-stage"
        st.html(f"""<div class='p4-attn {cls}'><div class='p4-attn-head'>{headline} · {p3dash.esc(r.get('title'))}</div>
        <div class='p4-attn-main'>{p3dash.esc(body)}</div><div class='p4-attn-note'>{p3dash.esc(note or '')}</div>
        <div class='p4-attn-meta'>{p3dash.esc(r.get('actor_name'))} · {p3dash.esc(p3dash.dt(r.get('created_at')))} · Mục hiện tại: {p3dash.esc(r.get('stage_name'))}</div></div>
        <style>.p4-attn{{padding:11px 13px;border-radius:11px;margin:8px 0;white-space:normal;overflow-wrap:anywhere}}
        .p4-attn-stage{{border:1px solid #F4B41A;border-left:7px solid #F4B41A;background:rgba(244,180,26,.13)}}
        .p4-attn-issue{{border:1px solid #F04438;border-left:7px solid #F04438;background:rgba(240,68,56,.13)}}
        .p4-attn-head{{font-size:.83rem;font-weight:950;color:#FFD166}}.p4-attn-main{{font-size:.95rem;font-weight:950;margin-top:4px}}
        .p4-attn-note{{font-size:.82rem;font-weight:850;margin-top:3px;color:#63DCCB}}.p4-attn-meta{{font-size:.73rem;opacity:.82;margin-top:5px}}</style>""")
        ack_note = st.text_input("Nội dung xử lý / ghi nhận" if issue else "Ghi nhận của lãnh đạo", key=f"p4_attn_note_{eid}")
        if st.button("✓ Đã xử lý" if issue else "✓ Đã xem", key=f"p4_attn_ack_{eid}", type="primary", use_container_width=True):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if issue and not r.get("resolved_at"):
                customer_core.resolve_issue(get_conn, int(r["source_id"]), uid, str(ack_note or "").strip(), logger)
            with get_conn() as c:
                c.execute("UPDATE planning_attention_events SET status='ACKED',acknowledged_at=?,acknowledged_by=?,acknowledgement_note=?,updated_at=? WHERE id=?",
                          (ts,uid,str(ack_note or "").strip(),ts,eid))
            if logger: logger.info("P4_ATTENTION_ACK event=%s actor=%s type=%s",eid,uid,r.get("event_type"))
            st.rerun()


def _install_combined_leader_queue(policy, weekly_core, customer_core, customer_ui, logger=None):
    def combined_queue(st, u, policy_arg, customer_core_arg, get_conn, logger=None):
        uid, cases, moves, plans, wmoves = _pending_approval_data(u, policy, weekly_core, customer_core, get_conn)
        attention = _attention_rows(u, policy, get_conn)
        approval_total = len(cases)+len(moves)+len(plans)+len(wmoves)
        st.markdown("## 🔔 Trung tâm việc chờ lãnh đạo xử lý")
        t1, t2 = st.tabs([
            f"✅ Phê duyệt kế hoạch / dời hạn ({approval_total})",
            f"🔄 Cập nhật tiến độ / vướng mắc ({len(attention)})",
        ])
        with t1:
            _render_approval_items(st, u, policy, weekly_core, customer_core, customer_ui, get_conn, logger)
        with t2:
            _render_attention_items(st, u, policy, customer_core, get_conn, logger)
        st.divider()
        phase2._render_manager_reviews(st, u, policy, weekly_core, get_conn, logger)
        phase2._render_room_performance(st, u, policy, weekly_core, get_conn)

    # Phase-3 room dashboard calls this function near the top, immediately after metrics.
    p3dash._attention_dashboard = combined_queue

    # Prevent the old approval center from being rendered again at the bottom.
    def no_bottom_approval(*args, **kwargs):
        return None
    room_dashboard._render_approval_center = no_bottom_approval
    if logger:
        logger.info("P4_COMBINED_LEADER_QUEUE_INSTALLED approvals_top=1 attention_top=1 duplicate_bottom=0")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    _install_week_add_gate(policy, weekly_core, logger)
    _install_room_card_parity(logger)
    _install_combined_leader_queue(policy, weekly_core, customer_core, customer_ui, logger)
    backup.install(app_ns, logger)
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info("PLANNING_OPERATIONAL_PHASE4_INSTALLED version=%s combined_queue=1 room_card_today_parity=1 weekly_add_fixed=1 backups=1", VERSION)
