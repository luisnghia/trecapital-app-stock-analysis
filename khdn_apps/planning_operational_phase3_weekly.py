"""Operational planning Phase 3 weekly board, inline progress and manager edit."""
from __future__ import annotations

from datetime import date, datetime, timedelta
import json

from khdn_apps import planning_week_board_focus_patch as weekboard
from khdn_apps import weekly_performance_phase2_patch as phase2
from khdn_apps.planning_operational_phase3_core import esc, dmy


def _status_label(weekly_core, value):
    return weekly_core.STAT.get(str(value or "PLANNED"), str(value or "PLANNED"))


def weekly_card(st, policy, weekly_core, item, prefix, can_update=False, can_edit=False):
    iid = int(item.get("id") or 0)
    q = int(item.get("priority_quadrant") or 4)
    heat = weekboard._HEAT.get(q, weekboard._HEAT[4])
    key = f"p3_wcard_{prefix}_{iid}"
    customer = item.get("customer_text") or item.get("master_customer_name") or "Công việc nội bộ"
    owner = item.get("owner_name_snapshot") or item.get("owner_name") or "—"
    controller = item.get("controller_name_snapshot") or item.get("controller_name") or "—"
    focus = item.get("focus_name_snapshot") or "Không thuộc trọng tâm"
    actual = item.get("actual_result") or ""
    with st.container(key=key, border=True):
        st.html(f"""
        <div class='p3-w-title'>{esc(item.get('title') or 'Công việc')}</div>
        <div class='p3-w-customer'>🏢 {esc(customer)}</div>
        <div class='p3-w-row'><span style='color:{heat['accent']};font-weight:950'>{esc(heat['label'])}</span>
          <span>📅 {esc(dmy(item.get('work_date')))}</span><span>🎯 Hạn {esc(dmy(item.get('expected_complete_date')))}</span></div>
        <div class='p3-w-row'><span>👤 {esc(owner)}</span><span>🛡️ {esc(controller)}</span></div>
        <div class='p3-w-row'><span>📌 {esc(focus)}</span><span>📍 {esc(_status_label(weekly_core,item.get('status')))}</span></div>
        {f"<div class='p3-w-result'>📝 {esc(actual)}</div>" if actual else ''}
        <style>div[class*='st-key-{key}']{{border-left:6px solid {heat['accent']}!important;background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important}}
        .p3-w-title{{font-weight:950;font-size:.90rem;line-height:1.25}}.p3-w-customer{{font-size:.78rem;color:#63DCCB;font-weight:850;margin-top:4px}}
        .p3-w-row{{display:flex;gap:7px 12px;flex-wrap:wrap;font-size:.72rem;margin-top:6px;white-space:normal;overflow-wrap:anywhere}}
        .p3-w-result{{font-size:.72rem;margin-top:6px;color:#FFD166;font-weight:800;white-space:normal;overflow-wrap:anywhere}}</style>""")
        if can_update and st.button("🔄 Cập nhật tiến độ", key=f"p3_update_btn_{prefix}_{iid}", use_container_width=True):
            st.session_state["p3_update_week_item"] = iid
            st.rerun()
        if can_edit and st.button("✏️ Điều chỉnh", key=f"p3_edit_btn_{prefix}_{iid}", use_container_width=True):
            st.session_state["p3_manager_edit_week_item"] = iid
            st.rerun()


