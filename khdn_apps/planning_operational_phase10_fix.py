"""Small safety shim for operational phase 10 legacy-contact migration."""
from __future__ import annotations

from khdn_apps import planning_operational_phase10_patch as phase10
from khdn_apps import planning_operational_phase11_patch as phase11

VERSION = "1.1.0"


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
    if logger:
        logger.info("PLANNING_OPERATIONAL_PHASE10_FIX_INSTALLED null_actor_for_legacy_migration=1 phase11_last=1")
