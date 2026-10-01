"""Submit-only browser form that keeps the legacy KHDN input layout.

Draft values live entirely in the browser component while the user types. Python
receives one payload only after the explicit save button, so long pages/tables do
not participate in the keyboard hot path.  ``columns`` is presentation-only and
lets larger forms keep their familiar desktop layout while collapsing to one
column on phones.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

# v2 intentionally changes the component registration name so iPad/Safari cannot
# keep serving the older iframe asset after a production deploy.  Business keys
# and submit de-duplication remain unchanged.
_component = components.declare_component(
    "khdn_legacy_fast_form_v2",
    path=str(Path(__file__).with_name("legacy_fast_form_component")),
)


def _normalize_customer_work_due_date(values, key):
    """Convert the iPad-safe DD/MM/YYYY display value back to legacy ISO format."""
    if not str(key).startswith("p17_customer_work_create_") or not isinstance(values, dict):
        return values
    raw = str(values.get("due_date") or "").strip()
    if not raw:
        return values
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            values["due_date"] = datetime.strptime(raw, fmt).date().isoformat()
            return values
        except ValueError:
            continue
    # Keep invalid text unchanged so the existing business validator displays
    # its standard "Ngày dự kiến hoàn thành không hợp lệ" message.
    return values


def legacy_fast_form(
    fields,
    button_label,
    key,
    *,
    reset_token="",
    title="",
    help_text="",
    columns=1,
):
    result = _component(
        fields=list(fields or []),
        buttonLabel=str(button_label or "Lưu"),
        resetToken=str(reset_token or ""),
        title=str(title or ""),
        helpText=str(help_text or ""),
        columns=max(1, min(4, int(columns or 1))),
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
    if not isinstance(values, dict):
        return {}
    values = dict(values)
    return _normalize_customer_work_due_date(values, key)
