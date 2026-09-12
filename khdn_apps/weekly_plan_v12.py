"""Weekly Plan V12: FR-33 configurable parameters and FR-34 audited unlock.

Source-faithful scope:
- FR-33 explicitly asks configurable Q1-Q4 share thresholds, score weights,
  reminder times and min/max work-item limits. This implementation uses the
  quadrant weights defined in scoring section 7.1 as the configurable score
  weights; it does not invent extra hidden scoring formulas.
- FR-34 says an administrator may unlock an evaluated week with audit logging,
  but does not define the target state. To avoid an implicit choice, the admin
  UI exposes two explicit unlock levels: re-open for leader re-review, or re-open
  for staff update. The pre-unlock review snapshot is retained immutably in a
  dedicated history table.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v4 as v4
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v7 as v7
from khdn_apps import weekly_plan_v10 as v10
from khdn_apps import weekly_plan_v11 as v11


DEFAULT_PARAMETERS = {
    "q2_target_pct": (60.0, "Tỷ trọng mục tiêu Q2 tối thiểu (%)"),
    "q1_max_pct": (20.0, "Tỷ trọng mục tiêu Q1 tối đa (%)"),
    "q3_max_pct": (15.0, "Tỷ trọng mục tiêu Q3 tối đa (%)"),
    "q4_target_pct": (5.0, "Tỷ trọng mục tiêu Q4 tối đa (%)"),
    "q4_warning_pct": (20.0, "Ngưỡng cảnh báo mềm Q4 (%)"),
    "weight_q2": (3.0, "Trọng số điểm Q2"),
    "weight_q1": (3.0, "Trọng số điểm Q1"),
    "weight_q3": (1.0, "Trọng số điểm Q3"),
    "weight_q4": (0.0, "Trọng số điểm Q4"),
    "max_planned_tasks": (7.0, "Số công việc kế hoạch tối đa"),
    "min_q2_tasks": (3.0, "Số công việc Q2 tối thiểu"),
    "friday_plan_hour": (16.0, "Thứ 6 - giờ nhắc lập kế hoạch tuần sau"),
    "monday_plan_hour": (8.0, "Thứ 2 - giờ nhắc hoàn thiện kế hoạch"),
    "monday_submit_deadline_hour": (9.0, "Thứ 2 - hạn nộp kế hoạch"),
    "monday_late_notice_hour": (9.5, "Thứ 2 - giờ thông báo chưa nộp"),
    "due_reminder_hour": (8.0, "Giờ nhắc công việc đến hạn ngày mai"),
    "friday_close_hour": (14.0, "Thứ 6 - giờ nhắc chốt tuần"),
    "monday_leader_review_hour": (8.0, "Thứ 2 - giờ nhắc lãnh đạo nhận xét"),
}

_ORIGINAL_PROGRESS_SCORE = wp._progress_score
_ORIGINAL_VALIDATE_SUBMIT = wp._validate_submit
_ORIGINAL_V10_ADD = v10._ORIGINAL_ADD
_ORIGINAL_CARRY_PANEL = v2._carry_panel
_ORIGINAL_WARNINGS = v2._warnings
_ORIGINAL_QUADRANT_STRUCTURE = v4._quadrant_structure
_ORIGINAL_V7_NOTIFICATIONS = v7._generate_in_app_notifications


def _init_v12_schema(get_conn: Callable):
    v10._init_autosave_schema(get_conn)
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_parameters (
            parameter_key TEXT PRIMARY KEY,
            parameter_value REAL NOT NULL,
            description TEXT NOT NULL,
            updated_by INTEGER,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(updated_by) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS weekly_unlock_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            old_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            unlock_mode TEXT NOT NULL,
            reason TEXT NOT NULL,
            review_snapshot_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES weekly_plans(id),
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_weekly_unlock_plan_time
            ON weekly_unlock_history(plan_id,created_at);
        """)
        for key, (value, desc) in DEFAULT_PARAMETERS.items():
            c.execute("""INSERT OR IGNORE INTO weekly_parameters
                (parameter_key,parameter_value,description,updated_by,updated_at)
                VALUES(?,?,?,NULL,?)""", (key, float(value), desc, wp._now()))
        c.commit()


