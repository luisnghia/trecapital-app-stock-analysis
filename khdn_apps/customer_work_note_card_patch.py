"""Final rerun-safe Customer Work card note overlay.

Purpose
-------
Show the persisted Customer Work ``note`` on every functional screen that
renders a Customer Work card, while preserving the existing card layout,
actions, priority heat, navigation and business logic.

This module is deliberately installed after all planning/runtime card patches.
It performs no schema migration and no background data write.
"""
from __future__ import annotations

import html

from khdn_apps import customer_work_refinement_patch as refinement
from khdn_apps import planning_final_ux_patch as finalux
from khdn_apps import planning_room_dashboard_detail_patch as room
from khdn_apps import planning_usability_v2_patch as v2
from khdn_apps import planning_usability_v3_patch as v3

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_WORK_NOTE_CARD_VERSION"


def _note_html(x, css_class="cwux-note"):
    """Return a safe, wrapped note block; blank notes do not consume card space."""
    raw = str((x or {}).get("note") or "").strip()
    if not raw:
        return ""
    note = html.escape(raw)
    return (
        f"<div class='{css_class}'>"
        f"📝 <b>Ghi chú:</b> <span>{note}</span>"
        "</div>"
    )


def _customer_card(st, customer_ui, refinement_module, x, get_conn, uid, manager,
                   logger=None, compact=False):
    """Canonical Customer Work card used by Processing/Today/detail/approval flows."""
    q = v2._q(x.get("quadrant")) or 4
    heat = refinement_module._HEAT[q]
    status_text, status_color, status_bg = refinement_module._status_meta(x)
    customer = html.escape(str(x.get("customer_name") or "—"))
    case_type = html.escape(str(x.get("case_type") or x.get("title") or "Công việc"))
    title = html.escape(str(x.get("title") or ""))
    code = html.escape(str(x.get("case_code") or ""))
    owner = html.escape(str(x.get("owner_name") or "—"))
    controller = html.escape(str(x.get("controller_name") or "—"))
    stage = html.escape(str(x.get("stage_name") or "—"))
    elapsed = html.escape(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    created = html.escape(customer_ui._dt_text(x.get("created_at")))
    due = html.escape(customer_ui._date_text(x.get("expected_complete_at")))
    issues = int(x.get("open_issue_count") or 0)
    contact = html.escape(str(x.get("contact_name") or ""))
    contact_phone = html.escape(str(x.get("contact_phone") or ""))
    contact_role = html.escape(str(x.get("contact_role") or ""))
    approval = str(x.get("plan_approval_status") or "PENDING")
    cid = int(x["id"])
    ctx = finalux._render_context()
    card_key = f"cwux_card_{cid}_{ctx}"
    note_block = _note_html(x, "cwux-note")

    with st.container(key=card_key, border=True):
        c1, c2, c3 = st.columns([5.5, 1.5, 3.0], vertical_alignment="top")
        with c1:
            st.markdown(
                f"<div class='cwux-title'>{customer} <span>·</span> {case_type}</div>"
                + (
                    f"<div class='cwux-work'>📌 {title}</div>"
                    if title and title.casefold() != case_type.casefold()
                    else ""
                ),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"<div class='cwux-code'>{code}</div>", unsafe_allow_html=True)
        with c3:
            if not compact and st.button(
                "🔎 Chi tiết", key=f"cwux_open_{cid}_{ctx}", use_container_width=True
            ):
                st.session_state["cw_case_id"] = cid
                st.rerun()

        st.markdown(
            f"<div class='cwux-row'><span>🕒 <b>Tạo lúc:</b> {created}</span>"
            f"<span>👤 <b>Phụ trách:</b> {owner}</span>"
            f"<span>🛡️ <b>Kiểm soát:</b> {controller}</span></div>"
            f"<div class='cwux-row'><span>📍 <b>{stage}</b></span><span>⏱ {elapsed}</span>"
            f"<span class='cwux-pill' style='color:{status_color};background:{status_bg}'>{status_text}</span></div>"
            f"<div class='cwux-row'><span>🎯 <b>Dự kiến:</b> {due}</span>"
            f"<span>⚠ <b>Vướng mắc:</b> {issues}</span>"
            f"<span class='cwux-pill' style='color:{heat['accent']};background:{heat['bg']};"
            f"border:1px solid {heat['border']}'>{v2._priority_label(q)}</span></div>"
            + note_block
            + (
                f"<div class='cwux-contact'>☎ <b>{contact}</b> · {contact_role} · {contact_phone}</div>"
                if contact or contact_phone else ""
            )
            + f"""
            <style>
            div[class*='st-key-{card_key}']{{
                border-left:6px solid {heat['accent']}!important;
                background:linear-gradient(120deg,{heat['bg']},rgba(6,78,72,.06))!important;
                box-shadow:0 6px 16px rgba(0,0,0,.09)
            }}
            div[class*='st-key-cwux_open_{cid}_{ctx}'] button{{
                background:linear-gradient(135deg,#F4B41A,#FFD45A)!important;
                color:#2B2410!important;-webkit-text-fill-color:#2B2410!important;
                border:2px solid #FFE589!important;font-weight:950!important;
            }}
            .cwux-title{{font-size:1.04rem;font-weight:950;color:#63DCCB;line-height:1.25}}
            .cwux-title span{{opacity:.7}}
            .cwux-work{{font-size:.82rem;font-weight:750;margin-top:3px}}
            .cwux-code{{font-size:.78rem;font-weight:950;color:#F4B41A;text-align:right;padding-top:.24rem}}
            .cwux-row{{display:flex;flex-wrap:wrap;gap:7px 14px;align-items:center;font-size:.83rem;margin-top:7px}}
            .cwux-pill{{padding:2px 7px;border-radius:999px;font-weight:900}}
            .cwux-note{{font-size:.80rem;line-height:1.42;margin-top:8px;padding:7px 9px;
                border-left:3px solid rgba(99,220,203,.58);border-radius:7px;
                background:rgba(99,220,203,.055);white-space:pre-wrap;overflow-wrap:anywhere}}
            .cwux-note span{{font-weight:500}}
            .cwux-contact{{font-size:.80rem;margin-top:7px;opacity:.94}}
            @media(max-width:760px){{
                .cwux-title{{font-size:.96rem}}
                .cwux-row,.cwux-note,.cwux-contact{{font-size:.76rem}}
                .cwux-code{{text-align:left}}
            }}
            </style>""",
            unsafe_allow_html=True,
        )

        if approval == "PENDING":
            st.warning("Kế hoạch công việc đang chờ phê duyệt.")
            if manager:
                approve_col, reject_col = st.columns(2)
                if approve_col.button(
                    "✅ Phê duyệt",
                    key=f"cwux_approve_{cid}_{ctx}",
                    type="primary",
                    use_container_width=True,
                ):
                    customer_ui.core.approve_case_plan(
                        get_conn, cid, int(uid), approve=True, note=None, logger=logger
                    )
                    st.toast("Đã phê duyệt công việc.", icon="✅")
                    st.rerun()
                if reject_col.button(
                    "↩ Từ chối",
                    key=f"cwux_reject_{cid}_{ctx}",
                    use_container_width=True,
                ):
                    customer_ui.core.approve_case_plan(
                        get_conn, cid, int(uid), approve=False, note=None, logger=logger
                    )
                    st.toast("Đã từ chối công việc.", icon="↩")
                    st.rerun()
        elif approval == "REJECTED":
            st.error(
                "Kế hoạch đã bị từ chối."
                + (f" {x.get('approval_note')}" if x.get("approval_note") else "")
            )
    return None


def _room_case_card(st, customer_ui, x):
    """Room dashboard card, including the same persisted Customer Work note."""
    q = room.priority_today._quadrant(x)
    heat = room.priority_today._HEAT[q]
    status_text, status_color, status_bg = ("🟢 Trong hạn", "#12B76A", "rgba(18,183,106,.12)")
    if x.get("is_overdue"):
        status_text, status_color, status_bg = ("🔴 Quá hạn", "#F04438", "rgba(240,68,56,.14)")
    elif x.get("is_stage_delayed"):
        status_text, status_color, status_bg = ("🔴 Mục bị chậm", "#F04438", "rgba(240,68,56,.14)")
    elif x.get("is_stage_warning"):
        status_text, status_color, status_bg = ("🟠 Sắp chậm", "#F79009", "rgba(247,144,9,.14)")

    customer = room._esc(x.get("customer_name"))
    case_type = room._esc(x.get("case_type") or "Công việc")
    title = room._esc(x.get("title") or "")
    code = room._esc(x.get("case_code") or "")
    owner = room._esc(x.get("owner_name") or "—")
    stage = room._esc(x.get("stage_name") or "—")
    elapsed = room._esc(customer_ui.core.duration_text(x.get("stage_elapsed_hours")))
    due = room._dt(x.get("expected_complete_at"))
    issues = int(x.get("open_issue_count") or 0)
    priority = room._esc(customer_ui.core.quadrant_label(q))
    work_line = "" if not title or title.casefold() == case_type.casefold() else f'<div class="rd-work">📌 {title}</div>'
    note_block = _note_html(x, "rd-note")

    st.markdown(
        f"""<div class="rd-card" style="--a:{heat['accent']};--b:{heat['border']};--bg:{heat['bg']};">
          <div class="rd-head"><div><div class="rd-title">{customer} <span>·</span> {case_type}</div>{work_line}</div><div class="rd-code">{code}</div></div>
          <div class="rd-row"><span>👤 <b>{owner}</b></span><span>📍 {stage}</span><span>⏱ {elapsed}</span><span class="rd-pill" style="color:{status_color};background:{status_bg};">{status_text}</span></div>
          <div class="rd-row"><span>🎯 <b>Dự kiến:</b> {room._esc(due)}</span><span>⚠ <b>Vướng mắc:</b> {issues}</span><span class="rd-priority" style="border-color:{heat['border']};background:{heat['bg']};color:{heat['accent']};">{heat['icon']} {priority}</span></div>
          {note_block}
        </div>
        <style>
          .rd-card{{border:1px solid var(--b);border-left:7px solid var(--a);border-radius:13px;padding:12px 14px;margin:.30rem 0 .30rem 0;background:linear-gradient(120deg,var(--bg),rgba(6,78,72,.07));}}
          .rd-head{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}}
          .rd-title{{font-size:1rem;font-weight:950;color:#63DCCB;line-height:1.25}} .rd-title span{{opacity:.7}}
          .rd-code{{font-size:.76rem;font-weight:900;color:#F4B41A;white-space:nowrap}} .rd-work{{font-size:.80rem;font-weight:760;margin-top:3px}}
          .rd-row{{display:flex;flex-wrap:wrap;gap:7px 14px;margin-top:8px;align-items:center;font-size:.81rem;line-height:1.35}}
          .rd-pill,.rd-priority{{padding:3px 8px;border-radius:999px;font-weight:900}} .rd-priority{{border:1px solid}}
          .rd-note{{font-size:.80rem;line-height:1.42;margin-top:8px;padding:7px 9px;border-left:3px solid rgba(99,220,203,.58);border-radius:7px;background:rgba(99,220,203,.055);white-space:pre-wrap;overflow-wrap:anywhere}}
          .rd-note span{{font-weight:500}}
        </style>""",
        unsafe_allow_html=True,
    )
    if st.button("🔎 Chi tiết", key=f"room_case_detail_{int(x.get('id') or 0)}", use_container_width=True):
        st.session_state["cw_case_id"] = int(x["id"])
        st.session_state["main_section"] = "plan"
        st.session_state["main_page"] = "customer_work"
        st.rerun()


def _case_card_bridge(st, x, get_conn, uid, manager, logger=None, compact=False):
    from khdn_apps import customer_work_ui
    return _customer_card(
        st, customer_work_ui, refinement, x, get_conn, uid, manager, logger, compact
    )


def install(customer_ui, logger=None):
    """Rebind all active Customer Work card entry points on every Streamlit run."""
    # No early return by design: later/historical patches may rebind renderers on rerun.
    finalux._customer_card = _customer_card
    v2._card = _customer_card
    v3._card = _customer_card
    customer_ui._case_card = _case_card_bridge
    room._room_case_card = _room_case_card
    setattr(customer_ui, _FLAG, VERSION)
    if logger:
        logger.info(
            "CUSTOMER_WORK_NOTE_CARD_REBOUND version=%s processing=1 today=1 detail=1 room=1 reschedule=1 approvals_existing_note=1 blank_note_hidden=1",
            VERSION,
        )
