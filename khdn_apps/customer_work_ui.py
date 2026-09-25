from __future__ import annotations

import html
from datetime import date, datetime, time, timedelta

from khdn_apps import customer_work as core

VERSION = "2.0.0"


def _manager(u):
    return str(u.get("role") or "") == "Lãnh đạo phòng" or bool(u.get("is_admin"))


def _dt_text(v):
    if not v:
        return "—"
    try:
        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(v)


def _date_text(v):
    if not v:
        return "—"
    try:
        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y")
    except Exception:
        return str(v)[:10]


def _html_table(st, heads, rows, widths=None):
    esc=lambda v: html.escape("" if v is None else str(v))
    if widths:
        colgroup="<colgroup>"+"".join(f'<col style="width:{w}">' for w in widths)+"</colgroup>"
    else:
        colgroup=""
    h="".join(f"<th>{esc(x)}</th>" for x in heads)
    b="".join("<tr>"+"".join(f"<td>{esc(x)}</td>" for x in r)+"</tr>" for r in rows)
    st.html(
        f'''<div class="cw-table-wrap"><table>{colgroup}<thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>
        <style>
        .cw-table-wrap{{overflow-x:auto;width:100%;}}
        .cw-table-wrap table{{width:100%;table-layout:fixed;border-collapse:collapse;}}
        .cw-table-wrap th,.cw-table-wrap td{{padding:8px 9px;border:1px solid rgba(120,160,150,.28);vertical-align:top;white-space:normal;overflow-wrap:anywhere;}}
        .cw-table-wrap th{{font-weight:800;}}
        </style>'''
    )


def _glossary(st):
    with st.expander("ⓘ Thuật ngữ sử dụng trong màn hình này"):
        st.markdown(
            "**Mục công việc (Stage):** bước hiện tại của một công việc khách hàng.  "
            "\n**SLA:** ngưỡng thời gian chuẩn của từng mục công việc; Lãnh đạo/Admin có thể thay đổi.  "
            "\n**Tồn đọng:** công việc chưa hoàn thành và đã quá hạn hoặc mục công việc đang bị chậm.  "
            "\n**Vướng mắc:** vấn đề phát sinh được ghi nhận kèm thời điểm và mục công việc.  "
            "\n**Góc phần tư:** mô hình ưu tiên Quan trọng/Khẩn cấp; tính Quan trọng chỉ do Lãnh đạo/Admin gán."
        )


def _warn_text(x):
    if x.get("is_stage_delayed"):
        return "🔴 Chậm"
    if x.get("is_stage_warning"):
        return "🟠 Sắp chậm"
    return "🟢 Trong hạn"


def _priority_text(x):
    return core.quadrant_label(x.get("quadrant"))


def _case_card(st, x, get_conn, uid, manager, logger=None, compact=False):
    with st.container(border=True):
        top1, top2 = st.columns([4, 1])
        top1.markdown(f"**{html.escape(str(x.get('customer_name') or ''))} · {html.escape(str(x.get('title') or ''))}**")
        top2.caption(str(x.get("case_code") or ""))
        st.caption(
            f"👤 {x.get('owner_name') or '—'} · 📍 {x.get('stage_name') or '—'} · "
            f"⏱ {core.duration_text(x.get('stage_elapsed_hours'))} · {_warn_text(x)}"
        )
        st.caption(
            f"🎯 Dự kiến hoàn thành: {_dt_text(x.get('expected_complete_at'))} · "
            f"⚠ Vướng mắc mở: {int(x.get('open_issue_count') or 0)} · {_priority_text(x)}"
        )
        approval=str(x.get("plan_approval_status") or "PENDING")
        if approval == "PENDING": st.warning("Kế hoạch công việc đang chờ phê duyệt.")
        elif approval == "REJECTED": st.error("Kế hoạch đã bị từ chối." + (f" {x.get('approval_note')}" if x.get("approval_note") else ""))
        if not compact and st.button("Mở chi tiết", key=f"cw_open_{x['id']}", use_container_width=True):
            st.session_state["cw_case_id"] = int(x["id"])
            st.rerun()