def render_week_board(st, policy, weekly_core, get_conn, uid, ws, items, status, manager_edit=False):
    st.markdown("### 🗓 Kế hoạch Thứ 2 → Thứ 6")
    live = [dict(x) for x in items if str(x.get("status") or "") != "CANCELLED"]
    cols = st.columns(5, gap="small")
    for idx, (col, label) in enumerate(zip(cols, ["Thứ 2","Thứ 3","Thứ 4","Thứ 5","Thứ 6"])):
        d = ws + timedelta(days=idx)
        arr = [x for x in live if str(x.get("work_date") or "")[:10] == d.isoformat()]
        arr.sort(key=lambda x: (policy.PRIORITY_ORDER.index(int(x.get("priority_quadrant") or 4)) if int(x.get("priority_quadrant") or 4) in policy.PRIORITY_ORDER else 9, int(x.get("id") or 0)))
        with col:
            st.html(f"<div class='p3-day-head'><b>{label}</b><span>{d:%d/%m}</span><em>{len(arr)} việc</em></div>")
            if not manager_edit and status in {"NHAP","DA_DUYET"}:
                if st.button("＋ Thêm công việc", key=f"p3_quick_add_{ws.isoformat()}_{idx}_{status}", use_container_width=True):
                    st.session_state[f"wp_quick_day_{ws.isoformat()}"] = d.isoformat()
                    if status == "DA_DUYET":
                        st.session_state[f"p3_emergent_open_{ws.isoformat()}"] = True
                    st.rerun()
            if not arr:
                st.caption("Chưa có công việc")
            for x in arr:
                weekly_card(st, policy, weekly_core, x, f"{ws.isoformat()}_{idx}_{'mgr' if manager_edit else 'staff'}",
                            can_update=(status=="DA_DUYET" and not manager_edit), can_edit=manager_edit)
                if not manager_edit and status == "NHAP" and not int(x.get("is_emergent") or 0):
                    if st.button("🗑 Bỏ", key=f"p3_remove_{x['id']}", use_container_width=True):
                        with get_conn() as c:
                            c.execute("UPDATE weekly_plan_items SET status='CANCELLED',updated_at=? WHERE id=? AND user_id=?",
                                      (policy._now(), int(x["id"]), int(uid)))
                            c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'DRAFT_REMOVE','Bỏ khỏi bản nháp',?)",
                                      (int(x["id"]), int(uid), policy._now()))
                        st.rerun()
    st.html("""<style>.p3-day-head{display:flex;flex-direction:column;gap:2px;padding:9px 10px;margin-bottom:7px;border-radius:12px;
    background:linear-gradient(135deg,#075C57,#0F746B);border:1px solid #F4B41A;color:#fff}.p3-day-head b{font-size:.96rem}.p3-day-head span{font-size:.78rem}.p3-day-head em{font-size:.70rem;opacity:.84;font-style:normal}</style>""")


def render_week_update_form(st, u, policy, weekly_core, get_conn, item, logger=None):
    iid = int(item["id"]); uid = int(policy._uget(u,"id"))
    if int(item.get("user_id") or 0) != uid:
        return
    with st.container(border=True):
        st.markdown(f"#### 🔄 Cập nhật tiến độ · {item.get('title')}")
        labels = {"PLANNED":"Chưa làm","IN_PROGRESS":"Đang làm","DONE":"Hoàn thành","CANCELLED":"Hủy"}
        opts = list(labels); cur = str(item.get("status") or "PLANNED")
        stat = st.selectbox("Trạng thái", opts, index=opts.index(cur) if cur in opts else 0, format_func=lambda z:labels[z], key=f"p3_status_{iid}")
        result = st.text_area("Kết quả thực tế / ghi chú", value=str(item.get("actual_result") or ""), max_chars=1000, key=f"p3_result_{iid}")
        a,b = st.columns(2)
        if a.button("Lưu cập nhật", key=f"p3_update_save_{iid}", type="primary", use_container_width=True):
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            completed = item.get("completed_at")
            if stat == "DONE" and not completed: completed = ts
            if stat != "DONE": completed = None
            with get_conn() as c:
                c.execute("UPDATE weekly_plan_items SET status=?,actual_result=?,completed_at=?,updated_at=? WHERE id=? AND user_id=?",
                          (stat, str(result or "").strip(), completed, ts, iid, uid))
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'EXEC_UPDATE_PHASE3',?,?)",
                          (iid, uid, json.dumps({"status":stat,"actual_result":str(result or "").strip()}, ensure_ascii=False), ts))
            if logger: logger.info("P3_WEEK_PROGRESS_UPDATE item=%s actor=%s status=%s",iid,uid,stat)
            st.session_state.pop("p3_update_week_item",None); st.rerun()
        if b.button("Đóng", key=f"p3_update_close_{iid}", use_container_width=True):
            st.session_state.pop("p3_update_week_item",None); st.rerun()


