"""Build-time QA for KHDN V2.31.3 full task editor."""
from __future__ import annotations

from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    patch = (root / "full_task_edit_patch.py").read_text(encoding="utf-8")
    online = (root / "online_entry.py").read_text(encoding="utf-8")
    offline = (root / "offline_entry.py").read_text(encoding="utf-8")
    compile(patch, "full_task_edit_patch.py", "exec")
    checks = {
        "closed_cancelled_scope": "CLOSED/CANCELLED" in patch or ("đã kết thúc" in patch and "đã hủy" in patch),
        "leader_nav": 'state_key == "leader_view"' in patch and '"full_edit"' in patch,
        "admin_nav": 'state_key == "admin_view"' in patch,
        "full_business_update": "UPDATE tasks SET task_code=?" in patch,
        "all_timestamps": all(x in patch for x in ["assigned_at","accepted_at","first_accepted_at","returned_to_qlkh_at","cancelled_at","evaluated_at","last_rework_at","start_time","due_time","end_time","closed_time","created_at"]),
        "evaluation_edit": "UPDATE evaluations SET" in patch,
        "task_audit": "TASK_FULL_EDIT" in patch and "LEADER_ADMIN_EDIT" in patch,
        "evaluation_audit": "EVALUATION_EDIT" in patch,
        "online_installed": "_install_v2313" in online,
        "offline_installed": "_install_v2313" in offline,
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise SystemExit(f"KHDN_FULL_TASK_EDIT_QA FAIL: {failed}")
    print("KHDN_FULL_TASK_EDIT_QA PASS", checks)


if __name__ == "__main__":
    main()