def render_today_page(st, u, get_conn, page_title=None, logger=None):
    core.ensure_schema(get_conn, logger)
    uid=int(u["id"])
    if page_title: page_title("Hôm nay", "Việc phải làm hôm nay và các công việc còn tồn đọng")
    else: st.title("🏠 Hôm nay")
    today=date.today().isoformat()
    with get_conn() as c:
        cases=core.list_cases(c,uid=uid,manager=False,include_completed=False)
        wp=[]
        try:
            wp=[dict(r) for r in c.execute("""SELECT * FROM weekly_plan_items WHERE user_id=? AND status NOT IN ('DONE','CANCELLED') AND COALESCE(approval_status,'APPROVED')='APPROVED' ORDER BY work_date,COALESCE(start_time,'99:99'),id""",(uid,)).fetchall()]
        except Exception:
            wp=[]
    due_today=[x for x in cases if str(x.get("expected_complete_at") or "")[:10]==today]
    backlog=[x for x in cases if x.get("is_overdue") or x.get("is_stage_delayed") or int(x.get("open_issue_count") or 0)>0]
    today_plan=[x for x in wp if str(x.get("work_date") or "")[:10]==today]
    plan_backlog=[x for x in wp if str(x.get("work_date") or "")[:10] < today]
    pending=sum(1 for x in cases if x.get("plan_approval_status")=="PENDING")
    a,b,c,d=st.columns(4)
    a.metric("Việc hôm nay",len(today_plan)+len(due_today))
    b.metric("Tồn đọng",len(backlog)+len(plan_backlog))
    c.metric("Đang vướng mắc",sum(int(x.get("open_issue_count") or 0)>0 for x in cases))
    d.metric("Chờ phê duyệt",pending)
    st.subheader("📅 Công việc theo kế hoạch hôm nay")
    if not today_plan and not due_today: st.info("Hôm nay chưa có công việc đã được phê duyệt.")
    for x in today_plan:
        with st.container(border=True):
            st.markdown(f"**{html.escape(str(x.get('title') or ''))}**")
            st.caption(f"{x.get('start_time') or x.get('daypart') or 'Cả ngày'} · {x.get('customer_text') or 'Công việc nội bộ'} · {x.get('category') or ''}")
    for x in due_today: _case_card(st,x,get_conn,uid,False,logger,compact=True)
    st.subheader("⏳ Công việc còn tồn đọng")
    if not backlog and not plan_backlog: st.success("Không có công việc tồn đọng.")
    for x in backlog: _case_card(st,x,get_conn,uid,False,logger,compact=True)
    for x in plan_backlog:
        with st.container(border=True):
            st.markdown(f"**📌 {html.escape(str(x.get('title') or ''))}**")
            st.caption(f"Kế hoạch ngày {_date_text(x.get('work_date'))} · {x.get('customer_text') or 'Công việc nội bộ'}")
            st.error("Quá ngày kế hoạch nhưng chưa hoàn thành.")
    _glossary(st)


