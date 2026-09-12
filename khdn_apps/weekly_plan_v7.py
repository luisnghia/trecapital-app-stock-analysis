"""Weekly Plan V7 hardening patch.

Corrects Friday/leader reminder generation and the Q2 focus matrix aggregation
without disturbing the stable V6 workflow.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Optional

import pandas as pd

from khdn_apps import weekly_plan as wp
from khdn_apps import weekly_plan_v2 as v2
from khdn_apps import weekly_plan_v6 as v6


def _generate_in_app_notifications(get_conn: Callable, u):
    uid = int(u["id"])
    year, week, monday, sunday = wp._iso_week()
    now = datetime.now(); weekday = now.weekday(); hour = now.hour + now.minute / 60.0

    if wp._is_officer(u) or wp._is_leader(u):
        plan = wp._get_or_create_plan(get_conn, uid, year, week, monday, sunday)
        status = str(plan.get("status") or "")

        # Friday 16:00 is a reminder to prepare the NEXT week's plan, so it must
        # not depend on the current plan still being DRAFT.
        if weekday == 4 and hour >= 16:
            next_monday = monday + timedelta(days=7)
            ni = next_monday.isocalendar()
            v6._notify_once(get_conn, uid, f"plan_friday_next:{uid}:{int(ni.year)}:{int(ni.week)}", "PLAN_REMINDER",
                            "Nhắc lập kế hoạch tuần", f"Hãy chuẩn bị kế hoạch cho tuần {int(ni.week)}/{int(ni.year)}.")

        if status in {"DRAFT", "RETURNED"} and weekday == 0 and hour >= 8:
            v6._notify_once(get_conn, uid, f"plan_monday8:{uid}:{year}:{week}", "PLAN_REMINDER",
                            "Nhắc nộp kế hoạch", "Hãy hoàn thiện và nộp kế hoạch tuần trước 09:00.", plan["id"])
        if status in {"DRAFT", "RETURNED"} and weekday == 0 and hour >= 9.5:
            v6._notify_once(get_conn, uid, f"not_submitted:{uid}:{year}:{week}", "NOT_SUBMITTED",
                            "Kế hoạch chưa được nộp", "Kế hoạch tuần hiện vẫn chưa được nộp cho Lãnh đạo phòng.", plan["id"])
        if status == "RETURNED":
            v6._notify_once(get_conn, uid, f"returned:{plan['id']}:{plan.get('updated_at')}", "RETURNED",
                            "Kế hoạch bị trả lại", f"Lý do: {plan.get('return_reason') or '—'}", plan["id"])
        if status == "APPROVED" and weekday == 4 and hour >= 14:
            v6._notify_once(get_conn, uid, f"close_friday:{uid}:{year}:{week}", "CLOSE_REMINDER",
                            "Nhắc chốt tuần", "Hãy cập nhật kết quả thực tế và chốt tuần trước 17:00.", plan["id"])
        if status == "REVIEWED":
            v6._notify_once(get_conn, uid, f"reviewed:{plan['id']}:{plan.get('reviewed_at')}", "WEEK_RESULT",
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
                    v6._notify_once(get_conn, uid, f"due_tomorrow:{int(r['id'])}:{due}", "DUE_SOON",
                                    "Công việc đến hạn ngày mai", str(r.get("title") or ""), plan["id"], r["id"])

        changes = wp._qdf(get_conn, """SELECT c.id,c.old_quadrant,c.new_quadrant,t.title
            FROM weekly_classification_changes c JOIN weekly_tasks t ON t.id=c.task_id
            WHERE c.user_id=? ORDER BY c.id DESC LIMIT 50""", (uid,))
        for _, r in changes.iterrows():
            v6._notify_once(get_conn, uid, f"reclass:{int(r['id'])}", "RECLASSIFIED",
                            "Phân loại công việc đã được điều chỉnh",
                            f"{r['title']}: {r['old_quadrant']} → {r['new_quadrant']}")

    if wp._is_leader(u):
        # LEFT JOIN includes staff who have never opened the page / have no plan.
        staff = wp._qdf(get_conn, """SELECT u.id user_id,u.full_name,p.id plan_id,p.status,p.submitted_at,p.closed_at
            FROM users u LEFT JOIN weekly_plans p
              ON p.user_id=u.id AND p.iso_year=? AND p.iso_week=?
            WHERE u.active=1 AND u.role IN ('Cán bộ hỗ trợ','Cán bộ QLKH')
            ORDER BY u.full_name""", (year, week))
        for _, p in staff.iterrows():
            plan_id = int(p["plan_id"]) if pd.notna(p.get("plan_id")) else None
            status = str(p.get("status") or "") if plan_id else ""
            if status == "SUBMITTED":
                v6._notify_once(get_conn, uid, f"waiting_approval:{plan_id}:{p.get('submitted_at')}", "WAITING_APPROVAL",
                                "Có kế hoạch chờ duyệt", f"{p['full_name']} đã nộp kế hoạch tuần.", plan_id)
            if status == "CLOSED" and weekday == 0 and hour >= 8:
                v6._notify_once(get_conn, uid, f"waiting_review:{plan_id}:{year}:{week}", "WAITING_REVIEW",
                                "Kế hoạch chờ nhận xét", f"{p['full_name']} đã chốt tuần và đang chờ nhận xét.", plan_id)
            if weekday == 0 and hour >= 9.5 and (not plan_id or status in {"DRAFT", "RETURNED"}):
                identity = plan_id if plan_id else f"user{int(p['user_id'])}"
                v6._notify_once(get_conn, uid, f"leader_not_submitted:{identity}:{year}:{week}", "NOT_SUBMITTED",
                                "Cán bộ chưa nộp kế hoạch", f"{p['full_name']} chưa nộp kế hoạch tuần.", plan_id)


def _focus_staff_matrix(get_conn: Callable):
    since = (date.today() - timedelta(days=56)).isoformat()
    df = wp._qdf(get_conn, """SELECT f.code||' — '||f.name focus,u.full_name,
        COALESCE(SUM(CASE WHEN p.id IS NOT NULL THEN t.actual_hours ELSE 0 END),0) actual_hours
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


def weekly_plan_page(u, get_conn: Callable, page_title: Callable, pill_nav: Optional[Callable] = None):
    # V6 resolves these names at render time; patch only corrected helpers.
    v6._generate_in_app_notifications = _generate_in_app_notifications
    v6._focus_staff_matrix = _focus_staff_matrix
    return v6.weekly_plan_page(u, get_conn, page_title, pill_nav)
