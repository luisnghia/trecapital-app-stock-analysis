"""Manager weekly adjustments with explicit Customer Work linkage and local drafts."""
from __future__ import annotations

from datetime import date, timedelta
import json
import logging

from khdn_apps import planning_operational_phase13_patch as links
from khdn_apps import weekly_entry_edit_patch as entry
from khdn_apps import weekly_plan_form_refinement_patch as form
from khdn_apps.legacy_fast_form import legacy_fast_form

LOGGER = logging.getLogger("khdn.weekly_manager_edit")


def _context(c, policy, uid, iid):
    row=c.execute("SELECT * FROM users WHERE id=?",(int(uid),)).fetchone()
    actor=dict(row) if row else {}
    if not actor.get("active") or not policy._manager(actor):
        raise PermissionError("Chỉ Admin/Lãnh đạo phòng đang hoạt động được điều chỉnh kế hoạch.")
    row=c.execute("SELECT * FROM weekly_plan_items WHERE id=?",(int(iid),)).fetchone()
    old=dict(row) if row else {}
    if not old or old.get("status")=="CANCELLED":
        raise ValueError("Công việc không còn tồn tại hoặc đã bị hủy.")
    row=c.execute("SELECT * FROM weekly_plans WHERE id=?",(int(old["plan_id"]),)).fetchone()
    plan=dict(row) if row else {}
    if not policy._direct_scope_ok(c,int(uid),int(old["user_id"]),policy._is_admin(actor)):
        raise PermissionError("Kế hoạch không thuộc phạm vi điều chỉnh của bạn.")
    if plan.get("workflow_status") not in {"DA_NOP","DA_DUYET","DA_CHOT"} or plan.get("classification_locked") or old.get("classification_locked"):
        raise PermissionError("Trạng thái kế hoạch đã thay đổi hoặc phân loại đang bị khóa. Hãy mở lại kế hoạch.")
    return actor,plan,old,date.fromisoformat(str(plan["week_start"])[:10])


def _linked_row(c, customer_id, linked_id, old):
    if not linked_id:
        return None
    row=c.execute("SELECT * FROM customer_work_cases WHERE id=?",(int(linked_id),)).fetchone()
    case=dict(row) if row else {}
    if not case or int(case.get("customer_id") or 0)!=int(customer_id or 0):
        raise ValueError("Công việc liên kết không thuộc khách hàng đã chọn.")
    # Preserve an existing completed link while editing other fields. Newly
    # selected work must still be active when Save actually executes.
    if case.get("status")!="ACTIVE" and int(old.get("linked_case_id") or 0)!=int(linked_id):
        raise ValueError("Công việc khách hàng vừa kết thúc hoặc bị hủy. Hãy chọn công việc khác.")
    return case


def _source(case, leaders, focus_rows):
    due,leader,focus,q=links._source_defaults(case,leaders,focus_rows)
    if case and q==2 and not focus:
        focus=next((x for x in focus_rows if int(x["id"])==int(case.get("focus_category_id") or 0)),None)
    return due,leader,focus,q