def _create_case_form(st, u, get_conn, logger=None):
    uid=int(u["id"]); manager=_manager(u)
    with get_conn() as c:
        cs=core.customers(c,uid)
        stages=core.active_stages(c)
        users=core.staff_users(c) if manager else []
    if not cs:
        st.warning("Chưa có khách hàng đang hoạt động."); return
    with st.form("cw_create_case",clear_on_submit=True):
        customer=st.selectbox("Khách hàng",cs,format_func=lambda x:f"{x['customer_name']} · CIF {x['cif']}")
        title=st.text_input("Công việc",placeholder="Ví dụ: Hạn mức tín dụng 2026 / Dự án A / Tiếp thị tiền gửi")
        c1,c2=st.columns(2)
        due_date=c1.date_input("Dự kiến hoàn thành",value=date.today()+timedelta(days=7))
        due_time=c2.time_input("Giờ dự kiến",value=time(17,0))
        stage=st.selectbox("Mục công việc bắt đầu",stages,format_func=lambda x:x["name"])
        owner=st.selectbox("Cán bộ phụ trách",users,format_func=lambda x:f"{x['full_name']} · {x['role']}") if manager else None
        case_type=st.text_input("Nhóm công việc",placeholder="Tín dụng / Huy động / Dự án / Chăm sóc KH...")
        note=st.text_area("Ghi chú",height=80)
        ok=st.form_submit_button("Tạo công việc",type="primary",use_container_width=True)
    if ok:
        try:
            due=datetime.combine(due_date,due_time).strftime("%Y-%m-%d %H:%M:%S")
            cid,state=core.create_case(get_conn,uid,customer["id"],title,due,owner_uid=owner["id"] if owner else uid,case_type=case_type,note=note,stage_id=stage["id"],logger=logger)
            st.session_state["cw_case_id"]=cid
            st.toast("Đã tạo công việc." if state=="APPROVED" else "Đã gửi kế hoạch chờ Lãnh đạo/Admin phê duyệt.",icon="✅")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _case_detail(st, u, get_conn, case_id, logger=None):
    uid=int(u["id"]); manager=_manager(u)
    with get_conn() as c:
        x=core.get_case(c,case_id)
        stages=core.active_stages(c)
        cats=core.active_important_categories(c)
        hist=core.case_history(c,case_id)
        issues=core.case_issues(c,case_id,include_resolved=True)
    if not x:
        st.warning("Không tìm thấy công việc."); st.session_state.pop("cw_case_id",None); return
    if not manager and int(x.get("owner_user_id") or 0)!=uid:
        st.error("Bạn không có quyền xem công việc này."); return
    if st.button("← Danh sách công việc",key="cw_back_list"): st.session_state.pop("cw_case_id",None);st.rerun()
    _case_card(st,x,get_conn,uid,manager,logger,compact=True)
    if x.get("plan_approval_status")=="APPROVED" and x.get("status")!="COMPLETED":
        st.subheader("Cập nhật tiến độ")
        current_idx=next((i for i,s in enumerate(stages) if int(s["id"])==int(x.get("current_stage_id") or 0)),0)
        stage=st.selectbox("Chuyển sang mục công việc",stages,index=current_idx,format_func=lambda s:s["name"],key=f"cw_stage_{case_id}")
        stage_note=st.text_input("Ghi chú chuyển bước",key=f"cw_stage_note_{case_id}")
        if st.button("Cập nhật mục công việc",type="primary",key=f"cw_stage_save_{case_id}",use_container_width=True):
            try:
                core.change_stage(get_conn,case_id,uid,stage["id"],stage_note,logger);st.toast("Đã cập nhật tiến độ.",icon="✅");st.rerun()
            except Exception as exc: st.error(str(exc))
    st.subheader("Vướng mắc")
    active=[i for i in issues if not i.get("resolved_at")]
    if not active: st.caption("Chưa có vướng mắc đang mở.")
    for i in active:
        with st.container(border=True):
            st.markdown(f"**⚠ {html.escape(str(i.get('issue_text') or ''))}**")
            st.caption(f"{i.get('stage_name') or '—'} · {i.get('opened_by_name') or '—'} · {_dt_text(i.get('opened_at'))} · Mức {core.SEVERITY_LABEL.get(i.get('severity'),i.get('severity'))}")
            resolution=st.text_input("Cách xử lý",key=f"cw_resolve_txt_{i['id']}")
            if st.button("Đánh dấu đã xử lý",key=f"cw_resolve_{i['id']}"):
                core.resolve_issue(get_conn,i["id"],uid,resolution,logger);st.rerun()
    with st.expander("＋ Ghi nhận vướng mắc",expanded=False):
        issue=st.text_area("Nội dung vướng mắc",key=f"cw_issue_txt_{case_id}")
        sev=st.selectbox("Mức độ",["LOW","MEDIUM","HIGH"],format_func=lambda z:core.SEVERITY_LABEL[z],index=1,key=f"cw_issue_sev_{case_id}")
        if st.button("Lưu vướng mắc",key=f"cw_issue_save_{case_id}",use_container_width=True):
            try: core.add_issue(get_conn,case_id,uid,issue,sev,logger);st.rerun()
            except Exception as exc: st.error(str(exc))
    st.subheader("Dời thời gian dự kiến hoàn thành")
    old=core.parse_dt(x.get("expected_complete_at")) or datetime.now()+timedelta(days=1)
    r1,r2=st.columns(2)
    nd=r1.date_input("Ngày mới",value=old.date(),key=f"cw_rd_{case_id}")
    nt=r2.time_input("Giờ mới",value=old.time().replace(second=0,microsecond=0),key=f"cw_rt_{case_id}")
    reason=st.text_input("Lý do dời",key=f"cw_rr_{case_id}")
    if st.button("Gửi đề nghị dời thời gian",key=f"cw_req_move_{case_id}",use_container_width=True):
        try:
            _,state=core.request_reschedule(get_conn,case_id,uid,datetime.combine(nd,nt).strftime("%Y-%m-%d %H:%M:%S"),reason,logger)
            st.toast("Đã cập nhật thời gian." if state=="APPROVED" else "Đã gửi đề nghị chờ phê duyệt.",icon="✅");st.rerun()
        except Exception as exc: st.error(str(exc))
    if manager:
        st.subheader("Ưu tiên góc phần tư")
        cat_options=[None]+cats
        current_cat=next((z for z in cats if int(z["id"])==int(x.get("important_category_id") or 0)),None)
        cat_index=cat_options.index(current_cat) if current_cat in cat_options else 0
        cat=st.selectbox("Danh mục công việc quan trọng",cat_options,index=cat_index,format_func=lambda z:"Không gán quan trọng" if z is None else z["name"],key=f"cw_cat_{case_id}")
        urgency=st.selectbox("Khẩn cấp",[None,1,0],index={None:0,1:1,0:2}.get(x.get("urgent_override"),0),format_func=lambda z:{None:"Tự động theo thời hạn",1:"Khẩn cấp",0:"Không khẩn cấp"}[z],key=f"cw_urg_{case_id}")
        if st.button("Lưu mức ưu tiên",key=f"cw_priority_{case_id}",use_container_width=True):
            core.set_importance(get_conn,case_id,uid,cat["id"] if cat else None,urgency,logger);st.rerun()
    st.subheader("Lịch sử mục công việc")
    rows=[]
    for h in hist:
        start=core.parse_dt(h.get("started_at")); end=core.parse_dt(h.get("ended_at")) or datetime.now(); hrs=max(0,(end-start).total_seconds()/3600) if start else 0
        rows.append([h.get("stage_name"),_dt_text(h.get("started_at")),_dt_text(h.get("ended_at")),core.duration_text(hrs),h.get("actor_name"),h.get("note") or "—"])
    _html_table(st,["Mục công việc","Bắt đầu","Kết thúc","Thời gian","Người cập nhật","Ghi chú"],rows,["22%","15%","15%","12%","16%","20%"])
    if issues:
        st.subheader("Lịch sử vướng mắc")
        _html_table(st,["Thời điểm","Mục công việc","Vướng mắc","Mức độ","Xử lý"],[[ _dt_text(i.get("opened_at")),i.get("stage_name") or "—",i.get("issue_text"),core.SEVERITY_LABEL.get(i.get("severity"),i.get("severity")),("Đã xử lý: "+str(i.get("resolution_text") or "")) if i.get("resolved_at") else "Đang mở"] for i in issues])


