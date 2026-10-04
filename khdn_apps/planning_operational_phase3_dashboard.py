"""Operational planning Phase 3 Today, room dashboard and approval center."""
from __future__ import annotations

from datetime import date, datetime
import json

from khdn_apps import planning_room_dashboard_detail_patch as room_dashboard
from khdn_apps import planning_dashboard_consolidation_patch as consolidation
from khdn_apps import priority_today_patch as priority_today
from khdn_apps import weekly_performance_phase2_patch as phase2
from khdn_apps.planning_operational_phase3_core import esc, dmy, dt, ensure_schema
from khdn_apps.planning_operational_phase3_weekly import weekly_card, render_week_board, render_week_update_form, manager_edit_item


def _today_weekly_rows(c, uid, manager):
    base = """SELECT w.*,u.full_name AS owner_name,c.customer_name AS master_customer_name,p.workflow_status
              FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id JOIN users u ON u.id=w.user_id
              LEFT JOIN customers c ON c.id=w.customer_id
              WHERE w.status NOT IN ('DONE','CANCELLED') AND COALESCE(w.approval_status,'APPROVED')='APPROVED'"""
    if manager:
        return [dict(r) for r in c.execute(base + " ORDER BY w.work_date,w.id").fetchall()]
    return [dict(r) for r in c.execute(base + " AND w.user_id=? ORDER BY w.work_date,w.id", (int(uid),)).fetchall()]


def install_today_page(customer_ui, customer_core, policy, weekly_core, logger=None):
    def render_today_page(st, u, get_conn, page_title=None, logger=None, **kwargs):
        customer_core.ensure_schema(get_conn, logger)
        phase2._ensure_schema(policy, weekly_core, get_conn, logger)
        uid = int(policy._uget(u,"id")); manager = policy._manager(u)
        if page_title: page_title("Hôm nay", "Việc phải làm hôm nay, tồn đọng và thứ tự ưu tiên")
        else: st.title("🏠 Hôm nay")
        if st.session_state.get("cw_case_id"):
            customer_ui._case_detail(st, u, get_conn, int(st.session_state["cw_case_id"]), logger)
            customer_ui._glossary(st)
            return
        today = date.today().isoformat()
        with get_conn() as c:
            cases = customer_core.list_cases(c, uid=uid, manager=manager, include_completed=False)
            wp = _today_weekly_rows(c, uid, manager)
        due_today = sorted([x for x in cases if str(x.get("expected_complete_at") or "")[:10] == today], key=lambda x: priority_today._priority_sort_key(customer_core,x))
        backlog = sorted([x for x in cases if x.get("is_overdue") or x.get("is_stage_delayed") or int(x.get("open_issue_count") or 0)>0], key=lambda x: priority_today._priority_sort_key(customer_core,x))
        today_plan = [x for x in wp if str(x.get("work_date") or "")[:10] == today]
        plan_backlog = [x for x in wp if str(x.get("work_date") or "")[:10] < today]
        a,b,c,d = st.columns(4)
        a.metric("Việc hôm nay", len(today_plan)+len(due_today)); b.metric("Tồn đọng",len(backlog)+len(plan_backlog)); c.metric("Đang vướng mắc",sum(int(x.get("open_issue_count") or 0)>0 for x in cases)); d.metric("Chờ phê duyệt",sum(x.get("plan_approval_status")=="PENDING" for x in cases))
        priority_today._render_priority_heatmap(st, customer_ui, cases, get_conn, uid, manager, logger)
        st.subheader("📅 Công việc theo kế hoạch hôm nay")
        if not today_plan and not due_today: st.info("Hôm nay chưa có công việc đã được phê duyệt.")
        for x in today_plan:
            weekly_card(st, policy, weekly_core, x, f"today_{uid}", can_update=(not manager and int(x.get("user_id") or 0)==uid and str(x.get("workflow_status") or "")=="DA_DUYET"))
        for x in due_today:
            customer_ui._case_card(st, x, get_conn, uid, manager, logger, compact=False)
        selected = st.session_state.get("p3_update_week_item")
        if selected and not manager:
            item = next((x for x in wp if int(x.get("id") or 0)==int(selected)), None)
            if item: render_week_update_form(st,u,policy,weekly_core,get_conn,item,logger)
        st.subheader("⏳ Công việc còn tồn đọng")
        if not backlog and not plan_backlog: st.success("Không có công việc tồn đọng.")
        for x in backlog:
            customer_ui._case_card(st, x, get_conn, uid, manager, logger, compact=False)
        for x in plan_backlog:
            weekly_card(st, policy, weekly_core, x, f"backlog_{uid}", can_update=(not manager and int(x.get("user_id") or 0)==uid and str(x.get("workflow_status") or "")=="DA_DUYET"))
            st.error("Quá ngày kế hoạch nhưng chưa hoàn thành.")
        customer_ui._glossary(st)
        if not manager:
            phase2._render_personal_performance(st, u, policy, weekly_core, get_conn)
    customer_ui.render_today_page = render_today_page
    if logger: logger.info("PLANNING_TODAY_RICH_CARDS_V3_INSTALLED")


