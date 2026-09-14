"""Build-time QA for the KHDN Light/Dark bridge."""
from pathlib import Path
import streamlit


def main() -> None:
    root = Path(__file__).resolve().parent
    loader = (root / "app.py").read_text(encoding="utf-8")
    index = (Path(streamlit.__file__).resolve().parent / "static" / "index.html").read_text(encoding="utf-8")

    checks = {
        "bridge_present": 'id="khdn-live-theme-class"' in index,
        "streamlit_theme_cache_key": 'stActiveTheme-${window.location.pathname}-v2' in index,
        "reads_local_storage": 'window.localStorage.getItem(cacheKey())' in index,
        "parses_light": "selection==='Light'" in index,
        "parses_dark": "selection==='Dark'" in index,
        "parses_system": "selection==='System'" in index,
        "same_window_poll": 'setInterval(syncFromStreamlitPreference,250)' in index,
        "system_listener": "systemQuery.addEventListener('change',onSystemChange)" in index,
        "probe_fallback": "data.type!=='khdn-theme-sync'" in index,
        "no_global_dom_observer": 'new MutationObserver' not in index,
        "light_root_canvas_css": 'html.khdn-light .stApp' in loader,
        "light_sidebar_css": 'html.khdn-light section[data-testid="stSidebar"]' in loader,
        "light_form_css": 'html.khdn-light [data-testid="stForm"]' in loader,
        "light_button_css": 'html.khdn-light div.stButton>button' in loader,
        "light_table_css": 'html.khdn-light div[data-testid="stDataFrame"]' in loader,
    }
    failed = [name for name, ok in checks.items() if not ok]
    print("KHDN_THEME_BRIDGE_QA", checks, flush=True)
    if failed:
        raise RuntimeError("KHDN theme bridge QA failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
