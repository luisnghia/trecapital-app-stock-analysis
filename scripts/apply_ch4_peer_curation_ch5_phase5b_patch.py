from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CH5 = ROOT / "modules" / "deep_company_analysis" / "chapter5.py"
CH4_SUPPORT = ROOT / "modules" / "deep_company_analysis" / "chapter4_page_support.py"
PAGE = ROOT / "pages" / "07_Phan_tich_chuyen_sau_doanh_nghiep.py"

# ---------------------------------------------------------------------------
# 1) Q23: hide Origin from the Risk editor while retaining internal provenance.
# ---------------------------------------------------------------------------
text = CH5.read_text(encoding="utf-8")
if "RISK_UI_COLUMNS" not in text:
    marker = '''RISK_COLUMNS = [
    "Risk", "Risk (VI)", "Origin", "Applicability", "Exposure Mechanism", "Frequency",
    "Severity", "Historical Company Evidence", "Peer / Historical Case", "Financial Consequence",
    "Mitigation", "Mitigation Evidence", "Early Warning Indicator", "Review Trigger",
    "Counter-Evidence", "Trend", "Analyst Assessment", "Evidence",
]
'''
    replacement = marker + '''\n# UI intentionally hides Origin to reduce clutter. Provenance is reconstructed internally on save:\n# known Shearn rows => Shearn; all other rows => Analyst-defined.\nRISK_UI_COLUMNS = [column for column in RISK_COLUMNS if column != "Origin"]\n'''
    if marker not in text:
        raise SystemExit("chapter5.py: RISK_COLUMNS marker not found")
    text = text.replace(marker, replacement, 1)

old_editor = '''risk_df = _editor("Risk Underwriter Register — Shearn defaults chỉ seed khi tạo mới + Analyst-defined risks", record.get("q23_risks", []), RISK_COLUMNS, f"{prefix}_q23_risks", 520)'''
new_editor = '''risk_df = _editor("Risk Underwriter Register — Shearn defaults chỉ seed khi tạo mới + analyst-added risks", record.get("q23_risks", []), RISK_UI_COLUMNS, f"{prefix}_q23_risks", 520)'''
if old_editor in text:
    text = text.replace(old_editor, new_editor, 1)
elif "RISK_UI_COLUMNS" not in text[text.find("with st.expander(\"Q23"):text.find("with st.expander(\"Q24")]:
    raise SystemExit("chapter5.py: Q23 editor marker not found")

old_help = '''Rủi ro đã xóa sẽ không tự xuất hiện lại khi lưu/mở lại; dòng mới được lưu là `Analyst-defined`.'''
new_help = '''Rủi ro đã xóa sẽ không tự xuất hiện lại khi lưu/mở lại. Cột nguồn được ẩn khỏi bảng để gọn hơn; app vẫn lưu provenance nội bộ.''' 
text = text.replace(old_help, new_help)
CH5.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# 2) Chapter 4: analyst-curated peer set before canonical refresh.
# ---------------------------------------------------------------------------
text = CH4_SUPPORT.read_text(encoding="utf-8")
import_marker = '''    refresh_peer_canonical_universe,\n)\nfrom modules.deep_company_analysis.chapter4_evidence import ('''
import_replacement = '''    refresh_peer_canonical_universe,\n)\nfrom modules.deep_company_analysis.chapter4_peer_selection import (\n    PEER_SELECTION_COLUMNS,\n    build_peer_selection_table,\n    normalize_ticker_list,\n    selected_peer_tickers,\n)\nfrom modules.deep_company_analysis.chapter4_evidence import ('''
if "chapter4_peer_selection" not in text:
    if import_marker not in text:
        raise SystemExit("chapter4_page_support.py: peer import marker not found")
    text = text.replace(import_marker, import_replacement, 1)

