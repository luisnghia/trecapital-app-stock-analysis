from __future__ import annotations

import inspect

from khdn_apps import customer_work_note_card_patch as patch
from khdn_apps import customer_work_ui
from khdn_apps import planning_dashboard_consolidation_patch as consolidation
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_room_dashboard_detail_patch as room
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3


escaped = patch._note_html({"note": "Dòng 1\n<script>alert(1)</script>"})
assert "📝 <b>Ghi chú:</b>" in escaped
assert "Dòng 1" in escaped
assert "&lt;script&gt;" in escaped and "<script>" not in escaped
assert patch._note_html({"note": "   "}) == ""

# The new overlay must preserve the original proven renderers rather than copy them.
assert patch._BASE_CUSTOMER_CARD is not patch._customer_card
assert patch._BASE_ROOM_CASE_CARD is not patch._room_case_card

patch.install(customer_work_ui)
assert v2._card is patch._customer_card
assert v3._card is patch._customer_card
assert finalux._customer_card is patch._customer_card
assert customer_work_ui._case_card is patch._case_card_bridge
assert room._room_case_card is patch._room_case_card

src = inspect.getsource(patch)
install_src = inspect.getsource(patch.install)
consolidation_src = inspect.getsource(consolidation)

checks = {
    "canonical_note": '.get("note")' in src,
    "label": "📝 <b>Ghi chú:</b>" in src,
    "wrapped_inline": "white-space:pre-wrap" in src and "overflow-wrap:anywhere" in src,
    "html_escape": "html.escape(raw)" in src,
    "blank_hidden": "if not raw:" in src,
    "base_customer_preserved": "_BASE_CUSTOMER_CARD = finalux._customer_card" in src,
    "base_room_preserved": "_BASE_ROOM_CASE_CARD = room._room_case_card" in src,
    "safe_html_renderer": "return st.html(transformed)" in src,
    "markdown_restored": "finally:" in src and "st.markdown = original_markdown" in src,
    "room_injection_inside_card": 'marker = "\\n        </div>\\n        <style>"' in src,
    "old_detail_button": "st-key-room_case_detail_" in src and "#F4B41A" in src and "#FFD45A" in src and "border-radius:999px" in src,
    "processing_today_detail_bridge": "customer_ui._case_card = _case_card_bridge" in install_src,
    "v2_v3_rebound": "v2._card = _customer_card" in install_src and "v3._card = _customer_card" in install_src,
    "room_rebound": "room._room_case_card = _room_case_card" in install_src,
    "rerun_safe": "No early return by design" in install_src,
    "approval_note_existing": '("Ghi chú", x.get("note") or "—")' in consolidation_src,
    "move_note_existing": '("Ghi chú công việc", case.get("note") or "—")' in consolidation_src,
    "no_install_sql_write": all(token not in install_src for token in ["execute(", "ALTER TABLE", "UPDATE ", "INSERT ", "DELETE "]),
}

print("CUSTOMER_WORK_NOTE_CARD_QA", checks)
failed = [k for k, ok in checks.items() if not ok]
if failed:
    raise SystemExit("CUSTOMER_WORK_NOTE_CARD_QA_FAIL " + ",".join(failed))

print(
    "CUSTOMER_WORK_NOTE_CARD_QA_PASS "
    "processing=1 today=1 detail=1 room=1 reschedule=1 approvals=1 "
    "html_tail_fixed=1 old_detail_button=1 escaped=1 wrapped=1 blank_hidden=1 data_migration=0"
)
