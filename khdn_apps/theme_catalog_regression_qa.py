"""Regression QA for catalog grid lines and the Trecapital/Oaktree Light theme."""
from pathlib import Path
import sys
import tomllib
from streamlit import config as st_config


def main():
    root=Path(__file__).resolve().parent
    cfg_text=(root/'.streamlit'/'config.toml').read_text(encoding='utf-8')
    cfg=tomllib.loads(cfg_text)
    catalog=(root/'catalog_input_fast_patch.py').read_text(encoding='utf-8')
    theme=(root/'install_theme.py').read_text(encoding='utf-8')
    component=(root/'fast_catalog_component'/'index.html').read_text(encoding='utf-8')
    component_py=(root/'fast_catalog_input.py').read_text(encoding='utf-8')
    probe=(root/'theme_probe_component'/'index.html').read_text(encoding='utf-8')

    checks={
        'default_dark': cfg.get('theme',{}).get('base')=='dark',
        'light_exists': 'light' in cfg.get('theme',{}),
        'dark_exists': 'dark' in cfg.get('theme',{}),
        'dark_primary_unchanged': cfg['theme']['dark'].get('primaryColor')=='#6FD6C4',
        'dark_bg_unchanged': cfg['theme']['dark'].get('backgroundColor')=='#0E1F1E',
        'dark_secondary_unchanged': cfg['theme']['dark'].get('secondaryBackgroundColor')=='#17312F',
        'dark_text_unchanged': cfg['theme']['dark'].get('textColor')=='#F4FFFC',
        'light_oaktree_primary': cfg['theme']['light'].get('primaryColor')=='#12362F',
        'light_oaktree_bg': cfg['theme']['light'].get('backgroundColor')=='#F5F1E8',
        'light_oaktree_secondary': cfg['theme']['light'].get('secondaryBackgroundColor')=='#FFFDF8',
        'light_oaktree_text': cfg['theme']['light'].get('textColor')=='#17231F',
        'light_oaktree_border': cfg['theme']['light'].get('borderColor')=='#D7CFBE',
        'streamlit_sees_dark_default': st_config.get_option('theme.base')=='dark',
        'streamlit_sees_light_theme': st_config.get_option('theme.light.backgroundColor')=='#F5F1E8',
        'streamlit_sees_dark_theme': st_config.get_option('theme.dark.backgroundColor')=='#0E1F1E',
        'catalog_header_inline_grid': 'border:1px solid rgba(127,127,127,.70)' in catalog,
        'catalog_cell_inline_grid': 'border:1px solid rgba(127,127,127,.55)' in catalog,
        'catalog_border_collapse': 'border-collapse:collapse' in catalog,
        'catalog_table_is_stable_html': 'st.html(table_html)' in catalog,
        'theme_runtime_no_st_context_api': 'getattr(st.context.theme' not in theme and 'getattr(st.context.theme' not in component_py,
        'light_css_is_scoped': 'html.khdn-light .stApp' in theme and 'html.khdn-light section[data-testid="stSidebar"]' in theme,
        'light_css_oaktree_tokens': '--oak-pine:#12362F' in theme and '--oak-gold:#B68A3A' in theme and '--oak-cream:#F5F1E8' in theme and '--oak-line:#D7CFBE' in theme,
        'light_css_oaktree_sidebar': 'linear-gradient(180deg,#F3EFE4 0%,#FBF8F0 100%)' in theme,
        'light_css_oaktree_buttons': 'background:var(--oak-pine-2)!important' in theme and 'border-color:var(--oak-gold)!important' in theme,
        'light_css_oaktree_inputs': 'background:#fff!important;color:var(--oak-ink)!important' in theme and 'box-shadow:0 0 0 3px rgba(182,138,58,.14)!important' in theme,
        'light_css_oaktree_table': 'html.khdn-light .khdn-catalog-table th' in theme and 'background:#F3EFE4!important' in theme,
        'theme_probe_reports_live_theme': "type:'khdn-theme-sync'" in probe and 'event.data.theme' in probe,
        'theme_probe_zero_rerun': 'streamlit:setComponentValue' not in probe,
        'theme_probe_streamlit_cache_key': 'stActiveTheme-${parent.location.pathname}-v2' in probe,
        'theme_probe_reads_parent_local_storage': 'parent.localStorage.getItem(key)' in probe,
        'theme_probe_parses_light': "selection==='Light'" in probe,
        'theme_probe_parses_dark': "selection==='Dark'" in probe,
        'theme_probe_parses_system': "selection==='System'" in probe,
        'theme_probe_same_window_poll': 'window.setInterval(syncCached,250)' in probe,
        'component_reads_live_render_theme': 'applyTheme(event.data.theme||{})' in component,
        'component_light_oaktree': "body.light input" in component and '#D7CFBE' in component and '#B68A3A' in component and '#0B2A25' in component,
        'component_no_stale_theme_arg': 'themeType=' not in component_py and 'args.themeType' not in component,
        'component_zero_keystroke': "addEventListener('input'" not in component,
        'component_submit_only': "streamlit:setComponentValue" in component and "buttonEl.addEventListener('click',submit)" in component,
    }
    failed=[k for k,v in checks.items() if not v]
    msg='KHDN_THEME_CATALOG_REGRESSION_QA '+repr(checks)
    print(msg,flush=True)
    sys.stderr.write(msg+'\n'); sys.stderr.flush()
    if failed:
        raise SystemExit('FAIL: '+', '.join(failed))


if __name__=='__main__':
    main()
