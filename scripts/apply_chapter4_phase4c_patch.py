from __future__ import annotations

"""Idempotently integrate automatic Q17 peer discovery + Phase 4C evidence bridge."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CH4 = ROOT / "modules" / "deep_company_analysis" / "chapter4.py"
SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter4_page_support.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Patch marker not found: {label}")
    return text.replace(old, new, 1)


def patch_chapter4() -> None:
    text = CH4.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "def save_record(payload: dict[str, Any]) -> str:\n",
        "def save_record(payload: dict[str, Any], create_snapshot: bool = True) -> str:\n",
        "save_record signature",
    )
    old = '''        conn.execute(\n            "INSERT INTO chapter4_snapshots (ticker, payload_json, understanding_status, created_at) VALUES (?, ?, ?, ?)",\n            (ticker, serialized, status, now),\n        )\n    return status\n'''
    new = '''        if create_snapshot:\n            conn.execute(\n                "INSERT INTO chapter4_snapshots (ticker, payload_json, understanding_status, created_at) VALUES (?, ?, ?, ?)",\n                (ticker, serialized, status, now),\n            )\n    return status\n'''
    text = replace_once(text, old, new, "optional system snapshot")
    CH4.write_text(text, encoding="utf-8")


def patch_support() -> None:
    text = SUPPORT.read_text(encoding="utf-8")
    import_old = '''from modules.deep_company_analysis.chapter4_quant import (\n    build_company_snapshot,\n    build_industry_distribution,\n    build_peer_benchmark,\n    build_peer_table,\n    pricing_context,\n    supply_chain_context,\n)\n'''
    import_new = import_old + '''from modules.deep_company_analysis.chapter4_peer_auto import (\n    DEFAULT_MAX_PEERS,\n    discover_same_industry_peers,\n    peer_refresh_plan,\n    refresh_peer_canonical_bundle,\n)\nfrom modules.deep_company_analysis.chapter4_evidence import (\n    Chapter4EvidenceAgent,\n    candidate_coverage,\n    merge_candidates_into_evidence_matrix,\n)\n'''
    text = replace_once(text, import_old, import_new, "Phase4C imports")

    marker = '''def _fmt(value: Any, suffix: str = "") -> str:\n'''
    helpers = '''@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)\ndef _industry_discovery_cached(ticker: str, raw_dir: str, max_peers: int = DEFAULT_MAX_PEERS):\n    discovery = discover_same_industry_peers(ticker, raw_dir, max_peers=max_peers)\n    return {\n        "target": discovery.target,\n        "industry_group": discovery.industry_group,\n        "peers": discovery.peers,\n        "tickers": discovery.tickers,\n        "note": discovery.note,\n        "raw_path": discovery.raw_path,\n        "truncated": discovery.truncated,\n    }\n\n\ndef _auto_peer_discovery(ticker: str):\n    safe = _safe_ticker(ticker)\n    try:\n        return _industry_discovery_cached(safe, str(m1.RAW_DIR), DEFAULT_MAX_PEERS)\n    except Exception as exc:\n        return {"target": safe, "industry_group": "", "peers": pd.DataFrame(), "tickers": [safe], "note": f"Không lấy được danh sách cùng ngành: {exc}", "raw_path": "", "truncated": False}\n\n\ndef _phase4c_existing_rows(record: dict[str, Any]) -> pd.DataFrame:\n    rows = record.get("evidence_matrix") if isinstance(record, dict) else []\n    if not isinstance(rows, list) or not rows:\n        return pd.DataFrame()\n    df = pd.DataFrame(rows)\n    if "Data Origin" not in df.columns:\n        return pd.DataFrame()\n    return df[df["Data Origin"].astype(str).str.contains("Chapter 4 Research Assistant Evidence Bridge", na=False)].copy()\n\n\ndef render_phase4c_evidence_bridge(ticker: str, company_name: str, industry_group: str) -> None:\n    safe = _safe_ticker(ticker)\n    record = load_record(safe, company_name)\n    existing = _phase4c_existing_rows(record)\n    with st.container(border=True):\n        st.markdown("### 🔎 Phase 4C — Research Assistant Evidence Bridge")\n        st.caption(\n            "Research Assistant tìm supporting evidence + counter-evidence cho Q15–Q20 và tự đưa vào Evidence Matrix dưới trạng thái Candidate. "\n            "Nó không được đổi Assessment, Trend, Confidence, Conclusion hay Research Gate."\n        )\n        if not existing.empty and "Question" in existing.columns:\n            counts = existing["Question"].value_counts().to_dict()\n            cols = st.columns(6)\n            for idx, q in enumerate(("Q15", "Q16", "Q17", "Q18", "Q19", "Q20")):\n                cols[idx].metric(q, int(counts.get(q, 0)))\n            st.caption(f"Đang lưu {len(existing)} evidence candidate(s) Phase 4C trong Evidence Matrix.")\n        else:\n            st.info("Chưa có evidence candidate Phase 4C được lưu cho mã này.")\n\n        if st.button("🌐 Cập nhật Evidence Q15–Q20", use_container_width=True, key=f"ch4c_refresh_evidence_{safe}"):\n            with st.spinner(f"Research Assistant đang tìm supporting/counter-evidence cho {safe}..."):\n                result = Chapter4EvidenceAgent(m1.RAW_DIR).search(safe, company_name, industry_group, max_results_per_query=4)\n                latest = load_record(safe, company_name)\n                latest = merge_candidates_into_evidence_matrix(latest, result.candidates)\n                save_record(latest, create_snapshot=False)\n                st.session_state[f"ch4c_candidates_{safe}"] = result.candidates\n                st.session_state[f"ch4c_note_{safe}"] = result.note\n            st.success(result.note)\n\n        candidates = st.session_state.get(f"ch4c_candidates_{safe}")\n        if isinstance(candidates, pd.DataFrame) and not candidates.empty:\n            coverage = candidate_coverage(candidates)\n            st.caption("Candidate coverage mới nhất: " + " | ".join(f"{q}: {coverage[q]}" for q in coverage))\n            show_cols = [c for c in ["Question", "Subtopic", "Direction", "Evidence Quality", "Explicitness", "Title", "URL", "Snippet"] if c in candidates.columns]\n            st.dataframe(candidates[show_cols].head(80), use_container_width=True, hide_index=True, height=360)\n            st.warning("Direction và Explicitness đều là Research Assistant candidate. Analyst phải mở nguồn và xác minh trước khi dùng làm kết luận.")\n        elif not existing.empty:\n            show_cols = [c for c in ["Question", "Claim", "Direction", "Evidence Type", "Source Title", "Source URL / File", "Evidence Text", "Status"] if c in existing.columns]\n            st.dataframe(existing[show_cols].tail(60), use_container_width=True, hide_index=True, height=320)\n\n\n'''
    text = replace_once(text, marker, helpers + marker, "peer/evidence helpers")

    old_setup = '''    record = load_record(safe, company_name)\n    stored = record.get("quantitative_peer_tickers", [])\n    stored_text = ", ".join(stored) if isinstance(stored, list) else str(stored or "")\n\n    with st.container(border=True):\n'''
    new_setup = '''    record = load_record(safe, company_name)\n    stored = record.get("quantitative_peer_tickers", [])\n    discovery = _auto_peer_discovery(safe)\n    industry_group = str(discovery.get("industry_group") or record.get("quantitative_industry_group") or "")\n    discovered_tickers = [_safe_ticker(x) for x in discovery.get("tickers", []) if _safe_ticker(x)]\n    fallback_tickers = _parse_peer_tickers(stored, safe)\n    peers = discovered_tickers if len(discovered_tickers) > 1 else fallback_tickers\n\n    with st.container(border=True):\n'''
    text = replace_once(text, old_setup, new_setup, "automatic discovery setup")

    old_manual = '''        peer_text = st.text_input(\n            "Peer tickers dùng cho Q17/Q19",\n            value=stored_text,\n            key=f"ch4q_peer_text_{safe}",\n            help="Nhập ticker, cách nhau bằng dấu phẩy. Target luôn được thêm tự động. Chỉ dùng peer có canonical cache; app không tự đoán peer theo tên ngành.",\n        )\n        peers = _parse_peer_tickers(peer_text, safe)\n        p1, p2 = st.columns(2)\n        if p1.button("💾 Lưu peer set", use_container_width=True, key=f"ch4q_save_peers_{safe}"):\n            record["quantitative_peer_tickers"] = [p for p in peers if p != safe]\n            save_record(record)\n            st.success("Đã lưu peer set. Đây là research configuration, không phải analyst conclusion.")\n            st.rerun()\n        p2.caption("Peer không có cache sẽ được giữ trong peer set nhưng không đưa số liệu giả vào bảng.")\n\n'''
    new_manual = '''        peer_list_df = discovery.get("peers")\n        if isinstance(peer_list_df, pd.DataFrame) and not peer_list_df.empty:\n            st.success(f"Tự nhận diện ngành: {industry_group or 'chưa rõ'} | {len(peers)} mã trong peer universe dùng cho Q17/Q19.")\n            list_cols = [c for c in ["ticker", "company_name", "exchange", "market_cap_bil", "peer_group"] if c in peer_list_df.columns]\n            st.dataframe(peer_list_df[list_cols], use_container_width=True, hide_index=True, height=min(360, 70 + 27 * len(peer_list_df)))\n            st.caption(str(discovery.get("note") or ""))\n        else:\n            st.warning(str(discovery.get("note") or "Chưa tự nhận diện được peer cùng ngành."))\n            if len(peers) > 1:\n                st.caption("Đang dùng peer set đã lưu trước đó làm fallback; không sinh peer suy đoán.")\n\n        if st.button("🔄 Tự động lấy cùng ngành + BCTC và cập nhật Q17/Q19", use_container_width=True, key=f"ch4q_auto_industry_{safe}"):\n            progress = st.progress(0.0, text="Đang cập nhật canonical BCTC cho peer cùng ngành...")\n            notes: list[str] = []\n            ok_count = 0\n            for idx, peer in enumerate(peers):\n                ok, _paths, note = refresh_peer_canonical_bundle(peer)\n                notes.append(note)\n                ok_count += int(ok)\n                progress.progress((idx + 1) / max(len(peers), 1), text=f"{peer}: {'OK' if ok else 'thiếu dữ liệu'}")\n            _snapshot_cached.clear()\n            snapshots_after = []\n            for peer in peers:\n                snap, _ = load_quant_snapshot(peer)\n                if snap:\n                    snapshots_after.append(snap)\n            peer_df_after = build_peer_table(snapshots_after)\n            latest_record = load_record(safe, company_name)\n            latest_record["quantitative_peer_tickers"] = [p for p in peers if p != safe]\n            latest_record["quantitative_industry_group"] = industry_group\n            latest_record["quantitative_peer_source"] = "Simplize same-industry universe + Trecapital canonical statements"\n            latest_record = _merge_q17_peer_rows(latest_record, peer_df_after)\n            save_record(latest_record, create_snapshot=False)\n            progress.empty()\n            st.success(f"Đã tự cập nhật {ok_count}/{len(peers)} mã; {len(peer_df_after)} mã có dữ liệu định lượng đã được đưa thẳng vào bảng Q17. Analyst Comment/kết luận được giữ nguyên.")\n            if notes:\n                with st.expander("Chi tiết cập nhật peer", expanded=False):\n                    st.write("\\n".join(f"- {x}" for x in notes))\n            st.rerun()\n\n'''
    text = replace_once(text, old_manual, new_manual, "manual peer set -> auto industry")

    old_apply = '''                if st.button("🧩 Đưa canonical peer snapshot vào bảng Q17", use_container_width=True, key=f"ch4q_apply_q17_{safe}"):\n                    latest_record = load_record(safe, company_name)\n                    latest_record["quantitative_peer_tickers"] = [p for p in peers if p != safe]\n                    latest_record = _merge_q17_peer_rows(latest_record, peer_df)\n                    save_record(latest_record)\n                    st.success("Đã cập nhật các cột định lượng Q17 từ canonical snapshot; Comment/analyst conclusion được giữ nguyên.")\n                    st.rerun()\n'''
    new_apply = '''                st.caption("Bảng editable Q17 được đồng bộ tự động khi bấm nút 'Tự động lấy cùng ngành + BCTC'; không còn bước nhập peer/copy canonical thủ công.")\n'''
    text = replace_once(text, old_apply, new_apply, "remove manual Q17 apply")

    text = replace_once(
        text,
        '''    return safe, company_name\n\n\ndef render_chapter4_tab(default_ticker: str) -> None:\n    safe, company_name = render_quantitative_bridge(default_ticker)\n    render_chapter4(default_ticker=safe, company_name=company_name)\n''',
        '''    return safe, company_name, industry_group\n\n\ndef render_chapter4_tab(default_ticker: str) -> None:\n    safe, company_name, industry_group = render_quantitative_bridge(default_ticker)\n    render_phase4c_evidence_bridge(safe, company_name, industry_group)\n    render_chapter4(default_ticker=safe, company_name=company_name)\n''',
        "Phase4C render hook",
    )
    SUPPORT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_chapter4()
    patch_support()
    print("Applied Chapter 4 auto-industry Q17 + Phase 4C Evidence Bridge patch.")
