"""Notification worker for Weekly Plan work.

This worker complements the existing task-action notification engine without
changing the legacy task workflow. It creates durable in-app + Web Push alerts
for newly added weekly work and approaching/overdue completion dates.
"""
from __future__ import annotations

from datetime import date, datetime
import logging
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any

from khdn_apps import notifications as notify
from khdn_apps import weekly_push

LOGGER = logging.getLogger("khdn_weekly_notifications")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _now() -> str:
    return weekly_push.local_now().strftime("%Y-%m-%d %H:%M:%S")


def _table_exists(c: sqlite3.Connection, name: str) -> bool:
    return bool(c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone())


def _columns(c: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def _pref_enabled(c: sqlite3.Connection, user_id: int, event_key: str) -> bool:
    if not _table_exists(c, "notification_preferences"):
        return True
    row = c.execute(
        "SELECT enabled FROM notification_preferences WHERE user_id=? AND event_key=?",
        (int(user_id), str(event_key)),
    ).fetchone()
    return True if row is None else bool(row[0])


def _state_get(c: sqlite3.Connection, key: str) -> str | None:
    if not _table_exists(c, "notification_state"):
        return None
    row = c.execute("SELECT value FROM notification_state WHERE key=?", (key,)).fetchone()
    return str(row[0]) if row else None


def _state_set(c: sqlite3.Connection, key: str, value: Any) -> None:
    c.execute(
        """INSERT INTO notification_state(key,value,updated_at) VALUES(?,?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
        (str(key), str(value), _now()),
    )


def ensure_schema(db_path: str | Path) -> bool:
    """Return False until Weekly Plan tables exist; never races core bootstrap."""
    weekly_push.ensure_schema(db_path)
    with _connect(db_path) as c:
        if not _table_exists(c, "weekly_plan_items") or not _table_exists(c, "weekly_plans"):
            return False
        c.execute(
            """CREATE TABLE IF NOT EXISTS weekly_notification_events(
                   item_id INTEGER NOT NULL,
                   user_id INTEGER NOT NULL,
                   event_code TEXT NOT NULL,
                   created_at TEXT NOT NULL,
                   PRIMARY KEY(item_id,user_id,event_code)
               )"""
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_weekly_notification_events_user ON weekly_notification_events(user_id,created_at)"
        )
        c.commit()
    return True


def _insert_notification(c, *, user_id: int, event_key: str, title: str,
                         body: str, event_code: str) -> int | None:
    return weekly_push.enqueue(c, user_id, title, body,
                               event_key=event_key, event_code=event_code)


def _short(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def process_new_work(db_path: str | Path) -> list[int]:
    """Notify the responsible leader for weekly work added after worker baseline."""
    if not ensure_schema(db_path):
        return []
    created: list[int] = []
    with _connect(db_path) as c:
        cols = _columns(c, "weekly_plan_items")
        if "controller_user_id" not in cols:
            return []
        max_id = int(c.execute("SELECT COALESCE(MAX(id),0) FROM weekly_plan_items").fetchone()[0] or 0)
        raw_last = _state_get(c, "last_weekly_item_id")
        if raw_last is None:
            # Establish a no-retroactive-blast baseline on first deployment.
            _state_set(c, "last_weekly_item_id", max_id)
            c.commit()
            return []
        last_id = int(raw_last or 0)
        rows = c.execute(
            """SELECT w.id,w.user_id,w.controller_user_id,w.title,w.customer_text,w.work_date,
                      w.expected_complete_date,w.is_emergent,u.full_name AS owner_name
               FROM weekly_plan_items w
               LEFT JOIN users u ON u.id=w.user_id
               WHERE w.id>? ORDER BY w.id""",
            (last_id,),
        ).fetchall()
        for r in rows:
            iid = int(r["id"])
            leader = int(r["controller_user_id"] or 0)
            owner = int(r["user_id"] or 0)
            if leader > 0 and leader != owner:
                exists = c.execute(
                    "SELECT 1 FROM weekly_notification_events WHERE item_id=? AND user_id=? AND event_code='NEW_WORK'",
                    (iid, leader),
                ).fetchone()
                if not exists:
                    label = "công việc phát sinh" if int(r["is_emergent"] or 0) else "công việc kế hoạch"
                    customer = f" · {r['customer_text']}" if r["customer_text"] else ""
                    due = str(r["expected_complete_date"] or r["work_date"] or "")[:10]
                    body = _short(
                        f"{r['owner_name'] or 'Cán bộ'} thêm {label}: {r['title']}{customer}. Dự kiến hoàn thành {due}."
                    )
                    nid = _insert_notification(
                        c,
                        user_id=leader,
                        event_key="weekly_update",
                        event_code="NEW_WORK",
                        title="🆕 Công việc kế hoạch mới",
                        body=body,
                    )
                    c.execute(
                        "INSERT OR IGNORE INTO weekly_notification_events(item_id,user_id,event_code,created_at) VALUES(?,?,?,?)",
                        (iid, leader, "NEW_WORK", _now()),
                    )
                    if nid:
                        created.append(nid)
            _state_set(c, "last_weekly_item_id", iid)
        c.commit()
    return created


def process_due_work(db_path: str | Path) -> list[int]:
    """One reminder tomorrow, one today, and one overdue alert per recipient/item."""
    if not ensure_schema(db_path):
        return []
    created: list[int] = []
    today = weekly_push.local_now().date()
    with _connect(db_path) as c:
        cols = _columns(c, "weekly_plan_items")
        required = {"expected_complete_date", "controller_user_id"}
        if not required.issubset(cols):
            return []
        rows = c.execute(
            """SELECT w.id,w.user_id,w.controller_user_id,w.title,w.customer_text,w.work_date,
                      w.expected_complete_date,w.status,p.workflow_status,u.full_name AS owner_name
               FROM weekly_plan_items w
               JOIN weekly_plans p ON p.id=w.plan_id
               LEFT JOIN users u ON u.id=w.user_id
               WHERE p.workflow_status='DA_DUYET'
                 AND w.status IN ('PLANNED','IN_PROGRESS')
                 AND w.expected_complete_date IS NOT NULL
                 AND w.expected_complete_date<>''"""
        ).fetchall()
        for r in rows:
            try:
                due = date.fromisoformat(str(r["expected_complete_date"])[:10])
            except Exception:
                continue
            delta = (due - today).days
            if delta > 1:
                continue
            if delta == 1:
                code = "DUE_TOMORROW"
                title = "⏰ Công việc đến hạn ngày mai"
                recipients = [int(r["user_id"])]
            elif delta == 0:
                code = "DUE_TODAY"
                title = "⏰ Công việc đến hạn hôm nay"
                recipients = [int(r["user_id"])]
            else:
                code = "OVERDUE"
                title = "⛔ Công việc đã quá hạn"
                recipients = [int(r["user_id"])]
                leader = int(r["controller_user_id"] or 0)
                if leader and leader not in recipients:
                    recipients.append(leader)
            customer = f" · {r['customer_text']}" if r["customer_text"] else ""
            if delta < 0:
                timing = f"quá hạn {abs(delta)} ngày (hạn {due:%d/%m/%Y})"
            elif delta == 0:
                timing = f"hạn hôm nay {due:%d/%m/%Y}"
            else:
                timing = f"hạn ngày mai {due:%d/%m/%Y}"
            body = _short(f"{r['owner_name'] or 'Cán bộ'} · {r['title']}{customer} · {timing}.")
            for uid in recipients:
                exists = c.execute(
                    "SELECT 1 FROM weekly_notification_events WHERE item_id=? AND user_id=? AND event_code=?",
                    (int(r["id"]), uid, code),
                ).fetchone()
                if exists:
                    continue
                nid = _insert_notification(
                    c,
                    user_id=uid,
                    event_key="weekly_deadline",
                    event_code=code,
                    title=title,
                    body=body,
                )
                c.execute(
                    "INSERT OR IGNORE INTO weekly_notification_events(item_id,user_id,event_code,created_at) VALUES(?,?,?,?)",
                    (int(r["id"]), uid, code, _now()),
                )
                if nid:
                    created.append(nid)
        c.commit()
    return created


def flush_pending_push(db_path: str | Path, limit: int = 80) -> int:
    """The only dispatcher for planning notifications, never operations alerts."""
    return weekly_push.flush(db_path, limit)


def process_once(db_path: str | Path) -> int:
    created = []
    created.extend(process_new_work(db_path))
    created.extend(process_due_work(db_path))
    # Deliver only the planning queue, including policy and cycle reminders.
    flush_pending_push(db_path)
    return len(created)


def worker_loop(db_path: str | Path, stop_event: threading.Event, poll_seconds: float = 60.0) -> None:
    LOGGER.info("WEEKLY_NOTIFICATION_WORKER_START push_configured=%s timezone=Asia/Ho_Chi_Minh", notify.push_available())
    schema_ready = False
    last_schema_notice = 0.0
    while not stop_event.is_set():
        try:
            if not ensure_schema(db_path):
                if time.monotonic() - last_schema_notice >= 60:
                    LOGGER.info("WEEKLY_NOTIFICATION_WAIT_SCHEMA")
                    last_schema_notice = time.monotonic()
            else:
                if not schema_ready:
                    LOGGER.info("WEEKLY_NOTIFICATION_SCHEMA_READY")
                    schema_ready = True
                process_once(db_path)
        except sqlite3.Error:
            # Core/weekly schemas may still be bootstrapping on a brand-new DB.
            LOGGER.debug("WEEKLY_NOTIFICATION_SCHEMA_WAIT", exc_info=True)
        except Exception:
            LOGGER.exception("WEEKLY_NOTIFICATION_WORKER_FAILED")
        stop_event.wait(max(10.0, float(poll_seconds)))
    LOGGER.info("WEEKLY_NOTIFICATION_WORKER_STOP")
