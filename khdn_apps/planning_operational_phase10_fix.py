"""Small safety shim for operational phase 10 legacy-contact migration."""
from __future__ import annotations

from khdn_apps import planning_operational_phase10_patch as phase10
from khdn_apps import planning_operational_phase11_patch as phase11
from khdn_apps import planning_operational_phase12_patch as phase12
from khdn_apps import planning_operational_phase13_patch as phase13
from khdn_apps import planning_operational_phase14_patch as phase14
from khdn_apps import planning_operational_phase15_patch as phase15
from khdn_apps import customer_cif_admin_patch as customer_cif_admin
from khdn_apps import mobile_input_performance_patch as mobile_input_perf

VERSION = "1.8.0"
_LEGACY_IMPORT_GUARD = "_CUSTOMER_CIF_LEGACY_IMPORT_GUARD"


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


def _install_legacy_customer_import_guard(app_ns, logger=None):
    """Disable the old CIF-only upsert button; the safe reconcile flow replaces it.

    The wrapper is installed once on the shared Streamlit module, but the route
    check uses session-local state, so other pages/buttons remain untouched.
    """
    if app_ns.get(_LEGACY_IMPORT_GUARD):
        return
    st = app_ns.get("st")
    if st is None or not hasattr(st, "button"):
        return
    original_button = st.button

    def guarded_button(label, *args, **kwargs):
        is_customer_admin = (
            str(label) == "Nạp/Đồng bộ khách hàng"
            and st.session_state.get("main_page") == "admin"
            and str(st.session_state.get("admin_scope", "system")) == "system"
            and st.session_state.get("admin_view") == "customers"
        )
        if is_customer_admin:
            kwargs["disabled"] = True
            kwargs.setdefault(
                "help",
                "Cơ chế nạp cũ chỉ đối chiếu theo CIF nên đã được khóa. "
                "Hãy dùng tab 'Nạp CIF an toàn' ở phần Đối chiếu CIF bên dưới.",
            )
            return original_button(
                "Nạp/Đồng bộ khách hàng (đã thay bằng Nạp CIF an toàn)",
                *args,
                **kwargs,
            )
        return original_button(label, *args, **kwargs)

    st.button = guarded_button
    app_ns[_LEGACY_IMPORT_GUARD] = True
    if logger:
        logger.info("CUSTOMER_CIF_LEGACY_IMPORT_GUARD_INSTALLED disabled_old_cif_upsert=1")


def install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger=None):
    phase10._sync_customer_contacts = _safe_sync_customer_contacts
    phase10.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase11.install(app_ns, policy, weekly_core, customer_core, customer_ui, logger)
    phase12.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase13.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase14.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    phase15.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    customer_cif_admin.install(app_ns, logger)
    _install_legacy_customer_import_guard(app_ns, logger)
    # Must stay last: later planning/operations/admin overlays introduce native
    # inputs after the original V2.14 performance transformer had already run.
    mobile_input_perf.install(app_ns, policy, logger)
    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE10_FIX_INSTALLED "
            "null_actor_for_legacy_migration=1 phase11=1 phase12=1 phase13=1 "
            "phase14=1 phase15=1 customer_cif_admin=1 legacy_import_guard=1 "
            "mobile_input_perf_last=1"
        )
