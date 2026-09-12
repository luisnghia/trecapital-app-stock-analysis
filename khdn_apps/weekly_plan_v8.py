"""Weekly Plan V8: personal dashboard and quality-score guidance.

Completes the personal dashboard elements from the v1.2 specification and makes
quality scoring transparent. No Ban Giám đốc functionality is introduced.
"""
from __future__ import annotations

import html
from datetime import date, timedelta
from typing import Callable, Optional

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v4 as v4
from khdn_apps import weekly_plan_v7 as v7


QUALITY_SCALE = [
    (5, "Vượt yêu cầu", "Kết quả tốt hơn dự kiến, không phải chỉnh sửa, có sáng kiến cải tiến"),
    (4, "Đạt đầy đủ yêu cầu", "Đúng hạn, chất lượng tốt"),
    (3, "Đạt yêu cầu cơ bản", "Còn phải chỉnh sửa nhỏ"),
    (2, "Chưa đạt một phần", "Phải làm lại hoặc có người hỗ trợ mới hoàn thành"),
    (1, "Không đạt yêu cầu", "Kết quả chưa đáp ứng yêu cầu"),
]


def _quality_scale_table():
    df = pd.DataFrame([{"Mức": n, "Đánh giá": title, "Mô tả": desc} for n, title, desc in QUALITY_SCALE])
    v2._html_table(df, 330)


def _approved_view_with_scale(get_conn: Callable, u, plan, tasks):
    st.markdown("### Công việc tuần này")
    for _, row in tasks.iterrows():
        wp._render_task_card(row)
        wp._task_runtime_controls(get_conn, u, row)
        v2._defer_controls(get_conn, u, row)
    with st.expander("⚡ Thêm việc phát sinh", expanded=False):
        wp._add_task_form(get_conn, u, plan, emergent=True)

    st.divider()
    st.markdown("### Chốt tuần & tự đánh giá")
    review = wp._review(get_conn, int(plan["id"])) or {}
    suggestions = v2._suggestions(tasks)
    st.caption("Nội dung được gợi ý từ dữ liệu tuần; cán bộ có thể chỉnh sửa.")
    with st.expander("ℹ️ Thang điểm chất lượng 1–5", expanded=False):
        _quality_scale_table()

    with st.form(f"weekly_close_v8_{int(plan['id'])}"):
        strengths = st.text_area("Mặt được *", value=str(review.get("strengths") or suggestions["strengths"]), max_chars=500)
        limitations = st.text_area("Tồn tại, hạn chế *", value=str(review.get("limitations") or suggestions["limitations"]), max_chars=500)
        causes = st.text_area("Nguyên nhân *", value=str(review.get("causes") or suggestions["causes"]), max_chars=500)
        next_actions = st.text_area("Đề xuất / kế hoạch khắc phục tuần sau *", value=str(review.get("next_actions") or suggestions["next"]), max_chars=500)
        self_score = st.slider("Tự chấm chất lượng tuần", 1, 5, int(review.get("self_score") or 4),
                               help="5: Vượt yêu cầu · 4: Đạt đầy đủ · 3: Đạt cơ bản · 2: Chưa đạt một phần · 1: Không đạt")
        close = st.form_submit_button("🔒 Chốt tuần", type="primary", use_container_width=True)
    if close:
        if any(not str(x).strip() for x in [strengths, limitations, causes, next_actions]):
            st.error("Bốn ô tự đánh giá đều bắt buộc.")
            return
        ts = wp._now()
        with get_conn() as c:
            c.execute("""INSERT INTO weekly_reviews(plan_id,self_score,strengths,limitations,causes,next_actions,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(plan_id) DO UPDATE SET self_score=excluded.self_score,
                strengths=excluded.strengths,limitations=excluded.limitations,causes=excluded.causes,
                next_actions=excluded.next_actions,updated_at=excluded.updated_at""",
                (int(plan["id"]), int(self_score), strengths.strip(), limitations.strip(), causes.strip(), next_actions.strip(), ts, ts))
            c.execute("UPDATE weekly_plans SET status='CLOSED',closed_at=?,updated_at=? WHERE id=?", (ts, ts, int(plan["id"])))
            c.execute("UPDATE weekly_tasks SET classification_locked=1,updated_at=? WHERE plan_id=?", (ts, int(plan["id"])))
            c.commit()
        wp._log(get_conn, int(u["id"]), "CLOSE_PLAN", "weekly_plan", plan["id"], f"self_score={self_score}")
        st.rerun()


