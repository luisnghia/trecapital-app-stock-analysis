from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Phase6D patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_chapter6() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter6.py"
    text = path.read_text(encoding="utf-8")
    text = _replace_once(text, "SCHEMA_VERSION = 2", "SCHEMA_VERSION = 3", "schema")
    text = _replace_once(
        text,
        "import sqlite3\n",
        "import sqlite3\n\nfrom modules.deep_company_analysis.chapter6_closure import default_final_checklist_rows, default_scenario_rows\n",
        "closure import",
    )
    text = _replace_once(
        text,
        '    "research_gaps_table": "chapter6_research_gaps",\n}',
        '    "research_gaps_table": "chapter6_research_gaps",\n'
        '    "q27_tax_footnote": "chapter6_tax_footnote",\n'
        '    "q27_unsustainable_earnings": "chapter6_unsustainable_earnings",\n'
        '    "q32_asset_replacement": "chapter6_asset_replacement",\n'
        '    "valuation_scenarios": "chapter6_valuation_scenarios",\n'
        '    "chapter6_final_checklist": "chapter6_final_checklist",\n'
        '}',
        "child tables",
    )
    text = _replace_once(
        text,
        '        "q27_reserve_rollforward": [],\n',
        '        "q27_reserve_rollforward": [],\n'
        '        "q27_tax_footnote": [],\n'
        '        "q27_unsustainable_earnings": [],\n',
        "q27 closure payload",
    )
    text = _replace_once(
        text,
        '        "q32_capex_register": [],\n',
        '        "q32_capex_register": [],\n'
        '        "q32_asset_replacement": [],\n',
        "q32 closure payload",
    )
    text = _replace_once(
        text,
        '        "earnings_distribution_matrix": _default_distribution_matrix(),\n',
        '        "earnings_distribution_matrix": _default_distribution_matrix(),\n'
        '        "valuation_scenarios": default_scenario_rows(),\n'
        '        "valuation_method_selected": "Unknown",\n'
        '        "valuation_bridge_note": "",\n'
        '        "chapter6_final_checklist": default_final_checklist_rows(),\n'
        '        "chapter6_complete_confirmed": False,\n'
        '        "chapter6_completion_note": "",\n',
        "closure defaults",
    )
    old = '''            if payload_key == "earnings_distribution_matrix" and old_schema < 2 and not rows:\n                rows = _default_distribution_matrix()\n            payload[payload_key] = rows\n'''
    new = '''            if payload_key == "earnings_distribution_matrix" and old_schema < 2 and not rows:\n                rows = _default_distribution_matrix()\n            if payload_key == "chapter6_final_checklist" and old_schema < 3 and not rows:\n                rows = default_final_checklist_rows()\n            if payload_key == "valuation_scenarios" and old_schema < 3 and not rows:\n                rows = default_scenario_rows()\n            payload[payload_key] = rows\n'''
    text = _replace_once(text, old, new, "schema-3 migration")
    path.write_text(text, encoding="utf-8")