def _attention_dashboard(st, u, policy, customer_core, get_conn, logger=None):
    uid = int(policy._uget(u,"id")); admin = policy._is_admin(u)
    with get_conn() as c:
        rows = [dict(r) for r in c.execute("""SELECT e.*,cw.owner_user_id,c.customer_name,u.full_name actor_name,
            s.name stage_name,i.resolved_at,i.resolution_text FROM planning_attention_events e
            JOIN customer_work_cases cw ON cw.id=e.case_id JOIN customers c ON c.id=cw.customer_id
            LEFT JOIN users u ON u.id=e.actor_user_id LEFT JOIN work_stage_catalog s ON s.id=cw.current_stage_id
            LEFT JOIN case_issues i ON e.event_type='ISSUE_OPEN' AND i.id=e.source_id
            WHERE e.status='OPEN' ORDER BY e.created_at DESC,e.id DESC""").fetchall()]
        rows = [r for r in rows if policy._direct_scope_ok(c,uid,int(r.get("owner_user_id") or 0),admin)]
    st.markdown("## 🔔 Cập nhật tiến độ / vướng mắc chờ lãnh đạo xử lý")
    if not rows:
        st.success("Không có cập nhật mới đang chờ xác nhận.")
        return
    for r in rows:
        eid = int(r["id"]); issue = str(r.get("event_type")) == "ISSUE_OPEN"
        try: detail = json.loads(r.get("detail") or "{}")
        except Exception: detail = {"text":r.get("detail")}
        headline = "⚠ VƯỚNG MẮC" if issue else "🔄 CẬP NHẬT TIẾN ĐỘ"
        body = detail.get("issue") if issue else f"{detail.get('from_stage','—')} → {detail.get('to_stage','—')}"
        note = detail.get("stage") if issue else detail.get("note")
        cls = "p3-attn-issue" if issue else "p3-attn-stage"
        st.html(f"""<div class='p3-attn {cls}'><div class='p3-attn-head'>{headline} · {esc(r.get('title'))}</div>
        <div class='p3-attn-main'>{esc(body)}</div><div class='p3-attn-note'>{esc(note or '')}</div>
        <div class='p3-attn-meta'>{esc(r.get('actor_name'))} · {esc(dt(r.get('created_at')))} · Mục hiện tại: {esc(r.get('stage_name'))}</div></div>
        <style>.p3-attn{{padding:11px 13px;border-radius:11px;margin:8px 0;white-space:normal;overflow-wrap:anywhere}}
        .p3-attn-stage{{border:1px solid #F4B41A;border-left:7px solid #F4B41A;background:rgba(244,180,26,.13)}}
        .p3-attn-issue{{border:1px solid #F04438;border-left:7px solid #F04438;background:rgba(240,68,56,.13)}}
        .p3-attn-head{{font-size:.83rem;font-weight:950;color:#FFD166}}.p3-attn-main{{font-size:.95rem;font-weight:950;margin-top:4px;color:#fff}}
        .p3-attn-note{{font-size:.82rem;font-weight:850;margin-top:3px;color:#63DCCB}}.p3-attn-meta{{font-size:.73rem;opacity:.82;margin-top:5px}}</style>""")
        ack_note = st.text_input("Nội dung xử lý / ghi nhận" if issue else "Ghi nhận của lãnh đạo", key=f"p3_attn_note_{eid}")
        if st.button("✓ Đã xử lý" if issue else "✓ Đã xem", key=f"p3_attn_ack_{eid}", type="primary", use_container_width=True):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if issue and not r.get("resolved_at"):
                customer_core.resolve_issue(get_conn, int(r["source_id"]), uid, str(ack_note or "").strip(), logger)
            with get_conn() as c:
                c.execute("UPDATE planning_attention_events SET status='ACKED',acknowledged_at=?,acknowledged_by=?,acknowledgement_note=?,updated_at=? WHERE id=?",
                          (ts,uid,str(ack_note or "").strip(),ts,eid))
            if logger: logger.info("P3_ATTENTION_ACK event=%s actor=%s type=%s",eid,uid,r.get("event_type"))
            st.rerun()