def render_cases_page(st, u, get_conn, page_title=None, logger=None):
    core.ensure_schema(get_conn,logger);uid=int(u["id"]);manager=_manager(u)
    if page_title: page_title("Công việc khách hàng", "Theo dõi xuyên suốt từ tiếp cận đến hoàn thành")
    else: st.title("👥 Công việc khách hàng")
    if st.session_state.get("cw_case_id"):
        _case_detail(st,u,get_conn,int(st.session_state["cw_case_id"]),logger);_glossary(st);return
    tabs=st.tabs(["Đang xử lý","Tạo công việc mới","Góc phần tư"])
    with tabs[0]:
        with get_conn() as c: data=core.list_cases(c,uid=uid,manager=manager,include_completed=False)
        f1,f2=st.columns(2)
        stages=sorted({x.get("stage_name") for x in data if x.get("stage_name")})
        sf=f1.selectbox("Lọc mục công việc",["Tất cả"]+stages,key="cw_filter_stage")
        search=f2.text_input("Tìm khách hàng/công việc",key="cw_filter_text")
        ss=str(search or "").lower().strip()
        shown=[x for x in data if (sf=="Tất cả" or x.get("stage_name")==sf) and (not ss or ss in str(x.get("customer_name") or "").lower() or ss in str(x.get("title") or "").lower())]
        if not shown: st.info("Không có công việc phù hợp.")
        for x in shown: _case_card(st,x,get_conn,uid,manager,logger)
    with tabs[1]: _create_case_form(st,u,get_conn,logger)
    with tabs[2]:
        with get_conn() as c: data=core.list_cases(c,uid=uid,manager=manager,include_completed=False)
        counts={q:sum(int(x.get("quadrant") or 4)==q for x in data) for q in range(1,5)}
        qcols=st.columns(4)
        for q,col in zip(range(1,5),qcols): col.metric(core.quadrant_label(q),counts[q])
        for q in range(1,5):
            with st.expander(f"{core.quadrant_label(q)} · {counts[q]} công việc",expanded=q in (1,2)):
                for x in [z for z in data if int(z.get("quadrant") or 4)==q]: _case_card(st,x,get_conn,uid,manager,logger,compact=True)
    _glossary(st)


