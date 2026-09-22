"""KHDN Ops notification engine: in-app center + standards-based Web Push.

The module is deliberately independent from Streamlit so it can run in the Railway
runtime worker and in the same-origin ASGI endpoints. It watches the immutable
``task_actions`` journal, fans relevant events out to the assigned CBHT/CBQLKH,
keeps a durable unread inbox, and sends Web Push to every active subscription.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("khdn_notifications")
_SCHEMA_READY: set[str] = set()
_SCHEMA_LOCK = threading.Lock()

EVENT_LABELS = {
    "assignment": "Giao/điều chuyển hồ sơ",
    "acceptance": "CBHT tiếp nhận",
    "return": "CBHT trả lại QLKH",
    "completion": "CBHT báo hoàn thành",
    "evaluation": "QLKH đánh giá",
    "rework": "Yêu cầu thực hiện lại",
    "update": "Cập nhật thông tin hồ sơ",
    "cancellation": "Hủy hồ sơ",
    "close": "Kết thúc hồ sơ",
    "sla": "Cảnh báo thời gian/SLA",
}

ACTION_CATEGORY = {
    "CREATE": "assignment",
    "ASSIGN": "assignment",
    "QLKH_REASSIGN": "assignment",
    "REOPEN_ASSIGN": "assignment",
    "REASSIGN": "assignment",
    "ACCEPT": "acceptance",
    "RETURN_TO_QLKH": "return",
    "SUBMIT_REVIEW": "completion",
    "EVALUATE": "evaluation",
    "REWORK": "rework",
    "LEADER_ADMIN_EDIT": "update",
    "UPDATE": "update",
    "QLKH_CANCEL": "cancellation",
    "CANCEL": "cancellation",
    "CLOSE": "close",
}

ACTION_TITLES = {
    "CREATE": "🆕 Hồ sơ mới",
    "ASSIGN": "📥 Hồ sơ mới được giao",
    "QLKH_REASSIGN": "🔄 Hồ sơ được giao lại",
    "REOPEN_ASSIGN": "🔄 Hồ sơ được giao lại",
    "REASSIGN": "🔄 Hồ sơ được điều chuyển",
    "ACCEPT": "✅ CBHT đã tiếp nhận hồ sơ",
    "RETURN_TO_QLKH": "↩️ CBHT trả lại hồ sơ",
    "SUBMIT_REVIEW": "🔔 Hồ sơ chờ QLKH đánh giá",
    "EVALUATE": "⭐ Hồ sơ đã được đánh giá",
    "REWORK": "🔁 Yêu cầu thực hiện lại",
    "LEADER_ADMIN_EDIT": "✏️ Hồ sơ được cập nhật",
    "UPDATE": "✏️ Hồ sơ được cập nhật",
    "QLKH_CANCEL": "🗑️ Hồ sơ đã hủy",
    "CANCEL": "🗑️ Hồ sơ đã hủy",
    "CLOSE": "✅ Hồ sơ đã kết thúc",
}


def _connect(db_path: str | Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(db_path: str | Path) -> None:
    key = str(Path(db_path).expanduser())
    if key in _SCHEMA_READY:
        return
    with _SCHEMA_LOCK:
        if key in _SCHEMA_READY:
            return
        with _connect(key) as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    task_id INTEGER,
                    event_key TEXT NOT NULL,
                    source_action_id INTEGER,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    deep_link TEXT,
                    created_at TEXT NOT NULL,
                    read_at TEXT,
                    push_status TEXT NOT NULL DEFAULT 'PENDING',
                    pushed_at TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    UNIQUE(user_id,source_action_id,event_key),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    endpoint TEXT NOT NULL UNIQUE,
                    p256dh TEXT NOT NULL,
                    auth TEXT NOT NULL,
                    user_agent TEXT,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_success_at TEXT,
                    last_error TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    user_id INTEGER NOT NULL,
                    event_key TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(user_id,event_key),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS notification_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notification_sla_events (
                    task_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    event_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(task_id,user_id,event_key),
                    FOREIGN KEY(task_id) REFERENCES tasks(id),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
                    ON notifications(user_id,read_at,id);
                CREATE INDEX IF NOT EXISTS idx_notifications_push
                    ON notifications(push_status,id);
                CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user
                    ON push_subscriptions(user_id,active,id);
                """
            )
            state = c.execute("SELECT value FROM notification_state WHERE key='last_action_id'").fetchone()
            if state is None:
                try:
                    max_id = int(c.execute("SELECT COALESCE(MAX(id),0) FROM task_actions").fetchone()[0] or 0)
                except sqlite3.Error:
                    max_id = 0
                c.execute(
                    "INSERT INTO notification_state(key,value,updated_at) VALUES('last_action_id',?,?)",
                    (str(max_id), _now()),
                )
            c.commit()
        _SCHEMA_READY.add(key)


