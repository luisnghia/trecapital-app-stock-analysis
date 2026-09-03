from __future__ import annotations

"""Unified-page support for Chapter 4 Phase 4B quantitative bridge."""

from typing import Any

import pandas as pd
import streamlit as st

import module1_dashboard as m1
from module1_engine import append_ttm_row
from modules.deep_company_analysis.chapter2_page_support import _active_paths, _path_signature
from modules.deep_company_analysis.chapter4 import INDUSTRY_PEER_COLUMNS, load_record, render_chapter4, save_record
from modules.deep_company_analysis.chapter4_quant import (
    build_company_snapshot,
    build_industry_distribution,
    build_peer_benchmark,
    build_peer_table,
    pricing_context,
    supply_chain_context,
)


def _safe_ticker(value: str) -> str:
    try:
        return m1._safe_ticker(value)
    except Exception:
        return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


@st.cache_data(ttl=120, show_spinner=False)
def _snapshot_cached(
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
    annual = append_ttm_row(annual_raw, quarterly)
    company_name = str(getattr(company, "company_name", "") or getattr(company, "name", "") or "")
    return build_company_snapshot(safe, company_name, annual, source_label=source_label)


def load_quant_snapshot(ticker: str):
    safe = _safe_ticker(ticker)
    paths, source_label = _active_paths(safe)
    if not paths:
        return None, f"{safe}: chưa có canonical statement cache trên máy."
    overview, year, quarter = paths
    try:
        snapshot = _snapshot_cached(
            safe,
            str(overview),
            str(year),
            str(quarter),
            _path_signature(overview),
            _path_signature(year),
            _path_signature(quarter),
            source_label,
        )
        return snapshot or None, "" if snapshot else f"{safe}: canonical bundle chưa có dữ liệu usable."
    except Exception as exc:
        return None, f"{safe}: không dựng được quantitative snapshot: {exc}"


def _parse_peer_tickers(value: Any, target: str) -> list[str]:
    if isinstance(value, list):
        raw = value
    else:
        text = str(value or "").replace(";", ",").replace("\n", ",")
        raw = [part.strip() for part in text.split(",")]
    out: list[str] = []
    for item in [target, *raw]:
        safe = _safe_ticker(str(item))
        if len(safe) >= 3 and safe not in out:
            out.append(safe)
        if len(out) >= 12:
            break
    return out


def _fmt(value: Any, suffix: str = "") -> str:
    try:
        if value is None or pd.isna(value):
            return "—"
        return f"{float(value):,.1f}{suffix}"
    except Exception:
        return "—"


def _styled_numeric(df: pd.DataFrame):
    if df is None or df.empty:
        return df
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    styler = df.style.format({c: "{:,.1f}" for c in numeric_cols}, na_rep="—")
    if numeric_cols:
        def _heat(v):
            try:
                value = float(v)
            except Exception:
                return ""
            if value < 0:
                return "color:#B91C1C;font-weight:700;"
            if value > 0:
                return "color:#047857;"
            return ""
        styler = styler.map(_heat, subset=numeric_cols)
    return styler


def _merge_q17_peer_rows(record: dict[str, Any], peer_df: pd.DataFrame) -> dict[str, Any]:
    """Refresh only canonical numeric columns, preserving analyst comments/unmatched rows."""
    existing = record.get("q17_industry_peers") if isinstance(record, dict) else []
    existing = existing if isinstance(existing, list) else []
    existing_by_company = {
        _safe_ticker(str(row.get("Company") or "")): row
        for row in existing if isinstance(row, dict) and _safe_ticker(str(row.get("Company") or ""))
    }
    generated: list[dict[str, Any]] = []
    if isinstance(peer_df, pd.DataFrame) and not peer_df.empty:
        for _, item in peer_df.iterrows():
            ticker = _safe_ticker(str(item.get("Company") or ""))
            if not ticker:
                continue
            old = existing_by_company.get(ticker, {})
            row = {col: old.get(col, "") for col in INDUSTRY_PEER_COLUMNS}
            row.update({
                "Company": ticker,
                "ROIC Latest": item.get("ROIC Latest"),
                "ROIC 5Y Median": item.get("ROIC 5Y Median"),
                "ROIC 10Y Median": item.get("ROIC 10Y Median"),
                "ROIC Min": item.get("ROIC Min"),
                "ROIC Max": item.get("ROIC Max"),
                "EBIT Margin": item.get("EBIT Margin"),
                "CCC": item.get("CCC"),
                "Comment": old.get("Comment", ""),
            })
            generated.append(row)
    generated_tickers = {_safe_ticker(str(row.get("Company") or "")) for row in generated}
    for row in existing:
        if not isinstance(row, dict):
            continue
        key = _safe_ticker(str(row.get("Company") or ""))
        if not key or key not in generated_tickers:
            generated.append(row)
    record["q17_industry_peers"] = generated
    return record


def _refresh_target_data(ticker: str) -> tuple[bool, str]:
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
            _snapshot_cached.clear()
            return True, f"Đã cập nhật canonical data cho {safe}."
        return False, f"Chưa lấy được canonical data cho {safe}; app không dùng dữ liệu mã khác thay thế."
    except Exception as exc:
        return False, f"Cập nhật canonical data chưa thành công: {exc}"


def render_quantitative_bridge(ticker: str) -> tuple[str, str]:
    safe = _safe_ticker(ticker) or "DGC"
    target_snapshot, target_error = load_quant_snapshot(safe)
    company_name = str((target_snapshot or {}).get("company_name") or "")
    record = load_record(safe, company_name)
    stored = record.get("quantitative_peer_tickers", [])
    stored_text = ", ".join(stored) if isinstance(stored, list) else str(stored or "")

    with st.container(border=True):
        st.markdown("### 📊 Phase 4B — Quantitative Bridge từ Trecapital canonical data")
        st.caption(
            "Data Suggested chỉ cung cấp lịch sử margins/ROIC/CCC/inventory turnover và peer distribution. "
            "Không tự kết luận moat, Pricing Power, Good/Bad Industry, Competition hay Supplier Quality."
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            if target_snapshot:
                prov = target_snapshot.get("provenance", {})
                st.success(
                    f"{safe} — {company_name or 'Doanh nghiệp'} | kỳ dữ liệu {target_snapshot.get('latest_period') or '—'} | "
                    f"{prov.get('source_label') or 'Trecapital'}"
                )
            else:
                st.warning(target_error)
        with c2:
            if st.button("🔄 Cập nhật data target", use_container_width=True, key=f"ch4q_refresh_target_{safe}"):
                with st.spinner(f"Đang cập nhật {safe}..."):
                    ok, note = _refresh_target_data(safe)
                (st.success if ok else st.warning)(note)
                if ok:
                    st.rerun()

        peer_text = st.text_input(
            "Peer tickers dùng cho Q17/Q19",
            value=stored_text,
            key=f"ch4q_peer_text_{safe}",
            help="Nhập ticker, cách nhau bằng dấu phẩy. Target luôn được thêm tự động. Chỉ dùng peer có canonical cache; app không tự đoán peer theo tên ngành.",
        )
        peers = _parse_peer_tickers(peer_text, safe)
        p1, p2 = st.columns(2)
        if p1.button("💾 Lưu peer set", use_container_width=True, key=f"ch4q_save_peers_{safe}"):
            record["quantitative_peer_tickers"] = [p for p in peers if p != safe]
            save_record(record)
            st.success("Đã lưu peer set. Đây là research configuration, không phải analyst conclusion.")
            st.rerun()
        p2.caption("Peer không có cache sẽ được giữ trong peer set nhưng không đưa số liệu giả vào bảng.")

        snapshots: list[dict[str, Any]] = []
        missing: list[str] = []
        for peer in peers:
            snap, _ = load_quant_snapshot(peer)
            if snap:
                snapshots.append(snap)
            else:
                missing.append(peer)
        peer_df = build_peer_table(snapshots)

        if target_snapshot:
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("ROIC latest", _fmt(target_snapshot.get("roic_latest"), "%"))
            k2.metric("Gross Margin", _fmt(target_snapshot.get("gross_margin_latest"), "%"))
            k3.metric("EBIT Margin", _fmt(target_snapshot.get("ebit_margin_latest"), "%"))
            k4.metric("CCC", _fmt(target_snapshot.get("ccc_latest"), " ngày"))
            k5.metric("Inventory Turns", _fmt(target_snapshot.get("inventory_turnover_latest"), "x"))

        if missing:
            st.info("Peer chưa có canonical cache nên chưa dùng định lượng: " + ", ".join(missing))

        with st.expander("Q16 — Historical margin context (không suy Pricing Power)", expanded=False):
            context = pricing_context(target_snapshot or {})
            if context.empty:
                st.caption("Chưa có lịch sử canonical đủ dùng.")
            else:
                st.dataframe(_styled_numeric(context), use_container_width=True, hide_index=True)
            st.caption(
                "Gross/EBIT margin chỉ là bằng chứng hỗ trợ. Không được suy 'đã tăng giá' hoặc 'có Pricing Power' từ margin tăng. "
                "Pricing Event vẫn cần explicit price/volume/customer evidence."
            )

        with st.expander("Q17 — Industry ROIC Distribution / Peer Economics", expanded=True):
            if peer_df.empty:
                st.caption("Chưa có peer canonical data.")
            else:
                display_cols = [c for c in (
                    "Company", "Company Name", "ROIC Latest", "ROIC 5Y Median", "ROIC 10Y Median",
                    "ROIC Min", "ROIC Max", "EBIT Margin", "CCC", "Data Period"
                ) if c in peer_df.columns]
                st.dataframe(_styled_numeric(peer_df[display_cols]), use_container_width=True, hide_index=True)
                dist = build_industry_distribution(peer_df)
                if dist:
                    d1, d2, d3, d4, d5 = st.columns(5)
                    d1.metric("Peer có ROIC", dist.get("peer_count", 0))
                    d2.metric("Median ROIC", _fmt(dist.get("median_roic"), "%"))
                    d3.metric("P25 / P75", f"{_fmt(dist.get('p25_roic'), '%')} / {_fmt(dist.get('p75_roic'), '%')}")
                    d4.metric("ROIC Spread", _fmt(dist.get("spread_roic"), " đpt"))
                    d5.metric("ROIC dương", _fmt(dist.get("positive_roic_pct"), "%"))
                if len(peer_df) < 3:
                    st.warning("Peer set còn nhỏ; chưa nên xem đây là đại diện cho economics toàn ngành.")
                if st.button("🧩 Đưa canonical peer snapshot vào bảng Q17", use_container_width=True, key=f"ch4q_apply_q17_{safe}"):
                    latest_record = load_record(safe, company_name)
                    latest_record["quantitative_peer_tickers"] = [p for p in peers if p != safe]
                    latest_record = _merge_q17_peer_rows(latest_record, peer_df)
                    save_record(latest_record)
                    st.success("Đã cập nhật các cột định lượng Q17 từ canonical snapshot; Comment/analyst conclusion được giữ nguyên.")
                    st.rerun()
            st.caption("Peer distribution là Data Suggested. 'Good / Mixed / Bad Industry' chỉ Analyst được chọn.")

        with st.expander("Q19 — Table 4.2 quantitative peer benchmark", expanded=False):
            bench = build_peer_benchmark(peer_df, safe)
            if bench.empty:
                st.caption("Chưa có peer canonical data để dựng benchmark.")
            else:
                st.dataframe(_styled_numeric(bench), use_container_width=True, hide_index=True)
            st.caption(
                "Peer Min/Max chỉ là mô tả. App không tự gọi Max hoặc Min là 'Ideal'. Analyst phải xác định doanh nghiệp/đặc tính chuẩn ngành và lý do."
            )

        with st.expander("Q20 — Supply-chain operating context", expanded=False):
            supply = supply_chain_context(target_snapshot or {})
            if supply.empty:
                st.caption("Chưa có canonical inventory/receivable/payable data đủ để tính lịch sử.")
            else:
                st.dataframe(_styled_numeric(supply), use_container_width=True, hide_index=True)
            st.caption(
                "Inventory Turnover và CCC là operating evidence. DPO tăng không tự động nghĩa là supplier relationship tốt; "
                "Supplier Reliability/Relationship/Concentration vẫn là analyst judgement dựa trên disclosure/evidence."
            )

        if snapshots:
            with st.expander("🔎 Data provenance — Phase 4B", expanded=False):
                prov_rows = []
                for snap in snapshots:
                    prov = snap.get("provenance", {})
                    prov_rows.append({
                        "Ticker": snap.get("ticker"),
                        "Doanh nghiệp": snap.get("company_name"),
                        "Kỳ dữ liệu": snap.get("latest_period"),
                        "Source Module": prov.get("source_module"),
                        "Data Origin": prov.get("data_origin"),
                        "Source Label": prov.get("source_label"),
                    })
                st.dataframe(pd.DataFrame(prov_rows), use_container_width=True, hide_index=True)

    return safe, company_name


def render_chapter4_tab(default_ticker: str) -> None:
    safe, company_name = render_quantitative_bridge(default_ticker)
    render_chapter4(default_ticker=safe, company_name=company_name)
