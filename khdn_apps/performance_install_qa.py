"""Verify built image keeps Dark intact and installs the Trecapital/Oaktree Light UI."""
from pathlib import Path
import streamlit
from streamlit import config as st_config


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
    light_controls=(root/"light_controls.css").read_text(encoding="utf-8")
    probe_py=(root/"theme_probe.py").read_text(encoding="utf-8")
    probe_html=(root/"theme_probe_component"/"index.html").read_text(encoding="utf-8")
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
        "theme_bridge_reasserts_light_class": "root.classList.contains(light?'khdn-light':'khdn-dark')" in index,
        "typing_focus_listener_removed": 'id="khdn-typing-fastpath"' not in index,
        "sidebar_permanent_will_change_removed": ";will-change:transform,width" not in index and "will-change:transform,width;" not in index,
        "legacy_draft_callback_rewriter_removed": "draft_widgets = [" not in perf and "for old_widget, new_widget, label in draft_widgets" not in perf,
        "callback_guard_present": "Invalid Streamlit string callback detected" in perf and "Invalid Streamlit string callback detected after input batching" in batch,
        "qlkh_batch_patch_present": "qlkh_create_payload_form" in batch,
        "support_batch_patch_present": "support_create_payload_form" in batch,
        "catalog_component_declared": "khdn_fast_catalog_input" in component_py and "declare_component" in component_py,
        "catalog_component_no_input_messages": "inputEl.addEventListener('input'" not in component_html and "streamlit:setComponentValue" in component_html,
        "catalog_component_submit_only": "buttonEl.addEventListener('click',submit)" in component_html and "event.key==='Enter'" in component_html,
        "catalog_component_reads_live_theme": "event.data.theme" in component_html and "applyTheme(event.data.theme||{})" in component_html,
        "catalog_component_light_oaktree": "body.light input" in component_html and "#C9DCD3" in component_html and "#F4B41A" in component_html and "#0B2A25" in component_html,
        "catalog_component_no_python_theme_hint": "themeType=" not in component_py and "args.themeType" not in component_html,
        "task_type_fast_component_present": 'key="catalog_submit_only_task_type"' in catalog and 'Tên công việc mới' in catalog,
        "reason_fast_component_present": 'catalog_submit_only_reason_' in catalog and 'Tên nhóm nguyên nhân mới' in catalog,
        "plain_catalog_table": 'class="khdn-catalog-table"' in catalog and 'st.html(table_html)' in catalog,
        "catalog_grid_intrinsic_header": 'border:1px solid rgba(127,127,127,.70)' in catalog,
        "catalog_grid_intrinsic_cells": 'border:1px solid rgba(127,127,127,.55)' in catalog,
        "default_dark_theme_file": '[theme]\nbase = "dark"' in config,
        "dark_palette_unchanged": '[theme.dark]\nprimaryColor = "#6FD6C4"\nbackgroundColor = "#0E1F1E"\nsecondaryBackgroundColor = "#17312F"\ntextColor = "#F4FFFC"\nborderColor = "#365A56"' in config,
        "trecapital_oaktree_light_palette_file": '[theme.light]\nprimaryColor = "#12362F"\nbackgroundColor = "#FFFFFF"\nsecondaryBackgroundColor = "#FFFFFF"\ntextColor = "#17231F"\nborderColor = "#C9DCD3"' in config,
        "switchable_light_dark_file": '[theme.light]' in config and '[theme.dark]' in config and '[theme.light.sidebar]' in config and '[theme.dark.sidebar]' in config,
        "streamlit_recognizes_default_dark": st_config.get_option("theme.base") == "dark",
        "streamlit_recognizes_light_bg": st_config.get_option("theme.light.backgroundColor") == "#FFFFFF",
        "streamlit_recognizes_light_primary": st_config.get_option("theme.light.primaryColor") == "#12362F",
        "streamlit_recognizes_dark_bg": st_config.get_option("theme.dark.backgroundColor") == "#0E1F1E",
        "runtime_theme_css_present": 'id="khdn-native-switchable-theme"' in loader,
        "runtime_does_not_use_st_context_theme": "st.context.theme" not in loader,
        "runtime_light_is_class_scoped": "html.khdn-light .stApp" in loader and "html.khdn-light section[data-testid=\"stSidebar\"]" in loader,
        "qlkh_slider_light_data_theme_fallback": 'html[data-khdn-theme="light"]' in light_controls,
        "qlkh_slider_react_aria_track": "react-aria-SliderTrack" in light_controls,
        "qlkh_slider_react_aria_thumb": "react-aria-SliderThumb" in light_controls,
        "qlkh_slider_red": "#C62828!important" in light_controls,
        "qlkh_slider_both_themes_scope": 'html :is([class*="st-key-q_"],[class*="st-key-p_"])' in light_controls,
        "qlkh_slider_dark_red": 'accent-color:#C62828!important' in light_controls and 'background:#C62828!important' in light_controls,
        "runtime_oaktree_tokens": "--oak-pine:#12362F" in loader and "--oak-gold:#F4B41A" in loader and "--oak-cream:#FFFFFF" in loader and "--oak-line:#C9DCD3" in loader,
        "runtime_oaktree_buttons": "html.khdn-light div.stButton>button" in loader and "background:var(--oak-pine-2)!important" in loader,
        "runtime_oaktree_inputs": "html.khdn-light div[data-baseweb=\"select\"]>div" in loader and "border-color:var(--oak-gold)!important" in loader,
        "runtime_oaktree_tables": "html.khdn-light .khdn-catalog-table th" in loader and "background:#F0F7F3!important" in loader,
        "runtime_catalog_grid_fallback": 'border:1px solid rgba(127,127,127,.70)!important' in loader and 'border:1px solid rgba(127,127,127,.55)!important' in loader,
        "theme_probe_declared": "khdn_theme_probe" in probe_py and "declare_component" in probe_py,
        "theme_probe_no_component_value": "streamlit:setComponentValue" not in probe_html,
        "theme_probe_reports_live_theme": "event.data.theme" in probe_html and "type:'khdn-theme-sync'" in probe_html,
        "theme_probe_rendered_before_app": "_khdn_render_theme_probe()" in loader,
        "static_theme_bridge_present": 'id="khdn-live-theme-class"' in index and "khdn-theme-sync" in index and "classList.toggle('khdn-light'" in index,
        "admin_index_does_not_force_dark": '#173A37' not in index,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_THEME_INSTALL_QA",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN theme install QA failed: "+", ".join(failed))


if __name__=="__main__":
    main()

# Railway deployment marker: keep branch-head deployments observable after connector ref updates.
