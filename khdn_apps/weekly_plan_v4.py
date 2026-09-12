"""Weekly Plan V4 completion layer for KHDN Ops.

Adds in-app reminders, full Q1-Q4 time structure, task cancellation/log viewer,
bulk approval, quick Q2 creation, focus catalogue maintenance and the 5-business-day
self-score fallback. No Ban Giám đốc role/view is implemented.
"""
from __future__ import annotations

import html
from datetime import date, datetime
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v3 as v3


def _init_v4_schema(get_conn: Callable):
    v2._init_v2_schema(get_conn)
    with get_conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(weekly_reviews)").fetchall()}
        if "auto_fallback" not in cols:
            c.execute("ALTER TABLE weekly_reviews ADD COLUMN auto_fallback INTEGER NOT NULL DEFAULT 0")
        c.commit()


def _apply_score_fallbacks(get_conn: Callable):
    rows = wp._qdf(get_conn, """SELECT p.id plan_id,p.closed_at,r.self_score,r.leader_score,r.auto_fallback
        FROM weekly_plans p JOIN weekly_reviews r ON r.plan_id=p.id
        WHERE p.status='CLOSED' AND p.closed_at IS NOT NULL AND r.self_score IS NOT NULL AND r.leader_score IS NULL""")
    for _, r in rows.iterrows():
        if wp._business_days_since(str(r["closed_at"])) < 5:
            continue
        tasks = wp._tasks_df(get_conn, int(r["plan_id"]))
        progress = wp._progress_score(tasks)
        quality = 20.0 * int(r["self_score"])
        week_score = 0.5 * progress + 0.5 * quality
        grade = wp._score_grade(week_score)
        wp._execute(get_conn, """UPDATE weekly_reviews SET progress_score=?,quality_score=?,week_score=?,grade=?,auto_fallback=1,updated_at=? WHERE plan_id=? AND leader_score IS NULL""",
            (progress, quality, week_score, grade, wp._now(), int(r["plan_id"])))


def _reset_resolved_fallbacks(get_conn: Callable):
    wp._execute(get_conn, "UPDATE weekly_reviews SET auto_fallback=0,updated_at=? WHERE auto_fallback=1 AND leader_score IS NOT NULL", (wp._now(),))


def _reminder_banner(plan):
    now = datetime.now(); weekday = now.weekday(); hour = now.hour + now.minute / 60.0
    status = str(plan.get("status") or "")
    if weekday == 0 and hour >= 9 and status in {"DRAFT", "RETURNED"}:
        st.error("🔔 Đã quá 09:00 Thứ 2 nhưng kế hoạch tuần chưa được nộp.")
    elif weekday == 0 and 8 <= hour < 9 and status in {"DRAFT", "RETURNED"}:
        st.warning("🔔 Nhắc lập và nộp kế hoạch tuần trước 09:00.")
    elif weekday == 4 and hour >= 14 and status == "APPROVED":
        st.warning("🔔 Chiều Thứ 6: cập nhật kết quả thực tế và chốt tuần trước 17:00.")


def _quadrant_structure(tasks: pd.DataFrame):
    if tasks is None or tasks.empty:
        return
    valid = tasks[tasks["status"].ne("CANCELLED")].copy()
    ptotal = float(pd.to_numeric(valid["planned_hours"], errors="coerce").fillna(0).sum())
    atotal = float(pd.to_numeric(valid["actual_hours"], errors="coerce").fillna(0).sum())
    targets = {"Q2": "≥60%", "Q1": "≤20%", "Q3": "≤15%", "Q4": "≤5%"}
    rows=[]
    for q in ["Q2","Q1","Q3","Q4"]:
        ph=float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q),"planned_hours"],errors="coerce").fillna(0).sum())
        ah=float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q),"actual_hours"],errors="coerce").fillna(0).sum())
        rows.append({"Nhóm":f"{q} – {wp.QUADRANT_META[q][0]}","Mục tiêu":targets[q],"Giờ KH":f"{ph:.1f}","KH %":f"{100*ph/ptotal:.1f}%" if ptotal else "0.0%","Giờ TT":f"{ah:.1f}","TT %":f"{100*ah/atotal:.1f}%" if atotal else "0.0%"})
    st.markdown("### Cơ cấu thời gian Q1–Q4")
    v2._html_table(pd.DataFrame(rows), 300)


