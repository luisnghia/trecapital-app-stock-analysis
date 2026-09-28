"""Room-wide planning dashboard detail + compact reschedule approval cards.

Installed last. Requested behavior:
- Lãnh đạo/Admin see the room's priority quadrants with the same detailed card
  experience as Công việc hôm nay, not just four counters.
- Customer-work and weekly-plan reschedule approvals use compact operational
  cards; the actual changed date and reason are visually emphasized.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import html

from khdn_apps import planning_dashboard_consolidation_patch as consolidation
from khdn_apps import priority_today_patch as priority_today

VERSION = "1.0.0"
_FLAG = "_PLANNING_ROOM_DASHBOARD_DETAIL_VERSION"


def _esc(v):
    return html.escape("—" if v is None or v == "" else str(v))


def _dmy(v):
    if not v:
        return "—"
    s = str(v).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except Exception:
        try:
            return date.fromisoformat(s[:10]).strftime("%d/%m/%Y")
        except Exception:
            return s


def _dt(v):
    if not v:
        return "—"
    s = str(v).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return s


def _user_name(c, uid):
    if not uid:
        return "—"
    row = c.execute("SELECT full_name FROM users WHERE id=?", (int(uid),)).fetchone()
    return str(row[0]) if row and row[0] else f"ID {uid}"


def _change_strip(st, label, old_value, new_value, reason=None, key="change"):
    st.html(
        f"""
        <div class="pd-change-strip pd-change-{_esc(key)}">
          <div class="pd-change-label">⚡ {_esc(label)}</div>
          <div class="pd-change-values">
            <span class="pd-old">{_esc(old_value)}</span>
            <span class="pd-arrow">→</span>
            <span class="pd-new">{_esc(new_value)}</span>
          </div>
          {f'<div class="pd-reason"><b>Lý do:</b> {_esc(reason)}</div>' if reason else ''}
        </div>
        <style>
          .pd-change-strip{{margin:.35rem 0 .55rem 0;padding:10px 12px;border:1px solid rgba(244,180,26,.88);border-left:6px solid #F4B41A;border-radius:10px;background:linear-gradient(110deg,rgba(244,180,26,.14),rgba(6,78,72,.08));}}
          .pd-change-label{{font-size:.72rem;font-weight:900;letter-spacing:.02em;color:#F4B41A;margin-bottom:4px}}
          .pd-change-values{{display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:.92rem}}
          .pd-old{{opacity:.68;text-decoration:line-through}}
          .pd-arrow{{font-weight:900;color:#F4B41A}}
          .pd-new{{font-weight:950;color:#FFD166;font-size:1rem}}
          .pd-reason{{margin-top:5px;font-size:.80rem;line-height:1.35;white-space:normal;overflow-wrap:anywhere}}
        </style>
        """
    )


def _room_case_card(st, customer_ui, x):
    """Read-only clone of the processing card with a room-dashboard-safe key."""
    q = priority_today._quadrant(x)
    heat = priority_today._HEAT[q]
    status_text, status_color, status_bg = ("🟢 Trong hạn", "#12B76A", "rgba(18,183,106,.12)")
    if x.get("is_overdue"):
        status_text, status_color, status_bg = ("🔴 Quá hạn", "#F04438", "rgba(240,68,56,.14)")
    elif x.get("is_stage_delayed"):
        status_text, status_color, status_bg = ("🔴 Mục bị chậm", "#F04438", "rgba(240,68,56,.14)")
    elif x.get("is_stage_warning"):
        status_text, status_color, status_bg = ("🟠 Sắp chậm", "#F79009", "rgba(247,144,9,.14)")

    customer = _esc(x.get("customer_name"))
    case_type = _esc(x.get("case_type") or "Công việc")
    title = _esc(x.get("title") or "")
    code = _esc(x.get("case_code") or "")
    owner = _esc(x.get("owner_name") or "—")
    stage = _esc(x.get("stage_name") or "—")
    elapsed = _esc(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    due = _dt(x.get("expected_complete_at"))
    issues = int(x.get("open_issue_count") or 0)
    priority = _esc(customer_ui.core.quadrant_label(q))
    work_line = "" if not title or title.casefold() == case_type.casefold() else f'<div class="rd-work">📌 {title}</div>'

    st.markdown(
        f"""<div class="rd-card" style="--a:{heat['accent']};--b:{heat['border']};--bg:{heat['bg']};">
          <div class="rd-head"><div><div class="rd-title">{customer} <span>·</span> {case_type}</div>{work_line}</div><div class="rd-code">{code}</div></div>
          <div class="rd-row"><span>👤 <b>{owner}</b></span><span>📍 {stage}</span><span>⏱ {elapsed}</span><span class="rd-pill" style="color:{status_color};background:{status_bg};">{status_text}</span></div>
          <div class="rd-row"><span>🎯 <b>Dự kiến:</b> {_esc(due)}</span><span>⚠ <b>Vướng mắc:</b> {issues}</span><span class="rd-priority" style="border-color:{heat['border']};background:{heat['bg']};color:{heat['accent']};">{heat['icon']} {priority}</span></div>
        </div>
        <style>
          .rd-card{{border:1px solid var(--b);border-left:7px solid var(--a);border-radius:13px;padding:12px 14px;margin:.30rem 0 .30rem 0;background:linear-gradient(120deg,var(--bg),rgba(6,78,72,.07));}}
          .rd-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}
          .rd-title{{font-size:1rem;font-weight:950;color:#63DCCB;line-height:1.25}} .rd-title span{{opacity:.7}}
          .rd-code{{font-size:.76rem;font-weight:900;color:#F4B41A;white-space:nowrap}} .rd-work{{font-size:.80rem;font-weight:760;margin-top:3px}}
          .rd-row{{display:flex;flex-wrap:wrap;gap:7px 14px;margin-top:8px;align-items:center;font-size:.81rem;line-height:1.35}}
          .rd-pill,.rd-priority{{padding:3px 8px;border-radius:999px;font-weight:900}} .rd-priority{{border:1px solid}}
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("🔎 Chi tiết", key=f"room_case_detail_{int(x.get('id') or 0)}", use_container_width=True):
        st.session_state["cw_case_id"] = int(x["id"])
        st.session_state["main_section"] = "plan"
        st.session_state["main_page"] = "customer_work"
        st.rerun()


def _render_room_priority(st, customer_ui, data):
    st.subheader("🔥 Góc phần tư ưu tiên")
    st.caption("Theo dõi chi tiết toàn bộ công việc phòng. Xếp I → IV; trong từng góc: quá hạn → mục bị chậm → có vướng mắc → hạn gần nhất.")
    priority_today._install_heat_css(st)
    ordered = sorted(list(data), key=lambda x: priority_today._priority_sort_key(customer_ui.core, x))
    counts = priority_today._heat_summary(st, customer_ui, ordered)
    for q in range(1, 5):
        meta = priority_today._HEAT[q]
        arr = [x for x in ordered if priority_today._quadrant(x) == q]
        with st.container(key=f"room_heat_q{q}"):
            with st.expander(
                f"{meta['icon']} {customer_ui.core.quadrant_label(q)} · {counts[q]} công việc",
                expanded=(q in (1, 2) and bool(arr)),
            ):
                if not arr:
                    st.caption("Không có công việc trong nhóm ưu tiên này.")
                for x in arr:
                    _room_case_card(st, customer_ui, x)


def _render_attention_table(st, customer_ui, rows):
    seen = set(); data = []
    for x in rows:
        iid = int(x.get("id") or 0)
        if iid in seen:
            continue
        seen.add(iid)
        flags = []
        if x.get("is_overdue"): flags.append("Quá hạn")
        if x.get("is_stage_delayed"): flags.append("Mục bị chậm")
        if int(x.get("open_issue_count") or 0) > 0: flags.append(f"{int(x.get('open_issue_count') or 0)} vướng mắc")
        data.append([
            x.get("customer_name") or "—", x.get("title") or "—", x.get("owner_name") or "—",
            x.get("stage_name") or "—", ", ".join(flags) or "—", _dmy(x.get("expected_complete_at")),
        ])
    customer_ui._html_table(st, ["Khách hàng", "Công việc", "Cán bộ", "Mục hiện tại", "Cần chú ý", "Dự kiến"], data)


def _render_case_move_card(st, customer_core, customer_ui, get_conn, req, uid, logger=None):
    rid = int(req.get("id") or 0)
    with get_conn() as c:
        case = customer_core.get_case(c, int(req.get("case_id") or 0)) or {}
    with st.container(key=f"room_case_move_{rid}", border=True):
        customer_ui._case_card(st, case, get_conn, int(uid), False, logger, compact=True)
        _change_strip(
            st,
            "THAY ĐỔI NGÀY DỰ KIẾN HOÀN THÀNH",
            _dmy(req.get("old_due_at")),
            _dmy(req.get("proposed_due_at")),
            req.get("reason") or "—",
            f"crm-{rid}",
        )
        st.caption(f"Người đề nghị: {req.get('requester_name') or '—'} · Gửi lúc {_dt(req.get('requested_at'))}")
        note = st.text_input("Ý kiến phê duyệt", key=f"room_cr_note_{rid}")
        a, b = st.columns(2)
        if a.button("✓ Phê duyệt", key=f"room_cr_yes_{rid}", type="primary", use_container_width=True):
            customer_core.decide_reschedule(get_conn, rid, int(uid), True, note, logger); st.rerun()
        if b.button("✕ Từ chối", key=f"room_cr_no_{rid}", use_container_width=True):
            customer_core.decide_reschedule(get_conn, rid, int(uid), False, note, logger); st.rerun()


def _weekly_move_card(st, policy, get_conn, req, uid):
    rid = int(req.get("id") or 0)
    with get_conn() as c:
        row = c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (int(req.get("item_id") or 0),)).fetchone()
        item = dict(row) if row else {}
        owner = item.get("owner_name_snapshot") or _user_name(c, item.get("user_id"))
    q = int(item.get("priority_quadrant") or 4)
    qlabel = policy.PRIORITY_SHORT.get(q, f"Q{q}")
    customer = item.get("customer_text") or "Công việc nội bộ"
    with st.container(key=f"room_week_move_{rid}", border=True):
        st.markdown(f"**{_esc(customer)} · {_esc(item.get('title') or 'Công việc')}**")
        st.caption(
            f"👤 {owner or '—'} · 🎯 {qlabel} · Trạng thái {item.get('status') or 'PLANNED'} · "
            f"Dự kiến hoàn thành {_dmy(item.get('expected_complete_date'))}"
        )
        _change_strip(
            st,
            "THAY ĐỔI NGÀY THỰC HIỆN KẾ HOẠCH",
            _dmy(req.get("old_work_date")),
            _dmy(req.get("proposed_work_date")),
            req.get("reason") or "—",
            f"wpm-{rid}",
        )
        st.caption(f"Người đề nghị: {req.get('requester_name') or '—'} · Gửi lúc {_dt(req.get('requested_at'))}")
        note = st.text_input("Ý kiến phê duyệt", key=f"room_wr_note_{rid}")
        a, b = st.columns(2)
        if a.button("✓ Phê duyệt", key=f"room_wr_yes_{rid}", type="primary", use_container_width=True):
            ts = policy._now()
            with get_conn() as c:
                c.execute("UPDATE weekly_plan_reschedule_requests SET status='APPROVED',decided_by=?,decided_at=?,decision_note=? WHERE id=?", (int(uid), ts, note, rid))
                c.execute("UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?", (req.get("proposed_work_date"), ts, int(req.get("item_id") or 0)))
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_APPROVE',?,?)", (int(req.get("item_id") or 0), int(uid), note, ts))
            st.rerun()
        if b.button("✕ Từ chối", key=f"room_wr_no_{rid}", use_container_width=True):
            ts = policy._now()
            with get_conn() as c:
                c.execute("UPDATE weekly_plan_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,decision_note=? WHERE id=?", (int(uid), ts, note, rid))
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_REJECT',?,?)", (int(req.get("item_id") or 0), int(uid), note, ts))
            st.rerun()


def _render_approval_center(st, u, policy, weekly_core, customer_core, customer_ui, get_conn, logger=None):
    if not policy._manager(u):
        return
    policy._ensure_schema(weekly_core, get_conn, logger)
    customer_core.ensure_schema(get_conn, logger)
    uid = int(policy._uget(u, "id")); admin = policy._is_admin(u)
    with get_conn() as c:
        cases, moves = customer_core.pending_case_approvals(c)
        cases = [x for x in cases if policy._direct_scope_ok(c, uid, int(x.get("owner_user_id") or 0), admin)]
        plans = [dict(r) for r in c.execute("""SELECT p.*,u.full_name,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.workflow_status='DA_NOP' ORDER BY p.week_start,u.full_name""").fetchall()]
        plans = [p for p in plans if policy._direct_scope_ok(c, uid, int(p.get("user_id") or 0), admin)]
        wmoves = [dict(r) for r in c.execute("""SELECT r.*,w.user_id,u.full_name AS requester_name FROM weekly_plan_reschedule_requests r JOIN weekly_plan_items w ON w.id=r.item_id JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
        wmoves = [r for r in wmoves if policy._direct_scope_ok(c, uid, int(r.get("user_id") or r.get("requested_by") or 0), admin)]
        scoped_moves = []
        for r in moves:
            owner = c.execute("SELECT owner_user_id FROM customer_work_cases WHERE id=?", (int(r.get("case_id") or 0),)).fetchone()
            if owner and policy._direct_scope_ok(c, uid, int(owner[0]), admin): scoped_moves.append(r)
        moves = scoped_moves

    total = len(cases) + len(moves) + len(plans) + len(wmoves)
    st.divider(); st.markdown("## ✅ Phê duyệt kế hoạch / dời hạn")
    st.caption(f"{total} nội dung đang chờ xử lý. Các đề nghị dời chỉ nhấn mạnh phần thay đổi để lãnh đạo quyết định nhanh.")

    st.subheader("Công việc khách hàng mới")
    if not cases: st.caption("Không có công việc khách hàng chờ phê duyệt.")
    for x in cases: consolidation._render_case_approval_card(st, policy, customer_core, get_conn, x, uid, logger)

    st.subheader("Kế hoạch tuần đã nộp")
    if not plans: st.caption("Không có kế hoạch tuần chờ duyệt.")
    for p in plans:
        ws = date.fromisoformat(str(p.get("week_start"))[:10])
        with get_conn() as c:
            items = [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id", (int(p["id"]),)).fetchall()]
            scope = policy._scope_key(c, int(p["user_id"])); cats = policy._focus_categories(c, scope, ws.year, False)
        with st.expander(f"{p.get('full_name')} · tuần {ws:%d/%m/%Y} · {len(items)} việc", expanded=True):
            policy._summary(st, items); policy._inline_focus_create(st, u, get_conn, ws.year, logger)
            for x in items:
                consolidation._render_weekly_item_full(st, policy, x)
                policy._manager_classification_editor(st, u, weekly_core, get_conn, p, x, cats, logger)
            decision = st.text_area("Ý kiến duyệt / lý do trả lại", key=f"room_plan_note_{p['id']}")
            a, b = st.columns(2)
            if a.button("✓ Phê duyệt kế hoạch", key=f"room_plan_yes_{p['id']}", type="primary", use_container_width=True):
                ts = policy._now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET',approved_at=?,approved_by=?,return_note=NULL,updated_at=? WHERE id=?", (ts, uid, ts, int(p["id"])))
                    c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE plan_id=? AND status<>'CANCELLED'", (uid, ts, int(p["id"])))
                    policy._notify(c, int(p["user_id"]), "✅ Kế hoạch tuần đã được duyệt", f"Tuần {ws:%d/%m/%Y}. {decision or ''}".strip())
                st.rerun()
            if b.button("↩ Trả lại điều chỉnh", key=f"room_plan_back_{p['id']}", use_container_width=True, disabled=not decision.strip()):
                ts = policy._now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='TRA_LAI',returned_at=?,returned_by=?,return_note=?,updated_at=? WHERE id=?", (ts, uid, decision.strip(), ts, int(p["id"])))
                    policy._notify(c, int(p["user_id"]), "↩ Kế hoạch tuần được trả lại", decision.strip())
                st.rerun()

    st.subheader("Đề nghị dời công việc khách hàng")
    if not moves: st.caption("Không có đề nghị dời ngày công việc khách hàng.")
    for r in moves: _render_case_move_card(st, customer_core, customer_ui, get_conn, r, uid, logger)

    st.subheader("Đề nghị dời kế hoạch tuần")
    if not wmoves: st.caption("Không có đề nghị dời kế hoạch tuần.")
    for r in wmoves: _weekly_move_card(st, policy, get_conn, r, uid)


def install(policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None, **kwargs):
        customer_core.ensure_schema(get_conn, logger)
        uid = int(policy._uget(u, "id"))
        if page_title: page_title("Điều hành công việc phòng", "Tình hình thực hiện kế hoạch, tồn đọng, cảnh báo và ưu tiên")
        else: st.title("📊 Điều hành công việc phòng")
        with get_conn() as c:
            data = customer_core.list_cases(c, manager=True, include_completed=False)
            plans, reschedules = customer_core.pending_case_approvals(c)
            today = date.today().isoformat()
            try:
                wp_today = [dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE work_date=? AND status<>'CANCELLED' AND COALESCE(approval_status,'APPROVED')='APPROVED'", (today,)).fetchall()]
                wp_plan = int(c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE approval_status='PENDING'").fetchone()[0])
                wp_move = int(c.execute("SELECT COUNT(*) FROM weekly_plan_reschedule_requests WHERE status='PENDING'").fetchone()[0])
            except Exception:
                wp_today = []; wp_plan = wp_move = 0
        delayed = [x for x in data if x.get("is_stage_delayed")]
        overdue = [x for x in data if x.get("is_overdue")]
        blocked = [x for x in data if int(x.get("open_issue_count") or 0) > 0]
        a,b,c,d,e = st.columns(5)
        a.metric("Đang xử lý", len(data)); b.metric("Kế hoạch hôm nay", len(wp_today)); c.metric("Quá hạn", len(overdue)); d.metric("Mục bị chậm", len(delayed)); e.metric("Chờ phê duyệt", len(plans)+len(reschedules)+wp_plan+wp_move)

        st.subheader("Theo mục công việc")
        stage_rows=[]
        for name in sorted({x.get("stage_name") for x in data if x.get("stage_name")}):
            arr=[x for x in data if x.get("stage_name")==name]
            stage_rows.append([name,len(arr),sum(bool(z.get("is_stage_delayed")) for z in arr),sum(int(z.get("open_issue_count") or 0)>0 for z in arr),sum(bool(z.get("is_overdue")) for z in arr)])
        customer_ui._html_table(st,["Mục công việc","Số việc","Bị chậm","Có vướng mắc","Quá hạn"],stage_rows)

        st.subheader("Theo cán bộ")
        staff={}
        for x in data:
            k=x.get("owner_name") or "—"; r=staff.setdefault(k,[0,0,0,0]); r[0]+=1; r[1]+=int(bool(x.get("is_stage_delayed"))); r[2]+=int(bool(x.get("is_overdue"))); r[3]+=int(int(x.get("open_issue_count") or 0)>0)
        customer_ui._html_table(st,["Cán bộ","Đang xử lý","Bị chậm","Quá hạn","Có vướng mắc"],[[k]+v for k,v in sorted(staff.items())])

        _render_room_priority(st, customer_ui, data)

        if overdue or delayed or blocked:
            st.subheader("⚠ Danh sách cần chú ý")
            _render_attention_table(st, customer_ui, overdue+delayed+blocked)

        customer_ui._glossary(st)
        _render_approval_center(st, u, policy, weekly_core, customer_core, customer_ui, get_conn, logger)

    customer_ui.render_leader_dashboard = render_leader_dashboard
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info("PLANNING_ROOM_DASHBOARD_DETAIL_INSTALLED version=%s room_priority_detail=1 compact_reschedule_cards=1 highlighted_changes=1", VERSION)
