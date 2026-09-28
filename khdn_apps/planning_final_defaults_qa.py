"""Guardrails for final blank-default and Weekly Plan card behavior."""
from pathlib import Path

src = (Path(__file__).resolve().parent / "planning_final_defaults_patch.py").read_text(encoding="utf-8")

checks = {
    "focus_none_last": 'options = list(focus_rows or []) + ["NONE"]' in src,
    "focus_blank_placeholder": 'placeholder="— Chọn —"' in src,
    "weekly_customer_blank": 'index=None' in src and 'placeholder="— Chọn khách hàng —"' in src,
    "weekly_day_blank": '"Ngày thực hiện *"' in src and 'value=None' in src,
    "weekly_due_blank": '"Ngày dự kiến hoàn thành *"' in src and 'value=None' in src,
    "weekly_leader_blank": '"Lãnh đạo phòng phụ trách *"' in src and 'index=None' in src,
    "customer_due_blank": '"Dự kiến hoàn thành *", value=None' in src,
    "customer_time_blank": '"Giờ dự kiến *", value=None' in src,
    "customer_owner_blank": '"Cán bộ phụ trách *", [current_owner]' in src and 'index=None' in src,
    "customer_controller_blank": '"Lãnh đạo kiểm soát *", leaders' in src and 'index=None' in src,
    "weekly_card_heat": "cwref._HEAT" in src and "wpfinal_card_" in src,
    "weekly_card_owner_controller": "owner_name_snapshot" in src and "controller_name_snapshot" in src,
    "weekly_card_customer_style": "background:linear-gradient(120deg" in src and "border-left:6px solid" in src,
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"PLANNING_FINAL_DEFAULTS_QA_FAIL {bad}")
print("PLANNING_FINAL_DEFAULTS_QA_PASS", checks)
