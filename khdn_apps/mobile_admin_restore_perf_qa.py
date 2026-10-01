from __future__ import annotations

from pathlib import Path
import streamlit

from khdn_apps import planning_operational_phase7_patch as phase7

ROOT = Path(__file__).resolve().parent
PATCH = (ROOT / "mobile_admin_restore_perf_patch.py").read_text(encoding="utf-8")
FORM = (ROOT / "fast_client_form_component" / "index.html").read_text(encoding="utf-8")
INSTALLER = (ROOT / "mobile_client_focus_install.py").read_text(encoding="utf-8")
FIX = (ROOT / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")
INDEX = (Path(streamlit.__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")

expected_routes = ["users", "customers", "types", "reasons", "audit", "backup"]
actual_routes = [x[0] for x in phase7._ADMIN_OPTIONS]

checks = {
    "six_admin_routes": actual_routes == expected_routes,
    "restore_uses_phase7_six_nav": "phase7._admin_cards" in PATCH and "_render_six_admin_nav" in PATCH,
    "restore_installed_last": "mobile_admin_restore.install(app_ns, policy, logger)" in FIX
        and FIX.index("mobile_admin_restore.install") > FIX.index("mobile_input_perf.install"),
    "users_lazy_single_form_mode": "system_users_perf_mode_v3" in PATCH
        and "if mode == \"create\"" in PATCH and "Quản lý người dùng hiện có" in PATCH,
    "task_types_lazy_single_form_mode": "system_task_types_perf_mode_v3" in PATCH
        and "system_task_type_create_fast_v6" in PATCH and "system_task_type_edit_fast_v6_" in PATCH,
    "task_type_cross_scope_guard_preserved": "WHERE module_scope=? AND lower(trim(name))=lower(trim(?))" in PATCH,
    "ios_font_16": "font-size:16px" in FORM,
    "no_keyboard_resize_listener": "addEventListener('resize'" not in FORM,
    "no_resize_observer": "ResizeObserver" not in FORM,
    "fixed_form_height_during_typing": "textarea{min-height:82px;resize:none}" in FORM,
    "ios_autocorrect_disabled": "autocorrect','off'" in FORM and "input.spellcheck=false" in FORM,
    "focus_signal_only": "khdn-fast-input-focus" in FORM and "addEventListener('input'" not in FORM,
    "focus_guard_no_polling": "setInterval" not in INSTALLER and "setTimeout" not in INSTALLER,
    "focus_guard_build_installed": 'id="khdn-fast-input-perf"' in INDEX and "khdn-fast-input-active" in INDEX,
    "focus_guard_event_driven": "data.type!=='khdn-fast-input-focus'" in INDEX,
}

failed = [k for k, v in checks.items() if not v]
print("MOBILE_ADMIN_RESTORE_PERF_QA", checks, "routes=" + ",".join(actual_routes), flush=True)
if failed:
    raise SystemExit("FAIL: " + ", ".join(failed))
print("MOBILE_ADMIN_RESTORE_PERF_QA_PASS admin_routes=6 lazy_iframe=1 keyboard_resize_messages=0 focus_guard_polling=0", flush=True)
