"""Install V2.14-style Light theme plus a clean selectable Dark theme.

The active theme is read from ``st.context.theme.type`` on each rerun. Light is the
configured default and deliberately mirrors the white V2.14 canvas/sidebar with high
contrast teal navigation. Dark remains available from Streamlit Settings without
forcing dark widget CSS onto Light mode.
"""
from pathlib import Path
import streamlit


def install():
    root = Path(__file__).resolve().parent
    loader = root / "app.py"
    text = loader.read_text(encoding="utf-8")

    start_marker = "# Dark-mode readability + yellow Create actions."
    end_marker = "# Keep the embedded guide available online."
    start = text.find(start_marker)
    end = text.find(end_marker, start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        raise RuntimeError("V2.14 theme installer cannot find runtime CSS span")

    runtime_theme = r'''# V2.14 visual baseline. Light is white/high-contrast; Dark is optional.
try:
    _khdn_theme_type = str(getattr(st.context.theme, "type", "light") or "light").lower()
except Exception:
    _khdn_theme_type = "light"
if _khdn_theme_type not in {"light", "dark"}:
    _khdn_theme_type = "light"

if _khdn_theme_type == "light":
    st.markdown(
        r"""
        <style id="khdn-v214-light-runtime-theme">
        :root{--khdn-bg:#FFFFFF;--khdn-surface:#FFFFFF;--khdn-soft:#F5F9F8;--khdn-text:#163B39;--khdn-muted:#607572;--khdn-primary:#007F78;--khdn-border:#BFD8D2;--khdn-gold:#F4B41A}
        html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:#FFFFFF!important;color:#163B39!important}
        [data-testid="stAppViewContainer"]{background:#FFFFFF!important;background-image:none!important}
        section[data-testid="stSidebar"]{background:#FFFFFF!important;color:#163B39!important;border-right:1px solid #D7E7E3!important;box-shadow:none!important}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] label{color:#163B39!important;-webkit-text-fill-color:#163B39!important}
        .sidebar-user-name{color:#163B39!important}.sidebar-user-role{color:#617572!important}

        /* V2.14 navigation: white idle buttons, teal active button, gold focus border. */
        div[class*="st-key-mainnav_"] button,div[class*="st-key-subnav_"] button,div[class*="st-key-admin_nav_card_"] button{background:#FFFFFF!important;color:#075E58!important;-webkit-text-fill-color:#075E58!important;border:1.5px solid #8BCBC1!important;box-shadow:none!important;text-shadow:none!important}
        div[class*="st-key-mainnav_"] button *,div[class*="st-key-subnav_"] button *,div[class*="st-key-admin_nav_card_"] button *{color:inherit!important;-webkit-text-fill-color:inherit!important}
        div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"],div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#00766F,#009084)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;border-color:#F4B41A!important;box-shadow:0 4px 12px rgba(0,107,104,.13)!important}
        div[class*="st-key-mainnav_"] button:hover,div[class*="st-key-subnav_"] button:hover,div[class*="st-key-admin_nav_card_"] button:hover{background:#F5FBF9!important;border-color:#F4B41A!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important;transform:none!important}

        /* White/light native-looking forms, matching the V2.14 screenshots. */
        [data-testid="stForm"]{background:#FFFFFF!important;border-color:#D5E4E1!important;box-shadow:none!important}
        div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,div[data-testid="stTextArea"] textarea,div[data-baseweb="input"] input,div[data-baseweb="textarea"] textarea,[data-baseweb="select"]>div,[data-baseweb="select"] input,[data-testid="stDateInput"] input,[data-testid="stTimeInput"] input{background:#F4F6F8!important;color:#163B39!important;-webkit-text-fill-color:#163B39!important;border-color:#C7D7D4!important;caret-color:#163B39!important;box-shadow:none!important}
        div[data-testid="stTextInput"] input:focus,div[data-testid="stNumberInput"] input:focus,div[data-testid="stTextArea"] textarea:focus,div[data-baseweb="input"] input:focus,div[data-baseweb="textarea"] textarea:focus{background:#FFFFFF!important;border-color:#00857A!important;box-shadow:0 0 0 1px #00857A!important}
        div[data-testid="stTextInput"] input::placeholder,div[data-testid="stNumberInput"] input::placeholder,div[data-testid="stTextArea"] textarea::placeholder{color:#6E807D!important;-webkit-text-fill-color:#6E807D!important;opacity:1!important}
        [data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],[role="option"]{background:#FFFFFF!important;color:#163B39!important;-webkit-text-fill-color:#163B39!important}
        [role="option"]:hover,[role="option"][aria-selected="true"]{background:#E9F5F2!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important}
        [data-testid="stAlert"],[data-testid="stExpander"],[data-testid="stExpanderDetails"],[data-testid="stMetric"],.tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert{background:#FFFFFF!important;color:#163B39!important;border-color:#D2E2DE!important;box-shadow:none!important}
        [data-testid="stAlert"] *,[data-testid="stExpander"] *,[data-testid="stMetric"] *,.tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:#163B39!important;-webkit-text-fill-color:#163B39!important}
        [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *,.kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail{color:#607572!important;-webkit-text-fill-color:#607572!important}
        [data-testid="stDataFrame"],.stDataFrame{background:#FFFFFF!important;color:#163B39!important;border-color:#D7E4E1!important}

        .task-chip{background:#FFFFFF!important;color:#163B39!important;-webkit-text-fill-color:#163B39!important;border-color:#C9DEDA!important;box-shadow:none!important;text-shadow:none!important}
        .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
        .task-chip.chip-kh{border-left-color:#4B83D1!important}.task-chip.chip-task{border-left-color:#F4B41A!important}.task-chip.chip-value{border-left-color:#2BAE8C!important}.task-chip.chip-time{border-left-color:#E87935!important}.task-chip.chip-support{border-left-color:#8568CF!important}.task-chip.chip-qlkh{border-left-color:#20A5A0!important}.task-chip.chip-status{border-left-color:#E35D7A!important}

        div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;box-shadow:none!important;font-weight:900!important}
        div[class*="st-key-ops_alert_create_"] button *,div[class*="st-key-ops_alert_create_"] button p{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
        </style>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        r"""
        <style id="khdn-clean-dark-runtime-theme">
        :root{--khdn-bg:#0E1F1E;--khdn-surface:#17312F;--khdn-text:#F4FFFC;--khdn-muted:#B7D5D0;--khdn-border:#365A56;--khdn-gold:#F4B41A}
        .task-chip{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border-color:var(--khdn-border)!important;box-shadow:none!important;text-shadow:none!important}
        .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
        .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;border-color:var(--khdn-border)!important}
        div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}
        div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}
        div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;box-shadow:none!important;font-weight:900!important}
        div[class*="st-key-ops_alert_create_"] button *,div[class*="st-key-ops_alert_create_"] button p{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
        </style>
        """,
        unsafe_allow_html=True,
    )


'''
    text = text[:start] + runtime_theme + text[end:]
    loader.write_text(text, encoding="utf-8")

    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    page = index.read_text(encoding="utf-8")
    admin_start = "/* Admin buttons use exactly the same idle/hover colors as work-management cards. */"
    admin_end = "/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */"
    a = page.find(admin_start)
    b = page.find(admin_end, a + 1) if a >= 0 else -1
    if a < 0 or b < 0:
        raise RuntimeError("V2.14 theme installer cannot find Admin color span")
    adaptive_admin = r'''/* Runtime app CSS owns Admin colors for the active Light/Dark theme. */
div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}
div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}

'''
    page = page[:a] + adaptive_admin + page[b:]
    index.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    install()
