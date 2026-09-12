"""Compressed loader for KHDN Ops production hosting.
Loads the engine with persistent paths, applies production hotfixes, then starts Streamlit.
"""
from pathlib import Path as _Path
import base64 as _base64
import gzip as _gzip

_parts = sorted((_Path(__file__).resolve().parent / "_src").glob("*.txt"))
_payload = "".join(_p.read_text(encoding="ascii") for _p in _parts)
_source = _gzip.decompress(_base64.b64decode(_payload)).decode("utf-8")


def _patch_once(old, new, label):
    """Apply a deterministic production patch and fail loudly if source drifted."""
    global _source
    if old not in _source:
        raise RuntimeError(f"KHDN production patch not applied: {label}")
    _source = _source.replace(old, new, 1)


# V2.30: delay app() until production overrides below are installed.
_patch_once(
    'if __name__ == "__main__":\n    app()\n',
    '# app() is started by the production loader after runtime overrides are installed.\n',
    'defer app start',
)

# Cancelled transactions remain in history/audit but must not contribute to the
# headline operational count on Dashboard.
_patch_once(
    '("Số tác nghiệp", money(len(analysis_f)), "Cá nhân" if operational_view else "Theo bộ lọc hiện tại"),',
    '("Số tác nghiệp", money(len(analysis_f[analysis_f.status.ne("CANCELLED")])), "Cá nhân" if operational_view else "Theo bộ lọc hiện tại"),',
    'dashboard cancelled count',
)

# Annual archive statistics/counts must follow the same rule; cancelled records
# remain preserved in SQLite audit/history, not in operational statistics.
_patch_once(
    '    ydf=room[room["archive_year"].eq(year)].copy()\n',
    '    ydf=room[room["archive_year"].eq(year) & room["status"].ne("CANCELLED")].copy()\n',
    'annual archive cancelled filter',
)

exec(compile(_source, str(_Path(__file__).resolve().parent / "app_v223_source.py"), "exec"), globals(), globals())


# ---------- V2.30 production behavior overrides ----------
def _exclude_cancelled(df):
    if df is None:
        return df
    try:
        if "status" in df.columns:
            return df[df["status"].ne("CANCELLED")].copy()
    except Exception:
        pass
    return df.copy() if hasattr(df, "copy") else df


# Value statistics and downstream staff/type/calendar aggregates receive a frame
# with cancelled tasks removed. The raw task frame stays intact for history/audit
# and the dedicated cancellation event counter.
_ORIGINAL_DASHBOARD_STAT_FRAME = _dashboard_stat_frame

def _dashboard_stat_frame(df):
    return _ORIGINAL_DASHBOARD_STAT_FRAME(_exclude_cancelled(df))


_ORIGINAL_MAKE_EXCEL_REPORT = make_excel_report

def make_excel_report(detail, support_privacy=False):
    return _ORIGINAL_MAKE_EXCEL_REPORT(_exclude_cancelled(detail), support_privacy=support_privacy)


# Long-horizon benchmark should not re-introduce cancelled transactions.
if "five_year_benchmark" in globals():
    _ORIGINAL_FIVE_YEAR_BENCHMARK = five_year_benchmark
    def five_year_benchmark(df, *args, **kwargs):
        return _ORIGINAL_FIVE_YEAR_BENCHMARK(_exclude_cancelled(df), *args, **kwargs)

if "_render_efficiency_assessment" in globals():
    _ORIGINAL_RENDER_EFFICIENCY_ASSESSMENT = _render_efficiency_assessment
    def _render_efficiency_assessment(u, df, *args, **kwargs):
        return _ORIGINAL_RENDER_EFFICIENCY_ASSESSMENT(u, _exclude_cancelled(df), *args, **kwargs)

if "_render_five_year_benchmark" in globals():
    _ORIGINAL_RENDER_FIVE_YEAR_BENCHMARK = _render_five_year_benchmark
    def _render_five_year_benchmark(u, df, *args, **kwargs):
        return _ORIGINAL_RENDER_FIVE_YEAR_BENCHMARK(u, _exclude_cancelled(df), *args, **kwargs)


# Remove the separate workflow pill strip on the two operational pages. Status
# cards themselves remain clickable; the single Create action is integrated into
# that same card grid to keep phone layouts compact.
_ORIGINAL_PILL_NAV = pill_nav

