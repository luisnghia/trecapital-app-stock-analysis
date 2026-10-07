"""Deliver new Customer Work assignments from the committed action journal.

Runs in the existing background notification worker, never during typing/save.
The recipient is the active assigned owner, not a department-wide audience.
Inbox creation, delivery queue and cursor advance commit together.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from khdn_apps import notifications as notify, weekly_push as push

LOGGER = logging.getLogger("khdn_customer_work_notifications")
EVENT_KEY = "customer_work_assignment"
CURSOR = "customer_work_assignment_last_action_id"


def _ready(c):
    tables = {str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"users", "customers", "customer_work_cases", "case_actions"} <= tables


def ensure_schema(db_path: str | Path) -> bool:
    notify.ensure_schema(db_path)
    with notify._connect(db_path) as c:
        if not _ready(c):
            return False
        c.execute("BEGIN IMMEDIATE")
        push.ensure_tables(c)
        if not notify._state_get(c, CURSOR):
            last = int(c.execute("SELECT COALESCE(MAX(id),0) FROM case_actions").fetchone()[0])
            notify._state_set(c, CURSOR, str(last))
            LOGGER.info("CUSTOMER_WORK_NOTIFICATION_READY cursor=%s historical_messages=0", last)
        c.commit()
    return True


def can_view_case(c, user_id: int, case_id: int) -> bool:
    if not _ready(c):
        return False
    row = c.execute("""SELECT w.owner_user_id,u.role,u.is_admin,u.active
        FROM customer_work_cases w JOIN users u ON u.id=? WHERE w.id=?""",
        (int(user_id), int(case_id))).fetchone()
    return bool(row and row["active"] and
                (int(row["owner_user_id"]) == int(user_id) or row["is_admin"] or row["role"] == "Lãnh đạo phòng"))


def process_actions(db_path: str | Path, limit: int = 100) -> int:
    if not ensure_schema(db_path):
        return 0
    created = 0
    with notify._connect(db_path) as c:
        c.execute("BEGIN IMMEDIATE")
        last = int(notify._state_get(c, CURSOR, "0"))
        rows = c.execute("SELECT * FROM case_actions WHERE id>? ORDER BY id LIMIT ?",
                         (last, max(1, min(int(limit), 1000)))).fetchall()
        for action in rows:
            if str(action["action"]) == "CREATE":
                row = c.execute("""SELECT w.*,u.active,cu.customer_name,a.full_name actor_name
                    FROM customer_work_cases w JOIN users u ON u.id=w.owner_user_id
                    JOIN customers cu ON cu.id=w.customer_id
                    LEFT JOIN users a ON a.id=? WHERE w.id=?""",
                    (int(action["actor_user_id"]), int(action["case_id"]))).fetchone()
                try:
                    detail = json.loads(action["detail"] or "{}")
                    owner = int(detail.get("owner_user_id") or (row["owner_user_id"] if row else 0))
                except (ValueError, TypeError, AttributeError):
                    owner = 0
                if (row and row["active"] and row["status"] not in {"CANCELLED", "COMPLETED"}
                        and owner == int(row["owner_user_id"]) and owner != int(action["actor_user_id"])):
                    body = f"{row['case_code']} · {notify._short(row['customer_name'])} · {notify._short(row['title'])}"
                    body += f". Người giao: {notify._short(row['actor_name'] or '—', 80)}"
                    if row["expected_complete_at"]:
                        body += f". Dự kiến hoàn thành: {row['expected_complete_at']}"
                    nid = push.enqueue(c, owner, "📥 Công việc khách hàng mới được giao", body,
                        event_key=EVENT_KEY, event_code="CUSTOMER_WORK_ASSIGNED",
                        source_action_id=int(action["id"]), customer_work_case_id=int(row["id"]))
                    if nid:
                        created += 1
                        LOGGER.info("CUSTOMER_WORK_NOTIFICATION_ENQUEUED case_id=%s user_id=%s notification_id=%s",
                                    row["id"], owner, nid)
            notify._state_set(c, CURSOR, str(int(action["id"])))
        c.commit()
    return created


def process_once(db_path: str | Path) -> int:
    created = process_actions(db_path)
    # Dedicated event filter preserves the timing/ownership of the weekly worker.
    push.flush(db_path, limit=100, event_key=EVENT_KEY)
    return created
