"""Refresh the assigned QLKH from the newest safe-CIF import row.

Scope is deliberately narrow: when ``Nạp CIF an toàn`` receives a CIF that
already exists in ``customers``, a non-blank QLKH value in the uploaded row is
now authoritative for the current customer assignment.  The existing Customer
ID and every linked workflow record stay untouched.

Blank QLKH cells keep the current assignment.  A non-blank QLKH value that
cannot be resolved to exactly one active ``Cán bộ QLKH`` is rejected instead of
silently retaining the old officer, so the import cannot look successful while
leaving stale ownership behind.
"""
from __future__ import annotations

from khdn_apps import customer_cif_admin_patch as base

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_CIF_QLKH_REFRESH_VERSION"
_ORIGINAL_APPLY = base.apply_cif_row


def _resolve_latest_qlkh(c, raw):
    """Resolve the newest file value, allowing common 'code - full name' cells."""
    text = str(raw or "").strip()
    if not text:
        return None

    exact = base._resolve_qlkh(c, text)
    if exact is not None:
        return int(exact)

    nraw = base._norm(text)
    if not nraw:
        return None

    rows = c.execute(
        "SELECT id,username,full_name FROM users WHERE active=1 AND role='Cán bộ QLKH'"
    ).fetchall()
    matched = []
    raw_tokens = set(nraw.split())
    for row in rows:
        uid = int(row[0])
        nuser = base._norm(row[1])
        nname = base._norm(row[2])
        hit = False
        # Username/employee-code embedded in a composite spreadsheet cell.
        if nuser and len(nuser) >= 3 and nuser in raw_tokens:
            hit = True
        # Full name embedded alongside employee code/department text.
        if nname and len(nname) >= 5 and nname in nraw:
            hit = True
        if hit:
            matched.append(uid)

    unique = sorted(set(matched))
    return unique[0] if len(unique) == 1 else None


def _apply_cif_row_refresh(c, actor_uid, *, cif, name, target_id=None, tax_id=None,
                           contact_name=None, contact_phone=None, qlkh_raw=None):
    """Apply a safe-CIF row, making newest QLKH authoritative for existing CIF."""
    cif_text = str(cif or "").strip()
    name_text = str(name or "").strip()
    if not cif_text or not name_text:
        raise ValueError("CIF và Tên KH là bắt buộc")

    existing = c.execute("SELECT * FROM customers WHERE cif=?", (cif_text,)).fetchone()
    if not existing:
        return _ORIGINAL_APPLY(
            c,
            actor_uid,
            cif=cif_text,
            name=name_text,
            target_id=target_id,
            tax_id=tax_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            qlkh_raw=qlkh_raw,
        )

    cid = int(existing["id"])
    if target_id and int(target_id) != cid:
        raise ValueError(
            f"CIF {cif_text} đã thuộc khách hàng ID {cid}; cần hợp nhất riêng nếu là cùng khách hàng"
        )

    raw = str(qlkh_raw or "").strip()
    old_qid = existing["qlkh_user_id"]
    old_source = str(existing["qlkh_source_text"] or "").strip()
    if raw:
        new_qid = _resolve_latest_qlkh(c, raw)
        if new_qid is None:
            raise ValueError(
                f"CIF {cif_text}: không xác định được duy nhất Cán bộ QLKH '{raw}' trong danh sách người dùng đang hoạt động"
            )
        new_source = raw
    else:
        # No new ownership information in the file: do not erase a valid current assignment.
        new_qid = old_qid
        new_source = old_source

    c.execute(
        """UPDATE customers SET customer_name=?, tax_id=COALESCE(NULLIF(?,''),tax_id),
           contact_name=COALESCE(NULLIF(?,''),contact_name),
           contact_phone=COALESCE(NULLIF(?,''),contact_phone),
           qlkh_user_id=?, qlkh_source_text=?,
           customer_status='ACTIVE_CIF',active=1,updated_at=? WHERE id=?""",
        (
            name_text,
            str(tax_id or "").strip(),
            str(contact_name or "").strip(),
            str(contact_phone or "").strip(),
            int(new_qid) if new_qid is not None else None,
            new_source or None,
            base._now(),
            cid,
        ),
    )
    base._audit(
        c,
        actor_uid,
        "CUSTOMER_CIF_SAFE_UPDATE",
        cid,
        {
            "cif": cif_text,
            "qlkh_refresh_from_latest_file": bool(raw),
            "old_qlkh_user_id": int(old_qid) if old_qid is not None else None,
            "new_qlkh_user_id": int(new_qid) if new_qid is not None else None,
            "old_qlkh_source_text": old_source or None,
            "new_qlkh_source_text": new_source or None,
        },
    )
    return cid, "UPDATED"


def install(app_ns=None, logger=None):
    # Re-assert on every installer call because later runtime overlays may import
    # the base module again, while assigning the same function remains idempotent.
    base.apply_cif_row = _apply_cif_row_refresh
    if isinstance(app_ns, dict):
        app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "CUSTOMER_CIF_QLKH_REFRESH_INSTALLED version=%s existing_cif_latest_qlkh=1 blank_preserves=1 unresolved_blocks=1 customer_id_preserved=1 data_migration=0",
            VERSION,
        )
