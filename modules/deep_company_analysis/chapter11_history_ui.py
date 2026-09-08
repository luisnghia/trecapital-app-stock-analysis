from __future__ import annotations

"""Chapter 11 Phase 11H / V89 — History/lineage UI and report bridge.

Exposes immutable snapshots, neutral deltas and explicit analyst re-review in the live
Chapter 11 workflow. A delta is only a change in the research record. It never means M&A
quality improved/worsened and never creates an acquisition-success classification, synergy
forecast, M&A score, valuation/MOS change, Investment Research Gate outcome or signal.
"""

from copy import deepcopy
from typing import Any

import pandas as pd
import streamlit as st

import modules.deep_company_analysis.chapter11_history as history
from modules.deep_company_analysis.chapter11_store import (
    create_snapshot,
    list_snapshots,
    mark_explicit_re_review,
)
from modules.deep_company_analysis.table_format import render_static_table

REVIEW_SECTIONS = ("Q58", "Q59", "M&A Synthesis", "Source Baseline")


def history_report_section(ticker: str, current_payload: dict[str, Any] | None) -> dict[str, Any]:
    snapshots = list_snapshots(ticker)
    lineage = history.build_version_lineage(snapshots)
    latest = snapshots[-1] if snapshots else None
    delta = pd.DataFrame(columns=history.DELTA_COLUMNS)
    summary = {
        "tracked_fields": 0,
        "changed_fields": 0,
        "unchanged_fields": 0,
        "source_baseline_changed": False,
        "historical_source_freshness_reconstructed": False,
        "automatic_question_status_change": False,
        "automatic_confidence_change": False,
        "automatic_analyst_text_change": False,
        "automatic_ma_score": False,
        "automatic_acquisition_success_classification": False,
        "automatic_synergy_forecast": False,
        "automatic_investment_signal": False,
        "mos_or_investment_research_gate_changed": False,
        "boundary": history.HISTORY_BOUNDARY,
    }
    if latest is not None:
        delta = history.compare_versions(
            latest.get("payload"), current_payload,
            before_label=f"Snapshot #{latest['snapshot_id']}", after_label="Current saved workspace",
        )
        summary = history.history_summary(latest.get("payload"), current_payload)
    return {
        "snapshot_count": len(snapshots),
        "latest_snapshot_id": latest.get("snapshot_id") if latest else None,
        "lineage": lineage,
        "latest_to_current_delta": delta,
        "summary": summary,
        "boundary_note": history.HISTORY_BOUNDARY,
    }


def _snapshot_label(row: dict[str, Any]) -> str:
    sid = row.get("snapshot_id")
    created = str(row.get("created_at") or "")
    reason = str(row.get("reason") or "").strip()
    suffix = f" — {reason}" if reason else ""
    return f"Snapshot #{sid} — {created}{suffix}"


def render_history_panel(ticker: str, current_payload: dict[str, Any], *, payload_session_key: str | None = None) -> None:
    st.markdown("### Version History & Explicit Re-review")
    st.caption("Snapshots are immutable. Delta only means the Chapter 11 research record changed; it is not an M&A-quality or investment signal.")

    reason = st.text_input("Snapshot reason / note", key=f"ch11_snapshot_reason_{ticker}")
    if st.button("📸 Create immutable snapshot", key=f"ch11_create_snapshot_{ticker}"):
        snap = create_snapshot(ticker, deepcopy(current_payload), reason=reason)
        if payload_session_key:
            st.session_state[payload_session_key] = deepcopy(snap["payload"])
        st.success(f"Created immutable Snapshot #{snap['snapshot_id']}.")
        st.rerun()

    snapshots = list_snapshots(ticker)
    if not snapshots:
        st.info("No Chapter 11 snapshot yet. Create one to establish an immutable comparison baseline.")
        return

    st.markdown("#### Version lineage")
    render_static_table(history.build_version_lineage(snapshots), hide_index=True, use_container_width=True)

    labels = {_snapshot_label(row): row for row in snapshots}
    left, right = st.columns(2)
    before_label = left.selectbox("Compare from", list(labels), index=max(len(labels) - 1, 0), key=f"ch11_hist_before_{ticker}")
    after_options = list(labels) + ["Current saved workspace"]
    after_label = right.selectbox("Compare to", after_options, index=len(after_options) - 1, key=f"ch11_hist_after_{ticker}")
    before = labels[before_label].get("payload")
    after = current_payload if after_label == "Current saved workspace" else labels[after_label].get("payload")
    delta = history.compare_versions(before, after, before_label=before_label, after_label=after_label)
    changed = delta[delta["Delta"] != "Unchanged"].reset_index(drop=True)
    st.markdown("#### Neutral delta")
    if changed.empty:
        st.caption("No tracked analyst-owned changes between the selected versions.")
    else:
        render_static_table(changed, hide_index=True, use_container_width=True)
    st.caption(history.HISTORY_BOUNDARY)

    st.markdown("#### Explicit analyst re-review")
    sections = st.multiselect("Sections re-reviewed", REVIEW_SECTIONS, key=f"ch11_re_review_sections_{ticker}")
    note = st.text_area("Re-review note", key=f"ch11_re_review_note_{ticker}")
    if st.button("✅ Record explicit re-review", disabled=not sections, key=f"ch11_re_review_save_{ticker}"):
        reviewed = mark_explicit_re_review(ticker, sections, note)
        if payload_session_key:
            st.session_state[payload_session_key] = reviewed
        st.success("Recorded explicit analyst re-review. No conclusion, status, confidence or investment signal was changed automatically.")
        st.rerun()


__all__ = ["REVIEW_SECTIONS", "history_report_section", "render_history_panel"]