def patch_evidence() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter6_evidence.py"
    text = path.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        '        "kiểm toán", "auditor", "inventory obsolescence", "bad debt", "phải thu khó đòi",\n',
        '        "kiểm toán", "auditor", "inventory obsolescence", "bad debt", "phải thu khó đòi",\n'
        '        "current tax", "income tax provision", "tax footnote", "thuế hiện hành", "chi phí thuế",\n'
        '        "debt retirement", "debt extinguishment", "early debt retirement", "xử lý nợ",\n',
        "Q27 focus terms",
    )
    text = _replace_once(
        text,
        '        ("Audit / accounting changes", ("auditor", "kiểm toán", "accounting policy", "chính sách kế toán", "impairment", "restructuring")),\n',
        '        ("Audit / accounting changes", ("auditor", "kiểm toán", "accounting policy", "chính sách kế toán", "impairment", "restructuring")),\n'
        '        ("Income-tax footnote", ("current tax", "income tax provision", "tax footnote", "thuế hiện hành", "chi phí thuế")),\n'
        '        ("Unsustainable earnings / debt retirement", ("debt retirement", "debt extinguishment", "early debt retirement", "xử lý nợ")),\n',
        "Q27 subtopics",
    )
    text = _replace_once(
        text,
        '            "Q27": ["revenue recognition provision depreciation accounting policy auditor", "dự phòng khấu hao ghi nhận doanh thu kiểm toán"],\n',
        '            "Q27": [\n'
        '                "revenue recognition provision depreciation accounting policy auditor current tax income tax provision tax footnote debt retirement",\n'
        '                "dự phòng khấu hao ghi nhận doanh thu kiểm toán thuế hiện hành chi phí thuế xử lý nợ",\n'
        '            ],\n',
        "Q27 focused query",
    )
    text = _replace_once(
        text,
        '        "Q27": "Verify accounting policies, estimates/reserves, auditor notes and revenue recognition in original filings.",\n',
        '        "Q27": "Verify accounting policies, Current Tax vs Income-Tax Provision, estimates/reserves, auditor notes, revenue recognition and debt-retirement/unsustainable gains in original filings.",\n',
        "Q27 research gap",
    )
    path.write_text(text, encoding="utf-8")


