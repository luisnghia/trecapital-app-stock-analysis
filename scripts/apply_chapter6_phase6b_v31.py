from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def patch_quant() -> None:
    p = ROOT / "modules/deep_company_analysis/chapter6_quant.py"
    s = p.read_text(encoding="utf-8")
    old = """        if cfo is not None and ni is not None:\n            cumulative_cfo += cfo\n            cumulative_ni += ni\n            cumulative_count += 1\n        cumulative_ratio = _ratio(cumulative_cfo, cumulative_ni) if cumulative_count and cumulative_ni > 0 else None\n"""
    new = """        overlapping_ttm = _is_ttm(row)\n        if cfo is not None and ni is not None and not overlapping_ttm:\n            cumulative_cfo += cfo\n            cumulative_ni += ni\n            cumulative_count += 1\n        cumulative_ratio = _ratio(cumulative_cfo, cumulative_ni) if cumulative_count and cumulative_ni > 0 and not overlapping_ttm else None\n"""
    if old in s:
        s = s.replace(old, new, 1)
    elif "overlapping_ttm = _is_ttm(row)" not in s:
        raise AssertionError("Q27 cumulative pattern changed")

    old2 = """            \"Cumulative CFO (tỷ)\": cumulative_cfo if cumulative_count else None,\n            \"Cumulative NI (tỷ)\": cumulative_ni if cumulative_count else None,\n"""
    new2 = """            \"Cumulative CFO (tỷ)\": cumulative_cfo if cumulative_count and not overlapping_ttm else None,\n            \"Cumulative NI (tỷ)\": cumulative_ni if cumulative_count and not overlapping_ttm else None,\n"""
    if old2 in s:
        s = s.replace(old2, new2, 1)
    elif "cumulative_count and not overlapping_ttm" not in s:
        raise AssertionError("Q27 cumulative display pattern changed")
    p.write_text(s, encoding="utf-8")


