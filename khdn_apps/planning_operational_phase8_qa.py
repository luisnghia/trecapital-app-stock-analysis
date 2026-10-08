from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile

from khdn_apps import planning_operational_phase8_patch as p8

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_operational_phase8_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "phase8_last": "_operational_phase8.install" in hotfix and hotfix.index("_operational_phase8.install") > hotfix.index("_operational_phase7.install"),
    "operational_backup_section": "Sao lưu Tác nghiệp & lưu trữ vận hành" in src,
    "current_sqlite_encrypted": "sqlite_backup_bytes" not in src and "Backup có mật khẩu" in src,
    "daily_backup_encrypted": "snapshot SQLite theo năm đã được mã hóa" in src,
    "annual_backup": "annual_archives" in src and "_render_annual_table(st, archives)" in src and "require_admin(db_path" in src,
    "html_table": "st.html(" in src and "table-layout:fixed" in src and "overflow-wrap:anywhere" in src,
    "case_link": "linked_case_id" in src and "workflow" in src,
    "case_due_source": "expected_complete_at" in src and "due_from_case" in src,
    "case_leader_source": "controller_user_id" in src and "leader_from_case" in src,
    "case_focus_source": "important_category_id" in src and "legacy_category_id" in src and "focus_from_case" in src,
    "source_fields_readonly": src.count("disabled=True") >= 3,
    "cancel_empty_red": "p7_cancel_reason_" in src and "placeholder-shown" in src and "#FF4B4B" in src,
    "runtime_logs": all(x in src for x in ["P8_OPERATIONAL_BACKUP_INSTALLED", "P8_WEEKLY_LINK_FORM_INSTALLED", "P8_CANCEL_REASON_REQUIRED_STYLE_INSTALLED"]),
}

bad = [name for name, ok in checks.items() if not ok]
if bad:
    raise SystemExit(f"PLANNING_OPERATIONAL_PHASE8_QA_FAIL {bad} {checks}")

# Semantic mapping: a linked Customer Work case must supply exactly the three
# requested Weekly Plan fields when the source records exist.
case = {
    "id": 91,
    "expected_complete_at": "2026-10-05 17:00:00",
    "controller_user_id": 7,
    "important_category_id": 12,
}
leaders = [{"id": 6, "full_name": "Lãnh đạo B"}, {"id": 7, "full_name": "Lãnh đạo A"}]
focus = [
    {"id": 100, "legacy_category_id": 11, "code": "TT11", "name": "Khác"},
    {"id": 101, "legacy_category_id": 12, "code": "TT12", "name": "Trọng tâm nguồn"},
]
due, leader, category = p8._source_defaults(case, leaders, focus)
assert due == date(2026, 10, 5), due
assert int(leader["id"]) == 7, leader
assert int(category["id"]) == 101, category

# Legacy annual archive resolution must stay inside the persistent data root.
with tempfile.TemporaryDirectory(prefix="p8-archive-qa-") as td:
    root = Path(td)
    annual = root / "annual_archive"
    annual.mkdir()
    file = annual / "ops-2025.xlsx"
    file.write_bytes(b"qa")
    assert p8._archive_file(root, "ops-2025.xlsx") == file.resolve()
    assert p8._archive_file(root, "../../etc/passwd") is None

print(
    "PLANNING_OPERATIONAL_PHASE8_QA_PASS",
    checks,
    "source_mapping=PASS archive_path_guard=PASS",
)
