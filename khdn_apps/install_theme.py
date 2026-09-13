"""Install selectable KHDN Dark plus a Trecapital-style Light theme.

Dark is the default from config.toml. Light follows the main Trecapital palette:
#0F766E primary, #F8FAFC canvas, #ECFDF5 secondary surface, #0F172A text.
Native Streamlit inputs/selects/textareas are left theme-driven for responsiveness.
"""
from pathlib import Path
import streamlit


def install():
    root=Path(__file__).resolve().parent
    loader=root/"app.py"
    text=loader.read_text(encoding="utf-8")
    start_marker="# Dark-mode readability + yellow Create actions."
    end_marker="# Keep the embedded guide available online."
    start=text.find(start_marker); end=text.find(end_marker,start+1) if start>=0 else -1
    if start<0 or end<0:
        raise RuntimeError("Theme installer cannot find runtime CSS span")

    runtime_theme=r'''# KHDN runtime themes. Dark default; Light mirrors Trecapital.
try:
    _khdn_theme_type=str(getattr(st.context.theme,"type","dark") or "dark").lower()
except Exception:
    _khdn_theme_type="dark"
if _khdn_theme_type not in {"light","dark"}:
    _khdn_theme_type="dark"

if _khdn_theme_type=="light":
    st.markdown(r"""
    <style id="khdn-trecapital-light-theme">
    :root{--tc-primary:#0F766E;--tc-primary2:#0D9488;--tc-bg:#F8FAFC;--tc-secondary:#ECFDF5;--tc-text:#0F172A;--tc-muted:#64748B;--tc-line:#CBD5E1;--tc-line-strong:#94A3B8;--tc-white:#FFFFFF;--tc-gold:#F4B41A}
    html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],.main,.block-container{background:var(--tc-bg)!important;color:var(--tc-text)!important;background-image:none!important}
    section[data-testid="stSidebar"]{background:var(--tc-secondary)!important;border-right:1px solid var(--tc-line)!important;box-shadow:none!important;color:var(--tc-text)!important}
    section[data-testid="stSidebar"]>div{background:transparent!important}
    h1,h2,h3,h4,h5,h6,[data-testid="stMarkdownContainer"],p,label{color:var(--tc-text)!important;-webkit-text-fill-color:var(--tc-text)!important}
    [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *,.sidebar-user-role,.kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail{color:var(--tc-muted)!important;-webkit-text-fill-color:var(--tc-muted)!important}
    .page-logo-wrap{background:var(--tc-white)!important;border:1px solid var(--tc-line)!important;box-shadow:0 4px 14px rgba(15,118,110,.06)!important}
    .page-hero-card{background:linear-gradient(112deg,#0F766E 0%,#0D9488 78%,#34A77B 118%)!important;color:#fff!important;border:1px solid rgba(255,255,255,.3)!important;box-shadow:0 8px 20px rgba(15,118,110,.14)!important}
    .page-hero-card h1,.page-hero-card h2,.page-hero-card h3,.page-hero-card p,.page-hero-card span{color:#fff!important;-webkit-text-fill-color:#fff!important}
    .sidebar-user-name{color:var(--tc-text)!important;-webkit-text-fill-color:var(--tc-text)!important}.sidebar-user-role{color:var(--tc-muted)!important}
    div[class*="st-key-mainnav_"] button,div[class*="st-key-subnav_"] button,div[class*="st-key-admin_nav_card_"] button{background:var(--tc-white)!important;color:#0F5F59!important;-webkit-text-fill-color:#0F5F59!important;border:1px solid var(--tc-line)!important;box-shadow:none!important;transform:none!important}
    div[class*="st-key-mainnav_"] button:hover,div[class*="st-key-subnav_"] button:hover,div[class*="st-key-admin_nav_card_"] button:hover{background:#F0FDFA!important;border-color:#5EEAD4!important;color:#115E59!important;-webkit-text-fill-color:#115E59!important}
    div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"],div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0F766E,#0D9488)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:2px solid var(--tc-gold)!important;box-shadow:0 4px 12px rgba(15,118,110,.12)!important}
    div[class*="st-key-mainnav_"] button *,div[class*="st-key-subnav_"] button *,div[class*="st-key-admin_nav_card_"] button *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    div.stButton>button,.stDownloadButton>button{background:linear-gradient(135deg,#0F766E,#0D9488)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #0F766E!important;box-shadow:none!important;transform:none!important}
    div.stButton>button *,div.stDownloadButton>button *{color:#fff!important;-webkit-text-fill-color:#fff!important}
    div.stButton>button:hover,.stDownloadButton>button:hover{background:#115E59!important;border-color:#0F766E!important;box-shadow:none!important}
    div[class*="st-key-logout_btn"] button{background:#DC2626!important;border-color:#B91C1C!important;color:#fff!important;-webkit-text-fill-color:#fff!important}
    [data-testid="stForm"],[data-testid="stAlert"],[data-testid="stExpander"],[data-testid="stExpanderDetails"],[data-testid="stMetric"],.tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert{background:var(--tc-white)!important;color:var(--tc-text)!important;border-color:var(--tc-line)!important;box-shadow:none!important}
    [data-testid="stAlert"] *,[data-testid="stExpander"] *,[data-testid="stMetric"] *,.tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:var(--tc-text)!important;-webkit-text-fill-color:var(--tc-text)!important}
    [data-testid="stTabs"] button[aria-selected="true"]{color:#0F766E!important;-webkit-text-fill-color:#0F766E!important;font-weight:850!important}[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background-color:var(--tc-gold)!important}
    .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid var(--tc-line-strong)!important;border-radius:10px;background:var(--tc-white)!important;margin:.45rem 0 1rem;box-shadow:none!important}
    .khdn-catalog-table{width:100%;border-collapse:collapse!important;border-spacing:0!important;font-size:.88rem;color:var(--tc-text)!important;background:var(--tc-white)!important}
    .khdn-catalog-table th{background:var(--tc-secondary)!important;color:#115E59!important;text-align:left;font-weight:850;padding:9px 10px;border:1px solid var(--tc-line)!important;white-space:nowrap}
    .khdn-catalog-table td{padding:8px 10px;border:1px solid var(--tc-line)!important;color:var(--tc-text)!important;background:var(--tc-white)!important;vertical-align:top}
    .task-chip{background:var(--tc-white)!important;color:var(--tc-text)!important;-webkit-text-fill-color:var(--tc-text)!important;border-color:var(--tc-line)!important;box-shadow:none!important;text-shadow:none!important}.task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;font-weight:900!important}div[class*="st-key-ops_alert_create_"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}
    </style>
    """,unsafe_allow_html=True)
else:
    st.markdown(r"""
    <style id="khdn-clean-dark-runtime-theme">
    :root{--khdn-bg:#0E1F1E;--khdn-surface:#17312F;--khdn-text:#F4FFFC;--khdn-border:#4B6A66;--khdn-gold:#F4B41A}
    .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid #4B6A66!important;border-radius:10px;background:#17312F!important;margin:.45rem 0 1rem}.khdn-catalog-table{width:100%;border-collapse:collapse!important;border-spacing:0!important;font-size:.88rem;color:#F4FFFC!important;background:#17312F!important}.khdn-catalog-table th{background:#1B4540!important;color:#F4FFFC!important;text-align:left;font-weight:850;padding:9px 10px;border:1px solid #4B6A66!important;white-space:nowrap}.khdn-catalog-table td{padding:8px 10px;border:1px solid #365A56!important;color:#F4FFFC!important;background:#17312F!important;vertical-align:top}
    .task-chip{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border-color:var(--khdn-border)!important;box-shadow:none!important;text-shadow:none!important}.task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;border-color:var(--khdn-border)!important}
    div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}
    div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;font-weight:900!important}div[class*="st-key-ops_alert_create_"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}
    </style>
    """,unsafe_allow_html=True)


'''
    text=text[:start]+runtime_theme+text[end:]
    loader.write_text(text,encoding="utf-8")

    index=Path(streamlit.__file__).resolve().parent/"static"/"index.html"
    page=index.read_text(encoding="utf-8")
    admin_start="/* Admin buttons use exactly the same idle/hover colors as work-management cards. */"
    admin_end="/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */"
    a=page.find(admin_start); b=page.find(admin_end,a+1) if a>=0 else -1
    if a<0 or b<0:
        raise RuntimeError("Theme installer cannot find Admin color span")
    adaptive_admin='''/* Runtime app CSS owns Admin colors for active Light/Dark theme. */\ndiv[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}\ndiv[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}\n\n'''
    page=page[:a]+adaptive_admin+page[b:]
    index.write_text(page,encoding="utf-8")


if __name__=="__main__":
    install()