def helper_block() -> str:
    return r'''

@st.cache_data(ttl=120, show_spinner=False)
def _chapter6_quant_cached(
    ticker: str,
    overview_path: str,
    year_path: str,
    quarter_path: str,
    overview_sig: tuple[int, int],
    year_sig: tuple[int, int],
    quarter_sig: tuple[int, int],
    source_label: str,
):
    del overview_sig, year_sig, quarter_sig
    safe = _safe_ticker(ticker)
    company = m1._load_overview_cached(overview_path, safe)
    annual_raw = m1._load_timeseries_cached(year_path, safe, "Y", 11)
    quarterly = m1._load_timeseries_cached(quarter_path, safe, "Q", 20)
    annual_and_ttm = append_ttm_row(annual_raw, quarterly)
    return build_chapter6_quant_context(
        safe,
        str(getattr(company, "company_name", "") or getattr(company, "name", "") or ""),
        annual_and_ttm,
        industry=str(getattr(company, "industry", "") or ""),
        sub_industry=str(getattr(company, "sub_industry", "") or ""),
        source_label=source_label,
        years=10,
    )


def _load_chapter6_quant(ticker: str):
    safe = _safe_ticker(ticker)
    paths, source_label = _active_paths(safe)
    if not paths:
        return None, f"{safe}: chưa có canonical statement cache trên máy."
    overview, year, quarter = paths
    try:
        ctx = _chapter6_quant_cached(
            safe,
            str(overview), str(year), str(quarter),
            _path_signature(overview), _path_signature(year), _path_signature(quarter),
            source_label,
        )
        if not ctx:
            return None, f"{safe}: canonical bundle chưa có dữ liệu usable cho Phase 6B."
        return ctx, ""
    except Exception as exc:
        return None, f"{safe}: không dựng được Chapter 6 quantitative context: {exc}"


def _refresh_chapter6_canonical(ticker: str) -> tuple[bool, str]:
    safe = _safe_ticker(ticker)
    try:
        st.session_state["last_query_ticker"] = safe
        st.session_state["last_query_source"] = "FireAnt + Vietstock"
        m1._search_and_bind(safe, "FireAnt + Vietstock")
        checker = getattr(m1, "_active_bundle_has_data_for_ticker", None)
        ok = bool(checker(safe)) if callable(checker) else _safe_ticker(str(st.session_state.get("active_ticker", ""))) == safe
        if ok:
            for key in ("active_ticker", "shared_ticker", "module1_ticker", "module2_ticker"):
                st.session_state[key] = safe
            _chapter6_quant_cached.clear()
            return True, f"Đã cập nhật Trecapital canonical data cho {safe}."
        return False, f"Chưa lấy được canonical data cho {safe}; Chương 6 không dùng dữ liệu mã khác thay thế."
    except Exception as exc:
        return False, f"Cập nhật canonical data chưa thành công: {exc}"


def _metric_value(value: Any, kind: str) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    return format_numeric(value, kind)


def _render_phase6b_quantitative_bridge(ticker: str) -> dict[str, Any] | None:
    safe = _safe_ticker(ticker)
    ctx, error = _load_chapter6_quant(safe)

    with st.container(border=True):
        st.markdown("## 📐 Phase 6B — Quantitative Bridge từ Trecapital canonical data")
        st.caption(
            "Single Source of Truth: FireAnt/Vietstock/Simplize → Trecapital normalize/validate → canonical dataset → Chapter 6. "
            "Bridge chỉ tạo evidence định lượng; không tự sửa Q27–Q32, Distribution Width, MOS hay BUY/HOLD/SELL."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            if ctx:
                prov = ctx.get("provenance", {})
                industry = str(ctx.get("industry") or "—")
                sub_industry = str(ctx.get("sub_industry") or "—")
                st.success(
                    f"{safe} — {ctx.get('company_name') or 'Doanh nghiệp'} | kỳ {ctx.get('latest_period') or '—'} | "
                    f"{industry} / {sub_industry} | {prov.get('source_label') or 'Trecapital canonical'}"
                )
            else:
                st.warning(error)
        with c2:
            if st.button("🔄 Cập nhật canonical data Chương 6", use_container_width=True, key=f"ch6b_refresh_{safe}"):
                with st.spinner(f"Đang cập nhật canonical data cho {safe}..."):
                    ok, note = _refresh_chapter6_canonical(safe)
                (st.success if ok else st.warning)(note)
                if ok:
                    st.rerun()

        if not ctx:
            return None

        warnings = ctx.get("coverage_warnings") or []
        if warnings:
            with st.expander(f"⚠ Phase 6B coverage / applicability warnings ({len(warnings)})", expanded=True):
                for warning in warnings:
                    st.write(f"- {warning}")

        with st.expander("Q27 — CFO/NI + Accounting-quality diagnostics", expanded=True):
            table = ctx.get("q27_accounting_quality")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
                summary = ctx.get("q27_summary") or {}
                cols = st.columns(3)
                cols[0].metric("Annual periods", int(summary.get("annual_periods") or 0))
                cols[1].metric("Cumulative CFO/NI", _metric_value(summary.get("cumulative_cfo_to_ni"), "ratio"))
                cols[2].metric("Current-tax comparison", "Available" if summary.get("tax_comparison_available") else "N/A")
            st.caption(
                "CFO/NI là research diagnostic. TTM không được cộng chồng vào cumulative annual CFO/NI. "
                "tax_paid_bil không bao giờ được dùng thay current-tax expense."
            )

        with st.expander("Q28 — Explicit recurring-revenue disclosure", expanded=False):
            table = ctx.get("q28_disclosed_recurring")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(300, 90 + 29 * len(table)))
            else:
                st.info(
                    "Canonical dataset hiện không có explicit recurring/contracted revenue share. "
                    "App giữ Unknown và không suy recurring % từ doanh thu lặp lại quan sát được."
                )

        with st.expander("Q29 — Historical cycle / drawdown context", expanded=True):
            table = ctx.get("q29_cycle_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
            st.caption(
                "Bảng chỉ mô tả historical variability. Không tự suy GDP/commodity/recession là nguyên nhân và không tự gắn Cyclical / Resistant."
            )

        with st.expander("Q30 — Historical Operating Leverage (DOL)", expanded=True):
            table = ctx.get("q30_dol_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(430, 90 + 29 * len(table)))
            summary = ctx.get("q30_summary") or {}
            cols = st.columns(4)
            cols[0].metric("Valid DOL periods", int(summary.get("valid_observations") or 0))
            cols[1].metric("Median DOL", _metric_value(summary.get("median_dol"), "ratio"))
            cols[2].metric("Downside median", _metric_value(summary.get("downside_median_dol"), "ratio"))
            cols[3].metric("Upside median", _metric_value(summary.get("upside_median_dol"), "ratio"))
            st.caption(
                "DOL = %Δ EBIT / %Δ Revenue. Revenue gần như không đổi hoặc EBIT ≤ 0/sign shift được giữ trên bảng là Invalid, "
                "không bị ẩn và không tham gia median."
            )

        with st.expander("Q31 — Working Capital / CCC 5–10 năm", expanded=True):
            summary = ctx.get("q31_summary") or {}
            if not summary.get("applicable", True):
                st.warning(summary.get("status") or "N/A — not economically applicable")
                st.caption(summary.get("reason") or "")
            else:
                table = ctx.get("q31_working_capital")
                if isinstance(table, pd.DataFrame) and not table.empty:
                    render_static_table(table, height=min(460, 90 + 29 * len(table)))
                st.info(summary.get("cash_sign_convention") or "Cash impact = -ΔOWC.")
                st.caption(summary.get("reconciliation_note") or "")
            st.caption("Không tự kết luận CCC thấp hoặc negative working capital là tốt. Analyst phải xem business mechanism và tính bền vững.")

        with st.expander("Q32 — Capex intensity / D&A / FCF / PP&E age diagnostic", expanded=True):
            table = ctx.get("q32_capex_history")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=min(460, 90 + 29 * len(table)))
            summary = ctx.get("q32_summary") or {}
            cols = st.columns(3)
            cols[0].metric("Median Capex/Revenue", _metric_value(summary.get("median_capex_to_revenue_pct"), "percent"))
            cols[1].metric("Median Capex/D&A", _metric_value(summary.get("median_capex_to_da"), "ratio"))
            cols[2].metric("Sector relevance", str(summary.get("relevance") or "—"))
            st.warning(summary.get("maintenance_capex_guardrail") or "Maintenance capex remains analyst/source driven.")

        with st.expander("🔎 Phase 6B provenance & formula audit", expanded=False):
            table = ctx.get("provenance_table")
            if isinstance(table, pd.DataFrame) and not table.empty:
                render_static_table(table, height=360)
            st.write(ctx.get("provenance") or {})
            st.caption("Formula methodology: docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md")

    return ctx
'''