def pill_nav(state_key, options, default=None, prefix="subnav"):
    if state_key in {"support_view", "qlkh_view"}:
        values = [v for v, _ in options]
        current = st.session_state.get(state_key)
        if current not in values:
            current = default if default in values else values[0]
            st.session_state[state_key] = current
        return current
    return _ORIGINAL_PILL_NAV(state_key, options, default=default, prefix=prefix)


_ORIGINAL_OPS_ACTION_CARDS = ops_action_cards

def ops_action_cards(state_key, cards):
    cards = list(cards)
    if state_key == "support_view" and not any(c[0] == "create" for c in cards):
        cards.insert(0, ("create", "➕", "Tạo công việc mới", None, False, False))
    elif state_key == "qlkh_view" and not any(c[0] == "create" for c in cards):
        cards.insert(0, ("create", "➕", "Tạo/giao hồ sơ", None, False, False))
    else:
        return _ORIGINAL_OPS_ACTION_CARDS(state_key, cards)

    with st.container(key=f"ops_cards_{state_key}"):
        cols = st.columns(len(cards), gap="small")
        for idx, (col, card) in enumerate(zip(cols, cards)):
            value, icon, label, count, hot = card[:5]
            danger = bool(card[5]) if len(card) > 5 else False
            extra_state = card[6] if len(card) > 6 and isinstance(card[6], dict) else {}
            is_create = count is None
            needs_attention = (not is_create) and bool(count) and bool(hot or danger)
            status_text = "\n⚠️ CẦN XỬ LÝ" if needs_attention else ""
            if is_create:
                button_text = f"{icon}  {label}"
                container_key = f"ops_alert_create_{state_key}_{idx}"
            else:
                button_text = f"{icon}  {label}\n\n{int(count)}{status_text}"
                container_key = f"ops_alert_hot_{state_key}_{idx}" if needs_attention else f"ops_alert_idle_{state_key}_{idx}"
            with col:
                with st.container(key=container_key):
                    if st.button(
                        button_text,
                        key=f"opsaction_{state_key}_{idx}_{value}",
                        use_container_width=True,
                        type="primary" if (needs_attention or is_create) else "secondary",
                    ):
                        st.session_state[state_key] = value
                        for sk, sv in extra_state.items():
                            st.session_state[sk] = sv
                        st.rerun()


