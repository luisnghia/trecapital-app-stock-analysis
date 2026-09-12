"""Weekly Plan V11: FR-28 period filters and FR-29 chart drill-down.

The KHDN deployment represents one room, so the department filter is fixed to
Phòng KHDN instead of duplicating organization data. Leaders can additionally
filter one staff member. Every chart rendered by the V11 personal/room dashboards
uses Streamlit Plotly selection and exposes the task list behind the selected
point. No Ban Giám đốc view is introduced.
"""
from __future__ import annotations

import calendar
import html
import re
from collections import Counter
from datetime import date, timedelta
from typing import Callable, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v6 as v6
from khdn_apps import weekly_plan_v8 as v8
from khdn_apps import weekly_plan_v10 as v10


PERIOD_MODES = ("Tuần", "Tháng", "Quý")
STAFF_ROLES = ("Cán bộ hỗ trợ", "Cán bộ QLKH")


def _period_bounds(mode: str, anchor: date):
    anchor = pd.to_datetime(anchor).date()
    if mode == "Tháng":
        start = anchor.replace(day=1)
        end = anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])
        return start, end
    if mode == "Quý":
        first_month = ((anchor.month - 1) // 3) * 3 + 1
        start = date(anchor.year, first_month, 1)
        last_month = first_month + 2
        end = date(anchor.year, last_month, calendar.monthrange(anchor.year, last_month)[1])
        return start, end
    start = anchor - timedelta(days=anchor.weekday())
    return start, start + timedelta(days=6)


def _period_label(mode: str, start: date, end: date):
    if mode == "Tuần":
        iso = start.isocalendar()
        return f"Tuần {int(iso.week)}/{int(iso.year)} · {start:%d/%m/%Y}–{end:%d/%m/%Y}"
    if mode == "Tháng":
        return f"Tháng {start.month}/{start.year} · {start:%d/%m/%Y}–{end:%d/%m/%Y}"
    quarter = (start.month - 1) // 3 + 1
    return f"Quý {quarter}/{start.year} · {start:%d/%m/%Y}–{end:%d/%m/%Y}"


def _selection_points(event):
    if event is None:
        return []
    try:
        selection = event.selection
    except Exception:
        selection = event.get("selection", {}) if isinstance(event, dict) else {}
    try:
        points = selection.points
    except Exception:
        points = selection.get("points", []) if isinstance(selection, dict) else []
    try:
        return list(points or [])
    except Exception:
        return []


def _point_value(point, key, default=None):
    if isinstance(point, dict):
        return point.get(key, default)
    try:
        return getattr(point, key)
    except Exception:
        return default


def _staff_df(get_conn: Callable):
    return wp._qdf(get_conn, """SELECT id,full_name,username,role FROM users
        WHERE active=1 AND role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') ORDER BY full_name""")


def _filter_controls(get_conn: Callable, prefix: str, *, allow_staff: bool):
    c1, c2 = st.columns(2)
    mode = c1.selectbox("Kỳ xem", PERIOD_MODES, index=0, key=f"{prefix}_period_mode")
    anchor = c2.date_input("Ngày thuộc kỳ", value=date.today(), key=f"{prefix}_period_anchor")
    start, end = _period_bounds(mode, anchor)
    selected_user = 0
    if allow_staff:
        c3, c4 = st.columns(2)
        c3.selectbox("Phòng", ["KHDN"], index=0, disabled=True, key=f"{prefix}_room")
        staff = _staff_df(get_conn)
        choices = [0] + (staff["id"].astype(int).tolist() if not staff.empty else [])
        def fmt(uid):
            if int(uid) == 0:
                return "Tất cả cán bộ"
            row = staff[staff["id"].eq(int(uid))]
            return str(row.iloc[0]["full_name"]) if not row.empty else str(uid)
        selected_user = int(c4.selectbox("Cán bộ", choices, format_func=fmt, key=f"{prefix}_staff"))
    st.caption(_period_label(mode, start, end))
    return mode, start, end, selected_user


def _plans_period(get_conn: Callable, start: date, end: date, user_id: int = 0):
    sql = """SELECT p.*,u.full_name,u.username,u.role FROM weekly_plans p
        JOIN users u ON u.id=p.user_id
        WHERE date(p.start_date)<=date(?) AND date(p.end_date)>=date(?)"""
    params = [end.isoformat(), start.isoformat()]
    if user_id:
        sql += " AND p.user_id=?"
        params.append(int(user_id))
    sql += " ORDER BY p.iso_year,p.iso_week,u.full_name"
    return wp._qdf(get_conn, sql, tuple(params))


def _tasks_period(get_conn: Callable, start: date, end: date, user_id: int = 0):
    sql = """SELECT t.*,p.user_id,p.iso_year,p.iso_week,p.start_date,p.end_date,
        u.full_name,u.username,u.role,f.code focus_code,f.name focus_name
        FROM weekly_tasks t JOIN weekly_plans p ON p.id=t.plan_id
        JOIN users u ON u.id=p.user_id
        LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
        WHERE date(p.start_date)<=date(?) AND date(p.end_date)>=date(?)"""
    params = [end.isoformat(), start.isoformat()]
    if user_id:
        sql += " AND p.user_id=?"
        params.append(int(user_id))
    sql += " ORDER BY p.iso_year,p.iso_week,u.full_name,t.id"
    return wp._qdf(get_conn, sql, tuple(params))


def _reviews_period(get_conn: Callable, start: date, end: date, user_id: int = 0):
    sql = """SELECT r.*,p.user_id,p.iso_year,p.iso_week,p.start_date,p.end_date,
        u.full_name,u.username,u.role FROM weekly_reviews r
        JOIN weekly_plans p ON p.id=r.plan_id JOIN users u ON u.id=p.user_id
        WHERE date(p.start_date)<=date(?) AND date(p.end_date)>=date(?)"""
    params = [end.isoformat(), start.isoformat()]
    if user_id:
        sql += " AND p.user_id=?"
        params.append(int(user_id))
    sql += " ORDER BY p.iso_year,p.iso_week,u.full_name"
    return wp._qdf(get_conn, sql, tuple(params))


def _render_task_subset(tasks: pd.DataFrame, title: str):
    st.markdown(f"#### {title}")
    if tasks is None or tasks.empty:
        st.info("Không có công việc phù hợp với điểm dữ liệu đã chọn.")
        return
    for _, row in tasks.sort_values(["iso_year", "iso_week", "id"], ascending=[False, False, True]).iterrows():
        name = str(row.get("full_name") or "")
        week = f"Tuần {int(row['iso_week'])}/{int(row['iso_year'])}" if pd.notna(row.get("iso_week")) else ""
        if name:
            st.caption(f"{name} · {week}")
        wp._render_task_card(row)


def _period_metrics(tasks: pd.DataFrame, reviews: pd.DataFrame):
    valid = tasks[tasks["status"].ne("CANCELLED")].copy() if tasks is not None and not tasks.empty else pd.DataFrame()
    total = len(valid)
    done = int(valid["status"].eq("COMPLETED").sum()) if total else 0
    on_time = 0
    if total:
        completed = valid[valid["status"].eq("COMPLETED")].copy()
        if not completed.empty:
            comp = pd.to_datetime(completed["completed_at"], errors="coerce").dt.date
            due = pd.to_datetime(completed["due_date"], errors="coerce").dt.date
            on_time = int((comp <= due).fillna(False).sum())
    scores = pd.to_numeric(reviews.get("week_score", pd.Series(dtype=float)), errors="coerce").dropna() if reviews is not None and not reviews.empty else pd.Series(dtype=float)
    avg_score = float(scores.mean()) if not scores.empty else None
    actual = float(pd.to_numeric(valid.get("actual_hours", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if total else 0.0
    q2_hours = float(pd.to_numeric(valid.loc[valid["quadrant"].eq("Q2"), "actual_hours"], errors="coerce").fillna(0).sum()) if total else 0.0
    emergent = int(pd.to_numeric(valid.get("is_emergent", pd.Series(dtype=float)), errors="coerce").fillna(0).astype(int).sum()) if total else 0
    return {
        "total": total,
        "done": done,
        "on_time": on_time,
        "avg_score": avg_score,
        "grade": wp._score_grade(avg_score) if avg_score is not None else "—",
        "q2_pct": 100.0 * q2_hours / actual if actual > 0 else 0.0,
        "emergent_pct": 100.0 * emergent / total if total else 0.0,
    }


def _personal_metric_cards(tasks: pd.DataFrame, reviews: pd.DataFrame):
    m = _period_metrics(tasks, reviews)
    completion = 100.0 * m["done"] / m["total"] if m["total"] else 0.0
    on_time = 100.0 * m["on_time"] / m["done"] if m["done"] else 0.0
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Điểm TB kỳ", f"{m['avg_score']:.1f}" if m["avg_score"] is not None else "—")
    c2.metric("Xếp loại theo điểm TB", m["grade"])
    c3.metric("Tỷ lệ hoàn thành", f"{completion:.1f}%")
    c4.metric("Tỷ lệ đúng hạn", f"{on_time:.1f}%")
    st.caption(f"Chỉ số Q2: {m['q2_pct']:.1f}% giờ thực tế · Tỷ lệ việc phát sinh: {m['emergent_pct']:.1f}%")


def _personal_quadrant_chart(tasks: pd.DataFrame):
    if tasks.empty:
        st.info("Kỳ được chọn chưa có công việc.")
        return None
    valid = tasks[tasks["status"].ne("CANCELLED")].copy()
    labels = ["Q2", "Q1", "Q3", "Q4"]
    planned = [float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q), "planned_hours"], errors="coerce").fillna(0).sum()) for q in labels]
    actual = [float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q), "actual_hours"], errors="coerce").fillna(0).sum()) for q in labels]
    fig = make_subplots(rows=1, cols=2, specs=[[{"type":"domain"},{"type":"domain"}]], subplot_titles=("Giờ kế hoạch", "Giờ thực tế"))
    palette = ["#62D7AF", "#FF7B72", "#F4B41A", "#8AA6A1"]
    fig.add_trace(go.Pie(labels=labels, values=planned, hole=.55, marker=dict(colors=palette), textinfo="label+percent"), 1, 1)
    fig.add_trace(go.Pie(labels=labels, values=actual, hole=.55, marker=dict(colors=palette), textinfo="label+percent"), 1, 2)
    fig.update_layout(height=330, margin=dict(l=10,r=10,t=50,b=20), paper_bgcolor="#0E1F1E", font=dict(color="#F4FFFC"), showlegend=False)
    return st.plotly_chart(fig, use_container_width=True, key="weekly_v11_personal_quadrant", on_select="rerun", selection_mode="points")