def patch_page_support() -> None:
    p = ROOT / "modules/deep_company_analysis/chapter6_page_support.py"
    s = p.read_text(encoding="utf-8")
    if "from modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context" not in s:
        marker = "import pandas as pd\nimport streamlit as st\n"
        add = """import pandas as pd\nimport streamlit as st\n\nimport module1_dashboard as m1\nfrom module1_engine import append_ttm_row\nfrom modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature\nfrom modules.deep_company_analysis.table_format import format_numeric, render_static_table\nfrom modules.deep_company_analysis.chapter6_quant import build_chapter6_quant_context\n"""
        if marker not in s:
            raise AssertionError("Chapter6 import marker changed")
        s = s.replace(marker, add, 1)

    if "def _render_phase6b_quantitative_bridge" not in s:
        marker = '\ndef render_chapter6_tab(default_ticker: str = "") -> None:\n'
        if marker not in s:
            raise AssertionError("Chapter6 render marker changed")
        s = s.replace(marker, helper_block() + marker, 1)

    s = s.replace(
        '"Michael Shearn Q27–Q32 | Approved Phase 6A: source-locked analyst workspace. "',
        '"Michael Shearn Q27–Q32 | Approved Phase 6A + implemented Phase 6B canonical quantitative bridge. "',
        1,
    )
    s = s.replace(
        '- **Q30:** Phase 6A phân rã fixed / variable / semi-variable; historical DOL thuộc Phase 6B.',
        '- **Q30:** Phase 6A phân rã fixed / variable / semi-variable; Phase 6B hiển thị historical DOL có invalid-row guardrails.',
        1,
    )

    if "_render_phase6b_quantitative_bridge(ticker)" not in s:
        call_marker = '''    payload["company_name"] = st.text_input(\n        "Tên doanh nghiệp (analyst, optional)",\n        value=str(payload.get("company_name") or ""),\n        key=f"dca_ch6_company_{ticker}",\n    )\n\n    with st.expander("Q27 — Accounting standards: Conservative hay Liberal?", expanded=True):\n'''
        call_repl = '''    payload["company_name"] = st.text_input(\n        "Tên doanh nghiệp (analyst, optional)",\n        value=str(payload.get("company_name") or ""),\n        key=f"dca_ch6_company_{ticker}",\n    )\n\n    _render_phase6b_quantitative_bridge(ticker)\n\n    with st.expander("Q27 — Accounting standards: Conservative hay Liberal?", expanded=True):\n'''
        if call_marker not in s:
            raise AssertionError("Chapter6 Phase6B call marker changed")
        s = s.replace(call_marker, call_repl, 1)

    p.write_text(s, encoding="utf-8")


