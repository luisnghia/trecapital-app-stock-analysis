from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_followup_ux_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "date_only_reschedule": "Dời ngày dự kiến hoàn thành" in src and "_HiddenTimeColumn" in src,
    "hidden_internal_1700": "return time(17, 0)" in src,
    "reschedule_red_validation": "cw_reschedule_invalid_" in src and "_fail_validation" in src,
    "strong_red_css": "box-shadow:0 0 0 2px rgba(255,75,75,.42)" in src,
    "weekday_quick_add": "wkday_quick_add_" in src and "＋ Thêm công việc" in src,
    "quick_day_preselect": "wp_quick_day_" in src and "session_state[f\"{prefix}_day\"]" in src,
    "weekly_next_to_today": "order = [\"work_today\", \"weekly_plan\", \"customer_work\"]" in src,
    "no_past_due": "min_value = max(today, old_min) if old_min else today" in src,
    "customer_due_guard": "weekboard._customer_create_form" in src and "_DueGuardProxy(st)" in src,
    "followup_installed": "_followup_ux.install" in hotfix,
    "hotfix_version": any(f'VERSION = "{v}"' in hotfix for v in ("2.2.0", "2.1.0")),
}

assert all(checks.values()), checks
print("PLANNING_FOLLOWUP_UX_QA_PASS", checks)
