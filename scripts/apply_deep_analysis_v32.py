from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def patch_editable_tables() -> None:
    editor_files = [
        "modules/deep_company_analysis/chapter2.py",
        "modules/deep_company_analysis/chapter3.py",
        "modules/deep_company_analysis/chapter4.py",
        "modules/deep_company_analysis/chapter4_page_support.py",
        "modules/deep_company_analysis/chapter5.py",
        "modules/deep_company_analysis/chapter6_page_support.py",
    ]
    for name in editor_files:
        s = read(name).replace("st.data_editor(", "sortable_data_editor(")
        lines = s.splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("from modules.deep_company_analysis.table_format import "):
                if "sortable_data_editor" not in line:
                    lines[i] = line + ", sortable_data_editor"
                found = True
                break
        if not found:
            for i, line in enumerate(lines):
                if line.strip() == "import streamlit as st":
                    lines.insert(i + 1, "from modules.deep_company_analysis.table_format import sortable_data_editor")
                    found = True
                    break
        assert found, name
        write(name, "\n".join(lines) + "\n")


def patch_chapter1_sort() -> None:
    name = "modules/deep_company_analysis/chapter1.py"
    s = read(name)
    imp = "from modules.deep_company_analysis.table_format import interactive_sort_frame\n"
    if imp not in s:
        s = s.replace("import streamlit as st\n", "import streamlit as st\n\n" + imp, 1)
    old = '''            if not subset.empty:\n                for col in ["Giá", "Target"]:\n'''
    new = '''            if not subset.empty:\n                subset = interactive_sort_frame(subset, key=f"ch1_inventory_{gate_key}")\n                for col in ["Giá", "Target"]:\n'''
    assert old in s, "Chapter1 inventory pattern changed"
    write(name, s.replace(old, new, 1))


def patch_chapter4_ttm() -> None:
    name = "modules/deep_company_analysis/chapter4_quant.py"
    s = read(name)
    old = '''    history: list[dict[str, Any]] = []\n    for row in annual_rows[-10:]:\n        history.append({\n'''
    new = '''    history: list[dict[str, Any]] = []\n    display_rows = annual_rows[-10:]\n    if current and _is_ttm(current):\n        display_rows = display_rows + [current]\n    for row in display_rows:\n        history.append({\n'''
    assert old in s, "Chapter4 history pattern changed"
    write(name, s.replace(old, new, 1))


def patch_chapter5_ttm() -> None:
    name = "modules/deep_company_analysis/chapter5_quant.py"
    s = read(name)
    marker = '''def _period(row: dict[str, Any]) -> str:\n    return str(row.get("period") or row.get("year") or "")\n\n\n'''
    add = '''def _period(row: dict[str, Any]) -> str:\n    return str(row.get("period") or row.get("year") or "")\n\n\ndef _is_ttm(row: dict[str, Any]) -> bool:\n    text = _period(row).upper()\n    return "TTM" in text or "T12M" in text\n\n\n'''
    assert marker in s
    s = s.replace(marker, add, 1)

    marker2 = '''def _current_row(df: pd.DataFrame) -> dict[str, Any]:\n    if not isinstance(df, pd.DataFrame) or df.empty:\n        return {}\n    if "period" in df.columns:\n        mask = df["period"].astype(str).str.upper().str.contains("TTM|T12M", regex=True, na=False)\n        if mask.any():\n            return df[mask].iloc[-1].to_dict()\n    annual = _annual_rows(df)\n    return annual[-1] if annual else df.iloc[-1].to_dict()\n\n\n'''
    add2 = marker2 + '''def _history_rows(df: pd.DataFrame, years: int = 10, include_ttm: bool = True) -> list[dict[str, Any]]:\n    rows = _annual_rows(df)[-max(1, int(years)):]\n    if include_ttm:\n        current = _current_row(df)\n        if current and _is_ttm(current):\n            rows = rows + [current]\n    return rows\n\n\n'''
    assert marker2 in s
    s = s.replace(marker2, add2, 1)
    s = s.replace("rows = _annual_rows(annual_df)[-max(1, int(years)):]", "rows = _history_rows(annual_df, years=years, include_ttm=True)", 2)

    old_q26 = '''    rows = _annual_rows(annual_df)\n    current = rows[-1] if rows else _current_row(annual_df)\n    previous = rows[-2] if len(rows) >= 2 else {}\n    if not current:\n'''
    new_q26 = '''    rows = _annual_rows(annual_df)\n    current = _current_row(annual_df)\n    if _is_ttm(current):\n        previous = rows[-1] if rows else {}\n    else:\n        previous = rows[-2] if len(rows) >= 2 else {}\n    if not current:\n'''
    assert old_q26 in s
    s = s.replace(old_q26, new_q26, 1)

    old_diag = '''    rows = _annual_rows(annual_df)\n    if not rows:\n        return pd.DataFrame()\n    current = rows[-1]\n'''
    new_diag = '''    rows = _annual_rows(annual_df)\n    current = _current_row(annual_df)\n    if not current and not rows:\n        return pd.DataFrame()\n'''
    assert old_diag in s
    s = s.replace(old_diag, new_diag, 1)

    old_reinv_end = '''        previous = row\n    return pd.DataFrame(out)\n\n\ndef build_chapter5_quant_context(\n'''
    new_reinv_end = '''        previous = row\n    current = _current_row(annual_df)\n    if current and _is_ttm(current):\n        out.append({\n            "Kỳ": _period(current),\n            "ΔNOPAT (tỷ)": None,\n            "ΔInvested Capital proxy (tỷ)": None,\n            "Incremental ROIC %": None,\n            "NOPAT Source": "TTM current context",\n            "Interpretation": "TTM displayed; incremental ROIC requires a comparable prior TTM. App does not compare TTM mechanically with full-year FY.",\n        })\n    return pd.DataFrame(out)\n\n\ndef build_chapter5_quant_context(\n'''
    assert old_reinv_end in s
    s = s.replace(old_reinv_end, new_reinv_end, 1)
    write(name, s)