def patch_formula_doc() -> None:
    p = ROOT / "docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md"
    s = p.read_text(encoding="utf-8")
    s = s.replace(
        "Status: **APPROVED Phase 6A source lock**. Computed metrics are deferred to Phase 6B unless explicitly noted.",
        "Status: **APPROVED Phase 6A source lock + IMPLEMENTED Phase 6B canonical quantitative bridge (V31)**.",
        1,
    )
    if "## Phase 6B implementation lock — V31" not in s:
        s = s.rstrip() + r'''

## Phase 6B implementation lock — V31

The production bridge reads only the active Trecapital canonical overview/year/quarter bundle and appends TTM through the existing Module-1 path. It does not fetch a second financial dataset.

### Q27 implementation

- Annual and valid TTM rows may display `CFO/NI` and `CFO - NI`.
- Cumulative CFO/NI is **annual-only**; an overlapping TTM row is never added on top of annual history.
- Current-tax comparison is calculated only from a separately mapped current-tax-expense field. `tax_paid_bil` is **not** substituted for current-tax expense.
- Missing current-tax expense therefore remains `N/A`.

### Q28 implementation

Phase 6B exposes only explicit canonical fields such as `recurring_revenue_pct`, `contracted_revenue_pct` or `subscription_revenue_pct` if such fields truly exist in the canonical row. Otherwise the table remains empty/Unknown. No observed repeat-sales pattern is converted into a recurring-revenue percentage.

### Q29 implementation

Historical context includes revenue, EBIT, revenue growth, EBIT growth, gross/EBIT margins, and drawdown from the running historical peak. These are variability diagnostics only.

### Q30 implementation

`Historical DOL = %Δ EBIT / %Δ Revenue`

A row is retained but marked `Invalid` when revenue growth is undefined, absolute revenue change is below 1.0%, or current/prior EBIT is non-positive/sign-shifted. Invalid rows do not enter median, downside-median or upside-median DOL.

### Q31 implementation

`OWC = Operating Current Assets - Operating Current Liabilities`

`ΔOWC = OWC_t - OWC_(t-1)`

`Cash impact from ΔOWC = -ΔOWC`

Therefore positive cash impact means cash released and negative cash impact means cash absorbed. The bridge displays the canonical CFS working-capital change beside the balance-sheet-derived cash impact and exposes the reconciliation gap rather than silently forcing them to match.

DSO/DIO/DPO prefer average current/prior balances. Canonical day metrics are used only as a labelled fallback when average-balance inputs are insufficient. Banks, insurers, securities firms and other identified financial-service businesses are marked `N/A — not economically applicable` for CCC/OWC analysis rather than being forced through an industrial-company formula.

### Q32 implementation

- Total Capex is displayed as expenditure magnitude.
- `Capex/Revenue`, `Capex/D&A`, canonical/transparent FCF and Net/Gross PP&E are diagnostics.
- Chapter 6 **does not import Module-1 `maintenance_capex_bil`** because upstream Owner-Earnings logic may contain a generic proxy. That proxy is not allowed to become a Chapter-6 maintenance-capex fact.
- Chapter-6 maintenance capex remains: company disclosure → analyst estimate with evidence → explicitly selected D&A rough proxy → Unknown.

### Analyst boundary

Phase 6B never changes Q27–Q32 analyst assessments, final Earnings/Cash-flow Distribution Width, MOS, Research Gate or BUY/HOLD/SELL. Quantitative context is evidence only.
'''
        s += "\n"
    p.write_text(s, encoding="utf-8")


