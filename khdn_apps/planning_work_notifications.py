"""Fast planning activity delivery from committed business journals.

Runs in the existing two-second background worker. No polling or network calls
are added to input forms. A journal cursor, inbox rows and push jobs commit
together, so rollback/restart cannot lose or repeat an activity notification.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging

from khdn_apps import notifications as notify, weekly_push as push
from khdn_apps import weekly_plan_notifications as work
from khdn_apps import weekly_phase2_notifications as cycle

LOGGER = logging.getLogger("khdn_planning_work_notifications")
WEEKLY_CURSOR = "planning_weekly_action_notification_cursor_v1"
CASE_CURSOR = "planning_case_action_notification_cursor_v1"
CASE_EVENT = "customer_work_update"
WEEKLY_ACTIONS = {
    "DRAFT_EDIT": "chỉnh sửa công việc",
    "MANAGER_EDIT_PHASE3": "điều chỉnh kế hoạch",
    "CLASSIFICATION_CHANGE": "điều chỉnh phân loại",
    "STATUS": "cập nhật trạng thái",
    "EXEC_UPDATE": "cập nhật kết quả thực hiện",
    "EXEC_UPDATE_PHASE2": "cập nhật kết quả thực hiện",
    "EXEC_UPDATE_PHASE3": "cập nhật kết quả thực hiện",
    "RESCHEDULE": "dời lịch thực hiện",
    "RESCHEDULE_REQUEST": "đề nghị dời lịch",
    "RESCHEDULE_APPROVE": "phê duyệt dời lịch",
    "RESCHEDULE_REJECT": "từ chối đề nghị dời lịch",
    "CANCEL_REQUEST": "đề nghị hủy công việc",
    "CANCEL_APPROVE": "phê duyệt hủy công việc",
    "CANCEL_REJECT": "từ chối đề nghị hủy",
}
CASE_ACTIONS = {
    "CREATE": "thêm công việc khách hàng",
    "PLAN_APPROVE": "phê duyệt kế hoạch",
    "PLAN_REJECT": "trả lại kế hoạch",
    "STAGE_CHANGE": "cập nhật mục công việc",
    "ISSUE_OPEN": "ghi nhận vướng mắc",
    "ISSUE_RESOLVE": "xử lý vướng mắc",
    "RESCHEDULE_REQUEST": "đề nghị/điều chỉnh hạn hoàn thành",
    "RESCHEDULE_DECISION": "xử lý đề nghị dời hạn",
    "PRIORITY_SET": "điều chỉnh công việc trọng tâm",
    "CONTACT_UPDATE_P10": "cập nhật thông tin liên hệ",
    "NOTE_EDIT": "cập nhật ghi chú",
    "CANCEL_REQUEST_P12": "đề nghị hủy công việc",
    "CANCEL_APPROVE_P12": "phê duyệt hủy công việc",
    "CANCEL_REJECT_P12": "từ chối đề nghị hủy",
}


def _tables(c):
    return {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def ensure_schema(db_path):
    notify.ensure_schema(db_path)
    with notify._connect(db_path) as c:
        tables = _tables(c)
        sources = []
        if {"users", "weekly_plans", "weekly_plan_items", "weekly_plan_actions"} <= tables:
            if "controller_user_id" in work._columns(c, "weekly_plan_items"):
                sources.append((WEEKLY_CURSOR, "weekly_plan_actions"))
        if {"users", "customers", "customer_work_cases", "case_actions"} <= tables:
            sources.append((CASE_CURSOR, "case_actions"))
        missing = [(cursor, table) for cursor, table in sources if notify._state_get(c, cursor, None) is None]
        if not missing:
            return bool(sources)
        c.execute("BEGIN IMMEDIATE")
        push.ensure_tables(c)
        for cursor, table in missing:
            if notify._state_get(c, cursor, None) is None:
                last = int(c.execute(f"SELECT COALESCE(MAX(id),0) FROM {table}").fetchone()[0])
                notify._state_set(c, cursor, str(last))
                LOGGER.info("PLANNING_ACTIVITY_READY source=%s cursor=%s historical_messages=0", table, last)
        c.commit()
    return bool(sources)


def weekly_context(c, user_id, item_id):
    if not {"users", "weekly_plans", "weekly_plan_items"} <= _tables(c):
        return None
    row = c.execute("""SELECT w.*,p.week_start,u.role viewer_role,u.is_admin viewer_admin,u.active viewer_active
        FROM weekly_plan_items w JOIN weekly_plans p ON p.id=w.plan_id
        JOIN users u ON u.id=? WHERE w.id=?""", (int(user_id), int(item_id))).fetchone()
    if not row or not row["viewer_active"]:
        return None
    if int(row["user_id"]) != int(user_id) and not row["viewer_admin"] and row["viewer_role"] != "Lãnh đạo phòng":
        return None
    return dict(row)


def _detail(action):
    try:
        value = json.loads(action["detail"] or "{}")
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _changed(action):
    detail = _detail(action)
    if isinstance(detail.get("before"), dict) and isinstance(detail.get("after"), dict):
        before, after = detail["before"], detail["after"]
        return any(before.get(k) != after.get(k) for k in set(before) | set(after) if k != "updated_at")
    if action["action"] == "CLASSIFICATION_CHANGE":
        return detail.get("old_q") is not None and (
            detail.get("old_q") != detail.get("new_q") or detail.get("old_focus") != detail.get("new_focus"))
    if action["action"] == "NOTE_EDIT":
        return str(detail.get("old_note") or "").strip() != str(detail.get("new_note") or "").strip()
    return True


def _recipients(c, row, *, case=False):
    owner = int(row["owner_user_id"] if case else row["user_id"])
    controller = int(row.get("controller_user_id") or cycle._leader_for_staff(c, owner) or 0)
    return {owner} | set(cycle._manager_recipients(c, controller))


def _date(v):
    try:
        return datetime.fromisoformat(str(v)[:19]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(v or "—")[:19]


def process_actions(db_path, limit=250):
    if not ensure_schema(db_path):
        return 0
    created = 0
    with notify._connect(db_path) as c:
        c.execute("BEGIN IMMEDIATE")
        for cursor, table, is_case, labels in (
            (WEEKLY_CURSOR, "weekly_plan_actions", False, WEEKLY_ACTIONS),
            (CASE_CURSOR, "case_actions", True, CASE_ACTIONS),
        ):
            last = notify._state_get(c, cursor, None)
            if last is None:
                continue
            actions = c.execute(f"SELECT * FROM {table} WHERE id>? ORDER BY id LIMIT ?",
                                (int(last), max(1, min(int(limit), 1000)))).fetchall()
            for action in actions:
                label = labels.get(action["action"])
                target_id = action["case_id"] if is_case else action["item_id"]
                row = None
                if label and target_id and _changed(action):
                    if is_case:
                        found = c.execute("""SELECT w.*,cu.customer_name FROM customer_work_cases w
                            JOIN customers cu ON cu.id=w.customer_id WHERE w.id=?""", (int(target_id),)).fetchone()
                        row = dict(found) if found else None
                    else:
                        found = c.execute("SELECT * FROM weekly_plan_items WHERE id=?", (int(target_id),)).fetchone()
                        row = dict(found) if found else None
                if row:
                    recipients = _recipients(c, row, case=is_case) - {0}
                    if is_case and action["action"] == "CREATE":
                        if row["status"] in {"COMPLETED", "CANCELLED"}:
                            recipients.clear()
                        if int(row["owner_user_id"]) != int(action["actor_user_id"]):
                            # The existing assignment category already owns this recipient.
                            recipients.discard(int(row["owner_user_id"]))
                    actor = c.execute("SELECT full_name FROM users WHERE id=?", (int(action["actor_user_id"]),)).fetchone()
                    name = actor[0] if actor else "Người dùng"
                    customer = row.get("customer_name") if is_case else row.get("customer_text")
                    due = row.get("expected_complete_at") if is_case else row.get("expected_complete_date")
                    title = "🆕 Công việc khách hàng mới" if action["action"] == "CREATE" else "📝 Công việc kế hoạch được cập nhật"
                    body = f"{notify._short(row.get('title'), 180)}" + (f" · {notify._short(customer, 100)}" if customer else "")
                    body += f". {notify._short(name, 80)} đã {label}."
                    if due:
                        body += f" Hạn hoàn thành: {_date(due)}."
                    for uid in sorted(recipients):
                        nid = push.enqueue(c, uid, title, body,
                            event_key=CASE_EVENT if is_case else "weekly_update",
                            event_code=f"WORK_UPDATE_{action['action']}",
                            source_action_id=int(action["id"]),
                            customer_work_case_id=int(target_id) if is_case else None,
                            weekly_plan_item_id=None if is_case else int(target_id))
                        if nid:
                            created += 1
                            LOGGER.info("PLANNING_ACTIVITY_ENQUEUED source=%s action_id=%s target_id=%s user_id=%s notification_id=%s",
                                        table, action["id"], target_id, uid, nid)
                notify._state_set(c, cursor, str(int(action["id"])))
        c.commit()
    return created


def process_once(db_path):
    created = process_actions(db_path)
    created += len(work.process_new_work(db_path))
    # Also flush policy decisions already queued inside their business transaction.
    push.flush(db_path, limit=80, event_key="weekly_update")
    push.flush(db_path, limit=80, event_key=CASE_EVENT)
    return created
