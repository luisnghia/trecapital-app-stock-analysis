from __future__ import annotations

from pathlib import Path


PATH = Path("modules/deep_company_analysis/chapter1.py")
text = PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"V4 patch anchor not found:\n{old[:500]}")
    text = text.replace(old, new, 1)


replace_once(
'''    auto_valuation = auto_data.get("valuation", {}) if isinstance(auto_data, dict) else {}
    auto_quality = auto_data.get("quality_suggestions", {}) if isinstance(auto_data, dict) else {}
''',
'''    auto_valuation = auto_data.get("valuation", {}) if isinstance(auto_data, dict) else {}
    auto_quality = auto_data.get("quality_suggestions", {}) if isinstance(auto_data, dict) else {}
    auto_signals = auto_data.get("opportunity_signals", {}) if isinstance(auto_data, dict) else {}
''',
)

replace_once(
'''    st.markdown("### B. Opportunity Signals")
    st.caption("Các tín hiệu dưới đây hiện cho phép nhập offline. Giai đoạn sau sẽ bridge từ Trecapital Data Layer mà không tạo nguồn dữ liệu song song.")
    sig = record.get("opportunity_signals", {})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        drawdown_52w = st.number_input("Giảm từ đỉnh 52 tuần (%)", value=float(sig.get("drawdown_52w_pct") or 0.0), step=0.1, format="%.1f", key=f"dca_dd_{ticker}")
    with c2:
        valuation_percentile = st.number_input("Valuation percentile lịch sử (%)", min_value=0.0, max_value=100.0, value=float(sig.get("valuation_percentile") or 0.0), step=1.0, format="%.1f", key=f"dca_vp_{ticker}")
    with c3:
        price_earnings_divergence = st.selectbox(
            "Giá giảm nhưng earnings/cash flow cải thiện?",
            ["— Chưa xác định", "Có", "Không"],
            index=["— Chưa xác định", "Có", "Không"].index(sig.get("price_earnings_divergence", "— Chưa xác định")) if sig.get("price_earnings_divergence", "— Chưa xác định") in ["— Chưa xác định", "Có", "Không"] else 0,
            key=f"dca_div_{ticker}",
        )
    with c4:
        special_event = st.text_input("Sự kiện/forced selling", value=str(sig.get("special_event", "")), key=f"dca_event_{ticker}")
''',
'''    st.markdown("### B. Opportunity Signals")
    st.caption(
        "Tín hiệu định lượng được prefill từ pipeline chung của Trecapital: price history FireAnt đã lưu + BCTC canonical + Table 1.2 proxy. "
        "Event Signal chỉ là ứng viên từ WebEvidence và luôn cần analyst xác minh; tất cả đều là research signal, không phải Buy Signal."
    )
    sig = record.get("opportunity_signals", {})

    def _signal_value(key: str, fallback: Any = None, *, prefer_auto: bool = True) -> Any:
        auto_value = auto_signals.get(key) if isinstance(auto_signals, dict) else None
        saved_value = sig.get(key) if isinstance(sig, dict) else None
        if prefer_auto and auto_value not in (None, ""):
            return auto_value
        if saved_value not in (None, ""):
            return saved_value
        if auto_value not in (None, ""):
            return auto_value
        return fallback

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        drawdown_52w = st.number_input(
            "Giảm từ đỉnh 52 tuần (%)",
            value=float(_signal_value("drawdown_52w_pct", 0.0) or 0.0),
            step=0.1,
            format="%.1f",
            key=f"dca_dd_{ticker}",
        )
        if auto_signals.get("high_52w") is not None:
            st.caption(
                f"52W High {_fmt_number(auto_signals.get('high_52w'), 0)} | Low {_fmt_number(auto_signals.get('low_52w'), 0)} | "
                f"as-of {auto_signals.get('price_history_as_of') or '—'} | {int(auto_signals.get('price_history_observations') or 0)} phiên"
            )
    with c2:
        valuation_percentile = st.number_input(
            "Valuation percentile lịch sử (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(_signal_value("valuation_percentile", 0.0) or 0.0),
            step=1.0,
            format="%.1f",
            key=f"dca_vp_{ticker}",
        )
        if auto_signals.get("valuation_metric"):
            st.caption(
                f"{auto_signals.get('valuation_metric')} hiện tại {_fmt_number(auto_signals.get('valuation_current'), 1)} | "
                f"{int(auto_signals.get('valuation_history_n') or 0)} kỳ lịch sử | 0%=rẻ nhất, 100%=đắt nhất"
            )
    with c3:
        divergence_options = ["— Chưa xác định", "Có", "Không"]
        divergence_default = str(_signal_value("price_earnings_divergence", "— Chưa xác định") or "— Chưa xác định")
        if divergence_default not in divergence_options:
            divergence_default = "— Chưa xác định"
        price_earnings_divergence = st.selectbox(
            "Giá giảm nhưng earnings/cash flow cải thiện?",
            divergence_options,
            index=divergence_options.index(divergence_default),
            key=f"dca_div_{ticker}",
        )
        if auto_signals.get("divergence_evidence"):
            st.caption(str(auto_signals.get("divergence_evidence")))
    with c4:
        saved_event = str(sig.get("special_event", "") or "")
        event_candidate = str(auto_signals.get("special_event", "") or "")
        event_default = saved_event or (event_candidate if not is_saved else "")
        special_event = st.text_input("Sự kiện/forced selling", value=event_default, key=f"dca_event_{ticker}")
        if event_candidate:
            st.caption(event_candidate)
            st.caption("Ứng viên tự động — phải mở nguồn/CBTT để xác minh trước khi dùng làm kết luận.")

    event_candidates = auto_signals.get("event_candidates", []) if isinstance(auto_signals, dict) else []
    if event_candidates:
        with st.expander("Event Signal — bằng chứng ứng viên", expanded=False):
            for event in event_candidates[:5]:
                st.markdown(f"- **{event.get('category') or 'Sự kiện'}:** {event.get('title') or '—'}")
                if event.get("snippet"):
                    st.caption(str(event.get("snippet")))
                if event.get("url"):
                    st.caption(f"Nguồn: {event.get('url')}")
    elif auto_data:
        st.caption("Event Signal: chưa tìm thấy ứng viên có keyword đủ rõ trong WebEvidence cache. Analyst vẫn có thể nhập thủ công.")
''',
)

replace_once(
'''                "opportunity_signals": {
                    "drawdown_52w_pct": drawdown_52w,
                    "valuation_percentile": valuation_percentile,
                    "price_earnings_divergence": price_earnings_divergence,
                    "special_event": special_event,
                },
''',
'''                "opportunity_signals": {
                    **(auto_signals if isinstance(auto_signals, dict) else {}),
                    "drawdown_52w_pct": drawdown_52w,
                    "valuation_percentile": valuation_percentile,
                    "price_earnings_divergence": price_earnings_divergence,
                    "special_event": special_event,
                },
''',
)

PATH.write_text(text, encoding="utf-8")
print(f"Patched {PATH} to Chapter 1 V4 Opportunity Signals")