def _task_detail_admin(get_conn: Callable, u, plan):
    tasks=wp._tasks_df(get_conn,int(plan["id"]))
    if tasks.empty: return
    st.divider(); st.markdown("### Chi tiết & nhật ký công việc")
    task_id=st.selectbox("Chọn công việc xem chi tiết",tasks["id"].astype(int).tolist(),format_func=lambda x:f"{tasks[tasks['id'].eq(int(x))].iloc[0]['quadrant']} · {tasks[tasks['id'].eq(int(x))].iloc[0]['title']}",key="weekly_detail_task")
    row=tasks[tasks["id"].eq(int(task_id))].iloc[0].to_dict()
    if str(row.get("status")) not in {"COMPLETED","CANCELLED"}:
        reason=st.text_input("Lý do hủy công việc",key="weekly_cancel_reason")
        if st.button("Hủy công việc",use_container_width=True,key="weekly_cancel_task"):
            if not reason.strip(): st.error("Bắt buộc ghi lý do hủy.")
            else:
                old=str(row.get("status") or "")
                wp._execute(get_conn,"UPDATE weekly_tasks SET status='CANCELLED',updated_at=? WHERE id=?",(wp._now(),int(task_id)))
                wp._task_log(get_conn,int(task_id),int(u["id"]),"status",old,"CANCELLED",reason.strip())
                wp._log(get_conn,int(u["id"]),"CANCEL_WEEKLY_TASK","weekly_task",task_id,reason.strip()); st.rerun()
    logs=wp._qdf(get_conn,"""SELECT l.created_at,u.full_name,l.field_name,l.old_value,l.new_value,l.detail
        FROM weekly_task_logs l LEFT JOIN users u ON u.id=l.actor_user_id
        WHERE l.task_id=? ORDER BY l.id DESC LIMIT 50""",(int(task_id),))
    if not logs.empty:
        logs=logs.rename(columns={"created_at":"Thời gian","full_name":"Người thực hiện","field_name":"Trường","old_value":"Giá trị cũ","new_value":"Giá trị mới","detail":"Chi tiết"})
        v2._html_table(logs,360)


def _my_plan(get_conn: Callable,u):
    year,week,monday,sunday=wp._iso_week(); plan=wp._get_or_create_plan(get_conn,int(u["id"]),year,week,monday,sunday)
    _reminder_banner(plan); v2._sync_overdue(get_conn,int(plan["id"])); tasks=wp._tasks_df(get_conn,int(plan["id"]))
    wp._render_header(plan,tasks); _quadrant_structure(tasks); v2._warnings(get_conn,u,plan,tasks)
    status=str(plan["status"])
    if status in {"DRAFT","RETURNED"}:
        v2._carry_panel(get_conn,u,plan); v3._copy_last_week_panel(get_conn,u,plan); v3._draft_editor(get_conn,u,plan); wp._draft_view(get_conn,u,plan,tasks)
    elif status=="SUBMITTED":
        st.info("Kế hoạch đã nộp, đang chờ lãnh đạo phòng duyệt."); wp._submitted_view(get_conn,u,plan,tasks)
    elif status=="APPROVED":
        v2._approved_view(get_conn,u,plan,tasks); _task_detail_admin(get_conn,u,plan)
    elif status in {"CLOSED","REVIEWED"}:
        rv=wp._review(get_conn,int(plan["id"])) or {}
        if status=="CLOSED" and int(rv.get("auto_fallback") or 0): st.warning("Lãnh đạo chưa nhận xét sau 5 ngày làm việc; điểm chất lượng tạm tính theo tự chấm với hệ số 1,0.")
        elif status=="CLOSED": st.info("Đã chốt tuần; dữ liệu chỉ đọc và đang chờ lãnh đạo đánh giá.")
        wp._reviewed_view(get_conn,plan,tasks)


