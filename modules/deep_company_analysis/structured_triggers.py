from __future__ import annotations

from typing import Any

import streamlit as st


METRIC_OPTIONS: dict[str, dict[str, Any]] = {
    "current_price": {"label": "Giá hiện tại", "unit": "đ", "default": 80000.0, "step": 1000.0},
    "mos_pct": {"label": "MOS", "unit": "%", "default": 25.0, "step": 1.0},
    "roic_pct": {"label": "ROIC", "unit": "%", "default": 15.0, "step": 1.0},
    "debt_ebitda": {"label": "Debt/EBITDA", "unit": "x", "default": 2.0, "step": 0.1},
    "ebit_interest": {"label": "EBIT/Interest", "unit": "x", "default": 3.0, "step": 0.1},
    "fcf_yield_pct": {"label": "FCF Yield", "unit": "%", "default": 8.0, "step": 0.5},
    "valuation_percentile": {"label": "Valuation Percentile", "unit": "%", "default": 20.0, "step": 1.0},
    "drawdown_52w_pct": {"label": "52W Drawdown", "unit": "%", "default": 30.0, "step": 1.0},
}

OPERATORS = ["<", "<=", ">", ">=", "="]
TRIGGER_TYPES = [
    "Chỉ tiêu định lượng",
    "Có BCTC mới",
    "BCTC kỳ cụ thể",
    "Có Event / CBTT mới",
    "Thủ công nâng cao",
]


def _format_number(value: float, metric: str) -> str:
    if metric == "current_price":
        return f"{float(value):,.0f}".replace(",", ".")
    if abs(float(value) - round(float(value))) < 1e-9:
        return f"{float(value):.0f}"
    return f"{float(value):.1f}".replace(".", ",")


def build_numeric_trigger(metric: str, operator: str, threshold: float) -> str:
    spec = METRIC_OPTIONS[metric]
    value = _format_number(float(threshold), metric)
    unit = spec["unit"]
    if metric == "current_price":
        return f"Review khi Giá {operator} {value}"
    if unit == "%":
        return f"Review khi {spec['label']} {operator} {value}%"
    if unit == "x":
        return f"Review khi {spec['label']} {operator} {value}x"
    return f"Review khi {spec['label']} {operator} {value}"


def build_statement_period_trigger(year: int, quarter: int) -> str:
    q = min(4, max(1, int(quarter)))
    y = min(2100, max(2000, int(year)))
    return f"Review khi có BCTC Q{q}/{y}"


def _append_unique(items: list[str], value: str) -> list[str]:
    clean = str(value or "").strip()
    if clean and clean not in items:
        return [*items, clean]
    return items


def render_structured_trigger_builder(ticker: str, saved_triggers: list[str]) -> list[str]:
    """Render a controlled trigger builder and return the in-session configured triggers.

    Stored form remains a human-readable trigger string for backward compatibility with V5 SQLite.
    Parsing/evaluation belongs to monitoring.py. The builder only reduces input ambiguity.
    """
    safe = str(ticker or "").upper().strip()
    state_key = f"dca_structured_triggers_{safe}"
    if state_key not in st.session_state:
        st.session_state[state_key] = [str(x).strip() for x in saved_triggers if str(x).strip()]

    st.markdown("#### Monitoring Trigger Builder")
    st.caption(
        "Chọn trigger theo cấu trúc để tránh nhập sai cú pháp. Trigger vẫn chỉ tạo Review Queue; không tự đổi Research Gate."
    )

    with st.container(border=True):
        trigger_type = st.selectbox(
            "Loại trigger",
            TRIGGER_TYPES,
            key=f"dca_trigger_type_{safe}",
        )
        candidate = ""

        if trigger_type == "Chỉ tiêu định lượng":
            c1, c2, c3 = st.columns([2.2, 1.0, 1.5])
            with c1:
                metric = st.selectbox(
                    "Chỉ tiêu",
                    list(METRIC_OPTIONS),
                    format_func=lambda key: METRIC_OPTIONS[key]["label"],
                    key=f"dca_trigger_metric_{safe}",
                )
            with c2:
                operator = st.selectbox("Điều kiện", OPERATORS, key=f"dca_trigger_op_{safe}")
            spec = METRIC_OPTIONS[metric]
            with c3:
                threshold = st.number_input(
                    f"Ngưỡng ({spec['unit']})",
                    value=float(spec["default"]),
                    step=float(spec["step"]),
                    key=f"dca_trigger_threshold_{safe}_{metric}",
                )
            candidate = build_numeric_trigger(metric, operator, threshold)

        elif trigger_type == "Có BCTC mới":
            candidate = "Review khi có BCTC mới"
            st.info("Lần đầu engine đặt baseline kỳ BCTC hiện tại; chỉ cảnh báo khi canonical period thay đổi.")

        elif trigger_type == "BCTC kỳ cụ thể":
            c1, c2 = st.columns(2)
            with c1:
                year = st.number_input(
                    "Năm",
                    min_value=2000,
                    max_value=2100,
                    value=2026,
                    step=1,
                    key=f"dca_trigger_year_{safe}",
                )
            with c2:
                quarter = st.selectbox("Quý", [1, 2, 3, 4], key=f"dca_trigger_quarter_{safe}")
            candidate = build_statement_period_trigger(int(year), int(quarter))
            st.info("Trigger kỳ cụ thể sẽ mở Review Queue khi dữ liệu canonical đạt đúng hoặc vượt qua quý đã chọn.")

        elif trigger_type == "Có Event / CBTT mới":
            candidate = "Review khi có Event / CBTT mới"
            st.info("Event chỉ là candidate từ evidence layer; analyst phải xác minh nguồn trước khi thay đổi thesis/Gate.")

        else:
            candidate = st.text_input(
                "Trigger thủ công",
                placeholder="Ví dụ: Review khi Valuation Percentile < 15%",
                key=f"dca_trigger_manual_{safe}",
            ).strip()

        st.caption(f"Sẽ thêm: **{candidate or '—'}**")
        if st.button("➕ Thêm trigger", use_container_width=True, key=f"dca_trigger_add_{safe}"):
            st.session_state[state_key] = _append_unique(list(st.session_state[state_key]), candidate)
            st.rerun()

    configured = [str(x).strip() for x in st.session_state.get(state_key, []) if str(x).strip()]
    st.markdown("**Trigger đang cấu hình**")
    if configured:
        for index, item in enumerate(configured, start=1):
            st.markdown(f"{index}. {item}")
        selected_remove = st.multiselect(
            "Chọn trigger cần xóa",
            configured,
            key=f"dca_trigger_remove_select_{safe}",
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ Xóa trigger đã chọn", use_container_width=True, key=f"dca_trigger_remove_{safe}"):
                remove_set = set(selected_remove)
                st.session_state[state_key] = [item for item in configured if item not in remove_set]
                st.rerun()
        with c2:
            if st.button("↩ Đồng bộ từ bản đã lưu", use_container_width=True, key=f"dca_trigger_reset_{safe}"):
                st.session_state[state_key] = [str(x).strip() for x in saved_triggers if str(x).strip()]
                st.rerun()
    else:
        st.caption("Chưa cấu hình trigger.")

    return [str(x).strip() for x in st.session_state.get(state_key, []) if str(x).strip()]