def _weekly_trend_frame(tasks: pd.DataFrame, reviews: pd.DataFrame):
    keys = ["plan_id", "iso_year", "iso_week"]
    plan_rows = []
    if tasks is not None and not tasks.empty:
        for vals, group in tasks.groupby(keys, dropna=False):
            valid = group[group["status"].ne("CANCELLED")]
            actual = float(pd.to_numeric(valid["actual_hours"], errors="coerce").fillna(0).sum())
            q2h = float(pd.to_numeric(valid.loc[valid["quadrant"].eq("Q2"), "actual_hours"], errors="coerce").fillna(0).sum())
            plan_rows.append({"plan_id": vals[0], "iso_year": vals[1], "iso_week": vals[2], "q2_pct": 100.0*q2h/actual if actual else 0.0})
    frame = pd.DataFrame(plan_rows)
    if reviews is not None and not reviews.empty:
        rv = reviews[["plan_id","iso_year","iso_week","week_score","leader_comment"]].drop_duplicates("plan_id")
        frame = rv.merge(frame, on=["plan_id","iso_year","iso_week"], how="outer") if not frame.empty else rv.assign(q2_pct=0.0)
    if frame.empty:
        return frame
    frame["Tuần"] = frame.apply(lambda r: f"{int(r['iso_week'])}/{int(r['iso_year'])}", axis=1)
    return frame.sort_values(["iso_year","iso_week"])


