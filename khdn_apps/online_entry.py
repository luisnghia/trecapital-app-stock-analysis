"""Standalone online entrypoint for KHDN Ops.
Use this entrypoint on Railway/Render; the Trecapital embedded page continues to use pages/KHDNApps.py.
"""
import os
import sqlite3
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("KHDN_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("KHDN_CLOUD_MODE", "1")
os.environ.setdefault("KHDN_DB_PATH", str(DATA_DIR / "khdn_ops.db"))

import khdn_apps.app as _app_module
import khdn_apps.cbht_workload_patch as _workload_patch_module
import khdn_apps.full_task_edit_patch as _full_task_edit_module
import khdn_apps.weekly_plan as _weekly_plan_module
import khdn_apps.weekly_plan_ui as _weekly_plan_ui_module
import khdn_apps.customer_work as _customer_work_module
import khdn_apps.customer_work_patch as _customer_work_patch_module
import khdn_apps.customer_work_ui as _customer_work_ui_module
import khdn_apps.customer_work_refinement_patch as _customer_work_refinement_module
import khdn_apps.potential_customer_patch as _potential_customer_module
import khdn_apps.worktype_contact_card_patch as _worktype_contact_card_module
import khdn_apps.weekly_priority_policy_patch as _weekly_priority_policy_module
from khdn_apps.cbht_workload_patch import install as _install_v231
from khdn_apps.leader_workload_match_patch import install as _install_v2311
from khdn_apps.amount_decimal_patch import install as _install_v2312
from khdn_apps.full_task_edit_patch import install as _install_v2313
from khdn_apps.direct_task_edit_button_patch import install as _install_v2314
from khdn_apps.catalog_sync_patch import install as _install_v2316
from khdn_apps.notification_ui_patch import install as _install_v2320
from khdn_apps.weekly_plan_governance_patch import install as _install_weekly_governance
from khdn_apps.weekly_plan_patch import install as _install_weekly_plan
from khdn_apps.customer_work_patch import install as _install_customer_work
from khdn_apps.operations_admin_nav_patch import install as _install_ops_admin_nav
from khdn_apps.priority_today_patch import install as _install_priority_today
from khdn_apps.potential_customer_patch import install as _install_potential_customer, _label as _potential_customer_label
from khdn_apps.planning_priority_patch import install as _install_planning_priority_v2
from khdn_apps.priority_workflow_patch import install as _install_priority_workflow_bridge
from khdn_apps.catalog_edit_state_patch import install as _install_catalog_edit_state_fix
from khdn_apps.customer_work_refinement_patch import install as _install_customer_work_refinement
from khdn_apps.customer_work_signature_fix import install as _install_customer_work_signature_fix
from khdn_apps.auto_remember_login_patch import install as _install_auto_remember_login
from khdn_apps.worktype_contact_card_patch import install as _install_worktype_contact_card
from khdn_apps.worktype_contact_postfix import install as _install_worktype_contact_postfix
from khdn_apps.planning_usability_v2_patch import install as _install_planning_usability_v2
from khdn_apps.planning_ui_admin_hotfix import install_pre as _install_planning_ui_pre
from khdn_apps.planning_ui_admin_hotfix import install_post as _install_planning_ui_post
from khdn_apps.planning_usability_v3_patch import install as _install_planning_usability_v3
from khdn_apps.planning_usability_v3_hotfix import install as _install_planning_usability_v3_hotfix
from khdn_apps.weekly_priority_policy_patch import install as _install_weekly_priority_policy
from khdn_apps.weekly_priority_policy_hotfix import install as _install_weekly_priority_policy_hotfix
from khdn_apps.global_zero_keystroke_patch import install as _install_global_zero_keystroke
from khdn_apps.customer_work_note_card_patch import install as _install_customer_work_note_cards

_install_v231(_app_module.__dict__)
_install_v2311(_app_module.__dict__, _workload_patch_module)
_install_v2312(_app_module.__dict__)
_install_v2313(_app_module.__dict__)
_install_v2314(_app_module.__dict__, _full_task_edit_module)
_install_v2316(_app_module.__dict__)
_install_v2320(_app_module.__dict__)
_install_weekly_governance(_weekly_plan_module, _app_module.__dict__.get("LOGGER"))
# Install before Weekly Plan/Customer Work navigation. Priority Today captures the
# prospect-aware customer-work create form installed here.
_install_potential_customer(
    _app_module.__dict__,
    _customer_work_module,
    _customer_work_ui_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
_weekly_plan_ui_module._customer_label = _potential_customer_label
_install_weekly_plan(_app_module.__dict__)
_install_customer_work(_app_module.__dict__)
_install_ops_admin_nav(_customer_work_patch_module, _app_module.__dict__)
_install_priority_today(
    _customer_work_ui_module,
    _customer_work_patch_module,
    _weekly_plan_module,
    _app_module.__dict__.get("LOGGER"),
)
# Priority V2 owns heat dashboard, per-item persisted priority and leader approval editing.
_install_planning_priority_v2(
    _customer_work_module,
    _customer_work_ui_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# Final UX bridge adds the always-visible QLKH selector and Q1..Q4 quick-input override.
_install_priority_workflow_bridge(
    _customer_work_ui_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# Catalog state sync keeps select-to-edit reliable for both catalog tabs.
_install_catalog_edit_state_fix(
    _customer_work_ui_module,
    _customer_work_module,
    _app_module.__dict__.get("LOGGER"),
)
# Final Customer Work UX/data-source refinement.
_install_customer_work_refinement(
    _app_module.__dict__,
    _customer_work_patch_module,
    _customer_work_module,
    _customer_work_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# The custom-page dispatcher invokes render_cases_page with keyword ``st=``.
# Normalize the final renderer signature after every Customer Work page patch.
_install_customer_work_signature_fix(
    _customer_work_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# Empty preview databases can be initialized by more than one Streamlit session at
# the same time. The legacy bootstrap checks COUNT(*) before inserting the default
# admin, so two sessions can race and the loser sees users.username UNIQUE failure.
# Keep the legacy initializer unchanged, but retry only that known bootstrap race.
if not getattr(_app_module, "_INIT_DB_RACE_SAFE_V1", False):
    _original_init_db = _app_module.init_db

    def _race_safe_init_db():
        for attempt in range(3):
            try:
                return _original_init_db()
            except sqlite3.IntegrityError as exc:
                if "UNIQUE constraint failed: users.username" not in str(exc) or attempt >= 2:
                    raise
                logger = _app_module.__dict__.get("LOGGER")
                if logger:
                    logger.warning("INIT_DB_BOOTSTRAP_RACE_RETRY attempt=%s error=%s", attempt + 1, exc)
                time.sleep(0.08 * (attempt + 1))

    _app_module.init_db = _race_safe_init_db
    _app_module._INIT_DB_RACE_SAFE_V1 = True

# Some headless/runtime checks import this entrypoint with a brand-new SQLite file.
# Create the legacy core tables before extension schemas that reference users/task_types.
_app_module.init_db()
# Partition Loại công việc by module, require case contacts, and compact the card action.
_install_worktype_contact_card(
    _app_module.__dict__,
    _customer_work_module,
    _customer_work_ui_module,
    _customer_work_refinement_module,
    _app_module.__dict__.get("LOGGER"),
)
# Replace only the create helper with a state-safe epoch reset implementation.
_install_worktype_contact_postfix(
    _customer_work_module,
    _customer_work_ui_module,
    _customer_work_refinement_module,
    _app_module.__dict__.get("LOGGER"),
)
# Install the command-tab bridge before V2 so V2 captures the exact same visual
# navigation function used by the main Kế hoạch command bar.
_install_planning_ui_pre(_app_module.__dict__, _app_module.__dict__.get("LOGGER"))
# Final planning usability layer: system-admin task types, blank required selectors,
# Customer Work priority, button subnav, stronger prospect de-duplication and card UX.
_install_planning_usability_v2(
    _app_module.__dict__,
    _customer_work_module,
    _customer_work_ui_module,
    _customer_work_refinement_module,
    _worktype_contact_card_module,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _potential_customer_module,
    _app_module.__dict__.get("LOGGER"),
)
# Last-mile fix: native System Admin task-type page, exact child command-tab styling,
# and get_conn-compatible approval dispatcher signature.
_install_planning_ui_post(
    _app_module.__dict__,
    _customer_work_ui_module,
    _worktype_contact_card_module,
    _app_module.__dict__.get("LOGGER"),
)
# Final business UX: red validation, self-owned staff work, leader controller,
# exact child command tabs, processing-default navigation and created-at card data.
_install_planning_usability_v3(
    _app_module.__dict__,
    _customer_work_module,
    _customer_work_ui_module,
    _customer_work_refinement_module,
    _worktype_contact_card_module,
    _customer_work_patch_module,
    _app_module.__dict__.get("LOGGER"),
)
# Bind child-navigation callbacks to Streamlit correctly. This is intentionally
# installed after V3 so Customer Work and Catalog both use the same command-button
# style as the main Kế hoạch strip without the V3 callback signature crash.
_install_planning_usability_v3_hotfix(
    _app_module.__dict__,
    _customer_work_module,
    _customer_work_ui_module,
    _customer_work_refinement_module,
    _worktype_contact_card_module,
    _app_module.__dict__.get("LOGGER"),
)
# Q2-first governance is installed last so no legacy free-choice priority or old
# underline catalog renderer can override the approved weekly-plan policy.
_install_weekly_priority_policy(
    _app_module.__dict__,
    _weekly_plan_module,
    _weekly_plan_ui_module,
    _customer_work_module,
    _customer_work_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
_install_weekly_priority_policy_hotfix(
    _weekly_priority_policy_module,
    _app_module.__dict__.get("LOGGER"),
)
# This final binding intentionally runs on EVERY Streamlit rerun. Earlier runtime
# hotfixes rebind Customer Work/Catalog renderers each run; without this step the
# submit-only input component can be replaced by native widgets after the first
# interaction, reintroducing typing lag on pages that also contain long tables.
_install_global_zero_keystroke(
    _app_module.__dict__,
    _weekly_priority_policy_module,
    _customer_work_module,
    _customer_work_ui_module,
    _worktype_contact_card_module,
    _app_module.__dict__.get("LOGGER"),
)
# Reassert the Customer Work note card after every renderer/hotfix binding above.
# This is presentation-only: it reads the persisted case note and performs no data migration.
_install_customer_work_note_cards(
    _customer_work_ui_module,
    _app_module.__dict__.get("LOGGER"),
)
# Successful logins automatically issue the existing 30-day device cookie.
_install_auto_remember_login(_app_module.__dict__)
_app_module.app()