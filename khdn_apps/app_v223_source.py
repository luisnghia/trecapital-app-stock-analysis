import os
import re
import hmac
import math
import sqlite3
import hashlib
import secrets
import json
import subprocess
import shutil
import smtplib
import ssl
import unicodedata
import base64
import html
import logging
from logging.handlers import RotatingFileHandler
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import httpx
from khdn_apps.storage import snapshot_database, sqlite_backup_bytes, read_status
from khdn_apps import device_login

APP_TITLE = "KHDN Ops - Theo dõi tác nghiệp"
APP_VERSION = "2.27.0"
CLOUD_MODE = str(os.getenv("KHDN_CLOUD_MODE", "0")).strip().lower() in {"1","true","yes","on"}
DB_PATH = os.getenv("KHDN_DB_PATH", "khdn_ops.db")

def _runtime_setting(name, default=""):
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    try:
        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default

DEFAULT_ADMIN_PASSWORD = _runtime_setting("KHDN_ADMIN_PASSWORD", "" if CLOUD_MODE else "Admin@123")
ADMIN_RECOVERY_EMAIL = os.getenv("KHDN_ADMIN_RECOVERY_EMAIL", "nghiatld@bidv.com.vn")
AUTO_REFRESH_SECONDS = max(3, int(os.getenv("KHDN_AUTO_REFRESH_SECONDS", "6") or 6))
BIDV_FX_URL = "https://bidv.com.vn/vn/ty-gia-ngoai-te"
BIDV_FX_TIME_URL = "https://bidv.com.vn/ServicesBIDV/ExchangeDetailSearchTimeServlet"
BIDV_FX_DETAIL_URL = "https://bidv.com.vn/ServicesBIDV/ExchangeDetailServlet"
BIDV_LOGO_URL = "https://bidv.com.vn/wps/wcm/connect/ebefa95d-1bed-49eb-8456-31a948a77309/logo_bidv_big.svg?CACHEID=ROOTWORKSPACE-ebefa95d-1bed-49eb-8456-31a948a77309-p3E781I&MOD=AJPERES"
APP_DIR = Path(__file__).resolve().parent
ASSET_DIR = APP_DIR / "assets"
BIDV_LOGO_PATH = ASSET_DIR / "bidv_logo.svg"
STATIC_DIR = APP_DIR / "static"
APP_ICON_SVG_PATH = STATIC_DIR / "bidv-icon.svg"
APP_ICON_PNG_PATH = STATIC_DIR / "bidv-icon-180.png"
APP_ICON_192_PATH = STATIC_DIR / "bidv-icon-192.png"
APP_ICON_512_PATH = STATIC_DIR / "bidv-icon-512.png"
APP_ICON_VERSION = "2.27"
RUNTIME_DATA_DIR = Path(os.getenv("KHDN_DATA_DIR", str(APP_DIR))).expanduser()
ANNUAL_ARCHIVE_DIR = RUNTIME_DATA_DIR / "annual_archive"
LOG_DIR = RUNTIME_DATA_DIR / "logs"
APP_LOG_PATH = LOG_DIR / "khdn_ops.log"
GUIDE_PATH = APP_DIR / "HUONG_DAN_SU_DUNG_KHDN_OPS_v2.22.docx"
GUIDE_MARKDOWN_PATH = APP_DIR / "GUIDE.md"
ROLES = ["Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng"]
DEFAULT_TASK_TYPES = ["Giải Ngân", "Bảo Lãnh", "LC", "Nhập/Xuất kho", "Công chứng TSBĐ", "Đăng ký thế chấp"]
STATUS_LABEL = {
    "PENDING_ACCEPTANCE": "Chờ CB hỗ trợ tiếp nhận",
    "OPEN": "Đang thực hiện",
    "PENDING_REVIEW": "Chờ QLKH đánh giá",
    "EVALUATED": "Đã đánh giá - chờ LĐP",
    "REWORK": "Yêu cầu thực hiện lại",
    "CLOSED": "Đã kết thúc",
    "CANCELLED": "Đã hủy",
    "RETURNED_TO_QLKH": "CB hỗ trợ trả lại QLKH",
}
ACTION_LABEL = {
    "CREATE": "Tạo tác nghiệp",
    "ASSIGN": "QLKH giao hồ sơ",
    "ACCEPT": "CB hỗ trợ tiếp nhận",
    "SUBMIT_REVIEW": "Báo hoàn thành",
    "EVALUATE": "QLKH đánh giá",
    "CLOSE": "Lãnh đạo kết thúc",
    "REWORK": "Lãnh đạo yêu cầu làm lại",
    "REASSIGN": "Điều chuyển người xử lý",
    "QLKH_REASSIGN": "QLKH đổi CB hỗ trợ",
    "RETURN_TO_QLKH": "CB hỗ trợ trả lại QLKH",
    "QLKH_CANCEL": "QLKH xóa/hủy hồ sơ đã tạo",
    "REOPEN_ASSIGN": "QLKH giao lại hồ sơ",
    "CANCEL": "Hủy tác nghiệp",
    "UPDATE": "Cập nhật",
}

_LOGGER_READY = False