def _personal_history_frame(get_conn: Callable, user_id: int, weeks: int = 8):
    return wp._qdf(get_conn, """SELECT p.id plan_id,p.iso_year,p.iso_week,p.status,p.start_date,p.end_date,
        COUNT(CASE WHEN t.status<>'CANCELLED' THEN t.id END) total_tasks,
        COUNT(CASE WHEN t.status='COMPLETED' THEN t.id END) done_tasks,
        COUNT(CASE WHEN t.status='COMPLETED' AND date(t.completed_at)<=date(t.due_date) THEN t.id END) on_time_tasks,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' THEN t.planned_hours ELSE 0 END),0) planned_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' THEN t.actual_hours ELSE 0 END),0) actual_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' AND t.quadrant='Q2' THEN t.actual_hours ELSE 0 END),0) q2_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' AND t.is_emergent=1 THEN 1 ELSE 0 END),0) emergent_tasks,
        r.self_score,r.leader_score,r.progress_score,r.quality_score,r.week_score,r.grade,r.leader_comment
        FROM weekly_plans p
        LEFT JOIN weekly_tasks t ON t.plan_id=p.id
        LEFT JOIN weekly_reviews r ON r.plan_id=p.id
        WHERE p.user_id=?
        GROUP BY p.id,p.iso_year,p.iso_week,p.status,p.start_date,p.end_date,
                 r.self_score,r.leader_score,r.progress_score,r.quality_score,r.week_score,r.grade,r.leader_comment
        ORDER BY p.iso_year DESC,p.iso_week DESC LIMIT ?""", (int(user_id), int(weeks)))


def _current_personal_metrics(get_conn: Callable, u):
    year, week, _, _ = wp._iso_week()
    plan = wp._get_plan(get_conn, int(u["id"]), year, week)
    if not plan:
        return None, pd.DataFrame(), None
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    review = wp._review(get_conn, int(plan["id"]))
    return plan, tasks, review


def _metric_cards(plan, tasks: pd.DataFrame, review):
    m = wp._plan_metrics(tasks)
    completion = 100.0 * m["done"] / m["total"] if m["total"] else 0.0
    on_time = 100.0 * m["on_time"] / m["done"] if m["done"] else 0.0
    score = float(review.get("week_score")) if review and pd.notna(review.get("week_score")) else None
    grade = str(review.get("grade") or "—") if review else "—"
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Điểm tuần", f"{score:.1f}" if score is not None else "—")
    c2.metric("Xếp loại", grade)
    c3.metric("Tỷ lệ hoàn thành", f"{completion:.1f}%")
    c4.metric("Tỷ lệ đúng hạn", f"{on_time:.1f}%")


def _quadrant_pies(tasks: pd.DataFrame):
    if tasks.empty:
        return
    valid = tasks[tasks["status"].ne("CANCELLED")].copy()
    labels = ["Q2", "Q1", "Q3", "Q4"]
    planned = [float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q), "planned_hours"], errors="coerce").fillna(0).sum()) for q in labels]
    actual = [float(pd.to_numeric(valid.loc[valid["quadrant"].eq(q), "actual_hours"], errors="coerce").fillna(0).sum()) for q in labels]
    fig = make_subplots(rows=1, cols=2, specs=[[{"type":"domain"},{"type":"domain"}]], subplot_titles=("Giờ kế hoạch", "Giờ thực tế"))
    palette = ["#62D7AF", "#FF7B72", "#F4B41A", "#8AA6A1"]
    fig.add_trace(go.Pie(labels=labels, values=planned, hole=.55, marker=dict(colors=palette), textinfo="label+percent"), 1, 1)
    fig.add_trace(go.Pie(labels=labels, values=actual, hole=.55, marker=dict(colors=palette), textinfo="label+percent"), 1, 2)
    fig.update_layout(height=330, margin=dict(l=10,r=10,t=50,b=20), paper_bgcolor="#0E1F1E", font=dict(color="#F4FFFC"), showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key="weekly_v8_personal_pies")