def _personal_trend_chart(frame: pd.DataFrame):
    if frame.empty:
        st.caption("Chưa có dữ liệu xu hướng trong kỳ.")
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame["Tuần"], y=pd.to_numeric(frame["q2_pct"], errors="coerce").fillna(0), mode="lines+markers", name="Chỉ số Q2"))
    fig.add_trace(go.Scatter(x=frame["Tuần"], y=pd.to_numeric(frame["week_score"], errors="coerce"), mode="lines+markers", name="Điểm tuần"))
    fig.update_layout(height=320, margin=dict(l=20,r=20,t=30,b=40), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"), yaxis=dict(range=[0,100]), legend=dict(orientation="h"))
    return st.plotly_chart(fig, use_container_width=True, key="weekly_v11_personal_trend", on_select="rerun", selection_mode="points")


def _personal_focus_chart(tasks: pd.DataFrame):
    q2 = tasks[(tasks["status"].ne("CANCELLED")) & (tasks["quadrant"].eq("Q2"))].copy() if not tasks.empty else tasks
    if q2.empty:
        st.caption("Chưa có giờ thực tế Q2 trong kỳ.")
        return None, pd.DataFrame()
    q2["focus_label"] = q2.apply(lambda r: f"{r.get('focus_code') or '—'} — {r.get('focus_name') or 'Không xác định'}", axis=1)
    dist = q2.groupby("focus_label", as_index=False)["actual_hours"].sum().sort_values("actual_hours")
    fig = go.Figure(go.Bar(x=pd.to_numeric(dist["actual_hours"], errors="coerce"), y=dist["focus_label"], orientation="h", text=[f"{float(v):.1f}h" for v in dist["actual_hours"]], textposition="auto"))
    fig.update_layout(height=max(280,45*len(dist)+100), margin=dict(l=20,r=20,t=25,b=40), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"), xaxis_title="Giờ thực tế")
    event = st.plotly_chart(fig, use_container_width=True, key="weekly_v11_personal_focus", on_select="rerun", selection_mode="points")
    return event, q2


def _personal_dashboard_filtered(get_conn: Callable, u):
    st.markdown("### Dashboard cá nhân")
    _, start, end, _ = _filter_controls(get_conn, "weekly_v11_personal", allow_staff=False)
    tasks = _tasks_period(get_conn, start, end, int(u["id"]))
    reviews = _reviews_period(get_conn, start, end, int(u["id"]))
    _personal_metric_cards(tasks, reviews)

    st.markdown("### Cơ cấu giờ Q1–Q4 · kế hoạch so với thực tế")
    q_event = _personal_quadrant_chart(tasks)
    points = _selection_points(q_event)
    if points:
        p = points[0]
        q = _point_value(p, "label")
        if not q:
            idx = _point_value(p, "point_index", _point_value(p, "pointNumber", None))
            labels = ["Q2","Q1","Q3","Q4"]
            try: q = labels[int(idx)]
            except Exception: q = None
        if q in {"Q1","Q2","Q3","Q4"}:
            _render_task_subset(tasks[tasks["quadrant"].eq(q)], f"Chi tiết {q} phía sau biểu đồ")

    trend = _weekly_trend_frame(tasks, reviews)
    st.markdown("### Xu hướng chỉ số Q2 & điểm tuần")
    t_event = _personal_trend_chart(trend)
    tpoints = _selection_points(t_event)
    if tpoints:
        week_label = str(_point_value(tpoints[0], "x", ""))
        try:
            week, year = [int(x) for x in week_label.split("/")]
            _render_task_subset(tasks[(tasks["iso_week"].eq(week)) & (tasks["iso_year"].eq(year))], f"Chi tiết tuần {week_label}")
        except Exception:
            pass

    st.markdown("### Công việc cần chú ý")
    if tasks.empty:
        st.caption("Chưa có dữ liệu.")
    else:
        due = pd.to_datetime(tasks["due_date"], errors="coerce").dt.date
        overdue = tasks[(~tasks["status"].isin(["COMPLETED","CANCELLED"])) & due.notna() & (due < date.today())]
        repeated = tasks[(tasks["quadrant"].eq("Q2")) & (pd.to_numeric(tasks["defer_count"], errors="coerce").fillna(0) > 2)]
        problem = pd.concat([overdue, repeated]).drop_duplicates("id")
        if problem.empty: st.success("Không có công việc trễ hạn hoặc Q2 bị lùi trên 2 lần trong kỳ.")
        else: _render_task_subset(problem, "Danh sách cần chú ý")

    st.markdown("### Giờ Q2 theo danh mục trọng tâm")
    f_event, q2tasks = _personal_focus_chart(tasks)
    fpoints = _selection_points(f_event)
    if fpoints and not q2tasks.empty:
        focus_label = str(_point_value(fpoints[0], "y", ""))
        subset = q2tasks[q2tasks["focus_label"].eq(focus_label)]
        _render_task_subset(subset, f"Chi tiết trọng tâm {focus_label}")

    st.markdown("### Lịch sử nhận xét của Lãnh đạo phòng")
    if reviews.empty:
        st.caption("Chưa có nhận xét của lãnh đạo trong kỳ.")
    else:
        comments = reviews[reviews["leader_comment"].fillna("").astype(str).str.strip().ne("")].sort_values(["iso_year","iso_week"], ascending=False)
        if comments.empty:
            st.caption("Chưa có nhận xét của lãnh đạo trong kỳ.")
        for _, r in comments.iterrows():
            score = f"{float(r['week_score']):.1f}" if pd.notna(r.get("week_score")) else "—"
            grade = str(r.get("grade") or "—")
            st.html(f'<div class="weekly-dashboard-card"><b>Tuần {int(r["iso_week"])}/{int(r["iso_year"])}</b> · Điểm {score} · {html.escape(grade)}<br><span class="muted">{html.escape(str(r["leader_comment"]))}</span></div>')

    with st.expander("🧮 Cách tính điểm", expanded=False):
        st.markdown("**Điểm tiến độ:** Q1/Q2 trọng số 3; Q3 trọng số 1; Q4 trọng số 0. Hoàn thành đúng hạn hệ số 1, trễ hạn hệ số 0,6, chưa hoàn thành hệ số 0.")
        st.markdown("**Điểm chất lượng:** 20 × (0,3 × tự chấm + 0,7 × điểm Lãnh đạo phòng). Nếu chưa có nhận xét sau 5 ngày làm việc, tạm lấy tự chấm với hệ số 1,0.")
        st.markdown("**Điểm tuần:** 0,5 × Điểm tiến độ + 0,5 × Điểm chất lượng. A ≥90; B 75–<90; C 60–<75; D <60.")
        v8._quality_scale_table()


def _room_period_frames(get_conn: Callable, start: date, end: date, user_id: int = 0):
    staff = _staff_df(get_conn)
    if user_id and not staff.empty:
        staff = staff[staff["id"].eq(int(user_id))].copy()
    plans = _plans_period(get_conn, start, end, user_id)
    tasks = _tasks_period(get_conn, start, end, user_id)
    reviews = _reviews_period(get_conn, start, end, user_id)
    return staff, plans, tasks, reviews


def _room_summary(staff: pd.DataFrame, plans: pd.DataFrame, tasks: pd.DataFrame, reviews: pd.DataFrame):
    rows = []
    for _, u in staff.iterrows():
        uid = int(u["id"])
        pp = plans[plans["user_id"].eq(uid)] if not plans.empty else plans
        tt = tasks[tasks["user_id"].eq(uid)] if not tasks.empty else tasks
        rr = reviews[reviews["user_id"].eq(uid)] if not reviews.empty else reviews
        valid = tt[tt["status"].ne("CANCELLED")] if not tt.empty else tt
        total = len(valid); done = int(valid["status"].eq("COMPLETED").sum()) if total else 0
        actual = float(pd.to_numeric(valid.get("actual_hours", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if total else 0.0
        q2h = float(pd.to_numeric(valid.loc[valid["quadrant"].eq("Q2"), "actual_hours"], errors="coerce").fillna(0).sum()) if total else 0.0
        scores = pd.to_numeric(rr.get("week_score", pd.Series(dtype=float)), errors="coerce").dropna() if not rr.empty else pd.Series(dtype=float)
        avg = float(scores.mean()) if not scores.empty else None
        statuses = set(pp["status"].astype(str).tolist()) if not pp.empty else set()
        if not pp.empty and len(pp) == 1:
            status_label = wp.PLAN_STATUS_LABELS.get(str(pp.iloc[0]["status"]), str(pp.iloc[0]["status"]))
        elif pp.empty:
            status_label = "Chưa có kế hoạch"
        elif "SUBMITTED" in statuses:
            status_label = "Có kế hoạch chờ duyệt"
        elif "CLOSED" in statuses:
            status_label = "Có tuần chờ nhận xét"
        else:
            status_label = f"{len(pp)} tuần có dữ liệu"
        rows.append({
            "user_id":uid,"Cán bộ":str(u["full_name"]),"Vai trò":str(u["role"]),"Trạng thái":status_label,
            "Hoàn thành":f"{done}/{total}","Q2":100.0*q2h/actual if actual else 0.0,
            "Điểm TB":avg,"Xếp loại":wp._score_grade(avg) if avg is not None else "—"
        })
    return pd.DataFrame(rows)


def _room_score_chart(summary: pd.DataFrame):
    scored = summary[pd.to_numeric(summary["Điểm TB"], errors="coerce").notna()].copy() if not summary.empty else summary
    if scored.empty:
        st.caption("Chưa có điểm tuần trong kỳ.")
        return None
    avg = float(pd.to_numeric(scored["Điểm TB"], errors="coerce").mean())
    fig = go.Figure()
    fig.add_trace(go.Bar(x=scored["Cán bộ"], y=pd.to_numeric(scored["Điểm TB"], errors="coerce"), name="Điểm TB"))
    fig.add_trace(go.Scatter(x=scored["Cán bộ"], y=[avg]*len(scored), name=f"TB phòng {avg:.1f}", mode="lines"))
    fig.update_layout(height=330, margin=dict(l=20,r=20,t=25,b=50), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"), yaxis=dict(range=[0,100]), legend=dict(orientation="h"))
    return st.plotly_chart(fig, use_container_width=True, key="weekly_v11_room_scores", on_select="rerun", selection_mode="points")


def _room_heatmap(tasks: pd.DataFrame, staff: pd.DataFrame):
    if tasks.empty:
        st.caption("Chưa có dữ liệu Q2 để lập bản đồ nhiệt.")
        return None
    rows=[]
    for (uid, year, week), group in tasks.groupby(["user_id","iso_year","iso_week"]):
        valid=group[group["status"].ne("CANCELLED")]
        actual=float(pd.to_numeric(valid["actual_hours"],errors="coerce").fillna(0).sum())
        q2h=float(pd.to_numeric(valid.loc[valid["quadrant"].eq("Q2"),"actual_hours"],errors="coerce").fillna(0).sum())
        name_row=staff[staff["id"].eq(int(uid))]
        name=str(name_row.iloc[0]["full_name"]) if not name_row.empty else str(uid)
        rows.append({"Cán bộ":name,"Tuần":f"{int(week)}/{int(year)}","Q2":100.0*q2h/actual if actual else 0.0})
    h=pd.DataFrame(rows)
    if h.empty: return None
    pivot=h.pivot_table(index="Cán bộ",columns="Tuần",values="Q2",aggfunc="mean",fill_value=0)
    fig=go.Figure(go.Heatmap(z=pivot.values,x=pivot.columns.tolist(),y=pivot.index.tolist(),zmin=0,zmax=100,
        colorbar=dict(title="Q2 %"),text=[[f"{v:.1f}%" for v in row] for row in pivot.values],texttemplate="%{text}"))
    fig.update_layout(height=max(280,45*len(pivot)+120),margin=dict(l=30,r=20,t=25,b=40),paper_bgcolor="#0E1F1E",plot_bgcolor="#17312F",font=dict(color="#F4FFFC"))
    return st.plotly_chart(fig,use_container_width=True,key="weekly_v11_room_heatmap",on_select="rerun",selection_mode="points")


def _room_focus_matrix(tasks: pd.DataFrame):
    q2=tasks[(tasks["quadrant"].eq("Q2")) & (tasks["status"].ne("CANCELLED"))].copy() if not tasks.empty else tasks
    if q2.empty:
        st.caption("Chưa có dữ liệu trọng tâm Q2 trong kỳ."); return
    q2["Trọng tâm Q2"]=q2.apply(lambda r:f"{r.get('focus_code') or '—'} — {r.get('focus_name') or 'Không xác định'}",axis=1)
    matrix=q2.pivot_table(index="Trọng tâm Q2",columns="full_name",values="actual_hours",aggfunc="sum",fill_value=0).reset_index()
    for c in matrix.columns[1:]: matrix[c]=pd.to_numeric(matrix[c],errors="coerce").fillna(0).map(lambda x:f"{float(x):.1f}h")
    v2._html_table(matrix,430)


def _room_reclass_counts(get_conn: Callable, start: date, end: date, user_id: int = 0):
    sql="""SELECT u.full_name,COUNT(*) changes,
        SUM(CASE WHEN c.old_quadrant='Q2' AND c.new_quadrant<>'Q2' THEN 1 ELSE 0 END) removed_q2
        FROM weekly_classification_changes c JOIN users u ON u.id=c.user_id
        WHERE date(c.created_at)>=date(?) AND date(c.created_at)<=date(?)"""
    params=[start.isoformat(),end.isoformat()]
    if user_id:
        sql+=" AND c.user_id=?"; params.append(int(user_id))
    sql+=" GROUP BY u.id,u.full_name ORDER BY changes DESC,u.full_name"
    df=wp._qdf(get_conn,sql,tuple(params))
    if df.empty: st.caption("Không có điều chỉnh phân loại trong kỳ.")
    else: v2._html_table(df.rename(columns={"full_name":"Cán bộ","changes":"Số lần điều chỉnh","removed_q2":"Số lần gỡ Q2"}),350)


def _room_limitation_keywords(reviews: pd.DataFrame):
    if reviews.empty:
        st.caption("Chưa có đủ nội dung 'Tồn tại, hạn chế' trong kỳ."); return
    stop={"và","có","còn","chưa","việc","công","trong","của","cho","được","cần","một","các","với","do","đã","là","ở","từ","theo","không","nên","về","để","này","tuần"}
    words=[]
    for text in reviews["limitations"].fillna("").astype(str):
        words.extend(w for w in re.findall(r"[A-Za-zÀ-ỹĐđ]{3,}",text.lower()) if w not in stop)
    counts=Counter(words).most_common(12)
    if not counts: st.caption("Chưa xác định được từ khóa lặp lại."); return
    pills="".join(f'<span class="weekly-badge" style="margin:3px">{html.escape(w)} · {n}</span>' for w,n in counts)
    st.html(f'<div class="weekly-dashboard-card">{pills}</div>')


def _room_dashboard_filtered(get_conn: Callable):
    st.markdown("### Tổng quan phòng")
    _, start, end, selected_user = _filter_controls(get_conn,"weekly_v11_room",allow_staff=True)
    staff,plans,tasks,reviews=_room_period_frames(get_conn,start,end,selected_user)
    if staff.empty:
        st.info("Không có cán bộ phù hợp bộ lọc."); return
    summary=_room_summary(staff,plans,tasks,reviews)
    show=summary.copy()
    show["Q2"]=pd.to_numeric(show["Q2"],errors="coerce").map(lambda x:f"{float(x):.1f}%")
    show["Điểm TB"]=pd.to_numeric(show["Điểm TB"],errors="coerce").map(lambda x:f"{float(x):.1f}" if pd.notna(x) else "—")
    v2._html_table(show[["Cán bộ","Vai trò","Trạng thái","Hoàn thành","Q2","Điểm TB","Xếp loại"]],450)

    st.markdown("### Điểm tuần theo cán bộ")
    score_event=_room_score_chart(summary)
    spoints=_selection_points(score_event)
    if spoints:
        name=str(_point_value(spoints[0],"x",""))
        _render_task_subset(tasks[tasks["full_name"].eq(name)],f"Chi tiết công việc của {name}")

    st.markdown("### Bản đồ nhiệt chỉ số Q2")
    heat_event=_room_heatmap(tasks,staff)
    hpoints=_selection_points(heat_event)
    if hpoints:
        name=str(_point_value(hpoints[0],"y","")); week_label=str(_point_value(hpoints[0],"x",""))
        try:
            week,year=[int(x) for x in week_label.split("/")]
            subset=tasks[(tasks["full_name"].eq(name))&(tasks["iso_week"].eq(week))&(tasks["iso_year"].eq(year))]
            _render_task_subset(subset,f"Chi tiết {name} · tuần {week_label}")
        except Exception:
            pass

    st.markdown("### Cảnh báo cần xử lý")
    no_plan=staff[~staff["id"].isin(plans["user_id"].unique())] if not plans.empty else staff
    waiting=plans[plans["status"].eq("SUBMITTED")] if not plans.empty else plans
    due=pd.to_datetime(tasks["due_date"],errors="coerce").dt.date if not tasks.empty else pd.Series(dtype=object)
    overdue=tasks[(~tasks["status"].isin(["COMPLETED","CANCELLED"])) & due.notna() & ((date.today()-pd.to_datetime(tasks["due_date"],errors="coerce").dt.date).map(lambda x:x.days if pd.notna(x) else 0)>3)] if not tasks.empty else tasks
    if no_plan.empty and waiting.empty and overdue.empty:
        st.success("Không có cảnh báo theo bộ lọc hiện tại.")
    else:
        if not no_plan.empty: st.warning("Chưa có kế hoạch trong kỳ: "+", ".join(no_plan["full_name"].astype(str).tolist()))
        if not waiting.empty: st.warning("Có kế hoạch chờ duyệt: "+", ".join(waiting["full_name"].astype(str).unique().tolist()))
        if not overdue.empty: st.error("Công việc quá hạn trên 3 ngày: "+"; ".join((overdue["full_name"].astype(str)+" — "+overdue["title"].astype(str)).tolist()[:8]))

    st.markdown("### Ma trận trọng tâm Q2 × cán bộ")
    _room_focus_matrix(tasks)
    st.markdown("### Điều chỉnh phân loại")
    _room_reclass_counts(get_conn,start,end,selected_user)
    st.markdown("### Từ khóa tồn tại lặp lại")
    _room_limitation_keywords(reviews)

    with st.expander("🔎 Xem chi tiết công việc theo bộ lọc",expanded=False):
        if tasks.empty:
            st.caption("Không có công việc trong kỳ.")
        else:
            choices=staff["id"].astype(int).tolist()
            who=st.selectbox("Cán bộ xem chi tiết",choices,format_func=lambda x:str(staff[staff["id"].eq(int(x))].iloc[0]["full_name"]),key="weekly_v11_room_drill_staff")
            _render_task_subset(tasks[tasks["user_id"].eq(int(who))],"Chi tiết công việc")


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    if not (wp._is_officer(u) or wp._is_leader(u)):
        st.error("Bạn không có quyền truy cập Kế hoạch tuần.")
        return
    # V10 remains responsible for the autosave install hook. V11 only replaces
    # the two dashboard renderers, preserving the stable planning/review flow.
    v8._personal_dashboard = _personal_dashboard_filtered
    v6._room_dashboard_enhanced = _room_dashboard_filtered
    return v10.weekly_plan_page(u, get_conn, page_title, pill_nav)
