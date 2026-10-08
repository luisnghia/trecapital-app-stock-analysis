"""Fallback policy for unresolved QLKH values during safe CIF import.

Business rule:
- Existing CIF: if the uploaded QLKH cannot be resolved uniquely, still import
  the customer row and keep the current QLKH assignment unchanged.
- New CIF: if the uploaded QLKH cannot be resolved uniquely, still import the
  customer row but leave QLKH blank.  This also applies when a new official CIF
  activates an existing PROSPECT record.

Only the unresolved-QLKH validation error is softened. Other row errors still
use the reliability layer's per-row SAVEPOINT/error reporting.
"""
from __future__ import annotations

from khdn_apps import customer_cif_admin_patch as base
from khdn_apps import customer_cif_import_reliability_patch as reliable

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_CIF_UNRESOLVED_QLKH_FALLBACK_VERSION"
_ORIGINAL_APPLY = reliable._apply_cif_row
_ERROR_TOKEN = "không xác định được duy nhất Cán bộ QLKH"


def _apply_with_qlkh_fallback(c, actor_uid, *, cif, name, target_id=None, tax_id=None,
                              contact_name=None, contact_phone=None, qlkh_raw=None):
    cif_text = reliable._clean_cif(cif)
    # Snapshot CIF existence before the row is applied. This distinguishes the
    # requested policies for existing-CIF and new-CIF rows.
    existing_before = reliable._find_existing_by_cif(c, cif_text)
    try:
        return _ORIGINAL_APPLY(
            c,
            actor_uid,
            cif=cif,
            name=name,
            target_id=target_id,
            tax_id=tax_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            qlkh_raw=qlkh_raw,
        )
    except ValueError as exc:
        if _ERROR_TOKEN not in str(exc):
            raise

        raw = reliable._clean_text(qlkh_raw)
        cid, result = _ORIGINAL_APPLY(
            c,
            actor_uid,
            cif=cif,
            name=name,
            target_id=target_id,
            tax_id=tax_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            qlkh_raw="",
        )

        if existing_before is None:
            # CIF is new to the official customer list. The row must still be
            # imported, but unresolved officer data must not be persisted.
            c.execute(
                "UPDATE customers SET qlkh_user_id=NULL, qlkh_source_text=NULL, updated_at=? WHERE id=?",
                (base._now(), int(cid)),
            )
            policy = "NEW_CIF_IMPORTED_QLKH_BLANK"
        else:
            # Existing CIF: blank fallback above deliberately preserves the
            # current assignment/source text in the reliability layer.
            policy = "EXISTING_CIF_KEEP_CURRENT_QLKH"

        base._audit(
            c,
            actor_uid,
            "CUSTOMER_CIF_UNRESOLVED_QLKH_FALLBACK",
            int(cid),
            {
                "cif": cif_text,
                "uploaded_qlkh": raw or None,
                "policy": policy,
                "result": result,
            },
        )
        return int(cid), result


def install(app_ns=None, logger=None):
    # apply_import_items() resolves reliable._apply_cif_row at execution time,
    # so rebinding both the reliability module and base module covers UI and
    # direct callers without touching existing customer/workflow data.
    reliable._apply_cif_row = _apply_with_qlkh_fallback
    base.apply_cif_row = _apply_with_qlkh_fallback
    if isinstance(app_ns, dict):
        app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "CUSTOMER_CIF_UNRESOLVED_QLKH_FALLBACK_INSTALLED version=%s "
            "existing_cif_keep_owner=1 new_cif_blank_owner=1 import_continues=1 data_migration=0",
            VERSION,
        )