def _trend_chart(history: pd.DataFrame):
    if history.empty:
        return
    h = history.sort_values(["iso_year","iso_week"]).copy()
    h["Tuần"] = h.apply(lambda r: f"{int(r['iso_week'])}/{int(r['iso_year'])}", axis=1)
    h["Q2 %"] = h.apply(lambda r: 100.0*float(r.get("q2_hours") or 0)/float(r.get("actual_hours")) if float(r.get("actual_hours") or 0)>0 else 0.0, axis=1)
    h["Điểm tuần"] = pd.to_numeric(h["week_score"], errors="coerce")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=h["Tuần"], y=h["Q2 %"], mode="lines+markers", name="Chỉ số Q2", line=dict(color="#62D7AF", width=3)))
    fig.add_trace(go.Scatter(x=h["Tuần"], y=h["Điểm tuần"], mode="lines+markers", name="Điểm tuần", line=dict(color="#F4B41A", width=3)))
    fig.update_layout(height=320, margin=dict(l=20,r=20,t=30,b=40), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"), yaxis=dict(range=[0,100], ticksuffix=""), legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True, key="weekly_v8_personal_trend")


def _problem_tasks(get_conn: Callable, user_id: int):
    df = wp._qdf(get_conn, """SELECT t.*,p.iso_year,p.iso_week,f.code focus_code,f.name focus_name
        FROM weekly_tasks t JOIN weekly_plans p ON p.id=t.plan_id
        LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
        WHERE p.user_id=? AND (
            (t.status NOT IN ('COMPLETED','CANCELLED') AND t.due_date IS NOT NULL AND date(t.due_date)<date('now'))
            OR (t.quadrant='Q2' AND t.defer_count>2)
        ) ORDER BY p.iso_year DESC,p.iso_week DESC,t.due_date,t.id LIMIT 30""", (int(user_id),))
    if df.empty:
        st.success("Không có công việc trễ hạn hoặc Q2 bị lùi trên 2 lần.")
        return
    for _, r in df.iterrows():
        wp._render_task_card(r)


def _q2_focus_distribution(get_conn: Callable, user_id: int):
    since = (date.today() - timedelta(days=56)).isoformat()
    df = wp._qdf(get_conn, """SELECT COALESCE(f.code||' — '||f.name,'Không xác định') focus,
        COALESCE(SUM(t.actual_hours),0) hours
        FROM weekly_tasks t JOIN weekly_plans p ON p.id=t.plan_id
        LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
        WHERE p.user_id=? AND date(p.start_date)>=date(?) AND t.quadrant='Q2' AND t.status<>'CANCELLED'
        GROUP BY f.id,f.code,f.name ORDER BY hours DESC""", (int(user_id), since))
    if df.empty:
        st.caption("Chưa có giờ thực tế Q2 trong 8 tuần gần nhất."); return
    fig = go.Figure(go.Bar(x=pd.to_numeric(df["hours"], errors="coerce"), y=df["focus"].astype(str), orientation="h", marker_color="#62D7AF", text=[f"{float(v):.1f}h" for v in df["hours"]], textposition="auto"))
    fig.update_layout(height=max(280, 45*len(df)+100), margin=dict(l=20,r=20,t=25,b=40), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"), xaxis_title="Giờ thực tế", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True, key="weekly_v8_focus_distribution")


def _leader_comment_history(history: pd.DataFrame):
    if history.empty:
        st.caption("Chưa có nhận xét của lãnh đạo."); return
    comments = history[history["leader_comment"].fillna("").astype(str).str.strip().ne("")].copy()
    if comments.empty:
        st.caption("Chưa có nhận xét của lãnh đạo."); return
    comments = comments.sort_values(["iso_year","iso_week"], ascending=False)
    for _, r in comments.iterrows():
        grade = str(r.get("grade") or "—") if pd.notna(r.get("grade")) else "—"
        score = f"{float(r['week_score']):.1f}" if pd.notna(r.get("week_score")) else "—"
        st.html(f'<div class="weekly-dashboard-card"><b>Tuần {int(r["iso_week"])}/{int(r["iso_year"])}</b> · Điểm {score} · {html.escape(grade)}<br><span class="muted">{html.escape(str(r["leader_comment"]))}</span></div>')


def _personal_dashboard(get_conn: Callable, u):
    st.markdown("### Dashboard cá nhân")
    plan, tasks, review = _current_personal_metrics(get_conn, u)
    if not plan:
        st.info("Chưa có kế hoạch tuần hiện tại.")
    else:
        _metric_cards(plan, tasks, review)
        st.markdown("### Cơ cấu giờ Q1–Q4 · kế hoạch so với thực tế")
        _quadrant_pies(tasks)

    history = _personal_history_frame(get_conn, int(u["id"]), 8)
    st.markdown("### Xu hướng chỉ số Q2 & điểm tuần · 8 tuần")
    _trend_chart(history)
    st.markdown("### Công việc cần chú ý")
    _problem_tasks(get_conn, int(u["id"]))
    st.markdown("### Giờ Q2 theo danh mục trọng tâm · 8 tuần")
    _q2_focus_distribution(get_conn, int(u["id"]))
    st.markdown("### Lịch sử nhận xét của Lãnh đạo phòng")
    _leader_comment_history(history)

    with st.expander("🧮 Cách tính điểm", expanded=False):
        st.markdown("**Điểm tiến độ:** Q1/Q2 trọng số 3; Q3 trọng số 1; Q4 trọng số 0. Hoàn thành đúng hạn hệ số 1, trễ hạn hệ số 0,6, chưa hoàn thành hệ số 0.")
        st.markdown("**Điểm chất lượng:** 20 × (0,3 × tự chấm + 0,7 × điểm Lãnh đạo phòng). Nếu chưa có nhận xét sau 5 ngày làm việc, tạm lấy tự chấm với hệ số 1,0.")
        st.markdown("**Điểm tuần:** 0,5 × Điểm tiến độ + 0,5 × Điểm chất lượng. A ≥90; B 75–<90; C 60–<75; D <60.")
        _quality_scale_table()


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    if not (wp._is_officer(u) or wp._is_leader(u)):
        st.error("Bạn không có quyền truy cập Kế hoạch tuần.")
        return

    # Patch only the review renderer; V7/V6 retain all classification,
    # notification and room-dashboard hardening.
    v2._approved_view = _approved_view_with_scale

    # Reproduce V7 entry to insert the full personal dashboard as a first-class view.
    from khdn_apps import weekly_plan_v6 as v6
    v6._generate_in_app_notifications = v7._generate_in_app_notifications
    v6._focus_staff_matrix = v7._focus_staff_matrix
    v6._init_v6_schema(get_conn)
    v6._install_due_driven_overrides()
    v4._apply_score_fallbacks(get_conn)
    wp._inject_weekly_css(); v2._inject_css(); v6._inject_v6_css()
    v7._generate_in_app_notifications(get_conn, u)
    page_title("Kế hoạch tuần", "Quản trị ưu tiên theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư.")
    v6._notification_center(get_conn, u)
    v2._glossary()

    if wp._is_leader(u):
        options = [("mine","📅 Kế hoạch của tôi"),("personal","📊 Dashboard cá nhân"),("review","✅ Duyệt & đánh giá"),("focus","🎯 Trọng tâm Q2"),("room","📊 Tổng quan phòng"),("history","📈 Lịch sử 8 tuần"),("export","⬇️ Xuất báo cáo")]
    else:
        options = [("mine","📅 Tuần của tôi"),("personal","📊 Dashboard cá nhân"),("history","📈 Lịch sử 8 tuần"),("export","⬇️ Xuất báo cáo")]
    if pill_nav:
        view = pill_nav("weekly_plan_view", options, default="mine", prefix="weekly_plan_v8")
    else:
        labels=[x[1] for x in options]; values=[x[0] for x in options]; current=st.session_state.get("weekly_plan_view","mine")
        idx=values.index(current) if current in values else 0
        selected=st.radio("Chế độ", labels, index=idx, horizontal=True, label_visibility="collapsed")
        view=dict((label,value) for value,label in options)[selected]; st.session_state["weekly_plan_view"]=view

    if view == "mine": v4._my_plan(get_conn, u)
    elif view == "personal": _personal_dashboard(get_conn, u)
    elif view == "review" and wp._is_leader(u): v4._leader_review(get_conn, u)
    elif view == "focus" and wp._is_leader(u): v4._focus_maintenance(get_conn, u)
    elif view == "room" and wp._is_leader(u): v6._room_dashboard_enhanced(get_conn)
    elif view == "history": v2._history_view(get_conn, u)
    elif view == "export":
        from khdn_apps import weekly_plan_v5 as v5
        v5._export_view(get_conn, u)
