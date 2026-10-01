from __future__ import annotations

import sqlite3
from pathlib import Path

from khdn_apps import customer_cif_admin_patch as patch


c = sqlite3.connect(":memory:")
c.row_factory = sqlite3.Row
c.execute("PRAGMA foreign_keys=ON")
c.executescript(
    """
CREATE TABLE users(
 id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, role TEXT, active INTEGER
);
CREATE TABLE customers(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 cif TEXT UNIQUE,
 customer_name TEXT NOT NULL,
 qlkh_user_id INTEGER,
 qlkh_source_text TEXT,
 active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 updated_at TEXT,
 customer_status TEXT NOT NULL DEFAULT 'ACTIVE_CIF',
 tax_id TEXT, contact_name TEXT, contact_phone TEXT
);
CREATE TABLE tasks(
 id INTEGER PRIMARY KEY,
 customer_id INTEGER REFERENCES customers(id)
);
CREATE TABLE customer_work_cases(
 id INTEGER PRIMARY KEY,
 customer_id INTEGER REFERENCES customers(id)
);
CREATE TABLE weekly_plan_items(
 id INTEGER PRIMARY KEY,
 customer_id INTEGER REFERENCES customers(id)
);
CREATE TABLE system_audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 actor_user_id INTEGER,
 action TEXT,
 object_type TEXT,
 object_id TEXT,
 detail TEXT,
 created_at TEXT
);
"""
)

c.execute("INSERT INTO users VALUES(1,'ql1','QL 1','Cán bộ QLKH',1)")
c.execute(
    "INSERT INTO customers(cif,customer_name,active,created_at,customer_status,tax_id) "
    "VALUES(NULL,'CÔNG TY ABC',0,'2026-01-01','PROSPECT','040123')"
)
prospect_id = c.execute(
    "SELECT id FROM customers WHERE customer_name='CÔNG TY ABC'"
).fetchone()[0]
c.execute("INSERT INTO tasks VALUES(1,?)", (prospect_id,))
c.execute("INSERT INTO weekly_plan_items VALUES(1,?)", (prospect_id,))

cid, result = patch.apply_cif_row(
    c,
    1,
    cif="00012345",
    name="CÔNG TY ABC",
    target_id=prospect_id,
    tax_id="040123",
    qlkh_raw="ql1",
)
assert cid == prospect_id and result == "ACTIVATED"
r = c.execute("SELECT * FROM customers WHERE id=?", (prospect_id,)).fetchone()
assert r["cif"] == "00012345"
assert r["customer_status"] == "ACTIVE_CIF"
assert r["active"] == 1
assert c.execute("SELECT customer_id FROM tasks WHERE id=1").fetchone()[0] == prospect_id
assert c.execute("SELECT customer_id FROM weekly_plan_items WHERE id=1").fetchone()[0] == prospect_id

# Duplicate row can be merged into the historic id while linked workflow moves.
c.execute(
    "INSERT INTO customers(cif,customer_name,active,created_at,customer_status) "
    "VALUES(NULL,'ABC duplicate',0,'2026-01-02','PROSPECT')"
)
dup_id = c.execute(
    "SELECT id FROM customers WHERE customer_name='ABC duplicate'"
).fetchone()[0]
c.execute("INSERT INTO customer_work_cases VALUES(1,?)", (dup_id,))
patch.merge_customers(c, 1, prospect_id, dup_id)
assert c.execute("SELECT COUNT(*) FROM customers WHERE id=?", (dup_id,)).fetchone()[0] == 0
assert c.execute("SELECT customer_id FROM customer_work_cases WHERE id=1").fetchone()[0] == prospect_id

# Bulk delete deletes only unreferenced rows and blocks workflow-linked rows.
c.execute(
    "INSERT INTO customers(cif,customer_name,active,created_at,customer_status) "
    "VALUES('999','FREE',1,'2026-01-03','ACTIVE_CIF')"
)
free_id = c.execute("SELECT id FROM customers WHERE cif='999'").fetchone()[0]
deleted, blocked = patch.delete_customers_safe(c, 1, [prospect_id, free_id])
assert free_id in deleted
assert prospect_id in blocked
assert c.execute("SELECT COUNT(*) FROM customers WHERE id=?", (free_id,)).fetchone()[0] == 0
assert c.execute("SELECT COUNT(*) FROM customers WHERE id=?", (prospect_id,)).fetchone()[0] == 1

# Exact MST candidate is deterministic and eligible for preserve-ID activation.
c.execute(
    "INSERT INTO customers(cif,customer_name,active,created_at,customer_status,tax_id) "
    "VALUES(NULL,'XYZ',0,'2026-01-04','PROSPECT','040999')"
)
cands = patch._prospect_candidates(c, "XYZ COMPANY", "040999")
assert len(cands) >= 1
assert cands[0]["_reason"].startswith("trùng MST")

src = Path(patch.__file__).read_text(encoding="utf-8")
for token in [
    "Nạp CIF an toàn",
    "Hợp nhất khách hàng trùng",
    "Xóa nhiều khách hàng",
    "PROSPECT_CUSTOMER_ACTIVATE_IMPORT",
    "CUSTOMER_MERGE",
    "CUSTOMER_BULK_DELETE",
    "dependency_counts",
    "preserve_customer_id=1",
]:
    assert token in src, token

fix_src = Path(patch.__file__).with_name("planning_operational_phase10_fix.py").read_text(encoding="utf-8")
for token in [
    "_install_legacy_customer_import_guard",
    'str(label) == "Nạp/Đồng bộ khách hàng"',
    'kwargs["disabled"] = True',
    "Nạp/Đồng bộ khách hàng (đã thay bằng Nạp CIF an toàn)",
    "legacy_import_guard=1",
    "mobile_input_perf.install(app_ns, policy, logger)",
]:
    assert token in fix_src, token

print(
    "CUSTOMER_CIF_ADMIN_PATCH_QA_PASS "
    "preserve_id=1 merge_fk=1 bulk_delete_guard=1 safe_import=1 weekly_fk=1 legacy_import_locked=1"
)
