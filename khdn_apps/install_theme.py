"""Install a V2.14-faithful Light UI plus selectable Dark UI.

Light deliberately leaves Streamlit form widgets native: V2.14 did not restyle every
input/textarea descendant, and avoiding those broad selectors also keeps text entry
cheap. Only app structure, navigation, cards, and lightweight catalog tables are styled.
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
        :root{--bidv:#0B7F75;--bidv2:#128C7E;--gold:#F5B21B;--ink:#12302D;--muted:#64748B;--line:rgba(11,127,117,.18)}
        html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background:#FFFFFF!important;color:#12302D!important}
        [data-testid="stAppViewContainer"]{background:#FFFFFF!important;background-image:none!important}
        section[data-testid="stSidebar"]{background:linear-gradient(180deg,#EAF7F1 0%,#FFFFFF 74%)!important;border-right:1px solid rgba(11,127,117,.14)!important;box-shadow:none!important;color:#12302D!important}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],section[data-testid="stSidebar"] p,section[data-testid="stSidebar"] span,section[data-testid="stSidebar"] label{color:#12302D!important;-webkit-text-fill-color:#12302D!important}
        .sidebar-user-name{color:#12302D!important}.sidebar-user-role{color:#64748B!important}

        .page-logo-wrap{background:linear-gradient(180deg,#FFFFFF 0%,#F8FFFB 100%)!important;border-color:rgba(11,127,117,.18)!important;box-shadow:0 10px 26px rgba(11,127,117,.10)!important}
        .page-hero-card{background:linear-gradient(135deg,#0B7F75 0%,#128C7E 58%,#7CA34C 112%)!important;color:#FFFFFF!important;border-color:rgba(255,255,255,.28)!important;box-shadow:0 14px 34px rgba(11,127,117,.20)!important}
        .page-hero-card h1,.page-hero-card p{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}

        /* Exact V2.14-style navigation contrast. */
        div[class*="st-key-mainnav_"] button{background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(248,255,251,.96))!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important;border:1.6px solid rgba(11,127,117,.26)!important;box-shadow:0 5px 14px rgba(11,127,117,.06)!important}
        div[class*="st-key-mainnav_"] button:hover{background:linear-gradient(135deg,#F8FFFB,#FFF7E6)!important;border-color:#F5B21B!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important;transform:none!important}
        div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0B7F75,#128C7E)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;border-color:#F5B21B!important;box-shadow:0 9px 20px rgba(11,127,117,.20)!important}
        div[class*="st-key-mainnav_"] button *,div[class*="st-key-mainnav_"] button[kind="primary"] *{color:inherit!important;-webkit-text-fill-color:inherit!important}

        div[class*="st-key-subnav_"] button,div[class*="st-key-admin_nav_card_"] button{background:#FFFFFF!important;color:#0B5F58!important;-webkit-text-fill-color:#0B5F58!important;border:1.6px solid rgba(11,127,117,.28)!important;box-shadow:0 5px 14px rgba(11,127,117,.06)!important}
        div[class*="st-key-subnav_"] button:hover,div[class*="st-key-admin_nav_card_"] button:hover{background:#FFF9EA!important;color:#064E47!important;-webkit-text-fill-color:#064E47!important;border-color:#F5B21B!important;transform:none!important}
        div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0B7F75,#128C7E)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;border-color:#F5B21B!important;box-shadow:0 8px 19px rgba(11,127,117,.18)!important}
        div[class*="st-key-subnav_"] button *,div[class*="st-key-admin_nav_card_"] button *{color:inherit!important;-webkit-text-fill-color:inherit!important}

        /* General actions use V2.14 teal/white contrast. Native inputs remain untouched. */
        div.stButton>button,.stDownloadButton>button{border-radius:999px!important;border:1px solid rgba(11,127,117,.35)!important;background:linear-gradient(135deg,#0B7F75,#139486)!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;font-weight:750!important;box-shadow:none!important}
        div.stButton>button *,div.stDownloadButton>button *{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}
        div.stButton>button:hover,.stDownloadButton>button:hover{border-color:#F5B21B!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;box-shadow:0 0 0 3px rgba(245,178,27,.16)!important}
        div[class*="st-key-logout_btn"] button{background:linear-gradient(135deg,#DC2626,#EF4444)!important;border-color:#B91C1C!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}
        div[class*="st-key-logout_btn"] button *{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}

        [data-testid="stForm"],[data-testid="stAlert"],[data-testid="stExpander"],[data-testid="stExpanderDetails"],[data-testid="stMetric"],.tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert{background:#FFFFFF!important;color:#12302D!important;border-color:#D5E4E1!important;box-shadow:none!important}
        [data-testid="stAlert"] *,[data-testid="stExpander"] *,[data-testid="stMetric"] *,.tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:#12302D!important;-webkit-text-fill-color:#12302D!important}
        [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *,.kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail{color:#64748B!important;-webkit-text-fill-color:#64748B!important}

        /* Lightweight catalog table: plain DOM, no dataframe canvas/event machinery. */
        .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid #D5E4E1;border-radius:11px;background:#FFFFFF;margin:.45rem 0 1rem}
        .khdn-catalog-table{width:100%;border-collapse:collapse;font-size:.88rem;color:#12302D;background:#FFFFFF}
        .khdn-catalog-table th{background:#EEF7F4;color:#064E47;text-align:left;font-weight:850;padding:9px 10px;border-bottom:1px solid #CFE1DD;white-space:nowrap}
        .khdn-catalog-table td{padding:8px 10px;border-bottom:1px solid #E5EFEC;color:#12302D;vertical-align:top}
        .khdn-catalog-table tr:last-child td{border-bottom:none}

        /* Catalog names use the same textarea implementation that is smooth in QLKH notes, but visually compact. */
        div[class*="st-key-catalog_fast_name_"] textarea,div[class*="st-key-catalog_fast_edit_"] textarea{min-height:46px!important;height:46px!important;resize:none!important;line-height:1.35!important}

        .task-chip{background:#FFFFFF!important;color:#12302D!important;-webkit-text-fill-color:#12302D!important;border-color:#C9DEDA!important;box-shadow:none!important;text-shadow:none!important}
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
        .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid #365A56;border-radius:11px;background:#17312F;margin:.45rem 0 1rem}
        .khdn-catalog-table{width:100%;border-collapse:collapse;font-size:.88rem;color:#F4FFFC;background:#17312F}.khdn-catalog-table th{background:#1B4540;color:#F4FFFC;text-align:left;font-weight:850;padding:9px 10px;border-bottom:1px solid #365A56}.khdn-catalog-table td{padding:8px 10px;border-bottom:1px solid #2C4A47;color:#F4FFFC}.khdn-catalog-table tr:last-child td{border-bottom:none}
        div[class*="st-key-catalog_fast_name_"] textarea,div[class*="st-key-catalog_fast_edit_"] textarea{min-height:46px!important;height:46px!important;resize:none!important;line-height:1.35!important}
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
    adaptive_admin='''/* Runtime app CSS owns Admin colors for the active Light/Dark theme. */\ndiv[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}\ndiv[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}\n\n'''
    page=page[:a]+adaptive_admin+page[b:]
    index.write_text(page,encoding="utf-8")


if __name__=="__main__":
    install()
