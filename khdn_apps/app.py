"""Compressed loader for KHDN Ops V2.28 production hosting.
Loads the engine with persistent paths and consistent SQLite backups.
"""
from pathlib import Path as _Path
import base64 as _base64
import gzip as _gzip

_parts = sorted((_Path(__file__).resolve().parent / "_src").glob("*.txt"))
_payload = "".join(_p.read_text(encoding="ascii") for _p in _parts)
_source = _gzip.decompress(_base64.b64decode(_payload)).decode("utf-8")
exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())

# V2.29 UI hotfix: the production app intentionally uses Streamlit Dark theme.
# Some record-information blocks still carry Light-theme pastel backgrounds, while
# Streamlit can inherit light text-fill into descendants.  Apply a final, post-render
# contrast layer so every record detail, form control, alert and popup remains legible.
st.markdown(
    r"""
    <style>
    :root{
      --khdn-bg:#0E1F1E;
      --khdn-surface:#17312F;
      --khdn-surface-2:#1C3A37;
      --khdn-text:#F4FFFC;
      --khdn-muted:#B7D5D0;
      --khdn-border:rgba(164,232,219,.48);
      --khdn-gold:#F4B41A;
    }

    /* Record information: never combine a Light card with inherited white text. */
    .task-chip-row{
      display:flex!important;flex-wrap:wrap!important;align-items:stretch!important;
      gap:8px!important;margin:.25rem 0 .65rem!important;
    }
    .task-chip{
      background:var(--khdn-surface)!important;
      color:var(--khdn-text)!important;
      -webkit-text-fill-color:var(--khdn-text)!important;
      border:1px solid var(--khdn-border)!important;
      border-left-width:4px!important;
      border-radius:10px!important;
      padding:.48rem .68rem!important;
      font-weight:800!important;line-height:1.3!important;
      white-space:normal!important;overflow-wrap:anywhere!important;
      text-shadow:none!important;box-shadow:0 4px 12px rgba(0,0,0,.18)!important;
    }
    .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    .task-chip.chip-kh{border-left-color:#78A9FF!important}
    .task-chip.chip-task{border-left-color:#F4B41A!important}
    .task-chip.chip-value{border-left-color:#62D7AF!important}
    .task-chip.chip-time{border-left-color:#FF9C5A!important}
    .task-chip.chip-support{border-left-color:#B79CFF!important}
    .task-chip.chip-qlkh{border-left-color:#62D5CF!important}
    .task-chip.chip-status{border-left-color:#FF8CA6!important;background:#2F2529!important}

    /* All custom read-only surfaces used around hồ sơ / KPI / workflow details. */
    .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,
    .bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,
    [data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{
      background:var(--khdn-surface)!important;
      color:var(--khdn-text)!important;
      border-color:rgba(164,232,219,.30)!important;
    }
    .tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,
    .annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{
      color:var(--khdn-text)!important;
      -webkit-text-fill-color:var(--khdn-text)!important;
    }
    .kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail,
    [data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{
      color:var(--khdn-muted)!important;
      -webkit-text-fill-color:var(--khdn-muted)!important;
    }
    .required-error,.required-error *{
      background:#442327!important;color:#FFD9DE!important;
      -webkit-text-fill-color:#FFD9DE!important;border-color:#F06A77!important;
    }

    /* Inputs/selects/date widgets: same high-contrast pair in every state. */
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea,
    [data-baseweb="select"]>div,
    [data-baseweb="select"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input{
      background:var(--khdn-surface)!important;
      color:var(--khdn-text)!important;
      -webkit-text-fill-color:var(--khdn-text)!important;
      border-color:rgba(164,232,219,.70)!important;
      caret-color:var(--khdn-text)!important;
    }
    input:disabled,textarea:disabled,[aria-disabled="true"]{
      opacity:1!important;color:#D4E9E5!important;-webkit-text-fill-color:#D4E9E5!important;
    }
    div[data-testid="stTextInput"] input::placeholder,
    div[data-testid="stNumberInput"] input::placeholder,
    div[data-testid="stTextArea"] textarea::placeholder{
      color:#A9C9C3!important;-webkit-text-fill-color:#A9C9C3!important;opacity:1!important;
    }
    [data-baseweb="select"] svg,[data-testid="stDateInput"] svg,[data-testid="stTimeInput"] svg{
      fill:var(--khdn-text)!important;color:var(--khdn-text)!important;
    }

    /* Dropdowns, menus, multiselect tags and tooltips. */
    [data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],
    [data-baseweb="popover"]>div,[data-baseweb="menu"]>div,[role="option"]{
      background:#15302E!important;color:var(--khdn-text)!important;
      -webkit-text-fill-color:var(--khdn-text)!important;
    }
    [role="option"]:hover,[role="option"][aria-selected="true"]{
      background:#24504A!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important;
    }
    [data-baseweb="tag"]{background:#24504A!important;color:#FFFFFF!important}
    [data-baseweb="tag"] *{color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}

    /* Alerts and expanders: preserve semantic border/icon, force readable copy. */
    [data-testid="stAlert"]{
      background:#17312F!important;color:var(--khdn-text)!important;
      border-color:rgba(164,232,219,.35)!important;
    }
    [data-testid="stAlert"] *{
      color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;
    }
    [data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{
      color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;
    }

    /* Table wrappers and native HTML tables used by reports / record history. */
    [data-testid="stDataFrame"],.stDataFrame{background:#122624!important;color:var(--khdn-text)!important}
    table,table td,table th{color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important}
    table td{background:#122624!important;border-color:rgba(164,232,219,.18)!important}
    table th{background:#1B4540!important;border-color:rgba(164,232,219,.30)!important}
    table tbody tr:hover td{background:#1D3A37!important}

    /* Generic markdown inside main content: readable by default, while semantic
       components above may still override with their own stronger selectors. */
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"]{
      color:var(--khdn-text)!important;
    }
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] li,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stAppViewContainer"] legend{
      color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;
    }

    /* Mobile: keep information compact instead of long vertical blocks. */
    @media (max-width: 700px){
      .task-chip-row{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:6px!important}
      .task-chip{font-size:.78rem!important;padding:.42rem .52rem!important;min-width:0!important}
      .task-chip.chip-kh,.task-chip.chip-status{grid-column:1/-1!important}
      [data-testid="stMetric"]{padding:.55rem .65rem!important}
    }
    @media (max-width: 430px){
      .task-chip-row{grid-template-columns:1fr!important}
      .task-chip.chip-kh,.task-chip.chip-status{grid-column:auto!important}
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# V2.24: always keep the user guide available online even when the DOCX is not
# stored in Git.  The full Word file is still used when present; otherwise the
# embedded Markdown guide is rendered and can be downloaded from the app.
_ORIGINAL_GUIDE_PAGE = guide_page

def guide_page(u):
    page_title("Hướng dẫn sử dụng", "Tài liệu hướng dẫn KHDN Ops được đính kèm trực tiếp trong ứng dụng.")
    st.info("📘 Workflow CBHT/QLKH/Lãnh đạo/Admin, Dashboard, mục tiêu tuần-tháng, lịch sử, tỷ giá, sao lưu và xử lý sự cố.")
    md_path = _Path(__file__).resolve().parent / "GUIDE.md"
    if GUIDE_PATH.exists():
        data = GUIDE_PATH.read_bytes()
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng KHDN Ops (.docx)",
            data=data,
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS_v2.22.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="download_khdn_guide_docx",
        )
    elif md_path.exists():
        guide_text = md_path.read_text(encoding="utf-8")
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng (.md)",
            data=guide_text.encode("utf-8"),
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS.md",
            mime="text/markdown",
            use_container_width=True,
            key="download_khdn_guide_md",
        )
        st.markdown(guide_text)
    else:
        st.warning("Chưa tìm thấy tài liệu hướng dẫn trong gói triển khai.")