def _param(get_conn: Callable, key: str) -> float:
    default = float(DEFAULT_PARAMETERS[key][0])
    df = wp._qdf(get_conn, "SELECT parameter_value FROM weekly_parameters WHERE parameter_key=?", (key,))
    if df.empty:
        return default
    try:
        return float(df.iloc[0]["parameter_value"])
    except Exception:
        return default


def _parameter_map(get_conn: Callable):
    return {key: _param(get_conn, key) for key in DEFAULT_PARAMETERS}


def _time_from_decimal(value: float) -> time:
    value = max(0.0, min(23.983333, float(value)))
    hour = int(value)
    minute = int(round((value - hour) * 60))
    if minute >= 60:
        hour = min(23, hour + 1); minute = 0
    return time(hour, minute)


def _decimal_from_time(value: time) -> float:
    return float(value.hour) + float(value.minute) / 60.0


def _validate_submit_configured(get_conn: Callable, tasks: pd.DataFrame):
    errors = []
    if tasks is None or tasks.empty:
        return ["Kế hoạch chưa có công việc."]
    planned = tasks[pd.to_numeric(tasks["is_emergent"], errors="coerce").fillna(0).eq(0)].copy()
    max_tasks = int(round(_param(get_conn, "max_planned_tasks")))
    min_q2 = int(round(_param(get_conn, "min_q2_tasks")))
    if len(planned) > max_tasks:
        errors.append(f"Kế hoạch có trên {max_tasks} công việc.")
    q2 = int((planned["quadrant"] == "Q2").sum())
    if q2 < min_q2:
        errors.append(f"Cần tối thiểu {min_q2} công việc Q2; hiện có {q2}.")
    hours = float(pd.to_numeric(planned["planned_hours"], errors="coerce").fillna(0).sum())
    if hours > 45:
        errors.append(f"Tổng giờ dự kiến {hours:.1f}h vượt giới hạn 45h.")
    if planned["expected_result"].fillna("").astype(str).str.strip().eq("").any():
        errors.append("Có công việc thiếu kết quả đầu ra dự kiến.")
    return errors


def _progress_score_configured(get_conn: Callable, tasks: pd.DataFrame) -> float:
    if tasks is None or tasks.empty:
        return 0.0
    weights = {q: _param(get_conn, f"weight_{q.lower()}") for q in ("Q1","Q2","Q3","Q4")}
    numerator = denominator = 0.0
    for _, row in tasks.iterrows():
        if str(row.get("status")) == "CANCELLED":
            continue
        w = max(0.0, float(weights.get(str(row.get("quadrant")), 0.0)))
        denominator += w
        h = 0.0
        if str(row.get("status")) == "COMPLETED":
            h = 0.6
            try:
                if pd.to_datetime(row.get("completed_at")).date() <= pd.to_datetime(row.get("due_date")).date():
                    h = 1.0
            except Exception:
                h = 1.0
        numerator += w * h
    return 100.0 * numerator / denominator if denominator > 0 else 0.0


