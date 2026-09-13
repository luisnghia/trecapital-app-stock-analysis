"""Verify built image contains KHDN input fast path, lazy catalogs, and callback guard."""
from pathlib import Path
import streamlit


def main():
    root=Path(__file__).resolve().parent
    loader=(root/"app.py").read_text(encoding="utf-8")
    device=(root/"device_login.py").read_text(encoding="utf-8")
    sessions=(root/"device_sessions.py").read_text(encoding="utf-8")
    perf=(root/"performance_patch.py").read_text(encoding="utf-8")
    batch=(root/"input_batch_patch.py").read_text(encoding="utf-8")
    index=(Path(streamlit.__file__).resolve().parent/"static"/"index.html").read_text(encoding="utf-8")
    checks={
        "loader_perf_patch": "_performance_patch_source" in loader,
        "loader_input_batch_patch": "_input_batch_patch_source" in loader,
        "component_command_gated": "if command:\n        result = _component" in device,
        "device_validation_throttled": "VALIDATE_SECONDS = 30.0" in device,
        "device_schema_once": "_SCHEMA_READY" in sessions and "_ensure_schema(path)" in sessions,
        "global_dom_observer_removed": "new MutationObserver(scheduleGrid).observe(document.documentElement" not in index,
        "grid_observer_filtered": "mutationTouchesGrid" in index and "OPS_GRID_SELECTOR" in index,
        "grid_observer_paused_while_typing": "khdn-typing-mode" in index and "gridObserver=new MutationObserver" in index,
        "typing_focus_script": 'id="khdn-typing-fastpath"' in index and "focusin" in index and "focusout" in index,
        "typing_animation_pause": 'body.khdn-typing-mode div[class*="st-key-ops_alert_hot_"] button' in index and "animation:none!important" in index,
        "legacy_draft_callback_rewriter_removed": "draft_widgets = [" not in perf and "for old_widget, new_widget, label in draft_widgets" not in perf,
        "callback_guard_present": "Invalid Streamlit string callback detected" in perf and "Invalid Streamlit string callback detected after input batching" in batch,
        "qlkh_batch_patch_present": "qlkh_create_payload_form" in batch,
        "support_batch_patch_present": "support_create_payload_form" in batch,
        "reason_lazy_catalog_present": "reason_catalog_kind_fast" in batch and "Danh sách / chỉnh sửa" in batch,
        "task_type_lazy_catalog_present": "task_type_catalog_mode_fast" in batch and "Danh sách / trạng thái" in batch,
        "catalog_fast_form_present": 'enter_to_submit=False' in batch,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_INPUT_FAST_INSTALL_QA",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN input fast install QA failed: "+", ".join(failed))


if __name__=="__main__":
    main()
