"""Durable planning and Customer Work delivery through the existing Push transport.

The weekly worker drains this queue; the operations worker also drains its
Customer Work category. Task actions keep their existing delivery path.
Enqueue is part of the caller's transaction.
"""
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sqlite3
import time
from zoneinfo import ZoneInfo

from khdn_apps import notifications as notify

LOGGER = logging.getLogger("khdn_weekly_push")
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
MAX_ATTEMPTS = 3
TTL_SECONDS = 24 * 3600


def local_now() -> datetime:
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def ensure_tables(c: sqlite3.Connection) -> None:
    # Individual statements preserve an already-open business transaction.
    c.execute("""CREATE TABLE IF NOT EXISTS weekly_push_queue(
        notification_id INTEGER PRIMARY KEY,
        event_code TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'PENDING',
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at REAL NOT NULL DEFAULT 0,
        lease_until REAL NOT NULL DEFAULT 0,
        expires_at REAL NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(notification_id) REFERENCES notifications(id) ON DELETE CASCADE
    )""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_weekly_push_due
                 ON weekly_push_queue(state,next_attempt_at)""")
    c.execute("""CREATE TABLE IF NOT EXISTS weekly_push_audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        notification_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        event_code TEXT NOT NULL,
        stage TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_weekly_push_audit
                 ON weekly_push_audit(notification_id,id)""")


def _audit(c, nid: int, uid: int, event_code: str, stage: str) -> None:
    c.execute("""INSERT INTO weekly_push_audit
        (notification_id,user_id,event_code,stage,created_at) VALUES(?,?,?,?,?)""",
        (nid, uid, event_code, stage, local_now().isoformat(timespec="seconds")))


def enqueue(c, user_id: int, title: str, body: str, *,
            event_code: str = "PLAN_UPDATE", event_key: str = "weekly_update",
            expires_at: float | None = None, source_action_id: int | None = None,
            customer_work_case_id: int | None = None) -> int | None:
    ensure_tables(c)
    uid = int(user_id)
    active = c.execute("SELECT active FROM users WHERE id=?", (uid,)).fetchone()
    if not active or not active[0] or not notify._pref_enabled(c, uid, event_key):
        return None
    ts = local_now().strftime("%Y-%m-%d %H:%M:%S")
    cur = c.execute("""INSERT INTO notifications
        (user_id,event_key,title,body,created_at,push_status,source_action_id,customer_work_case_id)
        VALUES(?,?,?,?,?,'PENDING',?,?)
        ON CONFLICT(user_id,source_action_id,event_key) DO NOTHING""",
        (uid, event_key, str(title), str(body), ts, source_action_id, customer_work_case_id))
    if not cur.rowcount:
        return None
    nid = int(cur.lastrowid)
    c.execute("UPDATE notifications SET deep_link=? WHERE id=?",
              (f"/?khdn_notification={nid}", nid))
    c.execute("""INSERT INTO weekly_push_queue
        (notification_id,event_code,expires_at,updated_at) VALUES(?,?,?,?)""",
        (nid, event_code, expires_at or time.time() + TTL_SECONDS, ts))
    _audit(c, nid, uid, event_code, "IN_APP_CREATED")
    return nid


def ensure_schema(db_path: str | Path) -> None:
    notify.ensure_schema(db_path)
    with notify._connect(db_path) as c:
        ensure_tables(c)
        # Earlier planning producers used task_id=NULL and update/sla. Recover
        # only recent unsent messages; never resend SENT or historical alerts.
        rows = c.execute("""SELECT n.id,n.user_id,n.created_at FROM notifications n
            LEFT JOIN weekly_push_queue q ON q.notification_id=n.id
            WHERE q.notification_id IS NULL AND n.task_id IS NULL
              AND n.source_action_id IS NULL
              AND n.event_key IN ('update','sla')
              AND n.push_status IN ('PENDING','DISABLED','NO_DEVICE','ERROR')""").fetchall()
        for r in rows:
            try:
                expires = datetime.fromisoformat(r["created_at"]).replace(tzinfo=LOCAL_TZ).timestamp() + TTL_SECONDS
            except (TypeError, ValueError):
                continue
            if expires <= time.time():
                continue
            cur = c.execute("""INSERT OR IGNORE INTO weekly_push_queue
                (notification_id,event_code,expires_at,updated_at) VALUES(?,'LEGACY_PLAN',?,?)""",
                (int(r["id"]), expires, local_now().isoformat(timespec="seconds")))
            if cur.rowcount:
                _audit(c, int(r["id"]), int(r["user_id"]), "LEGACY_PLAN", "RECOVERED")
        c.commit()


