"""Deterministic QA for the final zero-keystroke input layer."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
patch = (ROOT / "global_zero_keystroke_patch.py").read_text(encoding="utf-8")
entry = (ROOT / "online_entry.py").read_text(encoding="utf-8")
component = (ROOT / "legacy_fast_form_component" / "index.html").read_text(encoding="utf-8")
focus_guard = (ROOT / "mobile_client_focus_install.py").read_text(encoding="utf-8")

checks = {
    "final_import": "from khdn_apps.global_zero_keystroke_patch import install as _install_global_zero_keystroke" in entry,
    "final_call": "_install_global_zero_keystroke(" in entry,
    "after_weekly_hotfix": entry.rfind("_install_global_zero_keystroke(") > entry.rfind("_install_weekly_priority_policy_hotfix("),
    "rerun_no_early_return": "intentionally has no early return" in patch and "def install(app_ns, policy" in patch,
    "catalog_rebound": "legacy_ui._install_customer_catalog(customer_core, customer_ui, log)" in patch,
    "v2_create_rebound": "v2._create_form = create_form" in patch,
    "v3_create_rebound": "v3._create_form = create_form" in patch,
    "weekfocus_create_rebound": "weekfocus._customer_create_form" in patch,
    "prospect_quick_add_rebound": "prospects.render_quick_add = _fast_quick_add" in patch,
    "customer_create_submit_only": "payload = legacy_fast_form(" in patch and "key=f\"p17_customer_work_create_" in patch,
    "contact_three_rows": "for slot in (1, 2, 3):" in patch,
    "date_field": '"type":"date"' in patch,
    "desktop_three_columns": "columns=3" in patch,
    "component_date_support": "type==='date'?'date'" in component,
    "component_columns_support": "args.columns" in component and "--cols" in component,
    "component_span_support": "f.span" in component and "gridColumn" in component,
    "component_submit_bridge": "form.addEventListener('submit'" in component and "streamlit:setComponentValue" in component,
    "component_no_key_bridge": "addEventListener('input'" not in component and "addEventListener('keyup'" not in component,
    "native_focus_guard": "document.addEventListener('focusin'" in focus_guard and "khdn-fast-input-active" in focus_guard,
    "table_isolation": "contain:layout paint style" in focus_guard,
    "no_business_migration": "data_migration=0" in patch,
}

bad = [k for k, v in checks.items() if not v]
print("GLOBAL_ZERO_KEYSTROKE_QA", checks)
if bad:
    raise SystemExit("GLOBAL_ZERO_KEYSTROKE_QA_FAIL " + ",".join(bad))
print("GLOBAL_ZERO_KEYSTROKE_QA_PASS rerun_safe=1 catalog=1 customer_work=1 prospect=1 native_guard=1")
