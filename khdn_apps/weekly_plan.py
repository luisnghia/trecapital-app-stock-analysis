"""KHDN Ops - Weekly Plan module.

Implements the Weekly Plan v1.2 workflow inside the existing KHDN_APP.
This module intentionally has no Ban Giám đốc role/view.
"""
from __future__ import annotations

import html
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pandas as pd
import streamlit as st


PLAN_STATUS_LABELS = {
    "DRAFT": "Nháp",
    "SUBMITTED": "Đã nộp",
    "RETURNED": "Trả lại",
    "APPROVED": "Đã duyệt",
    "CLOSED": "Đã chốt",
    "REVIEWED": "Đã đánh giá",
}

TASK_STATUS_LABELS = {
    "NOT_STARTED": "Chưa làm",
    "IN_PROGRESS": "Đang làm",
    "COMPLETED": "Hoàn thành",
    "OVERDUE": "Trễ hạn",
    "CANCELLED": "Hủy",
}

QUADRANT_META = {
    "Q2": ("Trọng tâm", "Thuộc danh mục trọng tâm của phòng.", "#62D7AF"),
    "Q1": ("Cấp thiết", "Cấp bách và gắn chỉ tiêu/rủi ro trọng yếu.", "#FF7B72"),
    "Q3": ("Phân tâm", "Cấp bách nhưng không gắn chỉ tiêu/rủi ro trọng yếu.", "#F4B41A"),
    "Q4": ("Giá trị thấp", "Không thuộc trọng tâm và không cấp bách.", "#8AA6A1"),
}

