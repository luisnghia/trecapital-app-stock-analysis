from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from modules.deep_company_analysis.chapter7 import load_record, save_record
from modules.deep_company_analysis.chapter7_research import (
    CANDIDATE_COLUMNS,
    Chapter7ResearchAgent,
    RESEARCH_BOUNDARY,
    deep_extract_candidates,
    evidence_quality_summary,
    promote_candidates_into_record,
    research_gaps,
)
from modules.deep_company_analysis.table_format import render_static_table, sortable_data_editor


APP_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = APP_DIR / "data_cache" / "chapter7_research"


def _safe_ticker(value: str) -> str:
    return "".join(ch for ch in str(value).upper().strip() if ch.isalnum() or ch in {".", "-"})[:20]


def _manager_names(payload: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for row in payload.get("management_profiles") or []:
        if not isinstance(row, dict):
            continue
        name = " ".join(str(row.get("Manager") or "").split())
        if name and name not in names:
            names.append(name)
    return names[:5]


def _candidate_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        frame = value.copy()
    elif isinstance(value, list):
        frame = pd.DataFrame(value)
    else:
        frame = pd.DataFrame()
    for column in CANDIDATE_COLUMNS:
        if column not in frame.columns:
            frame[column] = False if column == "Select" else ""
    return frame[CANDIDATE_COLUMNS]


def render_chapter7_research_assistant(ticker: str, payload: dict[str, Any]) -> dict[str, Any]:
    safe = _safe_ticker(ticker)
    managers = _manager_names(payload)
    candidates_key = f"ch7c_candidates_{safe}"
    discovered_key = f"ch7c_discovered_managers_{safe}"
    note_key = f"ch7c_note_{safe}"
    raw_key = f"ch7c_raw_{safe}"

    st.markdown("## 🔎 Phase 7C — Management Evidence & Research Assistant")
    st.caption(
        "Tìm evidence/counter-evidence Q33–Q38 từ web và nguồn công bố, sau đó cho phép trích sâu PDF/HTML. "
        "Mọi kết quả chỉ là candidate; analyst phải chọn và Promote trước khi vào Evidence Matrix."
    )
    st.info(RESEARCH_BOUNDARY)

    if managers:
        st.success("Manager targets: " + ", ".join(managers))
    else:
        st.warning("Management Profile đang trống. Hệ thống sẽ thử auto-discover candidate manager targets từ nguồn doanh nghiệp/IR chính thức trước khi research; các identity này vẫn cần analyst xác nhận.")

    c1, c2 = st.columns([3, 1])
    with c1:
        company_name = str(payload.get("company_name") or "")
        st.caption(f"Target: {safe} — {company_name or 'chưa nhập tên doanh nghiệp'}")
    with c2:
        max_results = st.selectbox("Kết quả / query", [2, 3, 4], index=1, key=f"ch7c_max_{safe}")

    if st.button("🌐 Research Q33–Q38", use_container_width=True, key=f"ch7c_run_{safe}"):
        with st.spinner(f"Đang research management evidence cho {safe}..."):
            result = Chapter7ResearchAgent(RAW_DIR).search(
                safe,
                company_name,
                managers=managers,
                max_results_per_query=int(max_results),
            )
        st.session_state[candidates_key] = result.candidates.to_dict("records")
        discovered = result.manager_candidates if isinstance(result.manager_candidates, pd.DataFrame) else pd.DataFrame()
        st.session_state[discovered_key] = discovered.to_dict("records")
        st.session_state[note_key] = result.note
        st.session_state[raw_key] = result.raw_paths

    candidates = _candidate_frame(st.session_state.get(candidates_key))
    discovered = pd.DataFrame(st.session_state.get(discovered_key) or [])
    research_managers = list(managers)
    if not research_managers and not discovered.empty and "Manager" in discovered.columns:
        research_managers = list(dict.fromkeys(" ".join(str(x).split()) for x in discovered["Manager"].tolist() if str(x).strip()))[:5]

    if not discovered.empty:
        st.markdown("### Candidate management targets — auto-discovered")
        render_static_table(discovered, height=min(360, 120 + 30 * len(discovered)), sort_key=f"ch7c_discovered_{safe}")
        st.info("Các tên/chức vụ trên chỉ là research targets từ nguồn chính thức. App không tự ghi vào Management Profile và không tự xác nhận Q33/Q36.")

    if not candidates.empty:
        st.markdown("### Evidence coverage — A/B/C")
        render_static_table(evidence_quality_summary(candidates), height=300, sort_key=f"ch7c_quality_{safe}")

        st.markdown("### Candidate Evidence / Counter-Evidence")
        disabled = [col for col in CANDIDATE_COLUMNS if col != "Select"]
        edited = sortable_data_editor(
            candidates,
            key=f"ch7c_candidate_editor_{safe}",
            hide_index=True,
            use_container_width=True,
            height=min(620, 150 + 30 * len(candidates)),
            num_rows="fixed",
            disabled=disabled,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select"),
                "Evidence Text / Reference": st.column_config.TextColumn("Evidence Text / Reference", width="large"),
                "Source URL / File": st.column_config.LinkColumn("Source URL / File", width="large"),
            },
        )
        if isinstance(edited, pd.DataFrame):
            candidates = edited
            st.session_state[candidates_key] = candidates.to_dict("records")
        st.warning("Supporting/Counter chỉ là text cue để chống confirmation bias; không phải Lion/Hyena, OO/LT/HH hay management-quality conclusion.")

        selected_ids = candidates.loc[candidates["Select"].fillna(False).astype(bool), "Candidate ID"].astype(str).tolist()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📄 Trích sâu PDF/HTML đã chọn", use_container_width=True, key=f"ch7c_deep_{safe}", disabled=not bool(selected_ids)):
                with st.spinner("Đang tải và trích text từ nguồn đã chọn (không OCR)..."):
                    deep = deep_extract_candidates(candidates, selected_ids, managers=research_managers)
                if deep.empty:
                    st.warning("Không trích được text usable từ nguồn đã chọn. Nguồn có thể chặn truy cập, là trang động hoặc PDF scan cần OCR.")
                else:
                    merged = pd.concat([candidates, deep], ignore_index=True)
                    merged = merged.drop_duplicates(subset=["Candidate ID"], keep="first").reset_index(drop=True)
                    st.session_state[candidates_key] = merged.to_dict("records")
                    st.success(f"Đã thêm {len(deep)} deep-extraction candidates. Hãy review và chọn trước khi Promote.")
                    st.rerun()
        with c2:
            st.caption("Deep extract chỉ đọc HTML/PDF text. PDF scan/image không OCR và không được suy đoán nội dung.")
    else:
        st.info("Chưa có Phase 7C research candidates trong phiên này.")
        selected_ids = []

    gaps = research_gaps(candidates, managers)
    st.markdown("### Research Gaps")
    if not gaps.empty:
        render_static_table(gaps, height=min(420, 120 + 30 * len(gaps)), sort_key=f"ch7c_gaps_{safe}")
    else:
        st.success("Không phát hiện gap cơ học theo coverage hiện tại. Analyst vẫn phải kiểm tra material gaps thực tế.")

    if st.session_state.get(note_key):
        with st.expander("Research log", expanded=False):
            st.caption(str(st.session_state[note_key]))
            raw_paths = st.session_state.get(raw_key) or []
            if raw_paths:
                st.code("\n".join(str(x) for x in raw_paths), language=None)

    if st.button(
        "💾 Promote evidence đã chọn + lưu Research Gaps",
        use_container_width=True,
        key=f"ch7c_promote_{safe}",
        disabled=not bool(selected_ids) and gaps.empty,
    ):
        current = load_record(safe)
        updated, stats = promote_candidates_into_record(current, candidates, selected_ids, gaps)
        save_record(safe, updated, str(payload.get("company_name") or current.get("company_name") or ""))
        st.success(
            f"Promote: {stats['promoted']} evidence; bỏ qua {stats['duplicates']} duplicate; thêm {stats['gaps_added']} research gaps. "
            "Không có analyst conclusion/classification nào bị ghi đè."
        )
        st.rerun()

    return payload


__all__ = ["render_chapter7_research_assistant"]