def _add_task_form_configured(get_conn, u, plan, *, emergent=False):
    """V6 due-driven form with only the spec-configurable task cap changed."""
    year = int(plan["iso_year"])
    focus = wp._focus_df(get_conn, year, active_only=True)
    options = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
    prefix = f"weekly_v6_{'emergent' if emergent else 'planned'}_{int(plan['id'])}"
    nonce_key = f"{prefix}_nonce"; nonce = int(st.session_state.get(nonce_key, 0))
    k = lambda name: f"{prefix}_{nonce}_{name}"
    title = st.text_input("Tên công việc *", max_chars=200, key=k("title"))
    focus_id = st.selectbox("Danh mục công việc trọng tâm Q2", options, format_func=v6._focus_formatter(focus), key=k("focus"),
        help="Q2 là công việc thuộc danh mục trọng tâm do Lãnh đạo phòng ban hành. Chọn một mục sẽ tự xếp Q2.")
    if focus_id and not focus.empty:
        r = focus[focus["id"].eq(int(focus_id))].iloc[0]; st.caption(f"Phạm vi: {r['description']}")
    c1,c2=st.columns(2)
    due=c1.date_input("Hạn hoàn thành *",value=date.today()+timedelta(days=3),key=k("due"))
    planned_hours=c2.number_input("Giờ dự kiến *",min_value=0.5,max_value=45.0,value=2.0,step=0.5,key=k("hours"))
    urgent=False if focus_id else v6._urgent_from_due(due)
    if focus_id:
        has_kpi=False
    elif urgent:
        st.caption("Hệ thống xác định **có tính cấp bách** vì hạn hoàn thành nằm trong 7 ngày tới.")
        has_kpi=st.checkbox("Gắn với chỉ tiêu được giao hoặc rủi ro trọng yếu?",key=k("kpi"),help="Dùng để phân biệt Q1 với Q3 khi công việc đã cấp bách.")
    else:
        has_kpi=False; st.caption("Hệ thống xác định **không cấp bách** vì hạn hoàn thành ngoài 7 ngày tới.")
    q,urgent,has_kpi=v6._classification_from_inputs(focus_id,due,has_kpi)
    st.info(f"Hệ thống phân loại: **{q} – {wp.QUADRANT_META[q][0]}**. {wp.QUADRANT_META[q][1]}")
    expected=st.text_area("Kết quả đầu ra dự kiến *",max_chars=300,key=k("expected"))
    submitted=st.button("➕ Thêm việc phát sinh" if emergent else "➕ Thêm vào kế hoạch",type="primary",use_container_width=True,key=k("submit"))
    if not submitted: return
    if not title.strip(): st.error("Tên công việc là bắt buộc."); return
    if not expected.strip(): st.error("Kết quả đầu ra dự kiến là bắt buộc."); return
    existing=wp._tasks_df(get_conn,int(plan["id"]))
    if not emergent:
        planned_only=existing[pd.to_numeric(existing.get("is_emergent",0),errors="coerce").fillna(0).eq(0)] if not existing.empty else existing
        max_tasks=int(round(_param(get_conn,"max_planned_tasks")))
        if len(planned_only)>=max_tasks:
            st.error(f"Kế hoạch tuần tối đa {max_tasks} công việc. Việc vượt giới hạn chỉ được thêm dưới dạng phát sinh."); return
        total_hours=float(pd.to_numeric(existing.get("planned_hours",pd.Series(dtype=float)),errors="coerce").fillna(0).sum()) if not existing.empty else 0.0
        if total_hours+float(planned_hours)>45:
            st.error("Tổng giờ dự kiến vượt 45 giờ. Hãy điều chỉnh trước khi thêm."); return
    task_id=wp._execute(get_conn,"""INSERT INTO weekly_tasks(
        plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,
        planned_hours,actual_hours,status,is_emergent,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,0,'NOT_STARTED',?,?,?)""",
        (int(plan["id"]),title.strip(),expected.strip(),int(focus_id) if focus_id else None,int(bool(urgent)),int(bool(has_kpi)),q,due.isoformat(),float(planned_hours),int(bool(emergent)),wp._now(),wp._now()))
    wp._log(get_conn,int(u["id"]),"ADD_EMERGENT_TASK" if emergent else "ADD_TASK","weekly_task",task_id,f"quadrant={q};urgency_from_due=1")
    st.session_state[nonce_key]=nonce+1; st.success("Đã thêm công việc."); st.rerun()


def _carry_panel_configured(get_conn: Callable, u, plan):
    cand=v2._carry_candidates(get_conn,int(u["id"]),int(plan["iso_year"]),int(plan["iso_week"]),int(plan["id"]))
    if cand.empty: return
    with st.expander(f"↪ Công việc chưa xong tuần trước ({len(cand)})",expanded=True):
        st.caption("Chuyển tiếp giữ lịch sử, liên kết công việc gốc và tăng số lần lùi.")
        for _,r in cand.iterrows():
            wp._render_task_card(r)
            if st.button("Chuyển tiếp sang tuần này",key=f"weekly_carry_{int(r['id'])}",use_container_width=True):
                current=wp._tasks_df(get_conn,int(plan["id"])); planned=current[pd.to_numeric(current["is_emergent"],errors="coerce").fillna(0).eq(0)] if not current.empty else current
                max_tasks=int(round(_param(get_conn,"max_planned_tasks")))
                if len(planned)>=max_tasks:
                    st.error(f"Kế hoạch đã đủ {max_tasks} công việc."); continue
                _,_,monday,_=wp._iso_week()
                try: due=max(pd.to_datetime(r.get("due_date")).date()+timedelta(days=7),monday)
                except Exception: due=monday+timedelta(days=4)
                task_id=wp._execute(get_conn,"""INSERT INTO weekly_tasks(
                    plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,
                    planned_hours,actual_hours,status,is_emergent,defer_count,source_task_id,defer_reason,original_due_date,
                    classification_locked,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,0,'NOT_STARTED',0,?,?,?,?,0,?,?)""",
                    (int(plan["id"]),str(r.get("title") or ""),str(r.get("expected_result") or ""),int(r["focus_category_id"]) if pd.notna(r.get("focus_category_id")) else None,int(r.get("is_urgent") or 0),int(r.get("has_kpi_or_risk") or 0),str(r.get("quadrant") or "Q4"),due.isoformat(),float(r.get("planned_hours") or 0),int(r.get("defer_count") or 0)+1,int(r["id"]),"Chuyển tiếp từ tuần trước",str(r.get("original_due_date") or r.get("due_date") or ""),wp._now(),wp._now()))
                wp._task_log(get_conn,task_id,int(u["id"]),"carry_forward",r.get("id"),task_id,"Chuyển tiếp tuần")
                wp._log(get_conn,int(u["id"]),"CARRY_FORWARD","weekly_task",task_id,f"source_task_id={int(r['id'])}"); st.rerun()