def patch_chapter6_dol() -> None:
    name = "modules/deep_company_analysis/chapter6_quant.py"
    s = read(name)
    marker = '''        previous = row\n\n    def median(values: list[float]) -> Optional[float]:\n'''
    add = '''        previous = row\n\n    ttm = _ttm_row(df)\n    if ttm:\n        out.append({\n            "Kỳ": _period(ttm),\n            "Δ Revenue (%)": None,\n            "Δ EBIT (%)": None,\n            "Historical DOL (x)": None,\n            "Observation": "TTM current context",\n            "Validity": "N/A",\n            "Invalid Reason": "TTM displayed; comparable prior TTM is required for DOL. No FY-vs-TTM sensitivity is fabricated.",\n        })\n\n    def median(values: list[float]) -> Optional[float]:\n'''
    assert marker in s
    s = s.replace(marker, add, 1)
    s = s.replace('''        "invalid_observations": max(0, len(out) - 1 - len(valid_values)),\n''', '''        "invalid_observations": sum(1 for item in out if item.get("Validity") == "Invalid"),\n''', 1)
    write(name, s)


def patch_module2_snapshot() -> None:
    name = "module2_dashboard.py"
    s = read(name)
    before = "\ndef _render_tre_sidebar_nav() -> None:\n"
    helper = '''
def _publish_manipulation_snapshot(company, source_label, beneish_df, accrual_quality_df, modified_jones_df, rem_df) -> None:
    """Publish already-computed Module-2 diagnostics for read-only downstream evidence use."""
    mapping = [
        ("1. Beneish M-Score", beneish_df),
        ("2. Accrual Quality / Sloan", accrual_quality_df),
        ("3. Modified Jones / Kothari", modified_jones_df),
        ("4. REM — Real Earnings Management", rem_df),
    ]
    layers = []
    for layer_name, frame in mapping:
        latest_score = frame.attrs.get("latest_score") if isinstance(frame, pd.DataFrame) else None
        latest_risk = frame.attrs.get("latest_risk", "N/A") if isinstance(frame, pd.DataFrame) else "N/A"
        latest_period = frame.attrs.get("latest_period", "") if isinstance(frame, pd.DataFrame) else ""
        latest_note = frame.attrs.get("latest_note", "") if isinstance(frame, pd.DataFrame) else ""
        if not latest_period and isinstance(frame, pd.DataFrame) and not frame.empty:
            for period_col in ("Kỳ", "Period", "period"):
                if period_col in frame.columns:
                    latest_period = str(frame.iloc[-1].get(period_col) or "")
                    break
        layers.append({
            "layer": layer_name,
            "latest_score": latest_score,
            "latest_risk": latest_risk,
            "latest_period": latest_period,
            "latest_note": latest_note,
        })
    st.session_state["module2_manipulation_snapshot"] = {
        "ticker": _safe_ticker(str(getattr(company, "ticker", ""))),
        "company_name": str(getattr(company, "company_name", "") or ""),
        "source_label": str(source_label or "Trecapital Module 2"),
        "source_module": "Module 2 — Financial Manipulation 4 Layers",
        "data_origin": "Already-computed Module 2 diagnostics; downstream is read-only",
        "layers": layers,
    }

'''
    assert before in s
    s = s.replace(before, "\n" + helper + before, 1)
    old = '''    rem_df = build_real_earnings_management_table(company, annual_df)\n    summary = build_module2_summary(company, annual_df, valuation_df, moat_df)\n'''
    new = '''    rem_df = build_real_earnings_management_table(company, annual_df)\n    _publish_manipulation_snapshot(company, source_label, beneish_df, accrual_quality_df, modified_jones_df, rem_df)\n    summary = build_module2_summary(company, annual_df, valuation_df, moat_df)\n'''
    assert old in s
    write(name, s.replace(old, new, 1))


