from __future__ import annotations

from pathlib import Path

from khdn_apps import planning_operational_phase15_patch as p15

HERE = Path(__file__).resolve().parent
SRC = (HERE / "planning_operational_phase15_patch.py").read_text(encoding="utf-8")
FIX = (HERE / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")

checks = {
    "shared_customer_master": "potential_customer_patch" in SRC and "ensure_customer_master" in SRC,
    "schema_ensure_install_only": SRC.count("ensure_customer_master") == 1,
    "native_dropdown": 'st.selectbox(' in SRC and '"Khách hàng *"' in SRC,
    "planning_style_labels": "· CIF" in SRC and "· Chưa có CIF" in SRC,
    "native_search_help": "gõ CIF hoặc tên ngay trong ô danh sách" in SRC,
    "official_and_prospect": "c.active=1 OR c.customer_status='PROSPECT'" in SRC,
    "new_customer_option": "＋ Tạo khách hàng mới / chưa có CIF" in SRC,
    "name_only_create": '"Tên khách hàng mới *"' in SRC and "MST (nếu có)" not in SRC and "SĐT liên hệ" not in SRC and "Người liên hệ" not in SRC,
    "customer_work_later": "bổ sung sau ở Công việc khách hàng" in SRC,
    "duplicate_guard": "find_similar" in SRC and "Vẫn tạo mới" in SRC,
    "old_search_cards_removed": "Tìm thấy" not in SRC and "_search_customers" not in SRC,
    "support_role_wrapped": 'app_ns["support_page"] = support_page' in SRC,
    "qlkh_role_wrapped": 'app_ns["qlkh_page"] = qlkh_page' in SRC,
    "leader_admin_wrapped": 'app_ns["leader_page"] = leader_page' in SRC,
    "reset_support_picker": '_clear_picker_state(st, "new_cust")' in SRC,
    "reset_qlkh_picker": '_clear_picker_state(st, "ql_new_cust")' in SRC,
    "reset_leader_picker": '_clear_picker_state(st, "leader_ql_new_cust")' in SRC,
    "qlkh_owner_explicit": 'role == "Cán bộ QLKH"' in SRC,
    "leader_selected_owner": 'leader_ql_new_owner' in SRC,
    "support_master_unchanged": "UPDATE customers SET qlkh_user_id" not in SRC and "per-task" in SRC,
    "no_customer_id_rewrite": "UPDATE tasks SET customer_id" not in SRC,
    "no_schema_ddl": all(token not in SRC.upper() for token in ["ALTER TABLE", "DROP TABLE", "CREATE TABLE CUSTOMERS"]),
    "phase15_after_phase14": "phase14.install" in FIX and "phase15.install" in FIX and FIX.index("phase14.install") < FIX.index("phase15.install"),
}

assert all(checks.values()), checks

assert p15._eligible_customer(1, "ACTIVE_CIF") is True
assert p15._eligible_customer(0, "PROSPECT") is True
assert p15._eligible_customer(0, "INACTIVE") is False
assert p15._label({"cif": None, "customer_name": "CÔNG TY ABC"}) == "CÔNG TY ABC · Chưa có CIF"
assert p15._label({"cif": "12345", "customer_name": "CÔNG TY ABC"}) == "CÔNG TY ABC · CIF 12345"
assert p15._prospect_owner_id({"id": 7, "role": "Cán bộ QLKH"}, "ql_new_cust", {}) == 7
assert p15._prospect_owner_id({"id": 2, "role": "Lãnh đạo phòng"}, "leader_ql_new_cust", {"leader_ql_new_owner": 9}) == 9
assert p15._prospect_owner_id({"id": 3, "role": "Cán bộ hỗ trợ"}, "new_cust", {}) is None

print("PLANNING_OPERATIONAL_PHASE15_QA_PASS", checks, "dropdown=PASS native_search=PASS name_only_create=PASS role_reset=PASS no_data_rewrite=PASS")
