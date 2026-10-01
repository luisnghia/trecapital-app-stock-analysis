"""Small safety shim for operational phase 10 legacy-contact migration."""
from __future__ import annotations

from khdn_apps import planning_operational_phase10_patch as phase10
from khdn_apps import planning_operational_phase11_patch as phase11
from khdn_apps import planning_operational_phase12_patch as phase12
from khdn_apps import planning_operational_phase13_patch as phase13
from khdn_apps import planning_operational_phase14_patch as phase14
from khdn_apps import planning_operational_phase15_patch as phase15
from khdn_apps import operations_owner_roster_patch as operations_owner_roster
from khdn_apps import customer_cif_admin_patch as customer_cif_admin
from khdn_apps import mobile_input_performance_patch as mobile_input_perf
from khdn_apps import mobile_admin_restore_perf_patch as mobile_admin_restore
from khdn_apps import mobile_legacy_ui_perf_patch as mobile_legacy_ui_perf
from khdn_apps import task_type_scope_runtime_fix as task_type_scope_fix
from khdn_apps import catalog_command_nav_restore_patch as catalog_nav_restore

VERSION = "1.10.0"
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
    """Disable the old CIF-only upsert button; safe reconcile flow replaces it."""
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
    # Expand the owner roster used by Phase 14's leader-side Tạo / giao hồ sơ:
    # active QLKH + active Lãnh đạo phòng.  This only changes selectable user IDs;
    # it never rewrites historical tasks or changes the task schema.
    operations_owner_roster.install(app_ns, logger)
    phase15.install(app_ns, policy, weekly_core, customer_core, customer_ui, worktype, logger)
    # Patch task-type migration first so the legacy global UNIQUE(name) is rebuilt
    # safely before the transformed init_db() runs, then install zero-keystroke
    # forms. The final legacy-UI layer owns Admin grid + Customer Work catalog
    # renderers only; it performs no data migration or background data write.
    task_type_scope_fix.install(mobile_input_perf, app_ns, logger)
    mobile_input_perf.install(app_ns, policy, logger)
    mobile_admin_restore.install(app_ns, policy, logger)

    # The mobile performance renderer must retain the original two command-button
    # navigation (cream inactive, teal+gold active), not fall back to st.tabs.
    # Patch the installer before both this call and the final rerun-safe
    # global-zero-keystroke layer invoke it.
    catalog_nav_restore.patch_legacy_installer(mobile_legacy_ui_perf, logger)
    mobile_legacy_ui_perf.install(app_ns, policy, customer_core, customer_ui, worktype, logger)

    # Install Customer CIF tools after all Admin render overlays so the wrapper is
    # not replaced later. The legacy CIF-only importer is locked on this route.
    customer_cif_admin.install(app_ns, logger)
    _install_legacy_customer_import_guard(app_ns, logger)

    if logger:
        logger.info(
            "PLANNING_OPERATIONAL_PHASE10_FIX_INSTALLED null_actor_for_legacy_migration=1 phase11=1 phase12=1 phase13=1 phase14=1 operations_owner_roster=1 phase15=1 task_type_scope_fix=1 mobile_input_perf=1 mobile_admin_restore=1 catalog_command_nav=1 mobile_legacy_ui_perf=1 customer_cif_admin=1 legacy_import_guard=1 customer_cif_admin_last=1"
        )
