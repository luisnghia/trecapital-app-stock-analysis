from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from khdn_apps import customer_work as customer_core
from khdn_apps import planning_operational_phase6_patch as p6
from khdn_apps import planning_operational_phase9_patch as p9

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase9_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "phase9_after_phase8": "_operational_phase9.install" in hotfix and hotfix.index("_operational_phase9.install") > hotfix.index("_operational_phase8.install"),
    "leader_read_all": "Lãnh đạo phòng đang ở quyền xem toàn phòng" in src and "customer_core.list_cases(c, manager=True" in src,
    "room_customer_no_direct_filter": "data = customer_core.list_cases(c, manager=True, include_completed=False)" in src,
    "room_weekly_today_no_direct_filter": "wp_today = [dict(r) for r in c.execute" in src and "Kế hoạch hôm nay · toàn phòng" in src,
    "approval_center_preserved": "room_dashboard._render_approval_center" in src and "approval_scope=unchanged" in src,
    "attention_action_scope_preserved": "This is an ACTION queue" in src and "p3dash._attention_dashboard" in src,
    "weekly_outside_scope_readonly": "Kế hoạch ngoài phạm vi kiểm soát · chỉ xem" in src and "can_update=False, can_edit=False" in src,
    "approval_filter_not_replaced": "policy._direct_scope_ok(c, leader_uid" in src,
    "admin_leader_owner_list": "role='Lãnh đạo phòng'" in src and "P9_ADMIN_ASSIGNABLE_LEADERS_INSTALLED" in src,
}

bad = [name for name, ok in checks.items() if not ok]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE9_QA_FAIL {bad} {checks}")

# Semantic authorization proof: normal leader may approve only a case for which
# they are the exact controller; Admin remains allowed for all cases.
with tempfile.TemporaryDirectory(prefix="p9-auth-qa-") as td:
    db = Path(td) / "qa.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER);
        CREATE TABLE customer_work_cases(id INTEGER PRIMARY KEY,controller_user_id INTEGER);
        INSERT INTO users VALUES(1,'CB A','Cán bộ QLKH',0,1);
        INSERT INTO users VALUES(2,'LĐ A','Lãnh đạo phòng',0,1);
        INSERT INTO users VALUES(3,'LĐ B','Lãnh đạo phòng',0,1);
        INSERT INTO users VALUES(4,'Admin','Lãnh đạo phòng',1,1);
        INSERT INTO customer_work_cases VALUES(101,2);
        """
    )
    assert p6._controller_allows(c, 2, 101) is True
    assert p6._controller_allows(c, 3, 101) is False
    assert p6._controller_allows(c, 4, 101) is True
    c.close()

# Semantic assignment proof: phase 9's owner source includes active leaders.
with tempfile.TemporaryDirectory(prefix="p9-owner-qa-") as td:
    db = Path(td) / "qa.db"
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    c.executescript(
        """
        CREATE TABLE users(id INTEGER PRIMARY KEY,full_name TEXT,role TEXT,is_admin INTEGER,active INTEGER);
        INSERT INTO users VALUES(1,'CB A','Cán bộ QLKH',0,1);
        INSERT INTO users VALUES(2,'LĐ A','Lãnh đạo phòng',0,1);
        INSERT INTO users VALUES(3,'LĐ inactive','Lãnh đạo phòng',0,0);
        INSERT INTO users VALUES(4,'Admin','Lãnh đạo phòng',1,1);
        """
    )
    class Core:
        _P9_ASSIGNABLE_LEADERS = False
        @staticmethod
        def staff_users(conn):
            return [dict(r) for r in conn.execute(
                "SELECT id,full_name,role,is_admin FROM users WHERE active=1 AND role<>'Lãnh đạo phòng' ORDER BY full_name"
            ).fetchall()]
    p9._install_admin_assignable_leaders(Core)
    rows = Core.staff_users(c)
    active_ids = {int(x["id"]) for x in rows}
    assert 2 in active_ids, rows
    assert 3 not in active_ids, rows
    c.close()

class Policy:
    @staticmethod
    def _is_admin(u): return bool(u.get("is_admin"))
    @staticmethod
    def _is_leader(u): return str(u.get("role") or "") == "Lãnh đạo phòng"

assert p9._leader_read_all({"role":"Lãnh đạo phòng","is_admin":0}, Policy) is True
assert p9._leader_read_all({"role":"Cán bộ QLKH","is_admin":0}, Policy) is False
assert p9._leader_read_all({"role":"Lãnh đạo phòng","is_admin":1}, Policy) is True

print(
    "PLANNING_OPERATIONAL_PHASE9_QA_PASS",
    checks,
    "controller_exact=PASS admin_assign_leader=PASS leader_read_all=PASS",
)