def _submitted_valid_plans(get_conn: Callable):
    year,week,_,_=wp._iso_week()
    plans=wp._qdf(get_conn,"""SELECT p.*,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id
        WHERE p.iso_year=? AND p.iso_week=? AND p.status='SUBMITTED' AND u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') ORDER BY u.full_name""",(year,week))
    valid=[]
    for _,p in plans.iterrows():
        if not wp._validate_submit(wp._tasks_df(get_conn,int(p["id"]))): valid.append(int(p["id"]))
    return plans,valid


def _bulk_approve(get_conn: Callable,u):
    plans,valid=_submitted_valid_plans(get_conn)
    if plans.empty: return
    st.markdown("### Duyệt nhanh")
    st.caption(f"Có {len(plans)} kế hoạch chờ duyệt; {len(valid)} kế hoạch không có cảnh báo và có thể duyệt hàng loạt.")
    if st.button(f"✅ Duyệt hàng loạt {len(valid)} kế hoạch hợp lệ",type="primary",use_container_width=True,disabled=not valid,key="weekly_bulk_approve"):
        ts=wp._now()
        with get_conn() as c:
            for pid in valid:
                c.execute("UPDATE weekly_plans SET status='APPROVED',approved_at=?,reviewer_user_id=?,return_reason=NULL,updated_at=? WHERE id=? AND status='SUBMITTED'",(ts,int(u["id"]),ts,pid))
            c.commit()
        for pid in valid: wp._log(get_conn,int(u["id"]),"BULK_APPROVE_PLAN","weekly_plan",pid,"")
        st.success(f"Đã duyệt {len(valid)} kế hoạch."); st.rerun()


def _quick_focus(get_conn: Callable,u):
    year=date.today().year
    with st.expander("➕ Thêm nhanh mục trọng tâm Q2",expanded=False):
        with st.form("weekly_quick_focus"):
            code=st.text_input("Mã *",max_chars=20); name=st.text_input("Tên trọng tâm *",max_chars=200); desc=st.text_area("Mô tả phạm vi *",max_chars=500); ok=st.form_submit_button("Thêm trọng tâm",type="primary",use_container_width=True)
        if ok:
            if not code.strip() or not name.strip() or not desc.strip(): st.error("Mã, tên và mô tả đều bắt buộc.")
            else:
                count=wp._qdf(get_conn,"SELECT COUNT(*) n FROM weekly_focus_categories WHERE scope_key='KHDN' AND year=?",(year,)); order=int(count.iloc[0]["n"])+1
                try:
                    fid=wp._execute(get_conn,"""INSERT INTO weekly_focus_categories(scope_key,year,code,name,description,display_order,status,created_by,created_at,updated_at)
                        VALUES('KHDN',?,?,?,?,?,'ACTIVE',?,?,?)""",(year,code.strip().upper(),name.strip(),desc.strip(),order,int(u["id"]),wp._now(),wp._now()))
                    wp._log(get_conn,int(u["id"]),"QUICK_ADD_FOCUS","weekly_focus_category",fid,code.strip().upper()); st.rerun()
                except Exception as exc: st.error(f"Không thêm được mục trọng tâm: {exc}")


def _leader_review(get_conn: Callable,u):
    _bulk_approve(get_conn,u); _quick_focus(get_conn,u); v2._leader_review(get_conn,u); _reset_resolved_fallbacks(get_conn)


