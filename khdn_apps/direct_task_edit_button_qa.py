"""Static QA for KHDN V2.31.4 direct full-edit action."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
patch = (ROOT / "direct_task_edit_button_patch.py").read_text(encoding="utf-8")
online = (ROOT / "online_entry.py").read_text(encoding="utf-8")
offline = (ROOT / "offline_entry.py").read_text(encoding="utf-8")

checks = {
    "leader_admin_guard": "bool(user.get(\"is_admin\")) or user.get(\"role\") == \"Lãnh đạo phòng\"" in patch,
    "prominent_button": "✏️ SỬA TOÀN BỘ THÔNG TIN HỒ SƠ" in patch,
    "history_wrapped": 'original_task_history = ns["task_history"]' in patch and 'ns["task_history"] = task_history_with_direct_edit' in patch,
    "exact_task_target": 'st.session_state["full_edit_task_select"] = task_id' in patch,
    "leader_route": 'st.session_state["leader_view"] = "full_edit"' in patch,
    "admin_route": 'st.session_state["admin_view"] = "full_edit"' in patch,
    "audited_editor_reused": "full_edit_module.render_full_task_editor" in patch,
    "online_installed": "_install_v2314(_app_module.__dict__, _full_task_edit_module)" in online,
    "offline_installed": "_install_v2314(_app_module.__dict__, _full_task_edit_module)" in offline,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit(f"KHDN_DIRECT_TASK_EDIT_QA FAIL {failed} {checks}")
print("KHDN_DIRECT_TASK_EDIT_QA PASS", checks)