def _list_items(arr, flag=None):
    out=[]
    for x in arr:
        if flag and not flag(x): continue
        bits=[str(x.get("customer_name") or "—"),str(x.get("title") or "Công việc")]
        if x.get("owner_name"): bits.append(str(x.get("owner_name")))
        out.append(" · ".join(bits))
    return out


WORKLOAD_GROUP_NOTE = (
    "Mỗi công việc chỉ xuất hiện ở một cột. Khi có nhiều cảnh báo, ưu tiên: "
    "Quá hạn → Có vướng mắc → Bị chậm → Đang xử lý. "
    "Đang xử lý là công việc chưa có các cảnh báo trên."
)


def _workload_bucket(case):
    """Choose one table column; all original warning flags stay available."""
    if case.get("is_overdue"):
        return "OVERDUE"
    if int(case.get("open_issue_count") or 0) > 0:
        return "ISSUES"
    if case.get("is_stage_delayed"):
        return "DELAYED"
    return "PROCESSING"


def _workload_lists(arr, order=("PROCESSING", "DELAYED", "ISSUES", "OVERDUE")):
    groups = {key: [] for key in order}
    for case in arr:
        groups[_workload_bucket(case)].append(case)
    # Partition by work identity, never by rendered text: separate works can
    # legitimately have the same customer, title and owner.
    return [_list_items(groups[key]) for key in order]


def _matrix_table(st, heads, rows):
    def cell(v):
        if isinstance(v,list):
            return "<span class='p3-empty'>—</span>" if not v else "".join(f"<div class='p3-list-item'>• {esc(x)}</div>" for x in v)
        return esc(v)
    h="".join(f"<th>{esc(x)}</th>" for x in heads)
    b="".join("<tr>"+"".join(f"<td>{cell(v)}</td>" for v in row)+"</tr>" for row in rows)
    st.html(f"""<div class='p3-table'><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>
    <style>.p3-table{{overflow-x:auto;width:100%}}.p3-table table{{width:100%;table-layout:fixed;border-collapse:collapse}}
    .p3-table th,.p3-table td{{padding:8px 9px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere;font-size:.78rem}}
    .p3-table th{{font-weight:950;color:#63DCCB}}.p3-list-item{{margin:2px 0;padding:2px 0;border-bottom:1px dashed rgba(120,160,150,.18)}}.p3-empty{{opacity:.5}}</style>""")


def _attention_cards(st, data):
    seen=set()
    ordered=sorted(data,key=lambda z:(0 if z.get('is_overdue') else 1,0 if int(z.get('open_issue_count') or 0)>0 else 1,0 if z.get('is_stage_delayed') else 1,str(z.get('expected_complete_at') or '')))
    for x in ordered:
        iid=int(x.get("id") or 0)
        if iid in seen: continue
        seen.add(iid)
        overdue=bool(x.get("is_overdue")); issues=int(x.get("open_issue_count") or 0); delayed=bool(x.get("is_stage_delayed"))
        accent="#F04438" if overdue or delayed else "#F79009" if issues else "#F4B41A"
        flags=[]
        if overdue: flags.append("QUÁ HẠN")
        if delayed: flags.append("MỤC BỊ CHẬM")
        if issues: flags.append(f"{issues} VƯỚNG MẮC")
        st.html(f"""<div class='p3-watch' style='border-left-color:{accent}'><div class='p3-watch-title'>{esc(x.get('customer_name'))} · {esc(x.get('title'))}</div>
        <div class='p3-watch-flags' style='color:{accent}'>{esc(' · '.join(flags))}</div><div class='p3-watch-meta'>👤 {esc(x.get('owner_name'))} · 📍 {esc(x.get('stage_name'))} · 🎯 {esc(dmy(x.get('expected_complete_at')))}</div></div>
        <style>.p3-watch{{border:1px solid rgba(240,68,56,.35);border-left:7px solid;border-radius:11px;padding:10px 12px;margin:7px 0;background:rgba(240,68,56,.07)}}
        .p3-watch-title{{font-weight:950;color:#fff}}.p3-watch-flags{{font-weight:950;font-size:.82rem;margin-top:4px}}.p3-watch-meta{{font-size:.76rem;margin-top:5px}}</style>""")