def save_item(get_conn, policy, core, uid, iid, payload, *, expected_token, logger=None):
    """Persist customer + case + inherited fields together, with fresh checks."""
    with get_conn() as c:
        c.execute("BEGIN IMMEDIATE")
        actor,plan,old,ws=_context(c,policy,uid,iid)
        if entry.item_token(old)!=expected_token:
            raise ValueError("Công việc đã thay đổi ở phiên khác. Đóng rồi mở lại Điều chỉnh để nạp dữ liệu mới.")
        customer_id=int(payload.get("customer_id") or 0)
        customers={int(x["id"]):x for x in core.customers(c,int(uid))}
        customer=customers.get(customer_id)
        if customer_id and not customer:
            raise ValueError("Khách hàng không còn trong danh sách được chọn.")
        linked_id=int(payload.get("linked_case_id") or 0)
        case=_linked_row(c,customer_id,linked_id,old)
        if linked_id and c.execute("SELECT 1 FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id WHERE p.user_id=? AND p.week_start=? AND w.linked_case_id=? AND w.status<>'CANCELLED' AND w.id<>? LIMIT 1",(int(old["user_id"]),ws.isoformat(),linked_id,int(iid))).fetchone():
            raise ValueError("Công việc khách hàng đã được liên kết trong kế hoạch của cán bộ này ở tuần đang sửa.")
        leaders=form._leader_rows(c)
        focus_rows=policy._focus_categories(c,policy._scope_key(c,int(old["user_id"])),ws.year,False)
        auto_due,auto_leader,auto_focus,source_q=_source(case,leaders,focus_rows)
        title=str(payload.get("title") or "").strip()
        work_day=entry._day(payload.get("work_date"),"Ngày thực hiện")
        due=auto_due or entry._day(payload.get("due_date"),"Ngày dự kiến hoàn thành")
        if not title or not ws<=work_day<=ws+timedelta(days=6):
            raise ValueError("Nhập Công việc và chọn Ngày thực hiện trong tuần đang sửa.")
        if not auto_due and due<work_day:
            raise ValueError("Ngày dự kiến hoàn thành không được trước Ngày thực hiện.")
        leader_id=int(auto_leader["id"]) if auto_leader else int(payload.get("controller") or 0)
        leader=next((x for x in leaders if int(x["id"])==leader_id),None)
        if not leader:
            raise ValueError("Chọn Lãnh đạo kiểm soát đang hoạt động.")
        if case and source_q in {1,2,3,4}:
            q=int(source_q);focus=auto_focus if q==2 else None
            due7,risk=links._classification_from_source(q)
            basis=f"Kế thừa Công việc khách hàng #{linked_id}: {links._Q_LABEL[q]}"
            snapshot=focus or (case if q==2 else {})
        else:
            raw=str(payload.get("focus") or "NONE")
            focus=next((x for x in focus_rows if str(x["id"])==raw),None)
            if raw!="NONE" and not focus:
                raise ValueError("Danh mục công việc trọng tâm không còn áp dụng.")
            q=2 if focus else int(payload.get("nonfocus_q") or 4)
            if q not in {1,2,3,4} or (not focus and q==2):
                raise ValueError("Phân loại ngoài trọng tâm không hợp lệ.")
            due7,risk=links._classification_from_source(q)
            _,basis=policy._classify(focus,due7,risk)
            snapshot=focus or {}
        ts=policy._now()
        values={"work_date":work_day.isoformat(),"title":title,
                "customer_id":customer_id or None,"customer_text":str(customer.get("customer_name") or "") if customer else "",
                "linked_case_id":linked_id or None,"expected_complete_date":due.isoformat(),
                "controller_user_id":leader_id,"controller_name_snapshot":str(leader.get("full_name") or ""),
                "focus_category_id":int(focus["id"]) if focus else None,
                "focus_code_snapshot":snapshot.get("code") or snapshot.get("focus_code_snapshot"),
                "focus_name_snapshot":snapshot.get("name") or snapshot.get("focus_name_snapshot"),
                "focus_desc_snapshot":snapshot.get("description") or snapshot.get("focus_desc_snapshot"),
                "priority_quadrant":q,"priority_basis":basis,
                "deadline_within_7d":None if due7 is None else int(due7),"kpi_risk_flag":None if risk is None else int(risk),
                "category":str(payload.get("category") or "").strip(),"source_text":str(payload.get("source") or "").strip(),
                "expected_output":str(payload.get("output") or "").strip(),"note":str(payload.get("note") or "").strip(),"updated_at":ts}
        c.execute("UPDATE weekly_plan_items SET "+",".join(f"{key}=?" for key in values)+" WHERE id=?",(*values.values(),int(iid)))
        changed=old.get("focus_category_id")!=values["focus_category_id"] or int(old.get("priority_quadrant") or 0)!=q
        if changed:
            c.execute("INSERT INTO weekly_classification_audit(item_id,actor_user_id,old_focus_category_id,new_focus_category_id,old_quadrant,new_quadrant,old_basis,new_basis,reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(int(iid),int(uid),old.get("focus_category_id"),values["focus_category_id"],old.get("priority_quadrant"),q,old.get("priority_basis"),basis,"Lãnh đạo điều chỉnh kế hoạch / liên kết công việc",ts))
        after=dict(c.execute("SELECT * FROM weekly_plan_items WHERE id=?",(int(iid),)).fetchone())
        action_id=c.execute("INSERT INTO weekly_plan_actions(item_id,actor_user_id,action,detail,created_at) VALUES(?,?,'MANAGER_EDIT_PHASE3',?,?)",(int(iid),int(uid),json.dumps({"before":old,"after":after,"linked_case_id":linked_id or None},ensure_ascii=False),ts)).lastrowid
        if changed and int(uid)!=int(old["user_id"]):
            policy._notify(c,int(old["user_id"]),"🎯 Phân loại kế hoạch được điều chỉnh",f"{title}: {policy.PRIORITY_SHORT.get(q,q)}.",source_action_id=action_id,weekly_plan_item_id=int(iid),event_code="WORK_UPDATE_MANAGER_EDIT_PHASE3")
        c.execute("UPDATE weekly_plans SET updated_at=? WHERE id=?",(ts,int(plan["id"])))
    (logger or LOGGER).info("WEEKLY_MANAGER_EDIT_SAVED actor=%s owner=%s item=%s customer=%s linked_case=%s previous_link=%s q=%s",int(uid),int(old["user_id"]),int(iid),customer_id,linked_id,int(old.get("linked_case_id") or 0),q)
    return int(iid)


def render(st,u,policy,core,get_conn,plan,item,focus_rows,logger=None):
    uid=int(policy._uget(u,"id"));iid=int(item["id"])
    try:
        with get_conn() as c:
            actor,plan,item,ws=_context(c,policy,uid,iid)
            customers=core.customers(c,uid);leaders=form._leader_rows(c)
            focus_rows=policy._focus_categories(c,policy._scope_key(c,int(item["user_id"])),ws.year,False)
    except (ValueError,PermissionError) as exc:
        st.error(str(exc));return
    token=entry.item_token(item)
    (logger or LOGGER).info("WEEKLY_MANAGER_EDIT_OPEN actor=%s item=%s customers=%s linked_case=%s",uid,iid,len(customers),int(item.get("linked_case_id") or 0))
    st.markdown(f"### ✏️ Điều chỉnh kế hoạch · {item.get('title') or ''}")
    opts=[None]+customers;cur=next((x for x in customers if int(x["id"])==int(item.get("customer_id") or 0)),None)
    customer=st.selectbox("Khách hàng",opts,index=opts.index(cur),format_func=lambda x:"Không gắn khách hàng" if x is None else f"{x['customer_name']} · CIF {x.get('cif') or 'Chưa có CIF'}",key=f"p3_mgr_customer_{iid}")
    cid=int(customer["id"]) if customer else 0
    linked=None
    if customer:
        with get_conn() as c:
            cases=links._case_rows(c,cid,uid,True)
            old_id=int(item.get("linked_case_id") or 0)
            if old_id and old_id not in {int(x["id"]) for x in cases}:
                row=c.execute("SELECT * FROM customer_work_cases WHERE id=? AND customer_id=?",(old_id,cid)).fetchone()
                if row: cases.append(dict(row))
        cases=[None]+cases
        current=next((x for x in cases if x and int(x["id"])==old_id),None)
        selected=st.selectbox("Liên kết Công việc khách hàng (không bắt buộc)",cases,index=cases.index(current),format_func=links._linked_label,key=f"p3_mgr_case_{iid}_{cid}")
        if selected:
            with get_conn() as c:
                row=c.execute("SELECT * FROM customer_work_cases WHERE id=?",(int(selected["id"]),)).fetchone()
                linked=dict(row) if row else None
        if len(cases)==1: st.caption("Khách hàng này chưa có Công việc khách hàng đang hoạt động để liên kết.")
    linked_id=int(linked["id"]) if linked else 0
    auto_due,auto_leader,auto_focus,source_q=_source(linked,leaders,focus_rows)
    inherited=bool(linked and source_q in {1,2,3,4})
    if linked:
        st.info(f"Đã chọn liên kết: {linked.get('title') or ''}. Hạn hoàn thành và lãnh đạo được nạp từ công việc này."+(f" Phân loại: {links._Q_LABEL[int(source_q)]}." if inherited else ""))
    fields=[
        {"name":"title","label":"Công việc","type":"text","required":True,"full":True,"default":item.get("title") or (linked or {}).get("title") or item.get("source_text") or ""},
        {"name":"work_date","label":"Ngày thực hiện","type":"date","required":True,"default":str(item["work_date"])[:10],"min":ws.isoformat(),"max":(ws+timedelta(days=6)).isoformat()},
        {"name":"due_date","label":"Ngày dự kiến hoàn thành","type":"date","required":True,"default":auto_due.isoformat() if auto_due else str(item.get("expected_complete_date") or item["work_date"])[:10],"disabled":bool(auto_due),**({"minFrom":"work_date"} if not auto_due else {})},
        {"name":"controller","label":"Lãnh đạo kiểm soát","type":"select","required":True,"full":True,"options":entry._options(leaders,lambda x:str(x.get("full_name") or ""),"— Chọn lãnh đạo —"),"default":str(auto_leader["id"] if auto_leader else item.get("controller_user_id") or ""),"disabled":bool(auto_leader)},
    ]
    if not inherited:
        fields.extend([
            {"name":"focus","label":"Công việc trọng tâm / phân loại","type":"select","required":True,"full":True,"options":[{"value":"NONE","label":"Không thuộc công việc trọng tâm"}]+[{"value":str(x["id"]),"label":f"{x.get('code')} · {x.get('name')}"} for x in focus_rows],"default":str(item.get("focus_category_id") or "NONE")},
            {"name":"nonfocus_q","label":"Phân loại khi không thuộc trọng tâm","type":"select","full":True,"options":[{"value":str(q),"label":policy.PRIORITY_SHORT[q]} for q in (1,3,4)],"default":str(item.get("priority_quadrant") if item.get("priority_quadrant") in (1,3,4) else 4),"help":"Chỉ áp dụng khi chọn Không thuộc công việc trọng tâm."},
        ])
    fields.extend([{"name":name,"label":label,"type":kind,"full":True,"default":str(item.get(column) or "")} for name,label,column,kind in [
        ("category","Nhóm công việc","category","text"),("source","Nguồn / nội dung gốc","source_text","textarea"),
        ("output","Kết quả đầu ra","expected_output","textarea"),("note","Ghi chú","note","textarea")]])
    # A changed stored row or picker creates a different component identity,
    # so delayed submissions cannot be attached to a different edit context.
    key=f"weekly_manager_edit_{uid}_{iid}_{token}_{cid}_{linked_id}"
    payload=legacy_fast_form(fields,"💾 Lưu điều chỉnh",key=key,reset_token=token,columns=2,
                             help_text="Chọn công việc liên kết ở phía trên nếu cần. Nội dung được giữ trên thiết bị đến khi bấm Lưu điều chỉnh.")
    if payload is not None:
        payload.update(customer_id=cid or None,linked_case_id=linked_id or None)
        try:
            save_item(get_conn,policy,core,uid,iid,payload,expected_token=token,logger=logger)
        except (ValueError,PermissionError) as exc:
            st.error(str(exc))
        except Exception:
            (logger or LOGGER).exception("WEEKLY_MANAGER_EDIT_FAILED actor=%s item=%s",uid,iid)
            st.error("Chưa lưu được điều chỉnh. Vui lòng thử lại.")
        else:
            st.session_state.pop("p3_manager_edit_week_item",None)
            st.toast("Đã lưu điều chỉnh và liên kết Công việc khách hàng." if linked_id else "Đã lưu điều chỉnh kế hoạch.",icon="✅")
            st.rerun()
    if st.button("Đóng chỉnh sửa",key=f"p3_mgr_close_{iid}",use_container_width=True):
        st.session_state.pop("p3_manager_edit_week_item",None);st.rerun()
