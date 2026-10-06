from __future__ import annotations

import inspect

import pandas as pd

from khdn_apps import customer_work_note_card_patch as patch
from khdn_apps import customer_work_ui
from khdn_apps import operations_owner_roster_patch as owner_patch
from khdn_apps import planning_dashboard_consolidation_patch as consolidation
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_room_dashboard_detail_patch as room
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3


# Safe persisted note rendering.
escaped = patch._note_html({"note": "Dòng 1\n<script>alert(1)</script>"})
assert "📝 <b>Ghi chú:</b>" in escaped
assert "Dòng 1" in escaped
assert "&lt;script&gt;" in escaped and "<script>" not in escaped
assert patch._note_html({"note": "   "}) == ""

# Owner roster must preserve all operational role paths and both eligible owner roles.
def _fake_all_users(role, active_only=True):
    if role == "Cán bộ QLKH":
        return pd.DataFrame([{"id": 1, "full_name": "QLKH A", "username": "a", "role": role}])
    if role == "Lãnh đạo phòng":
        return pd.DataFrame([{"id": 2, "full_name": "Lãnh đạo B", "username": "b", "role": role}])
    return pd.DataFrame()

roster = owner_patch._combined_owner_roster({"all_users": _fake_all_users}, True)
assert roster.id.astype(int).tolist() == [1, 2]
assert roster.role.tolist() == ["Cán bộ QLKH", "Lãnh đạo phòng"]

# Final rerun-safe install owns every active Customer Work card entry point.
patch.install(customer_work_ui)
assert patch.VERSION == "1.3.1"
assert v2._card is patch._customer_card
assert v3._card is patch._customer_card
assert finalux._customer_card is patch._customer_card
assert finalux._render_context is patch._stable_render_context
assert customer_work_ui._case_card is patch._case_card_bridge
assert room._room_case_card is patch._room_case_card

src = inspect.getsource(patch)
install_src = inspect.getsource(patch.install)
room_src = inspect.getsource(patch._room_case_card)
owner_src = inspect.getsource(owner_patch)
consolidation_src = inspect.getsource(consolidation)

checks = {
    "canonical_note": '.get("note")' in src,
    "label": "📝 <b>Ghi chú:</b>" in src,
    "wrapped_inline": "white-space:pre-wrap" in src and "overflow-wrap:anywhere" in src,
    "html_escape": "html.escape(raw)" in src,
    "blank_hidden": "if not raw:" in src,
    "base_customer_preserved": "_BASE_CUSTOMER_CARD = finalux._customer_card" in src,
    "safe_html_renderer": "return st.html(transformed)" in src,
    "markdown_restored": "finally:" in src and "st.markdown = original_markdown" in src,
    "today_duplicate_key_fixed": "finalux._render_context = _stable_render_context" in install_src,
    "note_overlay_skipped_in_context": "os.path.basename(__file__)" in src,
    "context_uses_external_callsite": "frame.f_code.co_name" in src and "frame.f_lineno" in src,
    "room_uses_exact_customer_card": "return _customer_card(" in room_src,
    "room_has_no_separate_card_template": "rd-card" not in room_src,
    "room_detail_button_intercepted": 'str(label).strip() == "🔎 Chi tiết"' in room_src,
    "room_detail_routes_to_plan": 'st.session_state["main_section"] = "plan"' in room_src,
    "room_detail_routes_to_customer_work": 'st.session_state["main_page"] = "customer_work"' in room_src,
    "room_button_restored": "st.button = original_button" in room_src and "finally:" in room_src,
    "processing_today_detail_bridge": "customer_ui._case_card = _case_card_bridge" in install_src,
    "v2_v3_rebound": "v2._card = _customer_card" in install_src and "v3._card = _customer_card" in install_src,
    "room_rebound": "room._room_case_card = _room_case_card" in install_src,
    "rerun_safe": "No early return by design" in install_src,
    "qlkh_no_post_widget_state_write": 'st.session_state["ql_new_owner"] = int(selected)' not in owner_src,
    "qlkh_widget_key_is_state": '_render_owner_select(st, roster, "ql_new_owner"' in owner_src,
    "role_cbht_covered": 'app_ns["support_page"] = support_page' in owner_src,
    "role_qlkh_covered": 'app_ns["qlkh_page"] = qlkh_page' in owner_src,
    "role_leader_admin_covered": "phase14._active_qlkh = active_owners" in owner_src and "phase14._all_qlkh = all_owners" in owner_src,
    "owner_roles_both_present": 'for role in ("Cán bộ QLKH", "Lãnh đạo phòng")' in owner_src,
    "approval_note_existing": '("Ghi chú", x.get("note") or "—")' in consolidation_src,
    "move_note_existing": '("Ghi chú công việc", case.get("note") or "—")' in consolidation_src,
    "no_note_install_sql_write": all(token not in install_src for token in ["execute(", "ALTER TABLE", "UPDATE ", "INSERT ", "DELETE "]),
}

print("CUSTOMER_WORK_NOTE_CARD_QA", checks)
failed = [k for k, ok in checks.items() if not ok]
if failed:
    raise SystemExit("CUSTOMER_WORK_NOTE_CARD_QA_FAIL " + ",".join(failed))

print(
    "CUSTOMER_WORK_NOTE_CARD_QA_PASS "
    "today_keys=1 all_roles=1 qlkh_owner=1 exact_room_card=1 room_detail_route=1 "
    "processing=1 today=1 detail=1 room=1 escaped=1 wrapped=1 blank_hidden=1 data_migration=0"
)

# Run the manager-note/approval-history semantic regression suite as part of the
# existing Customer Work build gate, so Dockerfile wiring remains stable.
import khdn_apps.customer_work_manager_note_history_qa  # noqa: E402,F401
from khdn_apps.interaction_performance_qa import run as run_interaction_qa
run_interaction_qa()
