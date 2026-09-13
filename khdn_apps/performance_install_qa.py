"""Verify built image contains zero-keystroke catalog entry and selectable Dark/Trecapital Light styling."""
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
        "plain_catalog_table": 'class="khdn-catalog-table"' in catalog and 'st.html(table_html)' in catalog,
        "default_dark_theme": '[theme]\nbase = "dark"' in config,
        "trecapital_light_palette": '[theme.light]\nprimaryColor = "#0F766E"\nbackgroundColor = "#F8FAFC"\nsecondaryBackgroundColor = "#ECFDF5"\ntextColor = "#0F172A"' in config,
        "switchable_light_dark": '[theme.light]' in config and '[theme.dark]' in config and '[theme.light.sidebar]' in config and '[theme.dark.sidebar]' in config,
        "runtime_theme_uses_context": 'getattr(st.context.theme,"type","dark")' in loader or 'getattr(st.context.theme, "type", "dark")' in loader,
        "trecapital_light_runtime_css": 'id="khdn-trecapital-light-theme"' in loader and '--tc-primary:#0F766E' in loader and '--tc-bg:#F8FAFC' in loader and '--tc-secondary:#ECFDF5' in loader,
        "catalog_grid_lines_light": '.khdn-catalog-table th' in loader and 'border:1px solid var(--tc-line)!important' in loader,
        "catalog_grid_lines_dark": '.khdn-catalog-table td' in loader and 'border:1px solid #365A56!important' in loader,
        "native_inputs_not_broadly_repainted": '[data-testid="stTextInput"] input' not in loader and '[data-testid="stTextArea"] textarea' not in loader and '[data-baseweb="select"]' not in loader,
        "component_trecapital_light": 'body.light input{background:#FFFFFF;color:#0F172A;border:1px solid #CBD5E1' in component_html and 'body.light button{background:#0F766E' in component_html,
        "component_dark_default": '<body class="dark">' in component_html,
        "clean_dark_runtime_css": 'id="khdn-clean-dark-runtime-theme"' in loader,
        "admin_index_does_not_force_dark": '#173A37' not in index,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_THEME_INSTALL_QA",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN theme install QA failed: "+", ".join(failed))


if __name__=="__main__":
    main()
