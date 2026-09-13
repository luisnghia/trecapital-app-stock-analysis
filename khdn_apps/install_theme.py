"""Install a V2.14-faithful Light UI plus selectable Dark UI.

Light deliberately keeps native Streamlit inputs/selects/textareas theme-driven instead
of repainting them with broad CSS selectors. This preserves the fast input path while
making the overall app visually match the clean white V2.14 baseline.
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
        raise RuntimeError("V2.14 theme installer cannot find runtime CSS span")

    runtime_theme=r'''# V2.14 visual baseline. Light is white/high-contrast; Dark is optional.
try:
    _khdn_theme_type=str(getattr(st.context.theme,"type","light") or "light").lower()
except Exception:
    _khdn_theme_type="light"
if _khdn_theme_type not in {"light","dark"}:
    _khdn_theme_type="light"

if _khdn_theme_type=="light":
    st.markdown(
        r"""
        <style id="khdn-v214-light-runtime-theme">
        :root{--bidv:#0B7F75;--bidv2:#128C7E;--gold:#F5B21B;--ink:#12302D;--muted:#61726F;--line:#D8E5E2;--pale:#F4FBF8;--thead:#EEF7F4}

        /* V2.14 canvas: pure white main area, pale-green sidebar. */
        html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"],.main,.block-container{background:#FFFFFF!important;color:var(--ink)!important;background-image:none!important}
        [data-testid="stAppViewContainer"]{background:#FFFFFF!important;background-image:none!important}
        section[data-testid="stSidebar"]{background:#F4FBF8!important;border-right:1px solid #D4E7E2!important;box-shadow:none!important;color:var(--ink)!important}
        section[data-testid="stSidebar"]>div{background:transparent!important}

        /* High-contrast typography, while the hero retains white text. */
        h1,h2,h3,h4,h5,h6,[data-testid="stMarkdownContainer"],p,label{color:var(--ink)}
        [data-testid="stMain"] h1,[data-testid="stMain"] h2,[data-testid="stMain"] h3,[data-testid="stMain"] h4,[data-testid="stMain"] p,[data-testid="stMain"] label{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] label{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important}
        .sidebar-user-name{color:var(--ink)!important}.sidebar-user-role{color:var(--muted)!important}
        [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *,.kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail{color:var(--muted)!important;-webkit-text-fill-color:var(--muted)!important}

        /* BIDV brand header. */
        .page-logo-wrap{background:#FFFFFF!important;border-color:#D5E6E2!important;box-shadow:0 8px 22px rgba(11,127,117,.08)!important}
        .page-hero-card{background:linear-gradient(112deg,#0B7F75 0%,#139486 68%,#67A35A 118%)!important;color:#FFFFFF!important;border-color:rgba(255,255,255,.32)!important;box-shadow:0 11px 28px rgba(11,127,117,.16)!important}
        .page-hero-card h1,.page-hero-card h2,.page-hero-card h3,.page-hero-card p,.page-hero-card span{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}

        /* Sidebar/main navigation: white idle, BIDV-green active, gold selected border. */
        div[class*="st-key-mainnav_"] button{background:#FFFFFF!important;color:#075B54!important;-webkit-text-fill-color:#075B54!important;border:1.5px solid #B9D9D3!important;box-shadow:0 3px 10px rgba(11,127,117,.05)!important;transform:none!important}
        div[class*="st-key-mainnav_"] button:hover{background:#F7FCFA!important;border-color:#F5B21B!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important;transform:none!important}
        div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0B7F75,#139486)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;border:2px solid #F5B21B!important;box-shadow:0 6px 15px rgba(11,127,117,.14)!important}
        div[class*="st-key-mainnav_"] button *,div[class*="st-key-mainnav_"] button[kind="primary"] *{color:inherit!important;-webkit-text-fill-color:inherit!important}

        div[class*="st-key-subnav_"] button,div[class*="st-key-admin_nav_card_"] button{background:#FFFFFF!important;color:#075B54!important;-webkit-text-fill-color:#075B54!important;border:1.5px solid #B9D9D3!important;box-shadow:0 3px 10px rgba(11,127,117,.04)!important;transform:none!important}
        div[class*="st-key-subnav_"] button:hover,div[class*="st-key-admin_nav_card_"] button:hover{background:#F8FCFB!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important;border-color:#F5B21B!important;transform:none!important}
        div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0B7F75,#139486)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;border:2px solid #F5B21B!important;box-shadow:0 5px 13px rgba(11,127,117,.13)!important}
        div[class*="st-key-subnav_"] button *,div[class*="st-key-admin_nav_card_"] button *{color:inherit!important;-webkit-text-fill-color:inherit!important}

        /* Tabs/radio navigation use a gold active indicator without repainting native inputs. */
        [data-testid="stTabs"] button[aria-selected="true"]{color:#075B54!important;-webkit-text-fill-color:#075B54!important;font-weight:850!important;border-bottom-color:#F5B21B!important}
        [data-testid="stTabs"] [data-baseweb="tab-highlight"]{background-color:#F5B21B!important}

        /* Main action buttons: BIDV green + white text. */
        div.stButton>button,.stDownloadButton>button{border-radius:999px!important;border:1px solid #0B7F75!important;background:linear-gradient(135deg,#0B7F75,#139486)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;font-weight:780!important;box-shadow:none!important;transform:none!important}
        div.stButton>button *,div.stDownloadButton>button *{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}
        div.stButton>button:hover,.stDownloadButton>button:hover{border-color:#F5B21B!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;box-shadow:0 0 0 3px rgba(245,178,27,.12)!important;transform:none!important}
        div[class*="st-key-logout_btn"] button{background:#E53935!important;border-color:#C62828!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}
        div[class*="st-key-logout_btn"] button *{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}

        /* White surfaces, subtle borders; no broad CSS targets native text/select widgets. */
        [data-testid="stForm"],[data-testid="stAlert"],[data-testid="stExpander"],[data-testid="stExpanderDetails"],[data-testid="stMetric"],.tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert{background:#FFFFFF!important;color:var(--ink)!important;border-color:#D8E5E2!important;box-shadow:none!important}
        [data-testid="stAlert"] *,[data-testid="stExpander"] *,[data-testid="stMetric"] *,.tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important}

        /* Plain catalog tables: white body, very pale green header. */
        .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid #D8E5E2;border-radius:10px;background:#FFFFFF;margin:.45rem 0 1rem;box-shadow:none}
        .khdn-catalog-table{width:100%;border-collapse:collapse;font-size:.88rem;color:var(--ink);background:#FFFFFF}
        .khdn-catalog-table th{background:#EEF7F4;color:#064E47;text-align:left;font-weight:850;padding:9px 10px;border-bottom:1px solid #CFE1DD;white-space:nowrap}
        .khdn-catalog-table td{padding:8px 10px;border-bottom:1px solid #E6EFED;color:var(--ink);vertical-align:top;background:#FFFFFF}
        .khdn-catalog-table tr:last-child td{border-bottom:none}

        .task-chip{background:#FFFFFF!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;border-color:#C9DEDA!important;box-shadow:none!important;text-shadow:none!important}
        .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
        div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F5B21B 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;box-shadow:none!important;font-weight:900!important}
        div[class*="st-key-ops_alert_create_"] button *,div[class*="st-key-ops_alert_create_"] button p{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
        </style>
        """,unsafe_allow_html=True,
    )
else:
    st.markdown(
        r"""
        <style id="khdn-clean-dark-runtime-theme">
        :root{--khdn-bg:#0E1F1E;--khdn-surface:#17312F;--khdn-text:#F4FFFC;--khdn-border:#365A56;--khdn-gold:#F4B41A}
        .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid #365A56;border-radius:10px;background:#17312F;margin:.45rem 0 1rem}.khdn-catalog-table{width:100%;border-collapse:collapse;font-size:.88rem;color:#F4FFFC;background:#17312F}.khdn-catalog-table th{background:#1B4540;color:#F4FFFC;text-align:left;font-weight:850;padding:9px 10px;border-bottom:1px solid #365A56}.khdn-catalog-table td{padding:8px 10px;border-bottom:1px solid #2C4A47;color:#F4FFFC}.khdn-catalog-table tr:last-child td{border-bottom:none}
        .task-chip{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border-color:var(--khdn-border)!important;box-shadow:none!important;text-shadow:none!important}.task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
        .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;border-color:var(--khdn-border)!important}
        div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}
        div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;box-shadow:none!important;font-weight:900!important}div[class*="st-key-ops_alert_create_"] button *,div[class*="st-key-ops_alert_create_"] button p{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
        </style>
        """,unsafe_allow_html=True,
    )


'''
    text=text[:start]+runtime_theme+text[end:]
    loader.write_text(text,encoding="utf-8")

    index=Path(streamlit.__file__).resolve().parent/"static"/"index.html"
    page=index.read_text(encoding="utf-8")
    admin_start="/* Admin buttons use exactly the same idle/hover colors as work-management cards. */"
    admin_end="/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */"
    a=page.find(admin_start); b=page.find(admin_end,a+1) if a>=0 else -1
    if a<0 or b<0:
        raise RuntimeError("V2.14 theme installer cannot find Admin color span")
    adaptive_admin='''/* Runtime app CSS owns Admin colors for active Light/Dark theme. */\ndiv[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}\ndiv[class*="st-key-admin_nav_card_"] button:hover{border-color:#F5B21B!important;transform:none!important}\n\n'''
    page=page[:a]+adaptive_admin+page[b:]
    index.write_text(page,encoding="utf-8")


if __name__=="__main__":
    install()
