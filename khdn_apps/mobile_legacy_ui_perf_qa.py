"""Build-time regression checks for the legacy-UI mobile performance release."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATCH = (ROOT / "mobile_legacy_ui_perf_patch.py").read_text(encoding="utf-8")
FIX = (ROOT / "planning_operational_phase10_fix.py").read_text(encoding="utf-8")
FORM = (ROOT / "legacy_fast_form_component" / "index.html").read_text(encoding="utf-8")
BRIDGE = (ROOT / "legacy_fast_form.py").read_text(encoding="utf-8")
FOCUS = (ROOT / "mobile_client_focus_install.py").read_text(encoding="utf-8")
MOBILE = (ROOT / "mobile_input_performance_patch.py").read_text(encoding="utf-8")
RUNTIME = (ROOT / "appwide_input_performance_runtime.py").read_text(encoding="utf-8")
AUTO = (ROOT / "auto_remember_login_patch.py").read_text(encoding="utf-8")

checks = {
    "six_routes_source": "phase7._ADMIN_OPTIONS" in PATCH,
    "admin_three_rows_two_cols": "range(0, len(options), 2)" in PATCH and "st.columns(2" in PATCH,
    "admin_mobile_grid_css": "grid-template-columns:repeat(2,minmax(0,1fr))" in PATCH,
    "phase7_global_nav_replaced": "phase7._admin_cards = _admin_cards_2x3" in PATCH,
    "task_table_always_visible": PATCH.find('#### Danh sách loại công việc') < PATCH.find('### Tạo loại công việc'),
    "task_create_then_edit": PATCH.find('### Tạo loại công việc') < PATCH.find('### Sửa loại công việc'),
    "task_cross_scope_duplicate_allowed": "WHERE module_scope=? AND lower(trim(name))=lower(trim(?))" in PATCH,
    "task_no_create_manage_toggle": "system_task_types_perf_mode" not in PATCH,
    "customer_stage_table_retained": '["Thứ tự", "Mục công việc", "SLA (giờ)", "Hoàn tất", "Trạng thái"]' in PATCH,
    "customer_stage_old_labels": all(x in PATCH for x in ["Tên mục công việc", "Thứ tự", "SLA cảnh báo (giờ)", "Đây là bước kết thúc quy trình", "Đang sử dụng"]),
    "customer_stage_submit_only": "cw_stage_legacy_fast_p16_" in PATCH and "legacy_fast_form(" in PATCH,
    "customer_category_submit_only": "cw_cat_legacy_fast_p16_" in PATCH,
    "customer_table_contained": "contain:layout paint style" in PATCH and "content-visibility:auto" in PATCH,
    "data_calls_preserved": all(x in PATCH for x in ["save_stage_catalog(", "delete_stage_catalog(", "save_important_category(", "delete_important_category("]),
    "no_install_data_migration": "data_migration=0" in PATCH and "ALTER TABLE" not in PATCH and "DROP TABLE" not in PATCH,
    "legacy_bridge_submit_dedupe": "_khdn_legacy_fast_form_seen_" in BRIDGE,
    "legacy_component_ios_16": "font-size:16px" in FORM,
    "legacy_component_number_stepper": "number-control" in FORM and "step-button" in FORM and "clampNumber" in FORM,
    "legacy_component_no_resize_listener": "addEventListener('resize'" not in FORM and "ResizeObserver" not in FORM,
    "legacy_component_no_input_bridge": "addEventListener('input'" not in FORM,
    "legacy_component_submit_only": "streamlit:setComponentValue" in FORM and "form.addEventListener('submit'" in FORM,
    "native_focus_guard": "document.addEventListener('focusin'" in FOCUS and "document.addEventListener('focusout'" in FOCUS,
    "native_ios_16_guard": "font-size:16px!important" in FOCUS,
    "native_table_isolation": "content-visibility:auto" in FOCUS and "contain-intrinsic-size" in FOCUS,
    "focus_guard_no_polling": "setInterval(" not in FOCUS and "requestAnimationFrame(" not in FOCUS,
    "installed_last": "mobile_legacy_ui_perf.install(" in FIX and FIX.find("mobile_legacy_ui_perf.install(") > FIX.find("mobile_admin_restore.install("),
    "fix_version_19": 'VERSION = "1.9.0"' in FIX,

    # App-wide runtime activation: the previous release compiled/QA'd the fast
    # layers but did not put them on online_entry's live execution path.
    "runtime_hook_called_last": (
        "appwide_input_performance_runtime" in AUTO
        and "_install_appwide_input_performance(ns, ns.get(\"LOGGER\"))" in AUTO
    ),
    "runtime_stack_order": (
        RUNTIME.find("mobile_input.install(") >= 0
        and RUNTIME.find("mobile_admin.install(") > RUNTIME.find("mobile_input.install(")
        and RUNTIME.find("legacy_ui.install(") > RUNTIME.find("mobile_admin.install(")
        and RUNTIME.find("_install_task_type_scope_sort(app_ns, log)") > RUNTIME.find("legacy_ui.install(")
    ),
    "runtime_stage_and_important_category_submit_only": (
        "submit_only_stages=1" in RUNTIME
        and "submit_only_important_categories=1" in RUNTIME
        and "cw_stage_legacy_fast_p16_" in PATCH
        and "cw_cat_legacy_fast_p16_" in PATCH
    ),
    "runtime_disables_periodic_refresh": (
        "_disable_periodic_server_refresh(app_ns,log)" in MOBILE
        and "periodic_refresh=0" in RUNTIME
    ),
    "runtime_all_heavy_catalog_fast_paths": all(
        token in MOBILE
        for token in [
            "zero_keystroke_users=1",
            "zero_keystroke_task_types=1",
            "zero_keystroke_stages=1",
            "zero_keystroke_focus=1",
        ]
    ),
    "task_type_sorted_by_scope_then_name": (
        "CASE module_scope" in RUNTIME
        and "WHEN 'PLAN' THEN 0 WHEN 'OPS' THEN 1 ELSE 2 END" in RUNTIME
        and "lower(trim(name)), id" in RUNTIME
    ),
    "task_type_sort_rewired_all_routes": all(
        token in RUNTIME
        for token in [
            "legacy_ui._render_system_task_types_legacy_fast = sorted_renderer",
            "mobile_input._render_system_task_types_fast = sorted_renderer",
            "mobile_admin._render_system_task_types_fast = sorted_renderer",
            "admin_hotfix._render_system_task_types =",
        ]
    ),
    "runtime_source_compiles": bool(compile(RUNTIME, "appwide_input_performance_runtime.py", "exec")),
    "auto_source_compiles": bool(compile(AUTO, "auto_remember_login_patch.py", "exec")),
}

print("MOBILE_LEGACY_UI_PERF_QA", checks)
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("MOBILE_LEGACY_UI_PERF_QA_FAIL " + ",".join(failed))
print(
    "MOBILE_LEGACY_UI_PERF_QA_PASS admin_grid=2x3 task_table_old_order=1 "
    "customer_stage_submit_only=1 customer_focus_submit_only=1 native_focus_guard=1 "
    "runtime_appwide=1 task_type_scope_sort=PLAN,OPS data_migration=0"
)
