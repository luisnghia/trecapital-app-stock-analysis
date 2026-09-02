from __future__ import annotations

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter1.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"V3 patch anchor not found:\n{old[:300]}")
    text = text.replace(old, new, 1)


replace_once(
'''    record: dict[str, Any] = {
        "ticker": ticker,
        "company_name": "",
''',
'''    record: dict[str, Any] = {
        "ticker": ticker,
        "_exists": False,
        "company_name": "",
''',
)

replace_once(
'''        if row:
            record.update(
                {
                    "company_name": row["company_name"],
''',
'''        if row:
            record["_exists"] = True
            record.update(
                {
                    "company_name": row["company_name"],
''',
)

replace_once(
'''def render_chapter1(default_ticker: str = "") -> None:
    init_db()
''',
'''def render_chapter1(default_ticker: str = "", auto_data: dict[str, Any] | None = None, auto_company_name: str = "") -> None:
    init_db()
    auto_data = auto_data or {}
    auto_valuation = auto_data.get("valuation", {}) if isinstance(auto_data, dict) else {}
    auto_quality = auto_data.get("quality_suggestions", {}) if isinstance(auto_data, dict) else {}
''',
)

replace_once(
'''    record = load_record(ticker)
    with top2:
        company_name = st.text_input("Tên doanh nghiệp", value=record.get("company_name", ""), key=f"dca_company_{ticker}")
''',
'''    record = load_record(ticker)
    is_saved = bool(record.get("_exists"))
    with top2:
        company_default = record.get("company_name", "") or (auto_company_name if not is_saved else "")
        company_name = st.text_input("Tên doanh nghiệp", value=company_default, key=f"dca_company_{ticker}")
''',
)

replace_once(
'''    st.markdown("### C. Quality Filter — Table 1.1")
    st.caption("AI Suggested chưa bật ở bản offline này. Analyst Assessment là kết luận chính thức. Confidence chỉ còn 3 mức: Thấp / Trung bình / Cao và không cộng vào Quality Score.")
    quality: dict[str, dict[str, Any]] = {}
    header = st.columns([2.2, 1.1, 1, 3])
    header[0].markdown("**Tiêu chí**")
    header[1].markdown("**Analyst**")
    header[2].markdown("**Confidence**")
    header[3].markdown("**Evidence / Note**")
''',
'''    st.markdown("### C. Quality Filter — Table 1.1")
    st.caption(
        "Data Suggested dùng dữ liệu canonical Trecapital cho 4 tiêu chí định lượng. "
        "Nếu ticker chưa từng được lưu, app prefill đề xuất để analyst kiểm tra; bản đã lưu không bao giờ bị ghi đè. "
        "Confidence chỉ có Thấp / Trung bình / Cao và không cộng vào Quality Score."
    )
    quality: dict[str, dict[str, Any]] = {}
    header = st.columns([2.0, 1.25, 1.05, 1.0, 2.8])
    header[0].markdown("**Tiêu chí**")
    header[1].markdown("**Data Suggested**")
    header[2].markdown("**Analyst**")
    header[3].markdown("**Confidence**")
    header[4].markdown("**Evidence / Note**")
''',
)