def _warnings_configured(get_conn: Callable, u, plan, tasks):
    if not tasks.empty:
        valid=tasks[tasks["status"].ne("CANCELLED")].copy(); total=float(pd.to_numeric(valid["planned_hours"],errors="coerce").fillna(0).sum()); q4=float(pd.to_numeric(valid.loc[valid["quadrant"].eq("Q4"),"planned_hours"],errors="coerce").fillna(0).sum()); pct=100.0*q4/total if total>0 else 0.0
        threshold=_param(get_conn,"q4_warning_pct")
        if pct>threshold:
            st.html(f'<div class="weekly-warn-card">⚠️ Giờ dự kiến Q4 chiếm {pct:.1f}%, vượt ngưỡng cảnh báo {threshold:.1f}%. Hãy rà soát lại trọng tâm.</div>')
        q2_late=valid[(valid["quadrant"]=="Q2")&(pd.to_numeric(valid["defer_count"],errors="coerce").fillna(0)>2)]
        if not q2_late.empty:
            import html as _html
            st.html(f'<div class="weekly-warn-card">🚩 Q2 bị lùi trên 2 tuần: {_html.escape(", ".join(q2_late["title"].astype(str).tolist()[:5]))}</div>')
    py,pw,_=v2._previous_iso(int(plan["iso_year"]),int(plan["iso_week"])); d=wp._qdf(get_conn,"""SELECT COUNT(*) n FROM weekly_classification_changes c JOIN weekly_plans p ON p.id=c.plan_id WHERE c.user_id=? AND p.iso_year=? AND p.iso_week=? AND c.old_quadrant='Q2' AND c.new_quadrant<>'Q2'""",(int(u["id"]),py,pw)); n=int(d.iloc[0]["n"]) if not d.empty else 0
    if n>=3: st.html(f'<div class="weekly-warn-card">🔎 Tuần trước có {n} công việc bị gỡ khỏi Q2. Cần trao đổi lại với lãnh đạo về cách hiểu trọng tâm.</div>')


def _quadrant_structure_configured(get_conn: Callable, tasks: pd.DataFrame):
    if tasks is None or tasks.empty: return
    valid=tasks[tasks["status"].ne("CANCELLED")].copy(); ptotal=float(pd.to_numeric(valid["planned_hours"],errors="coerce").fillna(0).sum()); atotal=float(pd.to_numeric(valid["actual_hours"],errors="coerce").fillna(0).sum())
    targets={"Q2":f"≥{_param(get_conn,'q2_target_pct'):.1f}%","Q1":f"≤{_param(get_conn,'q1_max_pct'):.1f}%","Q3":f"≤{_param(get_conn,'q3_max_pct'):.1f}%","Q4":f"≤{_param(get_conn,'q4_target_pct'):.1f}%"}
    rows=[]
    for q in ["Q2","Q1","Q3","Q4"]:
        ph=float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q),"planned_hours"],errors="coerce").fillna(0).sum()); ah=float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q),"actual_hours"],errors="coerce").fillna(0).sum())
        rows.append({"Nhóm":f"{q} – {wp.QUADRANT_META[q][0]}","Mục tiêu":targets[q],"Giờ KH":f"{ph:.1f}","KH %":f"{100*ph/ptotal:.1f}%" if ptotal else "0.0%","Giờ TT":f"{ah:.1f}","TT %":f"{100*ah/atotal:.1f}%" if atotal else "0.0%"})
    st.markdown("### Cơ cấu thời gian Q1–Q4"); v2._html_table(pd.DataFrame(rows),300)


