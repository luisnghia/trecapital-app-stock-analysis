"""Final installer for operational planning Phase 3."""
from __future__ import annotations

from khdn_apps import planning_operational_phase3_core as core
from khdn_apps import planning_operational_phase3_weekly as weekly
from khdn_apps import planning_operational_phase3_dashboard as dashboard

VERSION = "1.0.0"
_FLAG = "_PLANNING_OPERATIONAL_PHASE3_VERSION"


def install(app_ns, policy, weekly_core, customer_core, customer_ui, logger=None):
    if getattr(policy, _FLAG, None) == VERSION:
        return
    get_conn = app_ns["get_conn"]
    core.ensure_schema(get_conn, logger)
    core.install_realtime_token(app_ns, get_conn, logger)
    core.install_event_wrappers(customer_core, logger)
    core.install_unique_card_context(logger)
    core.install_case_detail(customer_ui, customer_core, logger)
    weekly.install_weekly_staff(policy, weekly_core, logger)
    dashboard.install_today_page(customer_ui, customer_core, policy, weekly_core, logger)
    dashboard.install_room_dashboard(customer_ui, customer_core, policy, weekly_core, logger)
    setattr(policy, _FLAG, VERSION)
    if logger:
        logger.info("PLANNING_OPERATIONAL_PHASE3_INSTALLED version=%s realtime=1 mandatory_stage_note=1 attention_ack=1 approval_board=1 backlog_fix=1 rich_today=1 card_progress=1 room_detail_lists=1", VERSION)
