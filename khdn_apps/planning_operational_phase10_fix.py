"""Small safety shim for operational phase 10 legacy-contact migration."""
from __future__ import annotations

from khdn_apps import planning_operational_phase10_patch as phase10
from khdn_apps import planning_operational_phase11_patch as phase11
from khdn_apps import planning_operational_phase12_patch as phase12
from khdn_apps import planning_operational_phase13_patch as phase13
from khdn_apps import planning_operational_phase14_patch as phase14
from khdn_apps import planning_operational_phase15_patch as phase15
from khdn_apps import mobile_input_performance_patch as mobile_input_perf
from khdn_apps import mobile_admin_restore_perf_patch as mobile_admin_restore
from khdn_apps import task_type_scope_runtime_fix as task_type_scope_fix

VERSION = "1.8.0"


def _safe_sync_customer_contacts(c, customer_id, contacts, actor_uid, ts, source_case_id=None):
    """Persist shared contacts; legacy migration uses NULL updated_by, never user id 0."""
    c.execute("DELETE FROM customer_contact_master WHERE customer_id=?", (int(customer_id),))
    safe_actor = int(actor_uid) if actor_uid and int(actor_uid) > 0 else None
    for slot, item in enumerate(contacts[:3], 1):
        c.execute(
            """INSERT INTO customer_contact_master(
               customer_id,slot,contact_name,contact_phone,contact_role,
               updated_by,updated_at,source_case_id)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                int(customer_id), int(slot), item["name"], item["phone"], item["role"],
                safe_actor, str(ts), int(source_case_id) if source_case_id else None,
            ),
        )


def install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger=None):
    phase10._sync_customer_contacts = _safe_sync_customer_contacts
    phase10.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase11.install(app_ns, policy, weekly_core, customer_core, customer_ui, logger)
    phase12.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase13.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase14.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase15.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    # Patch task-type migration first so the legacy global UNIQUE(name) is rebuilt
    # safely before the transformed init_db() runs, then install zero-keystroke
    # forms. The final restore owns System Admin navigation/render load.
    task_type_scope_fix.install(mobile_input_perf, app_ns, logger)
    mobile_input_perf.install(app_ns, policy, logger)
    mobile_admin_restore.install(app_ns, policy, logger)
    if logger:
        logger.info("PLANNING_OPERATIONAL_PHASE10_FIX_INSTALLED null_actor_for_legacy_migration=1 phase11=1 phase12=1 phase13=1 phase14=1 phase15=1 task_type_scope_fix=1 mobile_input_perf=1 mobile_admin_restore_last=1")
