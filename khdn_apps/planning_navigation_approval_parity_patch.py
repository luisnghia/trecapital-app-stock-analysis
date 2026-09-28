"""Navigation state reset + approval-card parity for planning UX.

Requested guarantees:
- leaving Customer Work detail via the main Kế hoạch command bar clears cw_case_id;
- Today defensively clears any stale Customer Work detail state before rendering;
- customer-work approval cards reuse the exact same business card renderer as
  the Customer Work "Đang xử lý" screen, while keeping approval-note controls.
"""
from __future__ import annotations

from khdn_apps import customer_work_patch as customer_nav
from khdn_apps import planning_dashboard_consolidation_patch as consolidation

VERSION = "1.0.0"
_FLAG = "_PLANNING_NAV_APPROVAL_PARITY_VERSION"


def install(policy, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return

    # Navigation must not carry a selected Customer Work detail into other
    # planning pages.  Wrap the final command-tab renderer so this remains true
    # even after the V3 Customer Work navigation wrapper has been installed.
    original_tabs = customer_nav._render_command_tabs

    def render_command_tabs(st, section, current, options, role, admin):
        original_button = st.button

        def button(label, *args, **kwargs):
            clicked = original_button(label, *args, **kwargs)
            key = str(kwargs.get("key") or "")
            if clicked and key.startswith("khdn_subtab_") and not key.endswith("_customer_work"):
                st.session_state.pop("cw_case_id", None)
            return clicked

        st.button = button
        try:
            return original_tabs(st, section, current, options, role, admin)
        finally:
            st.button = original_button

    customer_nav._render_command_tabs = render_command_tabs

    # Defensive reset as a second line of protection.  Even if Today is reached
    # programmatically, an old cw_case_id can never force Customer Work detail UI
    # to survive on the Today page.
    original_today = customer_ui.render_today_page

    def render_today_page(st, u, get_conn, page_title=None, logger=None, **kwargs):
        st.session_state.pop("cw_case_id", None)
        return original_today(
            st=st,
            u=u,
            get_conn=get_conn,
            page_title=page_title,
            logger=logger,
            **kwargs,
        )

    customer_ui.render_today_page = render_today_page

    # Approval card parity: use the exact current Customer Work card renderer.
    # manager=False suppresses its embedded approval buttons so the dedicated
    # approval center can retain the opinion/note field and audited decision
    # controls directly below the card.
    def render_case_approval_card(st, policy_arg, customer_core_arg, get_conn, x, uid, logger=None):
        customer_ui._case_card(
            st,
            x,
            get_conn,
            int(uid),
            False,
            logger,
            compact=True,
        )
        iid = int(x.get("id") or 0)
        note = st.text_input("Ý kiến phê duyệt", key=f"pd_case_note_{iid}")
        approve_col, reject_col = st.columns(2)
        if approve_col.button(
            "✓ Phê duyệt",
            key=f"pd_case_yes_{iid}",
            type="primary",
            use_container_width=True,
        ):
            customer_core_arg.approve_case_plan(
                get_conn, iid, int(uid), True, note, logger
            )
            st.rerun()
        if reject_col.button(
            "✕ Từ chối",
            key=f"pd_case_no_{iid}",
            use_container_width=True,
        ):
            customer_core_arg.approve_case_plan(
                get_conn, iid, int(uid), False, note, logger
            )
            st.rerun()

    consolidation._render_case_approval_card = render_case_approval_card

    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info(
            "PLANNING_NAV_APPROVAL_PARITY_INSTALLED version=%s clear_detail_on_leave=1 today_defensive_reset=1 approval_card_processing_parity=1",
            VERSION,
        )