def _weekly_approval_counts(c):
    try:
        plan=int(c.execute("SELECT COUNT(*) FROM weekly_plan_items WHERE approval_status='PENDING'").fetchone()[0])
        move=int(c.execute("SELECT COUNT(*) FROM weekly_plan_reschedule_requests WHERE status='PENDING'").fetchone()[0])
    except Exception:
        plan=move=0
    return plan,move


def render_leader_dashboard(st, u, get_conn, page_title=None, logger=None):
    core.ensure_schema(get_conn,logger)
    if page_title: page_title("Điều hành công việc phòng", "Tình hình thực hiện kế hoạch, tồn đọng, cảnh báo và ưu tiên")
    else: st.title("📊 Điều hành công việc phòng")
    with get_conn() as c:
        data=core.list_cases(c,manager=True,include_completed=False)
        plans,reschedules=core.pending_case_approvals(c)
        wp_plan,wp_move=_weekly_approval_counts(c)
        today=date.today().isoformat()
        try:
            wp_today=[dict(r) for r in c.execute("SELECT * FROM weekly_plan_items WHERE work_date=? AND status<>'CANCELLED' AND COALESCE(approval_status,'APPROVED')='APPROVED'",(today,)).fetchall()]
        except Exception: wp_today=[]
    delayed=[x for x in data if x.get("is_stage_delayed")]
    overdue=[x for x in data if x.get("is_overdue")]
    blocked=[x for x in data if int(x.get("open_issue_count") or 0)>0]
    a,b,c,d,e=st.columns(5)
    a.metric("Đang xử lý",len(data));b.metric("Kế hoạch hôm nay",len(wp_today));c.metric("Quá hạn",len(overdue));d.metric("Mục bị chậm",len(delayed));e.metric("Chờ phê duyệt",len(plans)+len(reschedules)+wp_plan+wp_move)
    st.subheader("Theo mục công việc")
    stage_rows=[]
    for name in sorted({x.get("stage_name") for x in data if x.get("stage_name")}):
        arr=[x for x in data if x.get("stage_name")==name]
        stage_rows.append([name,len(arr),sum(z.get("is_stage_delayed") for z in arr),sum(int(z.get("open_issue_count") or 0)>0 for z in arr),sum(z.get("is_overdue") for z in arr)])
    _html_table(st,["Mục công việc","Số việc","Bị chậm","Có vướng mắc","Quá hạn"],stage_rows)
    st.subheader("Theo cán bộ")
    staff={}
    for x in data:
        k=x.get("owner_name") or "—";r=staff.setdefault(k,[0,0,0,0]);r[0]+=1;r[1]+=int(bool(x.get("is_stage_delayed")));r[2]+=int(bool(x.get("is_overdue")));r[3]+=int(int(x.get("open_issue_count") or 0)>0)
    _html_table(st,["Cán bộ","Đang xử lý","Bị chậm","Quá hạn","Có vướng mắc"],[[k]+v for k,v in sorted(staff.items())])
    st.subheader("Góc phần tư ưu tiên")
    qcols=st.columns(4)
    for q,col in zip(range(1,5),qcols): col.metric(core.quadrant_label(q),sum(int(x.get("quadrant") or 4)==q for x in data))
    if overdue or delayed or blocked:
        st.subheader("⚠ Danh sách cần chú ý")
        seen=set()
        for x in overdue+delayed+blocked:
            if x["id"] in seen: continue
            seen.add(x["id"]);_case_card(st,x,get_conn,int(u["id"]),True,logger,compact=True)
    _glossary(st)