def patch_page_support() -> None:
    path = ROOT / "modules" / "deep_company_analysis" / "chapter6_page_support.py"
    text = path.read_text(encoding="utf-8")
    text = _replace_once(
        text,
        'from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature\n',
        'from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature\n'
        'from modules.deep_company_analysis.chapter5_quant import build_balance_sheet_context\n'
        'from modules.deep_company_analysis.chapter6_closure import (\n'
        '    TAX_FOOTNOTE_COLUMNS,\n'
        '    UNSUSTAINABLE_EARNINGS_COLUMNS,\n'
        '    ASSET_REPLACEMENT_COLUMNS,\n'
        '    VALUATION_SCENARIO_COLUMNS,\n'
        '    FINAL_CHECKLIST_COLUMNS,\n'
        '    FINAL_CHECKLIST_STATUS_OPTIONS,\n'
        '    tax_footnote_analysis,\n'
        '    asset_replacement_analysis,\n'
        '    combined_leverage_evidence,\n'
        '    valuation_method_guidance,\n'
        '    chapter6_completion_status,\n'
        ')\n',
        "page closure imports",
    )
    text = _replace_once(
        text,
        '    if "Question" in columns:\n        config["Question"] = st.column_config.TextColumn("Question", disabled=True)\n',
        '    if "Question" in columns:\n        config["Question"] = st.column_config.TextColumn("Question", disabled=True)\n'
        '    if "Source-Locked Requirement" in columns and "Status" in columns:\n'
        '        config["Status"] = st.column_config.SelectboxColumn("Status", options=list(FINAL_CHECKLIST_STATUS_OPTIONS))\n',
        "checklist status selector",
    )
    old_return = '''    return build_chapter6_quant_context(\n        safe,\n        str(getattr(company, "company_name", "") or getattr(company, "name", "") or ""),\n        annual_and_ttm,\n        industry=str(getattr(company, "industry", "") or ""),\n        sub_industry=str(getattr(company, "sub_industry", "") or ""),\n        source_label=source_label,\n        years=10,\n    )\n'''
    new_return = '''    ctx = build_chapter6_quant_context(\n        safe,\n        str(getattr(company, "company_name", "") or getattr(company, "name", "") or ""),\n        annual_and_ttm,\n        industry=str(getattr(company, "industry", "") or ""),\n        sub_industry=str(getattr(company, "sub_industry", "") or ""),\n        source_label=source_label,\n        years=10,\n    )\n    # Phase 6D reuses Chapter-5 shared balance-sheet diagnostics read-only; no duplicate leverage formula.\n    ctx["chapter5_balance_sheet_context"] = build_balance_sheet_context(annual_and_ttm, years=10)\n    return ctx\n'''
    text = _replace_once(text, old_return, new_return, "quant context leverage bridge")
    text = _replace_once(
        text,
        '    _render_phase6b_quantitative_bridge(ticker)\n    _render_phase6c_research_assistant(ticker, str(payload.get("company_name") or ""))\n',
        '    quant_ctx = _render_phase6b_quantitative_bridge(ticker)\n    _render_phase6c_research_assistant(ticker, str(payload.get("company_name") or ""))\n',
        "capture quant ctx",
    )
    if "def _render_phase6d_final_closure(" not in text:
        marker = 'def render_chapter6_tab(default_ticker: str = "") -> None:\n'
        if marker not in text:
            raise RuntimeError("Phase6D patch marker not found: render_chapter6_tab")
        function = r'''

def _render_phase6d_final_closure(ticker: str, payload: dict[str, Any], quant_ctx: dict[str, Any] | None) -> None:
    safe = _safe_ticker(ticker)
    ctx = quant_ctx if isinstance(quant_ctx, dict) else {}
    with st.container(border=True):
        st.markdown("## 🔒 Phase 6D — Chapter 6 Final Source Closure")
        st.caption(
            "Source closure theo Shearn: tax footnote, unsustainable earnings, operating leverage × debt, asset replacement, "
            "Distribution→Valuation bridge và Final Source Checklist. Analyst vẫn sở hữu toàn bộ kết luận/assumptions."
        )

        with st.expander("Q27 — Income-tax Footnote Analyzer + Unsustainable Earnings", expanded=True):
            st.caption(
                "Current Tax phải đến từ disclosure thuế hiện hành; tax paid không được dùng thay thế. Annual-only disclosure không được chế tạo TTM."
            )
            payload["q27_tax_footnote"] = _editor(
                "Current Tax vs Income-Tax Provision — 5–10Y disclosure register",
                payload.get("q27_tax_footnote"),
                TAX_FOOTNOTE_COLUMNS,
                f"dca6d_{safe}_tax",
                height=330,
            )
            tax_view = tax_footnote_analysis(payload.get("q27_tax_footnote"))
            if not tax_view.empty:
                render_static_table(tax_view, height=min(430, 90 + 29 * len(tax_view)), sort_key=f"dca6d_{safe}_tax_analysis")
            else:
                st.info("Chưa có Current Tax + Tax Provision disclosure đủ dùng; giữ N/A thay vì proxy.")

            payload["q27_unsustainable_earnings"] = _editor(
                "Unsustainable Earnings / One-off Register",
                payload.get("q27_unsustainable_earnings"),
                UNSUSTAINABLE_EARNINGS_COLUMNS,
                f"dca6d_{safe}_oneoffs",
                height=310,
            )
            st.caption(
                "Bao gồm debt-retirement gains/losses, restructuring/write-offs và temporary cuts to advertising/R&D/maintenance khi có bằng chứng."
            )

        with st.expander("Q30 — Operating Leverage × Balance-Sheet Debt", expanded=True):
            leverage = combined_leverage_evidence(
                ctx.get("q30_summary") if ctx else {},
                ctx.get("chapter5_balance_sheet_context") if ctx else None,
            )
            if not leverage.empty:
                render_static_table(leverage, height=210, sort_key=f"dca6d_{safe}_leverage")
            else:
                st.info("Chưa đủ DOL và/hoặc Chapter-5 balance-sheet context để hiển thị combined leverage evidence.")
            st.caption(
                "Không tạo distress score. Bảng chỉ đặt DOL cạnh Net Debt, Debt/EBITDA và interest coverage để analyst đánh giá rủi ro kết hợp."
            )

        with st.expander("Q32 — Asset Replacement / PP&E Age Register", expanded=True):
            payload["q32_asset_replacement"] = _editor(
                "Asset Replacement Register",
                payload.get("q32_asset_replacement"),
                ASSET_REPLACEMENT_COLUMNS,
                f"dca6d_{safe}_asset_replacement",
                height=350,
            )
            asset_view = asset_replacement_analysis(payload.get("q32_asset_replacement"))
            if not asset_view.empty:
                render_static_table(asset_view, height=min(440, 90 + 29 * len(asset_view)), sort_key=f"dca6d_{safe}_asset_analysis")
            st.caption(
                "Net/Gross PP&E chỉ là diagnostic. Phải xem asset class, land/non-depreciable assets, remaining life, replacement timing "
                "và accelerated-depreciation comparability trước khi suy replacement burden."
            )

        with st.expander("Distribution Width → Valuation Method Bridge", expanded=True):
            guidance = valuation_method_guidance(str(payload.get("earnings_distribution_width") or "Unknown"))
            st.info(f"{guidance['guidance']} | {guidance['boundary']}")
            payload["valuation_method_selected"] = _select(
                "Analyst valuation-method selection",
                payload.get("valuation_method_selected"),
                (
                    "Unknown",
                    "Point estimate / normalized earnings or FCF",
                    "Hybrid point estimate + scenarios",
                    "Bear / Base / Bull scenario analysis",
                    "Analyst custom",
                ),
                f"dca6d_{safe}_valuation_method",
            )
            payload["valuation_bridge_note"] = st.text_area(
                "Valuation-method rationale / limitation",
                value=str(payload.get("valuation_bridge_note") or ""),
                key=f"dca6d_{safe}_valuation_note",
            )
            payload["valuation_scenarios"] = _editor(
                "Bear / Base / Bull — analyst-owned scenario workspace",
                payload.get("valuation_scenarios"),
                VALUATION_SCENARIO_COLUMNS,
                f"dca6d_{safe}_scenarios",
                height=300,
            )
            st.caption("App không tự đặt probability, revenue, margin, normalized earnings/FCF, fair value hoặc MOS.")

        with st.expander("Chapter 6 Final Source Checklist & Completion Gate", expanded=True):
            payload["chapter6_final_checklist"] = _editor(
                "Source-Locked Final Checklist",
                payload.get("chapter6_final_checklist"),
                FINAL_CHECKLIST_COLUMNS,
                f"dca6d_{safe}_final_checklist",
                height=390,
            )
            status = chapter6_completion_status(payload)
            if status["blockers"]:
                st.warning("Chapter 6 chưa thể khóa Final:\n\n- " + "\n- ".join(status["blockers"]))
            else:
                st.success("Không còn blocker theo Completion Gate. Analyst có thể xác nhận Chapter 6 Complete.")
            for warning in status["warnings"]:
                st.info(warning)

            if status["ready"]:
                payload["chapter6_complete_confirmed"] = st.checkbox(
                    "✅ Analyst xác nhận Chapter 6 Complete / Source-Closed",
                    value=bool(payload.get("chapter6_complete_confirmed")),
                    key=f"dca6d_{safe}_complete",
                )
            else:
                payload["chapter6_complete_confirmed"] = False
                st.checkbox(
                    "✅ Analyst xác nhận Chapter 6 Complete / Source-Closed",
                    value=False,
                    disabled=True,
                    key=f"dca6d_{safe}_complete_disabled",
                )
            payload["chapter6_completion_note"] = st.text_area(
                "Completion note / residual uncertainty accepted by analyst",
                value=str(payload.get("chapter6_completion_note") or ""),
                key=f"dca6d_{safe}_completion_note",
            )
            final_status = chapter6_completion_status(payload)
            st.caption(f"Completion status: {final_status['status']}. Đây là research/source-completion gate, không phải Research Gate đầu tư.")

'''
        text = text.replace(marker, function + marker, 1)
    text = _replace_once(
        text,
        '    warnings = research_gap_warnings(payload)\n',
        '    _render_phase6d_final_closure(ticker, payload, quant_ctx)\n\n    warnings = research_gap_warnings(payload)\n',
        "Phase6D render call",
    )
    text = _replace_once(
        text,
        '        "Michael Shearn Q27–Q32 | Approved Phase 6A + Phase 6B canonical bridge + Phase 6C Evidence & Research Assistant. "\n',
        '        "Michael Shearn Q27–Q32 | Phase 6A + 6B canonical bridge + 6C Evidence Assistant + 6D Final Source Closure. "\n',
        "chapter caption",
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_chapter6()
    patch_evidence()
    patch_page_support()
    print("Chapter 6 Phase 6D V33 patches applied")


if __name__ == "__main__":
    main()
