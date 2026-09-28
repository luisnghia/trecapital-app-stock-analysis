"""Static/runtime guardrails for the unified Weekly Plan screen and alerts."""
from pathlib import Path
import py_compile

root = Path(__file__).resolve().parent
unified = (root / "weekly_plan_unified_patch.py").read_text(encoding="utf-8")
hotfix = (root / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")
weekly_notify = (root / "weekly_plan_notifications.py").read_text(encoding="utf-8")
runtime = (root / "runtime.py").read_text(encoding="utf-8")

for name in (
    "weekly_plan_unified_patch.py",
    "weekly_priority_policy_hotfix.py",
    "weekly_plan_notifications.py",
    "runtime.py",
):
    py_compile.compile(str(root / name), doraise=True)

checks = {
    "logger_keyword_compat": "logger=None, logger_arg=None" in unified and "logger_arg=active_logger" in unified,
    "no_today_tab": '("today", "Hôm nay")' not in unified,
    "no_emergent_tab": '("emergent", "Phát sinh")' not in unified,
    "room_retained": '("room", "Kế hoạch phòng")' in unified,
    "same_screen_emergent_add": 'status == "DA_DUYET"' in unified and "emergent=True" in unified,
    "obsolete_text_replaced": "việc mới trong tuần ghi tại mục Phát sinh" in unified and "thêm ngay tại màn hình Kế hoạch tuần" in unified,
    "hotfix_idempotent": "_WEEKLY_PRIORITY_POLICY_HOTFIX_VERSION" in hotfix and "if getattr(policy, _FLAG, None) == VERSION" in hotfix,
    "unified_installed_after_refinement": hotfix.index("_form_refinement.install") < hotfix.index("_unified.install"),
    "new_work_notification": "NEW_WORK" in weekly_notify and "Công việc kế hoạch mới" in weekly_notify,
    "due_tomorrow_notification": "DUE_TOMORROW" in weekly_notify,
    "due_today_notification": "DUE_TODAY" in weekly_notify,
    "overdue_notification": "OVERDUE" in weekly_notify and "controller_user_id" in weekly_notify,
    "push_delivery": "_send_notification_push" in weekly_notify and "flush_pending_push" in weekly_notify,
    "runtime_worker": "weekly_plan_notifications.worker_loop" in runtime and "khdn-weekly-notifications" in runtime,
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"WEEKLY_PLAN_UNIFIED_QA_FAIL {bad}")
print("WEEKLY_PLAN_UNIFIED_QA_PASS", checks)
