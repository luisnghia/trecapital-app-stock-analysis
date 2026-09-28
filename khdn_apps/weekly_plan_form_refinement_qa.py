"""Static guardrails for the final Weekly Plan form refinement."""
from pathlib import Path

src = (Path(__file__).resolve().parent / "weekly_plan_form_refinement_patch.py").read_text(encoding="utf-8")

checks = {
    "customer_first": src.index('"Khách hàng"') < src.index('"Công việc *"'),
    "open_customer_cases": "customer_work_cases" in src and "cw.status='ACTIVE'" in src,
    "manual_when_no_case": "Khách hàng chưa có công việc đang xử lý" in src,
    "due_date": "Ngày dự kiến hoàn thành *" in src and "expected_complete_date" in src,
    "no_hour_input": 'number_input("Giờ dự kiến' not in src,
    "no_output_input": 'text_input("Kết quả đầu ra' not in src,
    "leader_controller": "Lãnh đạo phòng phụ trách *" in src and "controller_user_id" in src,
    "legacy_focus_sync": "important_categories" in src and "legacy_category_id" in src,
    "live_focus_refresh": "live_focus_rows" in src,
    "hard_tab_text": "-webkit-text-fill-color" in src and "#173B38" in src and "#FFFFFF" in src,
    "duplicate_case_guard": "Công việc khách hàng này đã có trong kế hoạch tuần" in src,
    "form_epoch_reset": "wp_refine_epoch_" in src,
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"WEEKLY_PLAN_FORM_REFINEMENT_QA_FAIL {bad}")
print("WEEKLY_PLAN_FORM_REFINEMENT_QA_PASS", checks)