# Make the merge helper able to remove peers the analyst excluded while preserving comments for retained peers.
text = text.replace(
    '''def _merge_q17_peer_rows(record: dict[str, Any], peer_df: pd.DataFrame) -> dict[str, Any]:\n    """Refresh only canonical numeric columns, preserving analyst comments/unmatched rows."""''',
    '''def _merge_q17_peer_rows(record: dict[str, Any], peer_df: pd.DataFrame, preserve_unmatched: bool = True) -> dict[str, Any]:\n    """Refresh canonical numeric columns while preserving comments for retained peers.\n\n    ``preserve_unmatched=False`` is used after analyst-curated peer confirmation so removed peers\n    do not silently come back into Q17.\n    """''',
    1,
)
old_tail = '''    generated_tickers = {_safe_ticker(str(row.get("Company") or "")) for row in generated}\n    for row in existing:\n        if not isinstance(row, dict):\n            continue\n        key = _safe_ticker(str(row.get("Company") or ""))\n        if not key or key not in generated_tickers:\n            generated.append(row)\n    record["q17_industry_peers"] = generated\n    return record'''
new_tail = '''    generated_tickers = {_safe_ticker(str(row.get("Company") or "")) for row in generated}\n    if preserve_unmatched:\n        for row in existing:\n            if not isinstance(row, dict):\n                continue\n            key = _safe_ticker(str(row.get("Company") or ""))\n            if not key or key not in generated_tickers:\n                generated.append(row)\n    record["q17_industry_peers"] = generated\n    return record'''
if old_tail in text:
    text = text.replace(old_tail, new_tail, 1)
elif "if preserve_unmatched:" not in text:
    raise SystemExit("chapter4_page_support.py: merge tail marker not found")