def approval_center(st,u,policy,weekly_core,customer_core,customer_ui,get_conn,logger=None):
    if not policy._manager(u): return
    phase2._ensure_schema(policy,weekly_core,get_conn,logger); customer_core.ensure_schema(get_conn,logger); ensure_schema(get_conn,logger)
    phase2._render_manager_reviews(st,u,policy,weekly_core,get_conn,logger)
    phase2._render_room_performance(st,u,policy,weekly_core,get_conn)
    uid=int(policy._uget(u,"id")); admin=policy._is_admin(u)
    with get_conn() as c:
        cases,moves=customer_core.pending_case_approvals(c)
        cases=[x for x in cases if policy._direct_scope_ok(c,uid,int(x.get("owner_user_id") or 0),admin)]
        plans=[dict(r) for r in c.execute("SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.workflow_status='DA_NOP' ORDER BY p.week_start,u.full_name").fetchall()]
        plans=[p for p in plans if policy._direct_scope_ok(c,uid,int(p["user_id"]),admin)]
        wmoves=[dict(r) for r in c.execute("SELECT r.*,w.user_id,u.full_name requester_name FROM weekly_plan_reschedule_requests r JOIN weekly_plan_items w ON w.id=r.item_id JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id").fetchall()]
        wmoves=[r for r in wmoves if policy._direct_scope_ok(c,uid,int(r.get("user_id") or r.get("requested_by") or 0),admin)]
        scoped=[]
        for r in moves:
            owner=c.execute("SELECT owner_user_id FROM customer_work_cases WHERE id=?",(int(r.get("case_id") or 0),)).fetchone()
            if owner and policy._direct_scope_ok(c,uid,int(owner[0]),admin): scoped.append(r)
        moves=scoped
    st.divider(); st.markdown("## ✅ Phê duyệt kế hoạch / dời hạn")
    st.subheader("Công việc khách hàng mới")
    if not cases: st.caption("Không có công việc khách hàng chờ phê duyệt.")
    for x in cases: consolidation._render_case_approval_card(st,policy,customer_core,get_conn,x,uid,logger)
    st.subheader("Kế hoạch tuần đã nộp")
    if not plans: st.caption("Không có kế hoạch tuần chờ duyệt.")
    for p in plans:
        ws=date.fromisoformat(str(p["week_start"])[:10])
        with get_conn() as c:
            items=[dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE plan_id=? AND status<>'CANCELLED' ORDER BY work_date,id",(int(p["id"]),)).fetchall()]
            focus=policy._focus_categories(c,policy._scope_key(c,int(p["user_id"])),ws.year,False)
        with st.expander(f"{p.get('full_name')} · tuần {ws:%d/%m/%Y} · {len(items)} việc",expanded=True):
            policy._summary(st,items)
            render_week_board(st,policy,weekly_core,get_conn,int(p["user_id"]),ws,items,"DA_NOP",manager_edit=True)
            selected=st.session_state.get("p3_manager_edit_week_item")
            if selected:
                item=next((x for x in items if int(x.get("id") or 0)==int(selected)),None)
                if item: manager_edit_item(st,u,policy,weekly_core,get_conn,p,item,focus,logger)
            decision=st.text_area("Ý kiến duyệt / lý do trả lại",key=f"p3_plan_note_{p['id']}")
            a,b=st.columns(2)
            if a.button("✓ Phê duyệt kế hoạch",key=f"p3_plan_yes_{p['id']}",type="primary",use_container_width=True):
                ts=policy._now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='DA_DUYET',approved_at=?,approved_by=?,return_note=NULL,updated_at=? WHERE id=?",(ts,uid,ts,int(p["id"])))
                    c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=? WHERE plan_id=? AND status<>'CANCELLED'",(uid,ts,int(p["id"])))
                    policy._notify(c,int(p["user_id"]),"✅ Kế hoạch tuần đã được duyệt",f"Tuần {ws:%d/%m/%Y}. {decision or ''}".strip())
                st.rerun()
            if b.button("↩ Trả lại điều chỉnh",key=f"p3_plan_back_{p['id']}",use_container_width=True,disabled=not decision.strip()):
                ts=policy._now()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plans SET workflow_status='TRA_LAI',returned_at=?,returned_by=?,return_note=?,updated_at=? WHERE id=?",(ts,uid,decision.strip(),ts,int(p["id"])))
                    policy._notify(c,int(p["user_id"]),"↩ Kế hoạch tuần được trả lại",decision.strip())
                st.rerun()
    st.subheader("Đề nghị dời công việc khách hàng")
    if not moves: st.caption("Không có đề nghị dời ngày công việc khách hàng.")
    for r in moves: room_dashboard._render_case_move_card(st,customer_core,customer_ui,get_conn,r,uid,logger)
    st.subheader("Đề nghị dời kế hoạch tuần")
    if not wmoves: st.caption("Không có đề nghị dời kế hoạch tuần.")
    for r in wmoves: room_dashboard._weekly_move_card(st,policy,get_conn,r,uid)


def install_room_dashboard(customer_ui, customer_core, policy, weekly_core, logger=None):
    room_dashboard._render_approval_center = approval_center

    def render_leader_dashboard(st,u,get_conn,page_title=None,logger=None,**kwargs):
        customer_core.ensure_schema(get_conn,logger); phase2._ensure_schema(policy,weekly_core,get_conn,logger); ensure_schema(get_conn,logger)
        uid=int(policy._uget(u,"id")); admin=policy._is_admin(u)
        if page_title: page_title("Điều hành công việc phòng","Tình hình thực hiện kế hoạch, cập nhật mới, tồn đọng, cảnh báo và ưu tiên")
        else: st.title("📊 Điều hành công việc phòng")
        with get_conn() as c:
            data=customer_core.list_cases(c,manager=True,include_completed=False)
            data=[x for x in data if policy._direct_scope_ok(c,uid,int(x.get("owner_user_id") or 0),admin)]
            plans,reschedules=customer_core.pending_case_approvals(c)
            today=date.today().isoformat()
            try:
                wp_today=[dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE work_date=? AND status<>'CANCELLED' AND COALESCE(approval_status,'APPROVED')='APPROVED'",(today,)).fetchall()]
                wp_today=[x for x in wp_today if policy._direct_scope_ok(c,uid,int(x.get("user_id") or 0),admin)]
                wp_plan=int(c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE approval_status='PENDING'").fetchone()[0]); wp_move=int(c.execute("SELECT COUNT(*) FROM weekly_plan_reschedule_requests WHERE status='PENDING'").fetchone()[0])
            except Exception: wp_today=[]; wp_plan=wp_move=0
        delayed=[x for x in data if x.get("is_stage_delayed")]; overdue=[x for x in data if x.get("is_overdue")]; blocked=[x for x in data if int(x.get("open_issue_count") or 0)>0]
        a,b,c,d,e=st.columns(5); a.metric("Đang xử lý",len(data)); b.metric("Kế hoạch hôm nay",len(wp_today)); c.metric("Quá hạn",len(overdue)); d.metric("Mục bị chậm",len(delayed)); e.metric("Chờ phê duyệt",len(plans)+len(reschedules)+wp_plan+wp_move)
        _attention_dashboard(st,u,policy,customer_core,get_conn,logger)
        st.caption(WORKLOAD_GROUP_NOTE)
        st.subheader("Theo mục công việc · danh sách khách hàng")
        stage_rows=[]
        for name in sorted({x.get("stage_name") for x in data if x.get("stage_name")}):
            arr=[x for x in data if x.get("stage_name")==name]
            stage_rows.append([name,*_workload_lists(arr)])
        _matrix_table(st,["Mục công việc","Đang xử lý","Bị chậm","Có vướng mắc","Quá hạn"],stage_rows)
        st.subheader("Theo cán bộ · danh sách khách hàng")
        staff_rows=[]
        for name in sorted({x.get("owner_name") or "—" for x in data}):
            arr=[x for x in data if (x.get("owner_name") or "—")==name]
            staff_rows.append([name,*_workload_lists(arr,("PROCESSING","DELAYED","OVERDUE","ISSUES"))])
        _matrix_table(st,["Cán bộ","Đang xử lý","Bị chậm","Quá hạn","Có vướng mắc"],staff_rows)
        room_dashboard._render_room_priority(st,customer_ui,data)
        if overdue or delayed or blocked:
            st.subheader("⚠ Danh sách cần chú ý"); _attention_cards(st,overdue+delayed+blocked)
        customer_ui._glossary(st)
        room_dashboard._render_approval_center(st,u,policy,weekly_core,customer_core,customer_ui,get_conn,logger)
    customer_ui.render_leader_dashboard=render_leader_dashboard
    if logger: logger.info("PLANNING_ROOM_DETAIL_LISTS_V3_INSTALLED")