def _generate_notifications_configured(get_conn: Callable, u):
    uid=int(u["id"]); year,week,monday,_=wp._iso_week(); now=datetime.now(); weekday=now.weekday(); hour=now.hour+now.minute/60.0
    fri_plan=_param(get_conn,"friday_plan_hour"); mon_plan=_param(get_conn,"monday_plan_hour"); late=_param(get_conn,"monday_late_notice_hour"); due_hour=_param(get_conn,"due_reminder_hour"); fri_close=_param(get_conn,"friday_close_hour"); leader_review=_param(get_conn,"monday_leader_review_hour")
    if wp._is_officer(u) or wp._is_leader(u):
        plan=wp._get_or_create_plan(get_conn,uid,year,week,monday,monday+timedelta(days=6)); status=str(plan.get("status") or "")
        if weekday==4 and hour>=fri_plan:
            next_monday=monday+timedelta(days=7); ni=next_monday.isocalendar(); v6._notify_once(get_conn,uid,f"plan_friday_next:{uid}:{int(ni.year)}:{int(ni.week)}","PLAN_REMINDER","Nhắc lập kế hoạch tuần",f"Hãy chuẩn bị kế hoạch cho tuần {int(ni.week)}/{int(ni.year)}.")
        if status in {"DRAFT","RETURNED"} and weekday==0 and hour>=mon_plan:
            deadline=_time_from_decimal(_param(get_conn,"monday_submit_deadline_hour")).strftime("%H:%M"); v6._notify_once(get_conn,uid,f"plan_monday8:{uid}:{year}:{week}","PLAN_REMINDER","Nhắc nộp kế hoạch",f"Hãy hoàn thiện và nộp kế hoạch tuần trước {deadline}.",plan["id"])
        if status in {"DRAFT","RETURNED"} and weekday==0 and hour>=late:
            v6._notify_once(get_conn,uid,f"not_submitted:{uid}:{year}:{week}","NOT_SUBMITTED","Kế hoạch chưa được nộp","Kế hoạch tuần hiện vẫn chưa được nộp cho Lãnh đạo phòng.",plan["id"])
        if status=="RETURNED": v6._notify_once(get_conn,uid,f"returned:{plan['id']}:{plan.get('updated_at')}","RETURNED","Kế hoạch bị trả lại",f"Lý do: {plan.get('return_reason') or '—'}",plan["id"])
        if status=="APPROVED" and weekday==4 and hour>=fri_close: v6._notify_once(get_conn,uid,f"close_friday:{uid}:{year}:{week}","CLOSE_REMINDER","Nhắc chốt tuần","Hãy cập nhật kết quả thực tế và chốt tuần.",plan["id"])
        if status=="REVIEWED": v6._notify_once(get_conn,uid,f"reviewed:{plan['id']}:{plan.get('reviewed_at')}","WEEK_RESULT","Kết quả tuần đã có","Lãnh đạo phòng đã hoàn tất nhận xét và chấm điểm tuần.",plan["id"])
        tasks=wp._tasks_df(get_conn,int(plan["id"]))
        if hour>=due_hour and not tasks.empty:
            tomorrow=date.today()+timedelta(days=1)
            for _,r in tasks.iterrows():
                if str(r.get("status")) in {"COMPLETED","CANCELLED"}: continue
                try: due=pd.to_datetime(r.get("due_date")).date()
                except Exception: continue
                if due==tomorrow: v6._notify_once(get_conn,uid,f"due_tomorrow:{int(r['id'])}:{due}","DUE_SOON","Công việc đến hạn ngày mai",str(r.get("title") or ""),plan["id"],r["id"])
        changes=wp._qdf(get_conn,"""SELECT c.id,c.old_quadrant,c.new_quadrant,t.title FROM weekly_classification_changes c JOIN weekly_tasks t ON t.id=c.task_id WHERE c.user_id=? ORDER BY c.id DESC LIMIT 50""",(uid,))
        for _,r in changes.iterrows(): v6._notify_once(get_conn,uid,f"reclass:{int(r['id'])}","RECLASSIFIED","Phân loại công việc đã được điều chỉnh",f"{r['title']}: {r['old_quadrant']} → {r['new_quadrant']}")
    if wp._is_leader(u):
        staff=wp._qdf(get_conn,"""SELECT u.id user_id,u.full_name,p.id plan_id,p.status,p.submitted_at,p.closed_at FROM users u LEFT JOIN weekly_plans p ON p.user_id=u.id AND p.iso_year=? AND p.iso_week=? WHERE u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') ORDER BY u.full_name""",(year,week))
        for _,p in staff.iterrows():
            plan_id=int(p["plan_id"]) if pd.notna(p.get("plan_id")) else None; status=str(p.get("status") or "") if plan_id else ""
            if status=="SUBMITTED": v6._notify_once(get_conn,uid,f"waiting_approval:{plan_id}:{p.get('submitted_at')}","WAITING_APPROVAL","Có kế hoạch chờ duyệt",f"{p['full_name']} đã nộp kế hoạch tuần.",plan_id)
            if status=="CLOSED" and weekday==0 and hour>=leader_review: v6._notify_once(get_conn,uid,f"waiting_review:{plan_id}:{year}:{week}","WAITING_REVIEW","Kế hoạch chờ nhận xét",f"{p['full_name']} đã chốt tuần và đang chờ nhận xét.",plan_id)
            if weekday==0 and hour>=late and (not plan_id or status in {"DRAFT","RETURNED"}):
                identity=plan_id if plan_id else f"user{int(p['user_id'])}"; v6._notify_once(get_conn,uid,f"leader_not_submitted:{identity}:{year}:{week}","NOT_SUBMITTED","Cán bộ chưa nộp kế hoạch",f"{p['full_name']} chưa nộp kế hoạch tuần.",plan_id)


