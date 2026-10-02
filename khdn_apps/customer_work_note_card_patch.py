"""Final rerun-safe Customer Work card note overlay.

Adds persisted Customer Work notes without replacing the proven card renderers.
The overlay intercepts only the HTML fragment that needs the note, renders that
fragment with st.html (not Markdown), and always restores st.markdown afterwards.
This avoids iOS/Streamlit showing closing tags or CSS as literal code.
"""
from __future__ import annotations

import html

from khdn_apps import customer_work_refinement_patch as refinement
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_room_dashboard_detail_patch as room
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3

VERSION = "1.1.0"
_FLAG = "_CUSTOMER_WORK_NOTE_CARD_VERSION"

# Capture the already-proven source renderers at module import time, before the
# runtime installers rebind them.  The note layer wraps these renderers instead
# of maintaining a second copy of their HTML/CSS/business behavior.
_BASE_CUSTOMER_CARD = finalux._customer_card
_BASE_ROOM_CASE_CARD = room._room_case_card


def _note_html(x, css_class="cwux-note"):
    """Safe inline-styled note block. Blank notes consume no card space."""
    raw = str((x or {}).get("note") or "").strip()
    if not raw:
        return ""
    note = html.escape(raw)
    return (
        f"<div class='{css_class}' style='font-size:.80rem;line-height:1.42;"
        "margin-top:8px;padding:7px 9px;border-left:3px solid rgba(99,220,203,.58);"
        "border-radius:7px;background:rgba(99,220,203,.055);white-space:pre-wrap;"
        "overflow-wrap:anywhere;word-break:break-word'>"
        f"📝 <b>Ghi chú:</b> <span style='font-weight:500'>{note}</span></div>"
    )


def _run_with_html_injection(st, note_block, mode, renderer):
    """Inject one note into the base renderer and bypass Markdown for that HTML block."""
    original_markdown = st.markdown
    injected = False

    def patched_markdown(body, *args, **kwargs):
        nonlocal injected
        text = body if isinstance(body, str) else None
        unsafe = bool(kwargs.get("unsafe_allow_html"))
        if note_block and not injected and text and unsafe:
            if mode == "customer" and "cwux-row" in text and "<style>" in text:
                injected = True
                transformed = text.replace("<style>", note_block + "<style>", 1)
                return st.html(transformed)
            if mode == "room" and 'class="rd-card"' in text and "<style>" in text:
                marker = "\n        </div>\n        <style>"
                if marker in text:
                    injected = True
                    transformed = text.replace(
                        marker,
                        "\n          " + note_block + "\n        </div>\n        <style>",
                        1,
                    )
                    return st.html(transformed)
        return original_markdown(body, *args, **kwargs)

    st.markdown = patched_markdown
    try:
        return renderer()
    finally:
        st.markdown = original_markdown


def _customer_card(st, customer_ui, refinement_module, x, get_conn, uid, manager,
                   logger=None, compact=False):
    """Original Customer Work card + note; original actions/button styling stay intact."""
    note_block = _note_html(x, "cwux-note")
    return _run_with_html_injection(
        st,
        note_block,
        "customer",
        lambda: _BASE_CUSTOMER_CARD(
            st, customer_ui, refinement_module, x, get_conn, uid, manager,
            logger, compact,
        ),
    )


def _old_room_detail_button_css(st, cid):
    """Restore the old gold/yellow pill used by Customer Work card Detail actions."""
    st.html(
        f"""<style>
        div[class*='st-key-room_case_detail_{int(cid)}'] button{{
          background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
          color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
          border:2px solid #FFE589!important;border-radius:999px!important;
          font-weight:950!important;min-height:2.45rem!important;
          box-shadow:none!important;
        }}
        div[class*='st-key-room_case_detail_{int(cid)}'] button *{{
          color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
          font-weight:950!important;
        }}
        </style>"""
    )


def _room_case_card(st, customer_ui, x):
    """Original room card + safe note injection + original gold Detail appearance."""
    cid = int((x or {}).get("id") or 0)
    _old_room_detail_button_css(st, cid)
    note_block = _note_html(x, "rd-note")
    return _run_with_html_injection(
        st,
        note_block,
        "room",
        lambda: _BASE_ROOM_CASE_CARD(st, customer_ui, x),
    )


def _case_card_bridge(st, x, get_conn, uid, manager, logger=None, compact=False):
    from khdn_apps import customer_work_ui
    return _customer_card(
        st, customer_work_ui, refinement, x, get_conn, uid, manager, logger, compact
    )


def install(customer_ui, logger=None):
    """Rebind all active Customer Work card entry points on every Streamlit run."""
    # No early return by design: historical/runtime patches may rebind on rerun.
    finalux._customer_card = _customer_card
    v2._card = _customer_card
    v3._card = _customer_card
    customer_ui._case_card = _case_card_bridge
    room._room_case_card = _room_case_card
    setattr(customer_ui, _FLAG, VERSION)
    if logger:
        logger.info(
            "CUSTOMER_WORK_NOTE_CARD_REBOUND version=%s safe_html=1 original_renderers=1 old_detail_button=1 processing=1 today=1 detail=1 room=1 data_migration=0",
            VERSION,
        )
