"""Final reliability layer for Admin -> Khách hàng CIF -> Nạp CIF an toàn.

Fixes two production failure modes:
1) mixed files (existing CIF + new CIF) could be rolled back as one transaction
   when one row had an unresolved officer;
2) existing CIF rows could miss a QLKH refresh because the spreadsheet header,
   CIF representation or officer cell did not exactly match the narrow parser.

The importer now normalizes spreadsheet CIF values, recognizes common QLKH
headers/cells, applies each row under a SAVEPOINT, and reports row-level errors
without rolling back rows that were already valid. Existing Customer IDs and
all workflow links are preserved.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from khdn_apps import customer_cif_admin_patch as base

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_CIF_IMPORT_RELIABILITY_VERSION"


def _clean_cif(value):
    """Normalize Excel/CSV identifier formatting without stripping leading zeroes."""
    s = str(value or "").replace("\u00a0", " ").strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    if s.startswith("'"):
        s = s[1:].strip()
    s = re.sub(r"\s+", "", s)
    if re.fullmatch(r"\d+\.0+", s):
        return s.split(".", 1)[0]
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?[eE][+-]?\d+", s):
        try:
            d = Decimal(s)
            if d == d.to_integral_value():
                return format(d.quantize(Decimal("1")), "f")
        except (InvalidOperation, ValueError):
            pass
    return s


def _clean_text(value):
    s = str(value or "").replace("\u00a0", " ").strip()
    return "" if s.lower() in {"nan", "none", "null"} else s


def _eligible_qlkh_rows(c):
    rows = c.execute(
        "SELECT id,username,full_name,role FROM users WHERE active=1 ORDER BY id"
    ).fetchall()
    out = []
    for r in rows:
        role = base._norm(r[3])
        # Keep Customer Master ownership scoped to QLKH roles, while accepting
        # harmless suffixes such as '(chính)' in historical role labels.
        if "qlkh" in role.replace(" ", ""):
            out.append(r)
    return out


def _resolve_qlkh(c, raw):
    """Resolve username/full-name/composite spreadsheet cells to one active QLKH."""
    text = _clean_text(raw)
    if not text:
        return None
    nraw = base._norm(text)
    compact_raw = re.sub(r"[^a-z0-9]", "", nraw)
    raw_tokens = set(nraw.split())
    exact, embedded = [], []
    for r in _eligible_qlkh_rows(c):
        uid = int(r[0])
        nuser = base._norm(r[1])
        nname = base._norm(r[2])
        if nraw in {nuser, nname}:
            exact.append(uid)
            continue
        cuser = re.sub(r"[^a-z0-9]", "", nuser)
        cname = re.sub(r"[^a-z0-9]", "", nname)
        hit = False
        if nuser and (nuser in raw_tokens or (len(cuser) >= 3 and cuser in compact_raw)):
            hit = True
        if nname and len(nname) >= 4 and nname in nraw:
            hit = True
        if cname and len(cname) >= 6 and cname in compact_raw:
            hit = True
        if hit:
            embedded.append(uid)
    exact = sorted(set(exact))
    if len(exact) == 1:
        return exact[0]
    embedded = sorted(set(embedded))
    return embedded[0] if len(embedded) == 1 else None


def _find_existing_by_cif(c, cif):
    target = _clean_cif(cif)
    if not target:
        return None
    row = c.execute("SELECT * FROM customers WHERE cif=?", (target,)).fetchone()
    if row:
        return row
    matches = []
    for r in c.execute("SELECT * FROM customers WHERE cif IS NOT NULL AND trim(cif)<>''").fetchall():
        if _clean_cif(r["cif"]) == target:
            matches.append(r)
    if len(matches) > 1:
        raise ValueError(f"CIF {target} đang khớp nhiều bản ghi khách hàng; cần hợp nhất dữ liệu trước")
    return matches[0] if matches else None


def _apply_cif_row(c, actor_uid, *, cif, name, target_id=None, tax_id=None,
                   contact_name=None, contact_phone=None, qlkh_raw=None):
    cif_text = _clean_cif(cif)
    name_text = _clean_text(name)
    if not cif_text or not name_text:
        raise ValueError("CIF và Tên KH là bắt buộc")

    raw_qlkh = _clean_text(qlkh_raw)
    qid = None
    if raw_qlkh:
        qid = _resolve_qlkh(c, raw_qlkh)
        if qid is None:
            raise ValueError(
                f"CIF {cif_text}: không xác định được duy nhất Cán bộ QLKH '{raw_qlkh}' "
                "trong danh sách QLKH đang hoạt động"
            )

    existing = _find_existing_by_cif(c, cif_text)
    if existing:
        cid = int(existing["id"])
        if target_id and int(target_id) != cid:
            raise ValueError(
                f"CIF {cif_text} đã thuộc khách hàng ID {cid}; cần hợp nhất riêng nếu là cùng khách hàng"
            )
        old_qid = existing["qlkh_user_id"]
        old_source = _clean_text(existing["qlkh_source_text"])
        new_qid = qid if raw_qlkh else old_qid
        new_source = raw_qlkh if raw_qlkh else old_source
        c.execute(
            """UPDATE customers SET customer_name=?, tax_id=COALESCE(NULLIF(?,''),tax_id),
               contact_name=COALESCE(NULLIF(?,''),contact_name),
               contact_phone=COALESCE(NULLIF(?,''),contact_phone),
               qlkh_user_id=?, qlkh_source_text=?, customer_status='ACTIVE_CIF',active=1,updated_at=?
               WHERE id=?""",
            (
                name_text, _clean_text(tax_id), _clean_text(contact_name), _clean_text(contact_phone),
                int(new_qid) if new_qid is not None else None, new_source or None, base._now(), cid,
            ),
        )
        base._audit(
            c, actor_uid, "CUSTOMER_CIF_SAFE_UPDATE", cid,
            {
                "cif": cif_text,
                "qlkh_refresh_from_latest_file": bool(raw_qlkh),
                "old_qlkh_user_id": int(old_qid) if old_qid is not None else None,
                "new_qlkh_user_id": int(new_qid) if new_qid is not None else None,
                "old_qlkh_source_text": old_source or None,
                "new_qlkh_source_text": new_source or None,
            },
        )
        return cid, "UPDATED"

    if target_id:
        target_id = int(target_id)
        row = c.execute("SELECT * FROM customers WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy khách hàng ID {target_id}")
        current_cif = _clean_cif(row["cif"])
        if current_cif and current_cif != cif_text:
            raise ValueError(f"Khách hàng ID {target_id} đã có CIF khác: {current_cif}")
        old_qid = row["qlkh_user_id"]
        old_source = _clean_text(row["qlkh_source_text"])
        new_qid = qid if raw_qlkh else old_qid
        new_source = raw_qlkh if raw_qlkh else old_source
        c.execute(
            """UPDATE customers SET cif=?,customer_name=?,tax_id=COALESCE(NULLIF(?,''),tax_id),
               contact_name=COALESCE(NULLIF(?,''),contact_name),
               contact_phone=COALESCE(NULLIF(?,''),contact_phone),
               qlkh_user_id=?,qlkh_source_text=?,customer_status='ACTIVE_CIF',active=1,updated_at=?
               WHERE id=?""",
            (
                cif_text, name_text, _clean_text(tax_id), _clean_text(contact_name), _clean_text(contact_phone),
                int(new_qid) if new_qid is not None else None, new_source or None, base._now(), target_id,
            ),
        )
        base._audit(
            c, actor_uid, "PROSPECT_CUSTOMER_ACTIVATE_IMPORT", target_id,
            {"cif": cif_text, "new_qlkh_user_id": int(new_qid) if new_qid is not None else None},
        )
        return target_id, "ACTIVATED"

    ts = base._now()
    cur = c.execute(
        """INSERT INTO customers(cif,customer_name,qlkh_user_id,qlkh_source_text,active,created_at,updated_at,
           customer_status,tax_id,contact_name,contact_phone)
           VALUES(?,?,?,?,1,?,?,'ACTIVE_CIF',?,?,?)""",
        (
            cif_text, name_text, int(qid) if qid is not None else None, raw_qlkh or None, ts, ts,
            _clean_text(tax_id) or None, _clean_text(contact_name) or None, _clean_text(contact_phone) or None,
        ),
    )
    cid = int(cur.lastrowid)
    base._audit(
        c, actor_uid, "CUSTOMER_CIF_SAFE_CREATE", cid,
        {"cif": cif_text, "new_qlkh_user_id": int(qid) if qid is not None else None},
    )
    return cid, "CREATED"


def _pick_col(columns, aliases, kind=None):
    direct = base._pick_col(columns, aliases)
    if direct:
        return direct
    scored = []
    for col in columns:
        n = base._norm(col)
        compact = n.replace(" ", "")
        score = 0
        if kind == "qlkh" and (
            "qlkh" in compact
            or ("quan ly" in n and ("khach hang" in n or re.search(r"\bkh\b", n)))
        ):
            score = 100
        elif kind == "cif" and (compact == "cif" or "macif" in compact or compact.startswith("cif")):
            score = 100
        elif kind == "name" and (
            "tenkhachhang" in compact or "tenkh" in compact or "tendoanhnghiep" in compact
        ):
            score = 100
        if score:
            scored.append((score, str(col)))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[0][1] if scored else None


def _build_plan(df, c):
    cif_col = _pick_col(df.columns, ["CIF", "Mã CIF"], "cif")
    name_col = _pick_col(df.columns, ["Tên KH", "Tên khách hàng", "customer_name", "Tên DN"], "name")
    tax_col = _pick_col(df.columns, ["MST", "Mã số thuế", "tax_id"])
    qlkh_col = _pick_col(
        df.columns,
        [
            "CB QLKH", "CBQLKH", "QLKH", "Cán bộ QLKH", "Cán bộ QLKH phụ trách",
            "CB QLKH phụ trách", "Cán bộ quản lý KH", "Cán bộ quản lý khách hàng",
            "QLKH mới", "CB QLKH mới", "qlkh",
        ],
        "qlkh",
    )
    contact_col = _pick_col(df.columns, ["Người liên hệ", "contact_name"])
    phone_col = _pick_col(df.columns, ["SĐT", "Số điện thoại", "Điện thoại", "contact_phone"])
    if not cif_col or not name_col:
        raise ValueError("File phải có tối thiểu 2 cột: CIF và Tên KH/Tên khách hàng.")

    plan = []
    for idx, row in df.iterrows():
        cif = _clean_cif(row.get(cif_col, ""))
        name = _clean_text(row.get(name_col, ""))
        if not cif or not name:
            continue
        tax = _clean_text(row.get(tax_col, "")) if tax_col else ""
        existing = _find_existing_by_cif(c, cif)
        candidates = base._prospect_candidates(c, name, tax)
        exact_tax = [x for x in candidates if tax and base._norm(x.get("tax_id")) == base._norm(tax)]
        action, target = "CREATE", None
        if existing:
            action, target = "UPDATE", int(existing["id"])
        elif len(exact_tax) == 1:
            action, target = "ACTIVATE", int(exact_tax[0]["id"])
        elif candidates:
            action = "REVIEW"
        plan.append(
            {
                "row": int(idx), "cif": cif, "name": name, "tax": tax,
                "qlkh_raw": _clean_text(row.get(qlkh_col, "")) if qlkh_col else "",
                "contact_name": _clean_text(row.get(contact_col, "")) if contact_col else "",
                "contact_phone": _clean_text(row.get(phone_col, "")) if phone_col else "",
                "action": action, "target": target, "candidates": candidates,
            }
        )
    return plan, {"cif": cif_col, "name": name_col, "qlkh": qlkh_col}


def apply_import_items(c, actor_uid, items, decisions=None):
    """Apply mixed existing/new rows independently; one bad row cannot roll back all."""
    decisions = decisions or {}
    done = {"UPDATED": 0, "ACTIVATED": 0, "CREATED": 0, "SKIPPED": 0, "FAILED": 0}
    errors = []
    for pos, item in enumerate(items):
        target = item.get("target")
        if item.get("action") == "REVIEW":
            choice = decisions.get(item.get("row"), base._SKIP)
            if choice == base._SKIP:
                done["SKIPPED"] += 1
                continue
            target = None if choice == base._NEW else int(choice)
        sp = f"cifrow_{pos}"
        c.execute(f"SAVEPOINT {sp}")
        try:
            _, result = _apply_cif_row(
                c, actor_uid, cif=item.get("cif"), name=item.get("name"), target_id=target,
                tax_id=item.get("tax"), contact_name=item.get("contact_name"),
                contact_phone=item.get("contact_phone"), qlkh_raw=item.get("qlkh_raw"),
            )
            c.execute(f"RELEASE SAVEPOINT {sp}")
            done[result] = done.get(result, 0) + 1
        except Exception as exc:
            c.execute(f"ROLLBACK TO SAVEPOINT {sp}")
            c.execute(f"RELEASE SAVEPOINT {sp}")
            done["FAILED"] += 1
            errors.append(
                {
                    "Dòng": int(item.get("row", pos)) + 2,
                    "CIF": item.get("cif") or "",
                    "Tên KH": item.get("name") or "",
                    "Cán bộ QLKH": item.get("qlkh_raw") or "",
                    "Lỗi": str(exc),
                }
            )
    return done, errors


def _render_safe_import(st, u, get_conn, logger=None):
    st.markdown("#### 1) Nạp/đối chiếu CIF an toàn")
    st.caption(
        "File có thể đồng thời chứa CIF cũ và CIF mới. CIF đã có sẽ cập nhật thông tin/QLKH theo file mới; "
        "CIF mới sẽ được thêm mới hoặc kích hoạt đúng Customer ID PROSPECT. Một dòng lỗi không làm mất các dòng hợp lệ."
    )
    last = st.session_state.pop("cif_safe_last_result", None)
    if last:
        st.success(
            f"Kết quả lần nạp trước: {last.get('updated',0)} cập nhật; {last.get('activated',0)} kích hoạt PROSPECT; "
            f"{last.get('created',0)} khách mới; {last.get('skipped',0)} bỏ qua; {last.get('failed',0)} lỗi."
        )
        if last.get("errors"):
            import pandas as pd
            st.warning("Một số dòng chưa nạp được. Các dòng hợp lệ khác đã được lưu.")
            st.dataframe(pd.DataFrame(last["errors"]), use_container_width=True, hide_index=True)

    upload = st.file_uploader(
        "Tải file CIF để đối chiếu (Excel/CSV)", type=["xlsx", "xls", "csv"], key="cif_safe_import_file"
    )
    if not upload:
        return
    try:
        df = base._import_dataframe(upload)
    except Exception as exc:
        st.error(f"Không đọc được file: {exc}")
        return

    try:
        with get_conn() as c:
            plan, columns = _build_plan(df, c)
    except Exception as exc:
        st.error(str(exc))
        return
    if not plan:
        st.warning("Không có dòng CIF hợp lệ để xử lý.")
        return

    st.caption(
        "Đã nhận cột: "
        f"CIF = {columns.get('cif') or '—'} · Tên KH = {columns.get('name') or '—'} · "
        f"Cán bộ QLKH = {columns.get('qlkh') or 'không có cột QLKH'}"
    )

    import pandas as pd
    preview, decisions = [], {}
    unresolved = 0
    for item in plan:
        desc = {
            "UPDATE": "Cập nhật CIF đã có + QLKH theo file",
            "ACTIVATE": "Kích hoạt PROSPECT giữ nguyên ID",
            "CREATE": "Tạo khách hàng CIF mới",
            "REVIEW": "Cần xác nhận",
        }[item["action"]]
        qstatus = item.get("qlkh_raw") or "(để trống/giữ hiện tại)"
        preview.append(
            {
                "CIF": item["cif"], "Tên KH": item["name"], "Cán bộ QLKH file": qstatus,
                "Xử lý dự kiến": desc, "Customer ID": item["target"] or "",
            }
        )
        if item["action"] == "REVIEW":
            options = [base._SKIP, base._NEW] + [int(x["id"]) for x in item["candidates"]]
            by_id = {int(x["id"]): x for x in item["candidates"]}

            def _fmt(v, by_id=by_id):
                if v == base._SKIP:
                    return "— Chưa chọn / bỏ qua dòng này —"
                if v == base._NEW:
                    return "Tạo khách hàng CIF mới"
                candidate = by_id.get(int(v))
                if not candidate:
                    return str(v)
                return "Dùng khách hiện có: " + base._customer_label(candidate) + f" · {candidate.get('_reason','')}"

            choice = st.selectbox(
                f"Đối chiếu CIF {item['cif']} · {item['name']}", options, format_func=_fmt,
                key=f"cif_safe_decision_{item['row']}_{item['cif']}",
            )
            decisions[item["row"]] = choice
            if choice == base._SKIP:
                unresolved += 1

    st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)
    if unresolved:
        st.warning(f"Có {unresolved} dòng cần chọn cách xử lý. Dòng đang để 'bỏ qua' sẽ không được nạp.")

    if st.button("✅ Thực hiện nạp CIF an toàn", key="cif_safe_apply", type="primary", use_container_width=True):
        try:
            with get_conn() as c:
                c.execute("BEGIN IMMEDIATE")
                done, errors = apply_import_items(c, int(u["id"]), plan, decisions)
                c.commit()
            if logger:
                logger.info(
                    "CUSTOMER_CIF_RELIABLE_IMPORT actor=%s updated=%s activated=%s created=%s skipped=%s failed=%s",
                    u["id"], done["UPDATED"], done["ACTIVATED"], done["CREATED"],
                    done["SKIPPED"], done["FAILED"],
                )
            st.session_state["cif_safe_last_result"] = {
                "updated": done["UPDATED"], "activated": done["ACTIVATED"], "created": done["CREATED"],
                "skipped": done["SKIPPED"], "failed": done["FAILED"], "errors": errors,
            }
            st.rerun()
        except Exception as exc:
            st.error(f"Không thể hoàn tất nạp dữ liệu: {exc}")


def install(app_ns=None, logger=None):
    # Final owner of safe-import behavior. Reassert on every installer call.
    base._resolve_qlkh = _resolve_qlkh
    base.apply_cif_row = _apply_cif_row
    base._render_safe_import = _render_safe_import
    if isinstance(app_ns, dict):
        app_ns[_FLAG] = VERSION
    if logger:
        logger.info(
            "CUSTOMER_CIF_IMPORT_RELIABILITY_INSTALLED version=%s mixed_file=1 normalized_cif=1 qlkh_refresh=1 row_savepoint=1 customer_id_preserved=1 data_migration=0",
            VERSION,
        )