def patch_chapter6_ui() -> None:
    name = "modules/deep_company_analysis/chapter6_page_support.py"
    s = read(name)
    marker = "from modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context\n"
    add = marker + '''from modules.deep_company_analysis.chapter6_evidence import (
    Chapter6EvidenceAgent,
    evidence_quality_summary,
    manipulation_snapshot_candidates,
    manipulation_snapshot_table,
    merge_candidates_into_record,
    research_gaps as phase6c_research_gaps,
)
'''
    assert marker in s
    s = s.replace(marker, add, 1)

    insert_before = "\ndef render_chapter6_tab(default_ticker: str = \"\") -> None:\n"
    renderer = '''
def _render_phase6c_research_assistant(ticker: str, company_name: str) -> None:
    safe = _safe_ticker(ticker)
    external_key = f"ch6c_external_candidates_{safe}"
    note_key = f"ch6c_note_{safe}"
    snapshot = st.session_state.get("module2_manipulation_snapshot")
    if not isinstance(snapshot, dict) or _safe_ticker(str(snapshot.get("ticker") or "")) != safe:
        snapshot = None

    with st.container(border=True):
        st.markdown("## 🔎 Phase 6C — Evidence & Research Assistant")
        st.caption(
            "AI/Data chỉ tìm candidate evidence, counter-evidence và research gaps. Không tự đổi Conservative/Liberal, recurring quality, "
            "cycle classification, Distribution Width, MOS, Research Gate hay BUY/HOLD/SELL."
        )

        with st.expander("Q27 — Read-only Financial Manipulation evidence bridge", expanded=True):
            if snapshot:
                table = manipulation_snapshot_table(snapshot)
                if not table.empty:
                    render_static_table(table, height=min(340, 100 + 30 * len(table)), sort_key=f"ch6c_manip_{safe}")
                st.caption(
                    "Beneish / Sloan / Modified Jones / REM được tính và sở hữu bởi Module 2. Chương 6 chỉ đọc snapshot đã tính; "
                    "dòng TTM là applicability guardrail, không phải M-Score/Jones/REM TTM giả lập."
                )
            else:
                st.info("Chưa có snapshot Module 2 cho đúng ticker trong phiên này. Mở/cập nhật Định giá chuyên sâu để Module 2 publish diagnostics, rồi quay lại Chương 6.")
                try:
                    st.page_link("pages/02_Dinh_gia_Porter_Moat.py", label="Mở Module 2 — Định giá chuyên sâu", icon="🧠")
                except Exception:
                    pass

        if st.button("🌐 Cập nhật evidence Chương 6", use_container_width=True, key=f"ch6c_refresh_{safe}"):
            with st.spinner(f"Đang tìm evidence Q27–Q32 cho {safe}..."):
                try:
                    agent = Chapter6EvidenceAgent(APP_DIR / "data_cache" / "deep_company_analysis_evidence")
                    result = agent.search(safe, company_name, max_results_per_query=3)
                    st.session_state[external_key] = result.candidates
                    st.session_state[note_key] = result.note
                    st.success(f"Đã cập nhật candidate evidence cho {safe}. Analyst cần mở nguồn và xác minh trước khi dùng làm kết luận.")
                except Exception as exc:
                    st.warning(f"Evidence search chưa hoàn tất: {exc}")

        external = st.session_state.get(external_key, pd.DataFrame())
        if not isinstance(external, pd.DataFrame):
            external = pd.DataFrame()
        internal = manipulation_snapshot_candidates(snapshot)
        pieces = [x for x in (external, internal) if isinstance(x, pd.DataFrame) and not x.empty]
        combined = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame()
        if not combined.empty:
            combined = combined.drop_duplicates(subset=["Question", "Title", "URL", "Snippet"], keep="first").reset_index(drop=True)

        if not external.empty:
            st.markdown("### Evidence coverage — A/B/C")
            render_static_table(evidence_quality_summary(external), height=300, sort_key=f"ch6c_quality_{safe}")
        elif not combined.empty:
            st.caption("Hiện mới có internal Module-2 diagnostic; chưa có external A/B/C evidence run trong phiên này.")

        if not combined.empty:
            st.markdown("### Candidate Evidence / Counter-Evidence")
            render_static_table(combined, height=min(560, 120 + 30 * len(combined)), sort_key=f"ch6c_candidates_{safe}")
            st.warning("Candidate ≠ verified evidence. Direction chỉ là research cue để chống confirmation bias, không phải kết luận Q27–Q32.")
        else:
            st.info("Chưa có candidate evidence trong phiên này.")

        gaps = phase6c_research_gaps(external)
        st.markdown("### Research Gaps")
        if not gaps.empty:
            render_static_table(gaps, height=min(360, 110 + 30 * len(gaps)), sort_key=f"ch6c_gaps_{safe}")

        if st.session_state.get(note_key):
            with st.expander("Research log", expanded=False):
                st.caption(str(st.session_state[note_key]))

        if not combined.empty or not gaps.empty:
            if st.button("💾 Lưu candidates + research gaps vào Evidence Matrix", use_container_width=True, key=f"ch6c_merge_{safe}"):
                current = load_record(safe)
                merged = merge_candidates_into_record(current, combined, gaps)
                save_record(safe, merged, company_name or str(current.get("company_name") or ""))
                st.success("Đã lưu candidates/research gaps. Không có analyst conclusion nào bị thay đổi.")
                st.rerun()

'''
    assert insert_before in s
    s = s.replace(insert_before, "\n" + renderer + insert_before, 1)
    call = "    _render_phase6b_quantitative_bridge(ticker)\n"
    new_call = call + '    _render_phase6c_research_assistant(ticker, str(payload.get("company_name") or ""))\n'
    assert call in s
    s = s.replace(call, new_call, 1)
    s = s.replace(
        "Approved Phase 6A + implemented Phase 6B canonical quantitative bridge.",
        "Approved Phase 6A + Phase 6B canonical bridge + Phase 6C Evidence & Research Assistant.",
    )
    write(name, s)