new_render = r'''def render_quantitative_bridge(ticker: str) -> tuple[str, str, str]:
    safe = _safe_ticker(ticker) or "DGC"
    target_snapshot, target_error = load_quant_snapshot(safe)
    company_name = str((target_snapshot or {}).get("company_name") or "")
    record = load_record(safe, company_name)

    stored_peers = record.get("quantitative_peer_tickers", [])
    if not isinstance(stored_peers, list):
        stored_peers = []
    confirmed_peers = normalize_ticker_list(stored_peers, safe, max_peers=DEFAULT_MAX_PEERS)
    industry_group = str(record.get("quantitative_industry_group") or "")

    discovery_key = f"ch4q_discovery_{safe}"
    selection_key = f"ch4q_selection_seed_{safe}"
    version_key = f"ch4q_selection_version_{safe}"
    discovery = st.session_state.get(discovery_key)

    with st.container(border=True):
        st.markdown("### 📊 Phase 4B — Quantitative Bridge từ Trecapital canonical data")
        st.caption(
            "Q17/Q19 dùng quy trình 2 bước: (1) tải danh sách cùng ngành để Analyst lọc/thêm/bớt; "
            "(2) chỉ khi bấm Xác nhận & cập nhật thì app mới tải BCTC canonical cho danh sách đã chọn. "
            "Không tự kết luận Good/Bad Industry, Competition hay Ideal Company."
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

        st.markdown("#### Bước 1 — Tải và lọc danh sách doanh nghiệp cùng ngành")
        l1, l2 = st.columns([2, 3])
        with l1:
            load_clicked = st.button(
                "1️⃣ Tải / tải lại danh sách cùng ngành",
                use_container_width=True,
                key=f"ch4q_load_industry_{safe}",
            )
        with l2:
            if confirmed_peers:
                st.info(
                    f"Peer set đã xác nhận đang dùng: {len(confirmed_peers) - 1} peer + {safe} target. "
                    "Danh sách này không tự mở rộng khi nguồn discovery xuất hiện mã mới."
                )
            else:
                st.caption("Chưa có peer set đã xác nhận; Q17 chỉ dùng target cho đến khi Analyst xác nhận.")

        if load_clicked:
            try:
                _industry_discovery_cached.clear()
            except Exception:
                pass
            discovery = _auto_peer_discovery(safe)
            st.session_state[discovery_key] = discovery
            peer_df_seed = discovery.get("peers") if isinstance(discovery, dict) else pd.DataFrame()
            if not isinstance(peer_df_seed, pd.DataFrame):
                peer_df_seed = pd.DataFrame()
            saved_for_seed = stored_peers if stored_peers else None
            st.session_state[selection_key] = build_peer_selection_table(peer_df_seed, safe, saved_for_seed)
            st.session_state[version_key] = int(st.session_state.get(version_key, 0)) + 1
            if isinstance(discovery, dict):
                industry_group = str(discovery.get("industry_group") or industry_group)

        selection_df = None
        if isinstance(discovery, dict):
            industry_group = str(discovery.get("industry_group") or industry_group)
            seed = st.session_state.get(selection_key)
            if not isinstance(seed, pd.DataFrame):
                peer_df_seed = discovery.get("peers")
                if not isinstance(peer_df_seed, pd.DataFrame):
                    peer_df_seed = pd.DataFrame()
                seed = build_peer_selection_table(peer_df_seed, safe, stored_peers if stored_peers else None)
                st.session_state[selection_key] = seed
            st.success(
                f"Nguồn discovery nhận diện: {industry_group or 'chưa rõ'} | "
                f"{max(0, len(seed) - 1)} candidate peer. Hãy bỏ chọn/xóa peer không sát hoặc thêm mã mới trước khi cập nhật dữ liệu."
            )
            version = int(st.session_state.get(version_key, 0))
            selection_df = st.data_editor(
                seed,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                height=min(500, 90 + 29 * max(1, len(seed))),
                key=f"ch4q_peer_editor_{safe}_{version}",
                column_config={
                    "Use?": st.column_config.CheckboxColumn("Dùng?", help="Chỉ các dòng được chọn mới được tải/cập nhật canonical data."),
                    "Ticker": st.column_config.TextColumn("Mã", required=True),
                },
            )
            st.caption(str(discovery.get("note") or ""))
            st.caption(f"Target {safe} luôn được giữ làm mốc benchmark dù có vô tình bỏ chọn/xóa trong editor.")
        elif stored_peers:
            st.caption("Bấm 'Tải / tải lại danh sách cùng ngành' để chỉnh peer set. Peer set đã xác nhận hiện tại vẫn được giữ nguyên.")

        st.markdown("#### Bước 2 — Xác nhận danh sách rồi mới tải/cập nhật BCTC")
        update_disabled = not isinstance(selection_df, pd.DataFrame)
        if st.button(
            "2️⃣ Xác nhận peer đã chọn & cập nhật dữ liệu Q17/Q19",
            use_container_width=True,
            disabled=update_disabled,
            key=f"ch4q_confirm_refresh_{safe}",
        ):
            selected = selected_peer_tickers(selection_df, safe, max_peers=DEFAULT_MAX_PEERS)
            if len(selected) < 2:
                st.warning("Danh sách chỉ có target. Hãy chọn/thêm ít nhất 1 doanh nghiệp so sánh trước khi cập nhật ngành.")
            else:
                progress = st.progress(0.02, text=f"Đang cập nhật canonical BCTC cho {len(selected)} mã đã được Analyst xác nhận...")
                refresh_results = refresh_peer_canonical_universe(selected, max_workers=3)
                notes = [note for _peer, _ok, _paths, note in refresh_results]
                ok_count = sum(1 for _peer, ok, _paths, _note in refresh_results if ok)
                progress.progress(0.90, text="Đang dựng ROIC/CCC/margins từ peer set đã xác nhận...")
                _snapshot_cached.clear()
                snapshots_after = []
                for peer in selected:
                    snap, _ = load_quant_snapshot(peer)
                    if snap:
                        snapshots_after.append(snap)
                peer_df_after = build_peer_table(snapshots_after)
                latest_record = load_record(safe, company_name)
                latest_record["quantitative_peer_tickers"] = [p for p in selected if p != safe]
                latest_record["quantitative_industry_group"] = industry_group
                latest_record["quantitative_peer_source"] = "Analyst-curated same-industry peer set + Trecapital canonical statements"
                latest_record["quantitative_peer_selection_updated_at"] = pd.Timestamp.now().isoformat()
                latest_record = _merge_q17_peer_rows(latest_record, peer_df_after, preserve_unmatched=False)
                save_record(latest_record, create_snapshot=False)
                st.session_state[selection_key] = build_peer_selection_table(
                    discovery.get("peers") if isinstance(discovery.get("peers"), pd.DataFrame) else pd.DataFrame(),
                    safe,
                    latest_record["quantitative_peer_tickers"],
                )
                progress.empty()
                st.success(
                    f"Đã xác nhận {len(selected)-1} peer; cập nhật thành công {ok_count}/{len(selected)} mã. "
                    f"Q17/Q19 chỉ dùng {len(peer_df_after)} mã có canonical data trong peer set này."
                )
                if notes:
                    with st.expander("Chi tiết cập nhật peer", expanded=False):
                        st.write("\n".join(f"- {x}" for x in notes))
                st.rerun()

        # Only the saved/confirmed list is used below. Discovery candidates alone never enter Q17/Q19.
        record = load_record(safe, company_name)
        stored_peers = record.get("quantitative_peer_tickers", []) if isinstance(record, dict) else []
        if not isinstance(stored_peers, list):
            stored_peers = []
        peers = normalize_ticker_list(stored_peers, safe, max_peers=DEFAULT_MAX_PEERS)
        if len(peers) == 1 and not stored_peers:
            peers = [safe]
        industry_group = str(record.get("quantitative_industry_group") or industry_group)

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
            st.info("Mã trong peer set đã xác nhận nhưng chưa có canonical cache: " + ", ".join(missing))

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
                st.caption("Chưa có canonical data trong peer set đã xác nhận.")
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
            st.caption(
                "Q17 chỉ sử dụng peer set đã được Analyst xác nhận. Discovery candidate không tự đi vào bảng. "
                "'Good / Mixed / Bad Industry' vẫn chỉ Analyst được chọn."
            )

        with st.expander("Q19 — Table 4.2 quantitative peer benchmark", expanded=False):
            bench = build_peer_benchmark(peer_df, safe)
            if bench.empty:
                st.caption("Chưa có peer canonical data để dựng benchmark.")
            else:
                st.dataframe(_styled_numeric(bench), use_container_width=True, hide_index=True)
            st.caption(
                "Benchmark dùng cùng peer set Analyst đã xác nhận ở Q17. Peer Min/Max chỉ là mô tả; app không tự chọn Ideal Company."
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


'''
pattern = re.compile(r"def render_quantitative_bridge\(ticker: str\) -> tuple\[str, str\]:\n.*?\n\ndef render_chapter4_tab", re.S)
if not pattern.search(text):
    # Allow rerun after patch.
    pattern = re.compile(r"def render_quantitative_bridge\(ticker: str\) -> tuple\[str, str, str\]:\n.*?\n\ndef render_chapter4_tab", re.S)
if not pattern.search(text):
    raise SystemExit("chapter4_page_support.py: render_quantitative_bridge block not found")
text = pattern.sub(new_render + "def render_chapter4_tab", text, count=1)
CH4_SUPPORT.write_text(text, encoding="utf-8")

# ---------------------------------------------------------------------------
# 3) Unified page: route Chapter 5 through the Phase 5B support wrapper.
# ---------------------------------------------------------------------------
text = PAGE.read_text(encoding="utf-8")
text = text.replace(
    "from modules.deep_company_analysis.chapter5 import render_chapter5",
    "from modules.deep_company_analysis.chapter5_page_support import render_chapter5_tab",
)
text = text.replace(
    "    render_chapter5(default_ticker=chapter5_ticker)",
    "    render_chapter5_tab(chapter5_ticker)",
)
PAGE.write_text(text, encoding="utf-8")

print("Applied: Q23 Origin UI hide + Chapter 4 analyst-curated peers + Chapter 5 Phase 5B page integration")
