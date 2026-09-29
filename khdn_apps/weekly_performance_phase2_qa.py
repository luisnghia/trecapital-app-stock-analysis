from pathlib import Path

from khdn_apps import weekly_performance_phase2_patch as p2

ROOT = Path(__file__).resolve().parent
src = (ROOT / "weekly_performance_phase2_patch.py").read_text(encoding="utf-8")
notify = (ROOT / "weekly_phase2_notifications.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")
runtime = (ROOT / "runtime.py").read_text(encoding="utf-8")

# Exact worked example from the approved specification: 73.75 progress, 80 quality, 76.88 weekly.
items = [
    {"status":"DONE","priority_quadrant":1,"expected_complete_date":"2026-09-10","completed_at":"2026-09-10 10:00:00"},
    {"status":"DONE","priority_quadrant":1,"expected_complete_date":"2026-09-10","completed_at":"2026-09-11 10:00:00"},
    {"status":"DONE","priority_quadrant":2,"expected_complete_date":"2026-09-10","completed_at":"2026-09-10 10:00:00"},
    {"status":"DONE","priority_quadrant":2,"expected_complete_date":"2026-09-10","completed_at":"2026-09-10 10:00:00"},
    {"status":"PLANNED","priority_quadrant":2,"expected_complete_date":"2026-09-10"},
    {"status":"DONE","priority_quadrant":3,"expected_complete_date":"2026-09-10","completed_at":"2026-09-10 10:00:00"},
]
m = p2._metrics(items)
quality = p2._quality(4, 4)
week_score = p2._week_score(m["progress"], quality)
assert abs(m["progress"] - 73.75) < 0.01, m
assert abs(quality - 80.0) < 0.01, quality
assert abs(week_score - 76.88) < 0.02, week_score
assert p2._grade(week_score).startswith("B"), p2._grade(week_score)
assert p2._metrics([{"status":"DONE","priority_quadrant":4}])["progress"] == 0.0

checks = {
    "no_manual_hours_phase2": "Giờ thực tế" not in src and "number_input(\"Giờ" not in src,
    "review_1_to_5": "options=[1,2,3,4,5]" in src and "SELF_LEVELS" in src,
    "four_required_500": src.count("max_chars=500") >= 5 and "Phải nhập đủ 4 nội dung" in src,
    "manager_comment_1000": "max_chars=1000" in src,
    "gap_reason_required": "gap >= 2" in src and "Lý do chênh lệch điểm" in src,
    "scoring_weights": "WEIGHTS = {2: 3.0, 1: 3.0, 3: 1.0, 4: 0.0}" in src,
    "zero_weight_guard": "zero_weight" in src and "Điểm tiến độ = 0" in src,
    "personal_8_week": "Hiệu quả 8 tuần" in src and "_render_personal_performance" in src,
    "room_8_week": "Hiệu quả công việc 8 tuần" in src and "_render_room_performance" in src,
    "preserve_landings": "original_today" in src and "room_dashboard._render_approval_center" in src,
    "scheduled_plan_reminders": all(x in notify for x in ["PLAN_REMINDER_FRI", "PLAN_REMINDER_MON", "PLAN_OVERDUE", "CLOSE_WEEK", "MANAGER_REVIEW_PENDING"]),
    "submitted_plan_notification": "PLAN_WAITING_APPROVAL" in notify,
    "five_business_day_fallback": "process_quality_fallback" in notify and "_business_days_since" in notify,
    "worker_started": "weekly_phase2_notifications.worker_loop" in runtime,
    "phase2_installed_last": "_performance_phase2.install" in hotfix,
    "hotfix_version": any(f'VERSION = "{v}"' in hotfix for v in ("2.3.0", "2.2.0", "2.1.0")),
}
assert all(checks.values()), checks
print("WEEKLY_PERFORMANCE_PHASE2_QA_PASS", checks, {"progress":m["progress"], "quality":quality, "week":week_score, "grade":p2._grade(week_score)})
