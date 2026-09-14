"""Standalone regression QA for the two user-visible issues: catalog grid lines and Light/Dark themes."""
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

    checks={
        'default_dark': cfg.get('theme',{}).get('base')=='dark',
        'light_exists': 'light' in cfg.get('theme',{}),
        'dark_exists': 'dark' in cfg.get('theme',{}),
        'light_trecapital_primary': cfg['theme']['light'].get('primaryColor')=='#0F766E',
        'light_trecapital_bg': cfg['theme']['light'].get('backgroundColor')=='#F8FAFC',
        'light_trecapital_secondary': cfg['theme']['light'].get('secondaryBackgroundColor')=='#ECFDF5',
        'light_trecapital_text': cfg['theme']['light'].get('textColor')=='#0F172A',
        'streamlit_sees_dark_default': st_config.get_option('theme.base')=='dark',
        'streamlit_sees_light_theme': st_config.get_option('theme.light.backgroundColor')=='#F8FAFC',
        'streamlit_sees_dark_theme': st_config.get_option('theme.dark.backgroundColor')=='#0E1F1E',
        'catalog_header_inline_grid': 'border:1px solid rgba(127,127,127,.70)' in catalog,
        'catalog_cell_inline_grid': 'border:1px solid rgba(127,127,127,.55)' in catalog,
        'catalog_border_collapse': 'border-collapse:collapse' in catalog,
        'catalog_table_is_stable_html': 'st.html(table_html)' in catalog,
        'theme_runtime_no_st_context_api': 'getattr(st.context.theme' not in theme and 'getattr(st.context.theme' not in component_py,
        'theme_runtime_does_not_force_canvas': 'html,body,.stApp' not in theme,
        'theme_runtime_neutral_id': 'khdn-native-switchable-theme' in theme,
        'component_reads_live_render_theme': 'applyTheme(event.data.theme||{})' in component,
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
