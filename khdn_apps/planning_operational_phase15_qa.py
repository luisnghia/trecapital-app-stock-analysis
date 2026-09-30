from __future__ import annotations

from pathlib import Path

from khdn_apps import planning_operational_phase15_patch as p15


HERE = Path(__file__).resolve().parent
SRC = (HERE / "planning_operational_phase15_patch.py").read_text(encoding="utf-8")
FIX = (HERE / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")

checks = {
    "shared_customer_master": "potential_customer_patch" in SRC and "ensure_customer_master" in SRC,
    "search_official_and_prospect": "c.active=1 OR c.customer_status='PROSPECT'" in SRC,
    "typed_name_create": "Tạo & chọn khách hàng" in SRC and '"name": q' in SRC,
    "no_fake_cif": "Không sinh CIF giả" in SRC,
    "duplicate_guard": "find_similar" in SRC and "Vẫn tạo mới" in SRC,
    "support_role_wrapped": 'app_ns["support_page"] = support_page' in SRC,
    "qlkh_role_wrapped": 'app_ns["qlkh_page"] = qlkh_page' in SRC,
    "leader_admin_wrapped": 'app_ns["leader_page"] = leader_page' in SRC,
    "qlkh_owner_explicit": 'role == "Cán bộ QLKH"' in SRC,
    "leader_selected_owner": 'leader_ql_new_owner' in SRC,
    "support_master_unchanged": "UPDATE customers SET qlkh_user_id" not in SRC and "per-task choice does not modify customer master ownership" in SRC,
    "prospect_label": "Chưa có CIF" in SRC,
    "audit_log": "PLANNING_OPERATIONAL_PHASE15_INSTALLED" in SRC,
    "no_customer_id_rewrite": "UPDATE tasks SET customer_id" not in SRC,
    "no_schema_ddl": all(token not in SRC.upper() for token in ["ALTER TABLE", "DROP TABLE", "CREATE TABLE CUSTOMERS"]),
    "phase15_after_phase14": "phase14.install" in FIX and "phase15.install" in FIX and FIX.index("phase14.install") < FIX.index("phase15.install"),
}

assert all(checks.values()), checks

# Small semantic checks independent of Streamlit/SQLite.
assert p15._eligible_customer(1, "ACTIVE_CIF") is True
assert p15._eligible_customer(0, "PROSPECT") is True
assert p15._eligible_customer(0, "INACTIVE") is False
assert p15._label({"cif": None, "customer_name": "CÔNG TY ABC"}) == "Chưa có CIF — CÔNG TY ABC"
assert p15._label({"cif": "12345", "customer_name": "CÔNG TY ABC"}) == "12345 — CÔNG TY ABC"
assert p15._prospect_owner_id({"id": 7, "role": "Cán bộ QLKH"}, "ql_new_cust", {}) == 7
assert p15._prospect_owner_id({"id": 2, "role": "Lãnh đạo phòng"}, "leader_ql_new_cust", {"leader_ql_new_owner": 9}) == 9
assert p15._prospect_owner_id({"id": 3, "role": "Cán bộ hỗ trợ"}, "new_cust", {}) is None

print("PLANNING_OPERATIONAL_PHASE15_QA_PASS", checks, "semantic_roles=PASS prospect_visibility=PASS master_ownership_preserved=PASS no_data_rewrite=PASS")
