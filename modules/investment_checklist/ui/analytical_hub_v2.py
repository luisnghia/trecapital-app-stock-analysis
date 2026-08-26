from __future__ import annotations

import pandas as pd
import streamlit as st

# Import first: installs the corrected formula-table renderer, correction-field selector, and
# per-tool Shearn guidance wrapper before integration_preview imports those helpers.
from . import phase2_2_fixes as _phase2_2_fixes  # noqa: F401
from . import page as _page
from . import quant_tools as _qt
from .book_guidance import render_book_guidance
from .portfolio_extensions import (
    _highlight_adjusted,
    _patched_quant_render,
    _patched_table12_trend,
    apply_table_overrides,
    render_numeric_override_editor,
    render_table11_historical_corrections,
)


def _render_stress_override_table(repo, company_ref_id: int, actor: str, name: str, df: pd.DataFrame) -> None:
    raw = df.copy().reset_index(drop=True)
    if "Revenue shock" in raw.columns:
        raw.insert(0, "Scenario", raw["Revenue shock"].map(lambda x: "—" if pd.isna(x) else f"Shock {float(x):,.1f}%"))
    else:
        raw.insert(0, "Scenario", [f"Scenario {i+1}" for i in range(len(raw))])
    table_key = f"Analytical · {name}"
    effective, adjusted = apply_table_overrides(repo, company_ref_id, table_key, raw, period_col="Scenario")
    st.dataframe(
        _highlight_adjusted(_qt._styled(effective), adjusted),
        use_container_width=True,
        hide_index=True,
    )
    render_book_guidance("Operating Leverage Stress", effective.columns, expanded=False)
    render_numeric_override_editor(
        repo,
        company_ref_id,
        actor,
        table_key=table_key,
        df=effective,
        period_col="Scenario",
    )


def render_analytical_hub_v2(repo, integration, company_ref_id: int, review, actor: str, data_provider, company_type: str) -> None:
    """11-tool architecture: Table 1.1/1.2 + quantitative tools in one lazy Analytical hub."""
    st.markdown("### 🧮 Analytical Tools")
    st.caption(
        "Table 1.1 và Table 1.2 nằm trong Analytical Tools theo kiến trúc nguồn. "
        "Mọi bảng dữ liệu ở đây hỗ trợ analyst correction; correction là overlay versioned, không sửa Trecapital Data Layer."
    )
    group = st.selectbox(
        "Nhóm Analytical Tool",
        [
            "1.1 · Quality Criteria Matrix",
            "1.2 · Opportunity Inventory",
            "5.x–10.x · Quantitative Analytical Tools",
        ],
        key=f"analytical_hub_v2_{company_ref_id}",
    )
    if group.startswith("1.1"):
        render_book_guidance("Table 1.1", expanded=False)
        _page._render_table11(repo, company_ref_id, review, actor)
        render_table11_historical_corrections(repo, company_ref_id, actor)
        return
    if group.startswith("1.2"):
        render_book_guidance("Table 1.2", expanded=False)
        with _patched_table12_trend(repo, integration, company_ref_id, actor):
            _page._render_table12(repo, integration, company_ref_id, review, actor)
        return

    with _patched_quant_render(repo, company_ref_id, actor):
        _qt.render_quantitative_tools(
            data_provider,
            company_type=company_type,
            auxiliary_table_renderer=lambda name, df: _render_stress_override_table(repo, company_ref_id, actor, name, df),
        )