def _render_self_close(st, u, policy, get_conn, ws, plan, metrics):
    uid = int(policy._uget(u,"id"))
    with st.expander("✅ Chốt tuần · tự đánh giá", expanded=False):
        s1,s2,s3,s4 = phase2._suggestions(metrics)
        st.info("Gợi ý từ dữ liệu hệ thống – cán bộ chỉnh lại trước khi chốt:\n\n"+s1+"\n\n"+s2)
        strengths = st.text_area("Mặt được *", value=str(plan.get("self_strengths") or s1), max_chars=500, key=f"p3_self_strength_{plan['id']}")
        issues = st.text_area("Tồn tại, hạn chế *", value=str(plan.get("self_issues") or s2), max_chars=500, key=f"p3_self_issues_{plan['id']}")
        causes = st.text_area("Nguyên nhân *", value=str(plan.get("self_causes") or s3), max_chars=500, key=f"p3_self_causes_{plan['id']}")
        proposals = st.text_area("Đề xuất / kế hoạch khắc phục tuần sau *", value=str(plan.get("self_proposals") or s4), max_chars=500, key=f"p3_self_prop_{plan['id']}")
        old = min(5,max(1,int(round(float(plan.get("self_score") or 3)))))
        score = st.select_slider("Tự chấm chất lượng tuần *",options=[1,2,3,4,5],value=old,format_func=lambda z:phase2.SELF_LEVELS[z],key=f"p3_self_score_{plan['id']}")
        if st.button("🔒 Chốt tuần", key=f"p3_close_{plan['id']}", type="primary", use_container_width=True):
            if not all([strengths.strip(),issues.strip(),causes.strip(),proposals.strip()]):
                st.error("Phải nhập đủ 4 nội dung: Mặt được, Tồn tại, Nguyên nhân và Đề xuất."); return
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn() as c:
                c.execute("""UPDATE weekly_plans SET workflow_status='DA_CHOT',self_score=?,self_strengths=?,self_issues=?,self_causes=?,self_proposals=?,closed_at=?,classification_locked=1,progress_score=?,quality_score=NULL,week_score=NULL,week_grade=NULL,score_gap_reason=NULL,quality_fallback=0,updated_at=? WHERE id=?""",
                          (int(score),strengths.strip(),issues.strip(),causes.strip(),proposals.strip(),ts,float(metrics['progress']),ts,int(plan['id'])))
                c.execute("UPDATE weekly_plan_items SET classification_locked=1 WHERE plan_id=?",(int(plan["id"]),))
                c.execute("INSERT INTO weekly_performance_audit(plan_id,actor_user_id,action,detail,created_at) VALUES(?,?,'SELF_CLOSE',?,?)",
                          (int(plan["id"]),uid,json.dumps({"self_score":int(score),"progress_score":metrics['progress']},ensure_ascii=False),ts))
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(NULL,?,'PLAN_CLOSE_PHASE3',?,?)",(uid,f"week={ws.isoformat()}",ts))
                leader = policy._leader_for_staff(c,uid)
                if leader and int(leader)!=uid:
                    policy._notify(c,int(leader),"📝 Có tuần chờ nhận xét",f"{policy._uget(u,'full_name') or policy._uget(u,'username')} đã chốt tuần {ws:%d/%m/%Y}.")
            st.rerun()


