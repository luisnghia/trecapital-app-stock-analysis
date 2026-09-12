"""Weekly Plan V6 UX/completeness layer for KHDN Ops.

Key goals:
- Do not ask users to re-enter urgency when a due date already determines it.
- Show Q1-Q4 classification immediately while editing.
- Add durable in-app notifications from the v1.2 notification matrix.
- Expand the room dashboard and remove horizontal table overflow on phone widths.
- Keep the module restricted to officers and room leaders; no Ban Giám đốc view.
"""
from __future__ import annotations

import html
import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v3 as v3
from khdn_apps import weekly_plan_v4 as v4
from khdn_apps import weekly_plan_v5 as v5


def _init_v6_schema(get_conn: Callable):
    v4._init_v4_schema(get_conn)
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_key TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            plan_id INTEGER,
            task_id INTEGER,
            created_at TEXT NOT NULL,
            read_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(plan_id) REFERENCES weekly_plans(id) ON DELETE CASCADE,
            FOREIGN KEY(task_id) REFERENCES weekly_tasks(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_weekly_notifications_user_read
            ON weekly_notifications(user_id,read_at,created_at);
        """)
        c.commit()


def _inject_v6_css():
    st.markdown(
        """
        <style>
        .weekly-notification{background:#17312F;border:1px solid rgba(164,232,219,.26);border-left:4px solid #F4B41A;border-radius:11px;padding:8px 10px;margin:6px 0;color:#F4FFFC;overflow-wrap:anywhere}
        .weekly-notification.read{opacity:.72;border-left-color:#6F918B}.weekly-notification .nt{font-weight:900;font-size:.83rem}.weekly-notification .nm{color:#CFE6E2!important;font-size:.77rem;margin-top:3px}.weekly-notification .ntime{color:#91B7B1!important;font-size:.68rem;margin-top:4px}
        .weekly-dashboard-card{background:#17312F;border:1px solid rgba(164,232,219,.26);border-radius:12px;padding:9px 10px;margin:5px 0;color:#F4FFFC}.weekly-dashboard-card *{color:#F4FFFC!important}.weekly-dashboard-card .muted{color:#B7D5D0!important;font-size:.76rem}
        @media(max-width:700px){
          .weekly-html-table-wrap{overflow-x:hidden!important;width:100%!important;max-width:100%!important}
          .weekly-html-table{min-width:0!important;width:100%!important;max-width:100%!important;table-layout:fixed!important;font-size:.62rem!important}
          .weekly-html-table th,.weekly-html-table td{white-space:normal!important;overflow-wrap:anywhere!important;word-break:break-word!important;padding:4px 3px!important;line-height:1.18!important}
          [data-testid="stHorizontalBlock"]{max-width:100%!important}
          .weekly-task-head{flex-wrap:wrap!important}.weekly-badge{white-space:normal!important}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _urgent_from_due(due) -> bool:
    try:
        due_date = pd.to_datetime(due).date()
    except Exception:
        return False
    return due_date <= (date.today() + timedelta(days=7))


def _classification_from_inputs(focus_id, due, has_kpi_or_risk):
    urgent = False if focus_id else _urgent_from_due(due)
    has_kpi = bool(has_kpi_or_risk) if urgent and not focus_id else False
    return wp._classification(int(focus_id) if focus_id else None, urgent, has_kpi), urgent, has_kpi


def _focus_formatter(focus: pd.DataFrame):
    def fmt(x):
        if int(x) == 0:
            return "— Không thuộc mục trọng tâm nào —"
        row = focus[focus["id"].eq(int(x))].iloc[0]
        return f"{row['code']} — {row['name']}"
    return fmt


def _add_task_form_due_driven(get_conn, u, plan, *, emergent=False):
    """Immediate classification UI; urgency is derived from due_date, not re-entered."""
    year = int(plan["iso_year"])
    focus = wp._focus_df(get_conn, year, active_only=True)
    options = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
    prefix = f"weekly_v6_{'emergent' if emergent else 'planned'}_{int(plan['id'])}"
    nonce_key = f"{prefix}_nonce"
    nonce = int(st.session_state.get(nonce_key, 0))
    k = lambda name: f"{prefix}_{nonce}_{name}"

    title = st.text_input("Tên công việc *", max_chars=200, key=k("title"))
    focus_id = st.selectbox(
        "Danh mục công việc trọng tâm Q2",
        options,
        format_func=_focus_formatter(focus),
        key=k("focus"),
        help="Q2 là công việc thuộc danh mục trọng tâm do Lãnh đạo phòng ban hành. Chọn một mục sẽ tự xếp Q2.",
    )
    if focus_id and not focus.empty:
        r = focus[focus["id"].eq(int(focus_id))].iloc[0]
        st.caption(f"Phạm vi: {r['description']}")

    c1, c2 = st.columns(2)
    due = c1.date_input("Hạn hoàn thành *", value=date.today() + timedelta(days=3), key=k("due"))
    planned_hours = c2.number_input("Giờ dự kiến *", min_value=0.5, max_value=45.0, value=2.0, step=0.5, key=k("hours"))

    urgent = False if focus_id else _urgent_from_due(due)
    if focus_id:
        has_kpi = False
    elif urgent:
        st.caption("Hệ thống xác định **có tính cấp bách** vì hạn hoàn thành nằm trong 7 ngày tới.")
        has_kpi = st.checkbox(
            "Gắn với chỉ tiêu được giao hoặc rủi ro trọng yếu?",
            key=k("kpi"),
            help="Chỉ tiêu/rủi ro trọng yếu là căn cứ để phân biệt Q1 với Q3 khi công việc đã có tính cấp bách.",
        )
    else:
        has_kpi = False
        st.caption("Hệ thống xác định **không cấp bách** vì hạn hoàn thành ngoài 7 ngày tới.")

    q, urgent, has_kpi = _classification_from_inputs(focus_id, due, has_kpi)
    qname, qdesc, _ = wp.QUADRANT_META[q]
    st.info(f"Hệ thống phân loại: **{q} – {qname}**. {qdesc}")
    expected = st.text_area("Kết quả đầu ra dự kiến *", max_chars=300, key=k("expected"))
    submitted = st.button(
        "➕ Thêm việc phát sinh" if emergent else "➕ Thêm vào kế hoạch",
        type="primary", use_container_width=True, key=k("submit"),
    )
    if not submitted:
        return
    if not title.strip():
        st.error("Tên công việc là bắt buộc."); return
    if not expected.strip():
        st.error("Kết quả đầu ra dự kiến là bắt buộc."); return

    existing = wp._tasks_df(get_conn, int(plan["id"]))
    if not emergent:
        planned_only = existing[pd.to_numeric(existing.get("is_emergent", 0), errors="coerce").fillna(0).eq(0)] if not existing.empty else existing
        if len(planned_only) >= 7:
            st.error("Kế hoạch tuần tối đa 7 công việc. Công việc thứ 8 chỉ được thêm dưới dạng phát sinh trong tuần."); return
        total_hours = float(pd.to_numeric(existing.get("planned_hours", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not existing.empty else 0.0
        if total_hours + float(planned_hours) > 45:
            st.error("Tổng giờ dự kiến vượt 45 giờ. Hãy điều chỉnh trước khi thêm."); return

    task_id = wp._execute(get_conn, """INSERT INTO weekly_tasks(
        plan_id,title,expected_result,focus_category_id,is_urgent,has_kpi_or_risk,quadrant,due_date,
        planned_hours,actual_hours,status,is_emergent,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,0,'NOT_STARTED',?,?,?)""",
        (int(plan["id"]), title.strip(), expected.strip(), int(focus_id) if focus_id else None,
         int(bool(urgent)), int(bool(has_kpi)), q, due.isoformat(), float(planned_hours), int(bool(emergent)),
         wp._now(), wp._now()))
    wp._log(get_conn, int(u["id"]), "ADD_EMERGENT_TASK" if emergent else "ADD_TASK",
            "weekly_task", task_id, f"quadrant={q};urgency_from_due=1")
    st.session_state[nonce_key] = nonce + 1
    st.success("Đã thêm công việc.")
    st.rerun()


def _draft_editor_due_driven(get_conn: Callable, u, plan):
    tasks = wp._tasks_df(get_conn, int(plan["id"]))
    if tasks.empty:
        return
    with st.expander("✏️ Sửa công việc trong kế hoạch", expanded=False):
        task_id = st.selectbox(
            "Chọn công việc", tasks["id"].astype(int).tolist(),
            format_func=lambda x: f"{tasks[tasks['id'].eq(int(x))].iloc[0]['quadrant']} · {tasks[tasks['id'].eq(int(x))].iloc[0]['title']}",
            key="weekly_v6_edit_task",
        )
        row = tasks[tasks["id"].eq(int(task_id))].iloc[0].to_dict()
        focus = wp._focus_df(get_conn, int(plan["iso_year"]), active_only=True)
        opts = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
        current_focus = int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else 0
        idx = opts.index(current_focus) if current_focus in opts else 0
        suffix = int(task_id)
        title = st.text_input("Tên công việc *", value=str(row.get("title") or ""), max_chars=200, key=f"weekly_v6_edit_title_{suffix}")
        focus_id = st.selectbox("Danh mục trọng tâm Q2", opts, index=idx,
                                format_func=_focus_formatter(focus), key=f"weekly_v6_edit_focus_{suffix}")
        try:
            due0 = pd.to_datetime(row.get("due_date")).date()
        except Exception:
            due0 = date.today()
        c1, c2 = st.columns(2)
        due = c1.date_input("Hạn hoàn thành *", value=due0, key=f"weekly_v6_edit_due_{suffix}")
        hours = c2.number_input("Giờ dự kiến *", min_value=0.5, max_value=45.0,
                                value=float(row.get("planned_hours") or 0.5), step=0.5,
                                key=f"weekly_v6_edit_hours_{suffix}")
        urgent = False if focus_id else _urgent_from_due(due)
        if focus_id:
            has_kpi = False
        elif urgent:
            st.caption("Hạn nằm trong 7 ngày tới nên hệ thống tự xác định công việc có tính cấp bách.")
            has_kpi = st.checkbox("Gắn chỉ tiêu hoặc rủi ro trọng yếu?",
                                  value=bool(row.get("has_kpi_or_risk") or 0),
                                  key=f"weekly_v6_edit_kpi_{suffix}")
        else:
            has_kpi = False
            st.caption("Hạn ngoài 7 ngày tới nên hệ thống tự xác định công việc không cấp bách.")
        q, urgent, has_kpi = _classification_from_inputs(focus_id, due, has_kpi)
        st.info(f"Phân loại sau khi lưu: **{q} – {wp.QUADRANT_META[q][0]}**")
        expected = st.text_area("Kết quả đầu ra dự kiến *", value=str(row.get("expected_result") or ""),
                                max_chars=300, key=f"weekly_v6_edit_expected_{suffix}")
        if st.button("Lưu thay đổi", type="primary", use_container_width=True, key=f"weekly_v6_edit_save_{suffix}"):
            if not title.strip() or not expected.strip():
                st.error("Tên công việc và kết quả đầu ra là bắt buộc."); return
            other_hours = float(pd.to_numeric(tasks.loc[tasks["id"].ne(int(task_id)), "planned_hours"], errors="coerce").fillna(0).sum())
            if other_hours + float(hours) > 45:
                st.error("Tổng giờ dự kiến sau chỉnh sửa vượt 45 giờ."); return
            old_q = str(row.get("quadrant") or "")
            wp._execute(get_conn, """UPDATE weekly_tasks SET title=?,expected_result=?,focus_category_id=?,is_urgent=?,
                has_kpi_or_risk=?,quadrant=?,due_date=?,planned_hours=?,updated_at=? WHERE id=?""",
                (title.strip(), expected.strip(), int(focus_id) if focus_id else None, int(urgent), int(has_kpi), q,
                 due.isoformat(), float(hours), wp._now(), int(task_id)))
            wp._task_log(get_conn, int(task_id), int(u["id"]), "draft_edit", old_q, q,
                         "Sửa kế hoạch tuần; cấp bách tự suy ra từ hạn")
            wp._log(get_conn, int(u["id"]), "EDIT_WEEKLY_TASK", "weekly_task", task_id, f"{old_q}->{q}")
            st.rerun()


def _leader_reclass_due_driven(get_conn: Callable, u):
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
    st.caption("Lãnh đạo phòng có thể gắn/đổi/gỡ danh mục Q2 trước khi cán bộ chốt tuần. Cấp bách được tự suy ra từ hạn; mọi thay đổi đều ghi log.")
    task_id = st.selectbox("Công việc", tasks["id"].astype(int).tolist(),
        format_func=lambda x: f"{tasks[tasks['id'].eq(int(x))].iloc[0]['quadrant']} · {tasks[tasks['id'].eq(int(x))].iloc[0]['title']}",
        key="weekly_v6_reclass_task")
    row = tasks[tasks["id"].eq(int(task_id))].iloc[0].to_dict()
    focus = wp._focus_df(get_conn, int(plan["iso_year"]), active_only=True)
    opts = [0] + (focus["id"].astype(int).tolist() if not focus.empty else [])
    current = int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else 0
    idx = opts.index(current) if current in opts else 0
    new_focus = st.selectbox("Danh mục trọng tâm", opts, index=idx,
                             format_func=_focus_formatter(focus), key="weekly_v6_reclass_focus")
    due = row.get("due_date")
    urgent = False if new_focus else _urgent_from_due(due)
    if new_focus:
        has_kpi = False
    elif urgent:
        st.caption(f"Hạn {due}: hệ thống xác định công việc có tính cấp bách.")
        has_kpi = st.checkbox("Gắn chỉ tiêu hoặc rủi ro trọng yếu?",
                              value=bool(row.get("has_kpi_or_risk") or 0), key="weekly_v6_reclass_kpi")
    else:
        has_kpi = False
        st.caption(f"Hạn {due}: hệ thống xác định công việc không cấp bách.")
    new_q, urgent, has_kpi = _classification_from_inputs(new_focus, due, has_kpi)
    st.info(f"Kết quả sau điều chỉnh: **{new_q} – {wp.QUADRANT_META[new_q][0]}**")
    if st.button("Lưu điều chỉnh", type="primary", use_container_width=True, key="weekly_v6_reclass_save"):
        old_q = str(row.get("quadrant") or "")
        old_focus = int(row["focus_category_id"]) if pd.notna(row.get("focus_category_id")) else None
        with get_conn() as c:
            c.execute("""UPDATE weekly_tasks SET focus_category_id=?,is_urgent=?,has_kpi_or_risk=?,quadrant=?,updated_at=?
                WHERE id=? AND classification_locked=0""",
                (int(new_focus) if new_focus else None, int(urgent), int(has_kpi), new_q, wp._now(), int(task_id)))
            c.execute("""INSERT INTO weekly_classification_changes(
                task_id,plan_id,user_id,actor_user_id,old_quadrant,new_quadrant,
                old_focus_category_id,new_focus_category_id,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (int(task_id), int(plan_id), int(plan["user_id"]), int(u["id"]), old_q, new_q,
                 old_focus, int(new_focus) if new_focus else None, wp._now()))
            change_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.commit()
        wp._task_log(get_conn, int(task_id), int(u["id"]), "quadrant", old_q, new_q, "Lãnh đạo điều chỉnh phân loại")
        wp._log(get_conn, int(u["id"]), "LEADER_RECLASSIFY", "weekly_task", task_id,
                f"user_id={int(plan['user_id'])};{old_q}->{new_q};change_id={change_id}")
        st.rerun()


def _install_due_driven_overrides():
    # Existing V2–V4 flows resolve these functions dynamically, so a narrow
    # override preserves the stable workflow while fixing duplicated input.
    wp._add_task_form = _add_task_form_due_driven
    v3._draft_editor = _draft_editor_due_driven
    v2._leader_reclass = _leader_reclass_due_driven


def _notify_once(get_conn: Callable, user_id: int, event_key: str, event_type: str,
                 title: str, message: str, plan_id=None, task_id=None):
    with get_conn() as c:
        c.execute("""INSERT OR IGNORE INTO weekly_notifications(
            user_id,event_key,event_type,title,message,plan_id,task_id,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (int(user_id), str(event_key), str(event_type), str(title), str(message),
             int(plan_id) if plan_id else None, int(task_id) if task_id else None, wp._now()))
        c.commit()


def _generate_in_app_notifications(get_conn: Callable, u):
    uid = int(u["id"]); role = str(u.get("role") or "")
    year, week, monday, sunday = wp._iso_week()
    now = datetime.now(); weekday = now.weekday(); hour = now.hour + now.minute / 60.0

    if wp._is_officer(u) or wp._is_leader(u):
        plan = wp._get_or_create_plan(get_conn, uid, year, week, monday, sunday)
        status = str(plan.get("status") or "")
        if status in {"DRAFT", "RETURNED"} and weekday == 4 and hour >= 16:
            _notify_once(get_conn, uid, f"plan_friday:{uid}:{year}:{week}", "PLAN_REMINDER",
                         "Nhắc lập kế hoạch tuần", "Hãy chuẩn bị kế hoạch cho tuần kế tiếp.", plan["id"])
        if status in {"DRAFT", "RETURNED"} and weekday == 0 and hour >= 8:
            _notify_once(get_conn, uid, f"plan_monday8:{uid}:{year}:{week}", "PLAN_REMINDER",
                         "Nhắc nộp kế hoạch", "Hãy hoàn thiện và nộp kế hoạch tuần trước 09:00.", plan["id"])
        if status in {"DRAFT", "RETURNED"} and weekday == 0 and hour >= 9.5:
            _notify_once(get_conn, uid, f"not_submitted:{uid}:{year}:{week}", "NOT_SUBMITTED",
                         "Kế hoạch chưa được nộp", "Kế hoạch tuần hiện vẫn chưa được nộp cho Lãnh đạo phòng.", plan["id"])
        if status == "RETURNED":
            _notify_once(get_conn, uid, f"returned:{plan['id']}:{plan.get('updated_at')}", "RETURNED",
                         "Kế hoạch bị trả lại", f"Lý do: {plan.get('return_reason') or '—'}", plan["id"])
        if status == "APPROVED" and weekday == 4 and hour >= 14:
            _notify_once(get_conn, uid, f"close_friday:{uid}:{year}:{week}", "CLOSE_REMINDER",
                         "Nhắc chốt tuần", "Hãy cập nhật kết quả thực tế và chốt tuần trước 17:00.", plan["id"])
        if status == "REVIEWED":
            _notify_once(get_conn, uid, f"reviewed:{plan['id']}:{plan.get('reviewed_at')}", "WEEK_RESULT",
                         "Kết quả tuần đã có", "Lãnh đạo phòng đã hoàn tất nhận xét và chấm điểm tuần.", plan["id"])

        tasks = wp._tasks_df(get_conn, int(plan["id"]))
        if hour >= 8 and not tasks.empty:
            tomorrow = date.today() + timedelta(days=1)
            for _, r in tasks.iterrows():
                if str(r.get("status")) in {"COMPLETED", "CANCELLED"}:
                    continue
                try:
                    due = pd.to_datetime(r.get("due_date")).date()
                except Exception:
                    continue
                if due == tomorrow:
                    _notify_once(get_conn, uid, f"due_tomorrow:{int(r['id'])}:{due}", "DUE_SOON",
                                 "Công việc đến hạn ngày mai", str(r.get("title") or ""), plan["id"], r["id"])

        changes = wp._qdf(get_conn, """SELECT c.id,c.old_quadrant,c.new_quadrant,t.title
            FROM weekly_classification_changes c JOIN weekly_tasks t ON t.id=c.task_id
            WHERE c.user_id=? ORDER BY c.id DESC LIMIT 50""", (uid,))
        for _, r in changes.iterrows():
            _notify_once(get_conn, uid, f"reclass:{int(r['id'])}", "RECLASSIFIED",
                         "Phân loại công việc đã được điều chỉnh",
                         f"{r['title']}: {r['old_quadrant']} → {r['new_quadrant']}")

    if wp._is_leader(u):
        staff_plans = wp._qdf(get_conn, """SELECT p.id,p.user_id,p.status,p.submitted_at,p.closed_at,u.full_name
            FROM weekly_plans p JOIN users u ON u.id=p.user_id
            WHERE p.iso_year=? AND p.iso_week=? AND u.active=1
              AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')""", (year, week))
        for _, p in staff_plans.iterrows():
            if str(p["status"]) == "SUBMITTED":
                _notify_once(get_conn, uid, f"waiting_approval:{int(p['id'])}:{p['submitted_at']}", "WAITING_APPROVAL",
                             "Có kế hoạch chờ duyệt", f"{p['full_name']} đã nộp kế hoạch tuần.", p["id"])
            if str(p["status"]) == "CLOSED" and weekday == 0 and hour >= 8:
                _notify_once(get_conn, uid, f"waiting_review:{int(p['id'])}:{year}:{week}", "WAITING_REVIEW",
                             "Kế hoạch chờ nhận xét", f"{p['full_name']} đã chốt tuần và đang chờ nhận xét.", p["id"])
            if str(p["status"]) in {"DRAFT", "RETURNED"} and weekday == 0 and hour >= 9.5:
                _notify_once(get_conn, uid, f"leader_not_submitted:{int(p['id'])}:{year}:{week}", "NOT_SUBMITTED",
                             "Cán bộ chưa nộp kế hoạch", f"{p['full_name']} chưa nộp kế hoạch tuần.", p["id"])


def _notification_center(get_conn: Callable, u):
    uid = int(u["id"])
    unread_df = wp._qdf(get_conn, "SELECT COUNT(*) n FROM weekly_notifications WHERE user_id=? AND read_at IS NULL", (uid,))
    unread = int(unread_df.iloc[0]["n"]) if not unread_df.empty else 0
    with st.expander(f"🔔 Thông báo ({unread} chưa đọc)", expanded=unread > 0):
        items = wp._qdf(get_conn, """SELECT * FROM weekly_notifications WHERE user_id=?
            ORDER BY CASE WHEN read_at IS NULL THEN 0 ELSE 1 END, id DESC LIMIT 30""", (uid,))
        if items.empty:
            st.caption("Chưa có thông báo Kế hoạch tuần.")
            return
        if unread and st.button("✓ Đánh dấu tất cả đã đọc", key="weekly_v6_mark_all_read", use_container_width=True):
            wp._execute(get_conn, "UPDATE weekly_notifications SET read_at=? WHERE user_id=? AND read_at IS NULL", (wp._now(), uid))
            st.rerun()
        for _, r in items.iterrows():
            css = "weekly-notification" + (" read" if pd.notna(r.get("read_at")) else "")
            st.html(f'<div class="{css}"><div class="nt">{html.escape(str(r["title"]))}</div><div class="nm">{html.escape(str(r["message"]))}</div><div class="ntime">{html.escape(str(r["created_at"]))}</div></div>')


def _room_alerts(get_conn: Callable):
    year, week, _, _ = wp._iso_week()
    staff = wp._qdf(get_conn, """SELECT u.full_name,p.id plan_id,p.status
        FROM users u LEFT JOIN weekly_plans p ON p.user_id=u.id AND p.iso_year=? AND p.iso_week=?
        WHERE u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') ORDER BY u.full_name""", (year, week))
    no_submit = staff[staff["status"].isna() | staff["status"].isin(["DRAFT", "RETURNED"])] if not staff.empty else staff
    waiting = staff[staff["status"].eq("SUBMITTED")] if not staff.empty else staff
    overdue = wp._qdf(get_conn, """SELECT u.full_name,t.title,t.due_date,t.quadrant
        FROM weekly_tasks t JOIN weekly_plans p ON p.id=t.plan_id JOIN users u ON u.id=p.user_id
        WHERE p.iso_year=? AND p.iso_week=? AND u.active=1
          AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
          AND t.status NOT IN ('COMPLETED','CANCELLED')
          AND t.due_date IS NOT NULL AND julianday(date('now'))-julianday(date(t.due_date))>3
        ORDER BY t.due_date""", (year, week))
    if no_submit.empty and waiting.empty and overdue.empty:
        st.success("Không có cảnh báo phòng cần xử lý.")
        return
    if not no_submit.empty:
        st.warning("Chưa nộp kế hoạch: " + ", ".join(no_submit["full_name"].astype(str).tolist()))
    if not waiting.empty:
        st.warning("Kế hoạch chờ duyệt: " + ", ".join(waiting["full_name"].astype(str).tolist()))
    if not overdue.empty:
        st.error("Công việc quá hạn trên 3 ngày: " + "; ".join((overdue["full_name"].astype(str)+" — "+overdue["title"].astype(str)).tolist()[:8]))


def _focus_staff_matrix(get_conn: Callable):
    since = (date.today() - timedelta(days=56)).isoformat()
    df = wp._qdf(get_conn, """SELECT f.code||' — '||f.name focus,u.full_name,
        COALESCE(SUM(t.actual_hours),0) actual_hours
        FROM weekly_focus_categories f
        CROSS JOIN users u
        LEFT JOIN weekly_tasks t ON t.focus_category_id=f.id
        LEFT JOIN weekly_plans p ON p.id=t.plan_id AND p.user_id=u.id AND date(p.start_date)>=date(?)
        WHERE f.scope_key='KHDN' AND f.year=? AND f.status='ACTIVE'
          AND u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
        GROUP BY f.id,f.code,f.name,u.id,u.full_name
        ORDER BY f.display_order,f.code,u.full_name""", (since, date.today().year))
    if df.empty:
        return
    pivot = df.pivot(index="focus", columns="full_name", values="actual_hours").fillna(0.0)
    show = pivot.reset_index().rename(columns={"focus": "Trọng tâm Q2"})
    for c in show.columns[1:]:
        show[c] = pd.to_numeric(show[c], errors="coerce").fillna(0).map(lambda x: f"{float(x):.1f}h")
    v2._html_table(show, 430)


def _reclass_counts(get_conn: Callable):
    since = (date.today() - timedelta(days=56)).isoformat()
    df = wp._qdf(get_conn, """SELECT u.full_name,
        COUNT(*) changes,
        SUM(CASE WHEN c.old_quadrant='Q2' AND c.new_quadrant<>'Q2' THEN 1 ELSE 0 END) removed_q2
        FROM weekly_classification_changes c JOIN users u ON u.id=c.user_id
        WHERE date(c.created_at)>=date(?) AND u.active=1
          AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
        GROUP BY u.id,u.full_name ORDER BY changes DESC,u.full_name""", (since,))
    if not df.empty:
        v2._html_table(df.rename(columns={"full_name":"Cán bộ","changes":"Số lần điều chỉnh","removed_q2":"Số lần gỡ Q2"}), 350)


def _limitation_keywords(get_conn: Callable):
    since = (date.today() - timedelta(days=56)).isoformat()
    df = wp._qdf(get_conn, """SELECT r.limitations FROM weekly_reviews r
        JOIN weekly_plans p ON p.id=r.plan_id JOIN users u ON u.id=p.user_id
        WHERE date(p.start_date)>=date(?) AND u.active=1
          AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH') AND r.limitations IS NOT NULL""", (since,))
    if df.empty:
        st.caption("Chưa có đủ nội dung 'Tồn tại, hạn chế' để tổng hợp."); return
    stop = {"và","có","còn","chưa","việc","công","trong","của","cho","được","cần","một","các","với","do","đã","là","ở","từ","theo","không","nên","về","để","này","tuần"}
    words = []
    for text in df["limitations"].fillna("").astype(str):
        words.extend(w for w in re.findall(r"[A-Za-zÀ-ỹĐđ]{3,}", text.lower()) if w not in stop)
    counts = Counter(words).most_common(12)
    if not counts:
        st.caption("Chưa xác định được từ khóa lặp lại."); return
    pills = "".join(f'<span class="weekly-badge" style="margin:3px">{html.escape(w)} · {n}</span>' for w,n in counts)
    st.html(f'<div class="weekly-dashboard-card">{pills}</div>')


def _room_dashboard_enhanced(get_conn: Callable):
    st.markdown("### Tổng quan phòng · tuần hiện tại")
    summary = v5._room_current_summary(get_conn)
    if summary.empty:
        st.info("Chưa có dữ liệu cán bộ."); return
    year, week, _, _ = wp._iso_week()
    summary = summary.copy()
    summary["Trạng thái"] = summary.apply(lambda r: "Chưa lập" if pd.isna(r.get("plan_id")) else wp.PLAN_STATUS_LABELS.get(str(r.get("status") or ""), str(r.get("status") or "")), axis=1)
    summary["Hoàn thành"] = summary.apply(lambda r: f"{int(r.get('done_tasks') or 0)}/{int(r.get('total_tasks') or 0)}", axis=1)
    summary["Q2"] = summary.apply(lambda r: f"{100.0*float(r.get('q2_hours') or 0)/float(r.get('actual_hours')):.1f}%" if float(r.get("actual_hours") or 0)>0 else "0.0%", axis=1)
    summary["Điểm tuần"] = summary["week_score"].map(lambda x: f"{float(x):.1f}" if pd.notna(x) else "—")
    summary["Xếp loại"] = summary["grade"].fillna("—")
    v2._html_table(summary[["full_name","role","Trạng thái","Hoàn thành","Q2","Điểm tuần","Xếp loại"]].rename(columns={"full_name":"Cán bộ","role":"Vai trò"}), 450)

    scored = summary[pd.to_numeric(summary["week_score"], errors="coerce").notna()].copy()
    if not scored.empty:
        st.markdown("### Điểm tuần theo cán bộ")
        avg = float(pd.to_numeric(scored["week_score"], errors="coerce").mean())
        fig = go.Figure()
        fig.add_trace(go.Bar(x=scored["full_name"].astype(str), y=pd.to_numeric(scored["week_score"], errors="coerce"), name="Điểm tuần", marker_color="#62D7AF"))
        fig.add_trace(go.Scatter(x=scored["full_name"].astype(str), y=[avg]*len(scored), name=f"TB phòng {avg:.1f}", mode="lines", line=dict(color="#F4B41A", width=2, dash="dash")))
        fig.update_layout(height=330, margin=dict(l=20,r=20,t=25,b=50), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"), legend=dict(orientation="h"), yaxis=dict(range=[0,100], title="Điểm"), xaxis=dict(title=""))
        st.plotly_chart(fig, use_container_width=True, key="weekly_v6_room_scores")

    st.markdown("### Cảnh báo cần xử lý")
    _room_alerts(get_conn)

    hist = v3._room_history(get_conn)
    if not hist.empty:
        hist = hist.copy()
        hist["q2_pct"] = hist.apply(lambda r: 100.0*float(r.get("q2_hours") or 0)/float(r.get("actual_hours")) if float(r.get("actual_hours") or 0)>0 else 0.0, axis=1)
        hist["Tuần"] = hist.apply(lambda r: f"{int(r['iso_week'])}/{int(r['iso_year'])}", axis=1)
        pivot = hist.pivot_table(index="full_name", columns="Tuần", values="q2_pct", aggfunc="mean", fill_value=0)
        if not pivot.empty:
            st.markdown("### Bản đồ nhiệt chỉ số Q2 · 8 tuần")
            heat = go.Figure(data=go.Heatmap(z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(), colorscale=[[0,"#17312F"],[0.5,"#0B7F75"],[1,"#F4B41A"]], zmin=0, zmax=100, colorbar=dict(title="Q2 %"), text=[[f"{v:.1f}%" for v in row] for row in pivot.values], texttemplate="%{text}"))
            heat.update_layout(height=max(280, 45*len(pivot)+120), margin=dict(l=30,r=20,t=25,b=40), paper_bgcolor="#0E1F1E", plot_bgcolor="#17312F", font=dict(color="#F4FFFC"))
            st.plotly_chart(heat, use_container_width=True, key="weekly_v6_q2_heatmap")

    st.markdown("### Ma trận trọng tâm Q2 × cán bộ · 8 tuần")
    _focus_staff_matrix(get_conn)
    st.markdown("### Điều chỉnh phân loại · 8 tuần")
    _reclass_counts(get_conn)
    st.markdown("### Từ khóa tồn tại lặp lại · 8 tuần")
    _limitation_keywords(get_conn)

    with st.expander("🔎 Xem chi tiết công việc theo cán bộ", expanded=False):
        choices = summary["user_id"].astype(int).tolist()
        if choices:
            who = st.selectbox("Cán bộ", choices, format_func=lambda x: str(summary[summary["user_id"].eq(int(x))].iloc[0]["full_name"]), key="weekly_v6_room_drill_staff")
            plan_row = summary[summary["user_id"].eq(int(who))].iloc[0]
            if pd.isna(plan_row.get("plan_id")):
                st.info("Cán bộ này chưa có kế hoạch tuần hiện tại.")
            else:
                tasks = wp._tasks_df(get_conn, int(plan_row["plan_id"]))
                for _, r in tasks.iterrows():
                    wp._render_task_card(r)


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    if not (wp._is_officer(u) or wp._is_leader(u)):
        st.error("Bạn không có quyền truy cập Kế hoạch tuần.")
        return

    _init_v6_schema(get_conn)
    _install_due_driven_overrides()
    v4._apply_score_fallbacks(get_conn)
    wp._inject_weekly_css(); v2._inject_css(); _inject_v6_css()
    _generate_in_app_notifications(get_conn, u)
    page_title("Kế hoạch tuần", "Quản trị ưu tiên theo Q1–Q4; hệ thống tự phân loại, cán bộ không tự chọn góc phần tư.")
    _notification_center(get_conn, u)
    v2._glossary()

    if wp._is_leader(u):
        options = [("mine","📅 Kế hoạch của tôi"),("review","✅ Duyệt & đánh giá"),("focus","🎯 Trọng tâm Q2"),("room","📊 Tổng quan phòng"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    else:
        options = [("mine","📅 Tuần của tôi"),("history","📈 8 tuần"),("export","⬇️ Xuất báo cáo")]
    if pill_nav:
        view = pill_nav("weekly_plan_view", options, default="mine", prefix="weekly_plan_v6")
    else:
        labels=[x[1] for x in options]; values=[x[0] for x in options]; current=st.session_state.get("weekly_plan_view","mine")
        idx=values.index(current) if current in values else 0
        selected=st.radio("Chế độ", labels, index=idx, horizontal=True, label_visibility="collapsed")
        view=dict((label,value) for value,label in options)[selected]; st.session_state["weekly_plan_view"]=view

    if view == "mine": v4._my_plan(get_conn, u)
    elif view == "review" and wp._is_leader(u): v4._leader_review(get_conn, u)
    elif view == "focus" and wp._is_leader(u): v4._focus_maintenance(get_conn, u)
    elif view == "room" and wp._is_leader(u): _room_dashboard_enhanced(get_conn)
    elif view == "history": v2._history_view(get_conn, u)
    elif view == "export": v5._export_view(get_conn, u)
