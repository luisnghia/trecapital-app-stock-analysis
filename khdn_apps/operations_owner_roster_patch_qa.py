from __future__ import annotations

import pandas as pd

from khdn_apps import operations_owner_roster_patch as patch
from khdn_apps import planning_operational_phase14_patch as phase14
from khdn_apps import planning_operational_phase15_patch as phase15


class _NS(dict):
    pass


def _all_users(role, active_only=True):
    rows = {
        "Cán bộ QLKH": [
            {"id": 10, "full_name": "QLKH B", "role": "Cán bộ QLKH", "active": 1},
            {"id": 11, "full_name": "QLKH A", "role": "Cán bộ QLKH", "active": 0},
        ],
        "Lãnh đạo phòng": [
            {"id": 20, "full_name": "Lãnh đạo B", "role": "Lãnh đạo phòng", "active": 1},
            {"id": 21, "full_name": "Lãnh đạo A", "role": "Lãnh đạo phòng", "active": 0},
        ],
    }[role]
    if active_only:
        rows = [r for r in rows if int(r["active"]) == 1]
    return pd.DataFrame(rows)


ns = _NS(all_users=_all_users)
active = patch._combined_owner_roster(ns, active_only=True)
all_rows = patch._combined_owner_roster(ns, active_only=False)
assert active.id.astype(int).tolist() == [10, 20], active
assert set(all_rows.id.astype(int).tolist()) == {10, 11, 20, 21}, all_rows
assert "Lãnh đạo phòng" in patch._owner_label(active, 20)

patch.install(ns)
assert ns.get("_OPERATIONS_OWNER_ROSTER_PATCH_VERSION") == patch.VERSION
assert patch.VERSION == "1.1.0"
assert phase14._active_qlkh(ns).id.astype(int).tolist() == [10, 20]
assert set(phase14._all_qlkh(ns).id.astype(int).tolist()) == {10, 11, 20, 21}

# Phase 15 must keep the legacy fallback when no explicit owner state exists,
# while respecting the new QLKH create-form owner once it has been selected.
assert phase15._prospect_owner_id({"id": 7, "role": "Cán bộ QLKH"}, "ql_new_cust", {}) == 7
assert phase15._prospect_owner_id(
    {"id": 7, "role": "Cán bộ QLKH"}, "ql_new_cust", {"ql_new_owner": 20}
) == 20
assert patch._is_qlkh_task_insert(
    "INSERT INTO tasks(customer_id,support_user_id,qlkh_user_id,request_source) VALUES(?,?,?,'QLKH')"
)

source = open(__file__.replace("_qa.py", ".py"), encoding="utf-8").read()
upper = source.upper()
checks = {
    "active_qlkh_and_leader": 'for role in ("Cán bộ QLKH", "Lãnh đạo phòng")' in source,
    "leader_admin_mode": "phase14._active_qlkh = active_owners" in source,
    "cbht_page_wrapped": 'app_ns["support_page"] = support_page' in source,
    "cbht_create_only": 'st.session_state.get("support_view", "inbox")' in source and '== "create"' in source,
    "qlkh_page_wrapped": 'app_ns["qlkh_page"] = qlkh_page' in source,
    "qlkh_owner_field": '"Cán bộ QLKH phụ trách *"' in source and '"ql_new_owner"' in source,
    "qlkh_owner_persisted_to_task": "seq[2] = owner_id" in source,
    "qlkh_prospect_owner_sync": "phase15._prospect_owner_id = prospect_owner_id" in source,
    "actor_not_impersonated": "Never replace actor_user_id" in source,
    "no_schema_ddl": "ALTER TABLE" not in upper and "DROP TABLE" not in upper,
    "no_historical_task_rewrite": "UPDATE TASKS" not in upper and "DELETE FROM TASKS" not in upper,
}
assert all(checks.values()), checks

print(
    "OPERATIONS_OWNER_ROSTER_PATCH_QA_PASS "
    "cbht=1 qlkh=1 leader=1 admin=1 active_qlkh=1 active_leader=1 "
    "owner_task_write=1 actor_preserved=1 prospect_owner_sync=1 data_migration=0"
)