def render_approvals_page(st, u, get_conn, page_title=None, logger=None):
    core.ensure_schema(get_conn,logger);uid=int(u["id"])
    if not _manager(u): st.error("Chỉ Lãnh đạo/Admin được phê duyệt.");return
    if page_title: page_title("Phê duyệt", "Kế hoạch mới và các đề nghị dời thời gian")
    else: st.title("✅ Phê duyệt")
    with get_conn() as c:
        plans,reschedules=core.pending_case_approvals(c)
        try:
            weekly=[dict(r) for r in c.execute("""SELECT w.*,u.full_name,c.customer_name FROM weekly_plan_items w JOIN users u ON u.id=w.user_id LEFT JOIN customers c ON c.id=w.customer_id WHERE w.approval_status='PENDING' ORDER BY w.work_date,w.id""").fetchall()]
            weekly_moves=[dict(r) for r in c.execute("""SELECT r.*,w.title,w.customer_text,u.full_name AS requester_name FROM weekly_plan_reschedule_requests r JOIN weekly_plan_items w ON w.id=r.item_id JOIN users u ON u.id=r.requested_by WHERE r.status='PENDING' ORDER BY r.requested_at,r.id""").fetchall()]
        except Exception:
            weekly=[];weekly_moves=[]
    total=len(plans)+len(reschedules)+len(weekly)+len(weekly_moves)
    st.caption(f"Có {total} đề nghị đang chờ xử lý.")
    st.subheader("Công việc khách hàng mới")
    if not plans: st.caption("Không có kế hoạch mới chờ phê duyệt.")
    for x in plans:
        with st.container(border=True):
            st.markdown(f"**{x.get('customer_name')} · {x.get('title')}**");st.caption(f"{x.get('owner_name')} · {x.get('stage_name')} · Dự kiến {_dt_text(x.get('expected_complete_at'))}")
            note=st.text_input("Ý kiến",key=f"ap_case_note_{x['id']}")
            a,b=st.columns(2)
            if a.button("✓ Phê duyệt",key=f"ap_case_yes_{x['id']}",type="primary",use_container_width=True): core.approve_case_plan(get_conn,x["id"],uid,True,note,logger);st.rerun()
            if b.button("✕ Từ chối",key=f"ap_case_no_{x['id']}",use_container_width=True): core.approve_case_plan(get_conn,x["id"],uid,False,note,logger);st.rerun()
    st.subheader("Đề nghị dời thời gian công việc khách hàng")
    if not reschedules: st.caption("Không có đề nghị dời thời gian.")
    for r in reschedules:
        with st.container(border=True):
            st.markdown(f"**{r.get('customer_name')} · {r.get('title')}**");st.caption(f"{r.get('requester_name')} · {_dt_text(r.get('old_due_at'))} → {_dt_text(r.get('proposed_due_at'))}");st.write(f"Lý do: {r.get('reason')}")
            note=st.text_input("Ý kiến",key=f"ap_rs_note_{r['id']}");a,b=st.columns(2)
            if a.button("✓ Phê duyệt",key=f"ap_rs_yes_{r['id']}",type="primary",use_container_width=True): core.decide_reschedule(get_conn,r["id"],uid,True,note,logger);st.rerun()
            if b.button("✕ Từ chối",key=f"ap_rs_no_{r['id']}",use_container_width=True): core.decide_reschedule(get_conn,r["id"],uid,False,note,logger);st.rerun()
    st.subheader("Kế hoạch tuần/ngày")
    if not weekly: st.caption("Không có kế hoạch tuần/ngày chờ phê duyệt.")
    for w in weekly:
        with st.container(border=True):
            st.markdown(f"**{w.get('full_name')} · {w.get('title')}**");st.caption(f"Ngày {_date_text(w.get('work_date'))} · {w.get('customer_name') or w.get('customer_text') or 'Nội bộ'}")
            note=st.text_input("Ý kiến",key=f"ap_wp_note_{w['id']}");a,b=st.columns(2)
            if a.button("✓ Phê duyệt",key=f"ap_wp_yes_{w['id']}",type="primary",use_container_width=True):
                with get_conn() as c:c.execute("UPDATE weekly_plan_items SET approval_status='APPROVED',approved_by_user_id=?,approved_at=?,approval_note=? WHERE id=?",(uid,core.now_str(),note,w["id"]));c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_APPROVE',?,?)",(w["id"],uid,note,core.now_str()))
                st.rerun()
            if b.button("✕ Từ chối",key=f"ap_wp_no_{w['id']}",use_container_width=True):
                with get_conn() as c:c.execute("UPDATE weekly_plan_items SET approval_status='REJECTED',rejected_by_user_id=?,rejected_at=?,approval_note=? WHERE id=?",(uid,core.now_str(),note,w["id"]));c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'PLAN_REJECT',?,?)",(w["id"],uid,note,core.now_str()))
                st.rerun()
    st.subheader("Đề nghị dời kế hoạch tuần/ngày")
    if not weekly_moves: st.caption("Không có đề nghị dời kế hoạch.")
    for r in weekly_moves:
        with st.container(border=True):
            st.markdown(f"**{r.get('requester_name')} · {r.get('title')}**");st.caption(f"{_date_text(r.get('old_work_date'))} → {_date_text(r.get('proposed_work_date'))} · {r.get('customer_text') or 'Nội bộ'}")
            note=st.text_input("Ý kiến",key=f"ap_wpr_note_{r['id']}");a,b=st.columns(2)
            if a.button("✓ Phê duyệt",key=f"ap_wpr_yes_{r['id']}",type="primary",use_container_width=True):
                ts=core.now_str()
                with get_conn() as c:
                    c.execute("UPDATE weekly_plan_reschedule_requests SET status='APPROVED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",(uid,ts,note,r["id"]));c.execute("UPDATE weekly_plan_items SET work_date=?,status='PLANNED',reschedule_count=reschedule_count+1,updated_at=? WHERE id=?",(r["proposed_work_date"],ts,r["item_id"]));c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_APPROVE',?,?)",(r["item_id"],uid,note,ts))
                st.rerun()
            if b.button("✕ Từ chối",key=f"ap_wpr_no_{r['id']}",use_container_width=True):
                ts=core.now_str()
                with get_conn() as c:c.execute("UPDATE weekly_plan_reschedule_requests SET status='REJECTED',decided_by=?,decided_at=?,decision_note=? WHERE id=?",(uid,ts,note,r["id"]));c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'RESCHEDULE_REJECT',?,?)",(r["item_id"],uid,note,ts))
                st.rerun()
    _glossary(st)


