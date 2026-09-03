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
from modules.deep_company_analysis.chapter4_peer_auto import (
    DEFAULT_MAX_PEERS,
    discover_same_industry_peers,
    peer_refresh_plan,
    refresh_peer_canonical_bundle,
    refresh_peer_canonical_universe,
)
from modules.deep_company_analysis.chapter4_evidence import (
    Chapter4EvidenceAgent,
    candidate_coverage,
    merge_candidates_into_evidence_matrix,
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


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def _industry_discovery_cached(ticker: str, raw_dir: str, max_peers: int = DEFAULT_MAX_PEERS):
    discovery = discover_same_industry_peers(ticker, raw_dir, max_peers=max_peers)
    return {
        "target": discovery.target,
        "industry_group": discovery.industry_group,
        "peers": discovery.peers,
        "tickers": discovery.tickers,
        "note": discovery.note,
        "raw_path": discovery.raw_path,
        "truncated": discovery.truncated,
    }


def _auto_peer_discovery(ticker: str):
    safe = _safe_ticker(ticker)
    try:
        return _industry_discovery_cached(safe, str(m1.RAW_DIR), DEFAULT_MAX_PEERS)
    except Exception as exc:
        return {"target": safe, "industry_group": "", "peers": pd.DataFrame(), "tickers": [safe], "note": f"Không lấy được danh sách cùng ngành: {exc}", "raw_path": "", "truncated": False}


def _phase4c_existing_rows(record: dict[str, Any]) -> pd.DataFrame:
    rows = record.get("evidence_matrix") if isinstance(record, dict) else []
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if "Data Origin" not in df.columns:
        return pd.DataFrame()
    return df[df["Data Origin"].astype(str).str.contains("Chapter 4 Research Assistant Evidence Bridge", na=False)].copy()


def render_phase4c_evidence_bridge(ticker: str, company_name: str, industry_group: str) -> None:
    safe = _safe_ticker(ticker)
    record = load_record(safe, company_name)
    existing = _phase4c_existing_rows(record)
    with st.container(border=True):
        st.markdown("### 🔎 Phase 4C — Research Assistant Evidence Bridge")
        st.caption(
            "Research Assistant tìm supporting evidence + counter-evidence cho Q15–Q20 và tự đưa vào Evidence Matrix dưới trạng thái Candidate. "
            "Nó không được đổi Assessment, Trend, Confidence, Conclusion hay Research Gate."
        )
        if not existing.empty and "Question" in existing.columns:
            counts = existing["Question"].value_counts().to_dict()
            cols = st.columns(6)
            for idx, q in enumerate(("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")):
                cols[idx].metric(q, int(counts.get(q, 0)))
            st.caption(f"Đang lưu {len(existing)} evidence candidate(s) Phase 4C trong Evidence Matrix.")
        else:
            st.info("Chưa có evidence candidate Phase 4C được lưu cho mã này.")

        if st.button("🌐 Cập nhật Evidence Q15–Q20", use_container_width=True, key=f"ch4c_refresh_evidence_{safe}"):
            with st.spinner(f"Research Assistant đang tìm supporting/counter-evidence cho {safe}..."):
                result = Chapter4EvidenceAgent(m1.RAW_DIR).search(safe, company_name, industry_group, max_results_per_query=4)
                latest = load_record(safe, company_name)
                latest = merge_candidates_into_evidence_matrix(latest, result.candidates)
                save_record(latest, create_snapshot=False)
                st.session_state[f"ch4c_candidates_{safe}"] = result.candidates
                st.session_state[f"ch4c_note_{safe}"] = result.note
            st.success(result.note)

        candidates = st.session_state.get(f"ch4c_candidates_{safe}")
        if isinstance(candidates, pd.DataFrame) and not candidates.empty:
            coverage = candidate_coverage(candidates)
            st.caption("Candidate coverage mới nhất: " + " | ".join(f"{q}: {coverage[q]}" for q in coverage))
            show_cols = [c for c in ["Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness", "Title", "URL", "Snippet"] if c in candidates.columns]
            st.dataframe(candidates[show_cols].head(80), use_container_width=True, hide_index=True, height=360)
            st.warning("Direction và Explicitness đều là Research Assistant candidate. Analyst phải mở nguồn và xác minh trước khi dùng làm kết luận.")
        elif not existing.empty:
            show_cols = [c for c in ["Question", "Claim", "Direction", "Evidence Type", "Source Title", "Source URL / File", "Evidence Text", "Status"] if c in existing.columns]
            st.dataframe(existing[show_cols].tail(60), use_container_width=True, hide_index=True, height=320)


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
    discovery = _auto_peer_discovery(safe)
    industry_group = str(discovery.get("industry_group") or record.get("quantitative_industry_group") or "")
    discovered_tickers = [_safe_ticker(x) for x in discovery.get("tickers", []) if _safe_ticker(x)]
    fallback_tickers = _parse_peer_tickers(stored, safe)
    peers = discovered_tickers if len(discovered_tickers) > 1 else fallback_tickers

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

        peer_list_df = discovery.get("peers")
        if isinstance(peer_list_df, pd.DataFrame) and not peer_list_df.empty:
            st.success(f"Tự nhận diện ngành: {industry_group or 'chưa rõ'} | {len(peers)} mã trong peer universe dùng cho Q17/Q19.")
            list_cols = [c for c in ["ticker", "company_name", "exchange", "market_cap_bil", "peer_group"] if c in peer_list_df.columns]
            st.dataframe(peer_list_df[list_cols], use_container_width=True, hide_index=True, height=min(360, 70 + 27 * len(peer_list_df)))
            st.caption(str(discovery.get("note") or ""))
        else:
            st.warning(str(discovery.get("note") or "Chưa tự nhận diện được peer cùng ngành."))
            if len(peers) > 1:
                st.caption("Đang dùng peer set đã lưu trước đó làm fallback; không sinh peer suy đoán.")

        if st.button("🔄 Tự động lấy cùng ngành + BCTC và cập nhật Q17/Q19", use_container_width=True, key=f"ch4q_auto_industry_{safe}"):
            progress = st.progress(0.02, text=f"Đang cập nhật canonical BCTC cho {len(peers)} mã cùng ngành (tối đa 3 luồng)...")
            refresh_results = refresh_peer_canonical_universe(peers, max_workers=3)
            notes = [note for _peer, _ok, _paths, note in refresh_results]
            ok_count = sum(1 for _peer, ok, _paths, _note in refresh_results if ok)
            progress.progress(0.92, text="Đang dựng ROIC/CCC/margins và đồng bộ bảng Q17/Q19...")
            _snapshot_cached.clear()
            snapshots_after = []
            for peer in peers:
                snap, _ = load_quant_snapshot(peer)
                if snap:
                    snapshots_after.append(snap)
            peer_df_after = build_peer_table(snapshots_after)
            latest_record = load_record(safe, company_name)
            latest_record["quantitative_peer_tickers"] = [p for p in peers if p != safe]
            latest_record["quantitative_industry_group"] = industry_group
            latest_record["quantitative_peer_source"] = "Simplize same-industry universe + Trecapital canonical statements"
            latest_record = _merge_q17_peer_rows(latest_record, peer_df_after)
            save_record(latest_record, create_snapshot=False)
            progress.empty()
            st.success(f"Đã tự cập nhật {ok_count}/{len(peers)} mã; {len(peer_df_after)} mã có dữ liệu định lượng đã được đưa thẳng vào bảng Q17. Analyst Comment/kết luận được giữ nguyên.")
            if notes:
                with st.expander("Chi tiết cập nhật peer", expanded=False):
                    st.write("\n".join(f"- {x}" for x in notes))
            st.rerun()

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
                st.caption("Bảng editable Q17 được đồng bộ tự động khi bấm nút 'Tự động lấy cùng ngành + BCTC'; không còn bước nhập peer/copy canonical thủ công.")
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

    return safe, company_name, industry_group


def render_chapter4_tab(default_ticker: str) -> None:
    safe, company_name, industry_group = render_quantitative_bridge(default_ticker)
    render_phase4c_evidence_bridge(safe, company_name, industry_group)
    render_chapter4(default_ticker=safe, company_name=company_name)
