from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

from khdn_apps import planning_operational_phase10_patch as p10
from khdn_apps import planning_operational_phase10_fix as p10fix

ROOT = Path(__file__).resolve().parent
SRC = (ROOT / "planning_operational_phase10_patch.py").read_text(encoding="utf-8")
HOT = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "three_contact_rows": "for slot in (1, 2, 3):" in SRC and "Người liên hệ {slot}" in SRC and "SĐT {slot}" in SRC and "Chức vụ {slot}" in SRC,
    "min_one_complete": "Tối thiểu 1 thông tin liên hệ hoàn chỉnh" in SRC and "if not complete:" in SRC,
    "partial_row_blocked": "Dòng liên hệ {slot} phải nhập đủ Người liên hệ, SĐT và Chức vụ" in SRC,
    "customer_selected_before_form": "Chọn khách hàng để tự động nạp thông tin liên hệ" in SRC and "if customer is None:" in SRC,
    "auto_load_master": "_load_contact_defaults" in SRC and "Đã tự động nạp" in SRC,
    "legacy_backfill": "NOT EXISTS(" in SRC and "customer_contact_master" in SRC and "migrated_customers" in SRC,
    "case_snapshot_three_rows": "contact2_name" in SRC and "contact3_name" in SRC and "_write_case_contacts" in SRC,
    "shared_contact_sync": "_sync_customer_contacts(c, customer_id, contacts, uid, ts, cid)" in SRC,
    "existing_case_edit": "Sửa thông tin liên hệ" in SRC and "CONTACT_UPDATE_P10" in SRC,
    "out_of_scope_leader_readonly": "leader and controller" in SRC and "không thuộc phạm vi được sửa" in SRC,
    "no_approval_override": "approve_case_plan =" not in SRC and "decide_reschedule =" not in SRC,
    "phase10_after_phase9": "_operational_phase9.install" in HOT and "_operational_phase10_fix.install" in HOT and HOT.index("_operational_phase10_fix.install") > HOT.index("_operational_phase9.install"),
}

assert all(checks.values()), checks

complete, partial = p10._normalize_contact_rows([
    {"name": " Anh A ", "phone": "0901", "role": "Giám đốc"},
    {"name": "Chị B", "phone": "", "role": "Kế toán trưởng"},
    {"name": "", "phone": "", "role": ""},
])
assert len(complete) == 1 and complete[0]["name"] == "Anh A", (complete, partial)
assert partial == [2], partial

with tempfile.TemporaryDirectory() as td:
    db = Path(td) / "p10.db"

    def get_conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    with get_conn() as c:
        c.executescript(
            """
            CREATE TABLE users(id INTEGER PRIMARY KEY, full_name TEXT);
            CREATE TABLE customers(id INTEGER PRIMARY KEY, customer_name TEXT);
            CREATE TABLE customer_work_cases(
                id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                contact_name TEXT,contact_phone TEXT,contact_role TEXT,
                created_at TEXT,updated_at TEXT,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );
            INSERT INTO users(id,full_name) VALUES(1,'Tester');
            INSERT INTO customers(id,customer_name) VALUES(10,'Customer A');
            INSERT INTO customer_work_cases(
                id,customer_id,contact_name,contact_phone,contact_role,created_at,updated_at
            ) VALUES(100,10,'Nguyen A','0901000000','Giám đốc','2026-09-01 08:00:00','2026-09-20 09:00:00');
            """
        )

    class Core:
        @staticmethod
        def ensure_schema(conn_fn, logger=None):
            return None

    class Worktype:
        @staticmethod
        def ensure_case_contacts(conn_fn, logger=None):
            return None

    p10._sync_customer_contacts = p10fix._safe_sync_customer_contacts
    p10._ensure_contact_schema(get_conn, Core, Worktype)

    with get_conn() as c:
        master = c.execute(
            "SELECT * FROM customer_contact_master WHERE customer_id=10 ORDER BY slot"
        ).fetchall()
        assert len(master) == 1, len(master)
        assert master[0]["contact_name"] == "Nguyen A"
        assert master[0]["updated_by"] is None
        defaults = p10._load_contact_defaults(c, 10)
        assert defaults[0]["phone"] == "0901000000", defaults

        contacts = [
            {"name": "Nguyen A", "phone": "0901111111", "role": "Giám đốc"},
            {"name": "Tran B", "phone": "0902222222", "role": "Kế toán trưởng"},
        ]
        p10._write_case_contacts(c, 100, contacts, "2026-09-29 17:00:00")
        p10fix._safe_sync_customer_contacts(c, 10, contacts, 1, "2026-09-29 17:00:00", 100)

    with get_conn() as c:
        row = c.execute("SELECT * FROM customer_work_cases WHERE id=100").fetchone()
        assert row["contact_name"] == "Nguyen A"
        assert row["contact2_name"] == "Tran B"
        assert row["contact3_name"] is None
        defaults = p10._load_contact_defaults(c, 10)
        assert defaults[0]["phone"] == "0901111111"
        assert defaults[1]["name"] == "Tran B"
        assert defaults[2]["name"] == ""

print(
    "PLANNING_OPERATIONAL_PHASE10_QA_PASS",
    checks,
    "three_rows=PASS min_one_complete=PASS legacy_carry=PASS editable_sync=PASS approval_scope_unchanged=PASS",
)
