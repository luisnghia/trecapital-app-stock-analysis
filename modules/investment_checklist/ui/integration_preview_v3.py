from __future__ import annotations

"""V99 shell around the proven V98 Checklist fragment.

The V98 renderer is preserved byte-for-byte in ``integration_preview_v3_legacy.py``.  V99 adds a
lazy Word-report surface below it without changing internal navigation, analyst workflows or the
fast-entry data contract.
"""

import streamlit as st

from . import integration_preview_v3_legacy as _legacy


# Preserve the V98 module API for regression tests and any callers importing helper functions.
for _name in dir(_legacy):
    if _name.startswith("__") or _name == "render_investment_checklist":
        continue
    globals().setdefault(_name, getattr(_legacy, _name))


def render_investment_checklist(host, *, repo=None, data_provider=None, theme=None) -> None:
    _legacy.render_investment_checklist(host, repo=repo, data_provider=data_provider, theme=theme)

    review_state_key = f"checklist_review_{host.company.company_key}"
    review_id = st.session_state.get(review_state_key)
    with st.expander("📄 Báo cáo Word Investment Checklist — V99", expanded=False):
        from .reporting import render_word_report_export

        render_word_report_export(
            host,
            review_id=int(review_id) if review_id is not None else None,
            data_provider=data_provider,
            repo=repo,
        )


__all__ = ["render_investment_checklist"]