replace_once(
'''    for code, book_label, vi_label in QUALITY_CRITERIA:
        item = record["quality"].get(code, {"status": "— Chưa biết", "confidence": 1, "note": ""})
        cols = st.columns([2.2, 1.1, 1, 3])
        with cols[0]:
            st.markdown(f"**{book_label}**  \\n{vi_label}")
        with cols[1]:
            current_status = item.get("status", "— Chưa biết")
            status = st.selectbox(
                f"Trạng thái {book_label}",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
                label_visibility="collapsed",
                key=f"dca_q_status_{ticker}_{code}",
            )
        with cols[2]:
            current_confidence = _normalize_confidence(item.get("confidence", 1))
            confidence = st.selectbox(
                f"Confidence {book_label}",
                list(CONFIDENCE_LEVELS),
                index=list(CONFIDENCE_LEVELS).index(current_confidence),
                format_func=lambda level: CONFIDENCE_LEVELS[level],
                label_visibility="collapsed",
                key=f"dca_q_conf_{ticker}_{code}",
            )
        with cols[3]:
            note = st.text_input(
                f"Note {book_label}", value=str(item.get("note", "")), label_visibility="collapsed", key=f"dca_q_note_{ticker}_{code}"
            )
        quality[code] = {"status": status, "confidence": confidence, "note": note}
''',
'''    for code, book_label, vi_label in QUALITY_CRITERIA:
        item = record["quality"].get(code, {"status": "— Chưa biết", "confidence": 1, "note": ""})
        suggested = auto_quality.get(code, {}) if isinstance(auto_quality, dict) else {}
        cols = st.columns([2.0, 1.25, 1.05, 1.0, 2.8])
        with cols[0]:
            st.markdown(f"**{book_label}**  \\n{vi_label}")
        with cols[1]:
            if suggested:
                suggested_status = str(suggested.get("status", "— Chưa biết"))
                st.markdown(f"**{suggested_status}**")
                st.caption(f"Nguồn: Trecapital | {_confidence_label(suggested.get('confidence', 1))}")
            else:
                st.markdown("—")
        with cols[2]:
            current_status = item.get("status", "— Chưa biết")
            if not is_saved and suggested and current_status == "— Chưa biết":
                current_status = str(suggested.get("status", current_status))
            status = st.selectbox(
                f"Trạng thái {book_label}",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(current_status) if current_status in STATUS_OPTIONS else 0,
                label_visibility="collapsed",
                key=f"dca_q_status_{ticker}_{code}",
            )
        with cols[3]:
            current_confidence = _normalize_confidence(item.get("confidence", 1))
            if not is_saved and suggested:
                current_confidence = _normalize_confidence(suggested.get("confidence", current_confidence))
            confidence = st.selectbox(
                f"Confidence {book_label}",
                list(CONFIDENCE_LEVELS),
                index=list(CONFIDENCE_LEVELS).index(current_confidence),
                format_func=lambda level: CONFIDENCE_LEVELS[level],
                label_visibility="collapsed",
                key=f"dca_q_conf_{ticker}_{code}",
            )
        with cols[4]:
            note_default = str(item.get("note", ""))
            if not is_saved and not note_default and suggested:
                note_default = str(suggested.get("evidence", ""))
            note = st.text_input(
                f"Note {book_label}", value=note_default, label_visibility="collapsed", key=f"dca_q_note_{ticker}_{code}"
            )
            if suggested and suggested.get("rule"):
                st.caption(str(suggested.get("rule")))
        quality[code] = {"status": status, "confidence": confidence, "note": note}
''',
)