def install_weekly_staff(policy, weekly_core, logger=None):
    original_staff = policy._render_staff_week

    def render_staff_week(st,u,core,get_conn,ws,plan,items,focus_rows,logger=None,logger_arg=None,**kwargs):
        active_logger = logger or logger_arg
        if str(plan.get("workflow_status") or "NHAP") != "DA_DUYET":
            return original_staff(st,u,core,get_conn,ws,plan,items,focus_rows,logger=active_logger,**kwargs)
        phase2._ensure_schema(policy,weekly_core,get_conn,active_logger)
        with get_conn() as c:
            fresh_plan = dict(c.execute("SELECT * FROM weekly_plans WHERE id=?",(int(plan["id"]),)).fetchone())
            fresh_items = phase2._load_items(c,int(plan["id"]))
        render_week_board(st,policy,weekly_core,get_conn,int(policy._uget(u,"id")),ws,fresh_items,"DA_DUYET")
        metrics = phase2._metrics(fresh_items); phase2._score_cards(st,metrics,fresh_plan)
        st.success("Kế hoạch đã duyệt. Cập nhật tiến độ trực tiếp trên từng card công việc.")
        selected = st.session_state.get("p3_update_week_item")
        if selected:
            item = next((x for x in fresh_items if int(x.get("id") or 0)==int(selected)),None)
            if item: render_week_update_form(st,u,policy,weekly_core,get_conn,item,active_logger)
        add_key = f"p3_emergent_open_{ws.isoformat()}"
        if not st.session_state.get(add_key):
            if st.button("＋ Thêm công việc mới trong tuần", key=f"p3_emergent_btn_{plan['id']}", use_container_width=True):
                st.session_state[add_key]=True; st.rerun()
        else:
            a,b = st.columns([6,1]); a.caption("Công việc thêm sau khi kế hoạch đã duyệt tự ghi nhận là công việc phát sinh.")
            if b.button("✕ Đóng",key=f"p3_emergent_close_{plan['id']}",use_container_width=True):
                st.session_state.pop(add_key,None); st.rerun()
            policy._add_item_form(st,u,weekly_core,get_conn,ws,focus_rows,emergent=True,logger=active_logger)
        st.divider(); _render_self_close(st,u,policy,get_conn,ws,fresh_plan,metrics)

    policy._render_staff_week = render_staff_week
    weekboard._render_week_board = lambda st,policy_arg,get_conn,uid,ws,items,status: render_week_board(st,policy_arg,weekly_core,get_conn,uid,ws,items,status)
    if logger: logger.info("PLANNING_WEEK_CARD_PROGRESS_V3_INSTALLED")


