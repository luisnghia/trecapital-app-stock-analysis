"""Deterministic QA for operational phase 14 leader/QLKH parity."""
from pathlib import Path
import pandas as pd

import khdn_apps.planning_operational_phase14_patch as p14

ROOT = Path(__file__).resolve().parent
SRC = (ROOT / "planning_operational_phase14_patch.py").read_text(encoding="utf-8")
FIX = (ROOT / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")

checks = {
    "leader_guard": 'str(u.get("role") or "") == "Lãnh đạo phòng"' in SRC,
    "preserve_original_leader": 'return original_leader_page(u)' in SRC,
    "leader_mode_nav": '💼 Tác nghiệp QLKH' in SRC and '👔 Quản lý lãnh đạo' in SRC,
    "all_room_scope": 'visible_tasks_sql' in SRC and 'Phạm vi Cán bộ QLKH' in SRC,
    "create_assign": 'Tạo/giao hồ sơ' in SRC and "INSERT INTO tasks" in SRC,
    "owner_not_impersonated": 'int(owner_id)' in SRC and 'actor_uid = int(_uget(u, "id"))' in SRC,
    "leader_audit": 'log_action' in SRC and 'Lãnh đạo thực hiện nghiệp vụ QLKH' in SRC,
    "pending_reassign": 'QLKH_REASSIGN' in SRC and "status='PENDING_ACCEPTANCE'" in SRC,
    "returned_reopen": 'REOPEN_ASSIGN' in SRC and "status='RETURNED_TO_QLKH'" in SRC,
    "review_close": 'INSERT INTO evaluations' in SRC and "status='CLOSED'" in SRC,
    "cancel_required": 'Bắt buộc nhập lý do xóa/hủy' in SRC and 'leader_ql_cancel_reason_' in SRC,
    "cancel_red": '#ff4b4b' in SRC and ':placeholder-shown' in SRC,
    "history": 'Lịch sử đánh giá' in SRC and 'evaluator_name' in SRC,
    "no_schema_ddl": all(token not in SRC.upper() for token in ('ALTER TABLE', 'DROP TABLE', 'CREATE TABLE')),
    "phase14_after_phase13": 'planning_operational_phase14_patch as phase14' in FIX and 'phase13.install' in FIX and 'phase14.install' in FIX and FIX.index('phase14.install') > FIX.index('phase13.install'),
}

sample = pd.DataFrame([
    {"id": 1, "qlkh_user_id": 10},
    {"id": 2, "qlkh_user_id": 11},
    {"id": 3, "qlkh_user_id": 10},
])
semantic_scope = p14._filter_scope(sample, 10)
semantic = (
    list(semantic_scope["id"]) == [1, 3]
    and p14._filter_scope(sample, 0).equals(sample)
    and p14._is_leader({"role": "Lãnh đạo phòng", "is_admin": 0})
    and p14._is_leader({"role": "Cán bộ QLKH", "is_admin": 1})
    and not p14._is_leader({"role": "Cán bộ QLKH", "is_admin": 0})
)

if not all(checks.values()) or not semantic:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE14_QA_FAIL {checks} semantic={semantic}")
print(f"PLANNING_OPERATIONAL_PHASE14_QA_PASS {checks} semantic_scope=PASS no_data_migration=PASS")