def setup_logging():
    """Ghi log xoay vòng để có dấu vết khi app chạy và khi tác vụ nền lỗi."""
    global _LOGGER_READY
    if _LOGGER_READY:
        return logging.getLogger("khdn_ops")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("khdn_ops")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = RotatingFileHandler(APP_LOG_PATH, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
    _LOGGER_READY = True
    logger.info("APP_START version=%s db=%s", APP_VERSION, DB_PATH)
    return logger

LOGGER = setup_logging()


def _cache_data(*args, **kwargs):
    """Use Streamlit cache in production, identity decorator in headless QA."""
    if hasattr(st, "cache_data"):
        return st.cache_data(*args, **kwargs)
    def deco(fn):
        from functools import lru_cache
        wrapped = lru_cache(maxsize=64)(fn)
        wrapped.clear = wrapped.cache_clear
        return wrapped
    return deco


# ---------- Core ----------
def now_dt():
    return datetime.now()


def now_str():
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(v):
    if not v or pd.isna(v):
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.strptime(str(v), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return pd.to_datetime(v).to_pydatetime()


def get_conn():
    db_target = Path(DB_PATH).expanduser()
    if str(db_target.parent) not in {"", "."}:
        db_target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_target), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def table_columns(conn, table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def add_column_if_missing(conn, table, column, ddl):
    if column not in table_columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000).hex()
        return hmac.compare_digest(test, digest)
    except Exception:
        return False


def password_ok(p):
    return len(p) >= 8 and bool(re.search(r"[A-Za-z]", p)) and bool(re.search(r"\d", p))


def init_db():
    with get_conn() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Cán bộ hỗ trợ','Cán bộ QLKH','Lãnh đạo phòng')),
            is_admin INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            must_change_password INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT,
            deleted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cif TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            qlkh_user_id INTEGER,
            qlkh_source_text TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            FOREIGN KEY(qlkh_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS task_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            sla_hours REAL NOT NULL DEFAULT 8,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_code TEXT UNIQUE,
            customer_id INTEGER NOT NULL,
            support_user_id INTEGER NOT NULL,
            qlkh_user_id INTEGER NOT NULL,
            request_source TEXT NOT NULL DEFAULT 'SUPPORT',
            assigned_at TEXT,
            accepted_at TEXT,
            first_accepted_at TEXT,
            returned_to_qlkh_at TEXT,
            cancelled_at TEXT,
            evaluated_at TEXT,
            last_rework_at TEXT,
            task_type TEXT NOT NULL,
            amount REAL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'VND',
            fx_rate REAL NOT NULL DEFAULT 1,
            amount_vnd REAL DEFAULT 0,
            start_time TEXT NOT NULL,
            due_time TEXT,
            end_time TEXT,
            closed_time TEXT,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN',
            current_round INTEGER NOT NULL DEFAULT 1,
            rework_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(support_user_id) REFERENCES users(id),
            FOREIGN KEY(qlkh_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            round_no INTEGER NOT NULL,
            evaluator_user_id INTEGER NOT NULL,
            quality_score REAL NOT NULL,
            progress_score REAL NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(task_id, round_no),
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(evaluator_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS task_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            actor_user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(id),
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS system_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER,
            action TEXT NOT NULL,
            object_type TEXT,
            object_id TEXT,
            detail TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency TEXT NOT NULL,
            rate_to_vnd REAL NOT NULL,
            rate_type TEXT NOT NULL DEFAULT 'Mua chuyển khoản',
            source TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS annual_archives (
            year INTEGER PRIMARY KEY,
            stats_file TEXT,
            detail_file TEXT,
            db_backup_file TEXT,
            task_count INTEGER NOT NULL DEFAULT 0,
            archived_at TEXT NOT NULL,
            best_five_year_reference INTEGER,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_fx_currency_time ON exchange_rates(currency, fetched_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_support ON tasks(support_user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_qlkh ON tasks(qlkh_user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_start ON tasks(start_time);
        CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_support_status_updated ON tasks(support_user_id,status,updated_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_qlkh_status_updated ON tasks(qlkh_user_id,status,updated_at);
        CREATE INDEX IF NOT EXISTS idx_tasks_status_assigned ON tasks(status,assigned_at);
        CREATE INDEX IF NOT EXISTS idx_customers_active_cif ON customers(active,cif);
        CREATE INDEX IF NOT EXISTS idx_customers_active_name ON customers(active,customer_name);
        CREATE INDEX IF NOT EXISTS idx_actions_task ON task_actions(task_id);
        CREATE INDEX IF NOT EXISTS idx_actions_action_task ON task_actions(action,task_id);
        CREATE INDEX IF NOT EXISTS idx_eval_task_round ON evaluations(task_id,round_no);
        ''')
        # migration from V1
        add_column_if_missing(c, "users", "must_change_password", "INTEGER NOT NULL DEFAULT 1")
        add_column_if_missing(c, "users", "last_login_at", "TEXT")
        add_column_if_missing(c, "users", "deleted_at", "TEXT")
        add_column_if_missing(c, "users", "avatar_blob", "BLOB")
        add_column_if_missing(c, "users", "avatar_mime", "TEXT")
        add_column_if_missing(c, "customers", "updated_at", "TEXT")
        add_column_if_missing(c, "customers", "qlkh_source_text", "TEXT")
        add_column_if_missing(c, "tasks", "task_code", "TEXT")
        add_column_if_missing(c, "tasks", "due_time", "TEXT")
        add_column_if_missing(c, "tasks", "closed_time", "TEXT")
        add_column_if_missing(c, "tasks", "rework_count", "INTEGER NOT NULL DEFAULT 0")
        add_column_if_missing(c, "tasks", "currency", "TEXT NOT NULL DEFAULT 'VND'")
        add_column_if_missing(c, "tasks", "fx_rate", "REAL NOT NULL DEFAULT 1")
        add_column_if_missing(c, "tasks", "amount_vnd", "REAL DEFAULT 0")
        add_column_if_missing(c, "tasks", "request_source", "TEXT NOT NULL DEFAULT 'SUPPORT'")
        add_column_if_missing(c, "tasks", "assigned_at", "TEXT")
        add_column_if_missing(c, "tasks", "accepted_at", "TEXT")
        add_column_if_missing(c, "tasks", "first_accepted_at", "TEXT")
        add_column_if_missing(c, "tasks", "returned_to_qlkh_at", "TEXT")
        add_column_if_missing(c, "tasks", "cancelled_at", "TEXT")
        add_column_if_missing(c, "tasks", "evaluated_at", "TEXT")
        add_column_if_missing(c, "tasks", "last_rework_at", "TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_code ON tasks(task_code) WHERE task_code IS NOT NULL")
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            ts = now_str()
            if DEFAULT_ADMIN_PASSWORD:
                c.execute('''INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at)
                             VALUES(?,?,?,?,1,1,1,?,?)''',
                          ("admin", "Quản trị hệ thống", hash_password(DEFAULT_ADMIN_PASSWORD), "Lãnh đạo phòng", ts, ts))
            elif CLOUD_MODE:
                LOGGER.warning("CLOUD_BOOTSTRAP_BLOCKED: KHDN_ADMIN_PASSWORD is not configured; no default admin created")
        ts = now_str()
        for name in DEFAULT_TASK_TYPES:
            c.execute('''INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES(?,8,1,?,?)
                         ON CONFLICT(name) DO NOTHING''', (name, ts, ts))
        # backfill mã tác nghiệp và dữ liệu tiền tệ cho bản cũ
        old = c.execute("SELECT id,task_code,amount,currency,fx_rate,amount_vnd FROM tasks").fetchall()
        for r in old:
            code = r["task_code"] or f"TN-{int(r['id']):06d}"
            cur = r["currency"] or "VND"
            rate = float(r["fx_rate"] or 1)
            amount_vnd = float(r["amount_vnd"] or 0)
            if amount_vnd == 0 and float(r["amount"] or 0) != 0:
                amount_vnd = float(r["amount"] or 0) * rate
            c.execute("UPDATE tasks SET task_code=?,currency=?,fx_rate=?,amount_vnd=?,due_time=NULL WHERE id=?", (code,cur,rate,amount_vnd,r["id"]))
        # V2.1 yêu cầu Lãnh đạo duyệt sau QLKH; từ V2.2 bỏ bước duyệt này. Hồ sơ đã QLKH đánh giá được tự chuyển sang kết thúc.
        c.execute("UPDATE tasks SET status='CLOSED',closed_time=COALESCE(closed_time,updated_at,end_time),updated_at=? WHERE status='EVALUATED'", (now_str(),))
        # V2.6: backfill mốc workflow cho dữ liệu cũ. Hồ sơ cũ được xem là do CB hỗ trợ tự khởi tạo/tiếp nhận ngay.
        c.execute("""UPDATE tasks SET request_source=COALESCE(NULLIF(request_source,''),'SUPPORT'),
                     assigned_at=COALESCE(assigned_at,created_at,start_time),
                     accepted_at=CASE WHEN request_source='SUPPORT' THEN COALESCE(accepted_at,start_time) ELSE accepted_at END,
                     first_accepted_at=COALESCE(first_accepted_at,accepted_at,CASE WHEN request_source='SUPPORT' THEN start_time ELSE NULL END),
                     evaluated_at=COALESCE(evaluated_at,closed_time)
                     WHERE request_source IS NULL OR assigned_at IS NULL OR first_accepted_at IS NULL OR (status='CLOSED' AND evaluated_at IS NULL)""")
        c.commit()


def execute(sql, params=()):
    with get_conn() as c:
        cur = c.execute(sql, params)
        c.commit()
        return cur.lastrowid


def qdf(sql, params=()):
    with get_conn() as c:
        return pd.read_sql_query(sql, c, params=params)


def audit(actor_user_id, action, object_type="", object_id="", detail=""):
    execute("INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) VALUES(?,?,?,?,?,?)",
            (actor_user_id, action, object_type, str(object_id or ""), detail, now_str()))


def log_action(task_id, user_id, action, detail=""):
    execute("INSERT INTO task_actions(task_id,actor_user_id,action,detail,created_at) VALUES(?,?,?,?,?)",
            (task_id, user_id, action, detail, now_str()))
    audit(user_id, action, "task", task_id, detail)


def user_by_username(username, active_only=True):
    with get_conn() as c:
        sql = "SELECT * FROM users WHERE lower(username)=lower(?)"
        if active_only:
            sql += " AND active=1"
        return c.execute(sql, (username,)).fetchone()


def _users_revision():
    with get_conn() as c:
        r=c.execute("SELECT COALESCE(MAX(updated_at),''),COUNT(*) FROM users").fetchone()
    return f"{r[0]}|{r[1]}"

@_cache_data(ttl=30, show_spinner=False)
def _all_users_cached(db_path, role, active_only, include_deleted, revision):
    sql = "SELECT id,username,full_name,role,is_admin,active,must_change_password,last_login_at,deleted_at FROM users"
    params = []
    clauses = []
    if role:
        clauses.append("role=?"); params.append(role)
    if active_only:
        clauses.append("active=1")
    if not include_deleted:
        clauses.append("deleted_at IS NULL")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY full_name"
    return qdf(sql, params)

def all_users(role=None, active_only=False, include_deleted=False):
    return _all_users_cached(str(DB_PATH), role, bool(active_only), bool(include_deleted), _users_revision()).copy()


def rename_username(actor, user_id, new_username):
    new_username = str(new_username or "").strip()
    if not new_username:
        raise ValueError("Username mới không được để trống.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,64}", new_username):
        raise ValueError("Username chỉ dùng chữ, số, dấu chấm, gạch dưới/gạch ngang; dài 3-64 ký tự.")
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (int(user_id),)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy user.")
        dup = c.execute("SELECT id FROM users WHERE lower(username)=lower(?) AND id<>? AND deleted_at IS NULL", (new_username, int(user_id))).fetchone()
        if dup:
            raise ValueError("Username mới đã tồn tại.")
        old_username = row["username"]
        c.execute("UPDATE users SET username=?,updated_at=? WHERE id=?", (new_username, now_str(), int(user_id)))
        # Cập nhật nguồn QLKH chỉ khi nguồn đang đúng bằng username cũ, tránh làm mất dữ liệu nhập tay theo họ tên.
        c.execute("UPDATE customers SET qlkh_source_text=?,updated_at=? WHERE qlkh_user_id=? AND lower(COALESCE(qlkh_source_text,''))=lower(?)", (new_username, now_str(), int(user_id), old_username))
        c.commit()
    audit(actor["id"], "RENAME_USER", "user", user_id, f"{old_username} -> {new_username}")
    return new_username


def delete_user_account(actor, user_id):
    user_id = int(user_id)
    if user_id == int(actor["id"]):
        raise ValueError("Không thể xóa chính tài khoản đang đăng nhập.")
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (user_id,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy user hoặc user đã được xóa.")
        open_count = c.execute("SELECT COUNT(*) FROM tasks WHERE (support_user_id=? OR qlkh_user_id=?) AND status NOT IN ('CLOSED','CANCELLED')", (user_id, user_id)).fetchone()[0]
        if open_count:
            raise ValueError(f"User còn {open_count} tác nghiệp chưa kết thúc. Hãy điều chuyển/hoàn tất trước khi xóa.")
        if row["is_admin"]:
            admin_count = c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1 AND active=1 AND deleted_at IS NULL").fetchone()[0]
            if admin_count <= 1:
                raise ValueError("Không thể xóa Admin hoạt động cuối cùng của hệ thống.")
        ts = now_str()
        deleted_username = f"__deleted_{user_id}_{datetime.now():%Y%m%d%H%M%S}"
        old_username = row["username"]
        # Soft delete để giữ nguyên lịch sử đánh giá/audit nhưng giải phóng username cho việc tạo lại.
        c.execute("UPDATE users SET username=?,full_name=?,active=0,is_admin=0,deleted_at=?,updated_at=? WHERE id=?",
                  (deleted_username, f"[Đã xóa] {row['full_name']}", ts, ts, user_id))
        c.execute("UPDATE customers SET qlkh_user_id=NULL,updated_at=? WHERE qlkh_user_id=?", (ts, user_id))
        c.commit()
    audit(actor["id"], "DELETE_USER", "user", user_id, f"Đã xóa tài khoản {old_username}; giữ row lịch sử với id={user_id}")
    return old_username


def _task_types_revision():
    with get_conn() as c:
        r=c.execute("SELECT COALESCE(MAX(updated_at),''),COUNT(*) FROM task_types").fetchone()
    return f"{r[0]}|{r[1]}"

@_cache_data(ttl=60, show_spinner=False)
def _active_task_types_cached(db_path, revision):
    return qdf("SELECT name,sla_hours FROM task_types WHERE active=1 ORDER BY id")

def active_task_types():
    return _active_task_types_cached(str(DB_PATH), _task_types_revision()).copy()


def task_sla_hours(task_type):
    d = qdf("SELECT sla_hours FROM task_types WHERE name=?", (task_type,))
    return float(d.iloc[0].sla_hours) if not d.empty else 8.0


def task_code(task_id):
    return f"TN-{int(task_id):06d}"


def visible_tasks_sql(user):
    base = '''SELECT t.id,t.task_code,c.cif,c.customer_name,s.full_name support_name,q.full_name qlkh_name,
              t.support_user_id,t.qlkh_user_id,t.request_source,t.assigned_at,t.accepted_at,t.first_accepted_at,t.returned_to_qlkh_at,t.cancelled_at,t.evaluated_at,t.last_rework_at,
              t.task_type,t.amount,t.currency,t.fx_rate,t.amount_vnd,t.start_time,t.due_time,t.end_time,t.closed_time,
              t.note,t.status,t.current_round,t.rework_count,
              e.quality_score,e.progress_score,e.comment,
              CASE WHEN t.end_time IS NOT NULL THEN ((julianday(t.end_time)-julianday(t.start_time))*24.0) ELSE NULL END duration_hours
              FROM tasks t
              JOIN customers c ON c.id=t.customer_id
              JOIN users s ON s.id=t.support_user_id
              JOIN users q ON q.id=t.qlkh_user_id
              LEFT JOIN evaluations e ON e.task_id=t.id AND e.round_no=t.current_round'''
    params = []
    if user["role"] == "Cán bộ hỗ trợ":
        base += " WHERE t.support_user_id=?"
        params.append(user["id"])
    elif user["role"] == "Cán bộ QLKH":
        base += " WHERE t.qlkh_user_id=?"
        params.append(user["id"])
    base += " ORDER BY COALESCE(t.assigned_at,t.created_at,t.start_time) DESC, c.cif ASC, t.id DESC"
    return base, params


def enrich_tasks(df):
    if df.empty:
        return df
    out = df.copy()
    out["avg_score"] = (pd.to_numeric(out["quality_score"], errors="coerce") + pd.to_numeric(out["progress_score"], errors="coerce")) / 2
    out["start_dt"] = pd.to_datetime(out["start_time"], errors="coerce")
    out["end_dt"] = pd.to_datetime(out["end_time"], errors="coerce")
    for _c in ["assigned_at","accepted_at","first_accepted_at","returned_to_qlkh_at","cancelled_at","evaluated_at","last_rework_at","closed_time"]:
        if _c in out.columns:
            out[_c + "_dt"] = pd.to_datetime(out[_c], errors="coerce")
    if "duration_hours" in out.columns:
        out["duration_minutes"] = pd.to_numeric(out["duration_hours"], errors="coerce") * 60.0
    else:
        out["duration_minutes"] = (out["end_dt"] - out["start_dt"]).dt.total_seconds() / 60.0
    # Thời gian chờ tiếp nhận: từ lúc QLKH khởi tạo/giao ban đầu đến lần CBHT tiếp nhận đầu tiên.
    if "assigned_at_dt" in out.columns and "first_accepted_at_dt" in out.columns:
        _first_accept = out["first_accepted_at_dt"]
        if "accepted_at_dt" in out.columns:
            _first_accept = _first_accept.fillna(out["accepted_at_dt"])
        out["assignment_to_accept_minutes"] = (_first_accept - out["assigned_at_dt"]).dt.total_seconds() / 60.0
    elif "assigned_at_dt" in out.columns and "accepted_at_dt" in out.columns:
        out["assignment_to_accept_minutes"] = (out["accepted_at_dt"] - out["assigned_at_dt"]).dt.total_seconds() / 60.0
    else:
        out["assignment_to_accept_minutes"] = pd.NA
    out["status_label"] = out["status"].map(STATUS_LABEL).fillna(out["status"])
    if "amount_vnd" not in out.columns:
        out["amount_vnd"] = pd.to_numeric(out.get("amount"), errors="coerce").fillna(0)
    out["amount_vnd"] = pd.to_numeric(out["amount_vnd"], errors="coerce").fillna(0)
    return out


# ---------- UI helpers ----------
def ensure_bidv_logo(max_age_days=30):
    """Tải/cache logo BIDV hiện hành trực tiếp từ website BIDV."""
    # Streamlit rerun rất thường xuyên; mỗi session chỉ thử tải mạng tối đa một lần.
    try:
        if st.session_state.get("_bidv_logo_checked"):
            return BIDV_LOGO_PATH if BIDV_LOGO_PATH.exists() else None
        st.session_state["_bidv_logo_checked"] = True
    except Exception:
        pass
    try:
        ASSET_DIR.mkdir(parents=True, exist_ok=True)
        if BIDV_LOGO_PATH.exists():
            age = now_dt().timestamp() - BIDV_LOGO_PATH.stat().st_mtime
            if age < max_age_days * 86400 and BIDV_LOGO_PATH.stat().st_size > 1000:
                return BIDV_LOGO_PATH
        headers = {
            "User-Agent": BIDV_HTTP_HEADERS.get("User-Agent", "Mozilla/5.0"),
            "Accept": "image/svg+xml,image/*,*/*;q=0.8",
            "Referer": "https://bidv.com.vn/vn/ve-bidv/thuong-hieu-nguon-nhan-luc-va-van-hoa-doanh-nghiep",
        }
        with httpx.Client(timeout=httpx.Timeout(8.0, connect=5.0), follow_redirects=True,
                          headers=headers, verify=_bidv_ssl_context(), trust_env=True, http2=False) as client:
            resp = client.get(BIDV_LOGO_URL)
            resp.raise_for_status()
            body = resp.content
            if b"<svg" not in body[:1000].lower() and b"<svg" not in body.lower():
                raise RuntimeError("BIDV không trả về SVG logo")
            BIDV_LOGO_PATH.write_bytes(body)
            return BIDV_LOGO_PATH
    except Exception:
        return BIDV_LOGO_PATH if BIDV_LOGO_PATH.exists() else None


def _logo_data_uri():
    try:
        if BIDV_LOGO_PATH.exists() and BIDV_LOGO_PATH.stat().st_size > 100:
            return "data:image/svg+xml;base64," + base64.b64encode(BIDV_LOGO_PATH.read_bytes()).decode("ascii")
    except Exception:
        pass
    fallback = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 120"><text x="28" y="80" font-family="Arial,Helvetica,sans-serif" font-weight="800" font-size="70" fill="#006B68">BIDV</text><circle cx="350" cy="58" r="25" fill="#F4B41A"/><path d="M350 22 L359 49 L388 49 L365 66 L374 94 L350 77 L326 94 L335 66 L312 49 L341 49 Z" fill="#F4B41A"/></svg>'''
    return "data:image/svg+xml;base64," + base64.b64encode(fallback.encode("utf-8")).decode("ascii")


def inject_app_icons():
    """Publish deterministic favicon/PWA metadata for browser and iOS Home Screen.

    Streamlit's ``page_icon`` covers the browser favicon, while iOS looks for an
    explicit ``apple-touch-icon`` when creating a Home Screen web clip. The
    assets are committed under ``static/`` and served by Streamlit so the icon
    does not depend on the network or on the runtime BIDV-logo cache.
    """
    icon_base = "/app/static"
    version = APP_ICON_VERSION
    st.markdown(
        f'''<link rel="icon" href="{icon_base}/favicon.ico?v={version}" sizes="any">
<link rel="icon" type="image/svg+xml" href="{icon_base}/bidv-icon.svg?v={version}">
<link rel="icon" type="image/png" sizes="192x192" href="{icon_base}/bidv-icon-192.png?v={version}">
<link rel="apple-touch-icon" sizes="180x180" href="{icon_base}/bidv-icon-180.png?v={version}">
<link rel="apple-touch-icon-precomposed" sizes="180x180" href="{icon_base}/bidv-icon-180.png?v={version}">
<link rel="manifest" href="{icon_base}/manifest.json?v={version}">
<meta name="theme-color" content="#006B68">
<meta name="apple-mobile-web-app-title" content="KHDN Apps">
<meta name="mobile-web-app-capable" content="yes">''',
        unsafe_allow_html=True,
    )


def _user_avatar_data_uri(user):
    """Return avatar as a data URI. Avatar is stored in SQLite so it follows DB backup/migration."""
    try:
        blob = user.get("avatar_blob") if isinstance(user, dict) else user["avatar_blob"]
        mime = user.get("avatar_mime") if isinstance(user, dict) else user["avatar_mime"]
        if blob and mime in {"image/png", "image/jpeg", "image/webp"}:
            return f"data:{mime};base64," + base64.b64encode(bytes(blob)).decode("ascii")
    except Exception:
        pass
    return ""


def inject_css():
    """V2.13: row-based workflow actions + Plotly dashboard + dashboard value policy + transparent BIDV branding."""
    st.markdown(r"""<style>
    :root{--bidv:#006B68;--bidv2:#00857A;--bidv3:#00A187;--gold:#F4B41A;--gold2:#FFD45A;--ink:#163B39;--muted:#64748b;--line:rgba(0,107,104,.16);--danger:#D93838;--warn:#F59E0B}
    html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],.stMainBlockContainer{width:100%!important;max-width:none!important}
     .main .block-container,.block-container,[class*="block-container"]{padding:6.05rem clamp(.78rem,1.25vw,1.35rem) 5.5rem!important;max-width:none!important;width:100%!important;overflow:visible!important;box-sizing:border-box!important}
    [data-testid="stAppViewContainer"]{overflow-y:auto;background:radial-gradient(circle at 8% 0%,rgba(0,133,122,.08),transparent 26%),linear-gradient(180deg,#F8FCFB 0%,#FFFFFF 60%)}
    [data-testid="stMain"]{overflow-y:auto}
    section[data-testid="stSidebar"]{background:#FFFFFF;border-right:1px solid rgba(0,107,104,.14);box-shadow:8px 0 28px rgba(0,107,104,.035)}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"]{display:none!important}
    div[data-testid="column"],div[data-testid="stHorizontalBlock"],div[data-testid="stVerticalBlock"],div[data-testid="stElementContainer"]{min-width:0!important;max-width:none!important}
    .page-brand-shell{display:grid;grid-template-columns:minmax(120px,165px) minmax(0,1fr);gap:14px;align-items:stretch;margin:.35rem 0 18px 0;overflow:visible!important;position:relative;z-index:1;width:100%!important;max-width:100%!important;box-sizing:border-box}
    .page-logo-wrap{min-height:122px;display:flex;align-items:center;justify-content:center;border-radius:23px;background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%);border:1.8px solid rgba(11,127,117,.18);box-shadow:0 10px 26px rgba(11,127,117,.10);padding:10px}
    .page-logo-img{max-height:76px;max-width:150px;width:100%;object-fit:contain}
    .page-hero-card{min-height:122px;display:flex;flex-direction:column;justify-content:center;padding:17px 22px;border-radius:23px;background:linear-gradient(112deg,#006B68 0%,#00857A 68%,#009F87 100%);position:relative;overflow:hidden;color:white;box-shadow:0 14px 34px rgba(11,127,117,.20);border:1px solid rgba(255,255,255,.28)}
    .page-hero-card:after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;background:linear-gradient(90deg,var(--gold),var(--gold2),transparent 82%)}
    .page-hero-card h1{position:relative;z-index:1;font-size:clamp(1.22rem,1.8vw,1.72rem);margin:0 0 7px 0;color:white;letter-spacing:-.02em;line-height:1.28;font-weight:900;white-space:normal!important;overflow:visible!important;overflow-wrap:anywhere}
    .page-hero-card p{position:relative;z-index:1;font-size:.88rem;margin:0;opacity:.96;line-height:1.55;font-weight:550;white-space:normal!important;overflow:visible!important;overflow-wrap:anywhere}
    .sidebar-logo{display:flex;align-items:center;justify-content:center;padding:4px 6px;margin:0 0 10px 0;border-radius:0;background:transparent!important;border:none!important;box-shadow:none!important}
    .sidebar-logo img{max-width:158px;max-height:58px;object-fit:contain}
    .sidebar-user-card{display:flex;align-items:center;gap:10px;margin:5px 0 8px;padding:8px 4px;border-radius:14px;background:transparent}
    .sidebar-avatar{width:46px;height:46px;border-radius:50%;object-fit:cover;border:2px solid #F4B41A;box-shadow:0 4px 12px rgba(0,107,104,.12);flex:0 0 46px}
    .sidebar-avatar-fallback{width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#006B68,#008F80);color:#fff;font-weight:900;font-size:1.05rem;border:2px solid #F4B41A;box-shadow:0 4px 12px rgba(0,107,104,.12);flex:0 0 46px}
    .sidebar-user-meta{min-width:0}.sidebar-user-name{font-weight:900;color:#143A37;line-height:1.18;overflow-wrap:anywhere}.sidebar-user-role{font-size:.75rem;color:#70807e;margin-top:3px;overflow-wrap:anywhere}
    div[class*="st-key-mainnav_"]{margin:5px 0!important}
    div[class*="st-key-mainnav_"] button{width:100%!important;min-height:46px!important;justify-content:flex-start!important;text-align:left!important;padding:0 15px!important;border-radius:15px!important;border:1.6px solid rgba(11,127,117,.22)!important;background:linear-gradient(135deg,rgba(255,255,255,.97),rgba(248,255,251,.93))!important;color:#064E47!important;font-size:.93rem!important;font-weight:850!important;box-shadow:0 5px 14px rgba(11,127,117,.06)!important}
    div[class*="st-key-mainnav_"] button:hover{border-color:var(--gold)!important;background:linear-gradient(135deg,#F8FFFB,#FFF7E6)!important;transform:translateY(-1px)}
    div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#006B68,#008F80)!important;color:#fff!important;border-color:var(--gold)!important;box-shadow:0 9px 20px rgba(11,127,117,.20)!important}
    div[class*="st-key-subnav_"] button{min-height:43px!important;border-radius:999px!important;border:1.6px solid rgba(11,127,117,.25)!important;background:#fff!important;color:#0B5F58!important;font-size:.88rem!important;font-weight:850!important;box-shadow:0 5px 14px rgba(11,127,117,.06)!important;padding:0 15px!important}
    div[class*="st-key-subnav_"] button:hover{border-color:var(--gold)!important;color:#064E47!important;background:#FFF9EA!important}
    div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#006B68,#008F80)!important;color:white!important;border-color:var(--gold)!important;box-shadow:0 8px 19px rgba(11,127,117,.20)!important}
    @keyframes opsPulse{0%,100%{box-shadow:0 7px 18px rgba(245,158,11,.18),0 0 0 0 rgba(220,38,38,.30)}50%{box-shadow:0 10px 26px rgba(220,38,38,.30),0 0 0 8px rgba(220,38,38,0)}}
    @keyframes opsRedOverlay{0%,42%,100%{opacity:0}58%,82%{opacity:.62}}
    div[class*="st-key-ops_alert_"] button,div[class*="st-key-opsaction_"] button{width:100%!important;min-height:118px!important;border-radius:18px!important;border:1.4px solid rgba(148,163,184,.24)!important;background:rgba(255,255,255,.96)!important;color:#12302d!important;justify-content:center!important;text-align:center!important;padding:12px 15px!important;box-shadow:0 6px 17px rgba(15,23,42,.055)!important;position:relative!important;overflow:hidden!important}
    div[class*="st-key-ops_alert_"] button p,div[class*="st-key-opsaction_"] button p{white-space:pre-line!important;line-height:1.30!important;font-size:.74rem!important;font-weight:850!important;margin:0!important;overflow-wrap:anywhere!important;text-align:center!important;width:100%!important;position:relative!important;z-index:2!important}
    div[class*="st-key-ops_alert_"] button:hover,div[class*="st-key-opsaction_"] button:hover{transform:translateY(-2px);border-color:var(--bidv)!important;box-shadow:0 10px 22px rgba(11,127,117,.14)!important}
    div[class*="st-key-ops_alert_hot_"] button{background:linear-gradient(135deg,#FFF6D8 0%,#FFE7A0 100%)!important;border:2px solid #F59E0B!important;color:#7C4700!important;animation:opsPulse 1.35s ease-in-out infinite!important}
    div[class*="st-key-ops_alert_hot_"] button::before,div[class*="st-key-ops_alert_danger_"] button::before{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(135deg,#EF4444,#DC2626);opacity:0;animation:opsRedOverlay 1.35s ease-in-out infinite;pointer-events:none;z-index:1}
    div[class*="st-key-ops_alert_danger_"] button{background:linear-gradient(135deg,#FFF0E5,#FFD6B5)!important;border-color:#EF4444!important;color:#7F1D1D!important;animation:opsPulse 1.10s ease-in-out infinite!important}
    div[class*="st-key-ops_alert_danger_"] button::before{animation-duration:1.10s;opacity:0}
    .kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:11px;margin:10px 0 18px}.kpi-card{min-width:0;background:rgba(255,255,255,.92);border:1px solid rgba(148,163,184,.24);border-top:4px solid var(--bidv);border-radius:17px;padding:12px 14px;box-shadow:0 5px 17px rgba(15,23,42,.05);overflow:hidden}.kpi-label{font-size:.79rem;color:#64748b;font-weight:700;line-height:1.25;white-space:normal;overflow-wrap:anywhere}.kpi-value{font-size:clamp(1.02rem,1.45vw,1.45rem);font-weight:900;color:#0B5F58;line-height:1.18;margin-top:5px;white-space:normal;overflow-wrap:anywhere;word-break:break-word}.kpi-sub{font-size:.72rem;color:#94a3b8;margin-top:4px;line-height:1.2;white-space:normal;overflow-wrap:anywhere}
    div[data-testid="stMetric"]{min-width:0!important;overflow:hidden!important;background:rgba(255,255,255,.9);border:1px solid rgba(148,163,184,.25);border-radius:16px;padding:11px 13px;box-shadow:0 4px 16px rgba(15,23,42,.04)}div[data-testid="stMetricLabel"] p{font-size:.78rem!important;color:#64748b!important;white-space:normal!important;overflow-wrap:anywhere!important}div[data-testid="stMetricValue"]{font-size:clamp(.96rem,1.35vw,1.25rem)!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:break-word!important}
    .tre-section{border:1px solid rgba(11,127,117,.18);border-radius:19px;padding:13px 15px;background:rgba(255,255,255,.82);box-shadow:0 7px 22px rgba(11,127,117,.06);margin:9px 0 14px}.section-note{font-size:.83rem;color:#56666a;background:rgba(234,247,241,.78);border-left:5px solid var(--bidv);padding:8px 11px;border-radius:10px;margin:7px 0 11px}.muted{color:#68737d;font-size:.88rem}.badge{display:inline-block;padding:3px 8px;border-radius:999px;background:#eef8f4;font-size:.82rem;margin-right:4px}

    .task-chip-row{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 12px}.task-chip{display:inline-flex;align-items:center;padding:6px 9px;border-radius:10px;font-size:.82rem;font-weight:800;border:1px solid rgba(15,23,42,.08)}.chip-kh{background:#EAF2FF;color:#164E9A}.chip-task{background:#FFF3CD;color:#7A4B00}.chip-value{background:#E7F7EF;color:#0B684F}.chip-time{background:#FFF0E5;color:#9A4300}.chip-support{background:#F1EAFE;color:#5A3A91}.chip-qlkh{background:#E6F7F5;color:#08645D}.chip-status{background:#FCE8EC;color:#9B2945}
    div[data-testid="stDataFrame"]{border-radius:13px!important;overflow:hidden!important;border:1px solid rgba(11,127,117,.16)!important}div[data-testid="stDataFrame"] [role="row"]{cursor:pointer!important}
    .task-pick-alert{padding:10px 13px;background:linear-gradient(135deg,#FFF8DE,#FFF0B3);border:2px solid var(--gold);border-left:8px solid var(--gold);border-radius:11px;margin:7px 0 9px;font-weight:850;color:#7c4a00;box-shadow:0 6px 16px rgba(245,178,27,.12)}.required-error{padding:7px 10px;background:#fff0f0;border-left:5px solid #e03131;border-radius:8px;color:#b42318;margin:4px 0 8px;font-weight:700}.open-list-note{padding:9px 12px;border-radius:12px;background:linear-gradient(135deg,#F0FBF7,#FFF9E9);border:1px solid rgba(11,127,117,.18);color:#365b55;font-size:.84rem;margin:7px 0 11px}
    div.stButton>button,.stDownloadButton>button{border-radius:999px;border:1px solid rgba(11,127,117,.35);background:linear-gradient(135deg,#006B68,#008F80);color:#fff;font-weight:750}div.stButton>button:hover,.stDownloadButton>button:hover{border-color:#F5B21B;color:#fff;box-shadow:0 0 0 3px rgba(245,178,27,.16)}
    div[data-testid="stDataFrame"]{border:1px solid rgba(11,127,117,.12);border-radius:13px;overflow:hidden}div[data-testid="stDataFrame"] [role="columnheader"]{font-weight:900!important;color:#064E47!important}div[data-testid="stExpander"]{border:1px solid rgba(11,127,117,.18)!important;border-radius:14px!important;background:rgba(255,255,255,.72)!important}
    .st-key-accept_task [data-baseweb="select"]>div,.st-key-finish_task [data-baseweb="select"]>div,.st-key-edit_note_task [data-baseweb="select"]>div,.st-key-eval_task [data-baseweb="select"]>div,.st-key-leader_manage_task [data-baseweb="select"]>div,div[class*="st-key-accept_task"] [data-baseweb="select"]>div,div[class*="st-key-finish_task"] [data-baseweb="select"]>div,div[class*="st-key-edit_note_task"] [data-baseweb="select"]>div,div[class*="st-key-eval_task"] [data-baseweb="select"]>div,div[class*="st-key-leader_manage_task"] [data-baseweb="select"]>div{background:linear-gradient(135deg,#FFF7D1,#FFE89A)!important;border:3px solid #F5B21B!important;border-radius:10px!important;box-shadow:0 0 0 3px rgba(245,178,27,.16),0 4px 11px rgba(0,0,0,.07)!important;font-weight:800!important}
    /* V2.9: logout red + pending work cards use a dedicated keyed container so animation is reliable across Streamlit versions. */
    div[class*="st-key-logout_btn"] button{background:linear-gradient(135deg,#DC2626,#EF4444)!important;border:1.5px solid #B91C1C!important;color:#fff!important;font-weight:850!important;box-shadow:0 7px 18px rgba(220,38,38,.18)!important}
    div[class*="st-key-logout_btn"] button:hover{background:linear-gradient(135deg,#B91C1C,#DC2626)!important;border-color:#7F1D1D!important;box-shadow:0 0 0 3px rgba(239,68,68,.18),0 8px 20px rgba(220,38,38,.22)!important}
    /* V2.16: destructive workflow actions are always red: trả lại / hủy / xóa. */
    div[class*="st-key-return_pending_btn_"] button,
    div[class*="st-key-return_work_btn_"] button,
    div[class*="st-key-"][class*="_cancel_"] button,
    div[class*="st-key-delete_user_"] button{background:linear-gradient(135deg,#DC2626,#EF4444)!important;border:1.6px solid #B91C1C!important;color:#fff!important;font-weight:850!important;box-shadow:0 7px 18px rgba(220,38,38,.18)!important}
    div[class*="st-key-return_pending_btn_"] button:hover,
    div[class*="st-key-return_work_btn_"] button:hover,
    div[class*="st-key-"][class*="_cancel_"] button:hover,
    div[class*="st-key-delete_user_"] button:hover{background:linear-gradient(135deg,#991B1B,#DC2626)!important;border-color:#7F1D1D!important;box-shadow:0 0 0 3px rgba(239,68,68,.18),0 8px 20px rgba(220,38,38,.22)!important}
    @keyframes opsAttentionBlink{
      0%,100%{background:linear-gradient(135deg,#FFF3C4,#FFD873);color:#7C4700;border-color:#F59E0B;box-shadow:0 7px 18px rgba(245,158,11,.24),0 0 0 0 rgba(245,158,11,.30);transform:translateY(0) scale(1)}
      50%{background:linear-gradient(135deg,#FF6B5F,#DC2626);color:#FFFFFF;border-color:#B91C1C;box-shadow:0 12px 28px rgba(220,38,38,.34),0 0 0 8px rgba(220,38,38,0);transform:translateY(-2px) scale(1.018)}
    }
    div[class*="st-key-ops_alert_hot_"] button,div[class*="st-key-ops_alert_idle_"] button{width:100%!important;min-height:118px!important;border-radius:18px!important;justify-content:center!important;text-align:center!important;padding:12px 15px!important;font-weight:900!important}
    div[class*="st-key-ops_alert_hot_"] button p,div[class*="st-key-ops_alert_idle_"] button p{white-space:pre-line!important;line-height:1.30!important;font-size:.74rem!important;margin:0!important;overflow-wrap:anywhere!important;text-align:center!important;width:100%!important}
    div[class*="st-key-ops_alert_idle_"] button{background:#FFFFFF!important;color:#12302d!important;border:1.5px solid rgba(11,127,117,.20)!important;box-shadow:0 6px 17px rgba(15,23,42,.055)!important}
    div[class*="st-key-ops_alert_idle_"] button:hover{background:linear-gradient(135deg,#FFFFFF,#F4FBF8)!important;color:#064E47!important;border-color:#0B7F75!important}
    div[class*="st-key-ops_alert_hot_"] button{animation:opsAttentionBlink .95s ease-in-out infinite!important}
    div[class*="st-key-ops_alert_hot_"] button:hover{animation-play-state:paused!important;background:linear-gradient(135deg,#DC2626,#B91C1C)!important;color:#fff!important}
    /* V2.10: ô tìm CIF/Tên KH lớn hơn 30%, nổi bật hơn. */
    div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input{min-height:54px!important;font-size:1.08rem!important;font-weight:750!important;background:linear-gradient(135deg,#FFFBEA,#F1FBF7)!important;border:2px solid #F5B21B!important;border-radius:13px!important;color:#12302d!important;box-shadow:0 0 0 3px rgba(245,178,27,.11),0 7px 18px rgba(11,127,117,.08)!important}
    div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input:focus{border-color:#0B7F75!important;box-shadow:0 0 0 4px rgba(11,127,117,.16),0 8px 20px rgba(11,127,117,.10)!important}
    div[class*="st-key-customer_search_"] label p{font-size:1rem!important;font-weight:900!important;color:#064E47!important}
    /* V2.11 global anti-overflow */
    h1,h2,h3,h4,p,label,span{max-width:100%;overflow-wrap:anywhere}
    div[data-testid="stDataFrame"],div[data-testid="stTable"]{max-width:100%!important;overflow:auto!important}div[data-testid="stVegaLiteChart"],div[data-testid="stAltairChart"],div[data-testid="stPlotlyChart"]{max-width:100%!important;overflow-x:auto!important;overflow-y:visible!important}
    div[data-testid="stVegaLiteChart"],div[data-testid="stAltairChart"]{width:100%!important;min-height:250px!important;padding:4px 2px 14px!important;box-sizing:border-box!important} div[data-testid="stVegaLiteChart"]>div,div[data-testid="stAltairChart"]>div{width:100%!important;overflow:visible!important}
    div[data-testid="stVegaLiteChart"]>div,div[data-testid="stVegaLiteChart"] canvas,div[data-testid="stVegaLiteChart"] svg,div[data-testid="stAltairChart"]>div,div[data-testid="stAltairChart"] svg{max-width:100%!important}
    [data-baseweb="select"]>div,input,textarea{max-width:100%!important;box-sizing:border-box!important}
    div[data-testid="stDataFrame"] [role="gridcell"],div[data-testid="stDataFrame"] [role="columnheader"]{font-size:.82rem!important}
    @media(max-width:1260px){
      div[data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:.8rem!important}
      div[data-testid="column"]{flex:1 1 310px!important;min-width:280px!important;width:auto!important}
    }
    @media(max-width:1100px){.page-brand-shell{grid-template-columns:140px minmax(0,1fr)}.page-hero-card{padding:15px 18px}.page-hero-card:after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;background:linear-gradient(90deg,var(--gold),var(--gold2),transparent 82%)}
    .page-hero-card h1{position:relative;z-index:1;font-size:1.32rem}.page-hero-card p{position:relative;z-index:1;font-size:.81rem}.main .block-container,.block-container,[class*="block-container"]{padding-top:5.7rem!important}}
    @media(max-width:900px){.page-brand-shell{grid-template-columns:122px minmax(0,1fr)}div[class*="st-key-ops_alert_"] button,div[class*="st-key-opsaction_"] button{min-height:104px!important}.page-logo-img{max-width:110px}.main .block-container,.block-container,[class*="block-container"]{padding-top:5.9rem!important}}
    @media(max-width:760px){.page-brand-shell{grid-template-columns:1fr}.page-logo-wrap{min-height:68px}.page-logo-img{max-height:48px}.page-hero-card{min-height:98px}.main .block-container,.block-container,[class*="block-container"]{padding:6rem .6rem 5rem!important}.kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}div[data-testid="column"]{min-width:100%!important;flex-basis:100%!important}}
    @media(max-width:520px){.kpi-grid{grid-template-columns:1fr}.page-hero-card:after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;background:linear-gradient(90deg,var(--gold),var(--gold2),transparent 82%)}
    .page-hero-card h1{position:relative;z-index:1;font-size:1.16rem}.page-hero-card p{position:relative;z-index:1;font-size:.78rem}}
    
    /* V2.17 - tinh chỉnh theo ngôn ngữ thị giác BIDV: emerald + mai vàng, white-space rộng, chuyển động nhẹ */
    *{scrollbar-color:rgba(0,107,104,.35) transparent}
    button,input,textarea,[data-baseweb="select"]>div{transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease,background-color .18s ease!important}
    div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,div[data-testid="stTextArea"] textarea{border-radius:12px!important;border:1px solid rgba(0,107,104,.18)!important;background:#FBFDFC!important}
    div[data-testid="stTextInput"] input:focus,div[data-testid="stNumberInput"] input:focus,div[data-testid="stTextArea"] textarea:focus{border-color:var(--bidv)!important;box-shadow:0 0 0 3px rgba(244,180,26,.20)!important}
    .tre-section{border-color:rgba(0,107,104,.14)!important;background:#FFFFFF!important;box-shadow:0 8px 24px rgba(0,107,104,.055)!important}
    .section-note{background:linear-gradient(90deg,#F0FAF7,#FFF9E8)!important;border-left-color:var(--gold)!important;color:#294E4B!important}
    .annual-benchmark-note{padding:12px 14px;margin:8px 0 16px;border-radius:14px;border:1px solid rgba(0,107,104,.16);background:linear-gradient(90deg,#F4FBF9 0%,#FFF9EA 100%);color:#244744;line-height:1.55}
    .bidv-table-wrap{width:100%;overflow:auto;border:1px solid rgba(0,107,104,.14);border-radius:14px;background:#fff;box-shadow:0 5px 18px rgba(0,107,104,.04)}
    .perf-period{border:1px solid rgba(11,127,117,.18);border-radius:18px;padding:14px 15px;margin:10px 0 15px;background:rgba(255,255,255,.92);box-shadow:0 7px 20px rgba(11,127,117,.055)}
    .perf-period-title{font-size:1rem;font-weight:900;color:#143A37;margin-bottom:10px;overflow-wrap:anywhere}
    .perf-trend-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(205px,1fr));gap:10px}
    .perf-trend-card{border:1px solid rgba(148,163,184,.25);border-radius:15px;padding:11px 12px;background:#fff;min-width:0}
    .perf-trend-label{font-size:.78rem;color:#64748b;font-weight:800;line-height:1.25}
    .perf-trend-value{font-size:1.12rem;font-weight:950;color:#183B38;margin:5px 0 4px;overflow-wrap:anywhere}
    .perf-trend-detail{font-size:.79rem;font-weight:850;line-height:1.35;overflow-wrap:anywhere}
    .trend-good{color:#08785E!important;background:linear-gradient(180deg,#F0FBF7,#FFFFFF)!important;border-color:rgba(8,120,94,.28)!important}
    .trend-bad{color:#C62828!important;background:linear-gradient(180deg,#FFF1F1,#FFFFFF)!important;border-color:rgba(198,40,40,.28)!important}
    .trend-neutral{color:#64748b!important;background:linear-gradient(180deg,#F8FAFC,#FFFFFF)!important}
    .annual-benchmark-note{border:1px solid rgba(11,127,117,.18);border-radius:14px;padding:11px 13px;margin:8px 0 12px;background:#fff;line-height:1.55}
    table.bidv-html-table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.82rem}
    table.bidv-html-table th{position:sticky;top:0;z-index:1;background:#006B68;color:#fff;padding:10px 9px;text-align:left;font-weight:800;border-bottom:3px solid #F4B41A;white-space:normal;overflow-wrap:anywhere}
    table.bidv-html-table td{padding:9px;border-bottom:1px solid #E6EFED;white-space:normal;overflow-wrap:anywhere;vertical-align:top}
    table.bidv-html-table tbody tr:hover{background:#F5FBF9}
    div[data-testid="stDataFrame"]{border-radius:14px;overflow:hidden;border:1px solid rgba(0,107,104,.12);box-shadow:0 4px 14px rgba(0,107,104,.035)}
    @media(max-width:900px){.main .block-container,.block-container,[class*="block-container"]{padding-top:6.45rem!important}.page-brand-shell{grid-template-columns:1fr}.page-logo-wrap{display:none}.page-hero-card{min-height:112px}}

    /* V2.23 responsive layout: iPhone/iOS/Android + desktop */
    input, textarea, select {font-size:16px!important;} /* prevents iOS focus zoom */
    [data-testid="stDataFrame"], [data-testid="stDataEditor"]{max-width:100%!important;overflow-x:auto!important;overscroll-behavior-x:contain!important}
    [data-testid="stPlotlyChart"]{max-width:100%!important;overflow:hidden!important}
    @media(max-width:768px){
      html,body,.stApp{font-size:15px!important}
      .main .block-container,.block-container,[class*="block-container"]{padding:5.15rem .58rem 5rem!important}
      section[data-testid="stSidebar"]{width:min(88vw,320px)!important}
      [data-testid="stHorizontalBlock"]{display:flex!important;flex-wrap:wrap!important;gap:.55rem!important}
      div[data-testid="column"]{flex:1 1 calc(50% - .55rem)!important;min-width:155px!important;width:auto!important}
      .page-brand-shell{grid-template-columns:1fr!important;gap:8px!important;margin:.15rem 0 12px!important}
      .page-logo-wrap{display:none!important}
      .page-hero-card{min-height:88px!important;padding:13px 14px!important;border-radius:17px!important}
      .page-hero-card h1{font-size:1.18rem!important;line-height:1.18!important;white-space:normal!important}
      .page-hero-card p{font-size:.80rem!important;line-height:1.35!important;white-space:normal!important}
      .kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:.55rem!important}
      .kpi-card{padding:10px!important;min-height:76px!important}
      div[class*="st-key-ops_alert_"] button,div[class*="st-key-opsaction_"] button{min-height:92px!important;padding:9px 8px!important;border-radius:15px!important}
      div[class*="st-key-ops_alert_"] button p,div[class*="st-key-opsaction_"] button p{font-size:.72rem!important;line-height:1.25!important}
      div.stButton>button,button[kind="primary"],button[kind="secondary"]{min-height:44px!important;white-space:normal!important;line-height:1.15!important;padding:.55rem .70rem!important}
      [data-testid="stMetric"]{min-height:72px!important;padding:8px 9px!important}
      [data-testid="stMetricValue"]{font-size:1.02rem!important}
      [data-testid="stMetricLabel"] p{font-size:.72rem!important;white-space:normal!important}
      .task-chip,.field-chip{font-size:.74rem!important;line-height:1.28!important;white-space:normal!important}
      h1{font-size:1.45rem!important} h2{font-size:1.22rem!important} h3{font-size:1.05rem!important}
      [data-baseweb="select"]>div,[data-baseweb="input"]>div{min-height:44px!important}
      .stDownloadButton button{min-height:44px!important;width:100%!important}
    }
    @media(max-width:480px){
      .main .block-container,.block-container,[class*="block-container"]{padding-left:.42rem!important;padding-right:.42rem!important}
      div[data-testid="column"]{flex:1 1 100%!important;min-width:100%!important}
      .kpi-grid{grid-template-columns:1fr!important}
      div[class*="st-key-ops_alert_"] button,div[class*="st-key-opsaction_"] button{min-height:82px!important}
      .page-hero-card{padding:12px!important;min-height:82px!important}
      .page-hero-card h1{font-size:1.08rem!important}
      .page-hero-card p{font-size:.76rem!important}
    }

    /* Theme-safe controls: Dark is the default; every editable control keeps a high-contrast foreground/background pair. */
    :root{color-scheme:dark;--khdn-input-bg:#17312F;--khdn-input-text:#F4FFFC;--khdn-input-placeholder:#B7D5D0;--khdn-input-border:rgba(164,232,219,.68)}
    html[data-theme="dark"],body[data-theme="dark"],[data-theme="dark"],[data-testid="stAppViewContainer"][data-theme="dark"],html[data-baseweb-theme="dark"],body[data-baseweb-theme="dark"],.dark{color-scheme:dark;--khdn-input-bg:#17312F;--khdn-input-text:#F4FFFC;--khdn-input-placeholder:#B7D5D0;--khdn-input-border:rgba(164,232,219,.68)}
    html[data-theme="light"],body[data-theme="light"],html[data-baseweb-theme="light"],body[data-baseweb-theme="light"]{color-scheme:light;--khdn-input-bg:#FFFFFF;--khdn-input-text:#12302D;--khdn-input-placeholder:#5E7773;--khdn-input-border:rgba(0,107,104,.30)}
    div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,div[data-testid="stTextArea"] textarea,div[data-baseweb="input"] input,div[data-baseweb="textarea"] textarea,[data-baseweb="select"]>div,[data-baseweb="select"] input{color:var(--khdn-input-text)!important;-webkit-text-fill-color:var(--khdn-input-text)!important;background:var(--khdn-input-bg)!important;border-color:var(--khdn-input-border)!important;caret-color:var(--khdn-input-text)!important}
    div[data-testid="stTextInput"] input::placeholder,div[data-testid="stNumberInput"] input::placeholder,div[data-testid="stTextArea"] textarea::placeholder,div[data-baseweb="input"] input::placeholder,div[data-baseweb="textarea"] textarea::placeholder{color:var(--khdn-input-placeholder)!important;-webkit-text-fill-color:var(--khdn-input-placeholder)!important;opacity:1!important}
    [data-baseweb="select"] [role="option"],[data-baseweb="popover"] [role="option"]{color:var(--khdn-input-text)!important;background:var(--khdn-input-bg)!important}
    [data-theme="dark"] label,[data-theme="dark"] [data-testid="stMarkdownContainer"],html[data-theme="dark"] label,body[data-theme="dark"] label{color:#F4FFFC!important}
    @media(prefers-color-scheme:dark){
      /* Keep the browser's native dark form controls legible even when the app menu has not set a DOM theme attribute. */
      div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,div[data-testid="stTextArea"] textarea,div[data-baseweb="input"] input,div[data-baseweb="textarea"] textarea,[data-baseweb="select"]>div,[data-baseweb="select"] input{color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;background:#17312F!important}
    }
    div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input{background:#17312F!important;color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;border:2px solid #A4E8DB!important;box-shadow:0 0 0 3px rgba(164,232,219,.13),0 7px 18px rgba(0,0,0,.25)!important}
    div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input:focus{border-color:#8FE5D4!important;box-shadow:0 0 0 4px rgba(143,229,212,.22),0 8px 20px rgba(0,0,0,.28)!important}
    div[class*="st-key-customer_search_"] label p{color:#F4FFFC!important}
    html[data-theme="light"] div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input,body[data-theme="light"] div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input,html[data-baseweb-theme="light"] div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input,body[data-baseweb-theme="light"] div[class*="st-key-customer_search_"] [data-testid="stTextInput"] input{background:linear-gradient(135deg,#FFFBEA,#F1FBF7)!important;color:#12302D!important;-webkit-text-fill-color:#12302D!important;border-color:#F5B21B!important;box-shadow:0 0 0 3px rgba(245,178,27,.11),0 7px 18px rgba(11,127,117,.08)!important}
    html[data-theme="light"] div[class*="st-key-customer_search_"] label p,body[data-theme="light"] div[class*="st-key-customer_search_"] label p,html[data-baseweb-theme="light"] div[class*="st-key-customer_search_"] label p,body[data-baseweb-theme="light"] div[class*="st-key-customer_search_"] label p{color:#064E47!important}
    html[data-theme="dark"] [data-baseweb="select"]>div,body[data-theme="dark"] [data-baseweb="select"]>div,html[data-baseweb-theme="dark"] [data-baseweb="select"]>div,body[data-baseweb-theme="dark"] [data-baseweb="select"]>div{background:#17312F!important;color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;border-color:#A4E8DB!important}
    html[data-theme="dark"] div[data-testid="stTextInput"] input,html[data-theme="dark"] div[data-testid="stNumberInput"] input,html[data-theme="dark"] div[data-testid="stTextArea"] textarea,html[data-theme="dark"] div[data-baseweb="input"] input,html[data-theme="dark"] div[data-baseweb="textarea"] textarea,html[data-theme="dark"] [data-baseweb="select"] input,body[data-theme="dark"] div[data-testid="stTextInput"] input,body[data-theme="dark"] div[data-testid="stNumberInput"] input,body[data-theme="dark"] div[data-testid="stTextArea"] textarea,body[data-theme="dark"] div[data-baseweb="input"] input,body[data-theme="dark"] div[data-baseweb="textarea"] textarea,body[data-theme="dark"] [data-baseweb="select"] input{background:#17312F!important;color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;caret-color:#F4FFFC!important}
    html[data-theme="dark"] div[class*="st-key-"] [data-baseweb="select"]>div,body[data-theme="dark"] div[class*="st-key-"] [data-baseweb="select"]>div,html[data-baseweb-theme="dark"] div[class*="st-key-"] [data-baseweb="select"]>div,body[data-baseweb-theme="dark"] div[class*="st-key-"] [data-baseweb="select"]>div{background:#17312F!important;color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;border-color:#A4E8DB!important}

    /* V2.24: coherent Dark shell and readable content.  The legacy visual rules above
       intentionally remain for Light-era semantic accents, but the application shell,
       surfaces, labels and controls must always have a dark/high-contrast pair. */
    :root,html,body,#root,.stApp{color-scheme:dark!important;background:#0E1F1E!important;color:#F4FFFC!important}
    [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"]>div,
    [data-testid="stMain"], [data-testid="stMainBlockContainer"],
    .main, section.main, .block-container{background-color:transparent!important;color:#F4FFFC!important}
    [data-testid="stAppViewContainer"]{background:radial-gradient(circle at 8% 0%,rgba(73,186,167,.18),transparent 28%),linear-gradient(180deg,#102B29 0%,#0E1F1E 64%,#091615 100%)!important}
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"]{background:transparent!important;color:#F4FFFC!important}
    section[data-testid="stSidebar"], [data-testid="stSidebar"], section[data-testid="stSidebar"]>div,
    [data-testid="stSidebar"]>div:first-child{background:linear-gradient(180deg,#0B1A19 0%,#0E2422 100%)!important;color:#F4FFFC!important;border-right:1px solid rgba(164,232,219,.22)!important;box-shadow:8px 0 28px rgba(0,0,0,.28)!important}
    .page-logo-wrap{background:linear-gradient(180deg,#163A37 0%,#102A28 100%)!important;border-color:rgba(164,232,219,.36)!important;box-shadow:0 10px 26px rgba(0,0,0,.28)!important}
    .sidebar-logo,.sidebar-user-card{background:transparent!important;color:#F4FFFC!important}
    .sidebar-user-name{color:#F4FFFC!important}.sidebar-user-role{color:#B7D5D0!important}
    .page-hero-card,.page-hero-card h1,.page-hero-card p{color:#FFFFFF!important}

    /* Streamlit text, labels and helper copy.  Avoid changing SVG/canvas plot colors. */
    [data-testid="stAppViewContainer"] h1,[data-testid="stAppViewContainer"] h2,
    [data-testid="stAppViewContainer"] h3,[data-testid="stAppViewContainer"] h4,
    [data-testid="stAppViewContainer"] h5,[data-testid="stAppViewContainer"] h6,
    [data-testid="stAppViewContainer"] p,[data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] legend,
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"],
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"],
    [data-testid="stAppViewContainer"] [data-testid="stWidgetLabel"] p,
    [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"]{
      color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important
    }
    [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] *{color:#B7D5D0!important;-webkit-text-fill-color:#B7D5D0!important}
    [data-testid="stAppViewContainer"] [data-testid="stHelp"],
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] small{color:#B7D5D0!important}

    /* Dark surfaces for all custom cards and Streamlit containers that were white in the Light theme. */
    .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,
    .bidv-table-wrap,[data-testid="stMetric"],[data-testid="stExpander"],
    [data-testid="stExpanderDetails"],[data-testid="stAlert"]{
      background:#17312F!important;color:#F4FFFC!important;border-color:rgba(164,232,219,.28)!important;box-shadow:0 8px 24px rgba(0,0,0,.22)!important
    }
    .kpi-label,.perf-trend-label{color:#B7D5D0!important}.kpi-value,.perf-period-title,.perf-trend-value{color:#F4FFFC!important}
    .kpi-sub,.perf-trend-detail{color:#B7D5D0!important}
    .section-note{background:linear-gradient(90deg,#163A37,#1D352E)!important;color:#E8FFFA!important;border-left-color:#F4B41A!important}
    .section-note *{color:#E8FFFA!important}
    .task-pick-alert{background:linear-gradient(135deg,#4E3C12,#3A2E11)!important;color:#FFE9A6!important;border-color:#F4B41A!important}
    .required-error{background:#421F23!important;color:#FFD3D8!important;border-left-color:#EF4444!important}
    .open-list-note{background:linear-gradient(135deg,#163A37,#2A3320)!important;color:#D7FFF5!important;border-color:rgba(164,232,219,.30)!important}
    .perf-trend-card{background:#17312F!important}.trend-good{background:linear-gradient(180deg,#163C35,#17312F)!important;color:#75E0C7!important}.trend-bad{background:linear-gradient(180deg,#432528,#301D21)!important;color:#FFB4B9!important}.trend-neutral{background:#17312F!important;color:#D5E8E4!important}

    /* Main navigation and idle action cards. */
    div[class*="st-key-mainnav_"] button,div[class*="st-key-subnav_"] button,
    div[class*="st-key-ops_alert_idle_"] button{
      background:linear-gradient(135deg,#173A37,#15302E)!important;color:#F4FFFC!important;border-color:rgba(164,232,219,.42)!important;box-shadow:0 6px 17px rgba(0,0,0,.24)!important
    }
    div[class*="st-key-mainnav_"] button:hover,div[class*="st-key-subnav_"] button:hover,
    div[class*="st-key-ops_alert_idle_"] button:hover{background:linear-gradient(135deg,#20514B,#1A3D39)!important;color:#FFFFFF!important;border-color:#F4B41A!important}
    div[class*="st-key-ops_alert_idle_"] button p{color:#F4FFFC!important}

    /* Editable controls: dark field, light text, visible mint border. */
    div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea,div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea,[data-baseweb="select"]>div,
    [data-baseweb="select"] input,[data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input{
      background:#17312F!important;color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important;border-color:#A4E8DB!important;caret-color:#F4FFFC!important
    }
    div[data-testid="stTextInput"] input::placeholder,div[data-testid="stNumberInput"] input::placeholder,
    div[data-testid="stTextArea"] textarea::placeholder,div[data-baseweb="input"] input::placeholder,
    div[data-baseweb="textarea"] textarea::placeholder{color:#B7D5D0!important;-webkit-text-fill-color:#B7D5D0!important;opacity:1!important}
    [data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],[data-baseweb="popover"]>div,
    [data-baseweb="menu"]>div,[role="option"]{background:#17312F!important;color:#F4FFFC!important}
    [data-baseweb="popover"] *,[data-baseweb="menu"] *,[role="listbox"] *,[role="option"] *{color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important}
    [data-testid="stCheckbox"] label,[data-testid="stRadio"] label,[data-testid="stSelectbox"] label,
    [data-testid="stMultiSelect"] label,[data-testid="stTextInput"] label,
    [data-testid="stNumberInput"] label,[data-testid="stTextArea"] label,
    [data-testid="stDateInput"] label,[data-testid="stTimeInput"] label{color:#F4FFFC!important;-webkit-text-fill-color:#F4FFFC!important}

    /* Dark tables retain the app's emerald/gold headers while keeping body text readable. */
    .bidv-table-wrap{background:#122624!important}
    table.bidv-html-table{background:#122624!important;color:#F4FFFC!important}
    table.bidv-html-table td{background:#122624!important;color:#EAFBF7!important;border-bottom-color:rgba(164,232,219,.20)!important}
    table.bidv-html-table tbody tr:hover{background:#1D403C!important}
    div[data-testid="stDataFrame"],div[data-testid="stTable"]{background:#122624!important;border-color:rgba(164,232,219,.26)!important}
    div[data-testid="stDataFrame"] [role="gridcell"],div[data-testid="stDataFrame"] [role="columnheader"]{background:#17312F!important;color:#F4FFFC!important;border-color:rgba(164,232,219,.20)!important}

    /* Buttons remain legible in Dark; semantic danger/hot actions keep their alert colors. */
    div.stButton>button,.stDownloadButton>button,button[kind="secondary"]{background:linear-gradient(135deg,#1A4C47,#126D62)!important;color:#FFFFFF!important;border-color:rgba(164,232,219,.48)!important}
    div.stButton>button:hover,.stDownloadButton>button:hover,button[kind="secondary"]:hover{background:linear-gradient(135deg,#26796D,#1A8D7D)!important;color:#FFFFFF!important;border-color:#F4B41A!important}
    div[class*="st-key-logout_btn"] button,
    div[class*="st-key-return_pending_btn_"] button,
    div[class*="st-key-return_work_btn_"] button,
    div[class*="st-key-"][class*="_cancel_"] button,
    div[class*="st-key-delete_user_"] button{background:linear-gradient(135deg,#DC2626,#EF4444)!important;color:#FFFFFF!important;border-color:#B91C1C!important}
    div[class*="st-key-ops_alert_hot_"] button{color:#7C4700!important}
    div[class*="st-key-ops_alert_danger_"] button{color:#7F1D1D!important}

    /* V2.27: the primary QLKH create action is intentionally yellow for fast
       recognition against the Dark shell. */
    div[class*="st-key-subnav_qlkh_create"] button,
    div[class*="st-key-subnav_qlkh_create"] button[kind="primary"],
    div[class*="st-key-subnav_qlkh_create"] button[data-testid="stBaseButton-primary"]{
      background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
      border-color:#FFF0A6!important;box-shadow:0 8px 20px rgba(244,180,26,.34)!important
    }
    div[class*="st-key-subnav_qlkh_create"] button:hover{
      background:linear-gradient(135deg,#FFD45A 0%,#FFE99B 100%)!important;
      color:#201B0A!important;-webkit-text-fill-color:#201B0A!important;border-color:#FFF7D1!important
    }

    /* Native Streamlit already animates the sidebar; keep that transition
       smooth on touch devices and make the collapse affordance easy to hit. */
    section[data-testid="stSidebar"]{transition:transform .30s cubic-bezier(.22,.61,.36,1),width .30s cubic-bezier(.22,.61,.36,1),box-shadow .30s ease!important;will-change:transform,width}
    [data-testid="stSidebarCollapseButton"] button,[data-testid="stExpandSidebarButton"]{min-width:42px!important;min-height:42px!important;border-radius:12px!important}
    @media(max-width:768px){
      section[data-testid="stSidebar"]{touch-action:pan-y;overscroll-behavior-x:contain}
      .main .block-container,.block-container,[class*="block-container"]{padding:3.85rem .42rem 2.65rem!important}
      [data-testid="stVerticalBlock"]{gap:.34rem!important}
      [data-testid="stElementContainer"]{margin-bottom:.05rem!important}

      /* Five workflow cards use a compact two-column grid on phones. */
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"]{
        display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
        gap:.42rem!important;align-items:stretch!important;overflow:visible!important
      }
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"]>div[data-testid="column"]{
        flex:none!important;width:auto!important;min-width:0!important;padding:0!important
      }
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_alert_"]),
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-opsaction_"]){
        display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
        gap:.42rem!important;align-items:stretch!important;overflow:visible!important
      }
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_alert_"])>div[data-testid="column"],
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-opsaction_"])>div[data-testid="column"]{
        flex:none!important;width:auto!important;min-width:0!important;padding:0!important
      }
      div[class*="st-key-ops_alert_"] button,div[class*="st-key-opsaction_"] button{
        min-height:68px!important;padding:7px 5px!important;border-radius:13px!important
      }
      div[class*="st-key-ops_alert_"] button p,div[class*="st-key-opsaction_"] button p,
      div[class*="st-key-ops_alert_"] button [data-testid="stMarkdownContainer"],
      div[class*="st-key-opsaction_"] button [data-testid="stMarkdownContainer"]{
        font-size:.68rem!important;line-height:1.14!important
      }

      /* The four QLKH tabs stay in one horizontally swipeable row. */
      div[class*="st-key-subnav_"][class*="_row"] [data-testid="stHorizontalBlock"]{
        display:flex!important;flex-wrap:nowrap!important;gap:.38rem!important;
        overflow-x:auto!important;overflow-y:visible!important;scroll-snap-type:x proximity;
        scrollbar-width:none!important;-ms-overflow-style:none!important
      }
      div[class*="st-key-subnav_"][class*="_row"] [data-testid="stHorizontalBlock"]::-webkit-scrollbar{display:none!important}
      div[class*="st-key-subnav_"][class*="_row"] [data-testid="stHorizontalBlock"]>div[data-testid="column"]{
        flex:0 0 auto!important;width:auto!important;min-width:max-content!important;padding:0!important;scroll-snap-align:start
      }
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-subnav_"]){
        display:flex!important;flex-wrap:nowrap!important;gap:.38rem!important;
        overflow-x:auto!important;overflow-y:visible!important;scroll-snap-type:x proximity;
        scrollbar-width:none!important;-ms-overflow-style:none!important
      }
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-subnav_"])::-webkit-scrollbar{display:none!important}
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-subnav_"])>div[data-testid="column"]{
        flex:0 0 auto!important;width:auto!important;min-width:max-content!important;padding:0!important;scroll-snap-align:start
      }
      div[class*="st-key-subnav_"] button{
        min-height:38px!important;padding:0 10px!important;font-size:.73rem!important;
        line-height:1.1!important;white-space:nowrap!important
      }
      .kpi-grid{gap:.42rem!important}.kpi-card{min-height:64px!important;padding:8px!important}
      [data-testid="stMetric"]{min-height:62px!important;padding:7px 8px!important}
      [data-testid="stMetricValue"]{font-size:.96rem!important}
      [data-testid="stMetricLabel"] p{font-size:.68rem!important}
      [data-testid="stCheckbox"] label p{font-size:.78rem!important;line-height:1.2!important}
    }
    @media(max-width:480px){
      /* Preserve the compact action grid even under the legacy one-column rule. */
      div[class*="st-key-ops_cards_"] [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(2,minmax(0,1fr))!important}
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-ops_alert_"]),
      [data-testid="stHorizontalBlock"]:has(div[class*="st-key-opsaction_"]){grid-template-columns:repeat(2,minmax(0,1fr))!important}
      div[class*="st-key-ops_alert_"] button,div[class*="st-key-opsaction_"] button{min-height:62px!important;padding:6px 4px!important;border-radius:12px!important}
      div[class*="st-key-ops_alert_"] button p,div[class*="st-key-opsaction_"] button p,
      div[class*="st-key-ops_alert_"] button [data-testid="stMarkdownContainer"],
      div[class*="st-key-opsaction_"] button [data-testid="stMarkdownContainer"]{font-size:.64rem!important;line-height:1.08!important}
    }
</style>""", unsafe_allow_html=True)

def page_title(title, caption=None):
    logo_uri = _logo_data_uri()
    logo_html = f'<img src="{logo_uri}" alt="BIDV" class="page-logo-img">' if logo_uri else '<b>BIDV</b>'
    cap = html.escape(str(caption or ""))
    st.markdown(
        f'''<div class="page-brand-shell"><div class="page-logo-wrap">{logo_html}</div><div class="page-hero-card"><h1>{html.escape(str(title))}</h1><p>{cap}</p></div></div>''',
        unsafe_allow_html=True,
    )

def attention_banner(text):
    st.markdown(f'<div class="task-pick-alert">🔔 {text}</div>', unsafe_allow_html=True)


def required_error(text):
    st.markdown(f'<div class="required-error">🔴 {text}</div>', unsafe_allow_html=True)


def pill_nav(state_key, options, default=None, prefix="subnav"):
    values = [v for v, _ in options]
    current = st.session_state.get(state_key)
    if current not in values:
        current = default if default in values else values[0]
        st.session_state[state_key] = current
    with st.container(key=f"{prefix}_row"):
        cols = st.columns(len(options), gap="small")
        for col, (value, label) in zip(cols, options):
            with col:
                if st.button(label, key=f"{prefix}_{value}", use_container_width=True, type="primary" if current == value else "secondary"):
                    st.session_state[state_key] = value
                    st.rerun()
    return st.session_state.get(state_key, current)


def ops_action_cards(state_key, cards):
    """Clickable workflow cards. Any non-zero actionable card flashes yellow/red until processed."""
    with st.container(key=f"ops_cards_{state_key}"):
        cols = st.columns(len(cards), gap="small")
        for idx, (col, card) in enumerate(zip(cols, cards)):
            value, icon, label, count, hot = card[:5]
            danger = bool(card[5]) if len(card) > 5 else False
            extra_state = card[6] if len(card) > 6 and isinstance(card[6], dict) else {}
            needs_attention = bool(count) and bool(hot or danger)
            status_text = "\n⚠️ CẦN XỬ LÝ" if needs_attention else ""
            container_key = f"ops_alert_hot_{state_key}_{idx}" if needs_attention else f"ops_alert_idle_{state_key}_{idx}"
            with col:
                with st.container(key=container_key):
                    if st.button(
                        f"{icon}  {label}\n\n{int(count)}{status_text}",
                        key=f"opsaction_{state_key}_{idx}_{value}",
                        use_container_width=True,
                        type="primary" if needs_attention else "secondary",
                    ):
                        st.session_state[state_key] = value
                        for sk, sv in extra_state.items():
                            st.session_state[sk] = sv
                        st.rerun()


def sidebar_navigation(u):
    options = []
    if u["role"] == "Cán bộ hỗ trợ": options.append(("support", "🧾  Tác nghiệp"))
    if u["role"] == "Cán bộ QLKH": options.append(("qlkh", "🧾  Tác nghiệp QLKH"))
    if u["role"] == "Lãnh đạo phòng": options.append(("leader", "🗂️  Quản lý công việc"))
    options += [("dashboard", "📊  Dashboard"), ("profile", "👤  Tài khoản"), ("guide", "📘  Hướng dẫn sử dụng")]
    if u["is_admin"]: options.append(("admin", "⚙️  Quản trị"))
    values = [x[0] for x in options]
    current = st.session_state.get("main_page")
    if current not in values:
        current = values[0]; st.session_state["main_page"] = current
    st.sidebar.markdown("#### Chức năng")
    for value, label in options:
        if st.sidebar.button(label, key=f"mainnav_{value}", use_container_width=True, type="primary" if current == value else "secondary"):
            st.session_state["main_page"] = value; st.rerun()
    return st.session_state.get("main_page", current)


def _workflow_delay_targets():
    h = qdf("""SELECT t.id,t.task_type,t.assigned_at,t.accepted_at,t.first_accepted_at,t.start_time,t.end_time,t.evaluated_at,t.amount_vnd,
                      e.quality_score,e.progress_score
               FROM tasks t LEFT JOIN evaluations e ON e.task_id=t.id AND e.round_no=t.current_round""")
    if h.empty:
        return {"accept": {}, "work": {}, "review": {}, "fallback": {"accept":60.0,"work":240.0,"review":120.0}}
    for c in ["assigned_at","accepted_at","first_accepted_at","start_time","end_time","evaluated_at"]:
        h[c+"_dt"] = pd.to_datetime(h[c], errors="coerce")
    h["accept_minutes"] = (h["first_accepted_at_dt"].fillna(h["accepted_at_dt"]) - h["assigned_at_dt"]).dt.total_seconds()/60.0
    h["work_minutes"] = (h["end_time_dt"] - h["start_time_dt"]).dt.total_seconds()/60.0
    h["review_minutes"] = (h["evaluated_at_dt"] - h["end_time_dt"]).dt.total_seconds()/60.0
    maps={"accept":{},"work":{},"review":{},"fallback":{}}
    for phase,col in [("accept","accept_minutes"),("work","work_minutes"),("review","review_minutes")]:
        vals=pd.to_numeric(h[col],errors="coerce")
        valid=h[vals.between(0,60*24*30,inclusive="both")].copy()
        if not valid.empty:
            med=valid.groupby("task_type")[col].median()
            maps[phase]={str(k):max(5.0,float(v)) for k,v in med.dropna().items()}
            maps["fallback"][phase]=max(5.0,float(valid[col].median()))
    maps["fallback"].setdefault("accept",60.0); maps["fallback"].setdefault("work",240.0); maps["fallback"].setdefault("review",120.0)
    return maps


def _phase_delay_info(row, targets=None):
    targets = targets or _workflow_delay_targets(); status=str(row.get("status")); task_type=str(row.get("task_type"))
    if status == "PENDING_ACCEPTANCE": phase="accept"; phase_label="Chờ tiếp nhận"; start=parse_dt(row.get("returned_to_qlkh_at")) or parse_dt(row.get("assigned_at"))
    elif status == "RETURNED_TO_QLKH": phase="accept"; phase_label="Chờ QLKH giao lại"; start=parse_dt(row.get("returned_to_qlkh_at")) or parse_dt(row.get("assigned_at"))
    elif status in ("OPEN","REWORK"):
        phase="work"; phase_label="Đang xử lý"; start=parse_dt(row.get("last_rework_at") if status=="REWORK" else row.get("start_time")) or parse_dt(row.get("start_time"))
    elif status == "PENDING_REVIEW": phase="review"; phase_label="Chờ QLKH đánh giá"; start=parse_dt(row.get("end_time"))
    else: return {"phase":STATUS_LABEL.get(status,status),"start":None,"elapsed":0.0,"target":math.nan,"ratio":math.nan,"level":"—","icon":"⚪"}
    elapsed=max(0.0,(now_dt()-start).total_seconds()/60.0) if start else 0.0
    target=float(targets.get(phase,{}).get(task_type,targets.get("fallback",{}).get(phase,60.0)) or 60.0); ratio=elapsed/target*100.0 if target>0 else math.nan
    if pd.isna(ratio) or ratio<=75: level,icon="Bình thường","🟢"
    elif ratio<=100: level,icon="Cần chú ý","🟡"
    elif ratio<=150: level,icon="Chậm","🟠"
    else: level,icon="Rất chậm","🔴"
    return {"phase":phase_label,"start":start,"elapsed":elapsed,"target":target,"ratio":ratio,"level":level,"icon":icon}


def _minutes_human(v):
    try: m=max(0,int(round(float(v))))
    except Exception: return "—"
    if m<60: return f"{m} phút"
    h,m2=divmod(m,60)
    if h<24: return f"{h}g {m2:02d}p"
    d,h2=divmod(h,24); return f"{d}n {h2}g"


def render_open_task_table(df, include_scores=False):
    if df is None or df.empty:
        st.info("Không có công việc chưa kết thúc."); return pd.DataFrame()
    e=enrich_tasks(df.copy()); e=e[~e.status.isin(["CLOSED","CANCELLED"])].copy()
    if e.empty:
        st.success("Không còn công việc chưa kết thúc."); return e
    targets=_workflow_delay_targets(); info=[_phase_delay_info(r,targets) for _,r in e.iterrows()]
    e["phase_name"]=[x["phase"] for x in info]; e["phase_start"]=[x["start"] for x in info]; e["wait_minutes"]=[x["elapsed"] for x in info]; e["phase_target"]=[x["target"] for x in info]; e["delay_ratio"]=[x["ratio"] for x in info]
    e["delay_level"]=[f'{x["icon"]} {x["level"]} · {x["ratio"]:.0f}%' if pd.notna(x["ratio"]) else "⚪ —" for x in info]
    e=e.sort_values(["phase_start","cif","id"],ascending=[True,True,True],na_position="last",kind="stable")
    cols=["cif","customer_name","support_name","qlkh_name","task_type","amount","currency","assigned_at","phase_name","phase_start","wait_minutes","phase_target","delay_level","current_round"]
    if include_scores: cols += ["quality_score","progress_score","avg_score"]
    cols=[c for c in cols if c in e.columns]; show=e[cols].copy(); show["amount"]=show["amount"].map(money)
    if "assigned_at" in show.columns: show["assigned_at"]=show["assigned_at"].map(fmt_dt)
    show["phase_start"]=show["phase_start"].map(lambda x:x.strftime("%H:%M %d/%m/%Y") if pd.notna(x) else "—"); show["wait_minutes"]=show["wait_minutes"].map(_minutes_human); show["phase_target"]=show["phase_target"].map(_minutes_human)
    for _score_col in ["quality_score","progress_score","avg_score"]:
        if _score_col in show.columns: show[_score_col]=show[_score_col].map(fmt_score)
    names={"cif":"CIF","customer_name":"Khách hàng","support_name":"CB hỗ trợ","qlkh_name":"CB QLKH","task_type":"Công việc","amount":"Giá trị","currency":"Đơn vị","assigned_at":"Thời gian giao","phase_name":"Mốc đang chờ","phase_start":"Bắt đầu mốc","wait_minutes":"TG đang chờ","phase_target":"Mục tiêu tham chiếu","delay_level":"Heatmap mức độ trễ","current_round":"Vòng","quality_score":"Chất lượng","progress_score":"Tiến độ","avg_score":"Điểm TB"}; show=show.rename(columns=names)
    def heat(v):
        s=str(v)
        if "🔴" in s:return "background-color:#FECACA;color:#7F1D1D;font-weight:800"
        if "🟠" in s:return "background-color:#FED7AA;color:#7C2D12;font-weight:800"
        if "🟡" in s:return "background-color:#FEF3C7;color:#713F12;font-weight:800"
        if "🟢" in s:return "background-color:#DCFCE7;color:#14532D;font-weight:800"
        return ""
    st.markdown('<div class="open-list-note"><b>Danh sách chỉ gồm hồ sơ chưa kết thúc</b> và được xếp <b>món cũ nhất ở trên</b>. Heatmap so sánh thời gian đang chờ ở từng bước với dữ liệu lịch sử cùng loại công việc.</div>',unsafe_allow_html=True)
    st.dataframe(show.style.map(heat,subset=["Heatmap mức độ trễ"]),use_container_width=True,hide_index=True,height=_task_list_height(len(show),560))
    return e


def money(v):
    try:
        return f"{float(v):,.0f}".replace(",", ".")
    except Exception:
        return "0"


def billion_value(v):
    try:
        return float(v or 0) / 1_000_000_000.0
    except Exception:
        return 0.0


def fmt_billion(v, with_unit=True):
    try:
        txt = f"{float(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{txt} tỷ đồng" if with_unit else txt
    except Exception:
        return "0,0 tỷ đồng" if with_unit else "0,0"


def fmt_score(v):
    """Điểm hiển thị thống nhất 1 chữ số thập phân trên toàn app."""
    try:
        if v is None or pd.isna(v):
            return "—"
        return f"{float(v):.1f}"
    except Exception:
        return "—"


def fmt_dt(v):
    dt = parse_dt(v)
    return dt.strftime("%H:%M %d/%m/%Y") if dt else "—"


def parse_amount_text(v):
    raw = re.sub(r"[^0-9]", "", str(v or ""))
    return float(raw) if raw else 0.0


def _strip_accents(v):
    return "".join(ch for ch in unicodedata.normalize("NFD", str(v or "")) if unicodedata.category(ch) != "Mn")


# ---------- BIDV FX: direct HTTP crawler, no browser automation ----------
BIDV_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BIDV_FX_URL,
}


def _bidv_ssl_context():
    """SSL context tương thích endpoint public của BIDV và certificate store của hệ điều hành."""
    ctx = ssl.create_default_context()
    # BIDV từng dùng cấu hình TLS cần legacy server connect ở một số OpenSSL 3.x clients.
    # Chỉ bật capability tương thích; vẫn giữ verify certificate mặc định.
    try:
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
    except Exception:
        pass
    return ctx


def _bidv_http_client():
    """HTTP client theo cùng hướng Trecapital: timeout ngắn, redirect, browser-like AJAX headers."""
    return httpx.Client(
        timeout=httpx.Timeout(10.0, connect=6.0),
        follow_redirects=True,
        headers=BIDV_HTTP_HEADERS,
        verify=_bidv_ssl_context(),
        trust_env=True,
        http2=False,
    )


def _bidv_get_json(client, url, params=None, retries=2):
    """GET JSON với exponential backoff; không khởi chạy Chrome/Edge."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client.get(url, params=params or {})
            resp.raise_for_status()
            text = (resp.text or "").strip().lstrip("\ufeff")
            if not text:
                raise RuntimeError("BIDV trả về nội dung rỗng")
            try:
                data = resp.json()
            except Exception:
                data = json.loads(text)
            if not isinstance(data, dict):
                raise RuntimeError("Dữ liệu BIDV không phải JSON object")
            return data
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                import time
                time.sleep(0.45 * (2 ** attempt))
    raise RuntimeError(str(last_error) if last_error else "Không đọc được JSON BIDV")


def _bidv_status_ok(payload):
    val = payload.get("status") if isinstance(payload, dict) else None
    return val in (1, "1", True, "true", "TRUE")


def _bidv_time_sort_key(item):
    """Chuẩn hóa trường time của BIDV để lấy bản cập nhật mới nhất trong ngày."""
    raw = str((item or {}).get("time") or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"):
        try:
            d = datetime.strptime(raw, fmt)
            return d.hour * 3600 + d.minute * 60 + d.second
        except Exception:
            pass
    digits = re.sub(r"[^0-9]", "", raw)
    try:
        return int(digits or 0)
    except Exception:
        return 0


def _parse_bidv_number(v):
    """Đọc số tỷ giá ở các dạng BIDV thường trả về: 26185, 26.185, 26,185, 30435.5..."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return float(v)
        except Exception:
            return 0.0
    s = re.sub(r"[^0-9.,-]", "", str(v).strip())
    if not s or s in {"-", ".", ","}:
        return 0.0
    neg = s.startswith("-")
    s = s.lstrip("-")
    if "," in s and "." in s:
        # Ký tự xuất hiện cuối cùng nhiều khả năng là dấu thập phân.
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        thou = "." if dec == "," else ","
        tail = s.rsplit(dec, 1)[-1]
        if len(tail) <= 2:
            s = s.replace(thou, "").replace(dec, ".")
        else:
            s = s.replace(",", "").replace(".", "")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        parts = s.split(sep)
        if len(parts) > 2:
            s = "".join(parts)
        elif len(parts) == 2:
            # Với USD/EUR/VND, 3 chữ số sau separator thường là hàng nghìn.
            if len(parts[1]) == 3 and len(parts[0]) >= 2:
                s = parts[0] + parts[1]
            else:
                s = parts[0] + "." + parts[1]
    try:
        val = float(s)
        return -val if neg else val
    except Exception:
        return 0.0


def _extract_bidv_rates_from_json(payload):
    """Lấy tỷ giá mua chuyển khoản USD/EUR từ payload ExchangeDetailServlet."""
    if not isinstance(payload, dict):
        return {}
    items = payload.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or items.get("items") or []
    if not isinstance(items, list):
        return {}
    rates = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        cur = str(item.get("currency") or "").strip().upper()
        if cur not in ("USD", "EUR"):
            continue
        val = _parse_bidv_number(item.get("muaCk"))
        if val > 1000:
            rates[cur] = val
    return rates


def _crawl_bidv_fx_for_date(client, date_obj):
    """Hai HTTP GET mà chính frontend BIDV dùng: time list -> detail JSON."""
    date_str = date_obj.strftime("%d/%m/%Y")
    time_payload = _bidv_get_json(client, BIDV_FX_TIME_URL, {"date": date_str})
    if not _bidv_status_ok(time_payload):
        return {}, None
    times = time_payload.get("data") or []
    if not isinstance(times, list) or not times:
        return {}, None
    latest = max(times, key=_bidv_time_sort_key)
    record = str(latest.get("namerecord") or latest.get("nameRecord") or "").strip()
    if not record:
        return {}, None
    detail_payload = _bidv_get_json(
        client,
        BIDV_FX_DETAIL_URL,
        {"date": date_str, "time": record},
    )
    if not _bidv_status_ok(detail_payload):
        return {}, None
    rates = _extract_bidv_rates_from_json(detail_payload)
    meta = {
        "date": date_str,
        "time": str(latest.get("time") or record),
        "record": record,
    }
    return rates, meta


def crawl_bidv_fx_rates(return_meta=False):
    """Crawl trực tiếp public JSON servlet của BIDV, không Selenium/CDP/ChromeDriver.

    Mặc định lấy hôm nay. Nếu hôm nay chưa có dữ liệu (ngày nghỉ hoặc đầu ngày), lùi tối đa 7 ngày
    để lấy bản BIDV gần nhất thay vì sử dụng nguồn tỷ giá bên thứ ba.
    """
    errors = []
    with _bidv_http_client() as client:
        for days_back in range(0, 8):
            d = now_dt().date() - timedelta(days=days_back)
            try:
                rates, meta = _crawl_bidv_fx_for_date(client, d)
                if all(rates.get(k, 0) > 1000 for k in ("USD", "EUR")):
                    if return_meta:
                        return rates, meta
                    return rates
                errors.append(f"{d.strftime('%d/%m/%Y')}: chưa có đủ USD/EUR")
            except Exception as exc:
                errors.append(f"{d.strftime('%d/%m/%Y')}: {exc}")
                # Nếu lỗi kết nối/TLS thì thử lại ngày khác không có ý nghĩa; dừng sớm.
                msg = str(exc).lower()
                if any(x in msg for x in ("connect", "ssl", "certificate", "timed out", "timeout", "proxy", "dns")):
                    break
    raise RuntimeError("; ".join(errors[-4:]) or "Không lấy được tỷ giá BIDV")


def fetch_bidv_fx_rates():
    """Cập nhật USD/EUR mua chuyển khoản từ backend public của trang BIDV."""
    rates = {"VND": 1.0}
    fetched = now_str()
    error = ""
    try:
        got, meta = crawl_bidv_fx_rates(return_meta=True)
        rates.update(got)
        bidv_time = f"{meta.get('time', '')} {meta.get('date', '')}".strip() if meta else ""
        source = "bidv.com.vn ServicesBIDV public servlet (direct HTTP)"
        if bidv_time:
            source += f" | BIDV {bidv_time}"
        with get_conn() as c:
            for cur in ("USD", "EUR"):
                c.execute(
                    "INSERT INTO exchange_rates(currency,rate_to_vnd,rate_type,source,fetched_at) VALUES(?,?,?,?,?)",
                    (cur, rates[cur], "Mua chuyển khoản", source, fetched),
                )
            c.commit()
        return rates, source, fetched, None
    except Exception as e:
        error = str(e)

    # Chỉ fallback sang dữ liệu BIDV đã lưu trước đó; tuyệt đối không lấy tỷ giá từ bên thứ ba.
    cached = qdf("""SELECT e.currency,e.rate_to_vnd,e.source,e.fetched_at
                    FROM exchange_rates e
                    JOIN (SELECT currency,MAX(id) max_id FROM exchange_rates GROUP BY currency) x ON e.id=x.max_id""")
    if not cached.empty:
        for _, row in cached.iterrows():
            rates[str(row.currency)] = float(row.rate_to_vnd)
        if all(rates.get(k, 0) > 0 for k in ("USD", "EUR")):
            last = cached.sort_values("fetched_at").iloc[-1]
            return rates, f"Tỷ giá BIDV gần nhất đã lưu ({last.source})", str(last.fetched_at), error
    return rates, "Chưa có dữ liệu tỷ giá", fetched, error

def _norm_search(v):
    v = "" if v is None else str(v)
    return re.sub(r"\s+", " ", v.strip().lower())


def _person_match_key(v):
    return re.sub(r"\s+", " ", _strip_accents(v).strip().lower())


def match_qlkh_user(users_df, raw_value):
    raw = "" if raw_value is None else str(raw_value).strip()
    if not raw or raw.lower() == "nan" or users_df.empty:
        return None, "Trống"
    # Ưu tiên username chính xác.
    m = users_df[users_df["username"].astype(str).str.strip().str.lower() == raw.lower()]
    if len(m) == 1:
        return int(m.iloc[0].id), "Khớp username"
    # Sau đó full name chính xác.
    m = users_df[users_df["full_name"].astype(str).str.strip().str.lower() == raw.lower()]
    if len(m) == 1:
        return int(m.iloc[0].id), "Khớp họ tên"
    # Cuối cùng bỏ dấu/chuẩn hóa khoảng trắng, chỉ nhận nếu duy nhất.
    key = _person_match_key(raw)
    mask = users_df["full_name"].astype(str).map(_person_match_key).eq(key) | users_df["username"].astype(str).map(_person_match_key).eq(key)
    m = users_df[mask]
    if len(m) == 1:
        return int(m.iloc[0].id), "Khớp chuẩn hóa"
    if len(m) > 1:
        return None, "Trùng nhiều user"
    return None, "Không tìm thấy user"


def _guess_column(columns, aliases):
    keys = [_person_match_key(c).replace(" ", "") for c in columns]
    alias_keys = [_person_match_key(a).replace(" ", "") for a in aliases]
    for a in alias_keys:
        for i, k in enumerate(keys):
            if k == a:
                return i
    for a in alias_keys:
        for i, k in enumerate(keys):
            if a in k or k in a:
                return i
    return 0


def customer_selector(key="cust", required_message=None):
    """Search-first customer picker.

    V2.22 queries only the top matching rows instead of loading the entire CIF
    master on every Streamlit rerun. This is materially faster for large lists.
    """
    selected_key = f"{key}_selected_id"
    with st.container(key=f"customer_search_{key}"):
        query = st.text_input(
            "🔎 Tìm theo CIF hoặc Tên khách hàng",
            key=f"{key}_query",
            placeholder="Nhập CIF hoặc tên khách hàng để tìm nhanh…",
        )
    q = _norm_search(query)
    if q:
        like = f"%{q}%"
        hits = qdf(
            """SELECT c.id,c.cif,c.customer_name,c.qlkh_user_id,u.full_name qlkh_name
               FROM customers c LEFT JOIN users u ON c.qlkh_user_id=u.id
               WHERE c.active=1 AND (lower(CAST(c.cif AS TEXT)) LIKE ? OR lower(c.customer_name) LIKE ?)
               ORDER BY CASE WHEN lower(CAST(c.cif AS TEXT))=? THEN 0 WHEN lower(c.customer_name)=? THEN 1 ELSE 2 END,
                        c.customer_name LIMIT 20""",
            (like, like, q, q),
        )
        if hits.empty:
            st.warning("Không tìm thấy khách hàng phù hợp.")
        else:
            st.caption(f"Tìm thấy {len(hits)} kết quả phù hợp. Bấm **Chọn** đúng khách hàng cần tác nghiệp.")
            for _, r in hits.iterrows():
                c1, c2, c3 = st.columns([1.2, 5, 1])
                c1.write(str(r["cif"]))
                c2.write(str(r["customer_name"]))
                if c3.button("Chọn", key=f"{key}_pick_{int(r['id'])}", use_container_width=True):
                    st.session_state[selected_key] = int(r["id"])
                    st.rerun()

    sid = st.session_state.get(selected_key)
    if sid is None:
        if required_message:
            required_error(required_message)
        st.info("Nhập CIF/Tên khách hàng ở ô trên để tìm và chọn khách hàng.")
        return None
    chosen = qdf(
        """SELECT c.id,c.cif,c.customer_name,c.qlkh_user_id,u.full_name qlkh_name
           FROM customers c LEFT JOIN users u ON c.qlkh_user_id=u.id WHERE c.id=? AND c.active=1""",
        (int(sid),),
    )
    if chosen.empty:
        st.session_state.pop(selected_key, None)
        return None
    r = chosen.iloc[0].to_dict()
    st.success(f"Đã chọn: **{r['cif']} — {r['customer_name']}**")
    if st.button("Đổi khách hàng", key=f"{key}_clear"):
        st.session_state.pop(selected_key, None)
        st.session_state.pop(f"{key}_query", None)
        st.rerun()
    return r


def render_task_table(df, include_scores=True, dashboard_billions=False):
    if df.empty:
        st.info("Không có dữ liệu phù hợp.")
        return
    e = enrich_tasks(df)
    cols = ["task_code", "cif", "customer_name", "support_name", "qlkh_name", "task_type", "amount", "currency", "amount_vnd", "assigned_at", "first_accepted_at", "accepted_at", "assignment_to_accept_minutes", "start_time", "end_time", "evaluated_at", "duration_minutes", "status_label", "current_round"]
    if include_scores:
        cols += ["quality_score", "progress_score", "avg_score"]
    cols = [c for c in cols if c in e.columns]
    show = e[cols].copy()
    for c in ("assigned_at", "first_accepted_at", "accepted_at", "start_time", "end_time", "evaluated_at"):
        if c in show.columns:
            show[c] = show[c].map(fmt_dt)
    if "amount" in show.columns:
        show["amount"] = show["amount"].map(money)
    if "amount_vnd" in show.columns:
        if dashboard_billions:
            show["amount_vnd"] = show["amount_vnd"].map(lambda x: fmt_billion(billion_value(x), with_unit=False))
        else:
            show["amount_vnd"] = show["amount_vnd"].map(money)
    if "assignment_to_accept_minutes" in show.columns:
        show["assignment_to_accept_minutes"] = show["assignment_to_accept_minutes"].map(lambda x: f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—")
    if "duration_minutes" in show.columns:
        show["duration_minutes"] = show["duration_minutes"].map(lambda x: f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—")
    for _score_col in ["quality_score","progress_score","avg_score"]:
        if _score_col in show.columns:
            show[_score_col] = show[_score_col].map(fmt_score)
    names = {
        "task_code":"Mã TN","cif":"CIF","customer_name":"Khách hàng","support_name":"CB hỗ trợ","qlkh_name":"CB QLKH",
        "task_type":"Công việc","amount":"Giá trị","currency":"Đơn vị",
        "amount_vnd":"Quy đổi (tỷ đồng)" if dashboard_billions else "Quy đổi VND",
        "assigned_at":"Giao/khởi tạo","first_accepted_at":"CBHT tiếp nhận lần đầu","accepted_at":"CBHT tiếp nhận gần nhất","assignment_to_accept_minutes":"TG giao→tiếp nhận (phút)","start_time":"Bắt đầu","end_time":"Kết thúc","evaluated_at":"QLKH đánh giá","duration_minutes":"TG xử lý (phút)","status_label":"Trạng thái","current_round":"Vòng",
        "quality_score":"Chất lượng","progress_score":"Tiến độ","avg_score":"Điểm TB"
    }
    st.dataframe(show.rename(columns=names), use_container_width=True, hide_index=True)




def render_task_chips(row, *, time_label="Giao", time_field="assigned_at"):
    """Hiển thị từng thành phần hồ sơ bằng một màu riêng để dễ quét mắt."""
    if row is None:
        return
    def _g(name, default=""):
        try:
            v = row.get(name, default)
        except Exception:
            try: v = row[name]
            except Exception: v = default
        return default if v is None or (isinstance(v, float) and pd.isna(v)) else v
    amount = f"{money(_g('amount',0))} {_g('currency','')}".strip()
    status = STATUS_LABEL.get(str(_g('status','')), str(_g('status_label', _g('status',''))))
    parts = [
        ("chip-kh", f"KH: {_g('cif','')} - {_g('customer_name','')}"),
        ("chip-task", f"Công việc: {_g('task_type','')}"),
        ("chip-value", f"Giá trị: {amount}"),
        ("chip-time", f"{time_label}: {fmt_dt(_g(time_field,''))}"),
        ("chip-support", f"CBHT: {_g('support_name','—')}"),
        ("chip-qlkh", f"QLKH: {_g('qlkh_name','—')}"),
    ]
    if status:
        parts.append(("chip-status", f"{status}"))
    st.markdown('<div class="task-chip-row">'+''.join(f'<span class="task-chip {cls}">{html.escape(str(txt))}</span>' for cls,txt in parts)+'</div>', unsafe_allow_html=True)


def _task_list_height(n, max_height=560):
    """Viewport đủ khoảng 5 hồ sơ, tăng dần nhưng không chiếm toàn màn hình."""
    try: n=int(n)
    except Exception: n=5
    visible=max(5,min(n,9))
    return min(int(max_height), 118 + visible*43)


def _history_table_height(n, max_height=600):
    """Bảng lịch sử luôn nhìn được tối thiểu ~5 dòng, tăng đến ~9 dòng rồi cuộn."""
    try: n=int(n)
    except Exception: n=5
    visible=max(5,min(n,9))
    return min(int(max_height), 126 + visible*47)


def selectable_task_table(df, key, *, include_status=True, include_phase=False, height=None):
    """Bảng chọn 1 dòng. Người dùng click trực tiếp vào hồ sơ thay vì chọn dropdown."""
    if df is None or df.empty:
        return None
    if height is None:
        height = _task_list_height(len(df))
    else:
        height = max(int(height), _task_list_height(min(len(df),5), max_height=max(int(height),333)))
    e = enrich_tasks(df.copy()).reset_index(drop=True)
    if include_phase:
        tg = _workflow_delay_targets()
        info = [_phase_delay_info(r, tg) for _, r in e.iterrows()]
        e["phase_name"] = [x["phase"] for x in info]
        e["wait_minutes"] = [x["elapsed"] for x in info]
        e["delay_level"] = [x["level"] for x in info]
    cols = ["cif","customer_name","support_name","qlkh_name","task_type","amount","currency","assigned_at"]
    if "start_time" in e.columns: cols.append("start_time")
    if "end_time" in e.columns: cols.append("end_time")
    if include_phase: cols += ["phase_name","wait_minutes","delay_level"]
    if include_status: cols.append("status_label")
    cols=[c for c in cols if c in e.columns]
    show=e[cols].copy()
    show["amount"] = show.apply(lambda r: f"{money(r.get('amount',0))} {r.get('currency','')}".strip(), axis=1)
    if "currency" in show.columns: show=show.drop(columns=["currency"])
    for c in ["assigned_at","start_time","end_time"]:
        if c in show.columns: show[c]=show[c].map(fmt_dt)
    if "wait_minutes" in show.columns: show["wait_minutes"]=show["wait_minutes"].map(_minutes_human)
    names={"cif":"CIF","customer_name":"Khách hàng","support_name":"CB hỗ trợ","qlkh_name":"CB QLKH","task_type":"Công việc","amount":"Giá trị","assigned_at":"Thời gian giao","start_time":"Bắt đầu","end_time":"Kết thúc","phase_name":"Mốc đang chờ","wait_minutes":"TG đang chờ","delay_level":"Mức độ trễ","status_label":"Trạng thái"}
    show=show.rename(columns=names)
    def _style_cols(col):
        colors={
            "Khách hàng":"background-color:#EAF2FF;color:#164E9A;font-weight:750",
            "Công việc":"background-color:#FFF3CD;color:#7A4B00;font-weight:800",
            "Giá trị":"background-color:#E7F7EF;color:#0B684F;font-weight:800",
            "Thời gian giao":"background-color:#FFF0E5;color:#9A4300;font-weight:700",
            "Bắt đầu":"background-color:#FFF0E5;color:#9A4300;font-weight:700",
            "Kết thúc":"background-color:#FCE8EC;color:#9B2945;font-weight:700",
            "CB hỗ trợ":"background-color:#F1EAFE;color:#5A3A91;font-weight:700",
            "CB QLKH":"background-color:#E6F7F5;color:#08645D;font-weight:700",
        }
        stl=colors.get(col.name,"")
        return [stl]*len(col)
    styler=show.style.apply(_style_cols,axis=0)
    if "Mức độ trễ" in show.columns:
        def _delay(v):
            sv=str(v)
            if "🔴" in sv:return "background-color:#FECACA;color:#7F1D1D;font-weight:850"
            if "🟠" in sv:return "background-color:#FED7AA;color:#7C2D12;font-weight:850"
            if "🟡" in sv:return "background-color:#FEF3C7;color:#713F12;font-weight:850"
            if "🟢" in sv:return "background-color:#DCFCE7;color:#14532D;font-weight:850"
            return ""
        styler=styler.map(_delay,subset=["Mức độ trễ"])
    try:
        event=st.dataframe(styler,use_container_width=True,hide_index=True,on_select="rerun",selection_mode="single-row",key=key,height=height)
        rows=list(getattr(getattr(event,"selection",None),"rows",[]) or [])
    except TypeError:
        # Giữ app chạy trên Streamlit cũ; v1.43+ sẽ dùng nhánh chọn dòng ở trên.
        st.dataframe(styler,use_container_width=True,hide_index=True,height=height)
        rows=[]
    if not rows:
        st.caption("👆 Chọn trực tiếp một dòng hồ sơ trong bảng để thao tác.")
        return None
    idx=int(rows[0])
    if idx<0 or idx>=len(e): return None
    return e.iloc[idx]

def filter_history_controls(df, key, date_candidates=None, staff_cols=None):
    """Bộ lọc lịch sử dùng chung: khoảng ngày + cán bộ liên quan."""
    if df is None or df.empty:
        return df
    out = df.copy()
    date_candidates = date_candidates or ["closed_time", "evaluated_at", "end_time", "created_at", "start_time"]
    staff_cols = staff_cols or [c for c in ["support_name", "qlkh_name"] if c in out.columns]
    date_col = next((c for c in date_candidates if c in out.columns), None)
    dt = pd.to_datetime(out[date_col], errors="coerce") if date_col else pd.Series(pd.NaT, index=out.index)
    valid = dt.dropna()
    c1, c2 = st.columns([1.15, 1.35])
    if not valid.empty:
        dmin, dmax = valid.min().date(), valid.max().date()
        dates = c1.date_input("Ngày", value=(dmin, dmax), key=f"{key}_dates")
    else:
        dates = None; c1.caption("Không có mốc ngày để lọc")
    staff_values = []
    for col in staff_cols:
        staff_values.extend(out[col].dropna().astype(str).tolist())
    staff_values = sorted(set(x for x in staff_values if x.strip()))
    selected_staff = c2.multiselect("Cán bộ", staff_values, key=f"{key}_staff") if staff_values else []
    if isinstance(dates, tuple) and len(dates) == 2 and date_col:
        mask = dt.dt.date.between(dates[0], dates[1])
        out = out[mask].copy()
    if selected_staff and staff_cols:
        mask = pd.Series(False, index=out.index)
        for col in staff_cols:
            if col in out.columns:
                mask = mask | out[col].astype(str).isin(selected_staff)
        out = out[mask].copy()
    st.caption(f"Lịch sử theo bộ lọc: **{len(out)}** hồ sơ/bản ghi.")
    return out

def task_history(task_id):
    actions = qdf('''SELECT a.created_at,u.full_name actor,a.action,a.detail
                     FROM task_actions a JOIN users u ON u.id=a.actor_user_id
                     WHERE a.task_id=? ORDER BY a.id''', (task_id,))
    evals = qdf('''SELECT e.round_no,u.full_name evaluator,e.quality_score,e.progress_score,e.comment,e.created_at
                   FROM evaluations e JOIN users u ON u.id=e.evaluator_user_id
                   WHERE e.task_id=? ORDER BY e.round_no''', (task_id,))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Lịch sử xử lý**")
        if actions.empty:
            st.caption("Chưa có lịch sử.")
        else:
            a = actions.copy()
            a["action"] = a["action"].map(ACTION_LABEL).fillna(a["action"])
            a["created_at"] = a["created_at"].map(fmt_dt)
            st.dataframe(a.rename(columns={"created_at":"Thời gian","actor":"Người thực hiện","action":"Hành động","detail":"Chi tiết"}), use_container_width=True, hide_index=True, height=_history_table_height(len(a), 560))
    with c2:
        st.markdown("**Lịch sử đánh giá**")
        if evals.empty:
            st.caption("Chưa có đánh giá.")
        else:
            evals["created_at"] = evals["created_at"].map(fmt_dt)
            for _score_col in ["quality_score","progress_score"]:
                if _score_col in evals.columns: evals[_score_col]=evals[_score_col].map(fmt_score)
            st.dataframe(evals.rename(columns={"round_no":"Vòng","evaluator":"Người đánh giá","quality_score":"Chất lượng","progress_score":"Tiến độ","comment":"Góp ý","created_at":"Thời gian"}), use_container_width=True, hide_index=True, height=_history_table_height(len(evals), 560))


def _temporary_password(length=12):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    # Bảo đảm có chữ hoa, chữ thường và số.
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if re.search(r"[A-Z]", pwd) and re.search(r"[a-z]", pwd) and re.search(r"\d", pwd):
            return pwd


def _send_recovery_via_smtp(to_email, subject, body):
    host = os.getenv("KHDN_SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError("SMTP chưa được cấu hình")
    port = int(os.getenv("KHDN_SMTP_PORT", "587"))
    username = os.getenv("KHDN_SMTP_USERNAME", "").strip()
    password = os.getenv("KHDN_SMTP_PASSWORD", "")
    sender = os.getenv("KHDN_SMTP_FROM", "").strip() or username
    if not sender:
        raise RuntimeError("Chưa cấu hình địa chỉ gửi KHDN_SMTP_FROM/KHDN_SMTP_USERNAME")
    use_ssl = os.getenv("KHDN_SMTP_SSL", "0").strip().lower() in ("1", "true", "yes")
    use_tls = os.getenv("KHDN_SMTP_TLS", "1").strip().lower() in ("1", "true", "yes")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as server:
            if username:
                server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=context)
                server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(msg)
    return "SMTP"


def _send_recovery_via_outlook(to_email, subject, body):
    if os.name != "nt":
        raise RuntimeError("Outlook COM chỉ khả dụng trên Windows")
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("Không tìm thấy PowerShell")
    # Dùng Outlook Desktop đã đăng nhập trên máy để gửi mail nội bộ, không lưu mật khẩu mail trong app.
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$outlook = New-Object -ComObject Outlook.Application\n"
        "$mail = $outlook.CreateItem(0)\n"
        "$mail.To = $env:KHDN_RECOVERY_TO\n"
        "$mail.Subject = $env:KHDN_RECOVERY_SUBJECT\n"
        "$mail.Body = $env:KHDN_RECOVERY_BODY\n"
        "$mail.Send()\n"
    )
    enc = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    env = os.environ.copy()
    env["KHDN_RECOVERY_TO"] = to_email
    env["KHDN_RECOVERY_SUBJECT"] = subject
    env["KHDN_RECOVERY_BODY"] = body
    cp = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
        capture_output=True, text=True, timeout=30, env=env,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout or "Outlook không gửi được email").strip()[-500:])
    return "Outlook Desktop"


def send_admin_recovery_email(username, temp_password):
    subject = "KHDN Ops - Mật khẩu Admin tạm thời"
    body = (
        "KHDN Ops - Phòng KHDN\n\n"
        f"Tài khoản Admin: {username}\n"
        f"Mật khẩu tạm thời: {temp_password}\n\n"
        "Hệ thống sẽ yêu cầu đổi mật khẩu ngay sau khi đăng nhập.\n"
        "Nếu bạn không yêu cầu khôi phục mật khẩu, hãy liên hệ người quản trị hệ thống.\n"
    )
    errors = []
    # Nếu đơn vị đã cấu hình SMTP, ưu tiên SMTP. Nếu chưa, thử Outlook Desktop trên Windows.
    if os.getenv("KHDN_SMTP_HOST", "").strip():
        try:
            return _send_recovery_via_smtp(ADMIN_RECOVERY_EMAIL, subject, body)
        except Exception as e:
            errors.append(f"SMTP: {e}")
    try:
        return _send_recovery_via_outlook(ADMIN_RECOVERY_EMAIL, subject, body)
    except Exception as e:
        errors.append(f"Outlook: {e}")
    raise RuntimeError("; ".join(errors) or "Chưa có kênh gửi email khả dụng")


def recover_admin_password(username):
    row = user_by_username(username.strip(), active_only=True)
    if not row or not int(row["is_admin"]):
        raise ValueError("Không tìm thấy tài khoản Admin đang hoạt động.")
    last = qdf("SELECT created_at FROM system_audit WHERE action='ADMIN_PASSWORD_RECOVERY' AND object_type='user' AND object_id=? ORDER BY id DESC LIMIT 1", (str(row["id"]),))
    if not last.empty:
        prev = parse_dt(last.iloc[0].created_at)
        if prev and (now_dt() - prev).total_seconds() < 300:
            raise RuntimeError("Yêu cầu khôi phục gần nhất chưa đủ 5 phút. Vui lòng kiểm tra email trước khi yêu cầu lại.")
    temp_password = _temporary_password()
    method = send_admin_recovery_email(row["username"], temp_password)
    execute(
        "UPDATE users SET password_hash=?,must_change_password=1,updated_at=? WHERE id=?",
        (hash_password(temp_password), now_str(), row["id"]),
    )
    audit(None, "ADMIN_PASSWORD_RECOVERY", "user", row["id"], f"Gửi mật khẩu tạm thời đến {ADMIN_RECOVERY_EMAIL} qua {method}")
    return method


# ---------- Login / profile ----------
def login_ui():
    page_title(APP_TITLE, f"Hệ thống theo dõi chất lượng và tiến độ tác nghiệp Phòng KHDN • v{APP_VERSION}")
    if CLOUD_MODE:
        try:
            user_count = int(qdf("SELECT COUNT(*) AS n FROM users").iloc[0].n)
        except Exception:
            user_count = 0
        if user_count == 0 and not DEFAULT_ADMIN_PASSWORD:
            st.error("Bản online chưa được kích hoạt an toàn. Chủ hệ thống cần cấu hình secret KHDN_ADMIN_PASSWORD trong môi trường triển khai rồi khởi động lại app.")
            st.caption("Vì lý do an toàn, bản online không tạo tài khoản admin/Admin@123 mặc định.")
            return
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            remember_device = st.checkbox("Ghi nhớ đăng nhập trên thiết bị này trong 30 ngày", value=False)
            st.caption("Chỉ bật trên điện thoại cá nhân có khóa màn hình. Không bật trên thiết bị dùng chung.")
            submitted = st.form_submit_button("Đăng nhập", use_container_width=True, type="primary")
        if submitted:
            u = user_by_username(username.strip())
            if u and verify_password(password, u["password_hash"]):
                execute("UPDATE users SET last_login_at=?,updated_at=? WHERE id=?", (now_str(), now_str(), u["id"]))
                st.session_state.user = dict(user_by_username(username.strip()))
                if remember_device:
                    device_login.remember(DB_PATH, st.session_state.user)
                else:
                    device_login.forget(DB_PATH)
                rates, fx_source, fx_time, fx_error = fetch_bidv_fx_rates()
                st.session_state.fx_rates = rates
                st.session_state.fx_source = fx_source
                st.session_state.fx_time = fx_time
                st.session_state.fx_error = fx_error
                audit(u["id"], "LOGIN", "user", u["id"], f"Đăng nhập thành công; FX={fx_source}")
                st.rerun()
            st.error("Sai tên đăng nhập hoặc mật khẩu, hoặc tài khoản đã bị khóa.")

        with st.expander("Quên mật khẩu Admin?"):
            st.caption(f"Mật khẩu tạm thời sẽ được gửi đến email khôi phục cố định: **{ADMIN_RECOVERY_EMAIL}**.")
            admin_username = st.text_input("Tên đăng nhập Admin", value="admin", key="recovery_admin_username")
            if st.button("Reset mật khẩu Admin và gửi email", use_container_width=True, key="recover_admin_btn"):
                try:
                    method = recover_admin_password(admin_username)
                    st.success(f"Đã reset mật khẩu. Mật khẩu tạm thời đã gửi đến {ADMIN_RECOVERY_EMAIL} qua {method}.")
                except Exception as e:
                    st.error(f"Chưa thể reset mật khẩu vì email chưa gửi thành công: {e}")
                    st.caption("Mật khẩu hiện tại vẫn được giữ nguyên. Trên Windows, app ưu tiên Outlook Desktop đã đăng nhập; máy chủ có thể cấu hình SMTP bằng biến môi trường KHDN_SMTP_*.")
        if CLOUD_MODE:
            st.caption("Bản online không công bố mật khẩu khởi tạo. Admin được cấu hình qua secret của môi trường triển khai.")
        else:
            st.caption("Tài khoản khởi tạo lần đầu: admin / Admin@123. Hệ thống bắt buộc đổi mật khẩu sau đăng nhập đầu tiên.")

def force_password_change(u):
    page_title("Đổi mật khẩu lần đầu", "Vì lý do an toàn, bạn cần đổi mật khẩu khởi tạo trước khi sử dụng ứng dụng.")
    with st.form("forced_pw"):
        current = st.text_input("Mật khẩu hiện tại", type="password")
        new = st.text_input("Mật khẩu mới", type="password")
        confirm = st.text_input("Nhập lại mật khẩu mới", type="password")
        ok = st.form_submit_button("Đổi mật khẩu", type="primary")
    if ok:
        row = user_by_username(u["username"])
        if not verify_password(current, row["password_hash"]):
            st.error("Mật khẩu hiện tại không đúng.")
        elif new != confirm:
            st.error("Hai lần nhập mật khẩu mới không khớp.")
        elif not password_ok(new):
            st.error("Mật khẩu phải có ít nhất 8 ký tự, gồm chữ và số.")
        elif verify_password(new, row["password_hash"]):
            st.error("Mật khẩu mới phải khác mật khẩu hiện tại.")
        else:
            execute("UPDATE users SET password_hash=?,must_change_password=0,updated_at=? WHERE id=?", (hash_password(new), now_str(), u["id"]))
            audit(u["id"], "CHANGE_PASSWORD", "user", u["id"], "Đổi mật khẩu bắt buộc")
            st.session_state.user = dict(user_by_username(u["username"]))
            st.success("Đã đổi mật khẩu.")
            st.rerun()


def _visible_task_change_token(u):
    """Lightweight change token for relevant workflow rows.

    V2.22 avoids loading every task into pandas every 6 seconds. All workflow
    mutations update ``updated_at``; the aggregate token is enough to detect
    creates/state changes while remaining very cheap even with a large history.
    """
    if u.get("is_admin") or u.get("role") == "Lãnh đạo phòng":
        where = ""
        params = ()
    elif u.get("role") == "Cán bộ hỗ trợ":
        where = " WHERE support_user_id=?"
        params = (int(u["id"]),)
    elif u.get("role") == "Cán bộ QLKH":
        where = " WHERE qlkh_user_id=?"
        params = (int(u["id"]),)
    else:
        return ""
    with get_conn() as c:
        row = c.execute(
            "SELECT COALESCE(MAX(updated_at),''),COALESCE(MAX(id),0),"
            "COALESCE(SUM(CASE WHEN status NOT IN ('CLOSED','CANCELLED') THEN id ELSE 0 END),0) "
            "FROM tasks" + where, params
        ).fetchone()
    return "|".join(str(v or "") for v in row)


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{AUTO_REFRESH_SECONDS}s")
    def _realtime_refresh_fragment(user_id, role, is_admin):
        current_user = {"id": user_id, "role": role, "is_admin": is_admin}
        token = _visible_task_change_token(current_user)
        key = f"_task_change_token_{int(user_id)}_{role}_{int(bool(is_admin))}"
        previous = st.session_state.get(key)
        if previous is None:
            st.session_state[key] = token
            return
        if token != previous:
            st.session_state[key] = token
            st.session_state["_auto_refresh_notice"] = "Dữ liệu tác nghiệp vừa thay đổi. Màn hình đã tự cập nhật."
            st.rerun()
else:
    def _realtime_refresh_fragment(user_id, role, is_admin):
        return None


def realtime_refresh_watch(u):
    """Poll relevant workflow data and refresh the app only when it changes."""
    _realtime_refresh_fragment(int(u["id"]), str(u.get("role") or ""), bool(u.get("is_admin")))

def sidebar_user(u):
    logo_uri = _logo_data_uri()
    if logo_uri:
        st.sidebar.markdown(f'<div class="sidebar-logo"><img src="{logo_uri}" alt="BIDV"></div>', unsafe_allow_html=True)
    avatar_uri = _user_avatar_data_uri(u)
    initials = "".join([part[:1].upper() for part in str(u.get("full_name") or "CB").split()[-2:]]) or "CB"
    avatar_html = f'<img src="{avatar_uri}" class="sidebar-avatar" alt="Avatar">' if avatar_uri else f'<div class="sidebar-avatar-fallback">{html.escape(initials)}</div>'
    st.sidebar.markdown(
        f'<div class="sidebar-user-card">{avatar_html}<div class="sidebar-user-meta"><div class="sidebar-user-name">{html.escape(str(u["full_name"]))}</div><div class="sidebar-user-role">{html.escape(str(u["role"]))}{" • Admin" if u["is_admin"] else ""}</div></div></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"KHDN Ops v{APP_VERSION}")
    if CLOUD_MODE:
        st.sidebar.caption("🌐 Online / responsive")
    st.sidebar.caption(f"Tự cập nhật dữ liệu: mỗi {AUTO_REFRESH_SECONDS} giây")
    rates = st.session_state.get("fx_rates", {"VND":1})
    if rates.get("USD") and rates.get("EUR"):
        st.sidebar.caption(f"Tỷ giá BIDV: USD {money(rates['USD'])} | EUR {money(rates['EUR'])}")
        st.sidebar.caption(f"Cập nhật: {fmt_dt(st.session_state.get('fx_time'))}")
    elif st.session_state.get("fx_error"):
        st.sidebar.warning("Chưa cập nhật được tỷ giá BIDV; USD/EUR sẽ bị khóa khi tạo tác nghiệp.")
        st.sidebar.caption(str(st.session_state.get("fx_error"))[:220])
    if st.sidebar.button("🔄 Cập nhật tỷ giá BIDV", use_container_width=True):
        with st.spinner("Đang tải tỷ giá trực tiếp từ BIDV..."):
            rates, fx_source, fx_time, fx_error = fetch_bidv_fx_rates()
            st.session_state.fx_rates = rates; st.session_state.fx_source = fx_source; st.session_state.fx_time = fx_time; st.session_state.fx_error = fx_error
        st.rerun()
    if st.sidebar.button("⏻ Đăng xuất", use_container_width=True, key="logout_btn"):
        device_login.forget(DB_PATH)
        audit(u["id"], "LOGOUT", "user", u["id"], "Đăng xuất")
        for k in ["user","fx_rates","fx_source","fx_time","fx_error"]: st.session_state.pop(k, None)
        st.rerun()

    st.sidebar.caption("Đăng xuất sẽ thu hồi phiên ghi nhớ trên thiết bị này.")


# ---------- Role pages ----------
def support_page(u):
    if st.session_state.pop("reset_new_task_fields", False):
        for k in ["new_cust_selected_id","new_cust_query","new_amount","new_note","new_currency","new_task_type","new_task_validation"]:
            st.session_state.pop(k, None)
        for k in list(st.session_state.keys()):
            if str(k).startswith("new_task_qlkh_"): st.session_state.pop(k, None)
    page_title("Tác nghiệp của Cán bộ hỗ trợ", "Tiếp nhận hồ sơ QLKH giao, tự tạo tác nghiệp, báo hoàn thành và theo dõi đầy đủ các mốc thời gian.")
    mine=enrich_tasks(qdf("""SELECT t.id,t.task_code,c.cif,c.customer_name,q.full_name qlkh_name,s.full_name support_name,
                               t.request_source,t.assigned_at,t.accepted_at,t.first_accepted_at,t.returned_to_qlkh_at,t.cancelled_at,t.evaluated_at,t.last_rework_at,
                               t.task_type,t.amount,t.currency,t.fx_rate,t.amount_vnd,t.start_time,t.end_time,t.closed_time,t.status,t.current_round,t.rework_count,
                               t.note,e.quality_score,e.progress_score,e.comment
                               FROM tasks t JOIN customers c ON c.id=t.customer_id JOIN users q ON q.id=t.qlkh_user_id JOIN users s ON s.id=t.support_user_id
                               LEFT JOIN evaluations e ON e.task_id=t.id AND e.round_no=t.current_round
                               WHERE t.support_user_id=?""",(u["id"],)))
    wait_count=int((mine.status=="PENDING_ACCEPTANCE").sum()) if not mine.empty else 0
    work_count=int(mine.status.isin(["OPEN","REWORK"]).sum()) if not mine.empty else 0
    review_count=int((mine.status=="PENDING_REVIEW").sum()) if not mine.empty else 0
    closed_count=int((mine.status=="CLOSED").sum()) if not mine.empty else 0
    ops_action_cards("support_view",[
        ("inbox","📥","Chờ tiếp nhận",wait_count,True,wait_count>0),
        ("work","🛠️","Đang xử lý",work_count,True,work_count>0),
        ("work","🔔","Chờ QLKH đánh giá",review_count,True,False,{"support_focus":"review"}),
        ("history","✅","Đã kết thúc",closed_count,False,False),
    ])
    view=pill_nav("support_view",[("inbox","📥 Hồ sơ chờ tiếp nhận"),("create","➕ Tạo công việc mới"),("work","🛠 Hồ sơ đang xử lý"),("history","🕘 Lịch sử hồ sơ")],default="inbox",prefix="subnav_support")
    # Card chờ đánh giá nhảy vào màn hình Hồ sơ đang xử lý và ưu tiên vùng chờ đánh giá.
    if view=="review":
        st.session_state["support_view"]="work"; st.session_state["support_focus"]="review"; view="work"

    if view=="inbox":
        waiting=mine[mine.status.eq("PENDING_ACCEPTANCE")].copy() if not mine.empty else pd.DataFrame()
        if waiting.empty: st.success("Không có hồ sơ QLKH giao đang chờ tiếp nhận.")
        else:
            waiting=waiting.sort_values(["assigned_at_dt","cif"],ascending=[True,True],kind="stable",na_position="last")
            attention_banner("Chọn trực tiếp một dòng hồ sơ QLKH giao để tiếp nhận")
            row=selectable_task_table(waiting,"accept_task_table",include_phase=True,height=_task_list_height(len(waiting),520))
            if row is not None:
                tid=int(row.id); render_task_chips(row,time_label="Giao",time_field="assigned_at")
                if row.note: st.caption(f"Ghi chú: {row.note}")
                return_reason = st.text_input("Lý do trả lại QLKH (chỉ nhập khi cần trả hồ sơ)", key=f"return_pending_reason_{tid}")
                ac1, ac2 = st.columns([2.2,1])
                if ac1.button("📥 Tiếp nhận hồ sơ & bắt đầu xử lý",type="primary",use_container_width=True,key=f"accept_btn_{tid}"):
                    ts=now_str()
                    execute("""UPDATE tasks SET status='OPEN',accepted_at=?,first_accepted_at=COALESCE(first_accepted_at,?),
                               start_time=CASE WHEN first_accepted_at IS NULL THEN ? ELSE start_time END,
                               returned_to_qlkh_at=NULL,end_time=NULL,updated_at=?
                               WHERE id=? AND support_user_id=? AND status='PENDING_ACCEPTANCE'""",
                            (ts,ts,ts,ts,int(tid),u["id"]))
                    first_accept = parse_dt(row.get("first_accepted_at")) or parse_dt(ts)
                    assigned = parse_dt(row.get("assigned_at"))
                    wait_mins = ((first_accept-assigned).total_seconds()/60.0) if first_accept and assigned else None
                    log_action(tid,u["id"],"ACCEPT",f"Tiếp nhận hồ sơ lúc {fmt_dt(ts)}; TG từ giao đến tiếp nhận lần đầu={wait_mins:.1f} phút" if wait_mins is not None else f"Tiếp nhận hồ sơ lúc {fmt_dt(ts)}")
                    st.success("Đã tiếp nhận hồ sơ. Mốc thời gian giao ban đầu được giữ nguyên để thống kê."); st.rerun()
                if ac2.button("↩️ Trả lại QLKH",use_container_width=True,key=f"return_pending_btn_{tid}"):
                    if not return_reason.strip():
                        st.error("Bắt buộc nhập lý do trả lại QLKH.")
                    else:
                        ts=now_str(); execute("UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,updated_at=? WHERE id=? AND support_user_id=? AND status='PENDING_ACCEPTANCE'",(ts,ts,tid,u["id"])); log_action(tid,u["id"],"RETURN_TO_QLKH",f"Trả lại trước khi tiếp nhận lúc {fmt_dt(ts)}; lý do={return_reason.strip()}"); st.success("Đã trả hồ sơ về Cán bộ QLKH. Mốc giao ban đầu vẫn được giữ nguyên."); st.rerun()

    elif view=="create":
        validation=st.session_state.get("new_task_validation",{}); types=active_task_types(); cust=customer_selector("new_cust",validation.get("customer")); qlkh_df=all_users("Cán bộ QLKH",active_only=True); qid_default=None
        if cust and pd.notna(cust.get("qlkh_user_id")) and not qlkh_df.empty and int(cust["qlkh_user_id"]) in qlkh_df.id.astype(int).tolist(): qid_default=int(cust["qlkh_user_id"])
        qid=None
        if qlkh_df.empty: st.error("Chưa có user Cán bộ QLKH đang hoạt động.")
        elif cust:
            opts=qlkh_df.id.astype(int).tolist(); idx=opts.index(qid_default) if qid_default in opts else None
            qid=st.selectbox("Cán bộ QLKH",opts,index=idx,key=f"new_task_qlkh_{int(cust['id'])}",placeholder="Chọn Cán bộ QLKH",format_func=lambda x:f"{qlkh_df[qlkh_df.id==x].iloc[0].full_name} ({qlkh_df[qlkh_df.id==x].iloc[0].username})",help="Mặc định theo nguồn khách hàng; có thể điều chỉnh cho riêng lần tác nghiệp này.")
            default_name="Chưa gắn trong nguồn" if qid_default is None else qlkh_df[qlkh_df.id==qid_default].iloc[0].full_name; st.caption(f"QLKH mặc định theo nguồn: **{default_name}**. Việc điều chỉnh tại đây không thay đổi danh mục khách hàng gốc.")
        else: st.selectbox("Cán bộ QLKH",["— Chọn khách hàng trước —"],disabled=True,key="new_task_qlkh_disabled")
        if validation.get("qlkh"): required_error(validation["qlkh"])
        task_type=st.selectbox("Công việc",types.name.tolist() if not types.empty else DEFAULT_TASK_TYPES,key="new_task_type");
        if validation.get("task_type"): required_error(validation["task_type"])
        ccur,camt=st.columns([1,3]); currency=ccur.selectbox("Đơn vị",["VND","USD","EUR"],key="new_currency"); amount_text=camt.text_input("Giá trị",placeholder="Ví dụ: 1.000.000",key="new_amount"); amount=parse_amount_text(amount_text)
        if validation.get("currency"): required_error(validation["currency"])
        if validation.get("amount"): required_error(validation["amount"])
        rates=st.session_state.get("fx_rates",{"VND":1.0}); rate=float(rates.get(currency,0) or 0); amount_vnd=amount*rate if rate else 0
        if amount>0:
            if currency=="VND": st.caption(f"Giá trị: **{money(amount)} VND**")
            elif rate>0: st.caption(f"Tỷ giá mua chuyển khoản BIDV: **1 {currency} = {money(rate)} VND** → Quy đổi: **{money(amount_vnd)} VND**")
            else: st.error(f"Chưa có tỷ giá {currency}/VND. Bấm **Cập nhật tỷ giá BIDV** ở thanh bên để thử lại.")
        note=st.text_area("Ghi chú / nội dung hồ sơ (không bắt buộc)",key="new_note")
        if st.button("Tạo tác nghiệp",use_container_width=True,type="primary"):
            errors={}
            if not cust: errors["customer"]="Bắt buộc chọn khách hàng theo CIF/Tên khách hàng."
            if qid is None: errors["qlkh"]="Bắt buộc chọn Cán bộ QLKH."
            if not task_type: errors["task_type"]="Bắt buộc chọn loại công việc."
            if not currency: errors["currency"]="Bắt buộc chọn đơn vị tiền."
            if amount<=0: errors["amount"]="Bắt buộc nhập Giá trị lớn hơn 0."
            if currency!="VND" and rate<=0: errors["amount"]=f"Chưa lấy được tỷ giá {currency}/VND từ BIDV nên chưa thể tạo tác nghiệp ngoại tệ."
            if errors: st.session_state["new_task_validation"]=errors; st.rerun()
            ts=now_str(); tid=execute("""INSERT INTO tasks(customer_id,support_user_id,qlkh_user_id,request_source,assigned_at,accepted_at,first_accepted_at,task_type,amount,currency,fx_rate,amount_vnd,start_time,due_time,note,status,current_round,rework_count,created_at,updated_at)
                                      VALUES(?,?,?,'SUPPORT',?,?,?, ?,?,?,?,?,?,NULL,?,'OPEN',1,0,?,?)""",(int(cust["id"]),u["id"],int(qid),ts,ts,ts,task_type,amount,currency,rate or 1,amount_vnd,ts,note.strip(),ts,ts))
            code=task_code(tid); execute("UPDATE tasks SET task_code=? WHERE id=?",(code,tid)); qname=qlkh_df[qlkh_df.id==int(qid)].iloc[0].full_name; log_action(tid,u["id"],"CREATE",f"CB hỗ trợ tự tạo và tiếp nhận lúc {fmt_dt(ts)}; {task_type}; giá trị={money(amount)} {currency}; quy đổi={money(amount_vnd)} VND; QLKH={qname}"); st.session_state["reset_new_task_fields"]=True; st.session_state["support_view"]="work"; st.success("Đã tạo tác nghiệp."); st.rerun()

    elif view=="work":
        unfinished=mine[~mine.status.isin(["CLOSED","CANCELLED"])].copy() if not mine.empty else pd.DataFrame()
        active=mine[mine.status.isin(["OPEN","REWORK"])].copy() if not mine.empty else pd.DataFrame(); editable=mine[mine.status.eq("PENDING_REVIEW")].copy() if not mine.empty else pd.DataFrame()
        focus=st.session_state.pop("support_focus",None)
        if focus=="review" and not editable.empty: st.warning("🔔 Có hồ sơ đã hoàn thành đang chờ QLKH đánh giá. Bạn chỉ còn có thể chỉnh Ghi chú trước khi QLKH chấm điểm.")
        if not active.empty:
            active=active.sort_values(["start_dt","cif"],ascending=[True,True],kind="stable"); attention_banner("Chọn trực tiếp một dòng hồ sơ đang xử lý để báo hoàn thành")
            row=selectable_task_table(active,"finish_task_table",include_phase=True,height=_task_list_height(len(active),540))
            if row is not None:
                tid=int(row.id); render_task_chips(row,time_label="Bắt đầu",time_field="start_time")
                default_note=str(row.note or "") if row.status=="REWORK" else ""; note2=st.text_area("Ghi chú khi hoàn thành",value=default_note,key=f"finish_note_{tid}_{int(row.current_round)}")
                return_reason = st.text_input("Lý do trả lại QLKH (nếu chưa thể xử lý xong)", key=f"return_work_reason_{tid}_{int(row.current_round)}")
                fc1, fc2 = st.columns([2.2,1])
                if fc1.button("✅ Hoàn thành xử lý – chuyển QLKH đánh giá",type="primary",use_container_width=True,key=f"finish_btn_{tid}"):
                    ts=now_str(); start_dt=parse_dt(row.start_time); mins=round((parse_dt(ts)-start_dt).total_seconds()/60) if start_dt else None; execute("UPDATE tasks SET status='PENDING_REVIEW',end_time=?,note=CASE WHEN ?='' THEN note ELSE ? END,updated_at=? WHERE id=? AND support_user_id=? AND status IN ('OPEN','REWORK')",(ts,note2.strip(),note2.strip(),ts,tid,u["id"])); log_action(tid,u["id"],"SUBMIT_REVIEW",f"Hoàn thành lúc {fmt_dt(ts)}; thời gian xử lý={mins} phút; ghi chú={note2.strip()}"); st.success(f"Đã báo hoàn thành. Thời gian xử lý: {money(mins)} phút."); st.rerun()
                if fc2.button("↩️ Trả lại QLKH",use_container_width=True,key=f"return_work_btn_{tid}_{int(row.current_round)}"):
                    if not return_reason.strip():
                        st.error("Bắt buộc nhập lý do trả lại QLKH.")
                    else:
                        ts=now_str(); execute("""UPDATE tasks SET status='RETURNED_TO_QLKH',returned_to_qlkh_at=?,accepted_at=NULL,updated_at=?
                                                   WHERE id=? AND support_user_id=? AND status IN ('OPEN','REWORK') AND end_time IS NULL""",(ts,ts,tid,u["id"])); log_action(tid,u["id"],"RETURN_TO_QLKH",f"Trả lại trong khi đang xử lý lúc {fmt_dt(ts)}; lý do={return_reason.strip()}; giữ nguyên mốc giao và mốc bắt đầu đầu tiên"); st.success("Đã trả hồ sơ về QLKH. Mốc giao/tiếp nhận lần đầu và thời gian đã trôi qua được giữ nguyên."); st.rerun()
        if not editable.empty:
            editable=editable.sort_values(["end_dt","cif"],ascending=[True,True],kind="stable"); st.markdown("### Chỉnh sửa ghi chú trước khi QLKH đánh giá"); attention_banner("Chọn trực tiếp một dòng hồ sơ đã hoàn thành để chỉnh Ghi chú")
            er=selectable_task_table(editable,"edit_note_task_table",include_phase=False,height=_task_list_height(len(editable),520))
            if er is not None:
                eid=int(er.id); render_task_chips(er,time_label="Kết thúc",time_field="end_time"); edited=st.text_area("Ghi chú",value=str(er.note or ""),key=f"post_note_{eid}_{int(er.current_round)}")
                if st.button("Lưu ghi chú",key=f"save_note_{eid}_{int(er.current_round)}"):
                    execute("UPDATE tasks SET note=?,updated_at=? WHERE id=? AND support_user_id=? AND status='PENDING_REVIEW'",(edited.strip(),now_str(),eid,u["id"])); log_action(eid,u["id"],"UPDATE",f"Cập nhật ghi chú trước đánh giá: {edited.strip()}"); st.success("Đã cập nhật ghi chú."); st.rerun()
        if not mine.empty and (mine.status=="CLOSED").any(): st.caption("🔒 Công việc đã được QLKH đánh giá đã khóa chỉnh sửa. Chỉ khi Lãnh đạo yêu cầu thực hiện lại, Cán bộ hỗ trợ mới được cập nhật ở vòng mới.")

    elif view=="history":
        hist=mine[mine.status.isin(["CLOSED","CANCELLED"])].copy() if not mine.empty else pd.DataFrame()
        if hist.empty: st.info("Chưa có hồ sơ đã kết thúc.")
        else:
            st.markdown("### Bộ lọc lịch sử")
            hist=filter_history_controls(hist,"support_history",date_candidates=["closed_time","end_time","evaluated_at","start_time"],staff_cols=["support_name","qlkh_name"])
            if hist.empty: st.info("Không có hồ sơ lịch sử theo bộ lọc.")
            else:
                hist=hist.sort_values(["closed_time_dt","cif"],ascending=[False,True],na_position="last",kind="stable")
                attention_banner("🔔 Click trực tiếp một dòng trong bảng lịch sử để xem toàn bộ lịch sử xử lý / đánh giá")
                hrow=selectable_task_table(hist,"support_history_table",include_phase=False,height=_history_table_height(len(hist),620))
                if hrow is not None:
                    tid=int(hrow.id)
                    render_task_chips(hrow,time_label="Kết thúc",time_field="closed_time")
                    task_history(tid)

def qlkh_page(u):
    if st.session_state.pop("reset_ql_create_fields",False):
        for k in ["ql_new_cust_selected_id","ql_new_cust_query","ql_new_amount","ql_new_note","ql_new_currency","ql_new_task_type","ql_new_support","ql_new_validation"]: st.session_state.pop(k,None)
    page_title("Tác nghiệp – Cán bộ QLKH","QLKH giao hồ sơ cho Cán bộ hỗ trợ, theo dõi tiến độ và đánh giá sau khi công việc hoàn thành.")
    mine_all=enrich_tasks(qdf("""SELECT t.id,t.task_code,c.cif,c.customer_name,s.full_name support_name,q.full_name qlkh_name,
                                   t.support_user_id,t.qlkh_user_id,t.request_source,t.assigned_at,t.accepted_at,t.first_accepted_at,t.returned_to_qlkh_at,t.cancelled_at,t.evaluated_at,t.last_rework_at,
                                   t.task_type,t.amount,t.currency,t.fx_rate,t.amount_vnd,t.start_time,t.end_time,t.closed_time,t.note,t.status,t.current_round,t.rework_count,
                                   e.quality_score,e.progress_score,e.comment
                                   FROM tasks t JOIN customers c ON c.id=t.customer_id JOIN users s ON s.id=t.support_user_id JOIN users q ON q.id=t.qlkh_user_id
                                   LEFT JOIN evaluations e ON e.task_id=t.id AND e.round_no=t.current_round WHERE t.qlkh_user_id=?""",(u["id"],)))
    wait=int((mine_all.status=="PENDING_ACCEPTANCE").sum()) if not mine_all.empty else 0; work=int(mine_all.status.isin(["OPEN","REWORK"]).sum()) if not mine_all.empty else 0; returned=int((mine_all.status=="RETURNED_TO_QLKH").sum()) if not mine_all.empty else 0; pending=mine_all[mine_all.status.eq("PENDING_REVIEW")].copy() if not mine_all.empty else pd.DataFrame(); closed=int((mine_all.status=="CLOSED").sum()) if not mine_all.empty else 0
    ops_action_cards("qlkh_view",[("assigned","📤","Chờ CBHT tiếp nhận",wait,True,wait>0),("assigned","↩️","CBHT trả lại",returned,True,returned>0,{"qlkh_focus":"returned"}),("assigned","🛠️","CBHT đang xử lý",work,True,False),("review","⭐","Chờ tôi đánh giá",len(pending),True,len(pending)>0),("history","✅","Đã kết thúc",closed,False,False)])
    view=pill_nav("qlkh_view",[("create","➕ Tạo / giao hồ sơ"),("review","⭐ Công việc chờ đánh giá"),("assigned","📂 Hồ sơ tôi phụ trách"),("history","🕘 Lịch sử đánh giá")],default="create",prefix="subnav_qlkh")
    if view=="create":
        _flash=st.session_state.pop("qlkh_create_flash",None)
        if _flash: st.success(_flash)
        validation=st.session_state.get("ql_new_validation",{}); types=active_task_types(); cust=customer_selector("ql_new_cust",validation.get("customer")); support_df=all_users("Cán bộ hỗ trợ",active_only=True); sid=None
        if support_df.empty: st.error("Chưa có Cán bộ hỗ trợ đang hoạt động.")
        else:
            opts=support_df.id.astype(int).tolist(); sid=st.selectbox("Cán bộ hỗ trợ thực hiện",opts,index=None,key="ql_new_support",placeholder="Chọn Cán bộ hỗ trợ",format_func=lambda x:f"{support_df[support_df.id==x].iloc[0].full_name} ({support_df[support_df.id==x].iloc[0].username})")
        if validation.get("support"): required_error(validation["support"])
        task_type=st.selectbox("Công việc",types.name.tolist() if not types.empty else DEFAULT_TASK_TYPES,key="ql_new_task_type");
        if validation.get("task_type"): required_error(validation["task_type"])
        ccur,camt=st.columns([1,3]); currency=ccur.selectbox("Đơn vị",["VND","USD","EUR"],key="ql_new_currency"); amount_text=camt.text_input("Giá trị",placeholder="Ví dụ: 1.000.000",key="ql_new_amount"); amount=parse_amount_text(amount_text)
        if validation.get("currency"): required_error(validation["currency"])
        if validation.get("amount"): required_error(validation["amount"])
        rates=st.session_state.get("fx_rates",{"VND":1.0}); rate=float(rates.get(currency,0) or 0); amount_vnd=amount*rate if rate else 0
        if amount>0:
            if currency=="VND": st.caption(f"Giá trị: **{money(amount)} VND**")
            elif rate>0: st.caption(f"Tỷ giá mua chuyển khoản BIDV: **1 {currency} = {money(rate)} VND** → Quy đổi: **{money(amount_vnd)} VND**")
            else: st.error(f"Chưa có tỷ giá {currency}/VND. Bấm **Cập nhật tỷ giá BIDV** ở thanh bên để thử lại.")
        note=st.text_area("Ghi chú / yêu cầu xử lý (không bắt buộc)",key="ql_new_note")
        if st.button("Giao hồ sơ cho Cán bộ hỗ trợ",type="primary",use_container_width=True,key="ql_create_btn"):
            errors={}
            if not cust: errors["customer"]="Bắt buộc chọn khách hàng theo CIF/Tên khách hàng."
            if sid is None: errors["support"]="Bắt buộc chọn Cán bộ hỗ trợ thực hiện."
            if not task_type: errors["task_type"]="Bắt buộc chọn loại công việc."
            if not currency: errors["currency"]="Bắt buộc chọn đơn vị tiền."
            if amount<=0: errors["amount"]="Bắt buộc nhập Giá trị lớn hơn 0."
            if currency!="VND" and rate<=0: errors["amount"]=f"Chưa lấy được tỷ giá {currency}/VND từ BIDV nên chưa thể giao tác nghiệp ngoại tệ."
            if errors: st.session_state["ql_new_validation"]=errors; st.rerun()
            ts=now_str(); tid=execute("""INSERT INTO tasks(customer_id,support_user_id,qlkh_user_id,request_source,assigned_at,accepted_at,task_type,amount,currency,fx_rate,amount_vnd,start_time,due_time,note,status,current_round,rework_count,created_at,updated_at) VALUES(?,?,?,'QLKH',?,NULL,?,?,?,?,?,?,NULL,?,'PENDING_ACCEPTANCE',1,0,?,?)""",(int(cust["id"]),int(sid),u["id"],ts,task_type,amount,currency,rate or 1,amount_vnd,ts,note.strip(),ts,ts)); code=task_code(tid); execute("UPDATE tasks SET task_code=? WHERE id=?",(code,tid)); sname=support_df[support_df.id==int(sid)].iloc[0].full_name; log_action(tid,u["id"],"CREATE",f"QLKH tạo hồ sơ lúc {fmt_dt(ts)}; {task_type}; giá trị={money(amount)} {currency}"); log_action(tid,u["id"],"ASSIGN",f"Giao cho CB hỗ trợ {sname} lúc {fmt_dt(ts)}"); st.session_state["reset_ql_create_fields"]=True; st.session_state["qlkh_view"]="create"; st.session_state["qlkh_create_flash"]="Đã giao hồ sơ cho Cán bộ hỗ trợ."; st.rerun()
    elif view=="review":
        if pending.empty: st.success("Không có công việc đang chờ đánh giá.")
        else:
            pending=pending.sort_values(["end_dt","cif"],ascending=[True,True],kind="stable"); attention_banner("Chọn trực tiếp một dòng công việc cần đánh giá")
            row=selectable_task_table(pending,"eval_task_table",include_phase=True,height=_task_list_height(len(pending),540))
            if row is not None:
                tid=int(row.id); elapsed_min=round((parse_dt(row.end_time)-parse_dt(row.start_time)).total_seconds()/60) if row.end_time and row.start_time else 0
                render_task_chips(row,time_label="Kết thúc",time_field="end_time")
                st.caption(f"Thời gian xử lý: **{money(elapsed_min)} phút**" + (f" · Ghi chú: {row.note}" if row.note else ""))
                scores=[x/2 for x in range(0,21)]
                with st.form(f"eval_form_{tid}_{int(row.current_round)}"):
                    q=st.select_slider("Chất lượng",options=scores,value=5.0,key=f"q_{tid}_{int(row.current_round)}"); p=st.select_slider("Tiến độ",options=scores,value=5.0,key=f"p_{tid}_{int(row.current_round)}"); comment=st.text_area("Góp ý / nhận xét",key=f"comment_{tid}_{int(row.current_round)}"); submit=st.form_submit_button("⭐ Lưu đánh giá & kết thúc",use_container_width=True,type="primary")
                if submit:
                    if (q<9 or p<9) and not comment.strip(): st.error("Điểm dưới 9 bắt buộc phải nhập Góp ý trước khi lưu.")
                    else:
                        try:
                            ts=now_str(); execute("INSERT INTO evaluations(task_id,round_no,evaluator_user_id,quality_score,progress_score,comment,created_at) VALUES(?,?,?,?,?,?,?)",(tid,int(row.current_round),u["id"],q,p,comment.strip(),ts)); execute("UPDATE tasks SET status='CLOSED',closed_time=?,evaluated_at=?,updated_at=? WHERE id=? AND status='PENDING_REVIEW'",(ts,ts,ts,tid)); log_action(tid,u["id"],"EVALUATE",f"Đánh giá lúc {fmt_dt(ts)}; Chất lượng={q}; Tiến độ={p}; Góp ý={comment.strip()}; tự động kết thúc"); st.success("Đã lưu đánh giá và kết thúc tác nghiệp."); st.rerun()
                        except sqlite3.IntegrityError: st.error("Vòng công việc này đã được đánh giá trước đó.")
    elif view=="assigned":
        returned_df = mine_all[mine_all.status.eq("RETURNED_TO_QLKH")].copy() if not mine_all.empty else pd.DataFrame()
        tracking = mine_all[~mine_all.status.isin(["CLOSED","CANCELLED","RETURNED_TO_QLKH"])].copy() if not mine_all.empty else pd.DataFrame()
        focus = st.session_state.pop("qlkh_focus", None)

        def _manage_assignment(rsel, key_prefix):
            tid=int(rsel.id)
            render_task_chips(rsel,time_label="Giao",time_field="assigned_at")
            task_history(tid)
            status_now=str(rsel.status)
            first_accept=parse_dt(rsel.get("first_accepted_at"))
            if status_now not in ("PENDING_ACCEPTANCE","RETURNED_TO_QLKH"):
                return
            st.markdown("### Điều phối hồ sơ")
            support_df=all_users("Cán bộ hỗ trợ",active_only=True)
            if support_df.empty:
                st.error("Không có Cán bộ hỗ trợ đang hoạt động để phân công.")
                return
            sup_ids=support_df.id.astype(int).tolist(); current_sid=int(rsel.support_user_id); idx=sup_ids.index(current_sid) if current_sid in sup_ids else 0
            new_sid=st.selectbox("Cán bộ hỗ trợ xử lý",sup_ids,index=idx,key=f"{key_prefix}_support_{tid}",format_func=lambda x:f"{support_df[support_df.id==x].iloc[0].full_name} ({support_df[support_df.id==x].iloc[0].username})")
            reason=st.text_input("Lý do đổi/giao lại (khuyến nghị ghi để audit)",key=f"{key_prefix}_reason_{tid}")
            if status_now=="PENDING_ACCEPTANCE":
                c1,c2=st.columns([2,1])
                if c1.button("🔁 Đổi Cán bộ hỗ trợ",use_container_width=True,key=f"{key_prefix}_reassign_{tid}"):
                    if int(new_sid)==current_sid:
                        st.info("Bạn đang chọn đúng Cán bộ hỗ trợ hiện tại, chưa có thay đổi.")
                    else:
                        ts=now_str(); old_name=str(rsel.support_name); new_name=support_df[support_df.id==int(new_sid)].iloc[0].full_name
                        execute("UPDATE tasks SET support_user_id=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='PENDING_ACCEPTANCE'",(int(new_sid),ts,tid,u["id"]))
                        log_action(tid,u["id"],"QLKH_REASSIGN",f"Đổi CBHT khi đang chờ tiếp nhận: {old_name} -> {new_name} lúc {fmt_dt(ts)}; lý do={reason.strip() or 'không ghi'}; giữ nguyên mốc giao {fmt_dt(rsel.assigned_at)} và mốc tiếp nhận lần đầu (nếu có)")
                        st.success("Đã đổi Cán bộ hỗ trợ. Các mốc thời gian gốc không thay đổi."); st.rerun()
                delete_reason=st.text_input("Lý do xóa/hủy hồ sơ chưa tiếp nhận",key=f"{key_prefix}_cancel_reason_{tid}")
                if c2.button("🗑️ Xóa công việc",use_container_width=True,key=f"{key_prefix}_cancel_{tid}"):
                    if first_accept is not None:
                        st.error("Hồ sơ đã từng được CBHT tiếp nhận nên không được xóa. Có thể tiếp tục điều phối/giao lại nhưng mốc thời gian gốc luôn được giữ.")
                    elif not delete_reason.strip():
                        st.error("Bắt buộc nhập lý do xóa/hủy để lưu dấu vết audit.")
                    else:
                        ts=now_str(); execute("UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='PENDING_ACCEPTANCE' AND first_accepted_at IS NULL",(ts,ts,tid,u["id"])); log_action(tid,u["id"],"QLKH_CANCEL",f"QLKH xóa/hủy hồ sơ chưa tiếp nhận lúc {fmt_dt(ts)}; lý do={delete_reason.strip()}; giữ bản ghi để thống kê/audit"); st.success("Đã hủy hồ sơ. Bản ghi và mốc thời gian vẫn được giữ để thống kê/audit."); st.rerun()
            else:
                st.warning("↩️ Hồ sơ này đã được CBHT trả lại và được tách riêng khỏi danh sách đang xử lý. Khi giao lại, hệ thống giữ nguyên toàn bộ mốc thời gian gốc.")
                if st.button("📤 Giao lại hồ sơ cho Cán bộ hỗ trợ",type="primary",use_container_width=True,key=f"{key_prefix}_reopen_{tid}"):
                    ts=now_str(); new_name=support_df[support_df.id==int(new_sid)].iloc[0].full_name; old_name=str(rsel.support_name)
                    if int(new_sid)!=current_sid:
                        log_action(tid,u["id"],"QLKH_REASSIGN",f"Đổi CBHT khi giao lại: {old_name} -> {new_name} lúc {fmt_dt(ts)}; lý do={reason.strip() or 'không ghi'}")
                    execute("""UPDATE tasks SET support_user_id=?,status='PENDING_ACCEPTANCE',accepted_at=NULL,updated_at=?
                               WHERE id=? AND qlkh_user_id=? AND status='RETURNED_TO_QLKH'""",(int(new_sid),ts,tid,u["id"]))
                    log_action(tid,u["id"],"REOPEN_ASSIGN",f"Giao lại cho CBHT {new_name} lúc {fmt_dt(ts)}; lý do={reason.strip() or 'không ghi'}; mốc giao ban đầu={fmt_dt(rsel.assigned_at)}")
                    st.success("Đã giao lại hồ sơ. Mốc thời gian ban đầu được giữ nguyên."); st.rerun()
                delete_reason=st.text_input("Lý do xóa/hủy hồ sơ CBHT đã trả lại",key=f"{key_prefix}_cancel_returned_reason_{tid}")
                if st.button("🗑️ Xóa / hủy công việc đã trả lại",use_container_width=True,key=f"{key_prefix}_cancel_returned_{tid}"):
                    if not delete_reason.strip():
                        st.error("Bắt buộc nhập lý do xóa/hủy để lưu dấu vết audit.")
                    else:
                        ts=now_str()
                        execute("UPDATE tasks SET status='CANCELLED',cancelled_at=?,updated_at=? WHERE id=? AND qlkh_user_id=? AND status='RETURNED_TO_QLKH'",(ts,ts,tid,u["id"]))
                        prior_accept = fmt_dt(rsel.first_accepted_at) if first_accept is not None else "chưa từng tiếp nhận"
                        log_action(tid,u["id"],"QLKH_CANCEL",f"QLKH xóa/hủy hồ sơ sau khi CBHT trả lại lúc {fmt_dt(ts)}; lý do={delete_reason.strip()}; tiếp nhận lần đầu={prior_accept}; giữ nguyên toàn bộ mốc thời gian và lịch sử để thống kê/audit")
                        st.success("Đã hủy hồ sơ CBHT trả lại. Bản ghi, mốc giao/tiếp nhận/xử lý và lịch sử audit vẫn được giữ nguyên.")
                        st.rerun()

        st.markdown("### ↩️ Hồ sơ CBHT trả lại – chờ QLKH xử lý")
        if returned_df.empty:
            st.success("Không có hồ sơ nào đang ở trạng thái CBHT trả lại QLKH.")
        else:
            if focus=="returned":
                st.warning("🔔 Có hồ sơ CBHT vừa trả lại. Vui lòng xem lý do và giao lại/điều phối theo nhu cầu.")
            returned_df=returned_df.sort_values(["returned_to_qlkh_at_dt","cif"],ascending=[True,True],kind="stable",na_position="last")
            attention_banner("Chọn trực tiếp một dòng hồ sơ CBHT trả lại để xử lý riêng")
            rret=selectable_task_table(returned_df,"qlkh_returned_table",include_phase=True,height=_task_list_height(len(returned_df),520))
            if rret is not None:
                _manage_assignment(rret,"ql_returned")

        st.markdown("### 📂 Hồ sơ đang theo dõi")
        if tracking.empty:
            st.info("Không có hồ sơ đang chờ tiếp nhận/đang xử lý/chờ đánh giá.")
        else:
            ordered=tracking.copy(); tmp=[]; tg=_workflow_delay_targets()
            for _,r in ordered.iterrows(): tmp.append(_phase_delay_info(r,tg)["start"])
            ordered["_phase_start"]=tmp; ordered=ordered.sort_values(["_phase_start","cif"],ascending=[True,True],na_position="last")
            attention_banner("Chọn trực tiếp một dòng hồ sơ đang theo dõi để xem mốc thời gian / lịch sử")
            rsel=selectable_task_table(ordered,"qlkh_assigned_table",include_phase=True,height=_task_list_height(len(ordered),560))
            if rsel is not None:
                if str(rsel.status)=="PENDING_ACCEPTANCE":
                    _manage_assignment(rsel,"ql_pending")
                else:
                    tid=int(rsel.id); render_task_chips(rsel,time_label="Giao",time_field="assigned_at"); task_history(tid)
    elif view=="history":
        hist=qdf("""SELECT t.id task_id,t.task_code,c.cif,c.customer_name,s.full_name support_name,t.task_type,
                           e.round_no,e.quality_score,e.progress_score,e.comment,e.created_at
                    FROM evaluations e
                    JOIN tasks t ON t.id=e.task_id
                    JOIN customers c ON c.id=t.customer_id
                    JOIN users s ON s.id=t.support_user_id
                    WHERE e.evaluator_user_id=?
                    ORDER BY e.created_at DESC,c.cif ASC""",(u["id"],))
        if hist.empty:
            st.info("Chưa có lịch sử đánh giá.")
        else:
            st.markdown("### Bộ lọc lịch sử")
            hist=filter_history_controls(hist,"qlkh_history",date_candidates=["created_at"],staff_cols=["support_name"])
            if hist.empty:
                st.info("Không có lịch sử đánh giá theo bộ lọc.")
            else:
                raw=hist.reset_index(drop=True).copy()
                show=raw.copy()
                show["Điểm TB"]=(pd.to_numeric(show.quality_score,errors="coerce")+pd.to_numeric(show.progress_score,errors="coerce"))/2
                show["created_at"]=show["created_at"].map(fmt_dt)
                show["quality_score"]=show["quality_score"].map(fmt_score)
                show["progress_score"]=show["progress_score"].map(fmt_score)
                show["Điểm TB"]=show["Điểm TB"].map(fmt_score)
                display=show.rename(columns={"task_code":"Mã TN","cif":"CIF","customer_name":"Khách hàng","support_name":"CB hỗ trợ","task_type":"Công việc","round_no":"Vòng","quality_score":"Chất lượng","progress_score":"Tiến độ","comment":"Góp ý","created_at":"Thời gian"})
                display=display[["Mã TN","CIF","Khách hàng","CB hỗ trợ","Công việc","Vòng","Chất lượng","Tiến độ","Điểm TB","Góp ý","Thời gian"]]
                attention_banner("🔔 Click trực tiếp một dòng trong bảng lịch sử để xem toàn bộ lịch sử hồ sơ")
                try:
                    event=st.dataframe(display,use_container_width=True,hide_index=True,on_select="rerun",selection_mode="single-row",key="qlkh_history_table",height=_history_table_height(len(display),620))
                    rows=getattr(getattr(event,"selection",None),"rows",[]) if event is not None else []
                except TypeError:
                    st.dataframe(display,use_container_width=True,hide_index=True,height=_history_table_height(len(display),620))
                    rows=[]
                if rows:
                    rr=raw.iloc[int(rows[0])]
                    task_id=int(rr.task_id)
                    # Lấy thông tin task hiện tại để hiển thị chip trước lịch sử.
                    task_df=enrich_tasks(qdf("""SELECT t.id,t.task_code,c.cif,c.customer_name,s.full_name support_name,q.full_name qlkh_name,
                                                     t.support_user_id,t.qlkh_user_id,t.task_type,t.amount,t.currency,t.fx_rate,t.amount_vnd,
                                                     t.assigned_at,t.start_time,t.end_time,t.closed_time,t.status,t.current_round,t.rework_count
                                              FROM tasks t JOIN customers c ON c.id=t.customer_id
                                              JOIN users s ON s.id=t.support_user_id JOIN users q ON q.id=t.qlkh_user_id
                                              WHERE t.id=?""",(task_id,)))
                    if not task_df.empty:
                        render_task_chips(task_df.iloc[0],time_label="Kết thúc",time_field="closed_time")
                    task_history(task_id)

def leader_page(u):
    # Legacy QA label retained: 🔔 Hồ sơ cần quản lý / làm lại
    page_title("Quản lý công việc – Lãnh đạo phòng","Theo dõi công việc chưa kết thúc theo mức độ trễ; hồ sơ CBHT trả lại được tách riêng để dễ kiểm soát.")
    sql,params=visible_tasks_sql(u); df=enrich_tasks(qdf(sql,params)); active=df[~df.status.isin(["CLOSED","CANCELLED"])].copy() if not df.empty else pd.DataFrame(); closed=df[df.status.eq("CLOSED")].copy() if not df.empty else pd.DataFrame()
    returned_active=active[active.status.eq("RETURNED_TO_QLKH")].copy() if not active.empty else pd.DataFrame()
    normal_active=active[~active.status.eq("RETURNED_TO_QLKH")].copy() if not active.empty else pd.DataFrame()
    ops_action_cards("leader_view",[("active","↩️","CBHT trả lại QLKH",len(returned_active),True,len(returned_active)>0,{"leader_focus":"returned"}),("active","⚠️","Đang/chờ xử lý",len(normal_active),True,len(normal_active)>0),("history","✅","Đã kết thúc",len(closed),False,False)])
    view=pill_nav("leader_view",[("active","📋 Công việc đang theo dõi"),("history","🕘 Lịch sử & yêu cầu làm lại")],default="active",prefix="subnav_leader")
    if view=="active":
        focus=st.session_state.pop("leader_focus",None)
        st.markdown("### ↩️ Hồ sơ CBHT trả lại QLKH")
        if returned_active.empty:
            st.success("Không có hồ sơ CBHT trả lại đang chờ QLKH xử lý.")
        else:
            if focus=="returned": st.warning("🔔 Có hồ sơ CBHT trả lại đang cần được theo dõi/điều phối.")
            rt=returned_active.sort_values(["returned_to_qlkh_at_dt","cif"],ascending=[True,True],na_position="last",kind="stable")
            attention_banner("Chọn trực tiếp một dòng hồ sơ CBHT trả lại để xem lịch sử / điều chuyển")
            rr=selectable_task_table(rt,"leader_returned_table",include_phase=True,height=_task_list_height(len(rt),520))
            if rr is not None:
                tid=int(rr.id); render_task_chips(rr,time_label="CBHT trả lại",time_field="returned_to_qlkh_at"); task_history(tid)
                st.markdown("### Điều chuyển người xử lý / QLKH"); support=all_users("Cán bộ hỗ trợ",active_only=True); qlkh=all_users("Cán bộ QLKH",active_only=True)
                if not support.empty and not qlkh.empty:
                    sup_ids=support.id.astype(int).tolist(); q_ids=qlkh.id.astype(int).tolist(); sup_index=sup_ids.index(int(rr.support_user_id)) if int(rr.support_user_id) in sup_ids else 0; q_index=q_ids.index(int(rr.qlkh_user_id)) if int(rr.qlkh_user_id) in q_ids else 0; cc1,cc2=st.columns(2); new_sup=cc1.selectbox("CB hỗ trợ",sup_ids,index=sup_index,key=f"ret_sup_{tid}",format_func=lambda x:support[support.id==x].iloc[0].full_name); new_q=cc2.selectbox("CB QLKH",q_ids,index=q_index,key=f"ret_ql_{tid}",format_func=lambda x:qlkh[qlkh.id==x].iloc[0].full_name)
                    if st.button("Cập nhật phân công",key=f"ret_assign_{tid}"):
                        execute("UPDATE tasks SET support_user_id=?,qlkh_user_id=?,updated_at=? WHERE id=?",(int(new_sup),int(new_q),now_str(),tid)); log_action(tid,u["id"],"REASSIGN",f"support_user_id={new_sup}; qlkh_user_id={new_q}; hồ sơ đang ở trạng thái CBHT trả lại"); st.success("Đã cập nhật phân công."); st.rerun()

        st.markdown("### 📋 Hồ sơ đang/chờ xử lý")
        if normal_active.empty:
            st.info("Không có hồ sơ đang/chờ xử lý khác.")
        else:
            ordered=normal_active.copy(); tg=_workflow_delay_targets(); ordered["_phase_start"]=[_phase_delay_info(r,tg)["start"] for _,r in ordered.iterrows()]; ordered=ordered.sort_values(["_phase_start","cif"],ascending=[True,True],na_position="last")
            attention_banner("Chọn trực tiếp một dòng hồ sơ chưa kết thúc để xem lịch sử / điều chuyển")
            r=selectable_task_table(ordered,"leader_manage_table",include_phase=True,height=_task_list_height(len(ordered),580))
            if r is not None:
                tid=int(r.id); render_task_chips(r,time_label="Giao",time_field="assigned_at"); task_history(tid)
                st.markdown("### Điều chuyển người xử lý / QLKH"); support=all_users("Cán bộ hỗ trợ",active_only=True); qlkh=all_users("Cán bộ QLKH",active_only=True)
                if not support.empty and not qlkh.empty:
                    sup_ids=support.id.astype(int).tolist(); q_ids=qlkh.id.astype(int).tolist(); sup_index=sup_ids.index(int(r.support_user_id)) if int(r.support_user_id) in sup_ids else 0; q_index=q_ids.index(int(r.qlkh_user_id)) if int(r.qlkh_user_id) in q_ids else 0; cc1,cc2=st.columns(2); new_sup=cc1.selectbox("CB hỗ trợ",sup_ids,index=sup_index,key=f"sup_{tid}",format_func=lambda x:support[support.id==x].iloc[0].full_name); new_q=cc2.selectbox("CB QLKH",q_ids,index=q_index,key=f"ql_{tid}",format_func=lambda x:qlkh[qlkh.id==x].iloc[0].full_name)
                    if st.button("Cập nhật phân công",key=f"assign_{tid}"):
                        execute("UPDATE tasks SET support_user_id=?,qlkh_user_id=?,updated_at=? WHERE id=?",(int(new_sup),int(new_q),now_str(),tid)); log_action(tid,u["id"],"REASSIGN",f"support_user_id={new_sup}; qlkh_user_id={new_q}"); st.success("Đã cập nhật phân công."); st.rerun()
    elif view=="history":
        if closed.empty:
            st.info("Chưa có hồ sơ đã kết thúc.")
        else:
            closed = closed.copy()
            st.markdown("### Bộ lọc lịch sử")
            fc1, fc2, fc3 = st.columns([1.25, 1, 1])
            date_series = closed["closed_time_dt"].dropna() if "closed_time_dt" in closed.columns else pd.Series(dtype="datetime64[ns]")
            if not date_series.empty:
                dmin, dmax = date_series.min().date(), date_series.max().date()
                hist_dates = fc1.date_input("Ngày / khoảng ngày", value=(dmin, dmax), key="leader_history_dates")
            else:
                hist_dates = ()
            staff_options = sorted(set(closed.get("support_name", pd.Series(dtype=str)).dropna().astype(str).tolist() + closed.get("qlkh_name", pd.Series(dtype=str)).dropna().astype(str).tolist()))
            hist_staff = fc2.multiselect("Cán bộ", staff_options, key="leader_history_staff")
            task_options = sorted(closed.get("task_type", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
            hist_tasks = fc3.multiselect("Công việc", task_options, key="leader_history_task")
            filtered = closed.copy()
            if isinstance(hist_dates, tuple) and len(hist_dates) == 2 and "closed_time_dt" in filtered.columns:
                _d = filtered["closed_time_dt"].dt.date
                filtered = filtered[(_d >= hist_dates[0]) & (_d <= hist_dates[1])]
            if hist_staff:
                filtered = filtered[filtered["support_name"].isin(hist_staff) | filtered["qlkh_name"].isin(hist_staff)]
            if hist_tasks:
                filtered = filtered[filtered["task_type"].isin(hist_tasks)]
            if filtered.empty:
                st.warning("Không có hồ sơ phù hợp bộ lọc lịch sử.")
                return
            closed = filtered.sort_values(["closed_time_dt","cif"],ascending=[False,True],na_position="last")
            attention_banner("Chọn trực tiếp một dòng hồ sơ đã kết thúc để xem lịch sử hoặc yêu cầu thực hiện lại")
            r=selectable_task_table(closed,"leader_history_table",include_phase=False,height=_history_table_height(len(closed),620))
            if r is not None:
                tid=int(r.id); render_task_chips(r,time_label="Kết thúc",time_field="closed_time"); task_history(tid); reason=st.text_area("Ý kiến lãnh đạo / yêu cầu thực hiện lại",key=f"leader_reason_{tid}")
                if st.button("↩️ Yêu cầu thực hiện lại",type="primary",use_container_width=True,key=f"rework_{tid}"):
                    if not reason.strip(): st.error("Bắt buộc nhập nội dung yêu cầu thực hiện lại.")
                    else:
                        ts=now_str(); execute("UPDATE tasks SET status='REWORK',current_round=current_round+1,rework_count=rework_count+1,end_time=NULL,closed_time=NULL,evaluated_at=NULL,last_rework_at=?,start_time=?,due_time=NULL,updated_at=? WHERE id=? AND status='CLOSED'",(ts,ts,ts,tid)); log_action(tid,u["id"],"REWORK",f"Trả lại lúc {fmt_dt(ts)}; {reason.strip()}"); st.session_state["leader_view"]="active"; st.success("Đã chuyển lại Cán bộ hỗ trợ thực hiện."); st.rerun()

def make_excel_report(detail, support_privacy=False):
    from openpyxl import load_workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    f = detail.copy()
    if f.empty:
        return b""
    f["avg_score"] = (f["quality_score"] + f["progress_score"]) / 2
    for _score_col in ["quality_score","progress_score","avg_score"]:
        if _score_col in f.columns: f[_score_col] = pd.to_numeric(f[_score_col], errors="coerce").round(1)
    f["thang"] = pd.to_datetime(f.start_time).dt.strftime("%m/%Y")
    f["status_label"] = f.status.map(STATUS_LABEL).fillna(f.status)
    g_sup = f.groupby("support_name", dropna=False).agg(so_tac_nghiep=("id", "count"), gia_tri=("amount_vnd", "sum"), diem_tb=("avg_score", "mean"), tg_giao_tiep_nhan_phut=("assignment_to_accept_minutes", "mean"), tg_tb_phut=("duration_minutes", "mean"), so_lam_lai=("rework_count", "sum")).reset_index()
    g_q = f.groupby("qlkh_name", dropna=False).agg(so_tac_nghiep=("id", "count"), gia_tri=("amount_vnd", "sum"), diem_tb=("avg_score", "mean"), tg_giao_tiep_nhan_phut=("assignment_to_accept_minutes", "mean"), tg_tb_phut=("duration_minutes", "mean")).reset_index()
    g_type = f.groupby("task_type", dropna=False).agg(so_tac_nghiep=("id", "count"), gia_tri=("amount_vnd", "sum"), diem_tb=("avg_score", "mean"), tg_giao_tiep_nhan_phut=("assignment_to_accept_minutes", "mean"), tg_tb_phut=("duration_minutes", "mean"), so_lam_lai=("rework_count", "sum")).reset_index()
    try:
        _gw = time_goal_table(f, "week")
        _gm = time_goal_table(f, "month")
        if not _gw.empty:
            g_type = g_type.merge(_gw[["task_type","target_minutes"]].rename(columns={"target_minutes":"muc_tieu_tuan_phut"}), on="task_type", how="left")
        if not _gm.empty:
            g_type = g_type.merge(_gm[["task_type","target_minutes"]].rename(columns={"target_minutes":"muc_tieu_thang_phut"}), on="task_type", how="left")
    except Exception:
        _gw = pd.DataFrame(); _gm = pd.DataFrame()
    g_month = f.groupby("thang").agg(so_tac_nghiep=("id", "count"), gia_tri=("amount_vnd", "sum"), diem_tb=("avg_score", "mean"), tg_giao_tiep_nhan_phut=("assignment_to_accept_minutes", "mean"), tg_tb_phut=("duration_minutes", "mean")).reset_index()
    for _summary in [g_sup, g_q, g_type, g_month]:
        if "diem_tb" in _summary.columns: _summary["diem_tb"] = pd.to_numeric(_summary["diem_tb"], errors="coerce").round(1)
    try:
        g_week = calendar_performance_summary(f, "week", by_task=False)
        if not g_week.empty:
            g_week = g_week.rename(columns={"period_label":"tuan_calendar","period_range":"khoang_ngay","samples":"so_tac_nghiep_hoan_thanh","active_days":"so_ngay_phat_sinh","value_vnd":"gia_tri","avg_score":"diem_tb","avg_accept_wait":"tg_giao_tiep_nhan_tb_phut","avg_minutes":"tg_tb_chuan_hoa_phut"})
        goals_export = _gw.rename(columns={"current_minutes":"tg_hien_tai_tuan","target_minutes":"muc_tieu_tuan","delta_minutes":"chenh_lech_tuan","samples":"mau_tuan","active_days":"ngay_phat_sinh_tuan","target_period":"ky_chuan_tuan","status":"ket_qua_tuan"}) if not _gw.empty else pd.DataFrame()
        if not _gm.empty:
            gm2 = _gm.rename(columns={"current_minutes":"tg_hien_tai_thang","target_minutes":"muc_tieu_thang","delta_minutes":"chenh_lech_thang","samples":"mau_thang","active_days":"ngay_phat_sinh_thang","target_period":"ky_chuan_thang","status":"ket_qua_thang"})
            keep=["task_type","tg_hien_tai_thang","muc_tieu_thang","chenh_lech_thang","mau_thang","ngay_phat_sinh_thang","ky_chuan_thang","ket_qua_thang"]
            goals_export = gm2[keep] if goals_export.empty else goals_export.merge(gm2[keep],on="task_type",how="outer")
    except Exception:
        g_week = pd.DataFrame(); goals_export = pd.DataFrame()
    score_df = f[f.avg_score.notna()].copy()
    if not score_df.empty:
        score_df["dai_diem"] = pd.cut(score_df.avg_score, bins=[-0.01, 7.99, 8.99, 9.49, 10.01], labels=["<8", "8-<9", "9-<9.5", "9.5-10"])
        g_score = score_df.groupby("dai_diem", observed=False).size().reset_index(name="so_tac_nghiep")
    else:
        g_score = pd.DataFrame(columns=["dai_diem", "so_tac_nghiep"])

    detail_cols = ["task_code", "cif", "customer_name", "support_name", "qlkh_name", "request_source", "task_type", "amount", "currency", "fx_rate", "amount_vnd", "assigned_at", "first_accepted_at", "accepted_at", "assignment_to_accept_minutes", "returned_to_qlkh_at", "cancelled_at", "start_time", "end_time", "evaluated_at", "last_rework_at", "closed_time", "status_label", "current_round", "rework_count", "quality_score", "progress_score", "avg_score", "duration_minutes", "duration_hours", "note", "comment"]
    detail_cols = [c for c in detail_cols if c in f.columns]
    if support_privacy:
        detail_cols = [c for c in detail_cols if c != "qlkh_name"]
    buf = BytesIO()
    task_ids = [int(x) for x in f["id"].dropna().unique().tolist()]
    if task_ids:
        marks = ",".join(["?"] * len(task_ids))
        eval_hist = qdf(f"""SELECT t.task_code,e.round_no,u.full_name evaluator,e.quality_score,e.progress_score,e.comment,e.created_at
                              FROM evaluations e JOIN tasks t ON t.id=e.task_id JOIN users u ON u.id=e.evaluator_user_id
                              WHERE e.task_id IN ({marks}) ORDER BY t.id,e.round_no""", task_ids)
        action_hist = qdf(f"""SELECT t.task_code,a.created_at,u.full_name actor,a.action,a.detail
                                FROM task_actions a JOIN tasks t ON t.id=a.task_id JOIN users u ON u.id=a.actor_user_id
                                WHERE a.task_id IN ({marks}) ORDER BY t.id,a.id""", task_ids)
        if not eval_hist.empty:
            for _score_col in ["quality_score","progress_score"]:
                if _score_col in eval_hist.columns: eval_hist[_score_col] = pd.to_numeric(eval_hist[_score_col], errors="coerce").round(1)
        if not action_hist.empty:
            action_hist["action"] = action_hist["action"].map(ACTION_LABEL).fillna(action_hist["action"])
    else:
        eval_hist = pd.DataFrame(); action_hist = pd.DataFrame()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        f[detail_cols].to_excel(w, index=False, sheet_name="Chi_tiet")
        g_sup.to_excel(w, index=False, sheet_name="Theo_CB_ho_tro")
        if not support_privacy:
            g_q.to_excel(w, index=False, sheet_name="Theo_CB_QLKH")
        g_type.to_excel(w, index=False, sheet_name="Theo_cong_viec")
        g_month.to_excel(w, index=False, sheet_name="Theo_thang")
        if 'g_week' in locals() and not g_week.empty:
            g_week.to_excel(w, index=False, sheet_name="Theo_tuan")
        if 'goals_export' in locals() and not goals_export.empty:
            goals_export.to_excel(w, index=False, sheet_name="Muc_tieu_thoi_gian")
        g_score.to_excel(w, index=False, sheet_name="Theo_dai_diem")
        if support_privacy and not eval_hist.empty:
            eval_hist = eval_hist.drop(columns=["evaluator"], errors="ignore")
        if support_privacy and not action_hist.empty:
            action_hist = action_hist.drop(columns=["actor"], errors="ignore")
            if "detail" in action_hist.columns:
                action_hist["detail"] = action_hist["detail"].astype(str).str.replace(r";\s*QLKH=.*$", "", regex=True)
        eval_hist.to_excel(w, index=False, sheet_name="Lich_su_danh_gia")
        action_hist.to_excel(w, index=False, sheet_name="Nhat_ky_tac_nghiep")
    buf.seek(0)
    wb = load_workbook(buf)
    header_fill = PatternFill("solid", fgColor="006B68")
    header_font = Font(color="FFFFFF", bold=True)
    thin = Side(style="thin", color="D9E2E8")
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.fill = header_fill; cell.font = header_font; cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in ws.iter_rows():
            for cell in row:
                cell.border = Border(bottom=thin)
                if isinstance(cell.value, (int, float)) and cell.value < 0:
                    cell.font = Font(color="FF0000")
        headers = {str(c.value): c.column for c in ws[1]}
        for h in ["assigned_at","accepted_at","start_time","end_time","evaluated_at","last_rework_at","closed_time","created_at"]:
            if h in headers:
                for cell in next(ws.iter_cols(min_col=headers[h],max_col=headers[h],min_row=2)):
                    if isinstance(cell.value,str):
                        try: cell.value=parse_dt(cell.value)
                        except Exception: pass
                    if cell.value: cell.number_format="hh:mm dd/mm/yyyy"
        for h in ["amount","amount_vnd","gia_tri","rate_to_vnd","fx_rate","duration_minutes","tg_tb_phut"]:
            if h in headers:
                for cell in next(ws.iter_cols(min_col=headers[h],max_col=headers[h],min_row=2)): cell.number_format='#,##0'
        for h in ["quality_score","progress_score","avg_score","diem_tb"]:
            if h in headers:
                for cell in next(ws.iter_cols(min_col=headers[h],max_col=headers[h],min_row=2)): cell.number_format='0.0'
        for i, col_cells in enumerate(ws.columns, 1):
            max_len = min(45, max(10, max(len(str(c.value or "")) for c in col_cells) + 2))
            ws.column_dimensions[get_column_letter(i)].width = max_len
    # simple charts on summary sheets
    for sheet, cat_col, val_col, title in [
        ("Theo_CB_ho_tro", 1, 2, "Số tác nghiệp theo CB hỗ trợ"),
        ("Theo_cong_viec", 1, 2, "Số tác nghiệp theo công việc"),
        ("Theo_thang", 1, 2, "Số tác nghiệp theo tháng"),
        ("Theo_tuan", 2, 4, "Số tác nghiệp hoàn thành theo tuần"),
    ]:
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        if ws.max_row >= 2:
            chart = BarChart(); chart.title = title; chart.y_axis.title = "Số tác nghiệp"
            data = Reference(ws, min_col=val_col, min_row=1, max_row=ws.max_row)
            cats = Reference(ws, min_col=cat_col, min_row=2, max_row=ws.max_row)
            chart.add_data(data, titles_from_data=True); chart.set_categories(cats); chart.height = 7; chart.width = 14
            ws.add_chart(chart, "H2")
    out = BytesIO(); wb.save(out); return out.getvalue()


# ---------- Annual archive & 5-year benchmark (V2.17) ----------
def _room_data_revision():
    """Small DB revision token used to reuse the heavy room-wide task frame."""
    with get_conn() as c:
        t = c.execute("SELECT COALESCE(MAX(updated_at),''),COALESCE(MAX(id),0) FROM tasks").fetchone()
        u = c.execute("SELECT COALESCE(MAX(updated_at),''),COUNT(*) FROM users WHERE deleted_at IS NULL").fetchone()
    return f"{t[0]}|{t[1]}|{u[0]}|{u[1]}"

@_cache_data(ttl=30, show_spinner=False)
def _room_tasks_cached(revision):
    room_user = {"id": 0, "role": "Lãnh đạo phòng", "is_admin": 1}
    sql, params = visible_tasks_sql(room_user)
    return enrich_tasks(qdf(sql, params))

def _room_tasks_frame():
    """Toàn bộ dữ liệu tác nghiệp; cache theo revision để tăng tốc các rerun/filter Dashboard."""
    return _room_tasks_cached(_room_data_revision()).copy()


def _task_archive_year_series(df):
    """Năm lưu hồ sơ: ưu tiên năm kết thúc; nếu chưa kết thúc dùng mốc giao/khởi tạo."""
    if df is None or df.empty:
        return pd.Series(dtype="Int64")
    candidates = []
    for c in ["closed_time", "end_time", "assigned_at", "start_time"]:
        if c in df.columns:
            candidates.append(pd.to_datetime(df[c], errors="coerce"))
    if not candidates:
        return pd.Series(pd.NA, index=df.index, dtype="Int64")
    dt = candidates[0]
    for other in candidates[1:]:
        dt = dt.fillna(other)
    return dt.dt.year.astype("Int64")


def _annual_metrics(base_df):
    """Tổng hợp hiệu suất theo năm, chuẩn hóa theo ngày thực tế phát sinh.

    V2.19: giữ riêng ba chỉ tiêu đánh giá minh bạch: thời gian xử lý,
    chất lượng và điểm trung bình; không tạo chỉ số tổng hợp có trọng số.
    """
    x = _perf_frame(_dashboard_stat_frame(base_df))
    cols = ["year","samples","active_days","value_vnd","avg_quality","avg_score","avg_minutes","avg_accept_wait","rework_rate"]
    if x.empty:
        return pd.DataFrame(columns=cols)
    x["year"] = x["end_dt"].dt.year.astype(int)
    if "quality_score" not in x.columns:
        x["quality_score"] = math.nan
    x["quality_score"] = pd.to_numeric(x["quality_score"], errors="coerce")
    day = x.groupby(["year","activity_date"], dropna=False).agg(
        daily_avg_minutes=("duration_minutes","mean"),
        daily_accept_wait=("assignment_to_accept_minutes","mean"),
        daily_samples=("id","count"),
        daily_value_vnd=("amount_vnd","sum"),
        daily_quality=("quality_score","mean"),
        daily_score=("avg_score","mean"),
    ).reset_index()
    out = day.groupby("year").agg(
        avg_minutes=("daily_avg_minutes","mean"),
        avg_accept_wait=("daily_accept_wait","mean"),
        samples=("daily_samples","sum"),
        active_days=("activity_date","nunique"),
        value_vnd=("daily_value_vnd","sum"),
        avg_quality=("daily_quality","mean"),
        avg_score=("daily_score","mean"),
    ).reset_index()
    rework = x.groupby("year")["rework_count"].apply(
        lambda z: float((pd.to_numeric(z,errors="coerce").fillna(0)>0).mean())
    ).reset_index(name="rework_rate")
    return out.merge(rework,on="year",how="left").sort_values("year")

def five_year_benchmark(base_df, ref_time=None):
    """Chuẩn dài hạn tối đa 5 năm theo *từng chỉ tiêu độc lập*.

    Không tạo chỉ số tổng hợp và không chọn một "năm hiệu quả nhất" chung.
    Mỗi chỉ tiêu có năm chuẩn riêng trong tối đa 5 năm đã kết thúc:
    - Thời gian xử lý: năm có TG TB thấp nhất.
    - Chất lượng: năm có điểm Chất lượng TB cao nhất.
    - Điểm trung bình: năm có Điểm TB cao nhất.
    Nếu đồng hạng, ưu tiên năm gần hơn.
    """
    now = pd.Timestamp(ref_time or now_dt())
    current_year = int(now.year)
    annual = _annual_metrics(base_df)
    candidates = annual[(annual["year"] >= current_year-5) & (annual["year"] < current_year) & (annual["samples"] > 0)].copy()
    result = {"best_year": None, "benchmark": None, "metric_benchmarks": {}, "current": None, "annual": annual}
    cur = annual[annual.year.eq(current_year)]
    result["current"] = None if cur.empty else cur.iloc[0].to_dict()
    if candidates.empty:
        return result

    specs = {
        "avg_minutes": {"label":"Thời gian xử lý", "ascending":True},
        "avg_quality": {"label":"Chất lượng", "ascending":False},
        "avg_score": {"label":"Điểm trung bình", "ascending":False},
    }
    for metric, meta in specs.items():
        vals = pd.to_numeric(candidates.get(metric), errors="coerce")
        valid = candidates[vals.notna()].copy()
        if valid.empty:
            continue
        valid[metric] = pd.to_numeric(valid[metric], errors="coerce")
        valid = valid.sort_values([metric, "year"], ascending=[meta["ascending"], False], kind="stable")
        best = valid.iloc[0]
        result["metric_benchmarks"][metric] = {
            "metric": metric,
            "label": meta["label"],
            "year": int(best.year),
            "value": float(best[metric]),
            "row": best.to_dict(),
        }

    # Tương thích dữ liệu lưu trữ cũ: best_year/benchmark chỉ là năm chuẩn TG,
    # không được dùng làm chỉ số tổng hợp hay nhận xét hiệu suất chung.
    time_ref = result["metric_benchmarks"].get("avg_minutes")
    if time_ref:
        result["best_year"] = int(time_ref["year"])
        result["benchmark"] = time_ref["row"]
    return result

def _annual_group_stats(df, group_col):
    x=_dashboard_stat_frame(enrich_tasks(df.copy())) if df is not None and not df.empty else pd.DataFrame()
    if x.empty or group_col not in x.columns:
        return pd.DataFrame()
    return x.groupby(group_col,dropna=False).agg(
        so_tac_nghiep=("id","count"), gia_tri_vnd=("amount_vnd","sum"), diem_tb=("avg_score","mean"),
        tg_giao_tiep_nhan_tb=("assignment_to_accept_minutes","mean"), tg_xu_ly_tb=("duration_minutes","mean"),
        lam_lai=("rework_count","sum")
    ).reset_index()


def _annual_stats_workbook(year, year_df):
    from openpyxl import load_workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    annual=_annual_metrics(year_df)
    overall=annual[annual.year.eq(int(year))].copy()
    by_task=_annual_group_stats(year_df,"task_type")
    by_support=_annual_group_stats(year_df,"support_name")
    by_qlkh=_annual_group_stats(year_df,"qlkh_name")
    for d in [overall,by_task,by_support,by_qlkh]:
        if d is not None and not d.empty:
            if "value_vnd" in d.columns: d["gia_tri_ty"]=(pd.to_numeric(d["value_vnd"],errors="coerce").fillna(0)/1e9).round(0)
            if "gia_tri_vnd" in d.columns: d["gia_tri_ty"]=(pd.to_numeric(d["gia_tri_vnd"],errors="coerce").fillna(0)/1e9).round(0)
            if "avg_score" in d.columns: d["avg_score"]=pd.to_numeric(d["avg_score"],errors="coerce").round(1)
            if "diem_tb" in d.columns: d["diem_tb"]=pd.to_numeric(d["diem_tb"],errors="coerce").round(1)
    buf=BytesIO()
    with pd.ExcelWriter(buf,engine="openpyxl") as w:
        overall.to_excel(w,index=False,sheet_name="Tong_quan_nam")
        by_task.to_excel(w,index=False,sheet_name="Theo_cong_viec")
        by_support.to_excel(w,index=False,sheet_name="Theo_CB_ho_tro")
        by_qlkh.to_excel(w,index=False,sheet_name="Theo_CB_QLKH")
    buf.seek(0); wb=load_workbook(buf)
    for ws in wb.worksheets:
        ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
        for c in ws[1]: c.fill=PatternFill("solid",fgColor="006B68"); c.font=Font(color="FFFFFF",bold=True); c.alignment=Alignment(horizontal="center",vertical="center")
        for i,col in enumerate(ws.columns,1): ws.column_dimensions[get_column_letter(i)].width=min(38,max(11,max(len(str(c.value or "")) for c in col)+2))
        headers={str(c.value):c.column for c in ws[1]}
        for h in ["gia_tri_ty"]:
            if h in headers:
                for c in next(ws.iter_cols(min_col=headers[h],max_col=headers[h],min_row=2)): c.number_format='#,##0'
        for h in ["avg_quality","avg_score","diem_tb","avg_minutes","avg_accept_wait","tg_giao_tiep_nhan_tb","tg_xu_ly_tb","rework_rate"]:
            if h in headers:
                for c in next(ws.iter_cols(min_col=headers[h],max_col=headers[h],min_row=2)): c.number_format='0.0'
    out=BytesIO(); wb.save(out); return out.getvalue()


def _resolve_archive_path(value):
    if not value:
        return Path("")
    p=Path(str(value))
    return p if p.is_absolute() else ANNUAL_ARCHIVE_DIR/p


def archive_year(year, force=False):
    year=int(year); current=now_dt().year
    if year>=current: return None
    ANNUAL_ARCHIVE_DIR.mkdir(parents=True,exist_ok=True)
    existing=qdf("SELECT * FROM annual_archives WHERE year=?",(year,))
    if not force and not existing.empty:
        row=existing.iloc[0]
        paths=[row.get("stats_file"),row.get("detail_file"),row.get("db_backup_file")]
        if all(pp and _resolve_archive_path(pp).exists() for pp in paths): return row.to_dict()
    room=_room_tasks_frame()
    if room.empty: return None
    room["archive_year"]=_task_archive_year_series(room)
    ydf=room[room["archive_year"].eq(year)].copy()
    if ydf.empty: return None
    stats_path=ANNUAL_ARCHIVE_DIR/f"Thong_ke_hieu_suat_{year}.xlsx"
    detail_path=ANNUAL_ARCHIVE_DIR/f"Chi_tiet_tac_nghiep_{year}.xlsx"
    db_path=ANNUAL_ARCHIVE_DIR/f"KHDN_Ops_EOY_{year}.db"
    stats_path.write_bytes(_annual_stats_workbook(year,ydf))
    detail_path.write_bytes(make_excel_report(ydf,support_privacy=False))
    if Path(DB_PATH).exists(): snapshot_database(DB_PATH, db_path)
    ref=five_year_benchmark(room,ref_time=datetime(year+1,1,1))
    with get_conn() as c:
        c.execute("""INSERT INTO annual_archives(year,stats_file,detail_file,db_backup_file,task_count,archived_at,best_five_year_reference,notes)
                     VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(year) DO UPDATE SET stats_file=excluded.stats_file,detail_file=excluded.detail_file,
                     db_backup_file=excluded.db_backup_file,task_count=excluded.task_count,archived_at=excluded.archived_at,
                     best_five_year_reference=excluded.best_five_year_reference,notes=excluded.notes""",
                  (year,stats_path.name,detail_path.name,db_path.name,len(ydf),now_str(),ref.get("best_year"),"Tự động lưu sau khi kết thúc năm"))
        c.commit()
    LOGGER.info("ANNUAL_ARCHIVE year=%s tasks=%s",year,len(ydf))
    return {"year":year,"stats_file":str(stats_path),"detail_file":str(detail_path),"db_backup_file":str(db_path),"task_count":len(ydf)}


def annual_archive_maintenance():
    """Mỗi lần app khởi động, tạo các archive năm đã kết thúc còn thiếu."""
    try:
        years=qdf("""SELECT DISTINCT CAST(strftime('%Y',COALESCE(closed_time,end_time,assigned_at,start_time,created_at)) AS INTEGER) year
                     FROM tasks WHERE COALESCE(closed_time,end_time,assigned_at,start_time,created_at) IS NOT NULL""")
        if years.empty: return
        for y in sorted(int(x) for x in years.year.dropna().tolist() if int(x)<now_dt().year):
            archive_year(y,force=False)
    except Exception:
        LOGGER.exception("ANNUAL_ARCHIVE_MAINTENANCE_FAILED")


def _html_table(df, max_height=360):
    """Bảng HTML read-only: wrap nội dung, fixed layout; bảng chọn dòng vẫn dùng st.dataframe."""
    if df is None or df.empty:
        st.info("Không có dữ liệu."); return
    table=df.copy().to_html(index=False,escape=True,classes="bidv-html-table",border=0)
    st.html(f'<div class="bidv-table-wrap" style="max-height:{int(max_height)}px">{table}</div>')


def _render_five_year_benchmark(u, room_df):
    """So sánh dài hạn theo từng chỉ tiêu riêng, không có chỉ số tổng hợp."""
    if u["role"]=="Cán bộ hỗ trợ":
        scope=room_df[room_df.support_user_id.eq(int(u["id"]))].copy(); title="cá nhân"
    elif u["role"]=="Cán bộ QLKH":
        scope=room_df[room_df.qlkh_user_id.eq(int(u["id"]))].copy(); title="cá nhân"
    else:
        scope=room_df.copy(); title="toàn phòng"
    b=five_year_benchmark(scope)
    refs=b.get("metric_benchmarks") or {}
    st.markdown("### 🏆 Chuẩn tham chiếu dài hạn (tối đa 5 năm)")
    if not refs:
        st.info("Chưa có dữ liệu của năm đã kết thúc trong 5 năm gần nhất để xác lập chuẩn dài hạn.")
        return

    metric_specs=[
        ("avg_minutes","TG xử lý chuẩn"," phút",True),
        ("avg_quality","Chất lượng chuẩn"," điểm",False),
        ("avg_score","Điểm TB chuẩn"," điểm",False),
    ]
    kpis=[]
    for key,label,unit,_lower in metric_specs:
        ref=refs.get(key)
        if not ref:
            kpis.append((label,"—","Chưa đủ dữ liệu lịch sử")); continue
        kpis.append((label,f"{float(ref['value']):.1f}{unit}",f"Năm {ref['year']} · chuẩn {title}"))
    render_kpi_cards(kpis)

    cur=b.get("current") or {}
    if cur:
        cards=[]
        for key,label,unit,lower in metric_specs:
            ref=refs.get(key)
            if not ref:
                payload={"state":"neutral","headline":"—","detail":"Chưa có năm lịch sử đủ dữ liệu để so sánh."}
                year="—"
            else:
                payload=_metric_trend_payload(cur.get(key,math.nan),ref.get("value",math.nan),lower_is_better=lower,unit=unit)
                year=str(ref.get("year","—"))
            css="trend-good" if payload["state"]=="good" else ("trend-bad" if payload["state"]=="bad" else "trend-neutral")
            cards.append(f'<div class="perf-trend-card {css}"><div class="perf-trend-label">{html.escape(label)} · so với {html.escape(year)}</div><div class="perf-trend-value">{html.escape(payload["headline"])}</div><div class="perf-trend-detail">{html.escape(payload["detail"])}</div></div>')
        st.html(f'<div class="perf-period"><div class="perf-period-title">{now_dt().year} YTD · nhận xét riêng từng chỉ tiêu</div><div class="perf-trend-grid">{"".join(cards)}</div></div>')

    if u.get("is_admin") or u.get("role")=="Lãnh đạo phòng":
        rows=[]
        for role,idcol in [("Cán bộ hỗ trợ","support_user_id"),("Cán bộ QLKH","qlkh_user_id")]:
            roster=all_users(role,active_only=True)
            for _,person in roster.iterrows():
                pdata=room_df[room_df[idcol].eq(int(person.id))].copy() if idcol in room_df.columns else pd.DataFrame()
                pb=five_year_benchmark(pdata); pref=pb.get("metric_benchmarks") or {}; current=pb.get("current") or {}
                row={"Cán bộ":person.full_name,"Vai trò":role}
                for key,prefix,lower in [("avg_minutes","TG",True),("avg_quality","Chất lượng",False),("avg_score","Điểm",False)]:
                    rr=pref.get(key) or {}; val=rr.get("value",math.nan); cv=current.get(key,math.nan)
                    row[f"Năm chuẩn {prefix}"]=rr.get("year","—")
                    if pd.notna(cv) and pd.notna(val) and abs(float(val))>1e-12:
                        row[f"Δ {prefix} %"]=(float(cv)-float(val))/abs(float(val))*100.0
                    else:
                        row[f"Δ {prefix} %"]=math.nan
                rows.append(row)
        if rows:
            d=pd.DataFrame(rows)
            for c in ["Δ TG %","Δ Chất lượng %","Δ Điểm %"]:
                d[c]=d[c].map(lambda x:f"{float(x):.1f}" if pd.notna(x) else "—")
            _html_table(d,max_height=420)

def _perf_frame(base_df):
    """Chuẩn hóa dữ liệu đã hoàn thành để đo hiệu suất thời gian."""
    if base_df is None or len(base_df) == 0:
        return pd.DataFrame()
    x = base_df.copy()
    if "end_dt" not in x.columns:
        x["end_dt"] = pd.to_datetime(x.get("end_time"), errors="coerce")
    if "start_dt" not in x.columns:
        x["start_dt"] = pd.to_datetime(x.get("start_time"), errors="coerce")
    if "duration_minutes" not in x.columns:
        x["duration_minutes"] = (x["end_dt"] - x["start_dt"]).dt.total_seconds() / 60.0
    x["duration_minutes"] = pd.to_numeric(x["duration_minutes"], errors="coerce")
    if "amount_vnd" not in x.columns:
        if "amount" in x.columns:
            x["amount_vnd"] = pd.to_numeric(x["amount"], errors="coerce").fillna(0)
        else:
            x["amount_vnd"] = 0.0
    if "avg_score" not in x.columns:
        q = pd.to_numeric(x["quality_score"], errors="coerce") if "quality_score" in x.columns else pd.Series(index=x.index, dtype="float64")
        p = pd.to_numeric(x["progress_score"], errors="coerce") if "progress_score" in x.columns else pd.Series(index=x.index, dtype="float64")
        x["avg_score"] = (q + p) / 2
    if "assignment_to_accept_minutes" not in x.columns:
        assigned_raw = x["assigned_at"] if "assigned_at" in x.columns else pd.Series(pd.NaT, index=x.index)
        first_raw = x["first_accepted_at"] if "first_accepted_at" in x.columns else (x["accepted_at"] if "accepted_at" in x.columns else pd.Series(pd.NaT, index=x.index))
        assigned = pd.to_datetime(assigned_raw, errors="coerce")
        first_accept = pd.to_datetime(first_raw, errors="coerce")
        if "accepted_at" in x.columns:
            first_accept = first_accept.fillna(pd.to_datetime(x["accepted_at"], errors="coerce"))
        x["assignment_to_accept_minutes"] = (first_accept - assigned).dt.total_seconds() / 60.0
    x["assignment_to_accept_minutes"] = pd.to_numeric(x["assignment_to_accept_minutes"], errors="coerce")
    x = x[x["end_dt"].notna() & x["duration_minutes"].notna() & (x["duration_minutes"] >= 0)].copy()
    if x.empty:
        return x
    x["activity_date"] = x["end_dt"].dt.normalize()
    return x


def _period_start_series(dt_series, freq):
    dt = pd.to_datetime(dt_series, errors="coerce")
    if freq == "week":
        return (dt - pd.to_timedelta(dt.dt.weekday, unit="D")).dt.normalize()
    if freq == "month":
        return dt.dt.to_period("M").dt.to_timestamp()
    raise ValueError("freq phải là week hoặc month")


def _period_label(start, freq):
    if pd.isna(start):
        return ""
    ts = pd.Timestamp(start)
    if freq == "week":
        iso = ts.isocalendar()
        return f"T{int(iso.week):02d}/{int(iso.year)}"
    return ts.strftime("%m/%Y")


def _period_range_label(start, freq):
    if pd.isna(start):
        return ""
    ts = pd.Timestamp(start)
    if freq == "week":
        end = ts + pd.Timedelta(days=6)
        return f"{ts:%d/%m}–{end:%d/%m/%Y}"
    end = ts + pd.offsets.MonthEnd(0)
    return f"{ts:%d/%m}–{end:%d/%m/%Y}"


def calendar_performance_summary(base_df, freq="week", by_task=True):
    """Bình quân calendar chuẩn hóa theo **ngày thực tế phát sinh**.

    Mỗi ngày phát sinh được tính bình quân trước, sau đó mới bình quân các ngày
    trong tuần/tháng. V2.19 bổ sung Chất lượng TB để đánh giá xu hướng riêng,
    không trộn vào chỉ số hiệu suất tổng hợp.
    """
    x = _perf_frame(base_df)
    keys = (["task_type"] if by_task else []) + ["period_start"]
    if x.empty:
        cols = (["task_type"] if by_task else []) + ["period_start", "period_label", "period_range", "avg_minutes", "avg_accept_wait", "samples", "active_days", "value_vnd", "avg_quality", "avg_score"]
        return pd.DataFrame(columns=cols)
    if "quality_score" not in x.columns:
        x["quality_score"] = math.nan
    x["quality_score"] = pd.to_numeric(x["quality_score"], errors="coerce")
    x["period_start"] = _period_start_series(x["end_dt"], freq)
    day_keys = (["task_type"] if by_task else []) + ["period_start", "activity_date"]
    daily = x.groupby(day_keys, dropna=False).agg(
        daily_avg_minutes=("duration_minutes", "mean"),
        daily_accept_wait=("assignment_to_accept_minutes", "mean"),
        daily_samples=("id", "count"),
        daily_value_vnd=("amount_vnd", "sum"),
        daily_quality=("quality_score", "mean"),
        daily_score=("avg_score", "mean"),
    ).reset_index()
    out = daily.groupby(keys, dropna=False).agg(
        avg_minutes=("daily_avg_minutes", "mean"),
        avg_accept_wait=("daily_accept_wait", "mean"),
        samples=("daily_samples", "sum"),
        active_days=("activity_date", "nunique"),
        value_vnd=("daily_value_vnd", "sum"),
        avg_quality=("daily_quality", "mean"),
        avg_score=("daily_score", "mean"),
    ).reset_index()
    out["period_label"] = out["period_start"].map(lambda z: _period_label(z, freq))
    out["period_range"] = out["period_start"].map(lambda z: _period_range_label(z, freq))
    return out.sort_values(keys, kind="stable").reset_index(drop=True)

def _current_period_start(ref_time, freq):
    ref = pd.Timestamp(ref_time or now_dt()).normalize()
    if freq == "week":
        return (ref - pd.Timedelta(days=int(ref.weekday()))).normalize()
    return ref.to_period("M").start_time


def time_goal_table(base_df, freq="week", ref_time=None):
    """Mục tiêu động = kỳ calendar gần nhất trước kỳ hiện tại có dữ liệu cùng loại công việc."""
    summary = calendar_performance_summary(base_df, freq=freq, by_task=True)
    current_start = _current_period_start(ref_time, freq)
    task_types = sorted(set(str(x) for x in base_df.get("task_type", pd.Series(dtype=str)).dropna().tolist())) if base_df is not None and len(base_df) else []
    if not task_types and not summary.empty:
        task_types = sorted(summary["task_type"].dropna().astype(str).unique().tolist())
    rows = []
    for task in task_types:
        s = summary[summary["task_type"].astype(str) == str(task)].sort_values("period_start")
        cur = s[s["period_start"] == current_start]
        prev = s[s["period_start"] < current_start].tail(1)
        cur_r = cur.iloc[0] if not cur.empty else None
        prev_r = prev.iloc[0] if not prev.empty else None
        current = float(cur_r["avg_minutes"]) if cur_r is not None and pd.notna(cur_r["avg_minutes"]) else math.nan
        target = float(prev_r["avg_minutes"]) if prev_r is not None and pd.notna(prev_r["avg_minutes"]) else math.nan
        delta = current - target if pd.notna(current) and pd.notna(target) else math.nan
        if pd.notna(delta):
            status = "Đạt" if delta <= 0 else "Chưa đạt"
        else:
            status = "Chưa đủ dữ liệu"
        rows.append({
            "task_type": task,
            "current_minutes": current,
            "target_minutes": target,
            "delta_minutes": delta,
            "samples": int(cur_r["samples"]) if cur_r is not None and pd.notna(cur_r["samples"]) else 0,
            "active_days": int(cur_r["active_days"]) if cur_r is not None and pd.notna(cur_r["active_days"]) else 0,
            "target_samples": int(prev_r["samples"]) if prev_r is not None and pd.notna(prev_r["samples"]) else 0,
            "target_active_days": int(prev_r["active_days"]) if prev_r is not None and pd.notna(prev_r["active_days"]) else 0,
            "target_period": str(prev_r["period_label"]) if prev_r is not None else "—",
            "status": status,
        })
    return pd.DataFrame(rows)


def period_heatmap_data(base_df, freq="week", periods=12):
    summary = calendar_performance_summary(base_df, freq=freq, by_task=True)
    if summary.empty:
        return summary
    out_parts = []
    for _, g in summary.groupby("task_type", dropna=False):
        g = g.sort_values("period_start").copy()
        g["target_minutes"] = g["avg_minutes"].shift(1)
        g["delta_minutes"] = g["avg_minutes"] - g["target_minutes"]
        g["delta_pct"] = (g["delta_minutes"] / g["target_minutes"].replace({0: pd.NA})) * 100.0
        g["status"] = g["delta_minutes"].map(lambda z: "Đạt" if pd.notna(z) and z <= 0 else ("Chưa đạt" if pd.notna(z) else "Chưa đủ dữ liệu"))
        out_parts.append(g)
    out = pd.concat(out_parts, ignore_index=True)
    unique_periods = sorted(out["period_start"].dropna().unique())[-int(periods):]
    return out[out["period_start"].isin(unique_periods)].copy()


def rolling_7d_targets(base_df=None, ref_time=None):
    """Tương thích báo cáo cũ: trả mục tiêu theo tuần calendar thay cho rolling 7 ngày."""
    if base_df is None:
        sql = """SELECT t.id,t.task_type,t.start_time,t.end_time,t.amount_vnd,e.quality_score,e.progress_score
                 FROM tasks t LEFT JOIN evaluations e ON e.task_id=t.id AND e.round_no=t.current_round
                 WHERE t.end_time IS NOT NULL"""
        base_df = qdf(sql)
    goals = time_goal_table(base_df, "week", ref_time)
    if goals.empty:
        return pd.DataFrame(columns=["task_type", "target_minutes", "samples"])
    return goals[["task_type", "target_minutes", "target_samples"]].rename(columns={"target_samples": "samples"})


_CHART_COLORS = ["#006B68", "#F4B41A", "#008F80", "#42A58F", "#2F6F8F", "#E4843A", "#6D62A8", "#60A56E", "#D55A7D", "#7D6D62"]


def render_kpi_cards(cards):
    html_cards = []
    for item in cards:
        if len(item) == 2:
            label, value = item; sub = ""
        else:
            label, value, sub = item
        html_cards.append(
            f'<div class="kpi-card"><div class="kpi-label">{html.escape(str(label))}</div>'
            f'<div class="kpi-value">{html.escape(str(value))}</div>'
            f'<div class="kpi-sub">{html.escape(str(sub or ""))}</div></div>'
        )
    st.markdown('<div class="kpi-grid">' + ''.join(html_cards) + '</div>', unsafe_allow_html=True)


def _chart_number_format(value_name="", y_title=""):
    text = f"{value_name} {y_title}".lower()
    if any(k in text for k in ["số tác nghiệp", "số tn", "samples", "ngày", "làm lại"]):
        return ",.0f"
    if "điểm" in text:
        return ".1f"
    if any(k in text for k in ["tỷ", "giá trị"]):
        return ",.1f"
    if "phút" in text or "thời gian" in text or "tg " in text:
        return ",.1f"
    return ",.1f"


def _plotly_config():
    return {"displayModeBar": False, "responsive": True, "scrollZoom": False}


def _altair_donut(df, category, value, title, tooltip_value_title="Giá trị"):
    """Tên hàm giữ tương thích source cũ; V2.13 render bằng Plotly, không dùng Altair."""
    import plotly.graph_objects as go
    d = df[[category, value]].dropna().copy()
    d[value] = pd.to_numeric(d[value], errors="coerce")
    d = d[d[value].notna()].copy()
    if d.empty or float(d[value].fillna(0).sum()) == 0:
        st.info(f"Chưa có dữ liệu cho {title.lower()}.")
        return
    d[category] = d[category].astype(str)
    ncat = max(1, int(d[category].nunique()))
    fmt = _chart_number_format(value, tooltip_value_title)
    if fmt == ",.0f":
        texts = [f"{float(v):,.0f}".replace(",", ".") for v in d[value]]
    else:
        texts = [f"{float(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") for v in d[value]]
    fig = go.Figure(go.Pie(
        labels=d[category].tolist(), values=d[value].tolist(), hole=.56,
        marker=dict(colors=[_CHART_COLORS[i % len(_CHART_COLORS)] for i in range(len(d))]),
        text=texts, textinfo="text", textposition="inside",
        insidetextfont=dict(size=11, color="white"),
        hovertemplate=f"%{{label}}<br>{html.escape(str(tooltip_value_title))}: %{{value}}<extra></extra>",
        sort=False,
    ))
    legend_rows = max(1, math.ceil(ncat / 3))
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=14)),
        height=max(300, 250 + legend_rows * 26),
        margin=dict(l=12, r=12, t=52, b=44 + legend_rows * 20),
        legend=dict(orientation="h", yanchor="top", y=-.10, xanchor="left", x=0, font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        uniformtext_minsize=9, uniformtext_mode="hide",
    )
    st.plotly_chart(fig, use_container_width=True, config=_plotly_config())


def _altair_bar(df, category, value, title, y_title, chronological=False):
    """Bar responsive bằng Plotly; nhãn dài tự chuyển ngang và luôn hiển thị data label."""
    import plotly.graph_objects as go
    d = df[[category, value]].dropna().copy()
    d[value] = pd.to_numeric(d[value], errors="coerce")
    d = d[d[value].notna()].copy()
    if d.empty:
        st.info(f"Chưa có dữ liệu cho {title.lower()}.")
        return
    d[category] = d[category].astype(str)
    if chronological:
        order = d[category].drop_duplicates().tolist()
        d[category] = pd.Categorical(d[category], categories=order, ordered=True)
        d = d.sort_values(category)
    ncat = max(1, int(d[category].nunique()))
    max_label_len = int(d[category].astype(str).str.len().max()) if not d.empty else 0
    horizontal = (not chronological) and (max_label_len > 13 or ncat > 7)
    fmt = _chart_number_format(value, y_title)
    def _txt(v):
        if pd.isna(v): return ""
        if fmt == ",.0f": return f"{float(v):,.0f}".replace(",", ".")
        return f"{float(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    text=[_txt(v) for v in d[value]]
    colors=[_CHART_COLORS[i % len(_CHART_COLORS)] for i in range(len(d))]
    if horizontal:
        fig = go.Figure(go.Bar(
            y=d[category].astype(str), x=d[value], orientation="h", text=text, textposition="outside",
            marker_color=colors, cliponaxis=False,
            hovertemplate="%{y}<br>" + html.escape(str(y_title)) + ": %{x}<extra></extra>",
        ))
        fig.update_yaxes(autorange="reversed", automargin=True, tickfont=dict(size=10))
        fig.update_xaxes(title=y_title, automargin=True)
        height=max(310, min(720, 50*ncat + 100))
        margins=dict(l=min(250, 70 + max_label_len*6), r=80, t=58, b=38)
    else:
        fig = go.Figure(go.Bar(
            x=d[category].astype(str), y=d[value], text=text, textposition="outside",
            marker_color=colors, cliponaxis=False,
            hovertemplate="%{x}<br>" + html.escape(str(y_title)) + ": %{y}<extra></extra>",
        ))
        fig.update_xaxes(type="category", tickangle=-25 if max_label_len > 6 else 0, automargin=True, tickfont=dict(size=10), categoryorder="array", categoryarray=d[category].astype(str).tolist())
        fig.update_yaxes(title=y_title, automargin=True, rangemode="tozero")
        height=max(320, 300 + (35 if max_label_len > 10 else 0))
        margins=dict(l=58, r=34, t=62, b=min(150, 58 + max_label_len*3))
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=14)),
        height=height, margin=margins, showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11, color="#334155"), bargap=.24,
    )
    st.plotly_chart(fig, use_container_width=True, config=_plotly_config())


def _altair_grouped_bar(df, period_col, staff_col, value_col, title, y_title, chronological=True):
    """Grouped bar bằng Plotly; tự tăng chiều cao/legend theo số cán bộ và kỳ."""
    import plotly.graph_objects as go
    d = df[[period_col, staff_col, value_col]].dropna(subset=[period_col, staff_col]).copy()
    d[value_col] = pd.to_numeric(d[value_col], errors="coerce")
    d = d[d[value_col].notna()].copy()
    if d.empty:
        st.info(f"Chưa có dữ liệu cho {title.lower()}.")
        return
    d[period_col] = d[period_col].astype(str); d[staff_col] = d[staff_col].astype(str)
    periods = d[period_col].drop_duplicates().tolist()
    staffs = d[staff_col].drop_duplicates().tolist()
    fig = go.Figure()
    fmt = _chart_number_format(value_col, y_title)
    def _txt(v):
        if pd.isna(v): return ""
        if fmt == ",.0f": return f"{float(v):,.0f}".replace(",", ".")
        return f"{float(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
    for i, staff in enumerate(staffs):
        part=d[d[staff_col].eq(staff)].set_index(period_col).reindex(periods)
        vals=pd.to_numeric(part[value_col],errors="coerce").fillna(0)
        fig.add_trace(go.Bar(
            name=staff, x=periods, y=vals, text=[_txt(v) for v in vals], textposition="outside",
            marker_color=_CHART_COLORS[i % len(_CHART_COLORS)], cliponaxis=False,
            hovertemplate="Kỳ: %{x}<br>Cán bộ: " + html.escape(staff) + "<br>" + html.escape(str(y_title)) + ": %{y}<extra></extra>",
        ))
    nstaff=max(1,len(staffs)); nperiod=max(1,len(periods)); legend_rows=max(1,math.ceil(nstaff/3))
    fig.update_layout(
        barmode="group", title=dict(text=title,x=0,xanchor="left",font=dict(size=14)),
        height=max(360, 315 + legend_rows*25 + (35 if nperiod>8 else 0)),
        margin=dict(l=58,r=28,t=62,b=75+legend_rows*24),
        legend=dict(orientation="h",yanchor="top",y=-.18,xanchor="left",x=0,font=dict(size=10)),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=11,color="#334155"), bargap=.18, bargroupgap=.06,
    )
    fig.update_xaxes(type="category",tickangle=-25,automargin=True,categoryorder="array",categoryarray=periods)
    fig.update_yaxes(title=y_title,automargin=True,rangemode="tozero")
    st.plotly_chart(fig,use_container_width=True,config=_plotly_config())


def _staff_period_summary(base_df, freq, staff_col, role_label=None, periods=16):
    """Tổng hợp theo tuần/tháng cho từng cán bộ theo chuẩn calendar/ngày phát sinh."""
    x = enrich_tasks(base_df.copy()) if base_df is not None and not base_df.empty else pd.DataFrame()
    if x.empty or staff_col not in x.columns:
        return pd.DataFrame()
    # So sánh hiệu suất thời gian chỉ dùng món đã hoàn thành; số lượng/giá trị trong kỳ cũng bám mốc hoàn thành.
    x = x[x["end_dt"].notna()].copy()
    if x.empty:
        return pd.DataFrame()
    x["period_start"] = _period_start_series(x["end_dt"], freq)
    x["period_label"] = x["period_start"].map(lambda z: _period_label(z, freq))
    x["activity_date"] = x["end_dt"].dt.normalize()
    # B1: bình quân từng ngày thực tế phát sinh của từng cán bộ.
    daily = x.groupby(["period_start","period_label",staff_col,"activity_date"], dropna=False).agg(
        daily_samples=("id","count"),
        daily_value_vnd=("amount_vnd","sum"),
        daily_score=("avg_score","mean"),
        daily_minutes=("duration_minutes","mean"),
        daily_accept_wait=("assignment_to_accept_minutes","mean"),
        daily_rework=("rework_count","sum"),
    ).reset_index()
    # B2: bình quân các ngày phát sinh trong tuần/tháng.
    g = daily.groupby(["period_start", "period_label", staff_col], dropna=False).agg(
        so_tac_nghiep=("daily_samples", "sum"),
        gia_tri_vnd=("daily_value_vnd", "sum"),
        diem_tb=("daily_score", "mean"),
        tg_tb_phut=("daily_minutes", "mean"),
        tg_tiep_nhan_tb=("daily_accept_wait", "mean"),
        lam_lai=("daily_rework", "sum"),
        active_days=("activity_date","nunique"),
    ).reset_index()
    g["gia_tri_ty"] = g["gia_tri_vnd"] / 1_000_000_000.0
    unique_periods = sorted(g["period_start"].dropna().unique())[-int(periods):]
    g = g[g["period_start"].isin(unique_periods)].copy()
    # Cross join roster x kỳ để cán bộ chưa phát sinh vẫn xuất hiện với Số TN/Giá trị = 0.
    role = role_label or ("Cán bộ hỗ trợ" if staff_col == "support_name" else "Cán bộ QLKH")
    roster = all_users(role, active_only=True)
    if roster is not None and not roster.empty and unique_periods:
        period_df = pd.DataFrame({"period_start": unique_periods})
        period_df["period_label"] = period_df["period_start"].map(lambda z: _period_label(z, freq))
        roster_df = roster[["full_name"]].rename(columns={"full_name": staff_col}).copy()
        period_df["_k"] = 1; roster_df["_k"] = 1
        grid = period_df.merge(roster_df, on="_k").drop(columns="_k")
        g = grid.merge(g, on=["period_start","period_label",staff_col], how="left")
        for c in ["so_tac_nghiep","gia_tri_vnd","gia_tri_ty","lam_lai","active_days"]:
            g[c] = pd.to_numeric(g[c], errors="coerce").fillna(0)
    return g.sort_values(["period_start", staff_col], kind="stable").reset_index(drop=True)


def _render_staff_period_comparison(base_df, freq, staff_col, staff_title):
    period_word = "tuần" if freq == "week" else "tháng"
    g = _staff_period_summary(base_df, freq, staff_col, role_label=("Cán bộ hỗ trợ" if staff_col=="support_name" else "Cán bộ QLKH"), periods=16 if freq == "week" else 12)
    if g.empty:
        st.info(f"Chưa có dữ liệu {period_word} theo {staff_title}."); return
    display = g.rename(columns={
        "period_label": "Tuần" if freq == "week" else "Tháng",
        staff_col: staff_title,
        "so_tac_nghiep": "Số TN",
        "gia_tri_ty": "Giá trị (tỷ đồng)",
        "diem_tb": "Điểm TB",
        "tg_tiep_nhan_tb": "TG giao→tiếp nhận TB (phút)",
        "tg_tb_phut": "TG xử lý TB (phút)",
        "lam_lai": "Làm lại",
        "active_days": "Ngày phát sinh",
    }).copy()
    pcol = "Tuần" if freq == "week" else "Tháng"
    display["Giá trị (tỷ đồng)"] = display["Giá trị (tỷ đồng)"].map(lambda x: fmt_billion(x, False))
    display["Điểm TB"] = display["Điểm TB"].map(fmt_score)
    display["TG giao→tiếp nhận TB (phút)"] = display["TG giao→tiếp nhận TB (phút)"].map(lambda x: f"{float(x):,.1f}".replace(",", ".") if pd.notna(x) else "—")
    display["TG xử lý TB (phút)"] = display["TG xử lý TB (phút)"].map(lambda x: f"{float(x):,.1f}".replace(",", ".") if pd.notna(x) else "—")
    st.dataframe(display[[pcol, staff_title, "Số TN", "Ngày phát sinh", "Giá trị (tỷ đồng)", "Điểm TB", "TG giao→tiếp nhận TB (phút)", "TG xử lý TB (phút)", "Làm lại"]], use_container_width=True, hide_index=True)
    a,b = st.columns(2)
    with a: _altair_grouped_bar(g, "period_label", staff_col, "so_tac_nghiep", f"Số tác nghiệp theo {period_word} · {staff_title}", "Số tác nghiệp")
    with b: _altair_grouped_bar(g, "period_label", staff_col, "gia_tri_ty", f"Giá trị theo {period_word} · {staff_title}", "Tỷ đồng")
    a,b = st.columns(2)
    with a: _altair_grouped_bar(g, "period_label", staff_col, "diem_tb", f"Điểm bình quân theo {period_word} · {staff_title}", "Điểm")
    with b: _altair_grouped_bar(g, "period_label", staff_col, "tg_tb_phut", f"TG xử lý bình quân theo {period_word} · {staff_title}", "Phút")
    _altair_grouped_bar(g, "period_label", staff_col, "tg_tiep_nhan_tb", f"TG giao→tiếp nhận theo {period_word} · {staff_title}", "Phút")



def _staff_aggregate_with_roster(base_df, staff_col, role):
    roster = all_users(role, active_only=True)
    roster_names = roster[["full_name"]].rename(columns={"full_name": staff_col}) if roster is not None and not roster.empty else pd.DataFrame(columns=[staff_col])
    if base_df is None or base_df.empty or staff_col not in base_df.columns:
        g = pd.DataFrame(columns=[staff_col,"so_tac_nghiep","gia_tri_vnd","diem_tb","tg_tb_phut","tg_tiep_nhan_tb","lam_lai"])
    else:
        g = base_df.groupby(staff_col, dropna=False).agg(
            so_tac_nghiep=("id", "count"), gia_tri_vnd=("amount_vnd", "sum"),
            diem_tb=("avg_score", "mean"), tg_tb_phut=("duration_minutes", "mean"), tg_tiep_nhan_tb=("assignment_to_accept_minutes", "mean"), lam_lai=("rework_count", "sum")
        ).reset_index()
    if not roster_names.empty:
        g = roster_names.merge(g, on=staff_col, how="left")
    for c in ["so_tac_nghiep","gia_tri_vnd","lam_lai"]:
        if c in g.columns: g[c] = pd.to_numeric(g[c], errors="coerce").fillna(0)
    g["gia_tri_ty"] = pd.to_numeric(g.get("gia_tri_vnd", 0), errors="coerce").fillna(0) / 1_000_000_000.0
    return g.sort_values(["so_tac_nghiep",staff_col], ascending=[False,True], kind="stable").reset_index(drop=True)

def _altair_heatmap(df, freq="week", title="Heatmap hiệu suất"):
    """Heatmap bằng Plotly để tránh lỗi Altair/typing_extensions trên Windows."""
    import plotly.graph_objects as go
    if df is None or df.empty:
        st.info("Chưa đủ dữ liệu để tạo heatmap."); return
    d=df.copy(); d=d[d["delta_pct"].notna()].copy()
    if d.empty:
        st.info("Cần tối thiểu 2 kỳ có dữ liệu cho cùng loại công việc để tạo heatmap."); return
    d["period_label"]=d["period_label"].astype(str); d["task_type"]=d["task_type"].astype(str)
    periods=d.sort_values("period_start")["period_label"].drop_duplicates().tolist()
    tasks=d["task_type"].drop_duplicates().tolist()
    pivot=d.pivot_table(index="task_type",columns="period_label",values="delta_pct",aggfunc="mean").reindex(index=tasks,columns=periods)
    text=pivot.copy().astype(object)
    for r in pivot.index:
        for c in pivot.columns:
            v=pivot.loc[r,c]
            text.loc[r,c]="" if pd.isna(v) else f"{float(v):+.0f}%"
    # customdata: avg, target, samples, active days, range, status
    custom=[]
    for task in tasks:
        row=[]
        for per in periods:
            hit=d[(d.task_type==task)&(d.period_label==per)]
            if hit.empty: row.append([None,None,None,None,"",""])
            else:
                h=hit.iloc[0]
                row.append([h.get("avg_minutes"),h.get("target_minutes"),h.get("samples"),h.get("active_days"),h.get("period_range",""),h.get("status","")])
        custom.append(row)
    fig=go.Figure(go.Heatmap(
        z=pivot.values,x=periods,y=tasks,text=text.values,texttemplate="%{text}",
        colorscale=[[0,"#0B7F75"],[.5,"#F5B21B"],[1,"#D64545"]],zmin=-30,zmax=30,zmid=0,
        colorbar=dict(title="Chênh lệch %",orientation="h",y=-.28,len=.65,thickness=12),
        customdata=custom,
        hovertemplate="Công việc: %{y}<br>Kỳ: %{x}<br>Khoảng ngày: %{customdata[4]}<br>TG TB: %{customdata[0]:.1f} phút<br>Mục tiêu kỳ trước: %{customdata[1]:.1f} phút<br>Chênh lệch: %{z:+.1f}%<br>Số mẫu: %{customdata[2]}<br>Ngày phát sinh: %{customdata[3]}<br>Kết quả: %{customdata[5]}<extra></extra>",
    ))
    n_tasks=max(1,len(tasks)); n_periods=max(1,len(periods))
    fig.update_layout(
        title=dict(text=title,x=0,xanchor="left",font=dict(size=14)),
        height=max(330,min(820,55*n_tasks+180)),
        margin=dict(l=min(260,90+max([len(x) for x in tasks] or [0])*5),r=28,t=62,b=120),
        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(size=11,color="#334155"),
    )
    fig.update_xaxes(title="Tuần calendar" if freq=="week" else "Tháng calendar",tickangle=-25,automargin=True)
    fig.update_yaxes(title=None,automargin=True)
    st.plotly_chart(fig,use_container_width=True,config=_plotly_config())
    st.caption("Heatmap: **xanh = nhanh hơn/đạt**, **vàng = gần mức kỳ trước**, **đỏ = chậm hơn/chưa đạt**. Số trong ô là % chênh lệch so với kỳ calendar liền trước có dữ liệu.")


def _show_goal_table(base_df, freq):
    goals = time_goal_table(base_df, freq=freq)
    label = "tuần" if freq == "week" else "tháng"
    if goals.empty:
        st.info(f"Chưa có dữ liệu để xây dựng mục tiêu {label}."); return
    show = goals.rename(columns={
        "task_type": "Công việc", "current_minutes": "TG TB hiện tại (phút)", "target_minutes": f"Mục tiêu {label} (phút)",
        "delta_minutes": "Chênh lệch (phút)", "samples": "Số mẫu", "active_days": "Ngày phát sinh",
        "target_period": "Kỳ chuẩn", "status": "Đạt-Chưa đạt",
    })[["Công việc", "TG TB hiện tại (phút)", f"Mục tiêu {label} (phút)", "Chênh lệch (phút)", "Số mẫu", "Ngày phát sinh", "Kỳ chuẩn", "Đạt-Chưa đạt"]].copy()
    for col in ["TG TB hiện tại (phút)", f"Mục tiêu {label} (phút)", "Chênh lệch (phút)"]:
        show[col] = show[col].map(lambda x: f"{float(x):,.1f}".replace(",", ".") if pd.notna(x) else "—")
    st.dataframe(show, use_container_width=True, hide_index=True)



def _is_dashboard_value_task(task_type):
    """Dashboard chỉ cộng giá trị cho Giải ngân, Bảo lãnh và L/C (LC)."""
    key = re.sub(r"[^a-z0-9]", "", _strip_accents(str(task_type or "")).lower())
    return key in {"giaingan", "baolanh", "lc"}


def _dashboard_stat_frame(df):
    if df is None:
        return pd.DataFrame()
    x = df.copy()
    if x.empty:
        return x
    if "amount_vnd" not in x.columns:
        x["amount_vnd"] = 0.0
    mask = x.get("task_type", pd.Series(index=x.index, dtype=str)).map(_is_dashboard_value_task)
    x["amount_vnd"] = pd.to_numeric(x["amount_vnd"], errors="coerce").fillna(0).where(mask, 0.0)
    return x

def workflow_event_stats(task_df):
    """Đếm các sự kiện điều phối theo tập hồ sơ Dashboard, giữ cả số hồ sơ và số lần phát sinh."""
    result = {
        "RETURN_TO_QLKH": {"tasks":0,"events":0},
        "QLKH_REASSIGN": {"tasks":0,"events":0},
        "QLKH_CANCEL": {"tasks":0,"events":0},
    }
    if task_df is None or task_df.empty or "id" not in task_df.columns:
        return result
    ids = sorted({int(x) for x in pd.to_numeric(task_df["id"], errors="coerce").dropna().tolist()})
    if not ids:
        return result
    marks=",".join(["?"]*len(ids))
    acts=qdf(f"""SELECT action,COUNT(*) events,COUNT(DISTINCT task_id) tasks
                 FROM task_actions WHERE task_id IN ({marks})
                   AND action IN ('RETURN_TO_QLKH','QLKH_REASSIGN','QLKH_CANCEL')
                 GROUP BY action""",ids)
    for _,r in acts.iterrows():
        a=str(r.action)
        if a in result:
            result[a]={"tasks":int(r.tasks or 0),"events":int(r.events or 0)}
    return result



def _period_efficiency_snapshot(base_df, freq="week", ref_time=None):
    """So sánh riêng từng chỉ tiêu của kỳ hiện tại với kỳ calendar gần nhất có dữ liệu.

    Không còn chỉ số 60/25/15. Ba chỉ tiêu nhận xét là:
    TG xử lý TB (thấp hơn tốt hơn), Chất lượng TB và Điểm TB (cao hơn tốt hơn).
    """
    empty = {
        "period": "—", "target_period": "—", "samples": 0, "active_days": 0,
        "avg_minutes": math.nan, "target_minutes": math.nan, "delta_minutes": math.nan, "delta_pct": math.nan,
        "avg_quality": math.nan, "target_quality": math.nan, "quality_delta": math.nan, "quality_delta_pct": math.nan,
        "avg_score": math.nan, "target_score": math.nan, "score_delta": math.nan, "score_delta_pct": math.nan,
    }
    if base_df is None or base_df.empty:
        return empty.copy()
    x = _dashboard_stat_frame(base_df.copy())
    summary = calendar_performance_summary(x, freq=freq, by_task=False).sort_values("period_start")
    if summary.empty:
        return empty.copy()
    current_start = _current_period_start(ref_time, freq)
    cur = summary[summary["period_start"].eq(current_start)]
    prev = summary[summary["period_start"].lt(current_start)].tail(1)
    out = empty.copy(); out["period"] = _period_label(current_start, freq)
    if cur.empty:
        return out
    c=cur.iloc[0]
    out.update({
        "samples": int(c.get("samples",0) or 0),
        "active_days": int(c.get("active_days",0) or 0),
        "avg_minutes": float(c["avg_minutes"]) if pd.notna(c.get("avg_minutes")) else math.nan,
        "avg_quality": float(c["avg_quality"]) if pd.notna(c.get("avg_quality")) else math.nan,
        "avg_score": float(c["avg_score"]) if pd.notna(c.get("avg_score")) else math.nan,
    })
    if prev.empty:
        return out
    p=prev.iloc[0]
    out["target_period"] = str(p.get("period_label") or "—")
    for cur_key, tgt_key, col, d_key, pct_key in [
        ("avg_minutes","target_minutes","avg_minutes","delta_minutes","delta_pct"),
        ("avg_quality","target_quality","avg_quality","quality_delta","quality_delta_pct"),
        ("avg_score","target_score","avg_score","score_delta","score_delta_pct"),
    ]:
        target=float(p[col]) if pd.notna(p.get(col)) else math.nan
        out[tgt_key]=target
        current=out[cur_key]
        if pd.notna(current) and pd.notna(target):
            out[d_key]=current-target
            if abs(target)>1e-12:
                out[pct_key]=(current-target)/abs(target)*100.0
    return out

def _metric_trend_payload(current, previous, *, lower_is_better=False, unit=""):
    """Trả thông tin hiển thị cho một chỉ tiêu, gồm số tuyệt đối và % thay đổi."""
    if pd.isna(current):
        return {"state":"neutral","headline":"—","detail":"Chưa có dữ liệu trong kỳ hiện tại."}
    current=float(current)
    headline=f"{current:.1f}{unit}"
    if pd.isna(previous):
        return {"state":"neutral","headline":headline,"detail":"Chưa có kỳ trước để so sánh."}
    previous=float(previous); diff=current-previous
    pct=(diff/abs(previous)*100.0) if abs(previous)>1e-12 else math.nan
    improved = diff < -1e-9 if lower_is_better else diff > 1e-9
    worsened = diff > 1e-9 if lower_is_better else diff < -1e-9
    state="good" if improved else ("bad" if worsened else "neutral")
    if abs(diff)<=1e-9:
        direction="không đổi"
    elif lower_is_better:
        direction="cải thiện" if improved else "chậm hơn"
    else:
        direction="tăng" if improved else "giảm"
    diff_abs=abs(diff)
    pct_text=f"{abs(pct):.1f}%" if pd.notna(pct) else "không xác định %"
    detail=f"Kỳ trước {previous:.1f}{unit} · {direction} {diff_abs:.1f}{unit} ({pct_text})."
    return {"state":state,"headline":headline,"detail":detail,"diff":diff,"pct":pct}


def _efficiency_text(snap, label):
    """Nhận xét thuần theo từng chỉ tiêu; không tạo điểm/chỉ số hiệu suất tổng hợp."""
    if not snap or snap.get("samples",0)<=0:
        return f"{label}: chưa có hồ sơ hoàn thành trong kỳ hiện tại."
    t=_metric_trend_payload(snap.get("avg_minutes"),snap.get("target_minutes"),lower_is_better=True,unit=" phút")
    q=_metric_trend_payload(snap.get("avg_quality"),snap.get("target_quality"),lower_is_better=False,unit=" điểm")
    a=_metric_trend_payload(snap.get("avg_score"),snap.get("target_score"),lower_is_better=False,unit=" điểm")
    return f"{label}: Thời gian {t['detail']} Chất lượng {q['detail']} Điểm TB {a['detail']}"

def _staff_efficiency_table(room_df, freq, role, id_col):
    roster = all_users(role, active_only=True)
    if roster is None or roster.empty:
        return pd.DataFrame()
    rows=[]
    for _,person in roster.iterrows():
        personal=room_df[room_df[id_col].eq(int(person.id))].copy() if id_col in room_df.columns else pd.DataFrame()
        snap=_period_efficiency_snapshot(personal,freq=freq)
        rows.append({
            "Cán bộ":person.full_name,"Vai trò":role,"Kỳ":snap.get("period","—"),"Số mẫu":snap.get("samples",0),"Ngày phát sinh":snap.get("active_days",0),
            "TG hiện tại":snap.get("avg_minutes",math.nan),"TG kỳ trước":snap.get("target_minutes",math.nan),"Δ TG %":snap.get("delta_pct",math.nan),
            "Chất lượng hiện tại":snap.get("avg_quality",math.nan),"Chất lượng kỳ trước":snap.get("target_quality",math.nan),"Δ Chất lượng %":snap.get("quality_delta_pct",math.nan),
            "Điểm TB hiện tại":snap.get("avg_score",math.nan),"Điểm TB kỳ trước":snap.get("target_score",math.nan),"Δ Điểm %":snap.get("score_delta_pct",math.nan),
        })
    return pd.DataFrame(rows)

def _render_period_trends(snap, label):
    """Hiển thị ba tiêu chí độc lập; xanh = cải thiện, đỏ = giảm sút."""
    t=_metric_trend_payload(snap.get("avg_minutes"),snap.get("target_minutes"),lower_is_better=True,unit=" phút")
    q=_metric_trend_payload(snap.get("avg_quality"),snap.get("target_quality"),lower_is_better=False,unit=" điểm")
    a=_metric_trend_payload(snap.get("avg_score"),snap.get("target_score"),lower_is_better=False,unit=" điểm")
    cards=[]
    for title,payload in [("Thời gian xử lý",t),("Chất lượng",q),("Điểm trung bình",a)]:
        css="trend-good" if payload["state"]=="good" else ("trend-bad" if payload["state"]=="bad" else "trend-neutral")
        cards.append(f'<div class="perf-trend-card {css}"><div class="perf-trend-label">{html.escape(title)}</div><div class="perf-trend-value">{html.escape(payload["headline"])}</div><div class="perf-trend-detail">{html.escape(payload["detail"])}</div></div>')
    period=html.escape(str(snap.get("period","—"))); target=html.escape(str(snap.get("target_period","—")))
    sample=int(snap.get("samples",0) or 0); days=int(snap.get("active_days",0) or 0)
    st.html(f'<div class="perf-period"><div class="perf-period-title">{html.escape(label)} · kỳ {period} · so với {target} · {sample} hồ sơ / {days} ngày phát sinh</div><div class="perf-trend-grid">{"".join(cards)}</div></div>')


def _render_efficiency_assessment(u, room_df):
    """Báo cáo đánh giá theo từng chỉ tiêu, không dùng chỉ số tổng hợp."""
    support_view=u["role"]=="Cán bộ hỗ trợ"; qlkh_view=u["role"]=="Cán bộ QLKH"; leader_view=not(support_view or qlkh_view)
    if support_view:
        scope=room_df[room_df["support_user_id"].eq(int(u["id"]))].copy(); scope_title=f"Cá nhân · {u.get('full_name','')}"
    elif qlkh_view:
        scope=room_df[room_df["qlkh_user_id"].eq(int(u["id"]))].copy(); scope_title=f"Cá nhân · {u.get('full_name','')}"
    else:
        scope=room_df.copy(); scope_title="Toàn Phòng KHDN"
    week=_period_efficiency_snapshot(scope,"week"); month=_period_efficiency_snapshot(scope,"month")
    st.markdown("## 📈 Báo cáo đánh giá hiệu quả công việc")
    st.html(f'<div class="section-note"><b>{html.escape(scope_title)}</b> · đánh giá riêng từng tiêu chí. Thời gian giảm là cải thiện; Chất lượng và Điểm số tăng là cải thiện. <span style="color:#08785E;font-weight:900">Xanh = tốt hơn</span>; <span style="color:#C62828;font-weight:900">đỏ = giảm sút</span>.</div>')
    _render_period_trends(week,"Theo tuần calendar")
    _render_period_trends(month,"Theo tháng calendar")
    if leader_view:
        st.markdown("### Đánh giá theo cán bộ")
        period_choice=pill_nav("efficiency_staff_period",[("week","📅 Tuần"),("month","🗓️ Tháng")],default="week",prefix="subnav_efficiency_staff")
        support_tbl=_staff_efficiency_table(room_df,period_choice,"Cán bộ hỗ trợ","support_user_id")
        qlkh_tbl=_staff_efficiency_table(room_df,period_choice,"Cán bộ QLKH","qlkh_user_id")
        staff=pd.concat([support_tbl,qlkh_tbl],ignore_index=True) if not support_tbl.empty or not qlkh_tbl.empty else pd.DataFrame()
        if staff.empty:
            st.info("Chưa có dữ liệu để đánh giá theo cán bộ.")
        else:
            show=staff.copy()
            for c in ["TG hiện tại","TG kỳ trước","Δ TG %","Chất lượng hiện tại","Chất lượng kỳ trước","Δ Chất lượng %","Điểm TB hiện tại","Điểm TB kỳ trước","Δ Điểm %"]:
                show[c]=pd.to_numeric(show[c],errors="coerce")
            def _row_color(col):
                vals=[]
                for v in show[col]:
                    if pd.isna(v): vals.append("")
                    else:
                        good=(v<0) if col=="Δ TG %" else (v>0)
                        bad=(v>0) if col=="Δ TG %" else (v<0)
                        vals.append("color:#08785E;font-weight:800" if good else ("color:#C62828;font-weight:800" if bad else "color:#64748b"))
                return vals
            sty=show.style.format({c:"{:.1f}" for c in ["TG hiện tại","TG kỳ trước","Δ TG %","Chất lượng hiện tại","Chất lượng kỳ trước","Δ Chất lượng %","Điểm TB hiện tại","Điểm TB kỳ trước","Δ Điểm %"]},na_rep="—")
            for c in ["Δ TG %","Δ Chất lượng %","Δ Điểm %"]:
                sty=sty.apply(lambda _s,col=c:_row_color(col),subset=[c])
            st.dataframe(sty,use_container_width=True,hide_index=True,height=_task_list_height(len(show),520))

def dashboard_page(u):
    support_view = u["role"] == "Cán bộ hỗ trợ"
    qlkh_view = u["role"] == "Cán bộ QLKH"
    operational_view = support_view or qlkh_view
    page_title("Dashboard & Báo cáo", "Phân tích cá nhân theo vai trò và benchmark toàn Phòng KHDN theo cán bộ, loại công việc và kỳ calendar.")

    # Lấy toàn phòng làm nguồn benchmark. Sau đó tách riêng scope cá nhân cho các phân tích nghiệp vụ.
    df = _room_tasks_frame()
    if df.empty:
        st.info("Chưa có dữ liệu."); return

    # Báo cáo hiệu quả ngắn hạn + chuẩn dài hạn 5 năm.
    _render_efficiency_assessment(u, df)
    _render_five_year_benchmark(u, df)

    if operational_view:
        who = "Cán bộ hỗ trợ" if support_view else "Cán bộ QLKH"
        st.markdown(f'<div class="section-note"><b>Phân tích cá nhân:</b> Theo loại công việc, Tuần, Tháng và Dữ liệu chi tiết chỉ dùng hồ sơ của {html.escape(who)} đang đăng nhập. Các khối benchmark cán bộ vẫn dùng dữ liệu toàn phòng để so sánh.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-note"><b>Góc nhìn toàn phòng:</b> Dashboard tổng hợp toàn bộ cán bộ theo cùng một chuẩn dữ liệu.</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-note"><b>Quy ước giá trị Dashboard:</b> chỉ cộng giá trị của <b>Giải ngân, Bảo lãnh và L/C (LC)</b>; các nghiệp vụ khác được tính <b>0 đồng</b> trong KPI/biểu đồ thống kê giá trị.</div>', unsafe_allow_html=True)

    with st.expander("Bộ lọc dữ liệu", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        sup_label = "CB hỗ trợ (benchmark)" if support_view else "CB hỗ trợ"
        ql_label = "CB QLKH (benchmark)" if qlkh_view else "CB QLKH"
        sup = c1.multiselect(sup_label, sorted(df.support_name.dropna().unique()))
        ql = c2.multiselect(ql_label, sorted(df.qlkh_name.dropna().unique()))
        typ = c3.multiselect("Công việc", sorted(df.task_type.dropna().unique()))
        status = c4.multiselect("Trạng thái", sorted(df.status.unique()), format_func=lambda x: STATUS_LABEL.get(x, x))
        dmin, dmax = df.start_dt.min().date(), df.start_dt.max().date()
        c5, c6 = st.columns(2)
        dates = c5.date_input("Khoảng thời gian", value=(dmin, dmax))
        score_range = c6.slider("Điểm TB", 0.0, 10.0, (0.0, 10.0), 0.5)

    def _common_filter(base, apply_support=True, apply_qlkh=True):
        x = base.copy()
        if apply_support and sup: x = x[x.support_name.isin(sup)]
        if apply_qlkh and ql: x = x[x.qlkh_name.isin(ql)]
        if typ: x = x[x.task_type.isin(typ)]
        scope_x = x.copy()
        if status: x = x[x.status.isin(status)]
        if isinstance(dates, tuple) and len(dates) == 2:
            ds = x.start_dt.dt.date; x = x[(ds >= dates[0]) & (ds <= dates[1])]
        x = x[x.avg_score.isna() | x.avg_score.between(score_range[0], score_range[1])]
        return scope_x, x.sort_values(["start_dt", "cif"], ascending=[False, True], kind="stable")

    # Benchmark toàn phòng chịu bộ lọc đầy đủ.
    room_scope, room_f = _common_filter(df, True, True)

    # Dữ liệu cá nhân: không để bộ lọc cùng vai trò vô tình chuyển sang dữ liệu cán bộ khác.
    if support_view:
        personal_base = df[df["support_user_id"] == int(u["id"])].copy()
        personal_scope, personal_f = _common_filter(personal_base, False, True)
    elif qlkh_view:
        personal_base = df[df["qlkh_user_id"] == int(u["id"])].copy()
        personal_scope, personal_f = _common_filter(personal_base, True, False)
    else:
        personal_scope, personal_f = room_scope, room_f

    analysis_scope = personal_scope if operational_view else room_scope
    analysis_f = personal_f if operational_view else room_f
    # V2.13: giá trị thống kê Dashboard chỉ tính Giải ngân/Bảo lãnh/L/C; nghiệp vụ khác = 0.
    analysis_scope_stats = _dashboard_stat_frame(analysis_scope)
    analysis_f_stats = _dashboard_stat_frame(analysis_f)
    room_f_stats = _dashboard_stat_frame(room_f)
    if analysis_f.empty:
        st.warning("Không có dữ liệu cá nhân/toàn phòng phù hợp theo bộ lọc hiện tại.")
    else:
        render_kpi_cards([
            ("Số tác nghiệp", money(len(analysis_f)), "Cá nhân" if operational_view else "Theo bộ lọc hiện tại"),
            ("Tổng giá trị", fmt_billion(billion_value(analysis_f_stats.amount_vnd.sum())), "Quy đổi VND"),
            ("Điểm TB", fmt_score(analysis_f.avg_score.mean()) if analysis_f.avg_score.notna().any() else "—", "Thang điểm 10"),
            ("TG giao→tiếp nhận TB", f"{float(analysis_f.assignment_to_accept_minutes.dropna().mean()):,.1f} phút".replace(",",".") if "assignment_to_accept_minutes" in analysis_f.columns and analysis_f.assignment_to_accept_minutes.notna().any() else "—", "QLKH khởi tạo → CBHT tiếp nhận lần đầu"),
            ("TG xử lý TB", f"{float(analysis_f.duration_minutes.dropna().mean()):,.1f} phút".replace(",",".") if analysis_f.duration_minutes.notna().any() else "—", "Từ mốc bắt đầu đầu tiên đến hoàn thành"),
            ("Tỷ lệ làm lại", f"{(analysis_f.rework_count.gt(0).mean()*100):.1f}%", "Số hồ sơ có ≥1 lần làm lại"),
        ])
        ev = workflow_event_stats(analysis_f)
        st.markdown("#### Theo dõi điều phối / trả lại / hủy hồ sơ")
        render_kpi_cards([
            ("CBHT trả lại QLKH", money(ev["RETURN_TO_QLKH"]["tasks"]), f"{money(ev['RETURN_TO_QLKH']['events'])} lần phát sinh"),
            ("QLKH đổi CBHT", money(ev["QLKH_REASSIGN"]["tasks"]), f"{money(ev['QLKH_REASSIGN']['events'])} lần thay đổi"),
            ("QLKH xóa/hủy hồ sơ", money(ev["QLKH_CANCEL"]["tasks"]), f"{money(ev['QLKH_CANCEL']['events'])} lần hủy; bản ghi vẫn giữ audit"),
        ])

    st.subheader("Mục tiêu thời gian xử lý")
    st.markdown('<div class="section-note"><b>Công thức calendar:</b> trong từng tuần (Thứ Hai–Chủ Nhật) hoặc tháng, app tính TG xử lý bình quân của từng <b>ngày thực tế có phát sinh món hoàn thành</b>, rồi lấy bình quân các ngày đó. Mục tiêu là mức của kỳ calendar gần nhất trước kỳ hiện tại có dữ liệu; <b>thời gian thấp hơn là tốt hơn</b>.</div>', unsafe_allow_html=True)
    goal_view = pill_nav("dashboard_goal_view", [("week","📅 Mục tiêu tuần calendar"),("month","🗓️ Mục tiêu tháng calendar")], default="week", prefix="subnav_dashboard_goal")
    if goal_view == "week":
        _show_goal_table(analysis_scope_stats, "week")
        _altair_heatmap(period_heatmap_data(analysis_scope_stats, "week", 12), "week", "Heatmap hiệu suất 12 tuần gần nhất")
    else:
        _show_goal_table(analysis_scope_stats, "month")
        _altair_heatmap(period_heatmap_data(analysis_scope_stats, "month", 8), "month", "Heatmap hiệu suất 8 tháng gần nhất")

    # Benchmark CB hỗ trợ luôn dùng dữ liệu toàn phòng.
    st.subheader("Phân tích theo Cán bộ hỗ trợ")
    g = _staff_aggregate_with_roster(room_f_stats, "support_name", "Cán bộ hỗ trợ")
    gshow = g.rename(columns={"support_name":"CB hỗ trợ","so_tac_nghiep":"Số TN","gia_tri_ty":"Giá trị (tỷ đồng)","diem_tb":"Điểm TB","tg_tb_phut":"TG xử lý TB (phút)","tg_tiep_nhan_tb":"TG giao→tiếp nhận TB (phút)","lam_lai":"Làm lại"})[["CB hỗ trợ","Số TN","Giá trị (tỷ đồng)","Điểm TB","TG giao→tiếp nhận TB (phút)","TG xử lý TB (phút)","Làm lại"]].copy()
    gshow["Giá trị (tỷ đồng)"] = gshow["Giá trị (tỷ đồng)"].map(lambda x: fmt_billion(x, False)); gshow["TG giao→tiếp nhận TB (phút)"] = gshow["TG giao→tiếp nhận TB (phút)"].map(lambda x: f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); gshow["TG xử lý TB (phút)"] = gshow["TG xử lý TB (phút)"].map(lambda x: f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); gshow["Điểm TB"] = gshow["Điểm TB"].map(fmt_score)
    if support_view:
        _my_name = str(u.get("full_name") or "")
        def _mark_me(row):
            return ["background-color:#E8F7F2;color:#064E47;font-weight:850;border-top:1px solid #0B7F75;border-bottom:1px solid #0B7F75" if str(row.get("CB hỗ trợ")) == _my_name else "" for _ in row.index]
        st.dataframe(gshow.style.apply(_mark_me, axis=1), use_container_width=True, hide_index=True)
        st.caption("Dòng màu xanh là tài khoản Cán bộ hỗ trợ đang đăng nhập.")
    else:
        st.dataframe(gshow, use_container_width=True, hide_index=True)
    a,b = st.columns(2)
    with a: _altair_donut(g,"support_name","so_tac_nghiep","Số tác nghiệp theo CB hỗ trợ","Số tác nghiệp")
    with b: _altair_donut(g,"support_name","gia_tri_ty","Giá trị theo CB hỗ trợ (tỷ đồng)","Tỷ đồng")
    a,b = st.columns(2)
    with a: _altair_bar(g,"support_name","diem_tb","Điểm bình quân theo CB hỗ trợ","Điểm")
    with b: _altair_bar(g,"support_name","tg_tb_phut","Thời gian xử lý bình quân theo CB hỗ trợ","Phút")
    _altair_bar(g,"support_name","tg_tiep_nhan_tb","Thời gian từ QLKH giao đến CBHT tiếp nhận lần đầu","Phút")

    # Benchmark QLKH toàn phòng; CBHT/QLKH không xem điểm bình quân theo từng QLKH.
    st.subheader("Phân tích theo Cán bộ QLKH")
    gq = _staff_aggregate_with_roster(room_f_stats, "qlkh_name", "Cán bộ QLKH")
    if operational_view:
        gqshow = gq.rename(columns={"qlkh_name":"CB QLKH","so_tac_nghiep":"Số TN","gia_tri_ty":"Giá trị (tỷ đồng)","tg_tb_phut":"TG xử lý TB (phút)","tg_tiep_nhan_tb":"TG giao→tiếp nhận TB (phút)","lam_lai":"Làm lại"})[["CB QLKH","Số TN","Giá trị (tỷ đồng)","TG giao→tiếp nhận TB (phút)","TG xử lý TB (phút)","Làm lại"]].copy()
        gqshow["Giá trị (tỷ đồng)"] = gqshow["Giá trị (tỷ đồng)"].map(lambda x:fmt_billion(x,False)); gqshow["TG giao→tiếp nhận TB (phút)"] = gqshow["TG giao→tiếp nhận TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); gqshow["TG xử lý TB (phút)"] = gqshow["TG xử lý TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—")
    else:
        gqshow = gq.rename(columns={"qlkh_name":"CB QLKH","so_tac_nghiep":"Số TN","gia_tri_ty":"Giá trị (tỷ đồng)","diem_tb":"Điểm TB","tg_tb_phut":"TG xử lý TB (phút)","tg_tiep_nhan_tb":"TG giao→tiếp nhận TB (phút)","lam_lai":"Làm lại"})[["CB QLKH","Số TN","Giá trị (tỷ đồng)","Điểm TB","TG giao→tiếp nhận TB (phút)","TG xử lý TB (phút)","Làm lại"]].copy()
        gqshow["Giá trị (tỷ đồng)"] = gqshow["Giá trị (tỷ đồng)"].map(lambda x:fmt_billion(x,False)); gqshow["TG giao→tiếp nhận TB (phút)"] = gqshow["TG giao→tiếp nhận TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); gqshow["TG xử lý TB (phút)"] = gqshow["TG xử lý TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); gqshow["Điểm TB"] = gqshow["Điểm TB"].map(fmt_score)
    st.dataframe(gqshow,use_container_width=True,hide_index=True)
    a,b=st.columns(2)
    with a: _altair_donut(gq,"qlkh_name","so_tac_nghiep","Số tác nghiệp theo CB QLKH","Số tác nghiệp")
    with b: _altair_donut(gq,"qlkh_name","gia_tri_ty","Giá trị theo CB QLKH (tỷ đồng)","Tỷ đồng")
    if operational_view:
        a,b=st.columns(2)
        with a: _altair_bar(gq,"qlkh_name","tg_tiep_nhan_tb","TG từ giao đến CBHT tiếp nhận theo CB QLKH","Phút")
        with b: _altair_bar(gq,"qlkh_name","tg_tb_phut","Thời gian xử lý bình quân theo CB QLKH","Phút")
    else:
        a,b=st.columns(2)
        with a: _altair_bar(gq,"qlkh_name","diem_tb","Điểm bình quân theo CB QLKH","Điểm")
        with b: _altair_bar(gq,"qlkh_name","tg_tb_phut","Thời gian xử lý bình quân theo CB QLKH","Phút")
        _altair_bar(gq,"qlkh_name","tg_tiep_nhan_tb","TG từ giao đến CBHT tiếp nhận theo CB QLKH","Phút")

    if analysis_f.empty:
        st.info("Không có dữ liệu để phân tích cá nhân theo loại công việc/tuần/tháng.")
    else:
        st.subheader("Theo loại công việc")
        g2 = analysis_f_stats.groupby("task_type", dropna=False).agg(so_tac_nghiep=("id","count"),gia_tri_vnd=("amount_vnd","sum"),diem_tb=("avg_score","mean"),tg_tiep_nhan_tb=("assignment_to_accept_minutes","mean"),tg_tb_phut=("duration_minutes","mean"),lam_lai=("rework_count","sum")).reset_index(); g2["gia_tri_ty"]=(g2["gia_tri_vnd"]/1_000_000_000).round(1)
        _wg = time_goal_table(analysis_scope_stats,"week"); _mg = time_goal_table(analysis_scope_stats,"month")
        week_goal = _wg[["task_type","target_minutes"]].rename(columns={"target_minutes":"muc_tieu_tuan"}) if not _wg.empty else pd.DataFrame(columns=["task_type","muc_tieu_tuan"])
        month_goal = _mg[["task_type","target_minutes"]].rename(columns={"target_minutes":"muc_tieu_thang"}) if not _mg.empty else pd.DataFrame(columns=["task_type","muc_tieu_thang"])
        g2 = g2.merge(week_goal,on="task_type",how="left").merge(month_goal,on="task_type",how="left")
        gg = g2.rename(columns={"task_type":"Công việc","so_tac_nghiep":"Số TN","gia_tri_ty":"Giá trị (tỷ đồng)","diem_tb":"Điểm TB","tg_tiep_nhan_tb":"TG giao→tiếp nhận (phút)","tg_tb_phut":"TG xử lý TB (phút)","lam_lai":"Làm lại","muc_tieu_tuan":"MT tuần","muc_tieu_thang":"MT tháng"})[["Công việc","Số TN","Giá trị (tỷ đồng)","Điểm TB","TG giao→tiếp nhận (phút)","TG xử lý TB (phút)","MT tuần","MT tháng","Làm lại"]].copy(); gg["Giá trị (tỷ đồng)"]=gg["Giá trị (tỷ đồng)"].map(lambda x:fmt_billion(x,False)); gg["Điểm TB"]=gg["Điểm TB"].map(fmt_score)
        for col in ["TG giao→tiếp nhận (phút)","TG xử lý TB (phút)","MT tuần","MT tháng"]: gg[col]=gg[col].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—")
        st.dataframe(gg,use_container_width=True,hide_index=True)
        a,b=st.columns(2)
        with a: _altair_donut(g2,"task_type","so_tac_nghiep","Số tác nghiệp theo loại công việc","Số tác nghiệp")
        with b: _altair_donut(g2,"task_type","gia_tri_ty","Giá trị theo loại công việc (tỷ đồng)","Tỷ đồng")
        a,b=st.columns(2)
        with a: _altair_bar(g2,"task_type","diem_tb","Điểm bình quân theo loại công việc","Điểm")
        with b: _altair_bar(g2,"task_type","tg_tb_phut","Thời gian xử lý bình quân theo loại công việc","Phút")
        _altair_bar(g2,"task_type","tg_tiep_nhan_tb","Thời gian từ QLKH giao đến CBHT tiếp nhận theo loại công việc","Phút")

        st.subheader("Theo tuần calendar")
        weekly = calendar_performance_summary(analysis_f_stats,"week",by_task=False)
        if weekly.empty:
            st.info("Chưa có tác nghiệp hoàn thành để tổng hợp theo tuần.")
        else:
            weekly = weekly.sort_values("period_start").tail(16).copy(); weekly["gia_tri_ty"]=(weekly["value_vnd"]/1_000_000_000).round(1)
            ws = weekly.rename(columns={"period_label":"Tuần","period_range":"Khoảng ngày","samples":"Số TN hoàn thành","active_days":"Ngày phát sinh","gia_tri_ty":"Giá trị (tỷ đồng)","avg_score":"Điểm TB","avg_accept_wait":"TG giao→tiếp nhận TB (phút)","avg_minutes":"TG xử lý TB/ngày phát sinh (phút)"})[["Tuần","Khoảng ngày","Số TN hoàn thành","Ngày phát sinh","Giá trị (tỷ đồng)","Điểm TB","TG giao→tiếp nhận TB (phút)","TG xử lý TB/ngày phát sinh (phút)"]].copy(); ws["Giá trị (tỷ đồng)"]=ws["Giá trị (tỷ đồng)"].map(lambda x:fmt_billion(x,False)); ws["TG giao→tiếp nhận TB (phút)"]=ws["TG giao→tiếp nhận TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); ws["TG xử lý TB/ngày phát sinh (phút)"]=ws["TG xử lý TB/ngày phát sinh (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); ws["Điểm TB"]=ws["Điểm TB"].map(fmt_score)
            st.dataframe(ws,use_container_width=True,hide_index=True)
            a,b=st.columns(2)
            with a: _altair_bar(weekly,"period_label","samples","Số tác nghiệp hoàn thành theo tuần","Số tác nghiệp",chronological=True)
            with b: _altair_bar(weekly,"period_label","gia_tri_ty","Giá trị tác nghiệp theo tuần (tỷ đồng)","Tỷ đồng",chronological=True)
            a,b=st.columns(2)
            with a: _altair_bar(weekly,"period_label","avg_minutes","TG xử lý bình quân chuẩn hóa theo tuần","Phút",chronological=True)
            with b: _altair_bar(weekly,"period_label","avg_accept_wait","TG từ giao đến tiếp nhận bình quân theo tuần","Phút",chronological=True)
            _altair_bar(weekly,"period_label","active_days","Số ngày thực tế phát sinh theo tuần","Ngày",chronological=True)
        # Chỉ benchmark CB hỗ trợ theo tuần; bỏ hoàn toàn so sánh QLKH tuần theo yêu cầu.
        if not qlkh_view:
            st.markdown("#### So sánh toàn bộ Cán bộ hỗ trợ theo tuần")
            _render_staff_period_comparison(room_f_stats, "week", "support_name", "CB hỗ trợ")
        if not operational_view:
            st.markdown("#### So sánh toàn bộ Cán bộ QLKH theo tuần")
            _render_staff_period_comparison(room_f_stats, "week", "qlkh_name", "CB QLKH")

        st.subheader("Theo tháng")
        gm = analysis_f_stats.copy(); gm["month_start"] = gm.start_dt.dt.to_period("M").dt.to_timestamp(); gm["thang"] = gm["month_start"].dt.strftime("%m/%Y")
        g3 = gm.groupby(["month_start","thang"]).agg(so_tac_nghiep=("id","count"),diem_tb=("avg_score","mean"),gia_tri_vnd=("amount_vnd","sum"),tg_tiep_nhan_tb=("assignment_to_accept_minutes","mean"),tg_tb_phut=("duration_minutes","mean")).reset_index(); g3["gia_tri_ty"]=(g3["gia_tri_vnd"]/1_000_000_000).round(1); g3=g3.sort_values("month_start")
        a,b=st.columns(2)
        with a: _altair_bar(g3,"thang","so_tac_nghiep","Số tác nghiệp theo tháng","Số tác nghiệp",chronological=True)
        with b: _altair_bar(g3,"thang","gia_tri_ty","Giá trị theo tháng (tỷ đồng)","Tỷ đồng",chronological=True)
        a,b=st.columns(2)
        with a: _altair_bar(g3,"thang","diem_tb","Điểm bình quân theo tháng","Điểm",chronological=True)
        with b: _altair_bar(g3,"thang","tg_tb_phut","Thời gian xử lý bình quân theo tháng","Phút",chronological=True)
        _altair_bar(g3,"thang","tg_tiep_nhan_tb","Thời gian từ QLKH giao đến CBHT tiếp nhận theo tháng","Phút",chronological=True)
        g3s=g3.rename(columns={"thang":"Tháng","so_tac_nghiep":"Số TN","diem_tb":"Điểm TB","gia_tri_ty":"Giá trị (tỷ đồng)","tg_tiep_nhan_tb":"TG giao→tiếp nhận TB (phút)","tg_tb_phut":"TG xử lý TB (phút)"})[["Tháng","Số TN","Giá trị (tỷ đồng)","Điểm TB","TG giao→tiếp nhận TB (phút)","TG xử lý TB (phút)"]].copy(); g3s["Giá trị (tỷ đồng)"]=g3s["Giá trị (tỷ đồng)"].map(lambda x:fmt_billion(x,False)); g3s["TG giao→tiếp nhận TB (phút)"]=g3s["TG giao→tiếp nhận TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); g3s["TG xử lý TB (phút)"]=g3s["TG xử lý TB (phút)"].map(lambda x:f"{float(x):,.1f}".replace(",",".") if pd.notna(x) else "—"); g3s["Điểm TB"]=g3s["Điểm TB"].map(fmt_score); st.dataframe(g3s,use_container_width=True,hide_index=True)
        if not qlkh_view:
            st.markdown("#### So sánh toàn bộ Cán bộ hỗ trợ theo tháng")
            _render_staff_period_comparison(room_f_stats, "month", "support_name", "CB hỗ trợ")
        if not operational_view:
            st.markdown("#### So sánh toàn bộ Cán bộ QLKH theo tháng")
            _render_staff_period_comparison(room_f_stats, "month", "qlkh_name", "CB QLKH")

    st.subheader("Dữ liệu chi tiết")
    detail_df = analysis_f if operational_view else room_f
    render_task_table(detail_df, include_scores=not support_view, dashboard_billions=True)
    report=make_excel_report(detail_df, support_privacy=support_view); st.download_button("Xuất báo cáo Excel theo bộ lọc",report,file_name=f"KHDN_TacNghiep_{datetime.now():%Y%m%d_%H%M}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",type="primary")


def customer_template_bytes():
    d = pd.DataFrame({"CIF": ["0001234567", "0007654321"], "Tên KH": ["CÔNG TY CP DEMO A", "CÔNG TY TNHH DEMO B"], "CB QLKH": ["qlkh1", "Nguyễn Văn QLKH"]})
    b = BytesIO(); d.to_excel(b, index=False); return b.getvalue()


def backup_db_bytes():
    return sqlite_backup_bytes(DB_PATH)


def admin_page(u):
    if not u["is_admin"]:
        st.error("Bạn không có quyền quản trị.")
        return
    page_title("Quản trị hệ thống", "Quản lý người dùng, khách hàng CIF, loại công việc, audit và sao lưu dữ liệu.")
    admin_view = pill_nav("admin_view", [("users","👥 Người dùng"),("customers","🏢 Khách hàng CIF"),("types","🧩 Loại công việc"),("audit","🧾 Audit"),("backup","💾 Sao lưu")], default="users", prefix="subnav_admin")
    if admin_view == "users":
        st.subheader("Tạo người dùng")
        with st.form("create_user"):
            c1, c2 = st.columns(2)
            username = c1.text_input("Username")
            full_name = c2.text_input("Họ tên")
            c3, c4, c5 = st.columns(3)
            role = c3.selectbox("Nhóm quyền", ROLES)
            password = c4.text_input("Mật khẩu khởi tạo", type="password", value="Bidv@123")
            is_admin = c5.checkbox("Quyền Admin")
            ok = st.form_submit_button("Tạo user", type="primary")
        if ok:
            if not username.strip() or not full_name.strip() or not password_ok(password):
                st.error("Nhập đủ thông tin. Mật khẩu tối thiểu 8 ký tự, gồm chữ và số.")
            else:
                try:
                    ts = now_str()
                    uid = execute('''INSERT INTO users(username,full_name,password_hash,role,is_admin,active,must_change_password,created_at,updated_at)
                                     VALUES(?,?,?,?,?,1,1,?,?)''',
                                  (username.strip(), full_name.strip(), hash_password(password), role, int(is_admin), ts, ts))
                    audit(u["id"], "CREATE_USER", "user", uid, f"{username.strip()} - {full_name.strip()} - {role}")
                    st.success("Đã tạo user. Người dùng sẽ phải đổi mật khẩu khi đăng nhập lần đầu.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Username đã tồn tại.")
        udf = all_users()
        udf_show=udf.copy(); udf_show["last_login_at"]=udf_show["last_login_at"].map(fmt_dt); udf_show=udf_show.drop(columns=["deleted_at"],errors="ignore"); st.dataframe(udf_show, use_container_width=True, hide_index=True)
        if not udf.empty:
            uid = st.selectbox("Chọn user để cập nhật", udf.id.tolist(), key="admin_selected_user", format_func=lambda x: f"{udf[udf.id == x].iloc[0].full_name} ({udf[udf.id == x].iloc[0].username})")
            cur = udf[udf.id == uid].iloc[0]
            st.markdown("#### Thông tin đăng nhập & phân quyền")
            c0,c1 = st.columns(2)
            new_username = c0.text_input("Username", value=str(cur.username), key=f"admin_username_{int(uid)}", help="Admin có thể đổi username. Username cũ được giải phóng ngay sau khi đổi.")
            nr = c1.selectbox("Nhóm quyền", ROLES, index=ROLES.index(cur.role), key=f"new_role_{int(uid)}")
            c2,c3 = st.columns(2)
            active = c2.checkbox("Đang hoạt động", value=bool(cur.active), key=f"active_flag_{int(uid)}")
            adminflag = c3.checkbox("Quyền Admin", value=bool(cur.is_admin), key=f"admin_flag_{int(uid)}")
            np = st.text_input("Reset mật khẩu (để trống nếu không đổi)", type="password", key=f"new_pw_{int(uid)}")
            st.caption("Admin có quyền đổi username và reset mật khẩu cho mọi user. Nếu Admin quên mật khẩu, tại màn hình đăng nhập chọn **Quên mật khẩu Admin?** để nhận mật khẩu tạm thời qua email khôi phục.")
            csave,cdelete=st.columns([3,1])
            if csave.button("Lưu thay đổi user", type="primary", use_container_width=True, key=f"save_user_{int(uid)}"):
                if int(uid) == int(u["id"]) and not active:
                    st.error("Không thể tự khóa tài khoản đang đăng nhập.")
                elif np and not password_ok(np):
                    st.error("Mật khẩu reset tối thiểu 8 ký tự, gồm chữ và số.")
                else:
                    try:
                        effective_username=str(cur.username)
                        if new_username.strip().lower()!=str(cur.username).strip().lower() or new_username.strip()!=str(cur.username).strip():
                            effective_username=rename_username(u,uid,new_username)
                        execute("UPDATE users SET role=?,active=?,is_admin=?,updated_at=? WHERE id=?", (nr, int(active), int(adminflag), now_str(), uid))
                        if np:
                            execute("UPDATE users SET password_hash=?,must_change_password=1,updated_at=? WHERE id=?", (hash_password(np), now_str(), uid))
                        audit(u["id"], "UPDATE_USER", "user", uid, f"username={effective_username}; role={nr}; active={active}; admin={adminflag}; reset_pw={bool(np)}")
                        if int(uid)==int(u["id"]):
                            fresh_self=user_by_username(effective_username,active_only=False)
                            if fresh_self: st.session_state.user=dict(fresh_self)
                        st.success("Đã cập nhật user."); st.rerun()
                    except (ValueError,sqlite3.IntegrityError) as exc:
                        st.error(str(exc) if str(exc) else "Không thể cập nhật username.")
            with cdelete:
                st.write("")
                delete_toggle=st.checkbox("Xóa user",key=f"delete_toggle_{int(uid)}",help="Xóa tài khoản khỏi danh sách đăng nhập nhưng vẫn giữ lịch sử tác nghiệp/audit.")
            if delete_toggle:
                st.warning("Xóa user sẽ khóa đăng nhập và giải phóng username để có thể tạo lại. Lịch sử công việc/đánh giá vẫn được giữ nguyên. User có tác nghiệp chưa kết thúc phải được điều chuyển trước.")
                confirm=st.text_input("Nhập đúng username để xác nhận xóa",key=f"delete_confirm_{int(uid)}")
                if st.button("Xác nhận xóa user",type="secondary",key=f"delete_user_{int(uid)}"):
                    if confirm.strip()!=str(cur.username):
                        st.error("Username xác nhận chưa đúng.")
                    else:
                        try:
                            deleted=delete_user_account(u,uid); st.success(f"Đã xóa user {deleted} khỏi hệ thống đăng nhập."); st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))

    if admin_view == "customers":
        st.download_button("Tải file mẫu danh mục khách hàng", customer_template_bytes(), "Mau_DanhMuc_KhachHang_KHDN.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.write("File cần có **CIF**, **Tên KH** và nên có **CB QLKH**. Cột QLKH có thể ghi **username** hoặc **họ tên user**; hệ thống sẽ đối chiếu chính xác và không tự gán user khác nếu không khớp.")
        upl = st.file_uploader("Tải danh sách khách hàng", type=["xlsx", "xls", "csv"])
        if upl:
            try:
                d = pd.read_csv(upl, dtype=str) if upl.name.lower().endswith(".csv") else pd.read_excel(upl, dtype=str)
                d = d.fillna("")
                st.dataframe(d.head(20), use_container_width=True, hide_index=True)
                if len(d.columns) < 2:
                    st.error("File phải có tối thiểu 2 cột.")
                else:
                    cols = list(d.columns)
                    cif_idx = _guess_column(cols, ["CIF", "Mã CIF", "Ma CIF"])
                    name_idx = _guess_column(cols, ["Tên KH", "Tên khách hàng", "Khách hàng"])
                    q_guess = _guess_column(cols, ["CB QLKH", "Cán bộ QLKH", "QLKH", "Username QLKH"])
                    q_opts = ["—"] + cols
                    q_index = (q_guess + 1) if cols and "qlkh" in _person_match_key(cols[q_guess]).replace(" ", "") else 0
                    c1, c2, c3 = st.columns(3)
                    cif_col = c1.selectbox("Cột CIF", cols, index=min(cif_idx, len(cols)-1))
                    name_col = c2.selectbox("Cột Tên KH", cols, index=min(name_idx, len(cols)-1))
                    qlkh_col = c3.selectbox("Cột CB QLKH", q_opts, index=min(q_index, len(q_opts)-1))

                    users = all_users("Cán bộ QLKH", active_only=True)
                    if qlkh_col != "—":
                        preview_rows = []
                        for _, rr in d.head(50).iterrows():
                            raw = str(rr.get(qlkh_col, "")).strip()
                            qid_preview, status_preview = match_qlkh_user(users, raw)
                            linked = "—"
                            if qid_preview is not None:
                                ur = users[users.id.astype(int) == int(qid_preview)].iloc[0]
                                linked = f"{ur.full_name} ({ur.username})"
                            preview_rows.append({"CIF": str(rr.get(cif_col, "")).strip(), "QLKH nguồn": raw, "User được liên kết": linked, "Kết quả": status_preview})
                        if preview_rows:
                            st.caption("Kiểm tra đối chiếu QLKH trước khi nạp")
                            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

                    if st.button("Nạp/Đồng bộ khách hàng", type="primary"):
                        n = 0
                        matched = 0
                        unmatched = []
                        ts = now_str()
                        for _, r in d.iterrows():
                            cif = str(r.get(cif_col, "")).strip()
                            name = str(r.get(name_col, "")).strip()
                            if not cif or cif.lower() == "nan" or not name or name.lower() == "nan":
                                continue
                            qid = None
                            qraw = ""
                            match_status = "Không có cột QLKH"
                            if qlkh_col != "—":
                                qraw = str(r.get(qlkh_col, "")).strip()
                                qid, match_status = match_qlkh_user(users, qraw)
                                if qid is not None:
                                    matched += 1
                                elif qraw and qraw.lower() != "nan":
                                    unmatched.append(f"{cif}: {qraw} ({match_status})")
                            with get_conn() as c:
                                if qlkh_col == "—":
                                    c.execute("""INSERT INTO customers(cif,customer_name,qlkh_user_id,qlkh_source_text,active,created_at,updated_at)
                                                 VALUES(?,?,NULL,NULL,1,?,?)
                                                 ON CONFLICT(cif) DO UPDATE SET customer_name=excluded.customer_name,active=1,updated_at=excluded.updated_at""",
                                              (cif, name, ts, ts))
                                else:
                                    # Khi file có cột QLKH, luôn dùng đúng kết quả của dòng đang nạp; không giữ nhầm QLKH cũ nếu dòng mới không khớp.
                                    c.execute("""INSERT INTO customers(cif,customer_name,qlkh_user_id,qlkh_source_text,active,created_at,updated_at)
                                                 VALUES(?,?,?,?,1,?,?)
                                                 ON CONFLICT(cif) DO UPDATE SET customer_name=excluded.customer_name,
                                                 qlkh_user_id=excluded.qlkh_user_id,qlkh_source_text=excluded.qlkh_source_text,
                                                 active=1,updated_at=excluded.updated_at""",
                                              (cif, name, qid, qraw, ts, ts))
                                c.commit()
                                n += 1
                        audit(u["id"], "IMPORT_CUSTOMERS", "customer", "", f"rows={n}; matched={matched}; unmatched={len(unmatched)}")
                        st.success(f"Đã đồng bộ {n} khách hàng; liên kết đúng {matched} dòng QLKH.")
                        if unmatched:
                            st.warning("Các dòng chưa liên kết QLKH sẽ để trống, không tự gán cán bộ khác:\n" + "\n".join(unmatched[:30]))
                            if len(unmatched) > 30:
                                st.caption(f"... và {len(unmatched)-30} dòng khác.")
            except Exception as e:
                st.error(f"Không đọc được file: {e}")

        cdf = qdf("""SELECT c.id,c.cif,c.customer_name,c.qlkh_source_text,
                            CASE WHEN u.id IS NULL THEN NULL ELSE u.full_name || ' (' || u.username || ')' END qlkh,
                            c.active
                     FROM customers c LEFT JOIN users u ON u.id=c.qlkh_user_id
                     ORDER BY c.customer_name,c.cif""")
        st.dataframe(cdf.rename(columns={"cif":"CIF","customer_name":"Tên KH","qlkh_source_text":"QLKH nguồn","qlkh":"QLKH đã liên kết","active":"Hoạt động"}), use_container_width=True, hide_index=True)
        if not cdf.empty:
            cid = st.selectbox("Chọn khách hàng để cập nhật phụ trách", cdf.id.tolist(), format_func=lambda x: f"{cdf[cdf.id == x].iloc[0].cif} - {cdf[cdf.id == x].iloc[0].customer_name}")
            qusers = all_users("Cán bộ QLKH", active_only=True)
            opts = [0] + qusers.id.astype(int).tolist()
            current_link = cdf[cdf.id == cid].iloc[0].qlkh
            idx = 0
            if pd.notna(current_link):
                current_id_df = qdf("SELECT qlkh_user_id FROM customers WHERE id=?", (int(cid),))
                if not current_id_df.empty and pd.notna(current_id_df.iloc[0].qlkh_user_id):
                    cur_id = int(current_id_df.iloc[0].qlkh_user_id)
                    if cur_id in opts:
                        idx = opts.index(cur_id)
            qid = st.selectbox("CB QLKH phụ trách", opts, index=idx, format_func=lambda x: "— Chưa gắn —" if x == 0 else f"{qusers[qusers.id==x].iloc[0].full_name} ({qusers[qusers.id==x].iloc[0].username})")
            active_c = st.checkbox("Khách hàng đang hoạt động", value=bool(cdf[cdf.id == cid].iloc[0].active))
            if st.button("Cập nhật khách hàng"):
                source_text = "" if qid == 0 else str(qusers[qusers.id==qid].iloc[0].username)
                execute("UPDATE customers SET qlkh_user_id=?,qlkh_source_text=?,active=?,updated_at=? WHERE id=?", (None if qid == 0 else int(qid), source_text, int(active_c), now_str(), cid))
                audit(u["id"], "UPDATE_CUSTOMER", "customer", cid, f"qlkh={qid}; active={active_c}")
                st.success("Đã cập nhật.")
                st.rerun()

    if admin_view == "types":
        types=qdf("SELECT id,name,active,created_at,updated_at FROM task_types ORDER BY id"); st.dataframe(types,use_container_width=True,hide_index=True)
        with st.form("new_type"):
            name=st.text_input("Tên công việc mới"); ok=st.form_submit_button("Thêm loại công việc")
        if ok:
            try:
                ts=now_str(); xid=execute("INSERT INTO task_types(name,sla_hours,active,created_at,updated_at) VALUES(?,8,1,?,?)",(name.strip(),ts,ts)); _active_task_types_cached.clear(); audit(u["id"],"CREATE_TASK_TYPE","task_type",xid,name.strip()); st.success("Đã thêm loại công việc."); st.rerun()
            except sqlite3.IntegrityError: st.error("Tên công việc đã tồn tại.")
        if not types.empty:
            xid=st.selectbox("Chọn loại công việc để sửa",types.id.tolist(),format_func=lambda x:types[types.id==x].iloc[0]["name"]); r=types[types.id==xid].iloc[0]; nactive=st.checkbox("Đang sử dụng",value=bool(r.active));
            if st.button("Cập nhật loại công việc"):
                execute("UPDATE task_types SET active=?,updated_at=? WHERE id=?",(int(nactive),now_str(),xid)); _active_task_types_cached.clear(); audit(u["id"],"UPDATE_TASK_TYPE","task_type",xid,f"active={nactive}"); st.success("Đã cập nhật."); st.rerun()

    if admin_view == "audit":
        aud = qdf('''SELECT a.id,a.created_at,u.full_name actor,a.action,a.object_type,a.object_id,a.detail
                     FROM system_audit a LEFT JOIN users u ON u.id=a.actor_user_id ORDER BY a.id DESC LIMIT 2000''')
        if not aud.empty: aud["created_at"]=aud["created_at"].map(fmt_dt)
        st.dataframe(aud.rename(columns={"created_at":"Thời gian","actor":"Người thực hiện","action":"Hành động","object_type":"Đối tượng","object_id":"ID","detail":"Chi tiết"}), use_container_width=True, hide_index=True)
    if admin_view == "backup":
        st.info("Ngoài backup thủ công, hệ thống tự tạo bộ lưu trữ cuối năm khi bước sang năm mới: thống kê năm, chi tiết tác nghiệp năm và snapshot SQLite.")
        st.download_button("Tải backup SQLite hiện tại", backup_db_bytes(), file_name=f"khdn_ops_backup_{datetime.now():%Y%m%d_%H%M}.db", mime="application/octet-stream")
        backup_status = read_status(RUNTIME_DATA_DIR / "backup_status.json")
        if backup_status.get("last_error"):
            st.error("Sao lưu tự động gần nhất chưa thành công. Hãy tải bản sao lưu hiện tại và kiểm tra dung lượng lưu trữ.")
        if backup_status.get("last_success"):
            st.caption(f"Sao lưu tự động thành công gần nhất: {backup_status['last_success']}. Giữ tối đa 14 bản hằng ngày, trong ngân sách lưu trữ 50 MB.")
            saved = sorted((RUNTIME_DATA_DIR / "backups").glob("khdn_ops_????-??-??.db.gz"), reverse=True)
            if saved:
                choice = st.selectbox("Chọn bản sao lưu tự động", [p.name for p in saved], key="scheduled_backup_choice")
                chosen = next(p for p in saved if p.name == choice)
                st.download_button("Tải bản sao lưu tự động", chosen.read_bytes(), file_name=chosen.name, mime="application/gzip", key="scheduled_backup_download")
            st.caption("Các bản sao tự động nằm cùng ổ với dữ liệu chính. Nên tải thêm một bản về nơi lưu trữ riêng để có thể phục hồi nếu ổ bị xóa.")
        archives=qdf("SELECT * FROM annual_archives ORDER BY year DESC")
        if archives.empty:
            st.caption("Chưa có năm đã kết thúc có dữ liệu để tạo lưu trữ tự động.")
        else:
            st.markdown("### Lưu trữ dữ liệu theo năm")
            show=archives[["year","task_count","archived_at","best_five_year_reference"]].rename(columns={"year":"Năm","task_count":"Số hồ sơ","archived_at":"Thời gian sao lưu","best_five_year_reference":"Năm chuẩn thời gian (tham chiếu lưu trữ)"}).copy()
            show["Thời gian sao lưu"]=show["Thời gian sao lưu"].map(fmt_dt)
            _html_table(show,max_height=300)
            y=int(st.selectbox("Chọn năm để tải file lưu trữ",archives.year.astype(int).tolist(),key="archive_download_year"))
            row=archives[archives.year.eq(y)].iloc[0]
            cols=st.columns(3)
            for col,label,field,mime in [
                (cols[0],"⬇️ Thống kê năm","stats_file","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                (cols[1],"⬇️ Chi tiết công việc","detail_file","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                (cols[2],"⬇️ Snapshot SQLite","db_backup_file","application/octet-stream")]:
                path=_resolve_archive_path(row.get(field))
                if path.exists(): col.download_button(label,path.read_bytes(),file_name=path.name,mime=mime,use_container_width=True,key=f"dl_{field}_{y}")


def profile_page(u):
    page_title("Tài khoản", "Cập nhật ảnh đại diện và đổi mật khẩu cá nhân.")

    st.subheader("Ảnh đại diện")
    c1, c2 = st.columns([1, 3], gap="large")
    with c1:
        avatar_uri = _user_avatar_data_uri(u)
        if avatar_uri:
            st.markdown(f'<div style="display:flex;justify-content:center;padding:8px"><img src="{avatar_uri}" style="width:132px;height:132px;border-radius:50%;object-fit:cover;border:3px solid #F4B41A;box-shadow:0 8px 22px rgba(0,107,104,.14)"></div>', unsafe_allow_html=True)
        else:
            st.info("Chưa có ảnh đại diện.")
    with c2:
        upload = st.file_uploader("Tải avatar", type=["png", "jpg", "jpeg", "webp"], help="PNG/JPG/WEBP, tối đa 2 MB. Ảnh được lưu trong database để đi cùng bản sao lưu.", key="profile_avatar_upload")
        cc1, cc2 = st.columns(2)
        if cc1.button("Lưu avatar", type="primary", use_container_width=True, disabled=upload is None, key="save_avatar_btn"):
            raw = upload.getvalue() if upload is not None else b""
            mime = str(getattr(upload, "type", "") or "").lower()
            if mime not in {"image/png", "image/jpeg", "image/webp"}:
                st.error("Định dạng ảnh không được hỗ trợ.")
            elif len(raw) > 2 * 1024 * 1024:
                st.error("Avatar vượt quá 2 MB.")
            elif not raw:
                st.error("File ảnh rỗng.")
            else:
                execute("UPDATE users SET avatar_blob=?,avatar_mime=?,updated_at=? WHERE id=?", (sqlite3.Binary(raw), mime, now_str(), int(u["id"])))
                audit(u["id"], "UPDATE_AVATAR", "user", u["id"], f"Cập nhật avatar {mime}; {len(raw)} bytes")
                st.success("Đã cập nhật avatar.")
                st.rerun()
        if cc2.button("Xóa avatar", use_container_width=True, key="remove_avatar_btn", disabled=not bool(u.get("avatar_blob"))):
            execute("UPDATE users SET avatar_blob=NULL,avatar_mime=NULL,updated_at=? WHERE id=?", (now_str(), int(u["id"])))
            audit(u["id"], "REMOVE_AVATAR", "user", u["id"], "Xóa avatar cá nhân")
            st.success("Đã xóa avatar.")
            st.rerun()

    st.divider()
    st.subheader("Đổi mật khẩu")
    with st.form("change_pw"):
        old = st.text_input("Mật khẩu hiện tại", type="password")
        new = st.text_input("Mật khẩu mới", type="password")
        confirm = st.text_input("Nhập lại mật khẩu mới", type="password")
        ok = st.form_submit_button("Đổi mật khẩu", type="primary")
    if ok:
        row = user_by_username(u["username"])
        if not verify_password(old, row["password_hash"]): st.error("Mật khẩu hiện tại không đúng.")
        elif new != confirm: st.error("Hai lần nhập mật khẩu mới không khớp.")
        elif not password_ok(new): st.error("Mật khẩu mới tối thiểu 8 ký tự, gồm chữ và số.")
        else:
            execute("UPDATE users SET password_hash=?,must_change_password=0,updated_at=? WHERE id=?", (hash_password(new), now_str(), u["id"]))
            audit(u["id"], "CHANGE_PASSWORD", "user", u["id"], "Đổi mật khẩu cá nhân")
            st.success("Đã đổi mật khẩu.")


def guide_page(u):
    page_title("Hướng dẫn sử dụng", "Tài liệu hướng dẫn KHDN Ops V2.22 được đính kèm trực tiếp trong ứng dụng.")
    st.info("📘 Tài liệu gồm workflow CBHT/QLKH/Lãnh đạo/Admin, Dashboard, mục tiêu tuần-tháng, lịch sử, tỷ giá, sao lưu và xử lý sự cố.")
    if GUIDE_PATH.exists():
        data = GUIDE_PATH.read_bytes()
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng KHDN Ops V2.22 (.docx)",
            data=data,
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS_v2.22.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="download_khdn_guide",
        )
        st.caption("Tài liệu hướng dẫn nội bộ • cập nhật 11/09/2026 • 16 trang.")
    elif CLOUD_MODE:
        st.caption("Bản online cung cấp hướng dẫn đọc trực tiếp bên dưới; bản Word đầy đủ nằm trong gói cài đặt nội bộ.")
    else:
        st.warning("Chưa tìm thấy file hướng dẫn Word trong gói triển khai.")
    if GUIDE_MARKDOWN_PATH.exists():
        with st.expander("📖 Xem hướng dẫn trực tiếp trong app", expanded=CLOUD_MODE):
            st.markdown(GUIDE_MARKDOWN_PATH.read_text(encoding="utf-8"))
    st.markdown("### Truy cập nhanh")
    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown("**CBHT**  \nTiếp nhận → xử lý → báo hoàn thành → lịch sử.")
    with c2:
        st.markdown("**QLKH**  \nTạo/giao → theo dõi → đánh giá → xử lý hồ sơ trả lại.")
    with c3:
        st.markdown("**Lãnh đạo/Admin**  \nTheo dõi toàn phòng → làm lại → dashboard → quản trị/backup.")
    if CLOUD_MODE:
        st.caption("Bạn đang dùng bản online. Dữ liệu tác nghiệp chỉ được xem là bền vững khi máy chủ đã cấu hình kho dữ liệu/persistence phù hợp.")


# ---------- Main ----------
def _runtime_maintenance_once_per_session():
    """Run schema migration once per Streamlit session and annual archive once/day.

    Streamlit reruns the script for every button/widget interaction. Running the
    full schema migration and annual archive scan on every rerun was one of the
    largest avoidable sources of latency.
    """
    db_key = f"_db_initialized_{APP_VERSION}"
    if not st.session_state.get(db_key):
        init_db()
        st.session_state[db_key] = True
    today = now_dt().date().isoformat()
    if st.session_state.get("_annual_archive_checked_date") != today:
        annual_archive_maintenance()
        st.session_state["_annual_archive_checked_date"] = today


def app():
    st.set_page_config(page_title=APP_TITLE, page_icon=str(APP_ICON_PNG_PATH), layout="wide", initial_sidebar_state="auto" if CLOUD_MODE else "expanded")
    # Home Screen metadata is installed in the initial document head at build time.
    # Cache logo chính thức BIDV từ website BIDV; thất bại tải logo không làm gián đoạn app.
    ensure_bidv_logo()
    inject_css()
    _runtime_maintenance_once_per_session()
    device_login.sync(DB_PATH)
    if "user" not in st.session_state:
        login_ui(); return
    fresh = user_by_username(st.session_state.user["username"])
    if not fresh:
        st.session_state.pop("user", None); st.rerun()
    st.session_state.user = dict(fresh)
    u = st.session_state.user
    if u.get("must_change_password"):
        force_password_change(u); return
    sidebar_user(u)
    realtime_refresh_watch(u)
    notice = st.session_state.pop("_auto_refresh_notice", None)
    if notice:
        st.toast(notice, icon="🔄")
    page = sidebar_navigation(u)
    if page == "support": support_page(u)
    elif page == "qlkh": qlkh_page(u)
    elif page == "leader": leader_page(u)
    elif page == "dashboard": dashboard_page(u)
    elif page == "profile": profile_page(u)
    elif page == "guide": guide_page(u)
    elif page == "admin": admin_page(u)


if __name__ == "__main__":
    app()