def render_catalog_page(st, u, get_conn, page_title=None, logger=None):
    core.ensure_schema(get_conn,logger);uid=int(u["id"])
    if not _manager(u): st.error("Chỉ Lãnh đạo/Admin được quản lý danh mục.");return
    if page_title: page_title("Danh mục quy trình", "Mục công việc, SLA và danh mục công việc quan trọng")
    else: st.title("⚙️ Danh mục quy trình")
    tab1,tab2=st.tabs(["Mục công việc / SLA","Danh mục công việc quan trọng"])
    with tab1:
        with get_conn() as c: stages=core.active_stages(c,include_inactive=True)
        _html_table(st,["Thứ tự","Mục công việc","SLA (giờ)","Hoàn tất","Trạng thái"],[[s["sort_order"],s["name"],f"{float(s['sla_hours']):.1f}","Có" if s["is_completion"] else "Không","Đang dùng" if s["active"] else "Ngưng"] for s in stages])
        opts=[None]+stages;edit=st.selectbox("Chọn để sửa",opts,format_func=lambda x:"＋ Tạo mới" if x is None else x["name"],key="cw_stage_edit")
        with st.form("cw_stage_form"):
            name=st.text_input("Tên mục công việc",value=edit["name"] if edit else "");order=st.number_input("Thứ tự",min_value=1,value=int(edit["sort_order"] if edit else len(stages)+1),step=1);sla=st.number_input("SLA cảnh báo (giờ)",min_value=0.0,value=float(edit["sla_hours"] if edit else 48),step=1.0);done=st.checkbox("Đây là mục hoàn thành",value=bool(edit["is_completion"]) if edit else False);active=st.checkbox("Đang sử dụng",value=bool(edit["active"]) if edit else True);save=st.form_submit_button("Lưu danh mục",type="primary")
        if save:
            try: core.save_stage_catalog(get_conn,uid,edit["id"] if edit else None,name,order,sla,done,active,logger);st.rerun()
            except Exception as exc: st.error(str(exc))
        if edit and st.button("Xóa/Ngưng sử dụng mục này",key="cw_stage_del"):
            mode=core.delete_stage_catalog(get_conn,uid,edit["id"],logger);st.toast("Đã xóa." if mode=="DELETE" else "Mục đã có lịch sử nên được ngưng sử dụng thay vì xóa dữ liệu cũ.");st.rerun()
    with tab2:
        with get_conn() as c: cats=core.active_important_categories(c,include_inactive=True)
        _html_table(st,["Thứ tự","Danh mục quan trọng","Diễn giải","Trạng thái"],[[x["sort_order"],x["name"],x.get("description") or "—","Đang dùng" if x["active"] else "Ngưng"] for x in cats])
        opts=[None]+cats;edit=st.selectbox("Chọn để sửa",opts,format_func=lambda x:"＋ Tạo mới" if x is None else x["name"],key="cw_cat_edit")
        with st.form("cw_cat_form"):
            name=st.text_input("Tên danh mục",value=edit["name"] if edit else "",key="cw_cat_name");desc=st.text_area("Diễn giải",value=edit.get("description") or "" if edit else "",key="cw_cat_desc");order=st.number_input("Thứ tự",min_value=1,value=int(edit["sort_order"] if edit else len(cats)+1),step=1,key="cw_cat_order");active=st.checkbox("Đang sử dụng",value=bool(edit["active"]) if edit else True,key="cw_cat_active");save=st.form_submit_button("Lưu danh mục",type="primary")
        if save:
            try: core.save_important_category(get_conn,uid,edit["id"] if edit else None,name,desc,order,active,logger);st.rerun()
            except Exception as exc: st.error(str(exc))
        if edit and st.button("Xóa/Ngưng sử dụng danh mục",key="cw_cat_del"):
            mode=core.delete_important_category(get_conn,uid,edit["id"],logger);st.toast("Đã xóa." if mode=="DELETE" else "Danh mục đã được dùng nên được ngưng sử dụng để giữ lịch sử.");st.rerun()
    _glossary(st)
