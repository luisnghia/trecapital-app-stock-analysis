"""Install theme-neutral KHDN styling on top of native Streamlit Light/Dark themes.

Dark remains the default in config.toml. Users can switch between the configured Light
and Dark themes from Streamlit Settings. Runtime CSS deliberately avoids Python-side
st.context.theme detection because it can be stale; colors that must follow the active
theme are left to Streamlit itself. Only stable BIDV/Trecapital brand accents are added.
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

    runtime_theme=r'''# Theme-neutral runtime CSS. Native Streamlit theme owns canvas,
# sidebar, typography, widgets, forms and popovers in both Light and Dark modes.
st.markdown(r"""
<style id="khdn-native-switchable-theme">
/* Brand hero remains stable in both themes. */
.page-hero-card{background:linear-gradient(112deg,#0F766E 0%,#0D9488 78%,#34A77B 118%)!important;color:#fff!important;border:1px solid rgba(127,127,127,.28)!important;box-shadow:0 8px 20px rgba(15,118,110,.14)!important}
.page-hero-card h1,.page-hero-card h2,.page-hero-card h3,.page-hero-card p,.page-hero-card span{color:#fff!important;-webkit-text-fill-color:#fff!important}
.page-logo-wrap{border:1px solid rgba(127,127,127,.32)!important;box-shadow:none!important}

/* Selected navigation is obvious in both modes without forcing a theme background. */
div[class*="st-key-mainnav_"] button[kind="primary"],div[class*="st-key-mainnav_"] button[data-testid="stBaseButton-primary"],
div[class*="st-key-subnav_"] button[kind="primary"],div[class*="st-key-subnav_"] button[data-testid="stBaseButton-primary"],
div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{border:2px solid #F4B41A!important;font-weight:850!important;box-shadow:none!important}
div[class*="st-key-mainnav_"] button,div[class*="st-key-subnav_"] button,div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important;transform:none!important}
div[class*="st-key-mainnav_"] button:hover,div[class*="st-key-subnav_"] button:hover,div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}

/* Custom KHDN containers inherit the active Streamlit theme. */
.task-chip-row{display:flex!important;flex-wrap:wrap!important;align-items:stretch!important;gap:8px!important;margin:.25rem 0 .65rem!important}
.task-chip{background:transparent!important;color:inherit!important;-webkit-text-fill-color:inherit!important;border:1px solid rgba(127,127,127,.42)!important;border-left-width:4px!important;border-radius:10px!important;padding:.48rem .68rem!important;font-weight:800!important;line-height:1.3!important;white-space:normal!important;overflow-wrap:anywhere!important;text-shadow:none!important;box-shadow:none!important}
.task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
.task-chip.chip-kh{border-left-color:#3B82F6!important}.task-chip.chip-task{border-left-color:#F4B41A!important}.task-chip.chip-value{border-left-color:#10B981!important}.task-chip.chip-time{border-left-color:#F97316!important}.task-chip.chip-support{border-left-color:#8B5CF6!important}.task-chip.chip-qlkh{border-left-color:#14B8A6!important}.task-chip.chip-status{border-left-color:#EF476F!important}
.tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert{background:transparent!important;color:inherit!important;border-color:rgba(127,127,127,.35)!important;box-shadow:none!important}
.tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:inherit!important;-webkit-text-fill-color:inherit!important}

/* Catalog tables: CSS duplicates the intrinsic inline grid as a safe fallback. */
.khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid rgba(127,127,127,.70)!important;border-radius:10px;background:transparent!important;margin:.45rem 0 1rem;box-shadow:none!important}
.khdn-catalog-table{width:100%;border-collapse:collapse!important;border-spacing:0!important;font-size:.88rem;color:inherit!important;background:transparent!important}
.khdn-catalog-table th{background:rgba(15,118,110,.10)!important;color:inherit!important;text-align:left;font-weight:850;padding:9px 10px;border:1px solid rgba(127,127,127,.70)!important;white-space:nowrap}
.khdn-catalog-table td{padding:8px 10px;border:1px solid rgba(127,127,127,.55)!important;color:inherit!important;background:transparent!important;vertical-align:top}

/* Create cards remain the intentional yellow CTA. */
div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;border:2px solid #D89A00!important;font-weight:900!important;box-shadow:none!important}
div[class*="st-key-ops_alert_create_"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}
div[class*="st-key-logout_btn"] button{background:#DC2626!important;border-color:#B91C1C!important;color:#fff!important;-webkit-text-fill-color:#fff!important}

@media (max-width:700px){.task-chip-row{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}.task-chip{font-size:.78rem!important;padding:.42rem .52rem!important;min-width:0!important}.task-chip.chip-kh,.task-chip.chip-status{grid-column:1/-1!important}}
@media (max-width:430px){.task-chip-row{grid-template-columns:1fr!important}.task-chip.chip-kh,.task-chip.chip-status{grid-column:auto!important}}
</style>
""",unsafe_allow_html=True)


'''
    text=text[:start]+runtime_theme+text[end:]
    loader.write_text(text,encoding="utf-8")

    # Remove the old hard-dark Admin palette from Streamlit's static shell.
    index=Path(streamlit.__file__).resolve().parent/"static"/"index.html"
    page=index.read_text(encoding="utf-8")
    admin_start="/* Admin buttons use exactly the same idle/hover colors as work-management cards. */"
    admin_end="/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */"
    a=page.find(admin_start); b=page.find(admin_end,a+1) if a>=0 else -1
    if a<0 or b<0:
        raise RuntimeError("Theme installer cannot find Admin color span")
    adaptive_admin='''/* Admin colors follow active Streamlit theme. */\ndiv[class*="st-key-admin_nav_card_"] button{box-shadow:none!important;transform:none!important}\ndiv[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}\n\n'''
    page=page[:a]+adaptive_admin+page[b:]
    index.write_text(page,encoding="utf-8")


if __name__=="__main__":
    install()
