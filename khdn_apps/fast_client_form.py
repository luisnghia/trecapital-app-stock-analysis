"""Browser-local submit-only form for mobile-sensitive KHDN data entry.

All draft values stay inside the component iframe while the user types/edits.
Python receives one payload only on explicit submit. This avoids Streamlit widget
traffic and reruns on the iOS keyboard hot path.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component(
    "khdn_fast_client_form",
    path=str(Path(__file__).with_name("fast_client_form_component")),
)


def fast_client_form(fields, button_label, key, *, reset_token="", title="", help_text=""):
    """Return submitted values once; return ``None`` while the user is editing."""
    result = _component(
        fields=list(fields or []),
        buttonLabel=str(button_label or "Lưu"),
        resetToken=str(reset_token or ""),
        title=str(title or ""),
        helpText=str(help_text or ""),
        key=str(key),
        default=None,
    )
    if not isinstance(result, dict):
        return None
    submit_id = str(result.get("submit_id") or "")
    if not submit_id:
        return None
    seen_key = f"_khdn_fast_client_form_seen_{key}"
    if st.session_state.get(seen_key) == submit_id:
        return None
    st.session_state[seen_key] = submit_id
    values = result.get("values")
    return dict(values) if isinstance(values, dict) else {}
