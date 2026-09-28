from pathlib import Path

ROOT = Path(__file__).resolve().parent
src = (ROOT / "planning_navigation_approval_parity_patch.py").read_text(encoding="utf-8")
hotfix = (ROOT / "weekly_priority_policy_hotfix.py").read_text(encoding="utf-8")

checks = {
    "clear_detail_when_leaving_customer_work": "cw_case_id" in src and "not key.endswith(\"_customer_work\")" in src,
    "today_defensive_reset": "render_today_page" in src and 'session_state.pop("cw_case_id", None)' in src,
    "approval_uses_processing_card": "customer_ui._case_card" in src and "compact=True" in src,
    "approval_note_retained": "Ý kiến phê duyệt" in src,
    "approval_actions_retained": "approve_case_plan" in src and "Phê duyệt" in src and "Từ chối" in src,
    "consolidation_renderer_replaced": "consolidation._render_case_approval_card = render_case_approval_card" in src,
    "nav_parity_installed": "_nav_approval_parity.install" in hotfix,
    "hotfix_version": 'VERSION = "2.1.0"' in hotfix,
}

assert all(checks.values()), checks
print("PLANNING_NAV_APPROVAL_PARITY_QA_PASS", checks)