def update_formula_doc() -> None:
    name = "docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md"
    s = read(name)
    s = s.replace(
        "Status: **APPROVED Phase 6A source lock**. Computed metrics are deferred to Phase 6B unless explicitly noted.",
        "Status: **APPROVED source lock + implemented Phase 6B quantitative bridge + Phase 6C Evidence & Research Assistant**.",
    )
    if "## Phase 6C evidence boundary" not in s:
        s += '''\n\n## Phase 6C evidence boundary\n\nPhase 6C may retrieve and classify candidate evidence for Q27–Q32 and surface counter-evidence/research gaps. A/B/C is a source-quality/coverage grade, not a company-quality score. Module 2 Beneish/Sloan/Modified Jones/REM diagnostics are consumed read-only; Chapter 6 does not recompute them. Evidence candidates never auto-set analyst conclusions, Distribution Width, MOS, Research Gate, or BUY/HOLD/SELL.\n\nFinancial time-series tables extend to a valid canonical TTM when available. Annual-only methodologies show TTM as N/A rather than fabricate a value.\n'''
    write(name, s)


def main() -> None:
    patch_editable_tables()
    patch_chapter1_sort()
    patch_chapter4_ttm()
    patch_chapter5_ttm()
    patch_chapter6_dol()
    patch_module2_snapshot()
    patch_chapter6_ui()
    update_formula_doc()
    print("V32 migration applied")


if __name__ == "__main__":
    main()