def _install_parameter_overrides(get_conn: Callable):
    wp._validate_submit=lambda tasks:_validate_submit_configured(get_conn,tasks)
    wp._progress_score=lambda tasks:_progress_score_configured(get_conn,tasks)
    v10._ORIGINAL_ADD=_add_task_form_configured
    v2._carry_panel=lambda conn,u,plan:_carry_panel_configured(conn,u,plan)
    v2._warnings=lambda conn,u,plan,tasks:_warnings_configured(conn,u,plan,tasks)
    v4._quadrant_structure=lambda tasks:_quadrant_structure_configured(get_conn,tasks)
    v7._generate_in_app_notifications=_generate_notifications_configured
    v6._generate_in_app_notifications=_generate_notifications_configured


def _save_parameter_group(get_conn: Callable, u, values: dict):
    with get_conn() as c:
        for key,value in values.items():
            if key not in DEFAULT_PARAMETERS: continue
            c.execute("UPDATE weekly_parameters SET parameter_value=?,updated_by=?,updated_at=? WHERE parameter_key=?",(float(value),int(u["id"]),wp._now(),key))
        c.commit()
    wp._log(get_conn,int(u["id"]),"UPDATE_WEEKLY_PARAMETERS","weekly_parameters",";".join(sorted(values)),json.dumps({k:float(v) for k,v in values.items()},ensure_ascii=False))