def _focus_maintenance(get_conn: Callable,u):
    v2._focus_admin(get_conn,u)
    year=date.today().year; df=wp._focus_df(get_conn,year,active_only=False)
    st.divider(); st.markdown("### Chỉnh sửa & sắp xếp danh mục")
    if not df.empty:
        fid=st.selectbox("Chọn mục cần sửa",df["id"].astype(int).tolist(),format_func=lambda x:f"{df[df['id'].eq(int(x))].iloc[0]['code']} — {df[df['id'].eq(int(x))].iloc[0]['name']}",key="weekly_focus_edit_select")
        r=df[df["id"].eq(int(fid))].iloc[0]
        with st.form("weekly_focus_edit_form"):
            name=st.text_input("Tên",value=str(r["name"]),max_chars=200); desc=st.text_area("Mô tả phạm vi",value=str(r["description"] or ""),max_chars=500); order=st.number_input("Thứ tự",min_value=1,max_value=99,value=int(r["display_order"] or 1)); save=st.form_submit_button("Lưu chỉnh sửa",type="primary")
        if save:
            wp._execute(get_conn,"UPDATE weekly_focus_categories SET name=?,description=?,display_order=?,updated_at=? WHERE id=?",(name.strip(),desc.strip(),int(order),wp._now(),int(fid))); wp._log(get_conn,int(u["id"]),"EDIT_FOCUS_CATEGORY","weekly_focus_category",fid,f"order={int(order)}"); st.rerun()
    prev=year-1; prev_df=wp._focus_df(get_conn,prev,active_only=False); cur_df=wp._focus_df(get_conn,year,active_only=False)
    if not prev_df.empty and cur_df.empty:
        if st.button(f"📋 Sao chép toàn bộ danh mục {prev} → {year}",use_container_width=True,key="weekly_focus_copy_year"):
            with get_conn() as c:
                for _,r in prev_df.iterrows():
                    c.execute("""INSERT OR IGNORE INTO weekly_focus_categories(scope_key,year,code,name,description,display_order,status,created_by,created_at,updated_at)
                        VALUES('KHDN',?,?,?,?,?,'ACTIVE',?,?,?)""",(year,str(r["code"]),str(r["name"]),str(r["description"] or ""),int(r["display_order"] or 0),int(u["id"]),wp._now(),wp._now()))
                c.commit()
            wp._log(get_conn,int(u["id"]),"COPY_FOCUS_YEAR","weekly_focus_category","",f"{prev}->{year}"); st.rerun()


def weekly_plan_page(u,get_conn:Callable,page_title:Callable,pill_nav:Optional[Callable]=None):
    _init_v4_schema(get_conn); _apply_score_fallbacks(get_conn); wp._inject_weekly_css(); v2._inject_css()
    page_title("Kế hoạch tuần","Quản trị ưu tiên theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư."); v2._glossary()
    if wp._is_leader(u): options=[("mine","📅 Kế hoạch của tôi"),("review","✅ Duyệt & đánh giá"),("focus","🎯 Trọng tâm Q2"),("room","📊 Tổng quan phòng"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    else: options=[("mine","📅 Tuần của tôi"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    if pill_nav: view=pill_nav("weekly_plan_view",options,default="mine",prefix="weekly_plan_v4")
    else:
        labels=[x[1] for x in options]; values=[x[0] for x in options]; current=st.session_state.get("weekly_plan_view","mine"); idx=values.index(current) if current in values else 0; selected=st.radio("Chế độ",labels,index=idx,horizontal=True,label_visibility="collapsed"); view=dict((label,value) for value,label in options)[selected]; st.session_state["weekly_plan_view"]=view
    if view=="mine": _my_plan(get_conn,u)
    elif view=="review" and wp._is_leader(u): _leader_review(get_conn,u)
    elif view=="focus" and wp._is_leader(u): _focus_maintenance(get_conn,u)
    elif view=="room" and wp._is_leader(u): v3._room_dashboard(get_conn)
    elif view=="history": v2._history_view(get_conn,u)
    elif view=="export": v3._export_view(get_conn,u)
