"""Verify built image contains zero-keystroke catalog entry and V2.14 Light/Dark styling."""
from pathlib import Path
import streamlit


def main():
    root=Path(__file__).resolve().parent
    loader=(root/"app.py").read_text(encoding="utf-8")
    device=(root/"device_login.py").read_text(encoding="utf-8")
    sessions=(root/"device_sessions.py").read_text(encoding="utf-8")
    perf=(root/"performance_patch.py").read_text(encoding="utf-8")
    batch=(root/"input_batch_patch.py").read_text(encoding="utf-8")
    catalog=(root/"catalog_input_fast_patch.py").read_text(encoding="utf-8")
    component_py=(root/"fast_catalog_input.py").read_text(encoding="utf-8")
    component_html=(root/"fast_catalog_component"/"index.html").read_text(encoding="utf-8")
    config=(root/".streamlit"/"config.toml").read_text(encoding="utf-8")
    index=(Path(streamlit.__file__).resolve().parent/"static"/"index.html").read_text(encoding="utf-8")
    checks={
        "loader_perf_patch": "_performance_patch_source" in loader,
        "loader_input_batch_patch": "_input_batch_patch_source" in loader,
        "loader_catalog_patch": "_catalog_input_fast_patch_source" in loader,
        "component_command_gated": "if command:\n        result = _component" in device,
        "device_validation_throttled": "VALIDATE_SECONDS = 30.0" in device,
        "device_schema_once": "_SCHEMA_READY" in sessions and "_ensure_schema(path)" in sessions,
        "global_dom_observer_removed": "new MutationObserver(scheduleGrid).observe(document.documentElement" not in index,
        "grid_observer_operational_only": "hasOpsGrid" in index and "gridObserver.disconnect()" in index,
        "typing_focus_listener_removed": 'id="khdn-typing-fastpath"' not in index,
        "sidebar_permanent_will_change_removed": ";will-change:transform,width" not in index and "will-change:transform,width;" not in index,
        "legacy_draft_callback_rewriter_removed": "draft_widgets = [" not in perf and "for old_widget, new_widget, label in draft_widgets" not in perf,
        "callback_guard_present": "Invalid Streamlit string callback detected" in perf and "Invalid Streamlit string callback detected after input batching" in batch,
        "qlkh_batch_patch_present": "qlkh_create_payload_form" in batch,
        "support_batch_patch_present": "support_create_payload_form" in batch,
        "catalog_component_declared": "khdn_fast_catalog_input" in component_py and "declare_component" in component_py,
        "catalog_component_no_input_messages": "inputEl.addEventListener('input'" not in component_html and "streamlit:setComponentValue" in component_html,
        "catalog_component_submit_only": "buttonEl.addEventListener('click',submit)" in component_html and "event.key==='Enter'" in component_html,
        "task_type_fast_component_present": 'key="catalog_submit_only_task_type"' in catalog and 'Tên công việc mới' in catalog,
        "reason_fast_component_present": 'catalog_submit_only_reason_' in catalog and 'Tên nhóm nguyên nhân mới' in catalog,
        "plain_catalog_table": 'class="khdn-catalog-table"' in catalog,
        "default_light_theme": '[theme]\nbase = "light"' in config,
        "v214_light_palette": '[theme.light]\nprimaryColor = "#0B7F75"\nbackgroundColor = "#FFFFFF"\nsecondaryBackgroundColor = "#F6F8F8"\ntextColor = "#12302D"' in config,
        "v214_sidebar_palette": '[theme.light.sidebar]\nprimaryColor = "#0B7F75"\nbackgroundColor = "#F4FBF8"\nsecondaryBackgroundColor = "#FFFFFF"' in config,
        "switchable_light_dark_themes": '[theme.light]' in config and '[theme.dark]' in config and '[theme.light.sidebar]' in config and '[theme.dark.sidebar]' in config,
        "runtime_theme_uses_context": 'getattr(st.context.theme,"type","light")' in loader or 'getattr(st.context.theme, "type", "light")' in loader,
        "v214_light_runtime_css": 'id="khdn-v214-light-runtime-theme"' in loader and 'background:#FFFFFF!important' in loader and '#F4FBF8' in loader,
        "v214_gold_selected_border": 'border:2px solid #F5B21B!important' in loader,
        "v214_plain_white_table": '.khdn-catalog-table td' in loader and 'background:#FFFFFF' in loader and '#EEF7F4' in loader,
        "native_inputs_not_broadly_repainted": '[data-testid="stTextInput"] input' not in loader and '[data-testid="stTextArea"] textarea' not in loader and '[data-baseweb="select"]' not in loader,
        "clean_dark_runtime_css": 'id="khdn-clean-dark-runtime-theme"' in loader,
        "admin_index_does_not_force_dark": '#173A37' not in index,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_V214_GOLDEN_INSTALL_QA",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN V2.14 golden install QA failed: "+", ".join(failed))


if __name__=="__main__":
    main()
