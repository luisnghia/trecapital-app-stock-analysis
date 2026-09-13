"""Verify built image contains KHDN fast input and adaptive Light/Dark styling."""
from pathlib import Path
import streamlit


def main():
    root=Path(__file__).resolve().parent
    loader=(root/"app.py").read_text(encoding="utf-8")
    device=(root/"device_login.py").read_text(encoding="utf-8")
    sessions=(root/"device_sessions.py").read_text(encoding="utf-8")
    perf=(root/"performance_patch.py").read_text(encoding="utf-8")
    batch=(root/"input_batch_patch.py").read_text(encoding="utf-8")
    config=(root/".streamlit"/"config.toml").read_text(encoding="utf-8")
    index=(Path(streamlit.__file__).resolve().parent/"static"/"index.html").read_text(encoding="utf-8")
    checks={
        "loader_perf_patch": "_performance_patch_source" in loader,
        "loader_input_batch_patch": "_input_batch_patch_source" in loader,
        "component_command_gated": "if command:\n        result = _component" in device,
        "device_validation_throttled": "VALIDATE_SECONDS = 30.0" in device,
        "device_schema_once": "_SCHEMA_READY" in sessions and "_ensure_schema(path)" in sessions,
        "global_dom_observer_removed": "new MutationObserver(scheduleGrid).observe(document.documentElement" not in index,
        "grid_observer_filtered": "mutationTouchesGrid" in index and "OPS_GRID_SELECTOR" in index,
        "grid_observer_mobile_only": "if(mobile()&&!gridWatching)" in index and "gridObserver.disconnect()" in index,
        "grid_observer_paused_while_typing": "khdn-typing-mode" in index and "gridObserver=new MutationObserver" in index,
        "typing_focus_script": 'id="khdn-typing-fastpath"' in index and "focusin" in index and "focusout" in index,
        "typing_animation_pause_all_screens": 'body.khdn-typing-mode div[class*="st-key-ops_alert_hot_"] button' in index and '@media(max-width:768px){\n  body.khdn-typing-mode' not in index,
        "typing_widget_transitions_off": 'body.khdn-typing-mode [data-testid="stTextInput"] *' in index and 'transition:none!important' in index,
        "sidebar_permanent_will_change_removed": ";will-change:transform,width" not in index,
        "legacy_draft_callback_rewriter_removed": "draft_widgets = [" not in perf and "for old_widget, new_widget, label in draft_widgets" not in perf,
        "callback_guard_present": "Invalid Streamlit string callback detected" in perf and "Invalid Streamlit string callback detected after input batching" in batch,
        "qlkh_batch_patch_present": "qlkh_create_payload_form" in batch,
        "support_batch_patch_present": "support_create_payload_form" in batch,
        "v214_task_type_flow_present": 'with st.form("new_type"):' in batch and 'Tên công việc mới' in batch and 'V2.14-style task type manager' in batch,
        "v214_reason_flow_present": 'reason_catalog_kind_v214' in batch and 'with st.form(f"reason_create_{kind}"):' in batch and 'V2.14-style reason manager' in batch,
        "default_light_theme": '[theme]\nbase = "light"' in config,
        "switchable_light_dark_themes": '[theme.light]' in config and '[theme.dark]' in config and '[theme.light.sidebar]' in config and '[theme.dark.sidebar]' in config,
        "adaptive_runtime_theme": 'id="khdn-adaptive-runtime-theme"' in loader and '--khdn-surface:var(--secondary-background-color)' in loader and '--khdn-text:var(--text-color)' in loader,
        "hard_dark_widget_css_removed": 'div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input' not in loader,
        "adaptive_admin_navigation": 'Admin navigation follows the active Streamlit Light/Dark theme.' in index and '#173A37' not in index,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_V214_THEME_INSTALL_QA",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN V2.14/theme install QA failed: "+", ".join(failed))


if __name__=="__main__":
    main()
