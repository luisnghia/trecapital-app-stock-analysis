from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from khdn_apps import customer_cif_admin_patch as patch
from khdn_apps import customer_cif_qlkh_refresh_patch as qlkh_refresh
from khdn_apps import customer_cif_import_reliability_patch as reliable
from khdn_apps import customer_cif_unresolved_qlkh_fallback_patch as qlkh_fallback


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
c.execute("INSERT INTO users VALUES(2,'ql2','QL 2','Cán bộ QLKH',1)")
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
assert r["qlkh_user_id"] == 1
assert c.execute("SELECT customer_id FROM tasks WHERE id=1").fetchone()[0] == prospect_id
assert c.execute("SELECT customer_id FROM weekly_plan_items WHERE id=1").fetchone()[0] == prospect_id

# Previous refresh behavior remains valid.
qlkh_refresh.install()
cid2, result2 = patch.apply_cif_row(
    c,
    1,
    cif="00012345",
    name="CÔNG TY ABC",
    tax_id="040123",
    qlkh_raw="ql2 - QL 2",
)
assert cid2 == prospect_id and result2 == "UPDATED"
r = c.execute("SELECT * FROM customers WHERE id=?", (prospect_id,)).fetchone()
assert r["qlkh_user_id"] == 2
assert r["qlkh_source_text"] == "ql2 - QL 2"
assert c.execute("SELECT customer_id FROM tasks WHERE id=1").fetchone()[0] == prospect_id
assert c.execute("SELECT customer_id FROM weekly_plan_items WHERE id=1").fetchone()[0] == prospect_id

# Reliability layer + final unresolved-QLKH policy are both active.
reliable.install()
qlkh_fallback.install()
assert patch.apply_cif_row is qlkh_fallback._apply_with_qlkh_fallback
assert reliable._apply_cif_row is qlkh_fallback._apply_with_qlkh_fallback
assert patch._render_safe_import is reliable._render_safe_import
assert patch._resolve_qlkh is reliable._resolve_qlkh

# Blank QLKH preserves current ownership for an existing CIF.
patch.apply_cif_row(c, 1, cif="00012345", name="CÔNG TY ABC", qlkh_raw="")
r = c.execute("SELECT * FROM customers WHERE id=?", (prospect_id,)).fetchone()
assert r["qlkh_user_id"] == 2
assert r["qlkh_source_text"] == "ql2 - QL 2"

# Unresolved QLKH on an existing CIF must NOT block and must keep current owner.
patch.apply_cif_row(
    c, 1, cif="00012345", name="CÔNG TY ABC",
    qlkh_raw="CAN BO KHONG TON TAI",
)
r = c.execute("SELECT * FROM customers WHERE id=?", (prospect_id,)).fetchone()
assert r["qlkh_user_id"] == 2
assert r["qlkh_source_text"] == "ql2 - QL 2"

# Flexible header and QLKH parsing.
df = pd.DataFrame([
    {"Mã CIF": "00012345", "Tên khách hàng": "CÔNG TY ABC", "CBQLKH phụ trách": "ql1 - QL 1"}
])
plan, cols = reliable._build_plan(df, c)
assert cols["cif"] == "Mã CIF"
assert cols["name"] == "Tên khách hàng"
assert cols["qlkh"] == "CBQLKH phụ trách"
assert plan[0]["action"] == "UPDATE"
assert reliable._resolve_qlkh(c, "ql1 - QL 1") == 1
assert reliable._resolve_qlkh(c, "QL 2") == 2

# Excel-like CIF values normalize consistently.
assert reliable._clean_cif("12345.0") == "12345"
assert reliable._clean_cif("1.2345E+4") == "12345"
assert reliable._clean_cif("'00012345") == "00012345"

# Mixed old/new file: unresolved QLKH is a fallback, not a failed customer row.
items = [
    {
        "row": 0, "cif": "00012345", "name": "CÔNG TY ABC", "tax": "040123",
        "qlkh_raw": "ql1 - QL 1", "contact_name": "", "contact_phone": "",
        "action": "UPDATE", "target": prospect_id, "candidates": [],
    },
    {
        "row": 1, "cif": "00099999", "name": "CÔNG TY MỚI", "tax": "040999",
        "qlkh_raw": "QL 2", "contact_name": "", "contact_phone": "",
        "action": "CREATE", "target": None, "candidates": [],
    },
    {
        "row": 2, "cif": "00088888", "name": "CÔNG TY QLKH KHÔNG KHỚP", "tax": "040888",
        "qlkh_raw": "CAN BO KHONG TON TAI", "contact_name": "", "contact_phone": "",
        "action": "CREATE", "target": None, "candidates": [],
    },
]
done, errors = reliable.apply_import_items(c, 1, items, {})
assert done["UPDATED"] == 1
assert done["CREATED"] == 2
assert done["FAILED"] == 0
assert errors == []
r = c.execute("SELECT * FROM customers WHERE cif='00012345'").fetchone()
assert r["id"] == prospect_id and r["qlkh_user_id"] == 1
new_row = c.execute("SELECT * FROM customers WHERE cif='00099999'").fetchone()
assert new_row is not None and new_row["qlkh_user_id"] == 2
fallback_new = c.execute("SELECT * FROM customers WHERE cif='00088888'").fetchone()
assert fallback_new is not None
assert fallback_new["qlkh_user_id"] is None
assert fallback_new["qlkh_source_text"] is None