def _state_get(c: sqlite3.Connection, key: str, default: str = "") -> str:
    row = c.execute("SELECT value FROM notification_state WHERE key=?", (key,)).fetchone()
    return str(row[0]) if row else default


def _state_set(c: sqlite3.Connection, key: str, value: str) -> None:
    c.execute(
        """INSERT INTO notification_state(key,value,updated_at) VALUES(?,?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
        (key, str(value), _now()),
    )


def _pref_enabled(c: sqlite3.Connection, user_id: int, event_key: str) -> bool:
    row = c.execute(
        "SELECT enabled FROM notification_preferences WHERE user_id=? AND event_key=?",
        (int(user_id), str(event_key)),
    ).fetchone()
    return True if row is None else bool(row[0])


def get_preferences(db_path: str | Path, user_id: int) -> dict[str, bool]:
    ensure_schema(db_path)
    out = {key: True for key in EVENT_LABELS}
    with _connect(db_path) as c:
        for row in c.execute(
            "SELECT event_key,enabled FROM notification_preferences WHERE user_id=?",
            (int(user_id),),
        ):
            if row["event_key"] in out:
                out[row["event_key"]] = bool(row["enabled"])
    return out


def set_preference(db_path: str | Path, user_id: int, event_key: str, enabled: bool) -> None:
    if event_key not in EVENT_LABELS:
        raise ValueError("Loại thông báo không hợp lệ")
    ensure_schema(db_path)
    with _connect(db_path) as c:
        c.execute(
            """INSERT INTO notification_preferences(user_id,event_key,enabled,updated_at)
               VALUES(?,?,?,?) ON CONFLICT(user_id,event_key)
               DO UPDATE SET enabled=excluded.enabled,updated_at=excluded.updated_at""",
            (int(user_id), event_key, int(bool(enabled)), _now()),
        )
        c.commit()


def unread_count(db_path: str | Path, user_id: int) -> int:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        return int(c.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND read_at IS NULL",
            (int(user_id),),
        ).fetchone()[0] or 0)


def list_notifications(db_path: str | Path, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        rows = c.execute(
            """SELECT id,task_id,event_key,title,body,deep_link,created_at,read_at,push_status
               FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?""",
            (int(user_id), max(1, min(int(limit), 500))),
        ).fetchall()
        return [dict(r) for r in rows]


def get_notification(db_path: str | Path, notification_id: int, user_id: int) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        row = c.execute(
            "SELECT * FROM notifications WHERE id=? AND user_id=?",
            (int(notification_id), int(user_id)),
        ).fetchone()
        return dict(row) if row else None


def mark_read(db_path: str | Path, notification_id: int, user_id: int) -> None:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        c.execute(
            "UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE id=? AND user_id=?",
            (_now(), int(notification_id), int(user_id)),
        )
        c.commit()


def mark_all_read(db_path: str | Path, user_id: int) -> None:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        c.execute(
            "UPDATE notifications SET read_at=COALESCE(read_at,?) WHERE user_id=? AND read_at IS NULL",
            (_now(), int(user_id)),
        )
        c.commit()


def subscription_count(db_path: str | Path, user_id: int) -> int:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        return int(c.execute(
            "SELECT COUNT(*) FROM push_subscriptions WHERE user_id=? AND active=1",
            (int(user_id),),
        ).fetchone()[0] or 0)


def save_subscription(db_path: str | Path, user_id: int, subscription: dict[str, Any], user_agent: str = "") -> None:
    ensure_schema(db_path)
    endpoint = str(subscription.get("endpoint") or "").strip()
    keys = subscription.get("keys") or {}
    p256dh = str(keys.get("p256dh") or "").strip()
    auth = str(keys.get("auth") or "").strip()
    if not endpoint.startswith("https://") or len(endpoint) > 4096 or not p256dh or not auth:
        raise ValueError("Push subscription không hợp lệ")
    ts = _now()
    with _connect(db_path) as c:
        c.execute(
            """INSERT INTO push_subscriptions(user_id,endpoint,p256dh,auth,user_agent,active,created_at,updated_at)
               VALUES(?,?,?,?,?,1,?,?)
               ON CONFLICT(endpoint) DO UPDATE SET user_id=excluded.user_id,p256dh=excluded.p256dh,
                 auth=excluded.auth,user_agent=excluded.user_agent,active=1,updated_at=excluded.updated_at,last_error=NULL""",
            (int(user_id), endpoint, p256dh, auth, str(user_agent or "")[:1000], ts, ts),
        )
        c.commit()


def deactivate_subscription(db_path: str | Path, user_id: int, endpoint: str) -> None:
    ensure_schema(db_path)
    with _connect(db_path) as c:
        c.execute(
            "UPDATE push_subscriptions SET active=0,updated_at=? WHERE user_id=? AND endpoint=?",
            (_now(), int(user_id), str(endpoint or "")),
        )
        c.commit()


def _ticket_secret() -> bytes:
    secret = os.getenv("KHDN_PUSH_TOKEN_SECRET", "").strip()
    if not secret:
        raise RuntimeError("KHDN_PUSH_TOKEN_SECRET chưa được cấu hình")
    return secret.encode("utf-8")


def issue_setup_ticket(user_id: int, ttl_seconds: int = 900) -> str:
    payload = {
        "uid": int(user_id),
        "exp": int(time.time()) + max(60, int(ttl_seconds)),
        "nonce": secrets.token_urlsafe(12),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(_ticket_secret(), b64.encode("ascii"), hashlib.sha256).digest()
    sig64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{b64}.{sig64}"


def verify_setup_ticket(ticket: str) -> int | None:
    try:
        b64, sig64 = str(ticket or "").split(".", 1)
        expected = hmac.new(_ticket_secret(), b64.encode("ascii"), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(sig64 + "=" * (-len(sig64) % 4))
        if not hmac.compare_digest(expected, actual):
            return None
        raw = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
        payload = json.loads(raw.decode("utf-8"))
        if int(payload.get("exp") or 0) < int(time.time()):
            return None
        uid = int(payload.get("uid") or 0)
        return uid if uid > 0 else None
    except Exception:
        return None


def _task_context(c: sqlite3.Connection, task_id: int) -> dict[str, Any] | None:
    row = c.execute(
        """SELECT t.id,t.task_code,t.support_user_id,t.qlkh_user_id,t.task_type,t.status,t.amount,t.currency,
                  c.cif,c.customer_name,s.full_name support_name,q.full_name qlkh_name
           FROM tasks t JOIN customers c ON c.id=t.customer_id
           JOIN users s ON s.id=t.support_user_id JOIN users q ON q.id=t.qlkh_user_id
           WHERE t.id=?""",
        (int(task_id),),
    ).fetchone()
    return dict(row) if row else None


def _recipients(action: str, actor_id: int, ctx: dict[str, Any]) -> list[int]:
    support = int(ctx["support_user_id"])
    qlkh = int(ctx["qlkh_user_id"])
    action = str(action or "").upper()
    if action in {"ASSIGN", "QLKH_REASSIGN", "REOPEN_ASSIGN"}:
        candidates = [support]
    elif action in {"ACCEPT", "SUBMIT_REVIEW", "RETURN_TO_QLKH"}:
        candidates = [qlkh]
    elif action == "EVALUATE":
        candidates = [support]
    elif action == "CREATE":
        candidates = [qlkh] if actor_id == support else [support]
    else:
        candidates = [support, qlkh]
    out: list[int] = []
    for uid in candidates:
        if uid != int(actor_id) and uid not in out:
            out.append(uid)
    return out


def _short(text: Any, limit: int = 150) -> str:
    value = " ".join(str(text or "").replace("\n", " ").split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def _insert_notification(
    c: sqlite3.Connection,
    *,
    user_id: int,
    task_id: int,
    event_key: str,
    source_action_id: int | None,
    title: str,
    body: str,
) -> int | None:
    if not _pref_enabled(c, user_id, event_key):
        return None
    try:
        cur = c.execute(
            """INSERT INTO notifications(user_id,task_id,event_key,source_action_id,title,body,created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (int(user_id), int(task_id), event_key, source_action_id, title, body, _now()),
        )
    except sqlite3.IntegrityError:
        return None
    nid = int(cur.lastrowid)
    deep_link = f"/?khdn_notification={nid}"
    c.execute("UPDATE notifications SET deep_link=? WHERE id=?", (deep_link, nid))
    return nid


def _create_from_action(c: sqlite3.Connection, action_row: sqlite3.Row) -> list[int]:
    action = str(action_row["action"] or "").upper()
    event_key = ACTION_CATEGORY.get(action)
    if not event_key:
        return []
    ctx = _task_context(c, int(action_row["task_id"]))
    if not ctx:
        return []
    title = ACTION_TITLES.get(action, "🔔 Hồ sơ có thay đổi")
    code = ctx.get("task_code") or f"TN-{int(ctx['id']):06d}"
    base = f"{code} · CIF {ctx.get('cif','')} · {ctx.get('customer_name','')} · {ctx.get('task_type','')}"
    detail = _short(action_row["detail"], 110)
    body = base + (f". {detail}" if detail else "")
    created: list[int] = []
    for uid in _recipients(action, int(action_row["actor_user_id"]), ctx):
        nid = _insert_notification(
            c,
            user_id=uid,
            task_id=int(ctx["id"]),
            event_key=event_key,
            source_action_id=int(action_row["id"]),
            title=title,
            body=body,
        )
        if nid:
            created.append(nid)
    return created


def _vapid_private_key() -> str:
    value = os.getenv("KHDN_VAPID_PRIVATE_KEY", "").strip()
    return value.replace("\\n", "\n")


def push_available() -> bool:
    return bool(_vapid_private_key() and os.getenv("KHDN_VAPID_PUBLIC_KEY", "").strip())


def _send_notification_push(db_path: str | Path, notification_id: int) -> None:
    ensure_schema(db_path)
    private_key = _vapid_private_key()
    if not private_key:
        with _connect(db_path) as c:
            c.execute(
                "UPDATE notifications SET push_status='DISABLED',last_error=? WHERE id=?",
                ("VAPID chưa cấu hình", int(notification_id)),
            )
            c.commit()
        return
    try:
        from pywebpush import WebPushException, webpush
    except Exception as exc:
        with _connect(db_path) as c:
            c.execute(
                "UPDATE notifications SET push_status='ERROR',last_error=?,attempt_count=attempt_count+1 WHERE id=?",
                (f"pywebpush: {exc}", int(notification_id)),
            )
            c.commit()
        return

    with _connect(db_path) as c:
        n = c.execute("SELECT * FROM notifications WHERE id=?", (int(notification_id),)).fetchone()
        if not n:
            return
        subs = c.execute(
            "SELECT * FROM push_subscriptions WHERE user_id=? AND active=1 ORDER BY id",
            (int(n["user_id"]),),
        ).fetchall()
        if not subs:
            c.execute(
                "UPDATE notifications SET push_status='NO_DEVICE',last_error=NULL WHERE id=?",
                (int(notification_id),),
            )
            c.commit()
            return
        badge = int(c.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id=? AND read_at IS NULL",
            (int(n["user_id"]),),
        ).fetchone()[0] or 0)

    payload = json.dumps(
        {
            "title": n["title"],
            "body": n["body"],
            "url": n["deep_link"] or "/",
            "tag": f"khdn-task-{n['task_id'] or n['id']}",
            "badgeCount": badge,
        },
        ensure_ascii=False,
    )
    subject = os.getenv("KHDN_VAPID_SUBJECT", "mailto:nghiatld@bidv.com.vn").strip()
    sent = 0
    errors: list[str] = []
    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=3600,
                timeout=10,
            )
            sent += 1
            with _connect(db_path) as c:
                c.execute(
                    "UPDATE push_subscriptions SET last_success_at=?,last_error=NULL,updated_at=? WHERE id=?",
                    (_now(), _now(), int(sub["id"])),
                )
                c.commit()
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            msg = _short(exc, 350)
            errors.append(msg)
            with _connect(db_path) as c:
                if status in {404, 410}:
                    c.execute(
                        "UPDATE push_subscriptions SET active=0,last_error=?,updated_at=? WHERE id=?",
                        (msg, _now(), int(sub["id"])),
                    )
                else:
                    c.execute(
                        "UPDATE push_subscriptions SET last_error=?,updated_at=? WHERE id=?",
                        (msg, _now(), int(sub["id"])),
                    )
                c.commit()
        except Exception as exc:
            errors.append(_short(exc, 350))

    with _connect(db_path) as c:
        if sent:
            c.execute(
                """UPDATE notifications SET push_status='SENT',pushed_at=?,attempt_count=attempt_count+1,last_error=?
                   WHERE id=?""",
                (_now(), "; ".join(errors)[:1000] if errors else None, int(notification_id)),
            )
        else:
            c.execute(
                """UPDATE notifications SET push_status='ERROR',attempt_count=attempt_count+1,last_error=?
                   WHERE id=?""",
                (("; ".join(errors) or "Không gửi được push")[:1000], int(notification_id)),
            )
        c.commit()


