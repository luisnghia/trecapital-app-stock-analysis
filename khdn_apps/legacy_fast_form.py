"""Submit-only browser form that keeps the legacy KHDN input layout on mobile.

Draft values live entirely in the browser component while the user types.  Python
receives one payload only after the explicit save button, so long catalog pages do
not participate in the iOS keyboard hot path.
"""
from __future__ import annotations

from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component(
    "khdn_legacy_fast_form",
    path=str(Path(__file__).with_name("legacy_fast_form_component")),
)


def legacy_fast_form(fields, button_label, key, *, reset_token="", title="", help_text=""):
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
    seen_key = f"_khdn_legacy_fast_form_seen_{key}"
    if st.session_state.get(seen_key) == submit_id:
        return None
    st.session_state[seen_key] = submit_id
    values = result.get("values")
    return dict(values) if isinstance(values, dict) else {}
