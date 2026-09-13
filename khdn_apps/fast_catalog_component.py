"""Ultra-light catalog text entry isolated from the main Streamlit React tree.

The component renders a plain HTML <input> in its own iframe. Keystrokes never touch
Streamlit widget state; only clicking Submit sends one value back to Python. This is
used for the two catalog-entry fields that users type into most often.
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component(
    "khdn_fast_catalog_input",
    path=str(Path(__file__).with_name("fast_catalog_component")),
)


def fast_catalog_input(label: str, button_label: str, key: str, placeholder: str = ""):
    result = _component(
        label=label,
        buttonLabel=button_label,
        placeholder=placeholder,
        key=key,
        default=None,
    )
    if not isinstance(result, dict):
        return None
    event_id = str(result.get("id") or "")
    if not event_id:
        return None
    seen_key = f"_fast_catalog_seen_{key}"
    if st.session_state.get(seen_key) == event_id:
        return None
    st.session_state[seen_key] = event_id
    return str(result.get("value") or "")
