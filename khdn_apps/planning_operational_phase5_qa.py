from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import time

from khdn_apps import planning_operational_phase5_patch as p5

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase5_patch.py").read_text(encoding="utf-8")
admin_scope = (ROOT / "admin_scope_patch.py").read_text(encoding="utf-8")
ops_nav = (ROOT / "operations_admin_nav_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "admin_only": 'Chỉ Admin mới có quyền truy cập Quản trị hệ thống.' in admin_scope and 'if not bool(u["is_admin"])' in admin_scope,
    "ops_admin_merged": 'Nhóm nguyên nhân tác nghiệp' in admin_scope and 'legacy_route_retired=1' in ops_nav,
    "backup_separate_page": 'admin_view' in src and '!= "backup"' in src,
    "planning_before_ops": src.index('📅  KẾ HOẠCH') < src.index('🧾  TÁC NGHIỆP'),
    "compact_detail": 'st-key-cw_open_' in src and 'max-width:240px' in src,
    "add_autoclose": 'wp_add_open_' in src and 'wp_quick_day_' in src and '_AddCloseProxy' in src,
    "fast_save": 'WEEKLY_PLAN_FAST_SAVE' in src and 'cur.lastrowid' in src,
    "progress_history": 'Lịch sử thay đổi / cập nhật tiến độ' in src and 'weekly_plan_actions' in src,
    "room_weekdays": 'Kế hoạch phòng · Thứ 2 → Thứ 6' in src and 'p3week.render_week_board' in src,
    "progress_highlights": all(x in src for x in ['🔴 QUÁ HẠN','🔄 ĐANG LÀM','↪ DỜI','🚩 Q2 CẦN CHÚ Ý']),
    "reviews_bottom": 'P5_LEADER_REVIEWS_MOVED_BOTTOM' in src and src.index('result = original(') < src.index('phase2._render_manager_reviews'),
    "backlog_update_yellow": 'p5_update_btn_' in src and '#F4B41A' in src and 'Cập nhật trực tiếp trên công việc này.' in src,
    "installed_last": '_operational_phase5.install' in hotfix,
}

bad = [k for k,v in checks.items() if not v]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE5_QA_FAIL {bad} {checks}")

# Small real SQLite benchmark for the new one-transaction insert path.
with tempfile.TemporaryDirectory(prefix="khdn-p5-qa-") as td:
    db = Path(td) / "qa.db"
    c = sqlite3.connect(db)
    c.executescript("""
    CREATE TABLE weekly_plans(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,week_start TEXT,status TEXT,created_at TEXT,updated_at TEXT,UNIQUE(user_id,week_start));
    CREATE TABLE weekly_plan_items(id INTEGER PRIMARY KEY AUTOINCREMENT,plan_id INTEGER,user_id INTEGER,work_date TEXT,start_time TEXT,daypart TEXT,title TEXT,customer_id INTEGER,customer_text TEXT,category TEXT,purposes_json TEXT,source_text TEXT,linked_task_id INTEGER,status TEXT,reschedule_count INTEGER,note TEXT,created_at TEXT,updated_at TEXT,estimated_hours REAL,actual_hours REAL,expected_output TEXT,is_emergent INTEGER,carryover_count INTEGER,carried_from_item_id INTEGER);
    CREATE TABLE weekly_plan_actions(id INTEGER PRIMARY KEY AUTOINCREMENT,item_id INTEGER,actor_user_id INTEGER,action TEXT,detail TEXT,created_at TEXT);
    """)
    c.commit(); c.close()

    @contextmanager
    def get_conn():
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def ensure_plan(conn, uid, ws):
        ts = "2026-09-29 10:00:00"
        conn.execute("INSERT OR IGNORE INTO weekly_plans(user_id,week_start,status,created_at,updated_at) VALUES(?,?,'ACTIVE',?,?)", (uid,ws.isoformat(),ts,ts))
        return int(conn.execute("SELECT id FROM weekly_plans WHERE user_id=? AND week_start=?", (uid,ws.isoformat())).fetchone()[0])

    fake = SimpleNamespace(
        _now=lambda: "2026-09-29 10:00:00",
        _set_classification=lambda *a, **k: True,
    )
    core = SimpleNamespace(ensure_plan=ensure_plan)
    p5._fast_save_extended_item(fake, core)
    started = time.perf_counter()
    iid, errs = fake._save_extended_item(core, get_conn, 1, date(2026,9,28), {
        "work_date":"2026-09-29","title":"QA","category":"Kế hoạch tuần","purposes":[],
        "source_text":"QA","estimated_hours":1,"is_emergent":0,"focus_category_id":1,
        "deadline_within_7d":None,"kpi_risk_flag":None,
    })
    elapsed = time.perf_counter() - started
    assert iid == 1 and not errs, (iid, errs)
    assert elapsed < 1.0, elapsed

print("PLANNING_OPERATIONAL_PHASE5_QA_PASS", checks, f"fast_save_seconds={elapsed:.4f}")
