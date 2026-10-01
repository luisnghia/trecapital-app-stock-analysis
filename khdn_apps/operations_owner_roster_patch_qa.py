from __future__ import annotations

import pandas as pd

from khdn_apps import operations_owner_roster_patch as patch
from khdn_apps import planning_operational_phase14_patch as phase14


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

patch.install(ns)
assert ns.get("_OPERATIONS_OWNER_ROSTER_PATCH_VERSION") == patch.VERSION
assert phase14._active_qlkh(ns).id.astype(int).tolist() == [10, 20]
assert set(phase14._all_qlkh(ns).id.astype(int).tolist()) == {10, 11, 20, 21}

# The patch must stay data-only/UI-roster-only: no DDL and no task UPDATE/DELETE.
source = open(__file__.replace("_qa.py", ".py"), encoding="utf-8").read().upper()
assert "ALTER TABLE" not in source
assert "DROP TABLE" not in source
assert "UPDATE TASKS" not in source
assert "DELETE FROM TASKS" not in source
assert '"CÁN BỘ QLKH", "LÃNH ĐẠO PHÒNG"' in source

print("OPERATIONS_OWNER_ROSTER_PATCH_QA_PASS active_qlkh=1 active_leader=1 scope_history=1 data_migration=0")