DEFAULT_FOCUS = [
    ("TT01", "Phát triển khách hàng mới", "Tiếp cận, khảo sát, lập hồ sơ khách hàng chưa có quan hệ với đơn vị."),
    ("TT02", "Chăm sóc khách hàng hiện hữu", "Thăm hỏi định kỳ, rà soát nhu cầu và gia tăng sản phẩm trên khách hàng đang có."),
    ("TT03", "Rà soát tuân thủ chủ động", "Tự kiểm tra hồ sơ, đối chiếu điều kiện, phát hiện sai sót trước khi bị kiểm tra."),
    ("TT04", "Nâng cao nghiệp vụ", "Học quy định mới, tham gia đào tạo, hướng dẫn cán bộ mới."),
    ("TT05", "Chuẩn hóa quy trình, biểu mẫu", "Xây dựng, cập nhật mẫu hồ sơ và tài liệu hướng dẫn dùng chung."),
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _iso_week(ref: Optional[date] = None):
    ref = ref or date.today()
    iso = ref.isocalendar()
    monday = ref - timedelta(days=ref.weekday())
    sunday = monday + timedelta(days=6)
    return int(iso.year), int(iso.week), monday, sunday


def _business_days_since(ts: str) -> int:
    try:
        d0 = pd.to_datetime(ts).date()
    except Exception:
        return 0
    d1 = date.today()
    if d1 <= d0:
        return 0
    days = 0
    cur = d0
    while cur < d1:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days


def _execute(get_conn: Callable, sql: str, params=()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def _qdf(get_conn: Callable, sql: str, params=()):
    with get_conn() as c:
        return pd.read_sql_query(sql, c, params=params)


def _log(get_conn: Callable, actor_id: int, action: str, object_type: str, object_id, detail=""):
    with get_conn() as c:
        c.execute(
            """INSERT INTO weekly_plan_logs(actor_user_id,action,object_type,object_id,detail,created_at)
               VALUES(?,?,?,?,?,?)""",
            (int(actor_id), action, object_type, str(object_id or ""), str(detail or ""), _now()),
        )
        c.commit()


def init_weekly_schema(get_conn: Callable):
    """Additive migration only; existing KHDN tables are untouched."""
    with get_conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS weekly_focus_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_key TEXT NOT NULL DEFAULT 'KHDN',
                year INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                display_order INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')),
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(scope_key, year, code),
                FOREIGN KEY(created_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS weekly_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                iso_year INTEGER NOT NULL,
                iso_week INTEGER NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'DRAFT'
                    CHECK(status IN ('DRAFT','SUBMITTED','RETURNED','APPROVED','CLOSED','REVIEWED')),
                submitted_at TEXT,
                approved_at TEXT,
                closed_at TEXT,
                reviewed_at TEXT,
                reviewer_user_id INTEGER,
                return_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, iso_year, iso_week),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(reviewer_user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS weekly_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                expected_result TEXT NOT NULL,
                focus_category_id INTEGER,
                is_urgent INTEGER NOT NULL DEFAULT 0,
                has_kpi_or_risk INTEGER NOT NULL DEFAULT 0,
                quadrant TEXT NOT NULL CHECK(quadrant IN ('Q1','Q2','Q3','Q4')),
                due_date TEXT,
                planned_hours REAL NOT NULL DEFAULT 0,
                actual_hours REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'NOT_STARTED'
                    CHECK(status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','OVERDUE','CANCELLED')),
                completed_at TEXT,
                actual_result TEXT,
                is_emergent INTEGER NOT NULL DEFAULT 0,
                defer_count INTEGER NOT NULL DEFAULT 0,
                source_task_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES weekly_plans(id) ON DELETE CASCADE,
                FOREIGN KEY(focus_category_id) REFERENCES weekly_focus_categories(id),
                FOREIGN KEY(source_task_id) REFERENCES weekly_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS weekly_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER UNIQUE NOT NULL,
                self_score INTEGER,
                strengths TEXT,
                limitations TEXT,
                causes TEXT,
                next_actions TEXT,
                leader_score INTEGER,
                leader_comment TEXT,
                score_gap_reason TEXT,
                progress_score REAL,
                quality_score REAL,
                week_score REAL,
                grade TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES weekly_plans(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS weekly_task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                actor_user_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                detail TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES weekly_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY(actor_user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS weekly_plan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                object_type TEXT,
                object_id TEXT,
                detail TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_weekly_plan_user_week
                ON weekly_plans(user_id, iso_year, iso_week);
            CREATE INDEX IF NOT EXISTS idx_weekly_plan_status
                ON weekly_plans(status, iso_year, iso_week);
            CREATE INDEX IF NOT EXISTS idx_weekly_task_plan
                ON weekly_tasks(plan_id, quadrant, status);
            CREATE INDEX IF NOT EXISTS idx_weekly_focus_year
                ON weekly_focus_categories(scope_key, year, status);
            """
        )
        c.commit()

    year = date.today().year
    existing = _qdf(
        get_conn,
        "SELECT COUNT(*) n FROM weekly_focus_categories WHERE scope_key='KHDN' AND year=?",
        (year,),
    )
    if existing.empty or int(existing.iloc[0]["n"]) == 0:
        with get_conn() as c:
            for idx, (code, name, desc) in enumerate(DEFAULT_FOCUS, start=1):
                c.execute(
                    """INSERT OR IGNORE INTO weekly_focus_categories
                       (scope_key,year,code,name,description,display_order,status,created_by,created_at,updated_at)
                       VALUES('KHDN',?,?,?,?,?,'ACTIVE',NULL,?,?)""",
                    (year, code, name, desc, idx, _now(), _now()),
                )
            c.commit()


def _get_plan(get_conn: Callable, user_id: int, iso_year: int, iso_week: int):
    df = _qdf(
        get_conn,
        "SELECT * FROM weekly_plans WHERE user_id=? AND iso_year=? AND iso_week=?",
        (int(user_id), int(iso_year), int(iso_week)),
    )
    return None if df.empty else df.iloc[0].to_dict()


def _get_or_create_plan(get_conn: Callable, user_id: int, iso_year: int, iso_week: int, start: date, end: date):
    plan = _get_plan(get_conn, user_id, iso_year, iso_week)
    if plan:
        return plan
    _execute(
        get_conn,
        """INSERT INTO weekly_plans
           (user_id,iso_year,iso_week,start_date,end_date,status,created_at,updated_at)
           VALUES(?,?,?,?,?,'DRAFT',?,?)""",
        (int(user_id), iso_year, iso_week, start.isoformat(), end.isoformat(), _now(), _now()),
    )
    return _get_plan(get_conn, user_id, iso_year, iso_week)


def _focus_df(get_conn: Callable, year: int, active_only=True):
    sql = """SELECT * FROM weekly_focus_categories
             WHERE scope_key='KHDN' AND year=?"""
    params = [int(year)]
    if active_only:
        sql += " AND status='ACTIVE'"
    sql += " ORDER BY display_order, code"
    return _qdf(get_conn, sql, tuple(params))


def _tasks_df(get_conn: Callable, plan_id: int):
    return _qdf(
        get_conn,
        """SELECT t.*, f.code focus_code, f.name focus_name, f.description focus_description
           FROM weekly_tasks t
           LEFT JOIN weekly_focus_categories f ON f.id=t.focus_category_id
           WHERE t.plan_id=?
           ORDER BY CASE t.quadrant WHEN 'Q2' THEN 1 WHEN 'Q1' THEN 2 WHEN 'Q3' THEN 3 ELSE 4 END,
                    t.is_emergent, COALESCE(t.due_date,'9999-12-31'), t.id""",
        (int(plan_id),),
    )


def _review(get_conn: Callable, plan_id: int):
    df = _qdf(get_conn, "SELECT * FROM weekly_reviews WHERE plan_id=?", (int(plan_id),))
    return None if df.empty else df.iloc[0].to_dict()


def _classification(focus_id, urgent, has_kpi_or_risk):
    if focus_id:
        return "Q2"
    if not urgent:
        return "Q4"
    return "Q1" if has_kpi_or_risk else "Q3"


def _task_log(get_conn: Callable, task_id: int, actor_id: int, field: str, old, new, detail=""):
    with get_conn() as c:
        c.execute(
            """INSERT INTO weekly_task_logs
               (task_id,actor_user_id,field_name,old_value,new_value,detail,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (int(task_id), int(actor_id), field, str(old or ""), str(new or ""), str(detail or ""), _now()),
        )
        c.commit()


def _plan_metrics(tasks: pd.DataFrame):
    if tasks is None or tasks.empty:
        return {"total": 0, "done": 0, "q2": 0, "planned_hours": 0.0, "actual_hours": 0.0, "on_time": 0, "emergent": 0}
    valid = tasks[tasks["status"].ne("CANCELLED")].copy()
    done = valid[valid["status"].eq("COMPLETED")]
    on_time = 0
    for _, row in done.iterrows():
        try:
            completed = pd.to_datetime(row["completed_at"]).date()
            due = pd.to_datetime(row["due_date"]).date()
            if completed <= due:
                on_time += 1
        except Exception:
            pass
    return {
        "total": int(len(valid)),
        "done": int(len(done)),
        "q2": int((valid["quadrant"] == "Q2").sum()),
        "planned_hours": float(pd.to_numeric(valid["planned_hours"], errors="coerce").fillna(0).sum()),
        "actual_hours": float(pd.to_numeric(valid["actual_hours"], errors="coerce").fillna(0).sum()),
        "on_time": int(on_time),
        "emergent": int(pd.to_numeric(valid["is_emergent"], errors="coerce").fillna(0).astype(int).sum()),
    }


def _progress_score(tasks: pd.DataFrame) -> float:
    if tasks is None or tasks.empty:
        return 0.0
    weights = {"Q2": 3.0, "Q1": 3.0, "Q3": 1.0, "Q4": 0.0}
    numerator = 0.0
    denominator = 0.0
    for _, r in tasks.iterrows():
        if str(r.get("status")) == "CANCELLED":
            continue
        w = weights.get(str(r.get("quadrant")), 0.0)
        denominator += w
        h = 0.0
        if str(r.get("status")) == "COMPLETED":
            h = 0.6
            try:
                if pd.to_datetime(r.get("completed_at")).date() <= pd.to_datetime(r.get("due_date")).date():
                    h = 1.0
            except Exception:
                h = 1.0
        numerator += w * h
    return 100.0 * numerator / denominator if denominator > 0 else 0.0


def _score_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def _is_officer(u) -> bool:
    return str(u.get("role")) in {"Cán bộ hỗ trợ", "Cán bộ QLKH"}


def _is_leader(u) -> bool:
    return str(u.get("role")) == "Lãnh đạo phòng"


def _inject_weekly_css():
    st.markdown(
        """
        <style>
        .weekly-hero{background:linear-gradient(135deg,#17312F 0%,#1D403C 100%);border:1px solid rgba(164,232,219,.30);border-radius:16px;padding:14px 16px;box-shadow:0 8px 20px rgba(0,0,0,.18);margin:.15rem 0 .8rem;color:#F4FFFC}
        .weekly-hero *{color:#F4FFFC!important}.weekly-hero-top{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.weekly-title{font-size:1.05rem;font-weight:900}.weekly-sub{color:#B7D5D0!important;font-size:.86rem;margin-top:3px}.weekly-status{border:1px solid rgba(244,180,26,.65);border-radius:999px;padding:5px 10px;font-size:.78rem;font-weight:900;background:rgba(244,180,26,.12)}
        .weekly-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}.weekly-kpi{background:#122624;border:1px solid rgba(164,232,219,.20);border-radius:12px;padding:9px 10px}.weekly-kpi .v{font-size:1.08rem;font-weight:900;color:#F4FFFC}.weekly-kpi .l{font-size:.72rem;color:#B7D5D0;margin-top:2px}
        .weekly-task-card{background:#17312F;border:1px solid rgba(164,232,219,.28);border-left:5px solid #62D7AF;border-radius:13px;padding:11px 12px;margin:7px 0;color:#F4FFFC;box-shadow:0 5px 14px rgba(0,0,0,.16)}.weekly-task-card.q1{border-left-color:#FF7B72}.weekly-task-card.q2{border-left-color:#62D7AF}.weekly-task-card.q3{border-left-color:#F4B41A}.weekly-task-card.q4{border-left-color:#8AA6A1}.weekly-task-card *{color:#F4FFFC!important}.weekly-task-head{display:flex;gap:8px;align-items:flex-start;justify-content:space-between}.weekly-task-title{font-weight:900;line-height:1.28;overflow-wrap:anywhere}.weekly-badge{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:3px 8px;font-size:.72rem;font-weight:900;border:1px solid rgba(255,255,255,.18);white-space:nowrap}.weekly-meta{color:#B7D5D0!important;font-size:.78rem;margin-top:6px;line-height:1.35;overflow-wrap:anywhere}.weekly-result{font-size:.82rem;margin-top:7px;padding-top:7px;border-top:1px solid rgba(164,232,219,.14);overflow-wrap:anywhere}
        div[class*="st-key-weekly_create_action"] button,div[class*="st-key-weekly_submit_action"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #FFE589!important;font-weight:900!important;box-shadow:0 8px 20px rgba(244,180,26,.26)!important}div[class*="st-key-weekly_create_action"] button *,div[class*="st-key-weekly_submit_action"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
        @media(max-width:700px){.weekly-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.weekly-hero{padding:11px 12px;border-radius:13px}.weekly-task-card{padding:9px 10px}.weekly-task-title{font-size:.88rem}.weekly-meta,.weekly-result{font-size:.74rem}.weekly-badge{font-size:.67rem;padding:3px 7px}}
        @media(max-width:390px){.weekly-grid{grid-template-columns:1fr 1fr}}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header(plan, tasks):
    m = _plan_metrics(tasks)
    progress = (100.0 * m["done"] / m["total"]) if m["total"] else 0.0
    q2_share = (100.0 * float(pd.to_numeric(tasks.loc[tasks["quadrant"].eq("Q2"), "actual_hours"], errors="coerce").fillna(0).sum()) / max(0.0001, m["actual_hours"])) if m["actual_hours"] > 0 else 0.0
    st.markdown(
        f"""
        <div class="weekly-hero"><div class="weekly-hero-top"><div><div class="weekly-title">📅 Tuần {int(plan['iso_week'])}/{int(plan['iso_year'])}</div><div class="weekly-sub">{html.escape(str(plan['start_date']))} → {html.escape(str(plan['end_date']))}</div></div><div class="weekly-status">{html.escape(PLAN_STATUS_LABELS.get(str(plan['status']), str(plan['status'])))}</div></div>
        <div class="weekly-grid"><div class="weekly-kpi"><div class="v">{m['done']}/{m['total']}</div><div class="l">Công việc hoàn thành</div></div><div class="weekly-kpi"><div class="v">{progress:.0f}%</div><div class="l">Tiến độ tuần</div></div><div class="weekly-kpi"><div class="v">{m['q2']}</div><div class="l">Công việc Q2</div></div><div class="weekly-kpi"><div class="v">{q2_share:.1f}%</div><div class="l">Tỷ trọng giờ Q2 thực tế</div></div></div></div>
        """,
        unsafe_allow_html=True,
    )


def _render_task_card(row):
    q = str(row.get("quadrant") or "Q4")
    qname = QUADRANT_META.get(q, ("", "", ""))[0]
    due = str(row.get("due_date") or "—")
    planned = float(row.get("planned_hours") or 0)
    actual = float(row.get("actual_hours") or 0)
    emergent = " · ⚡ Phát sinh" if int(row.get("is_emergent") or 0) else ""
    focus = f" · {row.get('focus_code')} — {row.get('focus_name')}" if row.get("focus_name") else ""
    status = TASK_STATUS_LABELS.get(str(row.get("status")), str(row.get("status")))
    expected = html.escape(str(row.get("expected_result") or ""))
    actual_result = html.escape(str(row.get("actual_result") or ""))
    actual_html = f"<div class='weekly-result'><b>Kết quả thực tế:</b> {actual_result}</div>" if actual_result else ""
    st.markdown(f"""<div class="weekly-task-card {q.lower()}"><div class="weekly-task-head"><div class="weekly-task-title">{html.escape(str(row.get('title') or ''))}</div><span class="weekly-badge">{q} · {html.escape(qname)}</span></div><div class="weekly-meta">{html.escape(status)}{emergent}{html.escape(focus)}<br>Hạn: {html.escape(due)} · {planned:.1f}h dự kiến / {actual:.1f}h thực tế</div><div class="weekly-result"><b>Đầu ra dự kiến:</b> {expected}</div>{actual_html}</div>""", unsafe_allow_html=True)


def _add_task_form(get_conn, u, plan, *, emergent=False):
    year = int(plan["iso_year"])
    focus = _focus_df(get_conn, year, active_only=True)
    options = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
    def fmt_focus(x):
        if x == 0: return "— Không thuộc mục trọng tâm nào —"
        r = focus[focus["id"].eq(int(x))].iloc[0]
        return f"{r['code']} — {r['name']}"
    key_prefix = "emergent" if emergent else "planned"
    with st.form(f"weekly_add_{key_prefix}", clear_on_submit=True):
        title = st.text_input("Tên công việc *", max_chars=200, key=f"{key_prefix}_title")
        focus_id = st.selectbox("Danh mục công việc trọng tâm Q2", options, format_func=fmt_focus, key=f"{key_prefix}_focus", help="Nếu chọn một mục trọng tâm, hệ thống tự xếp Q2 và không cần tự nhận định công việc là quan trọng.")
        if focus_id and not focus.empty:
            r = focus[focus["id"].eq(int(focus_id))].iloc[0]
            st.caption(f"Phạm vi: {r['description']}")
            urgent = False; has_kpi = False; q = "Q2"
        else:
            urgent = st.checkbox("Có hạn hoàn thành trong 7 ngày tới?", key=f"{key_prefix}_urgent")
            has_kpi = False
            if urgent:
                has_kpi = st.checkbox("Gắn với chỉ tiêu được giao hoặc rủi ro trọng yếu?", key=f"{key_prefix}_kpi")
            q = _classification(None, urgent, has_kpi)
        qname, qdesc, _ = QUADRANT_META[q]
        st.info(f"Hệ thống phân loại: **{q} – {qname}**. {qdesc}")
        c1, c2 = st.columns(2)
        due = c1.date_input("Hạn hoàn thành *", value=date.today() + timedelta(days=3), key=f"{key_prefix}_due")
        planned_hours = c2.number_input("Giờ dự kiến *", min_value=0.5, max_value=45.0, value=2.0, step=0.5, key=f"{key_prefix}_hours")
        expected = st.text_area("Kết quả đầu ra dự kiến *", max_chars=300, key=f"{key_prefix}_expected")
        submitted = st.form_submit_button("➕ Thêm việc phát sinh" if emergent else "➕ Thêm vào kế hoạch", type="primary", use_container_width=True)
    if submitted:
        if not title.strip(): st.error("Tên công việc là bắt buộc."); return
        if not expected.strip(): st.error("Kết quả đầu ra dự kiến là bắt buộc."); return
        existing = _tasks_df(get_conn, int(plan["id"]))
        if not emergent:
            planned_only = existing[pd.to_numeric(existing.get("is_emergent", 0), errors="coerce").fillna(0).eq(0)] if not existing.empty else existing
            if len(planned_only) >= 7: st.error("Kế hoạch tuần tối đa 7 công việc. Công việc thứ 8 chỉ được thêm dưới dạng phát sinh trong tuần."); return
            total_hours = float(pd.to_numeric(existing.get("planned_hours", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not existing.empty else 0.0
            if total_hours + float(planned_hours) > 45: st.error("Tổng giờ dự kiến vượt 45 giờ. Hãy điều chỉnh trước khi thêm."); return
        q = _classification(int(focus_id) if focus_id else None, bool(urgent), bool(has_kpi))
        task_id = _execute(get_conn, """INSERT INTO weekly_tasks(plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,planned_hours,actual_hours,status,is_emergent,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,0,'NOT_STARTED',?,?,?)""", (int(plan["id"]), title.strip(), expected.strip(), int(focus_id) if focus_id else None, int(bool(urgent)), int(bool(has_kpi)), q, due.isoformat(), float(planned_hours), int(bool(emergent)), _now(), _now()))
        _log(get_conn, int(u["id"]), "ADD_EMERGENT_TASK" if emergent else "ADD_TASK", "weekly_task", task_id, f"quadrant={q}")
        st.success("Đã thêm công việc."); st.rerun()


def _validate_submit(tasks: pd.DataFrame):
    errors = []
    if tasks is None or tasks.empty: return ["Kế hoạch chưa có công việc."]
    planned = tasks[pd.to_numeric(tasks["is_emergent"], errors="coerce").fillna(0).eq(0)].copy()
    if len(planned) > 7: errors.append("Kế hoạch có trên 7 công việc.")
    q2 = int((planned["quadrant"] == "Q2").sum())
    if q2 < 3: errors.append(f"Cần tối thiểu 3 công việc Q2; hiện có {q2}.")
    hours = float(pd.to_numeric(planned["planned_hours"], errors="coerce").fillna(0).sum())
    if hours > 45: errors.append(f"Tổng giờ dự kiến {hours:.1f}h vượt giới hạn 45h.")
    if planned["expected_result"].fillna("").astype(str).str.strip().eq("").any(): errors.append("Có công việc thiếu kết quả đầu ra dự kiến.")
    return errors


def _delete_draft_task(get_conn, u, task_id):
    _log(get_conn, int(u["id"]), "DELETE_DRAFT_TASK", "weekly_task", task_id, "")
    _execute(get_conn, "DELETE FROM weekly_tasks WHERE id=?", (int(task_id),))


def _draft_view(get_conn, u, plan, tasks):
    st.markdown("### Kế hoạch công việc")
    for _, row in tasks.iterrows():
        _render_task_card(row)
        cols = st.columns([1, 1, 3])
        if cols[0].button("🗑 Xóa", key=f"weekly_del_{int(row['id'])}", use_container_width=True): _delete_draft_task(get_conn, u, int(row["id"])); st.rerun()
    with st.expander("➕ Thêm công việc vào kế hoạch", expanded=tasks.empty): _add_task_form(get_conn, u, plan, emergent=False)
    tasks = _tasks_df(get_conn, int(plan["id"]))
    errors = _validate_submit(tasks)
    if errors: st.warning("Chưa thể nộp kế hoạch:\n\n- " + "\n- ".join(errors))
    with st.container(key="weekly_submit_action"):
        if st.button("📤 Nộp kế hoạch tuần", use_container_width=True, type="primary", disabled=bool(errors)):
            if _is_leader(u):
                _execute(get_conn, """UPDATE weekly_plans SET status='APPROVED',submitted_at=?,approved_at=?,reviewer_user_id=?,return_reason=NULL,updated_at=? WHERE id=?""", (_now(), _now(), int(u["id"]), _now(), int(plan["id"])))
                _log(get_conn, int(u["id"]), "SELF_APPROVE_LEADER_PLAN", "weekly_plan", plan["id"], "Leader plan has no higher approver in this module")
                st.success("Kế hoạch của lãnh đạo phòng đã được chốt làm kế hoạch thực hiện.")
            else:
                _execute(get_conn, "UPDATE weekly_plans SET status='SUBMITTED',submitted_at=?,return_reason=NULL,updated_at=? WHERE id=?", (_now(), _now(), int(plan["id"])))
                _log(get_conn, int(u["id"]), "SUBMIT_PLAN", "weekly_plan", plan["id"], "")
                st.success("Đã nộp kế hoạch cho lãnh đạo phòng.")
            st.rerun()


def _update_task_status(get_conn, u, row, new_status):
    old = str(row.get("status") or "")
    completed_at = _now() if new_status == "COMPLETED" else None
    _execute(get_conn, "UPDATE weekly_tasks SET status=?,completed_at=?,updated_at=? WHERE id=?", (new_status, completed_at, _now(), int(row["id"])))
    _task_log(get_conn, int(row["id"]), int(u["id"]), "status", old, new_status)
    _log(get_conn, int(u["id"]), "TASK_STATUS", "weekly_task", row["id"], f"{old}->{new_status}")


def _task_runtime_controls(get_conn, u, row):
    status = str(row.get("status") or "NOT_STARTED")
    labels = [("NOT_STARTED", "○ Chưa làm"), ("IN_PROGRESS", "▶ Đang làm"), ("COMPLETED", "✓ Hoàn thành")]
    cols = st.columns(3)
    for col, (value, label) in zip(cols, labels):
        if col.button(label, key=f"weekly_status_{int(row['id'])}_{value}", use_container_width=True, type="primary" if status == value else "secondary"):
            if status != value: _update_task_status(get_conn, u, row, value); st.rerun()
    with st.expander("Cập nhật giờ & kết quả thực tế", expanded=False):
        actual_hours = st.number_input("Giờ thực tế", min_value=0.0, max_value=100.0, value=float(row.get("actual_hours") or 0), step=0.5, key=f"weekly_actual_h_{int(row['id'])}")
        actual_result = st.text_area("Kết quả thực tế đạt được", value=str(row.get("actual_result") or ""), max_chars=1000, key=f"weekly_actual_result_{int(row['id'])}")
        if st.button("Lưu cập nhật", key=f"weekly_save_actual_{int(row['id'])}", use_container_width=True):
            _execute(get_conn, "UPDATE weekly_tasks SET actual_hours=?,actual_result=?,updated_at=? WHERE id=?", (float(actual_hours), actual_result.strip(), _now(), int(row["id"])))
            _task_log(get_conn, int(row["id"]), int(u["id"]), "actual", row.get("actual_hours"), actual_hours, "Cập nhật giờ/kết quả")
            st.success("Đã lưu."); st.rerun()


def _approved_view(get_conn, u, plan, tasks):
    st.markdown("### Công việc tuần này")
    for _, row in tasks.iterrows(): _render_task_card(row); _task_runtime_controls(get_conn, u, row)
    with st.expander("⚡ Thêm việc phát sinh", expanded=False): _add_task_form(get_conn, u, plan, emergent=True)
    st.divider(); st.markdown("### Chốt tuần & tự đánh giá")
    review = _review(get_conn, int(plan["id"])) or {}
    with st.form(f"weekly_close_{int(plan['id'])}"):
        strengths = st.text_area("Mặt được *", value=str(review.get("strengths") or ""), max_chars=500)
        limitations = st.text_area("Tồn tại, hạn chế *", value=str(review.get("limitations") or ""), max_chars=500)
        causes = st.text_area("Nguyên nhân *", value=str(review.get("causes") or ""), max_chars=500)
        next_actions = st.text_area("Đề xuất / kế hoạch khắc phục tuần sau *", value=str(review.get("next_actions") or ""), max_chars=500)
        self_score = st.slider("Tự chấm chất lượng tuần", 1, 5, int(review.get("self_score") or 4))
        close = st.form_submit_button("🔒 Chốt tuần", type="primary", use_container_width=True)
    if close:
        if any(not str(x).strip() for x in [strengths, limitations, causes, next_actions]): st.error("Bốn ô tự đánh giá đều bắt buộc.")
        else:
            ts = _now()
            with get_conn() as c:
                c.execute("""INSERT INTO weekly_reviews(plan_id,self_score,strengths,limitations,causes,next_actions,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(plan_id) DO UPDATE SET self_score=excluded.self_score,strengths=excluded.strengths,limitations=excluded.limitations,causes=excluded.causes,next_actions=excluded.next_actions,updated_at=excluded.updated_at""", (int(plan["id"]), int(self_score), strengths.strip(), limitations.strip(), causes.strip(), next_actions.strip(), ts, ts))
                c.execute("UPDATE weekly_plans SET status='CLOSED',closed_at=?,updated_at=? WHERE id=?", (ts, ts, int(plan["id"]))); c.commit()
            _log(get_conn, int(u["id"]), "CLOSE_PLAN", "weekly_plan", plan["id"], f"self_score={self_score}"); st.success("Đã chốt tuần."); st.rerun()


def _submitted_view(get_conn, u, plan, tasks):
    if plan.get("return_reason"): st.error(f"Lý do trả lại: {plan['return_reason']}")
    for _, row in tasks.iterrows(): _render_task_card(row)
    if str(plan["status"]) == "SUBMITTED" and _is_officer(u):
        if st.button("↩ Thu hồi kế hoạch để chỉnh sửa", use_container_width=True):
            _execute(get_conn, "UPDATE weekly_plans SET status='DRAFT',updated_at=? WHERE id=? AND status='SUBMITTED'", (_now(), int(plan["id"])))
            _log(get_conn, int(u["id"]), "RECALL_PLAN", "weekly_plan", plan["id"], ""); st.rerun()


def _reviewed_view(get_conn, plan, tasks):
    for _, row in tasks.iterrows(): _render_task_card(row)
    rv = _review(get_conn, int(plan["id"]))
    if not rv: st.info("Kế hoạch đã chốt, đang chờ lãnh đạo nhận xét."); return
    c1, c2, c3 = st.columns(3)
    c1.metric("Điểm tiến độ", f"{float(rv.get('progress_score') or 0):.1f}"); c2.metric("Điểm chất lượng", f"{float(rv.get('quality_score') or 0):.1f}"); c3.metric("Điểm tuần", f"{float(rv.get('week_score') or 0):.1f} · {rv.get('grade') or '—'}")
    if rv.get("leader_comment"): st.info(f"Nhận xét lãnh đạo: {rv['leader_comment']}")


def _my_plan_view(get_conn, u):
    year, week, monday, sunday = _iso_week(); plan = _get_or_create_plan(get_conn, int(u["id"]), year, week, monday, sunday); tasks = _tasks_df(get_conn, int(plan["id"])); _render_header(plan, tasks)
    if str(plan["status"]) in {"DRAFT", "RETURNED"}: _draft_view(get_conn, u, plan, tasks)
    elif str(plan["status"]) == "SUBMITTED": st.info("Kế hoạch đã nộp, đang chờ lãnh đạo phòng duyệt."); _submitted_view(get_conn, u, plan, tasks)
    elif str(plan["status"]) == "APPROVED": _approved_view(get_conn, u, plan, tasks)
    elif str(plan["status"]) == "CLOSED": st.info("Bạn đã chốt tuần. Dữ liệu hiện ở chế độ chỉ đọc và đang chờ lãnh đạo đánh giá."); _reviewed_view(get_conn, plan, tasks)
    elif str(plan["status"]) == "REVIEWED": _reviewed_view(get_conn, plan, tasks)


def _leader_plan_selector(get_conn):
    year, week, _, _ = _iso_week()
    return _qdf(get_conn, """SELECT p.*,u.full_name,u.username,u.role FROM weekly_plans p JOIN users u ON u.id=p.user_id WHERE p.iso_year=? AND p.iso_week=? AND u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') ORDER BY CASE p.status WHEN 'SUBMITTED' THEN 1 WHEN 'CLOSED' THEN 2 WHEN 'RETURNED' THEN 3 ELSE 4 END,u.full_name""", (year, week))


def _leader_review_view(get_conn, u):
    year, week, monday, sunday = _iso_week()
    users = _qdf(get_conn, """SELECT id,full_name,username,role FROM users WHERE active=1 AND role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') ORDER BY full_name""")
    for _, person in users.iterrows():
        if _get_plan(get_conn, int(person["id"]), year, week) is None: _get_or_create_plan(get_conn, int(person["id"]), year, week, monday, sunday)
    plans = _leader_plan_selector(get_conn)
    if plans.empty: st.info("Chưa có cán bộ."); return
    counts = {s: int((plans["status"] == s).sum()) for s in ["SUBMITTED", "CLOSED", "APPROVED", "REVIEWED"]}
    cols = st.columns(4); cols[0].metric("Chờ duyệt", counts["SUBMITTED"]); cols[1].metric("Chờ nhận xét", counts["CLOSED"]); cols[2].metric("Đang thực hiện", counts["APPROVED"]); cols[3].metric("Hoàn tất", counts["REVIEWED"])
    pid = st.selectbox("Chọn cán bộ", plans["id"].astype(int).tolist(), format_func=lambda x: f"{plans[plans['id'].eq(int(x))].iloc[0]['full_name']} · {PLAN_STATUS_LABELS.get(plans[plans['id'].eq(int(x))].iloc[0]['status'], plans[plans['id'].eq(int(x))].iloc[0]['status'])}", key="weekly_leader_plan_select")
    plan = plans[plans["id"].eq(int(pid))].iloc[0].to_dict(); tasks = _tasks_df(get_conn, int(plan["id"])); _render_header(plan, tasks)
    for _, row in tasks.iterrows(): _render_task_card(row)
    status = str(plan["status"])
    if status == "SUBMITTED":
        errors = _validate_submit(tasks)
        if errors: st.warning("Kế hoạch có cảnh báo:\n\n- " + "\n- ".join(errors))
        c1, c2 = st.columns(2)
        if c1.button("✅ Duyệt kế hoạch", type="primary", use_container_width=True, disabled=bool(errors)):
            _execute(get_conn, """UPDATE weekly_plans SET status='APPROVED',approved_at=?,reviewer_user_id=?,return_reason=NULL,updated_at=? WHERE id=? AND status='SUBMITTED'""", (_now(), int(u["id"]), _now(), int(plan["id"]))); _log(get_conn, int(u["id"]), "APPROVE_PLAN", "weekly_plan", plan["id"], ""); st.rerun()
        with c2:
            reason = st.text_input("Lý do trả lại *", key=f"weekly_return_reason_{int(plan['id'])}")
            if st.button("↩ Trả lại", use_container_width=True, key=f"weekly_return_{int(plan['id'])}"):
                if not reason.strip(): st.error("Bắt buộc ghi lý do khi trả lại.")
                else: _execute(get_conn, """UPDATE weekly_plans SET status='RETURNED',return_reason=?,updated_at=? WHERE id=?""", (reason.strip(), _now(), int(plan["id"]))); _log(get_conn, int(u["id"]), "RETURN_PLAN", "weekly_plan", plan["id"], reason.strip()); st.rerun()
    elif status == "CLOSED":
        rv = _review(get_conn, int(plan["id"])) or {}
        st.markdown("### Tự đánh giá của cán bộ"); st.caption(f"Tự chấm: {rv.get('self_score') or '—'}/5"); st.write(f"**Mặt được:** {rv.get('strengths') or '—'}"); st.write(f"**Tồn tại:** {rv.get('limitations') or '—'}"); st.write(f"**Nguyên nhân:** {rv.get('causes') or '—'}"); st.write(f"**Đề xuất:** {rv.get('next_actions') or '—'}")
        with st.form(f"weekly_leader_review_{int(plan['id'])}"):
            leader_score = st.slider("Điểm chất lượng của lãnh đạo", 1, 5, int(rv.get("leader_score") or 4)); comment = st.text_area("Nhận xét lãnh đạo *", max_chars=1000, value=str(rv.get("leader_comment") or "")); self_score = int(rv.get("self_score") or 0); gap_reason = ""
            if self_score and abs(leader_score - self_score) >= 2: gap_reason = st.text_area("Lý do chênh lệch từ 2 điểm trở lên *", max_chars=500)
            submit_review = st.form_submit_button("Hoàn tất đánh giá", type="primary", use_container_width=True)
        if submit_review:
            if not comment.strip(): st.error("Nhận xét lãnh đạo là bắt buộc.")
            elif self_score and abs(leader_score - self_score) >= 2 and not gap_reason.strip(): st.error("Bắt buộc ghi lý do khi chênh lệch từ 2 điểm trở lên.")
            else:
                progress = _progress_score(tasks); quality = 20.0 * (0.3 * self_score + 0.7 * leader_score); week_score = 0.5 * progress + 0.5 * quality; grade = _score_grade(week_score); ts = _now()
                with get_conn() as c:
                    c.execute("""UPDATE weekly_reviews SET leader_score=?,leader_comment=?,score_gap_reason=?,progress_score=?,quality_score=?,week_score=?,grade=?,updated_at=? WHERE plan_id=?""", (leader_score, comment.strip(), gap_reason.strip(), progress, quality, week_score, grade, ts, int(plan["id"]))); c.execute("UPDATE weekly_plans SET status='REVIEWED',reviewed_at=?,reviewer_user_id=?,updated_at=? WHERE id=?", (ts, int(u["id"]), ts, int(plan["id"]))); c.commit()
                _log(get_conn, int(u["id"]), "REVIEW_PLAN", "weekly_plan", plan["id"], f"week_score={week_score:.2f};grade={grade}"); st.success("Đã hoàn tất đánh giá tuần."); st.rerun()
    elif status == "RETURNED": st.warning(f"Đã trả lại cán bộ: {plan.get('return_reason') or 'Không có lý do'}")
    elif status == "DRAFT": st.info("Cán bộ đang lập kế hoạch, chưa nộp.")
    elif status == "APPROVED": st.info("Kế hoạch đã duyệt và đang thực hiện.")
    elif status == "REVIEWED":
        rv = _review(get_conn, int(plan["id"]));
        if rv: st.success(f"Đã đánh giá · Điểm tuần {float(rv.get('week_score') or 0):.1f} · Xếp loại {rv.get('grade') or '—'}")


def _focus_admin_view(get_conn, u):
    year = st.selectbox("Năm áp dụng", [date.today().year - 1, date.today().year, date.today().year + 1], index=1, key="weekly_focus_year"); df = _focus_df(get_conn, int(year), active_only=False)
    if not df.empty:
        show = df[["code", "name", "description", "display_order", "status"]].rename(columns={"code": "Mã", "name": "Tên trọng tâm", "description": "Phạm vi", "display_order": "Thứ tự", "status": "Trạng thái"}); st.dataframe(show, use_container_width=True, hide_index=True)
    st.markdown("### Thêm mục trọng tâm")
    with st.form("weekly_new_focus"):
        code = st.text_input("Mã *", max_chars=20); name = st.text_input("Tên ngắn gọn *", max_chars=200); description = st.text_area("Mô tả phạm vi *", max_chars=500); order = st.number_input("Thứ tự hiển thị", min_value=1, max_value=99, value=max(1, len(df) + 1)); add = st.form_submit_button("Thêm mục", type="primary")
    if add:
        if not code.strip() or not name.strip() or not description.strip(): st.error("Mã, tên và mô tả phạm vi đều bắt buộc.")
        else:
            try:
                xid = _execute(get_conn, """INSERT INTO weekly_focus_categories(scope_key,year,code,name,description,display_order,status,created_by,created_at,updated_at) VALUES('KHDN',?,?,?,?,?,'ACTIVE',?,?,?)""", (int(year), code.strip().upper(), name.strip(), description.strip(), int(order), int(u["id"]), _now(), _now())); _log(get_conn, int(u["id"]), "ADD_FOCUS_CATEGORY", "weekly_focus_category", xid, code.strip().upper()); st.rerun()
            except sqlite3.IntegrityError: st.error("Mã trọng tâm đã tồn tại trong năm này.")
    if not df.empty:
        st.markdown("### Ngừng / kích hoạt lại"); focus_id = st.selectbox("Chọn mục", df["id"].astype(int).tolist(), format_func=lambda x: f"{df[df['id'].eq(int(x))].iloc[0]['code']} — {df[df['id'].eq(int(x))].iloc[0]['name']}", key="weekly_focus_toggle_select"); row = df[df["id"].eq(int(focus_id))].iloc[0]; target = "INACTIVE" if row["status"] == "ACTIVE" else "ACTIVE"; label = "Ngừng áp dụng" if target == "INACTIVE" else "Kích hoạt lại"
        if st.button(label, use_container_width=True): _execute(get_conn, "UPDATE weekly_focus_categories SET status=?,updated_at=? WHERE id=?", (target, _now(), int(focus_id))); _log(get_conn, int(u["id"]), "TOGGLE_FOCUS_CATEGORY", "weekly_focus_category", focus_id, f"{row['status']}->{target}"); st.rerun()


def _room_dashboard(get_conn):
    year, week, _, _ = _iso_week(); df = _qdf(get_conn, """SELECT p.id,p.status,u.full_name,u.role,COUNT(t.id) task_count,SUM(CASE WHEN t.status='COMPLETED' THEN 1 ELSE 0 END) done_count,SUM(CASE WHEN t.quadrant='Q2' THEN 1 ELSE 0 END) q2_count,COALESCE(SUM(t.actual_hours),0) actual_hours,COALESCE(SUM(CASE WHEN t.quadrant='Q2' THEN t.actual_hours ELSE 0 END),0) q2_hours,r.week_score,r.grade FROM weekly_plans p JOIN users u ON u.id=p.user_id LEFT JOIN weekly_tasks t ON t.plan_id=p.id AND t.status<>'CANCELLED' LEFT JOIN weekly_reviews r ON r.plan_id=p.id WHERE p.iso_year=? AND p.iso_week=? AND u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') GROUP BY p.id,p.status,u.full_name,u.role,r.week_score,r.grade ORDER BY u.full_name""", (year, week))
    if df.empty: st.info("Chưa có dữ liệu kế hoạch tuần."); return
    df["Tỷ lệ hoàn thành"] = df.apply(lambda r: (100.0 * float(r["done_count"] or 0) / float(r["task_count"] or 1)) if float(r["task_count"] or 0) > 0 else 0.0, axis=1); df["Chỉ số Q2"] = df.apply(lambda r: (100.0 * float(r["q2_hours"] or 0) / float(r["actual_hours"] or 1)) if float(r["actual_hours"] or 0) > 0 else 0.0, axis=1)
    show = df[["full_name", "role", "status", "task_count", "done_count", "Tỷ lệ hoàn thành", "Chỉ số Q2", "week_score", "grade"]].copy(); show["status"] = show["status"].map(lambda x: PLAN_STATUS_LABELS.get(str(x), str(x))); show = show.rename(columns={"full_name": "Cán bộ", "role": "Vai trò", "status": "Trạng thái", "task_count": "Số việc", "done_count": "Hoàn thành", "week_score": "Điểm tuần", "grade": "Xếp loại"})
    st.dataframe(show.style.format({"Tỷ lệ hoàn thành": "{:.1f}%", "Chỉ số Q2": "{:.1f}%", "Điểm tuần": "{:.1f}"}, na_rep="—"), use_container_width=True, hide_index=True)


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    """Entry point used by KHDN_APP."""
    init_weekly_schema(get_conn); _inject_weekly_css(); page_title("Kế hoạch tuần", "Quản trị ưu tiên công việc theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư.")
    if _is_leader(u): options = [("mine", "📅 Kế hoạch của tôi"), ("review", "✅ Duyệt & đánh giá"), ("focus", "🎯 Trọng tâm Q2"), ("room", "📊 Tổng quan phòng")]
    else: options = [("mine", "📅 Tuần của tôi")]
    if pill_nav: view = pill_nav("weekly_plan_view", options, default="mine", prefix="weekly_plan")
    else:
        labels = [x[1] for x in options]; current = st.session_state.get("weekly_plan_view", "mine"); idx = [x[0] for x in options].index(current) if current in [x[0] for x in options] else 0; label = st.radio("Chế độ", labels, index=idx, horizontal=True, label_visibility="collapsed"); view = dict((b, a) for a, b in options)[label]; st.session_state["weekly_plan_view"] = view
    if view == "mine": _my_plan_view(get_conn, u)
    elif view == "review" and _is_leader(u): _leader_review_view(get_conn, u)
    elif view == "focus" and _is_leader(u): _focus_admin_view(get_conn, u)
    elif view == "room" and _is_leader(u): _room_dashboard(get_conn)