def write_docs_and_test() -> None:
    (ROOT / "docs/CHAPTER6_PHASE6B_IMPLEMENTATION.md").write_text(r'''# Chapter 6 — Phase 6B Quantitative Bridge V31

Status: **IMPLEMENTED — approved specification**.

## Scope

Phase 6B connects Q27–Q32 to the existing Trecapital canonical Data Layer. It does not create a new data-fetching pipeline and does not write quantitative evidence back into analyst-owned conclusions automatically.

## Delivered

- Q27: CFO/NI, CFO−NI, annual cumulative cash conversion, current-tax vs provision only when separately disclosed.
- Q28: explicit recurring/contracted/subscription revenue share only; no inference.
- Q29: 10-year + valid TTM revenue/EBIT/margins/peak-drawdown context.
- Q30: period-by-period historical DOL with visible invalid rows plus median/downside/upside summaries.
- Q31: AR/Inventory/AP, DSO/DIO/DPO/CCC, OWC, ΔOWC, cash absorbed/released and CFS reconciliation; financial-sector N/A guardrail.
- Q32: Total Capex, Capex/Revenue, Capex/D&A, CFO/FCF, FCF margin and Net/Gross PP&E when available.
- Provenance audit table: source fields, source module, source period, data origin and formula boundary.

## Critical guardrails

1. `tax_paid_bil` is not current-tax expense.
2. TTM is not double-counted in cumulative annual CFO/NI.
3. Invalid DOL observations stay visible and do not enter summary medians.
4. `Cash impact from ΔOWC = -ΔOWC` is displayed explicitly; reconciliation differences are not hidden.
5. CCC/OWC is N/A for identified banks/insurers/securities/financial-services models.
6. Module-1 `maintenance_capex_bil` is not imported into Chapter 6 because a generic Owner-Earnings proxy must not be relabelled as maintenance capex evidence.
7. No 0–100 score, no automatic Distribution Width, no automatic MOS change, no BUY/HOLD/SELL.

## Display contract

The V30 global format lock remains active: VND amounts are shown in tỷ đồng with 0 decimals; percentages and ratios use 1 decimal; read-only tables use the shared `st.html()` renderer with fixed layout/wrap; signed performance/cash-flow heat is contextual rather than a quality verdict.
''', encoding="utf-8")

    (ROOT / "modules/deep_company_analysis/test_chapter6_phase6b_integration.py").write_text(r'''from pathlib import Path


def test_phase6b_is_wired_to_unified_chapter6_page():
    root = Path(__file__).resolve().parent
    text = (root / "chapter6_page_support.py").read_text(encoding="utf-8")
    assert "build_chapter6_quant_context" in text
    assert "_render_phase6b_quantitative_bridge(ticker)" in text
    assert "Cập nhật canonical data Chương 6" in text
    assert "render_static_table(" in text
    assert "st.dataframe(" not in text


def test_phase6b_methodology_locks_critical_boundaries():
    root = Path(__file__).resolve().parents[2]
    formulas = (root / "docs/formulas/DEEP_COMPANY_ANALYSIS_CHAPTER6_FORMULAS.md").read_text(encoding="utf-8")
    implementation = (root / "docs/CHAPTER6_PHASE6B_IMPLEMENTATION.md").read_text(encoding="utf-8")
    combined = formulas + implementation
    assert "tax_paid_bil" in combined
    assert "Cash impact from ΔOWC = -ΔOWC" in combined
    assert "does not import Module-1 `maintenance_capex_bil`" in combined
    assert "Invalid" in combined
    assert "BUY/HOLD/SELL" in combined
''', encoding="utf-8")


def main() -> None:
    patch_quant()
    patch_page_support()
    patch_formula_doc()
    write_docs_and_test()
    print("Chapter 6 Phase 6B V31 integration script applied.")


if __name__ == "__main__":
    main()