def _claim(db_path, now_ts: float, event_key: str | None = None):
    with notify._connect(db_path) as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("""SELECT q.*,n.user_id,n.push_status,n.read_at,n.event_key,n.customer_work_case_id
            FROM weekly_push_queue q JOIN notifications n ON n.id=q.notification_id
            WHERE ((q.state IN ('PENDING','RETRY') AND q.next_attempt_at<=?)
               OR (q.state='SENDING' AND q.lease_until<=?))
               AND (? IS NULL OR n.event_key=?)
            ORDER BY q.notification_id LIMIT 1""", (now_ts, now_ts, event_key, event_key)).fetchone()
        if not row:
            return None
        r = dict(row)
        uid, nid = int(r["user_id"]), int(r["notification_id"])
        active = c.execute("SELECT active FROM users WHERE id=?", (uid,)).fetchone()
        case_allowed = True
        if r["customer_work_case_id"]:
            case = c.execute("SELECT owner_user_id,status FROM customer_work_cases WHERE id=?",
                             (int(r["customer_work_case_id"]),)).fetchone()
            case_allowed = bool(case and int(case[0]) == uid and case[1] not in {"CANCELLED", "COMPLETED"})
        terminal = None
        if r["push_status"] == "SENT":
            terminal = "SENT"
        elif r["expires_at"] <= now_ts:
            terminal = "EXPIRED"
        elif r["read_at"] or not active or not active[0] or not case_allowed or not notify._pref_enabled(c, uid, r["event_key"]):
            terminal = "SKIPPED"
        if terminal:
            if terminal in {"EXPIRED", "SKIPPED"}:
                c.execute("UPDATE notifications SET push_status=? WHERE id=?", (terminal, nid))
            c.execute("UPDATE weekly_push_queue SET state=?,lease_until=0,updated_at=? WHERE notification_id=?",
                      (terminal, local_now().isoformat(timespec="seconds"), nid))
            _audit(c, nid, uid, r["event_code"], terminal)
            c.commit()
            r["skip"] = True
            return r
        devices = c.execute("SELECT COUNT(*) FROM push_subscriptions WHERE user_id=? AND active=1", (uid,)).fetchone()[0]
        c.execute("UPDATE weekly_push_queue SET state='SENDING',lease_until=?,updated_at=? WHERE notification_id=?",
                  (now_ts + max(120, int(devices) * 12 + 30), local_now().isoformat(timespec="seconds"), nid))
        _audit(c, nid, uid, r["event_code"], "PUSH_ATTEMPT")
        c.commit()
        return r


def flush(db_path: str | Path, limit: int = 80, now_ts: float | None = None,
          *, event_key: str | None = None) -> int:
    ensure_schema(db_path)
    delivered = 0
    for _ in range(max(1, min(int(limit), 500))):
        now = time.time() if now_ts is None else now_ts
        r = _claim(db_path, now, event_key)
        if not r:
            break
        if r.get("skip"):
            continue
        nid, uid = int(r["notification_id"]), int(r["user_id"])
        LOGGER.info("WEEKLY_PUSH_ATTEMPT notification_id=%s event=%s user_id=%s created_in_app=1",
                    nid, r["event_code"], uid)
        try:
            notify._send_notification_push(db_path, nid)
            with notify._connect(db_path) as c:
                n = c.execute("SELECT push_status FROM notifications WHERE id=?", (nid,)).fetchone()
            status = str(n[0]) if n else "ERROR"
        except Exception as exc:
            # Never write subscription endpoints, credentials or content to logs.
            LOGGER.warning("WEEKLY_PUSH_TRANSPORT_EXCEPTION id=%s type=%s", nid, type(exc).__name__)
            status = "ERROR"
            with notify._connect(db_path) as c:
                c.execute("UPDATE notifications SET push_status='ERROR',last_error=? WHERE id=?",
                          (f"Transport exception: {type(exc).__name__}", nid))
                c.commit()
        attempts = int(r["attempts"]) + int(status not in {"DISABLED", "NO_DEVICE"})
        state = "SENT" if status == "SENT" else ("ERROR" if attempts >= MAX_ATTEMPTS else "RETRY")
        delay = 300 if status in {"DISABLED", "NO_DEVICE"} else 60 * 2 ** max(0, attempts - 1)
        with notify._connect(db_path) as c:
            c.execute("""UPDATE weekly_push_queue SET state=?,attempts=?,next_attempt_at=?,lease_until=0,
                updated_at=? WHERE notification_id=?""",
                (state, attempts, now + delay, local_now().isoformat(timespec="seconds"), nid))
            _audit(c, nid, uid, r["event_code"], f"PUSH_{status}")
            c.commit()
        LOGGER.info("WEEKLY_PUSH_RESULT notification_id=%s event=%s user_id=%s status=%s queue=%s attempts=%s",
                    nid, r["event_code"], uid, status, state, attempts)
        delivered += int(status == "SENT")
    return delivered
