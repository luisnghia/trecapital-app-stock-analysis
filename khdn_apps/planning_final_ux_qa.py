"""Guardrails for final UX behavior requested on Preview."""
from pathlib import Path

src = (Path(__file__).resolve().parent / "planning_final_ux_patch.py").read_text(encoding="utf-8")

checks = {
    "all_date_inputs_dmy": 'kwargs.setdefault("format", "DD/MM/YYYY")' in src and 'format="DD/MM/YYYY"' in src,
    "customer_priority_label": '"Công việc ưu tiên *"' in src,
    "customer_due_time_removed": '"Giờ dự kiến' not in src and '.time_input(' not in src,
    "customer_internal_end_of_day": 'time(17, 0)' in src,
    "required_red_persisted": '_fail_validation' in src and 'st.rerun()' in src and '#FF4B4B' in src,
    "weekly_case_code_hidden": 'def _case_option_label' in src and 'x.get("case_code")' not in src[src.index('def _case_option_label'):src.index('def _weekly_add_form')],
    "weekly_red_validation": 'invalid_state = f"{prefix}_invalid"' in src and '_fail_validation(st, invalid_state' in src,
    "duplicate_card_key_fixed": 'card_key = f"cwux_card_{cid}_{ctx}"' in src and 'def _render_context' in src,
    "pending_inline_approve": '"✅ Phê duyệt"' in src and 'approve_case_plan' in src and 'approve=True' in src,
    "pending_inline_reject": '"↩ Từ chối"' in src and 'approve=False' in src,
    "customer_card_patched": 'v3._card = _customer_card' in src and 'v2._card = _customer_card' in src,
    "customer_form_patched": 'v3._create_form = _customer_create_form' in src and 'v2._create_form = _customer_create_form' in src,
}

bad = [k for k, v in checks.items() if not v]
if bad:
    raise SystemExit(f"PLANNING_FINAL_UX_QA_FAIL {bad}")
print("PLANNING_FINAL_UX_QA_PASS", checks)