def manager_edit_item(st,u,policy,weekly_core,get_conn,plan,item,focus_rows,logger=None):
    iid = int(item["id"]); uid = int(policy._uget(u,"id")); ws = date.fromisoformat(str(plan["week_start"])[:10])
    with get_conn() as c:
        customers=[dict(r) for r in c.execute("SELECT id,cif,customer_name FROM customers WHERE active=1 ORDER BY customer_name").fetchall()]
        leaders=[dict(r) for r in c.execute("SELECT id,full_name FROM users WHERE active=1 AND role='Lãnh đạo phòng' ORDER BY full_name").fetchall()]
    st.markdown(f"### ✏️ Điều chỉnh kế hoạch · {esc(item.get('title'))}")
    opts=[None]+customers; cur=next((x for x in customers if int(x["id"])==int(item.get("customer_id") or 0)),None)
    customer=st.selectbox("Khách hàng",opts,index=opts.index(cur) if cur in opts else 0,format_func=lambda x:"Không gắn khách hàng" if x is None else f"{x['customer_name']} · CIF {x.get('cif') or '—'}",key=f"p3_mgr_customer_{iid}")
    title=st.text_input("Công việc *",value=str(item.get("title") or ""),key=f"p3_mgr_title_{iid}")
    c1,c2=st.columns(2)
    work_date=c1.date_input("Ngày thực hiện *",value=date.fromisoformat(str(item.get("work_date"))[:10]),min_value=ws,max_value=ws+timedelta(days=6),format="DD/MM/YYYY",key=f"p3_mgr_workdate_{iid}")
    due_raw=item.get("expected_complete_date") or item.get("work_date")
    due_date=c2.date_input("Ngày dự kiến hoàn thành *",value=date.fromisoformat(str(due_raw)[:10]),min_value=work_date,format="DD/MM/YYYY",key=f"p3_mgr_due_{iid}")
    cur_leader=next((x for x in leaders if int(x["id"])==int(item.get("controller_user_id") or 0)),None)
    leader=st.selectbox("Lãnh đạo kiểm soát *",leaders,index=leaders.index(cur_leader) if cur_leader in leaders else 0,format_func=lambda x:x["full_name"],key=f"p3_mgr_leader_{iid}") if leaders else None
    focus_opts=list(focus_rows)+["NONE"]; cur_focus=next((x for x in focus_rows if int(x.get("id") or 0)==int(item.get("focus_category_id") or 0)),None)
    focus_choice=st.selectbox("Công việc trọng tâm / phân loại *",focus_opts,index=focus_opts.index(cur_focus) if cur_focus in focus_opts else len(focus_opts)-1,format_func=lambda x:"Không thuộc công việc trọng tâm" if x=="NONE" else f"{x.get('code')} · {x.get('name')}",key=f"p3_mgr_focus_{iid}")
    q=int(item.get("priority_quadrant") or 4); nonfocus_q=q if q in (1,3,4) else 4
    if focus_choice=="NONE":
        nonfocus_q=st.selectbox("Phân loại khi không thuộc trọng tâm",[1,3,4],index=[1,3,4].index(nonfocus_q),format_func=lambda z:policy.PRIORITY_SHORT[z],key=f"p3_mgr_q_{iid}")
    category=st.text_input("Nhóm công việc",value=str(item.get("category") or ""),key=f"p3_mgr_cat_{iid}")
    source=st.text_area("Nguồn / nội dung gốc",value=str(item.get("source_text") or ""),key=f"p3_mgr_source_{iid}")
    output=st.text_area("Kết quả đầu ra",value=str(item.get("expected_output") or ""),key=f"p3_mgr_output_{iid}")
    note=st.text_area("Ghi chú",value=str(item.get("note") or ""),key=f"p3_mgr_note_{iid}")
    a,b=st.columns(2)
    if a.button("💾 Lưu điều chỉnh",key=f"p3_mgr_save_{iid}",type="primary",use_container_width=True):
        if not title.strip() or due_date<work_date or not leader:
            st.error("Vui lòng nhập đủ Công việc, Lãnh đạo kiểm soát và ngày dự kiến hoàn thành hợp lệ.")
        else:
            ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn() as c:
                c.execute("""UPDATE weekly_plan_items SET work_date=?,title=?,customer_id=?,customer_text=?,category=?,source_text=?,expected_complete_date=?,controller_user_id=?,controller_name_snapshot=?,expected_output=?,note=?,updated_at=? WHERE id=?""",
                          (work_date.isoformat(),title.strip(),int(customer['id']) if customer else None,str(customer['customer_name']) if customer else "",category.strip(),source.strip(),due_date.isoformat(),int(leader['id']),str(leader['full_name']),output.strip(),note.strip(),ts,iid))
                focus = focus_choice if isinstance(focus_choice,dict) else None
                if focus:
                    policy._set_classification(c,iid,uid,int(focus["id"]),None,None,reason="Lãnh đạo điều chỉnh khi phê duyệt",allow_locked=True)
                else:
                    due7=nonfocus_q in (1,3); risk=True if nonfocus_q==1 else False if nonfocus_q==3 else None
                    policy._set_classification(c,iid,uid,None,due7,risk,reason="Lãnh đạo điều chỉnh khi phê duyệt",allow_locked=True)
                c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'MANAGER_EDIT_PHASE3',?,?)",
                          (iid,uid,json.dumps({"title":title.strip(),"work_date":work_date.isoformat(),"due":due_date.isoformat(),"customer_id":customer['id'] if customer else None},ensure_ascii=False),ts))
            if logger: logger.info("P3_MANAGER_WEEK_ITEM_EDIT item=%s actor=%s",iid,uid)
            st.session_state.pop("p3_manager_edit_week_item",None); st.rerun()
    if b.button("Đóng chỉnh sửa",key=f"p3_mgr_close_{iid}",use_container_width=True):
        st.session_state.pop("p3_manager_edit_week_item",None); st.rerun()