replace_once(
'''    st.markdown("### E. Valuation Snapshot — Table 1.2 bridge")
    valuation = record.get("valuation", {})
    r1 = st.columns(4)
    with r1[0]:
        current_price = st.number_input("Giá hiện tại", min_value=0.0, value=float(valuation.get("current_price") or 0.0), step=100.0, key=f"dca_price_{ticker}")
    with r1[1]:
        target_price = st.number_input("Target Price", min_value=0.0, value=float(valuation.get("target_price") or 0.0), step=100.0, key=f"dca_target_{ticker}")
    with r1[2]:
        fcf_yield_pct = st.number_input("FCF Yield (%)", value=float(valuation.get("fcf_yield_pct") or 0.0), step=0.1, format="%.1f", key=f"dca_fcfy_{ticker}")
    with r1[3]:
        dividend_yield_pct = st.number_input("Dividend Yield (%)", value=float(valuation.get("dividend_yield_pct") or 0.0), step=0.1, format="%.1f", key=f"dca_divy_{ticker}")
    r2 = st.columns(4)
    with r2[0]:
        tev_ebit = st.number_input("TEV / EBIT (x)", value=float(valuation.get("tev_ebit") or 0.0), step=0.1, format="%.1f", key=f"dca_te_{ticker}")
    with r2[1]:
        tev_ebitda = st.number_input("TEV / EBITDA (x)", value=float(valuation.get("tev_ebitda") or 0.0), step=0.1, format="%.1f", key=f"dca_tebitda_{ticker}")
    with r2[2]:
        debt_ebitda = st.number_input("Debt / EBITDA (x)", value=float(valuation.get("debt_ebitda") or 0.0), step=0.1, format="%.1f", key=f"dca_debt_{ticker}")
    with r2[3]:
        ebit_interest = st.number_input("EBIT / Interest (x)", value=float(valuation.get("ebit_interest") or 0.0), step=0.1, format="%.1f", key=f"dca_interest_{ticker}")
''',
'''    st.markdown("### E. Valuation Snapshot — Table 1.2 bridge")
    valuation = record.get("valuation", {})

    def _auto_value(key: str, fallback: float = 0.0) -> float:
        if key in valuation and valuation.get(key) is not None:
            return float(valuation.get(key))
        value = auto_valuation.get(key) if isinstance(auto_valuation, dict) else None
        return fallback if value is None else float(value)

    if auto_valuation:
        st.caption(
            f"Prefill từ Trecapital canonical data | kỳ {auto_data.get('as_of') or '—'} | "
            f"nguồn {auto_data.get('source_module') or 'Trecapital'}. Analyst có thể chỉnh trước khi lưu snapshot."
        )
    else:
        st.caption("Chưa có canonical data cho ticker này; các ô vẫn cho phép analyst nhập thủ công.")

    r1 = st.columns(4)
    with r1[0]:
        current_price = st.number_input("Giá hiện tại", min_value=0.0, value=_auto_value("current_price"), step=100.0, key=f"dca_price_{ticker}")
    with r1[1]:
        target_price = st.number_input("Target Price", min_value=0.0, value=_auto_value("target_price"), step=100.0, key=f"dca_target_{ticker}")
    with r1[2]:
        fcf_yield_pct = st.number_input("FCF Yield (%)", value=_auto_value("fcf_yield_pct"), step=0.1, format="%.1f", key=f"dca_fcfy_{ticker}")
    with r1[3]:
        dividend_yield_pct = st.number_input("Dividend Yield (%)", value=_auto_value("dividend_yield_pct"), step=0.1, format="%.1f", key=f"dca_divy_{ticker}")
    r2 = st.columns(4)
    with r2[0]:
        tev_ebit = st.number_input("TEV / EBIT (x)", value=_auto_value("tev_ebit"), step=0.1, format="%.1f", key=f"dca_te_{ticker}")
    with r2[1]:
        tev_ebitda = st.number_input("TEV / EBITDA (x)", value=_auto_value("tev_ebitda"), step=0.1, format="%.1f", key=f"dca_tebitda_{ticker}")
    with r2[2]:
        debt_ebitda = st.number_input("Debt / EBITDA (x)", value=_auto_value("debt_ebitda"), step=0.1, format="%.1f", key=f"dca_debt_{ticker}")
    with r2[3]:
        ebit_interest = st.number_input("EBIT / Interest (x)", value=_auto_value("ebit_interest"), step=0.1, format="%.1f", key=f"dca_interest_{ticker}")

    source_notes = auto_data.get("source_notes", []) if isinstance(auto_data, dict) else []
    if source_notes:
        with st.expander("Nguồn & reconciliation notes từ Trecapital", expanded=False):
            for source_note in source_notes:
                st.markdown(f"- {source_note}")
''',
)

PATH.write_text(text, encoding="utf-8")
print(f"Patched {PATH} to Chapter 1 V3")