# New official CIF activating a PROSPECT with unresolved QLKH also ends blank.
c.execute(
    "INSERT INTO customers(cif,customer_name,qlkh_user_id,qlkh_source_text,active,created_at,customer_status,tax_id) "
    "VALUES(NULL,'PROSPECT NEW CIF',1,'ql1',0,'2026-01-02','PROSPECT','040555')"
)
prospect_new_cif = c.execute("SELECT id FROM customers WHERE customer_name='PROSPECT NEW CIF'").fetchone()[0]
cid3, result3 = patch.apply_cif_row(
    c, 1, cif="00055555", name="PROSPECT NEW CIF", target_id=prospect_new_cif,
    tax_id="040555", qlkh_raw="UNKNOWN OFFICER",
)
assert cid3 == prospect_new_cif and result3 == "ACTIVATED"
r = c.execute("SELECT * FROM customers WHERE id=?", (prospect_new_cif,)).fetchone()
assert r["qlkh_user_id"] is None and r["qlkh_source_text"] is None

# Duplicate row can be merged into the historic id while linked workflow moves.
c.execute(
    "INSERT INTO customers(cif,customer_name,active,created_at,customer_status) "
    "VALUES(NULL,'ABC duplicate',0,'2026-01-03','PROSPECT')"
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
    "VALUES('999','FREE',1,'2026-01-04','ACTIVE_CIF')"
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
    "VALUES(NULL,'XYZ',0,'2026-01-05','PROSPECT','040777')"
)
cands = patch._prospect_candidates(c, "XYZ COMPANY", "040777")
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

reliable_src = Path(reliable.__file__).read_text(encoding="utf-8")
for token in [
    "mixed_file=1",
    "normalized_cif=1",
    "qlkh_refresh=1",
    "row_savepoint=1",
    "customer_id_preserved=1",
    "SAVEPOINT",
    "CBQLKH",
    "Một dòng lỗi không làm mất các dòng hợp lệ",
]:
    assert token in reliable_src, token

fallback_src = Path(qlkh_fallback.__file__).read_text(encoding="utf-8")
for token in [
    "existing_cif_keep_owner=1",
    "new_cif_blank_owner=1",
    "import_continues=1",
    "CUSTOMER_CIF_UNRESOLVED_QLKH_FALLBACK",
    "EXISTING_CIF_KEEP_CURRENT_QLKH",
    "NEW_CIF_IMPORTED_QLKH_BLANK",
]:
    assert token in fallback_src, token

fix_src = Path(patch.__file__).with_name("planning_operational_phase10_fix.py").read_text(encoding="utf-8")
for token in [
    "_install_legacy_customer_import_guard",
    'str(label) == "Nạp/Đồng bộ khách hàng"',
    'kwargs["disabled"] = True',
    "Nạp/Đồng bộ khách hàng (đã thay bằng Nạp CIF an toàn)",
    "legacy_import_guard=1",
    "customer_cif_qlkh_refresh.install(app_ns, logger)",
    "customer_cif_import_reliability.install(app_ns, logger)",
    "customer_cif_unresolved_qlkh_fallback.install(app_ns, logger)",
    "customer_cif_unresolved_qlkh_fallback=1",
    "mobile_input_perf.install(app_ns, policy, logger)",
]:
    assert token in fix_src, token

print(
    "CUSTOMER_CIF_ADMIN_PATCH_QA_PASS "
    "preserve_id=1 merge_fk=1 bulk_delete_guard=1 safe_import=1 weekly_fk=1 "
    "legacy_import_locked=1 existing_cif_qlkh_refresh=1 mixed_old_new=1 new_cif_create=1 "
    "row_error_isolated=1 normalized_cif=1 flexible_qlkh_header=1 customer_id_preserved=1 "
    "unresolved_existing_keeps_qlkh=1 unresolved_new_imports_blank_qlkh=1 unresolved_does_not_block=1"
)
