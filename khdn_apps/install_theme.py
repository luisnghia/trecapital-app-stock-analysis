"""Install KHDN Light/Dark theming.

Dark mode is intentionally preserved. Light mode copies the institutional visual
language used by the main Trecapital stock-analysis app (ui_oaktree_theme.py):
white surfaces, pine typography, gold focus/selection accents, restrained
shadows, white inputs and strongly contrasted controls.

A zero-height custom component reports Streamlit's *live* active theme to the parent
page. The static shell toggles `html.khdn-light` client-side, so switching Light/Dark
works immediately without relying on a Python rerun or stale st.context.theme state.
"""
from pathlib import Path
import re
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
        raise RuntimeError("Theme installer cannot find runtime CSS span")

    runtime_theme = r'''# KHDN theme runtime. Dark remains exactly on the existing shared path;
# Trecapital/Oaktree overrides activate only when the live client theme is Light.
from khdn_apps.theme_probe import render_theme_probe as _khdn_render_theme_probe
_khdn_render_theme_probe()

st.markdown(r"""
<style id="khdn-native-switchable-theme">
/* ---------- Shared rules: preserve the current Dark appearance ---------- */
.page-hero-card{background:linear-gradient(112deg,#0F766E 0%,#0D9488 78%,#34A77B 118%)!important;color:#fff!important;border:1px solid rgba(127,127,127,.28)!important;box-shadow:0 8px 20px rgba(15,118,110,.14)!important}
.page-hero-card h1,.page-hero-card h2,.page-hero-card h3,.page-hero-card p,.page-hero-card span{color:#fff!important;-webkit-text-fill-color:#fff!important}
.page-logo-wrap{border:1px solid rgba(127,127,127,.32)!important;box-shadow:none!important}

div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"],
div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],
div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{border:2px solid #F4B41A!important;font-weight:850!important;box-shadow:none!important}
div[class*="st-key-mainnav_"] button,div[class*="st-key-subnav_"] button,div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important;transform:none!important}
div[class*="st-key-mainnav_"] button:hover,div[class*="st-key-subnav_"] button:hover,div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}

.task-chip-row{display:flex!important;flex-wrap:wrap!important;align-items:stretch!important;gap:8px!important;margin:.25rem 0 .65rem!important}
.task-chip{background:transparent!important;color:inherit!important;-webkit-text-fill-color:inherit!important;border:1px solid rgba(127,127,127,.42)!important;border-left-width:4px!important;border-radius:10px!important;padding:.48rem .68rem!important;font-weight:800!important;line-height:1.3!important;white-space:normal!important;overflow-wrap:anywhere!important;text-shadow:none!important;box-shadow:none!important}
.task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
.task-chip.chip-kh{border-left-color:#3B82F6!important}.task-chip.chip-task{border-left-color:#F4B41A!important}.task-chip.chip-value{border-left-color:#10B981!important}.task-chip.chip-time{border-left-color:#F97316!important}.task-chip.chip-support{border-left-color:#8B5CF6!important}.task-chip.chip-qlkh{border-left-color:#14B8A6!important}.task-chip.chip-status{border-left-color:#EF476F!important}
.tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert{background:transparent!important;color:inherit!important;border-color:rgba(127,127,127,.35)!important;box-shadow:none!important}
.tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:inherit!important;-webkit-text-fill-color:inherit!important}

.khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid rgba(127,127,127,.70)!important;border-radius:10px;background:transparent!important;margin:.45rem 0 1rem;box-shadow:none!important}
.khdn-catalog-table{width:100%;border-collapse:collapse!important;border-spacing:0!important;font-size:.88rem;color:inherit!important;background:transparent!important}
.khdn-catalog-table th{background:rgba(15,118,110,.10)!important;color:inherit!important;text-align:left;font-weight:850;padding:9px 10px;border:1px solid rgba(127,127,127,.70)!important;white-space:nowrap}
.khdn-catalog-table td{padding:8px 10px;border:1px solid rgba(127,127,127,.55)!important;color:inherit!important;background:transparent!important;vertical-align:top}

div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;font-weight:900!important;box-shadow:none!important}
div[class*="st-key-ops_alert_create_"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}
div[class*="st-key-logout_btn"] button{background:#DC2626!important;border-color:#B91C1C!important;color:#fff!important;-webkit-text-fill-color:#fff!important}

/* ---------- LIGHT ONLY: copied/adapted from Trecapital ui_oaktree_theme.py ---------- */
html.khdn-light{
  color-scheme:light;
  --khdn-input-bg:#FFFFFF;--khdn-input-text:#17231F;--khdn-input-placeholder:#547064;--khdn-input-border:#C9DCD3;
  --oak-pine:#12362F;--oak-pine-2:#0B2A25;--oak-pine-3:#1F4A42;
  --oak-gold:#F4B41A;--oak-gold-soft:#FFF1C2;--oak-cream:#FFFFFF;
  --oak-paper:#FFFFFF;--oak-ink:#17231F;--oak-muted:#47665A;
  --oak-line:#C9DCD3;--oak-red:#A43A2F;--oak-green:#16624F;
}
html.khdn-light .stApp{
  background:linear-gradient(90deg,rgba(18,54,47,.030) 0 1px,transparent 1px) 0 0/72px 72px,
             linear-gradient(180deg,var(--oak-cream) 0%,#FFFFFF 18%,#FFFFFF 72%)!important;
  color:var(--oak-ink)!important;
}
html.khdn-light [data-testid="stAppViewContainer"],
html.khdn-light [data-testid="stMain"],
html.khdn-light [data-testid="stMainBlockContainer"],
html.khdn-light .main,html.khdn-light .block-container{background:transparent!important;color:var(--oak-ink)!important}
html.khdn-light .main .block-container{max-width:none!important;width:100%!important;padding-top:1.05rem!important;padding-bottom:2.6rem!important}
html.khdn-light [data-testid="stHeader"]{background:rgba(255,255,255,.96)!important;border-bottom:1px solid rgba(201,220,211,.72)!important}
html.khdn-light h1,html.khdn-light h2,html.khdn-light h3,html.khdn-light h4,html.khdn-light h5,html.khdn-light h6{color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;letter-spacing:-.015em!important}
html.khdn-light p,html.khdn-light li,html.khdn-light label,html.khdn-light .stMarkdown,html.khdn-light [data-testid="stMarkdownContainer"]{color:var(--oak-ink)!important;-webkit-text-fill-color:var(--oak-ink)!important}
html.khdn-light [data-testid="stCaptionContainer"],html.khdn-light [data-testid="stCaptionContainer"] *,html.khdn-light .small-muted{color:var(--oak-muted)!important;-webkit-text-fill-color:var(--oak-muted)!important}

html.khdn-light section[data-testid="stSidebar"]{background:linear-gradient(180deg,#F0F7F3 0%,#FFFFFF 100%)!important;border-right:1px solid var(--oak-line)!important;box-shadow:12px 0 28px rgba(18,54,47,.045)!important;color:var(--oak-pine-2)!important}
html.khdn-light section[data-testid="stSidebar"]>div{background:transparent!important}
html.khdn-light section[data-testid="stSidebar"] h1,html.khdn-light section[data-testid="stSidebar"] h2,html.khdn-light section[data-testid="stSidebar"] h3,html.khdn-light section[data-testid="stSidebar"] label,html.khdn-light section[data-testid="stSidebar"] p,html.khdn-light section[data-testid="stSidebar"] span{color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important}
html.khdn-light section[data-testid="stSidebar"] hr,html.khdn-light section[data-testid="stSidebar"] [data-testid="stDivider"]{border-color:rgba(18,54,47,.18)!important}

html.khdn-light .page-logo-wrap{height:auto!important;min-height:124px!important;display:flex!important;align-items:center!important;justify-content:center!important;border-radius:18px!important;background:linear-gradient(135deg,#FFF7E6 0%,#EAF7F1 100%)!important;border:2.6px solid #0B7F75!important;border-bottom:4px solid rgba(6,78,71,.38)!important;box-shadow:0 12px 30px rgba(11,127,117,.16)!important}
html.khdn-light .page-logo-wrap:hover{background:linear-gradient(135deg,#FFE8A3 0%,#D8F3E4 100%)!important;border-color:#F5B21B!important;box-shadow:0 16px 36px rgba(245,178,27,.20),0 10px 22px rgba(11,127,117,.16)!important;transform:translateY(-1px)!important}
html.khdn-light .page-hero-card{position:relative!important;padding:28px 34px!important;border-radius:4px!important;background:linear-gradient(135deg,var(--oak-pine-2) 0%,var(--oak-pine) 70%,#294E44 100%)!important;border:1px solid rgba(255,255,255,.12)!important;border-left:6px solid var(--oak-gold)!important;color:#fff!important;box-shadow:0 20px 48px rgba(18,54,47,.22)!important;overflow:hidden!important}
html.khdn-light .page-hero-card:after{content:"";position:absolute;inset:auto 0 0 0;height:3px;background:linear-gradient(90deg,var(--oak-gold),rgba(255,255,255,0))}
html.khdn-light .page-hero-card h1,html.khdn-light .page-hero-card h2,html.khdn-light .page-hero-card h3,html.khdn-light .page-hero-card p,html.khdn-light .page-hero-card span{color:#fff!important;-webkit-text-fill-color:#fff!important}

html.khdn-light [data-testid="stForm"],html.khdn-light [data-testid="stMetric"],html.khdn-light [data-testid="stAlert"],html.khdn-light [data-testid="stExpander"],html.khdn-light [data-testid="stExpanderDetails"],html.khdn-light .tre-section,html.khdn-light .kpi-card,html.khdn-light .perf-period,html.khdn-light .perf-trend-card,html.khdn-light .annual-benchmark-note,html.khdn-light .bidv-table-wrap,html.khdn-light .section-note,html.khdn-light .open-list-note,html.khdn-light .task-pick-alert{border-radius:5px!important;background:#FFFFFF!important;color:var(--oak-ink)!important;border:1px solid var(--oak-line)!important;box-shadow:0 10px 22px rgba(18,54,47,.055)!important}
html.khdn-light [data-testid="stMetric"]{padding:16px 18px!important;min-height:82px!important}
html.khdn-light [data-testid="stMetricValue"]{color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;font-size:1.34rem!important;font-weight:780!important}
html.khdn-light [data-testid="stMetricLabel"] p{color:var(--oak-muted)!important;-webkit-text-fill-color:var(--oak-muted)!important}
html.khdn-light [data-testid="stAlert"] *,html.khdn-light [data-testid="stExpander"] *,html.khdn-light .tre-section *,html.khdn-light .kpi-card *,html.khdn-light .perf-period *,html.khdn-light .perf-trend-card *,html.khdn-light .annual-benchmark-note *,html.khdn-light .section-note *,html.khdn-light .open-list-note *,html.khdn-light .task-pick-alert *{color:var(--oak-ink)!important;-webkit-text-fill-color:var(--oak-ink)!important}

html.khdn-light div.stButton>button,html.khdn-light div[data-testid="stButton"] button,html.khdn-light div[data-testid="stDownloadButton"] button,html.khdn-light button[kind="primary"],html.khdn-light button[kind="secondary"],html.khdn-light button[kind="formSubmit"],html.khdn-light button[data-testid^="baseButton"]{border-radius:4px!important;border:1px solid var(--oak-pine-2)!important;background:var(--oak-pine-2)!important;background-color:var(--oak-pine-2)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;font-weight:820!important;letter-spacing:.01em!important;box-shadow:none!important;transform:none!important}
html.khdn-light div.stButton>button *,html.khdn-light div[data-testid="stButton"] button *,html.khdn-light div[data-testid="stDownloadButton"] button *,html.khdn-light button[kind="primary"] *,html.khdn-light button[kind="secondary"] *,html.khdn-light button[kind="formSubmit"] *,html.khdn-light button[data-testid^="baseButton"] *{color:#fff!important;fill:#fff!important;stroke:#fff!important;-webkit-text-fill-color:#fff!important}
html.khdn-light div.stButton>button:hover,html.khdn-light div[data-testid="stButton"] button:hover,html.khdn-light div[data-testid="stDownloadButton"] button:hover,html.khdn-light button[kind="primary"]:hover,html.khdn-light button[kind="secondary"]:hover,html.khdn-light button[kind="formSubmit"]:hover,html.khdn-light button[data-testid^="baseButton"]:hover{background:#fff!important;background-color:#fff!important;color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;border-color:var(--oak-gold)!important;box-shadow:inset 0 -3px 0 var(--oak-gold),0 8px 18px rgba(18,54,47,.08)!important}
html.khdn-light div.stButton>button:hover *,html.khdn-light div[data-testid="stButton"] button:hover *,html.khdn-light div[data-testid="stDownloadButton"] button:hover *,html.khdn-light button[kind="primary"]:hover *,html.khdn-light button[kind="secondary"]:hover *,html.khdn-light button[kind="formSubmit"]:hover *,html.khdn-light button[data-testid^="baseButton"]:hover *{color:var(--oak-pine-2)!important;fill:var(--oak-pine-2)!important;stroke:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important}
html.khdn-light button:disabled{background:#EFF5F1!important;border-color:#C9DCD3!important;color:#47665A!important;-webkit-text-fill-color:#47665A!important;opacity:1!important}
html.khdn-light button:disabled *{color:#47665A!important;fill:#47665A!important;stroke:#47665A!important;-webkit-text-fill-color:#47665A!important}

/* Navigation: paper idle state, pine active state, gold selection rule. */
html.khdn-light div[class*="st-key-mainnav_"] button,html.khdn-light div[class*="st-key-subnav_"] button,html.khdn-light div[class*="st-key-admin_nav_card_"] button{background:#FFFFFF!important;color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;border:1px solid var(--oak-line)!important;border-radius:5px!important;box-shadow:0 5px 13px rgba(18,54,47,.055)!important}
html.khdn-light div[class*="st-key-mainnav_"] button *,html.khdn-light div[class*="st-key-subnav_"] button *,html.khdn-light div[class*="st-key-admin_nav_card_"] button *{color:inherit!important;fill:currentColor!important;stroke:currentColor!important;-webkit-text-fill-color:inherit!important}
html.khdn-light div[class*="st-key-mainnav_"] button[kind="primary"],html.khdn-light div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"],html.khdn-light div[class*="st-key-subnav_"] button[kind="primary"],html.khdn-light div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],html.khdn-light div[class*="st-key-admin_nav_card_"] button[kind="primary"],html.khdn-light div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,var(--oak-pine-2) 0%,var(--oak-green) 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:2px solid var(--oak-gold)!important;box-shadow:0 9px 22px rgba(18,54,47,.15)!important}
html.khdn-light div[class*="st-key-mainnav_"] button[kind="primary"] *,html.khdn-light div[class*="st-key-subnav_"] button[kind="primary"] *,html.khdn-light div[class*="st-key-admin_nav_card_"] button[kind="primary"] *{color:#fff!important;-webkit-text-fill-color:#fff!important;fill:#fff!important;stroke:#fff!important}

/* Operational cards: institutional paper cards instead of a dark dashboard wall. */
html.khdn-light div[class*="st-key-ops_alert_idle_"] button{background:#FFFFFF!important;color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;border:1px solid var(--oak-line)!important;border-left:4px solid var(--oak-green)!important;box-shadow:0 8px 18px rgba(18,54,47,.055)!important}
html.khdn-light div[class*="st-key-ops_alert_idle_"] button *{color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;fill:var(--oak-pine-2)!important;stroke:var(--oak-pine-2)!important}
html.khdn-light div[class*="st-key-ops_alert_hot_"] button{background:linear-gradient(180deg,#FFF8E6 0%,#FFFFFF 100%)!important;color:#12362F!important;-webkit-text-fill-color:#12362F!important;border:1px solid rgba(182,138,58,.48)!important;border-left:5px solid var(--oak-gold)!important;box-shadow:0 10px 24px rgba(182,138,58,.10)!important}
html.khdn-light div[class*="st-key-ops_alert_hot_"] button *{color:#12362F!important;-webkit-text-fill-color:#12362F!important;fill:#12362F!important;stroke:#12362F!important}
html.khdn-light div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#12362F!important;-webkit-text-fill-color:#12362F!important;border:2px solid #D89A00!important;border-radius:5px!important;font-weight:900!important;box-shadow:0 8px 18px rgba(182,138,58,.14)!important}
html.khdn-light div[class*="st-key-ops_alert_create_"] button *{color:#12362F!important;-webkit-text-fill-color:#12362F!important;fill:#12362F!important;stroke:#12362F!important}
html.khdn-light div[class*="st-key-logout_btn"] button{background:#A43A2F!important;border-color:#873028!important;color:#fff!important;-webkit-text-fill-color:#fff!important}
html.khdn-light div[class*="st-key-logout_btn"] button *{color:#fff!important;-webkit-text-fill-color:#fff!important;fill:#fff!important;stroke:#fff!important}

/* Inputs and BaseWeb menus: exact paper/line/gold-focus language from Trecapital. */
html.khdn-light div[data-baseweb="select"]>div,html.khdn-light div[data-baseweb="input"]>div,html.khdn-light div[data-baseweb="textarea"]>div,html.khdn-light textarea,html.khdn-light input{border-radius:4px!important;border-color:var(--oak-line)!important;background:#fff!important;color:var(--oak-ink)!important;-webkit-text-fill-color:var(--oak-ink)!important;caret-color:var(--oak-ink)!important}
html.khdn-light div[data-baseweb="select"]>div:focus-within,html.khdn-light div[data-baseweb="input"]>div:focus-within,html.khdn-light div[data-baseweb="textarea"]>div:focus-within,html.khdn-light textarea:focus,html.khdn-light input:focus{border-color:var(--oak-gold)!important;box-shadow:0 0 0 3px rgba(182,138,58,.14)!important;outline:none!important}
html.khdn-light input::placeholder,html.khdn-light textarea::placeholder{color:#547064!important;-webkit-text-fill-color:#547064!important;opacity:1!important}
html.khdn-light [data-baseweb="popover"],html.khdn-light [data-baseweb="menu"],html.khdn-light [role="listbox"],html.khdn-light [role="option"]{background:#FFFFFF!important;color:var(--oak-ink)!important;-webkit-text-fill-color:var(--oak-ink)!important}
html.khdn-light [role="option"]:hover,html.khdn-light [role="option"][aria-selected="true"]{background:#F0F7F3!important;color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important}

/* Tabs from the Trecapital Insights/Strategies treatment. */
html.khdn-light div[data-testid="stTabs"]{margin-top:14px!important;margin-bottom:18px!important}
html.khdn-light div[data-testid="stTabs"] div[data-baseweb="tab-list"],html.khdn-light div[data-testid="stTabs"] div[role="tablist"]{gap:6px!important;min-height:58px!important;padding:8px!important;margin:12px 0 22px!important;background:#fff!important;border:1px solid var(--oak-line)!important;border-radius:5px!important;box-shadow:0 10px 22px rgba(18,54,47,.055)!important}
html.khdn-light div[data-testid="stTabs"] button[data-baseweb="tab"],html.khdn-light div[data-testid="stTabs"] button[role="tab"]{min-height:44px!important;height:44px!important;padding:0 18px!important;border-radius:3px!important;border:1.8px solid rgba(182,138,58,.42)!important;border-bottom:4px solid rgba(18,54,47,.32)!important;background:linear-gradient(135deg,#FFF6D8 0%,#EAF5EC 100%)!important;color:var(--oak-pine-2)!important;-webkit-text-fill-color:var(--oak-pine-2)!important;font-size:15px!important;font-weight:760!important;box-shadow:0 5px 13px rgba(18,54,47,.07)!important}
html.khdn-light div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],html.khdn-light div[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{background:linear-gradient(135deg,var(--oak-pine-2) 0%,var(--oak-green) 72%,var(--oak-gold) 132%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border-color:var(--oak-gold)!important;border-bottom-color:var(--oak-gold)!important;box-shadow:0 9px 22px rgba(18,54,47,.18)!important}
html.khdn-light div[data-testid="stTabs"] button[aria-selected="true"] *{color:#fff!important;-webkit-text-fill-color:#fff!important}
html.khdn-light div[data-baseweb="tab-highlight"],html.khdn-light div[data-baseweb="tab-border"]{display:none!important}

/* Tables/dataframes and custom catalog table. */
html.khdn-light div[data-testid="stDataFrame"],html.khdn-light div[data-testid="stDataEditor"]{border-radius:5px!important;overflow:hidden!important;border:1px solid var(--oak-line)!important;box-shadow:0 10px 22px rgba(18,54,47,.05)!important;background:#fff!important}
html.khdn-light div[data-testid="stDataFrame"] [role="columnheader"],html.khdn-light div[data-testid="stDataEditor"] [role="columnheader"]{background:#F0F7F3!important;color:var(--oak-pine-2)!important;font-weight:820!important;border-bottom:1px solid var(--oak-line)!important}
html.khdn-light .khdn-catalog-table-wrap{border:1px solid var(--oak-line)!important;border-radius:5px!important;background:#fff!important;box-shadow:0 10px 22px rgba(18,54,47,.05)!important}
html.khdn-light .khdn-catalog-table{color:var(--oak-ink)!important;background:#fff!important}
html.khdn-light .khdn-catalog-table th{background:#F0F7F3!important;color:var(--oak-pine-2)!important;border:1px solid var(--oak-line)!important;font-weight:820!important}
html.khdn-light .khdn-catalog-table td{background:#fff!important;color:var(--oak-ink)!important;border:1px solid var(--oak-line)!important}
html.khdn-light .khdn-catalog-table tr:hover td{background:#FFFFFF!important}

html.khdn-light .task-chip{background:#FFFFFF!important;color:var(--oak-ink)!important;-webkit-text-fill-color:var(--oak-ink)!important;border-color:var(--oak-line)!important;box-shadow:0 6px 14px rgba(18,54,47,.04)!important}
html.khdn-light .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}

@media(max-width:900px){html.khdn-light .page-hero-card{padding:22px 24px!important}html.khdn-light .page-logo-wrap{min-height:92px!important}html.khdn-light div[data-testid="stTabs"] button[role="tab"]{width:100%!important;justify-content:flex-start!important}}
@media(max-width:700px){.task-chip-row{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}.task-chip{font-size:.78rem!important;padding:.42rem .52rem!important;min-width:0!important}.task-chip.chip-kh,.task-chip.chip-status{grid-column:1/-1!important}}
@media(max-width:430px){.task-chip-row{grid-template-columns:1fr!important}.task-chip.chip-kh,.task-chip.chip-status{grid-column:auto!important}}
</style>
""",unsafe_allow_html=True)


'''
    light_controls = (root / "light_controls.css").read_text(encoding="utf-8")
    runtime_theme = runtime_theme.replace("</style>", light_controls + "\n</style>", 1)
    # online_entry imports app once, then calls app() on each Streamlit rerun.
    # Emit the theme through inject_css(), which app() calls every time, so
    # cached module imports cannot remove the CSS or the live theme probe.
    import textwrap
    runtime_theme = (
        "_khdn_base_inject_css = inject_css\n"
        "def inject_css():\n"
        "    _khdn_base_inject_css()\n"
        + textwrap.indent(runtime_theme, "    ")
    )
    text = text[:start] + runtime_theme + text[end:]
    loader.write_text(text, encoding="utf-8")

    # Remove the old hard-dark Admin palette from Streamlit's static shell and
    # install a client listener for the authoritative live theme probe.
    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    page = index.read_text(encoding="utf-8")
    admin_start = "/* Admin buttons use exactly the same idle/hover colors as work-management cards. */"
    admin_end = "/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */"
    a = page.find(admin_start)
    b = page.find(admin_end, a + 1) if a >= 0 else -1
    if a < 0 or b < 0:
        raise RuntimeError("Theme installer cannot find Admin color span")
    adaptive_admin = '''/* Admin colors follow active Streamlit theme. */\ndiv[class*="st-key-admin_nav_card_"] button{box-shadow:none!important;transform:none!important}\ndiv[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}\n\n'''
    page = page[:a] + adaptive_admin + page[b:]

    page = re.sub(r'<script id="khdn-live-theme-class">.*?</script>', '', page, flags=re.S)
    theme_bridge = r'''
<script id="khdn-live-theme-class">
(()=>{
  const root=document.documentElement;
  const apply=(base)=>{
    const light=String(base||'').toLowerCase()==='light';
    root.classList.toggle('khdn-light',light);
    root.classList.toggle('khdn-dark',!light);
    root.dataset.khdnTheme=light?'light':'dark';
  };
  /* Dark is the configured default. The live probe replaces it as soon as
     Streamlit reports the actual user-selected theme. */
  apply('dark');
  window.addEventListener('message',event=>{
    const data=event.data;
    if(!data||data.type!=='khdn-theme-sync') return;
    const base=String(data.base||'').toLowerCase();
    if(base!=='light'&&base!=='dark') return;
    apply(base);
  });
})();
</script>
'''
    if "</head>" not in page:
        raise RuntimeError("Streamlit index has no head for live theme bridge")
    page = page.replace("</head>", theme_bridge + "</head>", 1)
    index.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    install()
