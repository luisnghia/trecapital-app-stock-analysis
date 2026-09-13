"""Install the exact V2.14 Light stylesheet plus an isolated optional Dark layer.

The Light stylesheet is copied byte-for-byte from the user-provided V2.14 app.py into
``v214_exact_light.html``. We do not broadly repaint native inputs/selects/textareas.
Only a tiny compatibility layer styles components that did not exist in V2.14.
"""
from pathlib import Path
import streamlit


def install():
    root=Path(__file__).resolve().parent
    exact_light=root/"v214_exact_light.html"
    if not exact_light.exists():
        raise RuntimeError("Exact V2.14 Light stylesheet snapshot is missing")

    loader=root/"app.py"
    text=loader.read_text(encoding="utf-8")
    start_marker="# Dark-mode readability + yellow Create actions."
    end_marker="# Keep the embedded guide available online."
    start=text.find(start_marker); end=text.find(end_marker,start+1) if start>=0 else -1
    if start<0 or end<0:
        raise RuntimeError("V2.14 theme installer cannot find runtime CSS span")

    runtime_theme=r'''# Exact V2.14 Light CSS. Dark remains optional and isolated.
try:
    _khdn_theme_type=str(getattr(st.context.theme,"type","light") or "light").lower()
except Exception:
    _khdn_theme_type="light"
if _khdn_theme_type not in {"light","dark"}:
    _khdn_theme_type="light"

if _khdn_theme_type=="light":
    _v214_exact_css=__import__("pathlib").Path(__file__).resolve().parent.joinpath("v214_exact_light.html").read_text(encoding="utf-8")
    st.markdown(_v214_exact_css,unsafe_allow_html=True)
    # Compatibility only for post-V2.14 components. Values intentionally reuse
    # the exact V2.14 palette; native input/select/textarea widgets are untouched.
    st.markdown(r"""
    <style id="khdn-v214-postcompat">
    div[class*="st-key-admin_nav_card_"] button{min-height:43px!important;border-radius:999px!important;border:1.6px solid rgba(11,127,117,.25)!important;background:#fff!important;color:#0B5F58!important;font-size:.88rem!important;font-weight:850!important;box-shadow:0 5px 14px rgba(11,127,117,.06)!important;padding:0 15px!important}
    div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F5B21B!important;color:#064E47!important;background:#FFF9EA!important}
    div[class*="st-key-admin_nav_card_"] button[kind="primary"],div[class*="st-key-admin_nav_card_"] button[data-testid="stBaseButton-primary"]{background:linear-gradient(135deg,#0B7F75,#128C7E)!important;color:white!important;border-color:#F5B21B!important;box-shadow:0 8px 19px rgba(11,127,117,.20)!important}
    .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid rgba(11,127,117,.12);border-radius:13px;background:#fff;margin:.45rem 0 1rem}
    .khdn-catalog-table{width:100%;border-collapse:collapse;font-size:.82rem;color:#12302d;background:#fff}
    .khdn-catalog-table th{background:#F0F8F5;color:#064E47;text-align:left;font-weight:900;padding:9px 10px;border-bottom:1px solid rgba(11,127,117,.14);white-space:nowrap}
    .khdn-catalog-table td{padding:8px 10px;border-bottom:1px solid rgba(11,127,117,.09);color:#12302d;background:#fff;vertical-align:top}
    .khdn-catalog-table tr:last-child td{border-bottom:none}
    div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F5B21B 0%,#FFD45A 100%)!important;color:#2B2410!important;border:2px solid #D89A00!important;font-weight:900!important}
    div[class*="st-key-ops_alert_create_"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}
    </style>
    """,unsafe_allow_html=True)
else:
    st.markdown(r"""
    <style id="khdn-clean-dark-runtime-theme">
    :root{--khdn-bg:#0E1F1E;--khdn-surface:#17312F;--khdn-text:#F4FFFC;--khdn-border:#365A56;--khdn-gold:#F4B41A}
    .khdn-catalog-table-wrap{width:100%;overflow:auto;border:1px solid #365A56;border-radius:10px;background:#17312F;margin:.45rem 0 1rem}.khdn-catalog-table{width:100%;border-collapse:collapse;font-size:.88rem;color:#F4FFFC;background:#17312F}.khdn-catalog-table th{background:#1B4540;color:#F4FFFC;text-align:left;font-weight:850;padding:9px 10px;border-bottom:1px solid #365A56}.khdn-catalog-table td{padding:8px 10px;border-bottom:1px solid #2C4A47;color:#F4FFFC}.khdn-catalog-table tr:last-child td{border-bottom:none}
    .task-chip{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border-color:var(--khdn-border)!important;box-shadow:none!important;text-shadow:none!important}.task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;border-color:var(--khdn-border)!important}
    div[class*="st-key-admin_nav_card_"] button{box-shadow:none!important}div[class*="st-key-admin_nav_card_"] button:hover{border-color:#F4B41A!important;transform:none!important}
    div[class*="st-key-ops_alert_create_"] button{background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;color:#2B2410!important;border:2px solid #D89A00!important;font-weight:900!important}div[class*="st-key-ops_alert_create_"] button *{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important}
    </style>
    """,unsafe_allow_html=True)


'''
    text=text[:start]+runtime_theme+text[end:]
    loader.write_text(text,encoding="utf-8")

    # Remove legacy index-level Admin color forcing; runtime Light/Dark owns it.
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
