"""Install adaptive KHDN styling after production/performance patches.

Streamlit owns widget colors for both light and dark themes. This installer removes the
old hard-dark widget overrides from the runtime loader and keeps only KHDN-specific
semantic styling (status chips and yellow Create actions). It also makes Admin nav cards
follow the active Streamlit theme instead of forcing dark colors.
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
        raise RuntimeError("Adaptive theme installer cannot find runtime CSS span")

    adaptive = r'''# Adaptive BIDV styling. Native Streamlit owns all form/input/table colors so
# switching Light/Dark is immediate and typing does not carry a large CSS override set.
st.markdown(
    r"""
    <style id="khdn-adaptive-runtime-theme">
    :root{
      --khdn-bg:var(--background-color);
      --khdn-surface:var(--secondary-background-color);
      --khdn-text:var(--text-color);
      --khdn-primary:var(--primary-color);
      --khdn-border:rgba(79,132,123,.36);
      --khdn-gold:#F4B41A;
    }

    .task-chip-row{display:flex!important;flex-wrap:wrap!important;align-items:stretch!important;gap:8px!important;margin:.25rem 0 .65rem!important}
    .task-chip{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border:1px solid var(--khdn-border)!important;border-left-width:4px!important;border-radius:10px!important;padding:.48rem .68rem!important;font-weight:800!important;line-height:1.3!important;white-space:normal!important;overflow-wrap:anywhere!important;text-shadow:none!important;box-shadow:none!important}
    .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    .task-chip.chip-kh{border-left-color:#4B83D1!important}.task-chip.chip-task{border-left-color:#F4B41A!important}.task-chip.chip-value{border-left-color:#2BAE8C!important}.task-chip.chip-time{border-left-color:#E87935!important}.task-chip.chip-support{border-left-color:#8568CF!important}.task-chip.chip-qlkh{border-left-color:#20A5A0!important}.task-chip.chip-status{border-left-color:#E35D7A!important}

    .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;border-color:var(--khdn-border)!important}
    .tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important}
    .kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail{opacity:.76}
    .required-error,.required-error *{color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border-color:#E25A67!important}

    /* Only Create cards keep a fixed semantic yellow. All form widgets remain native. */
    div[class*="st-key-ops_alert_create_"] button{
      background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
      border:2px solid #D89A00!important;box-shadow:none!important;
      min-height:118px!important;font-weight:900!important;
    }
    div[class*="st-key-ops_alert_create_"] button *,div[class*="st-key-ops_alert_create_"] button p{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
    div[class*="st-key-ops_alert_create_"] button:hover{background:linear-gradient(135deg,#FFD45A 0%,#FFE99B 100%)!important;color:#201B0A!important;-webkit-text-fill-color:#201B0A!important;border-color:#F4B41A!important;transform:translateY(-1px)}

    @media (max-width:700px){
      .task-chip-row{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}.task-chip{font-size:.78rem!important;padding:.42rem .52rem!important;min-width:0!important}.task-chip.chip-kh,.task-chip.chip-status{grid-column:1/-1!important}[data-testid="stMetric"]{padding:.55rem .65rem!important}
      div[class*="st-key-ops_alert_create_"] button{min-height:68px!important;padding:7px 5px!important;border-radius:13px!important}
      div[class*="st-key-ops_alert_create_"] button p,div[class*="st-key-ops_alert_create_"] button [data-testid="stMarkdownContainer"]{font-size:.70rem!important;line-height:1.14!important}
    }
    @media (max-width:430px){.task-chip-row{grid-template-columns:1fr!important}.task-chip.chip-kh,.task-chip.chip-status{grid-column:auto!important}}
    </style>
    """,
    unsafe_allow_html=True,
)


'''
    text = text[:start] + adaptive + text[end:]
    loader.write_text(text, encoding="utf-8")

    index = Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    page = index.read_text(encoding="utf-8")
    admin_start = "/* Admin buttons use exactly the same idle/hover colors as work-management cards. */"
    admin_end = "/* CSS fallback only. The JS below resolves Streamlit's nested column wrapper. */"
    a = page.find(admin_start)
    b = page.find(admin_end, a + 1) if a >= 0 else -1
    if a < 0 or b < 0:
        raise RuntimeError("Adaptive theme installer cannot find Admin color span")
    adaptive_admin = r'''/* Admin navigation follows the active Streamlit Light/Dark theme. */
div[class*="st-key-admin_nav_card_"] button{
  box-shadow:none!important;
}
div[class*="st-key-admin_nav_card_"] button:hover{
  border-color:#F4B41A!important;
  transform:translateY(-1px)!important;
}

'''
    page = page[:a] + adaptive_admin + page[b:]
    index.write_text(page, encoding="utf-8")


if __name__ == "__main__":
    install()
