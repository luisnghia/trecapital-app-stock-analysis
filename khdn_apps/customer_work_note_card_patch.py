"""Final rerun-safe Customer Work card note overlay.

Adds persisted Customer Work notes without replacing the proven Customer Work
card renderer. It also owns the final render-context resolver so the note
wrapper never collapses multiple cards onto the same Streamlit key, and the
room dashboard reuses the exact Customer Work card format/content.
"""
from __future__ import annotations

import html
import sys
import os
import re

from khdn_apps import customer_work_refinement_patch as refinement
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_room_dashboard_detail_patch as room
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3

VERSION = "1.3.1"
_FLAG = "_CUSTOMER_WORK_NOTE_CARD_VERSION"

# Capture the proven Customer Work renderer once. The overlay only injects the
# persisted note and otherwise delegates layout/actions/business behavior to it.
_BASE_CUSTOMER_CARD = finalux._customer_card


def _stable_render_context():
    """Return the real external card call-site, ignoring renderer/overlay frames.

    The previous resolver could stop at this module's lambda, so the same case
    rendered in two Today sections received the same ``cwux_card_*`` key. That
    produced StreamlitDuplicateElementKey for every role using the Today page.
    """
    skip = {
        os.path.basename(__file__),
        "planning_final_ux_patch.py",
        "planning_usability_v3_patch.py",
        "planning_ui_v4_patch.py",
    }
    frame = None
    try:
        # inspect.stack() reads source and scans loaded modules for every card.
        # Only filename/function/line are needed to preserve the exact call-site key.
        frame = sys._getframe(2)
        while frame is not None:
            name = os.path.basename(frame.f_code.co_filename)
            if name in skip:
                frame = frame.f_back
                continue
            raw = f"{name}_{frame.f_code.co_name}_{frame.f_lineno}"
            return re.sub(r"[^A-Za-z0-9_]+", "_", raw)
    except Exception:
        pass
    finally:
        del frame
    return "default"


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


def _run_with_html_injection(st, note_block, renderer):
    """Inject one note into the proven Customer Work HTML block safely."""
    original_markdown = st.markdown
    injected = False

    def patched_markdown(body, *args, **kwargs):
        nonlocal injected
        text = body if isinstance(body, str) else None
        unsafe = bool(kwargs.get("unsafe_allow_html"))
        if note_block and not injected and text and unsafe and "cwux-row" in text and "<style>" in text:
            injected = True
            transformed = text.replace("<style>", note_block + "<style>", 1)
            return st.html(transformed)
        return original_markdown(body, *args, **kwargs)

    st.markdown = patched_markdown
    try:
        return renderer()
    finally:
        st.markdown = original_markdown


def _customer_card(st, customer_ui, refinement_module, x, get_conn, uid, manager,
                   logger=None, compact=False):
    """Exact Customer Work card + persisted note."""
    note_block = _note_html(x, "cwux-note")
    return _run_with_html_injection(
        st,
        note_block,
        lambda: _BASE_CUSTOMER_CARD(
            st, customer_ui, refinement_module, x, get_conn, uid, manager,
            logger, compact,
        ),
    )


def _room_case_card(st, customer_ui, x):
    """Exact Customer Work card plus room -> Customer Work detail navigation.

    The final exact-card overlay delegates to the normal Customer Work renderer,
    whose Detail button only sets ``cw_case_id``. On the Customer Work page that
    is enough, but the room dashboard must also switch the outer navigation to
    ``plan/customer_work`` before the renderer reruns. The historical room card
    already did this; preserve that routing while keeping the exact card layout.
    """
    original_button = st.button

    def room_button(label, *args, **kwargs):
        clicked = original_button(label, *args, **kwargs)
        if clicked and str(label).strip() == "🔎 Chi tiết":
            st.session_state["main_section"] = "plan"
            st.session_state["main_page"] = "customer_work"
        return clicked

    st.button = room_button
    try:
        return _customer_card(
            st,
            customer_ui,
            refinement,
            x,
            None,
            0,
            False,
            None,
            False,
        )
    finally:
        st.button = original_button


def _case_card_bridge(st, x, get_conn, uid, manager, logger=None, compact=False):
    from khdn_apps import customer_work_ui
    return _customer_card(
        st, customer_work_ui, refinement, x, get_conn, uid, manager, logger, compact
    )


def install(customer_ui, logger=None):
    """Rebind active Customer Work cards on every Streamlit run."""
    # No early return by design: historical/runtime patches may rebind on rerun.
    # Reassert the context resolver first so every role gets unique card keys.
    finalux._render_context = _stable_render_context
    finalux._customer_card = _customer_card
    v2._card = _customer_card
    v3._card = _customer_card
    customer_ui._case_card = _case_card_bridge
    room._room_case_card = _room_case_card
    setattr(customer_ui, _FLAG, VERSION)
    if logger:
        logger.info(
            "CUSTOMER_WORK_NOTE_CARD_REBOUND version=%s stable_keys=1 exact_room_card=1 room_detail_route=1 safe_html=1 processing=1 today=1 detail=1 room=1 data_migration=0",
            VERSION,
        )
