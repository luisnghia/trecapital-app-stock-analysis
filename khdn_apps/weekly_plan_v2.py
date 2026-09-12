"""Enhancements for KHDN Ops Weekly Plan.

Adds carry-forward, defer reasons, leader reclassification, 8-week history,
focus warnings and Excel export. There is intentionally no Ban Giám đốc view.
"""
from __future__ import annotations

import html
from datetime import date, timedelta
from io import BytesIO
from typing import Callable, Optional

import pandas as pd
import streamlit as st

from khdn_apps import weekly_plan as wp


DEFER_REASONS = [
    "Phát sinh công việc ưu tiên cao hơn",
    "Chờ ý kiến, phê duyệt của cấp trên",
    "Chờ hồ sơ, thông tin từ khách hàng hoặc bộ phận khác",
    "Ước lượng thời gian chưa sát",
    "Nguyên nhân khách quan (công tác, nghỉ, sự cố hệ thống)",
    "Lý do khác",
]


def _init_v2_schema(get_conn: Callable):
    wp.init_weekly_schema(get_conn)
    with get_conn() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(weekly_tasks)").fetchall()}
        if "defer_reason" not in cols:
            c.execute("ALTER TABLE weekly_tasks ADD COLUMN defer_reason TEXT")
        if "original_due_date" not in cols:
            c.execute("ALTER TABLE weekly_tasks ADD COLUMN original_due_date TEXT")
        if "classification_locked" not in cols:
            c.execute("ALTER TABLE weekly_tasks ADD COLUMN classification_locked INTEGER NOT NULL DEFAULT 0")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_classification_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            old_quadrant TEXT,
            new_quadrant TEXT,
            old_focus_category_id INTEGER,
            new_focus_category_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES weekly_tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(plan_id) REFERENCES weekly_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_weekly_class_change_user_time
            ON weekly_classification_changes(user_id,created_at);
        """)
        c.commit()


def _inject_css():
    st.markdown("""
    <style>
    .weekly-warn-card{background:#392F16;border:1px solid rgba(244,180,26,.60);color:#FFF4CE;border-radius:12px;padding:9px 11px;margin:7px 0;font-size:.82rem}
    .weekly-warn-card *{color:#FFF4CE!important}
    .weekly-glossary{background:#122624;border:1px solid rgba(164,232,219,.18);border-radius:12px;padding:10px 12px;line-height:1.45;font-size:.80rem;color:#E7FAF6}
    .weekly-glossary b{color:#F4B41A!important}
    .weekly-html-table-wrap{width:100%;overflow-x:auto;border:1px solid rgba(164,232,219,.22);border-radius:12px;background:#122624;margin:.35rem 0 .8rem}
    .weekly-html-table{width:100%;border-collapse:collapse;table-layout:fixed;color:#F4FFFC;font-size:.78rem}
    .weekly-html-table th{background:#1B4540;color:#F4FFFC;padding:8px;border:1px solid rgba(164,232,219,.20);white-space:normal;overflow-wrap:anywhere}
    .weekly-html-table td{background:#122624;color:#E9FAF7;padding:7px;border:1px solid rgba(164,232,219,.12);vertical-align:top;white-space:normal;overflow-wrap:anywhere}
    @media(max-width:700px){.weekly-html-table{min-width:680px;font-size:.72rem}.weekly-html-table th,.weekly-html-table td{padding:6px}}
    </style>
    """, unsafe_allow_html=True)


def _html_table(df: pd.DataFrame, max_height=500):
    if df is None or df.empty:
        st.info("Chưa có dữ liệu.")
        return
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = []
        for value in row.tolist():
            text = "—" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)
            cells.append(f"<td>{html.escape(text)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    st.html(f'<div class="weekly-html-table-wrap" style="max-height:{int(max_height)}px"><table class="weekly-html-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def _previous_iso(year: int, week: int):
    monday = date.fromisocalendar(int(year), int(week), 1) - timedelta(days=7)
    iso = monday.isocalendar()
    return int(iso.year), int(iso.week), monday


def _carry_candidates(get_conn: Callable, user_id: int, year: int, week: int, current_plan_id: int):
    py, pw, _ = _previous_iso(year, week)
    prev = wp._get_plan(get_conn, user_id, py, pw)
    if not prev:
        return pd.DataFrame()
    return wp._qdf(get_conn, """SELECT t.*,f.code focus_code,f.name focus_name FROM weekly_tasks t
        LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
        WHERE t.plan_id=? AND t.status NOT IN ('COMPLETED','CANCELLED')
        AND NOT EXISTS(SELECT 1 FROM weekly_tasks n WHERE n.plan_id=? AND n.source_task_id=t.id)
        ORDER BY CASE t.quadrant WHEN 'Q2' THEN 1 WHEN 'Q1' THEN 2 WHEN 'Q3' THEN 3 ELSE 4 END,t.id""",
        (int(prev["id"]), int(current_plan_id)))


def _carry_panel(get_conn: Callable, u, plan):
    cand = _carry_candidates(get_conn, int(u["id"]), int(plan["iso_year"]), int(plan["iso_week"]), int(plan["id"]))
    if cand.empty:
        return
    with st.expander(f"↪ Công việc chưa xong tuần trước ({len(cand)})", expanded=True):
        st.caption("Chuyển tiếp giữ lịch sử, liên kết công việc gốc và tăng số lần lùi.")
        for _, r in cand.iterrows():
            wp._render_task_card(r)
            if st.button("Chuyển tiếp sang tuần này", key=f"weekly_carry_{int(r['id'])}", use_container_width=True):
                current = wp._tasks_df(get_conn, int(plan["id"]))
                planned = current[pd.to_numeric(current["is_emergent"], errors="coerce").fillna(0).eq(0)] if not current.empty else current
                if len(planned) >= 7:
                    st.error("Kế hoạch đã đủ 7 công việc.")
                    continue
                _, _, monday, _ = wp._iso_week()
                try:
                    due = max(pd.to_datetime(r.get("due_date")).date() + timedelta(days=7), monday)
                except Exception:
                    due = monday + timedelta(days=4)
                task_id = wp._execute(get_conn, """INSERT INTO weekly_tasks(
                    plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,
                    planned_hours,actual_hours,status,is_emergent,defer_count,source_task_id,defer_reason,original_due_date,
                    classification_locked,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,0,'NOT_STARTED',0,?,?,?,?,0,?,?)""",
                    (int(plan["id"]), str(r.get("title") or ""), str(r.get("expected_result") or ""),
                     int(r["focus_category_id"]) if pd.notna(r.get("focus_category_id")) else None,
                     int(r.get("is_urgent") or 0), int(r.get("has_kpi_or_risk") or 0), str(r.get("quadrant") or "Q4"),
                     due.isoformat(), float(r.get("planned_hours") or 0), int(r.get("defer_count") or 0) + 1,
                     int(r["id"]), "Chuyển tiếp từ tuần trước", str(r.get("original_due_date") or r.get("due_date") or ""),
                     wp._now(), wp._now()))
                wp._task_log(get_conn, task_id, int(u["id"]), "carry_forward", r.get("id"), task_id, "Chuyển tiếp tuần")
                wp._log(get_conn, int(u["id"]), "CARRY_FORWARD", "weekly_task", task_id, f"source_task_id={int(r['id'])}")
                st.rerun()


def _sync_overdue(get_conn: Callable, plan_id: int):
    wp._execute(get_conn, """UPDATE weekly_tasks SET status='OVERDUE',updated_at=?
        WHERE plan_id=? AND status IN ('NOT_STARTED','IN_PROGRESS') AND due_date IS NOT NULL AND date(due_date)<date(?)""",
        (wp._now(), int(plan_id), date.today().isoformat()))


def _warnings(get_conn: Callable, u, plan, tasks):
    if not tasks.empty:
        valid = tasks[tasks["status"].ne("CANCELLED")].copy()
        total = float(pd.to_numeric(valid["planned_hours"], errors="coerce").fillna(0).sum())
        q4 = float(pd.to_numeric(valid.loc[valid["quadrant"].eq("Q4"), "planned_hours"], errors="coerce").fillna(0).sum())
        pct = 100.0 * q4 / total if total > 0 else 0.0
        if pct > 20:
            st.html(f'<div class="weekly-warn-card">⚠️ Giờ dự kiến Q4 chiếm {pct:.1f}%, vượt ngưỡng cảnh báo 20%. Hãy rà soát lại trọng tâm.</div>')
        q2_late = valid[(valid["quadrant"] == "Q2") & (pd.to_numeric(valid["defer_count"], errors="coerce").fillna(0) > 2)]
        if not q2_late.empty:
            st.html(f'<div class="weekly-warn-card">🚩 Q2 bị lùi trên 2 tuần: {html.escape(", ".join(q2_late["title"].astype(str).tolist()[:5]))}</div>')
    py, pw, _ = _previous_iso(int(plan["iso_year"]), int(plan["iso_week"]))
    d = wp._qdf(get_conn, """SELECT COUNT(*) n FROM weekly_classification_changes c
        JOIN weekly_plans p ON p.id=c.plan_id WHERE c.user_id=? AND p.iso_year=? AND p.iso_week=?
        AND c.old_quadrant='Q2' AND c.new_quadrant<>'Q2'""", (int(u["id"]), py, pw))
    n = int(d.iloc[0]["n"]) if not d.empty else 0
    if n >= 3:
        st.html(f'<div class="weekly-warn-card">🔎 Tuần trước có {n} công việc bị gỡ khỏi Q2. Cần trao đổi lại với lãnh đạo về cách hiểu trọng tâm.</div>')


def _defer_controls(get_conn: Callable, u, row):
    if str(row.get("status")) in {"COMPLETED", "CANCELLED"}:
        return
    with st.expander("🗓 Điều chỉnh hạn hoàn thành", expanded=False):
        try:
            current_due = pd.to_datetime(row.get("due_date")).date()
        except Exception:
            current_due = date.today()
        new_due = st.date_input("Hạn mới", value=current_due, min_value=date.today(), key=f"weekly_new_due_{int(row['id'])}")
        reason = st.selectbox("Lý do lùi hạn *", DEFER_REASONS, key=f"weekly_defer_reason_{int(row['id'])}")
        other = st.text_input("Ghi rõ lý do *", key=f"weekly_defer_other_{int(row['id'])}") if reason == "Lý do khác" else ""
        if st.button("Cập nhật hạn", key=f"weekly_defer_save_{int(row['id'])}", use_container_width=True):
            if new_due <= current_due:
                st.error("Hạn mới phải sau hạn hiện tại.")
            elif reason == "Lý do khác" and not other.strip():
                st.error("Bắt buộc ghi rõ lý do khác.")
            else:
                detail = other.strip() if reason == "Lý do khác" else reason
                original = str(row.get("original_due_date") or row.get("due_date") or "")
                new_status = "IN_PROGRESS" if str(row.get("status")) == "OVERDUE" else str(row.get("status"))
                wp._execute(get_conn, """UPDATE weekly_tasks SET due_date=?,defer_count=defer_count+1,defer_reason=?,
                    original_due_date=COALESCE(NULLIF(original_due_date,''),?),status=?,updated_at=? WHERE id=?""",
                    (new_due.isoformat(), detail, original, new_status, wp._now(), int(row["id"])))
                wp._task_log(get_conn, int(row["id"]), int(u["id"]), "due_date", current_due.isoformat(), new_due.isoformat(), detail)
                wp._log(get_conn, int(u["id"]), "DEFER_TASK", "weekly_task", row["id"], detail)
                st.rerun()


def _suggestions(tasks: pd.DataFrame):
    m = wp._plan_metrics(tasks)
    unfinished = tasks[~tasks["status"].isin(["COMPLETED", "CANCELLED"])] if not tasks.empty else tasks
    names = ", ".join(unfinished["title"].astype(str).tolist()[:4]) if not unfinished.empty else "không có"
    total = max(1, m["total"])
    return {
        "strengths": f"Hoàn thành {m['done']}/{m['total']} công việc; có {m['q2']} việc Q2.",
        "limitations": f"Còn {len(unfinished)} công việc chưa hoàn thành: {names}.",
        "causes": f"Phát sinh {m['emergent']} công việc, chiếm {100.0*m['emergent']/total:.1f}% tổng số việc.",
        "next": f"Tuần tới ưu tiên các việc chuyển tiếp: {names}." if not unfinished.empty else "Duy trì ưu tiên Q2 và hạn chế việc phân tâm.",
    }


def _approved_view(get_conn: Callable, u, plan, tasks):
    st.markdown("### Công việc tuần này")
    for _, row in tasks.iterrows():
        wp._render_task_card(row)
        wp._task_runtime_controls(get_conn, u, row)
        _defer_controls(get_conn, u, row)
    with st.expander("⚡ Thêm việc phát sinh", expanded=False):
        wp._add_task_form(get_conn, u, plan, emergent=True)
    st.divider()
    st.markdown("### Chốt tuần & tự đánh giá")
    review = wp._review(get_conn, int(plan["id"])) or {}
    s = _suggestions(tasks)
    st.caption("Nội dung được gợi ý từ dữ liệu tuần; cán bộ có thể chỉnh sửa.")
    with st.form(f"weekly_close_v2_{int(plan['id'])}"):
        strengths = st.text_area("Mặt được *", value=str(review.get("strengths") or s["strengths"]), max_chars=500)
        limitations = st.text_area("Tồn tại, hạn chế *", value=str(review.get("limitations") or s["limitations"]), max_chars=500)
        causes = st.text_area("Nguyên nhân *", value=str(review.get("causes") or s["causes"]), max_chars=500)
        next_actions = st.text_area("Đề xuất / kế hoạch khắc phục tuần sau *", value=str(review.get("next_actions") or s["next"]), max_chars=500)
        self_score = st.slider("Tự chấm chất lượng tuần", 1, 5, int(review.get("self_score") or 4))
        close = st.form_submit_button("🔒 Chốt tuần", type="primary", use_container_width=True)
    if close:
        if any(not str(x).strip() for x in [strengths, limitations, causes, next_actions]):
            st.error("Bốn ô tự đánh giá đều bắt buộc.")
        else:
            ts = wp._now()
            with get_conn() as c:
                c.execute("""INSERT INTO weekly_reviews(plan_id,self_score,strengths,limitations,causes,next_actions,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(plan_id) DO UPDATE SET self_score=excluded.self_score,
                    strengths=excluded.strengths,limitations=excluded.limitations,causes=excluded.causes,next_actions=excluded.next_actions,updated_at=excluded.updated_at""",
                    (int(plan["id"]), int(self_score), strengths.strip(), limitations.strip(), causes.strip(), next_actions.strip(), ts, ts))
                c.execute("UPDATE weekly_plans SET status='CLOSED',closed_at=?,updated_at=? WHERE id=?", (ts, ts, int(plan["id"])))
                c.execute("UPDATE weekly_tasks SET classification_locked=1,updated_at=? WHERE plan_id=?", (ts, int(plan["id"])))
                c.commit()
            wp._log(get_conn, int(u["id"]), "CLOSE_PLAN", "weekly_plan", plan["id"], f"self_score={self_score}")
            st.rerun()


def _my_plan(get_conn: Callable, u):
    year, week, monday, sunday = wp._iso_week()
    plan = wp._get_or_create_plan(get_conn, int(u["id"]), year, week, monday, sunday)
    _sync_overdue(get_conn, int(plan["id"]))
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    wp._render_header(plan, tasks)
    _warnings(get_conn, u, plan, tasks)
    status = str(plan["status"])
    if status in {"DRAFT", "RETURNED"}:
        _carry_panel(get_conn, u, plan)
        wp._draft_view(get_conn, u, plan, tasks)
    elif status == "SUBMITTED":
        st.info("Kế hoạch đã nộp, đang chờ lãnh đạo phòng duyệt.")
        wp._submitted_view(get_conn, u, plan, tasks)
    elif status == "APPROVED":
        _approved_view(get_conn, u, plan, tasks)
    elif status in {"CLOSED", "REVIEWED"}:
        if status == "CLOSED":
            st.info("Đã chốt tuần; dữ liệu chỉ đọc và đang chờ lãnh đạo đánh giá.")
        wp._reviewed_view(get_conn, plan, tasks)


def _leader_reclass(get_conn: Callable, u):
    plan_id = st.session_state.get("weekly_leader_plan_select")
    if not plan_id:
        return
    pdf = wp._qdf(get_conn, "SELECT * FROM weekly_plans WHERE id=?", (int(plan_id),))
    if pdf.empty or str(pdf.iloc[0]["status"]) not in {"SUBMITTED", "APPROVED"}:
        return
    plan = pdf.iloc[0].to_dict()
    tasks = wp._tasks_df(get_conn, int(plan_id))
    if tasks.empty:
        return
    st.divider(); st.markdown("### 🧭 Điều chỉnh phân loại Q1–Q4")
    st.caption("Lãnh đạo phòng có thể gắn/đổi/gỡ danh mục Q2 trước khi cán bộ chốt tuần. Mọi thay đổi đều ghi log.")
    task_id = st.selectbox("Công việc", tasks["id"].astype(int).tolist(), format_func=lambda x: f"{tasks[tasks['id'].eq(int(x))].iloc[0]['quadrant']} · {tasks[tasks['id'].eq(int(x))].iloc[0]['title']}", key="weekly_reclass_task")
    row = tasks[tasks["id"].eq(int(task_id))].iloc[0].to_dict()
    focus = wp._focus_df(get_conn, int(plan["iso_year"]), active_only=True)
    opts = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
    current = int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else 0
    idx = opts.index(current) if current in opts else 0
    def ff(x):
        if x == 0: return "— Không thuộc mục trọng tâm nào —"
        r = focus[focus["id"].eq(int(x))].iloc[0]; return f"{r['code']} — {r['name']}"
    new_focus = st.selectbox("Danh mục trọng tâm", opts, index=idx, format_func=ff, key="weekly_reclass_focus")
    urgent = bool(row.get("is_urgent") or 0); has_kpi = bool(row.get("has_kpi_or_risk") or 0)
    if not new_focus:
        urgent = st.checkbox("Có hạn trong 7 ngày tới?", value=urgent, key="weekly_reclass_urgent")
        has_kpi = st.checkbox("Gắn chỉ tiêu hoặc rủi ro trọng yếu?", value=has_kpi if urgent else False, disabled=not urgent, key="weekly_reclass_kpi")
    new_q = wp._classification(int(new_focus) if new_focus else None, urgent, has_kpi)
    st.info(f"Kết quả sau điều chỉnh: **{new_q} – {wp.QUADRANT_META[new_q][0]}**")
    if st.button("Lưu điều chỉnh", type="primary", use_container_width=True, key="weekly_reclass_save"):
        old_q = str(row.get("quadrant") or ""); old_focus = int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else None
        with get_conn() as c:
            c.execute("UPDATE weekly_tasks SET focus_category_id=?,is_urgent=?,has_kpi_or_risk=?,quadrant=?,updated_at=? WHERE id=? AND classification_locked=0",
                (int(new_focus) if new_focus else None, int(urgent), int(has_kpi), new_q, wp._now(), int(task_id)))
            c.execute("""INSERT INTO weekly_classification_changes(task_id,plan_id,user_id,actor_user_id,old_quadrant,new_quadrant,old_focus_category_id,new_focus_category_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""", (int(task_id), int(plan_id), int(plan["user_id"]), int(u["id"]), old_q, new_q, old_focus, int(new_focus) if new_focus else None, wp._now()))
            c.commit()
        wp._task_log(get_conn, int(task_id), int(u["id"]), "quadrant", old_q, new_q, "Lãnh đạo điều chỉnh phân loại")
        wp._log(get_conn, int(u["id"]), "LEADER_RECLASSIFY", "weekly_task", task_id, f"user_id={int(plan['user_id'])};{old_q}->{new_q}")
        st.rerun()


def _leader_review(get_conn: Callable, u):
    wp._leader_review_view(get_conn, u)
    _leader_reclass(get_conn, u)


def _focus_admin(get_conn: Callable, u):
    wp._focus_admin_view(get_conn, u)
    since = (date.today() - timedelta(days=56)).isoformat()
    unused = wp._qdf(get_conn, """SELECT f.code,f.name,COUNT(CASE WHEN p.id IS NOT NULL THEN t.id END) n
        FROM weekly_focus_categories f LEFT JOIN weekly_tasks t ON t.focus_category_id=f.id
        LEFT JOIN weekly_plans p ON p.id=t.plan_id AND date(p.start_date)>=date(?)
        WHERE f.scope_key='KHDN' AND f.year=? AND f.status='ACTIVE'
        GROUP BY f.id,f.code,f.name HAVING n=0 ORDER BY f.display_order,f.code""", (since, date.today().year))
    if not unused.empty:
        st.divider(); st.markdown("### 🔔 Trọng tâm không phát sinh trong 8 tuần")
        for _, r in unused.iterrows():
            st.html(f'<div class="weekly-warn-card"><b>{html.escape(str(r["code"]))} — {html.escape(str(r["name"]))}</b><br>Không có công việc gắn trong 8 tuần gần nhất; cần rà soát trọng tâm này.</div>')


def _history(get_conn: Callable, user_id: int, weeks=8):
    return wp._qdf(get_conn, """SELECT p.iso_year,p.iso_week,p.status,
        COUNT(CASE WHEN t.status<>'CANCELLED' THEN t.id END) total_tasks,
        COUNT(CASE WHEN t.status='COMPLETED' THEN t.id END) done_tasks,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' THEN t.actual_hours ELSE 0 END),0) actual_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' AND t.quadrant='Q2' THEN t.actual_hours ELSE 0 END),0) q2_hours,
        COALESCE(SUM(CASE WHEN t.status<>'CANCELLED' AND t.is_emergent=1 THEN 1 ELSE 0 END),0) emergent_tasks,
        r.week_score,r.grade FROM weekly_plans p LEFT JOIN weekly_tasks t ON t.plan_id=p.id
        LEFT JOIN weekly_reviews r ON r.plan_id=p.id WHERE p.user_id=?
        GROUP BY p.id,p.iso_year,p.iso_week,p.status,r.week_score,r.grade
        ORDER BY p.iso_year DESC,p.iso_week DESC LIMIT ?""", (int(user_id), int(weeks)))


def _history_view(get_conn: Callable, u):
    st.markdown("### Xu hướng 8 tuần gần nhất")
    h = _history(get_conn, int(u["id"]), 8)
    if h.empty:
        st.info("Chưa có lịch sử kế hoạch tuần."); return
    h["Tuần"] = h.apply(lambda r: f"{int(r['iso_week'])}/{int(r['iso_year'])}", axis=1)
    h["Trạng thái"] = h["status"].map(lambda x: wp.PLAN_STATUS_LABELS.get(str(x), str(x)))
    h["Hoàn thành"] = h.apply(lambda r: f"{int(r['done_tasks'])}/{int(r['total_tasks'])}", axis=1)
    h["Q2"] = h.apply(lambda r: f"{100.0*float(r['q2_hours'] or 0)/float(r['actual_hours']):.1f}%" if float(r["actual_hours"] or 0)>0 else "0.0%", axis=1)
    h["Phát sinh"] = h.apply(lambda r: f"{100.0*float(r['emergent_tasks'] or 0)/float(r['total_tasks']):.1f}%" if float(r["total_tasks"] or 0)>0 else "0.0%", axis=1)
    h["Điểm tuần"] = h["week_score"].map(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    h["Xếp loại"] = h["grade"].fillna("—")
    _html_table(h[["Tuần","Trạng thái","Hoàn thành","Q2","Phát sinh","Điểm tuần","Xếp loại"]], 430)
    chart = h[pd.to_numeric(h["week_score"], errors="coerce").notna()].sort_values(["iso_year","iso_week"])
    if len(chart) >= 2:
        st.line_chart(chart.set_index("Tuần")[["week_score"]].rename(columns={"week_score":"Điểm tuần"}), height=220)


def _excel_bytes(get_conn: Callable, user_id: int):
    plans = wp._qdf(get_conn, "SELECT * FROM weekly_plans WHERE user_id=? ORDER BY iso_year DESC,iso_week DESC LIMIT 8", (int(user_id),))
    if plans.empty: return b""
    ids = plans["id"].astype(int).tolist(); marks = ",".join(["?"]*len(ids))
    tasks = wp._qdf(get_conn, f"SELECT * FROM weekly_tasks WHERE plan_id IN ({marks}) ORDER BY plan_id,id", tuple(ids))
    reviews = wp._qdf(get_conn, f"SELECT * FROM weekly_reviews WHERE plan_id IN ({marks}) ORDER BY plan_id", tuple(ids))
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        plans.to_excel(writer,index=False,sheet_name="Ke_hoach")
        tasks.to_excel(writer,index=False,sheet_name="Cong_viec")
        reviews.to_excel(writer,index=False,sheet_name="Danh_gia")
        for ws in writer.book.worksheets:
            ws.freeze_panes="A2"
            for col in ws.columns:
                letter=col[0].column_letter
                ws.column_dimensions[letter].width=min(45,max(11,max(len(str(c.value or "")) for c in col[:80])+2))
                for cell in col:
                    cell.alignment=cell.alignment.copy(wrap_text=True,vertical="top")
    return out.getvalue()


def _export_view(get_conn: Callable, u):
    st.markdown("### Xuất báo cáo Kế hoạch tuần")
    data = _excel_bytes(get_conn, int(u["id"]))
    if not data:
        st.info("Chưa có dữ liệu để xuất."); return
    st.download_button("⬇️ Tải báo cáo Excel 8 tuần", data=data,
        file_name=f"Ke_hoach_tuan_{u.get('username','can_bo')}_{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)


def _glossary():
    with st.expander("ℹ️ Giải thích Q1–Q4 và chỉ số", expanded=False):
        st.html('<div class="weekly-glossary"><b>Q2 – Trọng tâm:</b> thuộc danh mục trọng tâm do Lãnh đạo phòng ban hành.<br><b>Q1 – Cấp thiết:</b> không thuộc Q2, có hạn trong 7 ngày và gắn chỉ tiêu/rủi ro trọng yếu.<br><b>Q3 – Phân tâm:</b> có hạn trong 7 ngày nhưng không gắn chỉ tiêu/rủi ro trọng yếu.<br><b>Q4 – Giá trị thấp:</b> không thuộc trọng tâm và không cấp bách.<br><b>Chỉ số Q2:</b> giờ thực tế Q2 / tổng giờ thực tế; theo dõi xu hướng, không dùng để phạt.</div>')


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    _init_v2_schema(get_conn); wp._inject_weekly_css(); _inject_css()
    page_title("Kế hoạch tuần", "Quản trị ưu tiên theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư.")
    _glossary()
    if wp._is_leader(u):
        options=[("mine","📅 Kế hoạch của tôi"),("review","✅ Duyệt & đánh giá"),("focus","🎯 Trọng tâm Q2"),("room","📊 Tổng quan phòng"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    else:
        options=[("mine","📅 Tuần của tôi"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    if pill_nav:
        view=pill_nav("weekly_plan_view",options,default="mine",prefix="weekly_plan_v2")
    else:
        labels=[x[1] for x in options]; values=[x[0] for x in options]; current=st.session_state.get("weekly_plan_view","mine")
        idx=values.index(current) if current in values else 0
        selected=st.radio("Chế độ",labels,index=idx,horizontal=True,label_visibility="collapsed")
        view=dict((label,value) for value,label in options)[selected]; st.session_state["weekly_plan_view"]=view
    if view=="mine": _my_plan(get_conn,u)
    elif view=="review" and wp._is_leader(u): _leader_review(get_conn,u)
    elif view=="focus" and wp._is_leader(u): _focus_admin(get_conn,u)
    elif view=="room" and wp._is_leader(u): wp._room_dashboard(get_conn)
    elif view=="history": _history_view(get_conn,u)
    elif view=="export": _export_view(get_conn,u)