def process_task_actions(db_path: str | Path, limit: int = 100) -> int:
    ensure_schema(db_path)
    created_ids: list[int] = []
    with _connect(db_path) as c:
        last_id = int(_state_get(c, "last_action_id", "0") or 0)
        rows = c.execute(
            "SELECT id,task_id,actor_user_id,action,detail,created_at FROM task_actions WHERE id>? ORDER BY id LIMIT ?",
            (last_id, max(1, min(int(limit), 1000))),
        ).fetchall()
        for row in rows:
            try:
                created_ids.extend(_create_from_action(c, row))
            except Exception:
                LOGGER.exception("NOTIFICATION_ACTION_FAILED action_id=%s", row["id"])
            _state_set(c, "last_action_id", str(int(row["id"])))
        c.commit()
    for nid in created_ids:
        _send_notification_push(db_path, nid)
    return len(created_ids)


def _parse_local(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def process_sla_alerts(db_path: str | Path) -> int:
    """Create one 75%-SLA warning and one overdue alert per active task/user."""
    ensure_schema(db_path)
    now = datetime.now()
    created_ids: list[int] = []
    with _connect(db_path) as c:
        rows = c.execute(
            """SELECT t.id,t.task_code,t.support_user_id,t.qlkh_user_id,t.task_type,t.start_time,
                      COALESCE(tt.sla_hours,8) sla_hours,c.cif,c.customer_name
               FROM tasks t JOIN customers c ON c.id=t.customer_id
               LEFT JOIN task_types tt ON tt.name=t.task_type
               WHERE t.status IN ('OPEN','REWORK') AND t.start_time IS NOT NULL"""
        ).fetchall()
        for row in rows:
            start = _parse_local(row["start_time"])
            if not start:
                continue
            sla_hours = max(0.25, float(row["sla_hours"] or 8.0))
            ratio = max(0.0, (now - start).total_seconds() / 3600.0 / sla_hours)
            if ratio < 0.75:
                continue
            event = "SLA_OVERDUE" if ratio >= 1.0 else "SLA_WARNING"
            title = "⛔ Hồ sơ đã vượt SLA" if event == "SLA_OVERDUE" else "⚠️ Hồ sơ sắp đến SLA"
            pct = int(round(ratio * 100))
            code = row["task_code"] or f"TN-{int(row['id']):06d}"
            body = f"{code} · CIF {row['cif']} · {row['customer_name']} · {row['task_type']} · {pct}% SLA"
            for uid in {int(row["support_user_id"]), int(row["qlkh_user_id"])}:
                if not _pref_enabled(c, uid, "sla"):
                    continue
                exists = c.execute(
                    "SELECT 1 FROM notification_sla_events WHERE task_id=? AND user_id=? AND event_key=?",
                    (int(row["id"]), uid, event),
                ).fetchone()
                if exists:
                    continue
                c.execute(
                    "INSERT INTO notification_sla_events(task_id,user_id,event_key,created_at) VALUES(?,?,?,?)",
                    (int(row["id"]), uid, event, _now()),
                )
                nid = _insert_notification(
                    c,
                    user_id=uid,
                    task_id=int(row["id"]),
                    event_key="sla",
                    source_action_id=None,
                    title=title,
                    body=body,
                )
                if nid:
                    created_ids.append(nid)
        c.commit()
    for nid in created_ids:
        _send_notification_push(db_path, nid)
    return len(created_ids)


def worker_loop(db_path: str | Path, stop_event: threading.Event, poll_seconds: float = 2.0) -> None:
    ensure_schema(db_path)
    last_sla = 0.0
    LOGGER.info("NOTIFICATION_WORKER_START db=%s push=%s", db_path, push_available())
    while not stop_event.is_set():
        try:
            process_task_actions(db_path)
            if time.time() - last_sla >= 60:
                process_sla_alerts(db_path)
                last_sla = time.time()
        except Exception:
            LOGGER.exception("NOTIFICATION_WORKER_LOOP_FAILED")
        stop_event.wait(max(1.0, float(poll_seconds)))
    LOGGER.info("NOTIFICATION_WORKER_STOP")