# Dark-mode readability + yellow Create actions. The semantic status cards keep
# their current alert behavior, while the Create card is stable yellow on desktop
# and mobile.
st.markdown(
    r"""
    <style>
    :root{
      --khdn-bg:#0E1F1E;--khdn-surface:#17312F;--khdn-text:#F4FFFC;
      --khdn-muted:#B7D5D0;--khdn-border:rgba(164,232,219,.48);--khdn-gold:#F4B41A;
    }
    .task-chip-row{display:flex!important;flex-wrap:wrap!important;align-items:stretch!important;gap:8px!important;margin:.25rem 0 .65rem!important}
    .task-chip{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border:1px solid var(--khdn-border)!important;border-left-width:4px!important;border-radius:10px!important;padding:.48rem .68rem!important;font-weight:800!important;line-height:1.3!important;white-space:normal!important;overflow-wrap:anywhere!important;text-shadow:none!important;box-shadow:0 4px 12px rgba(0,0,0,.18)!important}
    .task-chip *{color:inherit!important;-webkit-text-fill-color:inherit!important}
    .task-chip.chip-kh{border-left-color:#78A9FF!important}.task-chip.chip-task{border-left-color:#F4B41A!important}.task-chip.chip-value{border-left-color:#62D7AF!important}.task-chip.chip-time{border-left-color:#FF9C5A!important}.task-chip.chip-support{border-left-color:#B79CFF!important}.task-chip.chip-qlkh{border-left-color:#62D5CF!important}.task-chip.chip-status{border-left-color:#FF8CA6!important;background:#2F2529!important}

    .tre-section,.kpi-card,.perf-period,.perf-trend-card,.annual-benchmark-note,.bidv-table-wrap,.section-note,.open-list-note,.task-pick-alert,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stExpanderDetails"]{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;border-color:rgba(164,232,219,.30)!important}
    .tre-section *,.kpi-card *,.perf-period *,.perf-trend-card *,.annual-benchmark-note *,.section-note *,.open-list-note *,.task-pick-alert *{color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important}
    .kpi-label,.kpi-sub,.perf-trend-label,.perf-trend-detail,[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] *{color:var(--khdn-muted)!important;-webkit-text-fill-color:var(--khdn-muted)!important}
    .required-error,.required-error *{background:#442327!important;color:#FFD9DE!important;-webkit-text-fill-color:#FFD9DE!important;border-color:#F06A77!important}

    div[data-testid="stTextInput"] input,div[data-testid="stNumberInput"] input,div[data-testid="stTextArea"] textarea,div[data-baseweb="input"] input,div[data-baseweb="textarea"] textarea,[data-baseweb="select"]>div,[data-baseweb="select"] input,[data-testid="stDateInput"] input,[data-testid="stTimeInput"] input{background:var(--khdn-surface)!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important;border-color:rgba(164,232,219,.70)!important;caret-color:var(--khdn-text)!important}
    input:disabled,textarea:disabled,[aria-disabled="true"]{opacity:1!important;color:#D4E9E5!important;-webkit-text-fill-color:#D4E9E5!important}
    div[data-testid="stTextInput"] input::placeholder,div[data-testid="stNumberInput"] input::placeholder,div[data-testid="stTextArea"] textarea::placeholder{color:#A9C9C3!important;-webkit-text-fill-color:#A9C9C3!important;opacity:1!important}
    [data-baseweb="popover"],[data-baseweb="menu"],[role="listbox"],[data-baseweb="popover"]>div,[data-baseweb="menu"]>div,[role="option"]{background:#15302E!important;color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important}
    [role="option"]:hover,[role="option"][aria-selected="true"]{background:#24504A!important;color:#FFFFFF!important;-webkit-text-fill-color:#FFFFFF!important}
    [data-testid="stAlert"]{background:#17312F!important;color:var(--khdn-text)!important;border-color:rgba(164,232,219,.35)!important}[data-testid="stAlert"] *{color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important}
    [data-testid="stDataFrame"],.stDataFrame{background:#122624!important;color:var(--khdn-text)!important}table,table td,table th{color:var(--khdn-text)!important;-webkit-text-fill-color:var(--khdn-text)!important}table td{background:#122624!important;border-color:rgba(164,232,219,.18)!important}table th{background:#1B4540!important;border-color:rgba(164,232,219,.30)!important}

    /* Only the two Create cards are persistent yellow actions. */
    div[class*="st-key-ops_alert_create_"] button{
      background:linear-gradient(135deg,#F4B41A 0%,#FFD45A 100%)!important;
      color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
      border:2px solid #FFE589!important;box-shadow:0 8px 20px rgba(244,180,26,.32)!important;
      min-height:118px!important;font-weight:900!important;
    }
    div[class*="st-key-ops_alert_create_"] button *,div[class*="st-key-ops_alert_create_"] button p{color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;font-weight:900!important}
    div[class*="st-key-ops_alert_create_"] button:hover{background:linear-gradient(135deg,#FFD45A 0%,#FFE99B 100%)!important;color:#201B0A!important;-webkit-text-fill-color:#201B0A!important;border-color:#FFF4BE!important;transform:translateY(-2px)}

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


# Keep the embedded guide available online.
_ORIGINAL_GUIDE_PAGE = guide_page

def guide_page(u):
    page_title("Hướng dẫn sử dụng", "Tài liệu hướng dẫn KHDN Ops được đính kèm trực tiếp trong ứng dụng.")
    st.info("📘 Workflow CBHT/QLKH/Lãnh đạo/Admin, Dashboard, mục tiêu tuần-tháng, lịch sử, tỷ giá, sao lưu và xử lý sự cố.")
    md_path = _Path(__file__).resolve().parent / "GUIDE.md"
    if GUIDE_PATH.exists():
        data = GUIDE_PATH.read_bytes()
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng KHDN Ops (.docx)", data=data,
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS_v2.22.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True, key="download_khdn_guide_docx",
        )
    elif md_path.exists():
        guide_text = md_path.read_text(encoding="utf-8")
        st.download_button(
            "⬇️ Tải Hướng dẫn sử dụng (.md)", data=guide_text.encode("utf-8"),
            file_name="HUONG_DAN_SU_DUNG_KHDN_OPS.md", mime="text/markdown",
            use_container_width=True, key="download_khdn_guide_md",
        )
        st.markdown(guide_text)
    else:
        st.warning("Chưa tìm thấy tài liệu hướng dẫn trong gói triển khai.")


if __name__ == "__main__":
    app()
