from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_dashboard_consolidation_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "weekly_form_hidden_by_default": "wp_add_open_" in src and "if not st.session_state.get(gate_key)" in src,
    "weekday_click_opens_form": "class _BoardOpenProxy" in src and "key.startswith(\"wkday_quick_add_\")" in src,
    "approval_tab_removed": 'route != "work_approvals"' in src,
    "approvals_embedded_dashboard": "original_dashboard" in src and "_render_approval_center" in src and "render_leader_dashboard" in src,
    "all_approval_sections": all(x in src for x in [
        "Công việc khách hàng mới",
        "Kế hoạch tuần đã nộp",
        "Đề nghị dời công việc khách hàng",
        "Đề nghị dời kế hoạch tuần",
    ]),
    "full_customer_card": all(x in src for x in [
        "Mã công việc", "Khách hàng / CIF", "Nhóm / Loại công việc", "Mục công việc",
        "Cán bộ phụ trách", "Lãnh đạo kiểm soát", "Người liên hệ", "Ghi chú",
    ]),
    "full_weekly_card": all(x in src for x in [
        "Mã kế hoạch", "Ngày thực hiện", "Ngày dự kiến hoàn thành", "Kết quả đầu ra",
        "Căn cứ phân loại", "Số lần dời", "Số lần chuyển tiếp",
    ]),
    "html_wrapped_metadata": "st.html(" in src and "white-space:normal" in src and "overflow-wrap:anywhere" in src,
    "actions_preserved": all(x in src for x in [
        "approve_case_plan", "decide_reschedule", "RESCHEDULE_APPROVE", "RESCHEDULE_REJECT",
        "Phê duyệt kế hoạch", "Trả lại điều chỉnh",
    ]),
    "hotfix_installs": "_dashboard_consolidation.install" in hotfix,
    "hotfix_version": any(f'VERSION = "{v}"' in hotfix for v in ("2.3.0", "2.2.0", "2.1.0")),
}

assert all(checks.values()), checks
print("PLANNING_DASHBOARD_CONSOLIDATION_QA_PASS", checks)
