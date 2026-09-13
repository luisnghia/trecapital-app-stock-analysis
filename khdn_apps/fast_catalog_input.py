"""Ultra-light catalog text entry for KHDN Ops.

This custom component intentionally does not send keystrokes to Streamlit. The browser
keeps the draft locally and only emits a value when the user clicks the submit button or
presses Enter. It is used for short catalog-name creation where production users reported
visible typing lag despite st.form batching.
"""
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

_component = components.declare_component(
    "khdn_fast_catalog_input",
    path=str(Path(__file__).with_name("fast_catalog_component")),
)


def _theme_type():
    try:
        value = getattr(getattr(st, "context", None), "theme", None)
        if value is not None:
            kind = getattr(value, "type", None)
            if kind in {"light", "dark"}:
                return kind
    except Exception:
        pass
    return "light"


def fast_catalog_input(label, button_label, key, *, placeholder="", reset_token="", default_value=""):
    """Return submitted text once; return ``None`` while the user is only typing.

    The iframe uses a plain DOM ``<input>``. No ``streamlit:setComponentValue`` message
    is sent for ``input``/``keyup`` events, so the rest of the Streamlit tree cannot be
    involved in per-character rendering.
    """
    result = _component(
        label=str(label),
        buttonLabel=str(button_label),
        placeholder=str(placeholder or ""),
        resetToken=str(reset_token or ""),
        defaultValue=str(default_value or ""),
        themeType=_theme_type(),
        key=str(key),
        default=None,
    )
    if not isinstance(result, dict):
        return None
    submit_id = str(result.get("submit_id") or "")
    if not submit_id:
        return None
    seen_key = f"_khdn_fast_catalog_seen_{key}"
    if st.session_state.get(seen_key) == submit_id:
        return None
    st.session_state[seen_key] = submit_id
    return str(result.get("value") or "")