def _parameter_admin(get_conn: Callable, u):
    st.markdown("### ⚙️ Tham số Kế hoạch tuần")
    st.caption("Các giá trị mặc định bám đặc tả v1.2. Thay đổi được ghi nhật ký và áp dụng cho các kỳ xử lý sau khi lưu.")
    p=_parameter_map(get_conn)
    with st.form("weekly_v12_param_form"):
        st.markdown("**Tỷ trọng mục tiêu & cảnh báo**")
        a,b=st.columns(2); q2=a.number_input("Q2 tối thiểu (%)",0.0,100.0,float(p["q2_target_pct"]),0.5); q1=b.number_input("Q1 tối đa (%)",0.0,100.0,float(p["q1_max_pct"]),0.5)
        c,d=st.columns(2); q3=c.number_input("Q3 tối đa (%)",0.0,100.0,float(p["q3_max_pct"]),0.5); q4=d.number_input("Q4 tối đa (%)",0.0,100.0,float(p["q4_target_pct"]),0.5)
        q4w=st.number_input("Ngưỡng cảnh báo mềm Q4 (%)",0.0,100.0,float(p["q4_warning_pct"]),0.5)
        st.markdown("**Trọng số điểm Q1–Q4**")
        w1,w2,w3,w4=st.columns(4); weight_q1=w1.number_input("Q1",0.0,10.0,float(p["weight_q1"]),0.5); weight_q2=w2.number_input("Q2",0.0,10.0,float(p["weight_q2"]),0.5); weight_q3=w3.number_input("Q3",0.0,10.0,float(p["weight_q3"]),0.5); weight_q4=w4.number_input("Q4",0.0,10.0,float(p["weight_q4"]),0.5)
        st.markdown("**Giới hạn kế hoạch**")
        e,f=st.columns(2); max_tasks=e.number_input("Số việc kế hoạch tối đa",3,20,int(round(p["max_planned_tasks"])),1); min_q2=f.number_input("Số việc Q2 tối thiểu",0,20,int(round(p["min_q2_tasks"])),1)
        st.markdown("**Thời điểm nhắc việc**")
        t1,t2,t3=st.columns(3); friday_plan=t1.time_input("Thứ 6 · lập tuần sau",_time_from_decimal(p["friday_plan_hour"])); monday_plan=t2.time_input("Thứ 2 · nhắc hoàn thiện",_time_from_decimal(p["monday_plan_hour"])); submit_deadline=t3.time_input("Thứ 2 · hạn nộp",_time_from_decimal(p["monday_submit_deadline_hour"]))
        t4,t5,t6=st.columns(3); late_notice=t4.time_input("Thứ 2 · báo chưa nộp",_time_from_decimal(p["monday_late_notice_hour"])); due_reminder=t5.time_input("Nhắc đến hạn ngày mai",_time_from_decimal(p["due_reminder_hour"])); friday_close=t6.time_input("Thứ 6 · nhắc chốt",_time_from_decimal(p["friday_close_hour"]))
        leader_review=st.time_input("Thứ 2 · nhắc lãnh đạo nhận xét",_time_from_decimal(p["monday_leader_review_hour"]))
        save=st.form_submit_button("💾 Lưu tham số",type="primary",use_container_width=True)
    if save:
        if int(min_q2)>int(max_tasks): st.error("Số việc Q2 tối thiểu không được lớn hơn số việc kế hoạch tối đa."); return
        if _decimal_from_time(late_notice)<_decimal_from_time(submit_deadline): st.error("Giờ báo chưa nộp phải bằng hoặc sau hạn nộp."); return
        values={"q2_target_pct":q2,"q1_max_pct":q1,"q3_max_pct":q3,"q4_target_pct":q4,"q4_warning_pct":q4w,"weight_q1":weight_q1,"weight_q2":weight_q2,"weight_q3":weight_q3,"weight_q4":weight_q4,"max_planned_tasks":max_tasks,"min_q2_tasks":min_q2,"friday_plan_hour":_decimal_from_time(friday_plan),"monday_plan_hour":_decimal_from_time(monday_plan),"monday_submit_deadline_hour":_decimal_from_time(submit_deadline),"monday_late_notice_hour":_decimal_from_time(late_notice),"due_reminder_hour":_decimal_from_time(due_reminder),"friday_close_hour":_decimal_from_time(friday_close),"monday_leader_review_hour":_decimal_from_time(leader_review)}
        _save_parameter_group(get_conn,u,values); st.success("Đã lưu tham số Kế hoạch tuần."); st.rerun()


