from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_room_dashboard_detail_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "room_priority_same_logic_as_today": "priority_today._priority_sort_key" in src and "priority_today._heat_summary" in src,
    "room_priority_detailed_cards": "_room_case_card" in src and "room_case_detail_" in src,
    "leader_dashboard_replaced": "customer_ui.render_leader_dashboard = render_leader_dashboard" in src,
    "customer_move_compact": "customer_ui._case_card" in src and "THAY ĐỔI NGÀY DỰ KIẾN HOÀN THÀNH" in src,
    "weekly_move_compact": "THAY ĐỔI NGÀY THỰC HIỆN KẾ HOẠCH" in src and "room_week_move_" in src,
    "change_highlight": "pd-change-strip" in src and "pd-old" in src and "pd-new" in src,
    "reason_highlighted": "Lý do:" in src,
    "approval_actions_preserved": "decide_reschedule" in src and "RESCHEDULE_APPROVE" in src and "RESCHEDULE_REJECT" in src,
    "approval_center_preserved": all(x in src for x in ["Công việc khách hàng mới", "Kế hoạch tuần đã nộp", "Đề nghị dời công việc khách hàng", "Đề nghị dời kế hoạch tuần"]),
    "room_dashboard_installed_before_phase2": "_room_dashboard.install" in hotfix and hotfix.index("_room_dashboard.install") < hotfix.index("_performance_phase2.install"),
    "hotfix_version": any(f'VERSION = "{v}"' in hotfix for v in ("2.4.0", "2.3.0", "2.2.0", "2.1.0")),
}

assert all(checks.values()), checks
print("PLANNING_ROOM_DASHBOARD_DETAIL_QA_PASS", checks)
