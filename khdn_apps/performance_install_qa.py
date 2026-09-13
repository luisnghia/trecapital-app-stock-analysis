"""Verify that the built image contains the performance fast path."""
from pathlib import Path
import streamlit


def main():
    root=Path(__file__).resolve().parent
    loader=(root/"app.py").read_text(encoding="utf-8")
    device=(root/"device_login.py").read_text(encoding="utf-8")
    sessions=(root/"device_sessions.py").read_text(encoding="utf-8")
    index=(Path(streamlit.__file__).resolve().parent/"static"/"index.html").read_text(encoding="utf-8")
    checks={
        "loader_perf_patch": "_performance_patch_source" in loader,
        "component_command_gated": "if command:\n        result = _component" in device,
        "device_validation_throttled": "VALIDATE_SECONDS = 30.0" in device,
        "device_schema_once": "_SCHEMA_READY" in sessions and "_ensure_schema(path)" in sessions,
        "global_dom_observer_removed": "new MutationObserver(scheduleGrid).observe(document.documentElement" not in index,
        "grid_observer_filtered": "mutationTouchesGrid" in index and "OPS_GRID_SELECTOR" in index,
    }
    failed=[k for k,v in checks.items() if not v]
    print("KHDN_SPEED_INSTALL_QA",checks,flush=True)
    if failed:
        raise RuntimeError("KHDN speed install QA failed: "+", ".join(failed))


if __name__=="__main__":
    main()