def _unlock_admin(get_conn: Callable, u):
    st.markdown("### 🔓 Mở khóa kỳ tuần")
    st.caption("Đặc tả yêu cầu quản trị viên có thể mở khóa kỳ đã đánh giá và phải ghi nhật ký, nhưng không quy định trạng thái đích. Bản triển khai cho chọn rõ mức mở khóa thay vì tự suy diễn.")
    plans=wp._qdf(get_conn,"""SELECT p.id,p.user_id,p.iso_year,p.iso_week,p.status,u.full_name FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.status IN ('CLOSED','REVIEWED') ORDER BY p.iso_year DESC,p.iso_week DESC,u.full_name LIMIT 150""")
    if plans.empty: st.info("Không có kỳ đã chốt/đánh giá để mở khóa."); return
    pid=st.selectbox("Kỳ cần mở khóa",plans["id"].astype(int).tolist(),format_func=lambda x:f"{plans[plans['id'].eq(int(x))].iloc[0]['full_name']} · Tuần {int(plans[plans['id'].eq(int(x))].iloc[0]['iso_week'])}/{int(plans[plans['id'].eq(int(x))].iloc[0]['iso_year'])} · {wp.PLAN_STATUS_LABELS.get(str(plans[plans['id'].eq(int(x))].iloc[0]['status']),str(plans[plans['id'].eq(int(x))].iloc[0]['status']))}",key="weekly_v12_unlock_plan")
    mode=st.radio("Mức mở khóa",["Lãnh đạo đánh giá lại","Cán bộ cập nhật lại kỳ"],horizontal=True,key="weekly_v12_unlock_mode")
    reason=st.text_area("Lý do mở khóa *",max_chars=500,key="weekly_v12_unlock_reason")
    if st.button("🔓 Xác nhận mở khóa",type="primary",use_container_width=True,key="weekly_v12_unlock_button"):
        if not reason.strip(): st.error("Bắt buộc ghi lý do mở khóa."); return
        row=plans[plans["id"].eq(int(pid))].iloc[0].to_dict(); old_status=str(row["status"])
        rv=wp._review(get_conn,int(pid)) or {}; snapshot=json.dumps(rv,ensure_ascii=False,default=str)
        new_status="CLOSED" if mode=="Lãnh đạo đánh giá lại" else "APPROVED"; unlock_mode="LEADER_REVIEW" if new_status=="CLOSED" else "STAFF_UPDATE"; ts=wp._now()
        with get_conn() as c:
            c.execute("INSERT INTO weekly_unlock_history(plan_id,actor_user_id,old_status,new_status,unlock_mode,reason,review_snapshot_json,created_at) VALUES(?,?,?,?,?,?,?,?)",(int(pid),int(u["id"]),old_status,new_status,unlock_mode,reason.strip(),snapshot,ts))
            if new_status=="CLOSED":
                c.execute("UPDATE weekly_plans SET status='CLOSED',reviewed_at=NULL,updated_at=? WHERE id=?",(ts,int(pid)))
                c.execute("UPDATE weekly_reviews SET leader_score=NULL,leader_comment=NULL,score_gap_reason=NULL,progress_score=NULL,quality_score=NULL,week_score=NULL,grade=NULL,auto_fallback=0,updated_at=? WHERE plan_id=?",(ts,int(pid)))
            else:
                c.execute("UPDATE weekly_plans SET status='APPROVED',closed_at=NULL,reviewed_at=NULL,updated_at=? WHERE id=?",(ts,int(pid)))
                c.execute("UPDATE weekly_tasks SET classification_locked=0,updated_at=? WHERE plan_id=?",(ts,int(pid)))
                c.execute("UPDATE weekly_reviews SET leader_score=NULL,leader_comment=NULL,score_gap_reason=NULL,progress_score=NULL,quality_score=NULL,week_score=NULL,grade=NULL,auto_fallback=0,updated_at=? WHERE plan_id=?",(ts,int(pid)))
            c.commit()
        wp._log(get_conn,int(u["id"]),"UNLOCK_WEEKLY_PLAN","weekly_plan",pid,f"{old_status}->{new_status};mode={unlock_mode};reason={reason.strip()}")
        st.success("Đã mở khóa kỳ tuần và lưu bản chụp đánh giá trước khi mở khóa."); st.rerun()


def weekly_admin_panel(u, get_conn: Callable):
    if not bool((u or {}).get("is_admin")):
        st.error("Bạn không có quyền quản trị tham số Kế hoạch tuần."); return
    _init_v12_schema(get_conn)
    st.divider(); st.markdown("## 📅 Quản trị Kế hoạch tuần")
    tab1,tab2=st.tabs(["Tham số","Mở khóa kỳ"])
    with tab1: _parameter_admin(get_conn,u)
    with tab2: _unlock_admin(get_conn,u)


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    if not (wp._is_officer(u) or wp._is_leader(u)):
        st.error("Bạn không có quyền truy cập Kế hoạch tuần."); return
    _init_v12_schema(get_conn)
    _install_parameter_overrides(get_conn)
    return v11.weekly_plan_page(u,get_conn,page_title,pill_nav)
