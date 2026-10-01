"""Admin Customer CIF safety tools: reconcile/merge and bulk delete.

Adds an Admin-only panel to System Admin -> Customer CIF without changing the
legacy operations/history model. The key invariant is that an existing
PROSPECT keeps its customers.id when a real CIF later arrives.
"""
from __future__ import annotations

from datetime import datetime
import json
import re
import unicodedata

VERSION = "1.0.0"
_FLAG = "_CUSTOMER_CIF_ADMIN_PATCH_VERSION"
_NEW = "__CREATE_NEW_CUSTOMER__"
_SKIP = "__SKIP_ROW__"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm(value):
    text = unicodedata.normalize("NFD", str(value or "").strip().lower()).replace("đ", "d")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _qi(name):
    return '"' + str(name).replace('"', '""') + '"'


def _tables(c):
    return [str(r[0]) for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()]


def _customer_fk_columns(c):
    """Return [(table, column)] for declared FKs referencing customers(id)."""
    refs = []
    for table in _tables(c):
        if table == "customers":
            continue
        try:
            for fk in c.execute(f"PRAGMA foreign_key_list({_qi(table)})").fetchall():
                if str(fk[2]) == "customers" and str(fk[4] or "id") == "id":
                    refs.append((table, str(fk[3])))
        except Exception:
            continue
    return refs


def dependency_counts(c, customer_ids):
    ids = sorted({int(x) for x in customer_ids if x not in (None, "")})
    out = {cid: {} for cid in ids}
    if not ids:
        return out
    marks = ",".join("?" for _ in ids)
    for table, col in _customer_fk_columns(c):
        try:
            rows = c.execute(
                f"SELECT {_qi(col)} AS cid, COUNT(*) AS n FROM {_qi(table)} "
                f"WHERE {_qi(col)} IN ({marks}) GROUP BY {_qi(col)}",
                ids,
            ).fetchall()
            for row in rows:
                cid, n = int(row[0]), int(row[1] or 0)
                if n:
                    out.setdefault(cid, {})[table] = out.setdefault(cid, {}).get(table, 0) + n
        except Exception:
            continue
    return out


def _customer_rows(c):
    cols = {str(r[1]) for r in c.execute("PRAGMA table_info(customers)").fetchall()}
    wanted = [
        "id", "cif", "customer_name", "qlkh_user_id", "qlkh_source_text", "active",
        "created_at", "updated_at", "customer_status", "tax_id", "contact_name", "contact_phone",
    ]
    select = [x for x in wanted if x in cols]
    rows = c.execute(
        f"SELECT {','.join(_qi(x) for x in select)} FROM customers ORDER BY customer_name,id"
    ).fetchall()
    return [dict(r) for r in rows]


def _prospect_candidates(c, name, tax_id=None, limit=8):
    nn, ntax = _norm(name), _norm(tax_id)
    found = []
    for row in _customer_rows(c):
        if str(row.get("customer_status") or "").upper() != "PROSPECT" and str(row.get("cif") or "").strip():
            continue
        rn, rtax = _norm(row.get("customer_name")), _norm(row.get("tax_id"))
        reasons = []
        score = 0
        if ntax and rtax and ntax == rtax:
            score = 100
            reasons.append("trùng MST")
        if nn and rn and nn == rn:
            score = max(score, 98)
            reasons.append("trùng tên")
        elif nn and rn and (nn in rn or rn in nn):
            score = max(score, 90)
            reasons.append("tên gần giống")
        if reasons:
            item = dict(row)
            item["_score"] = score
            item["_reason"] = ", ".join(reasons)
            found.append(item)
    found.sort(key=lambda x: (-int(x.get("_score") or 0), str(x.get("customer_name") or "")))
    return found[:limit]


def _resolve_qlkh(c, raw):
    text = str(raw or "").strip()
    if not text:
        return None
    rows = c.execute(
        "SELECT id,username,full_name FROM users WHERE active=1 AND role='Cán bộ QLKH'"
    ).fetchall()
    n = _norm(text)
    exact = [r for r in rows if _norm(r[1]) == n or _norm(r[2]) == n]
    return int(exact[0][0]) if len(exact) == 1 else None


def _audit(c, actor_uid, action, object_id, detail):
    try:
        c.execute(
            "INSERT INTO system_audit(actor_user_id,action,object_type,object_id,detail,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (int(actor_uid) if actor_uid else None, action, "customer", str(object_id),
             json.dumps(detail, ensure_ascii=False), _now()),
        )
    except Exception:
        pass


def apply_cif_row(c, actor_uid, *, cif, name, target_id=None, tax_id=None,
                  contact_name=None, contact_phone=None, qlkh_raw=None):
    """Apply one official-CIF row while preserving a chosen PROSPECT id."""
    cif = str(cif or "").strip()
    name = str(name or "").strip()
    if not cif or not name:
        raise ValueError("CIF và Tên KH là bắt buộc")

    existing = c.execute("SELECT * FROM customers WHERE cif=?", (cif,)).fetchone()
    if existing:
        cid = int(existing["id"])
        if target_id and int(target_id) != cid:
            raise ValueError(
                f"CIF {cif} đã thuộc khách hàng ID {cid}; cần hợp nhất riêng nếu là cùng khách hàng"
            )
        qid = _resolve_qlkh(c, qlkh_raw)
        c.execute(
            """UPDATE customers SET customer_name=?, tax_id=COALESCE(NULLIF(?,''),tax_id),
               contact_name=COALESCE(NULLIF(?,''),contact_name),
               contact_phone=COALESCE(NULLIF(?,''),contact_phone),
               qlkh_user_id=CASE WHEN ? IS NULL THEN qlkh_user_id ELSE ? END,
               qlkh_source_text=CASE WHEN ?='' THEN qlkh_source_text ELSE ? END,
               customer_status='ACTIVE_CIF',active=1,updated_at=? WHERE id=?""",
            (name, str(tax_id or "").strip(), str(contact_name or "").strip(),
             str(contact_phone or "").strip(), qid, qid, str(qlkh_raw or "").strip(),
             str(qlkh_raw or "").strip(), _now(), cid),
        )
        _audit(c, actor_uid, "CUSTOMER_CIF_SAFE_UPDATE", cid, {"cif": cif})
        return cid, "UPDATED"

    qid = _resolve_qlkh(c, qlkh_raw)
    if target_id:
        target_id = int(target_id)
        row = c.execute("SELECT * FROM customers WHERE id=?", (target_id,)).fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy khách hàng ID {target_id}")
        current_cif = str(row["cif"] or "").strip()
        if current_cif and current_cif != cif:
            raise ValueError(f"Khách hàng ID {target_id} đã có CIF khác: {current_cif}")
        c.execute(
            """UPDATE customers SET cif=?,customer_name=?,tax_id=COALESCE(NULLIF(?,''),tax_id),
               contact_name=COALESCE(NULLIF(?,''),contact_name),
               contact_phone=COALESCE(NULLIF(?,''),contact_phone),
               qlkh_user_id=CASE WHEN ? IS NULL THEN qlkh_user_id ELSE ? END,
               qlkh_source_text=CASE WHEN ?='' THEN qlkh_source_text ELSE ? END,
               customer_status='ACTIVE_CIF',active=1,updated_at=? WHERE id=?""",
            (cif, name, str(tax_id or "").strip(), str(contact_name or "").strip(),
             str(contact_phone or "").strip(), qid, qid, str(qlkh_raw or "").strip(),
             str(qlkh_raw or "").strip(), _now(), target_id),
        )
        _audit(c, actor_uid, "PROSPECT_CUSTOMER_ACTIVATE_IMPORT", target_id, {"cif": cif})
        return target_id, "ACTIVATED"

    ts = _now()
    cur = c.execute(
        """INSERT INTO customers(cif,customer_name,qlkh_user_id,qlkh_source_text,active,created_at,updated_at,
           customer_status,tax_id,contact_name,contact_phone)
           VALUES(?,?,?,?,1,?,?,'ACTIVE_CIF',?,?,?)""",
        (cif, name, qid, str(qlkh_raw or "").strip() or None, ts, ts,
         str(tax_id or "").strip() or None, str(contact_name or "").strip() or None,
         str(contact_phone or "").strip() or None),
    )
    cid = int(cur.lastrowid)
    _audit(c, actor_uid, "CUSTOMER_CIF_SAFE_CREATE", cid, {"cif": cif})
    return cid, "CREATED"


def merge_customers(c, actor_uid, keep_id, merge_id):
    """Merge duplicate customer rows and preserve all declared FK history."""
    keep_id, merge_id = int(keep_id), int(merge_id)
    if keep_id == merge_id:
        raise ValueError("Hai bản ghi hợp nhất phải khác nhau")
    keep = c.execute("SELECT * FROM customers WHERE id=?", (keep_id,)).fetchone()
    src = c.execute("SELECT * FROM customers WHERE id=?", (merge_id,)).fetchone()
    if not keep or not src:
        raise ValueError("Không tìm thấy bản ghi khách hàng")
    keep_cif, src_cif = str(keep["cif"] or "").strip(), str(src["cif"] or "").strip()
    if keep_cif and src_cif and keep_cif != src_cif:
        raise ValueError("Hai bản ghi đều có CIF khác nhau; không cho phép tự động hợp nhất")

    tables = set(_tables(c))
    if "customer_contact_master" in tables:
        try:
            source_contacts = c.execute(
                "SELECT id,slot FROM customer_contact_master WHERE customer_id=? ORDER BY slot,id",
                (merge_id,),
            ).fetchall()
            for contact_id, slot in source_contacts:
                exists = c.execute(
                    "SELECT id FROM customer_contact_master WHERE customer_id=? AND slot=?",
                    (keep_id, slot),
                ).fetchone()
                if exists:
                    c.execute("DELETE FROM customer_contact_master WHERE id=?", (int(contact_id),))
                else:
                    c.execute(
                        "UPDATE customer_contact_master SET customer_id=? WHERE id=?",
                        (keep_id, int(contact_id)),
                    )
        except Exception:
            pass

    for table, col in _customer_fk_columns(c):
        if table == "customer_contact_master":
            continue
        try:
            c.execute(
                f"UPDATE {_qi(table)} SET {_qi(col)}=? WHERE {_qi(col)}=?",
                (keep_id, merge_id),
            )
        except Exception as exc:
            raise ValueError(f"Không thể chuyển lịch sử tại bảng {table}: {exc}") from exc

    final_cif = keep_cif or src_cif or None
    keep_status = "ACTIVE_CIF" if final_cif else "PROSPECT"
    final_name = str(keep["customer_name"] or "").strip()
    if (not keep_cif) and src_cif and str(src["customer_name"] or "").strip():
        final_name = str(src["customer_name"]).strip()
    qlkh = keep["qlkh_user_id"] if keep["qlkh_user_id"] is not None else src["qlkh_user_id"]
    tax_id = str(keep["tax_id"] or "").strip() or str(src["tax_id"] or "").strip() or None
    contact_name = str(keep["contact_name"] or "").strip() or str(src["contact_name"] or "").strip() or None
    contact_phone = str(keep["contact_phone"] or "").strip() or str(src["contact_phone"] or "").strip() or None
    qsource = str(keep["qlkh_source_text"] or "").strip() or str(src["qlkh_source_text"] or "").strip() or None
    c.execute(
        """UPDATE customers SET cif=?,customer_name=?,qlkh_user_id=?,qlkh_source_text=?,
           active=?,customer_status=?,tax_id=?,contact_name=?,contact_phone=?,updated_at=? WHERE id=?""",
        (final_cif, final_name, qlkh, qsource, 1 if final_cif else int(keep["active"] or 0),
         keep_status, tax_id, contact_name, contact_phone, _now(), keep_id),
    )
    c.execute("DELETE FROM customers WHERE id=?", (merge_id,))
    _audit(c, actor_uid, "CUSTOMER_MERGE", keep_id, {"merged_customer_id": merge_id, "cif": final_cif})
    return keep_id


def delete_customers_safe(c, actor_uid, customer_ids):
    """Hard-delete only unreferenced customer rows; linked history is protected."""
    ids = sorted({int(x) for x in customer_ids})
    deps = dependency_counts(c, ids)
    deleted, blocked = [], {}
    for cid in ids:
        links = deps.get(cid) or {}
        if sum(int(v) for v in links.values()) > 0:
            blocked[cid] = links
            continue
        row = c.execute("SELECT customer_name,cif FROM customers WHERE id=?", (cid,)).fetchone()
        if not row:
            continue
        _audit(c, actor_uid, "CUSTOMER_BULK_DELETE", cid, {"customer_name": row[0], "cif": row[1]})
        c.execute("DELETE FROM customers WHERE id=?", (cid,))
        deleted.append(cid)
    return deleted, blocked


def _pick_col(columns, aliases):
    lookup = {_norm(c): c for c in columns}
    for alias in aliases:
        if _norm(alias) in lookup:
            return lookup[_norm(alias)]
    return None


def _import_dataframe(upload):
    import pandas as pd
    if str(upload.name).lower().endswith(".csv"):
        return pd.read_csv(upload, dtype=str).fillna("")
    return pd.read_excel(upload, dtype=str).fillna("")


def _customer_label(row):
    cif = str(row.get("cif") or "").strip()
    status = str(row.get("customer_status") or "")
    tail = f"CIF {cif}" if cif else "Chưa có CIF"
    if status == "PROSPECT" and not cif:
        tail += " · PROSPECT"
    return f"#{row['id']} · {row.get('customer_name') or ''} · {tail}"


def _render_safe_import(st, u, get_conn, logger=None):
    st.markdown("#### 1) Nạp/đối chiếu CIF an toàn")
    st.caption(
        "Khi CIF mới khớp khách hàng chưa có CIF, hệ thống cập nhật trên đúng Customer ID cũ để giữ nguyên Kế hoạch, Công việc khách hàng và Tác nghiệp."
    )
    upload = st.file_uploader(
        "Tải file CIF để đối chiếu (Excel/CSV)",
        type=["xlsx", "xls", "csv"],
        key="cif_safe_import_file",
    )
    if not upload:
        return
    try:
        df = _import_dataframe(upload)
    except Exception as exc:
        st.error(f"Không đọc được file: {exc}")
        return

    cif_col = _pick_col(df.columns, ["CIF", "Mã CIF"])
    name_col = _pick_col(df.columns, ["Tên KH", "Tên khách hàng", "customer_name", "Tên DN"])
    tax_col = _pick_col(df.columns, ["MST", "Mã số thuế", "tax_id"])
    qlkh_col = _pick_col(df.columns, ["CB QLKH", "QLKH", "Cán bộ QLKH", "qlkh"])
    contact_col = _pick_col(df.columns, ["Người liên hệ", "contact_name"])
    phone_col = _pick_col(df.columns, ["SĐT", "Số điện thoại", "Điện thoại", "contact_phone"])
    if not cif_col or not name_col:
        st.error("File phải có tối thiểu 2 cột: CIF và Tên KH/Tên khách hàng.")
        return

    plan = []
    with get_conn() as c:
        for idx, row in df.iterrows():
            cif = str(row.get(cif_col, "")).strip()
            name = str(row.get(name_col, "")).strip()
            if not cif or not name or cif.lower() == "nan" or name.lower() == "nan":
                continue
            tax = str(row.get(tax_col, "")).strip() if tax_col else ""
            existing = c.execute(
                "SELECT id,customer_name,cif FROM customers WHERE cif=?", (cif,)
            ).fetchone()
            candidates = _prospect_candidates(c, name, tax)
            exact_tax = [x for x in candidates if tax and _norm(x.get("tax_id")) == _norm(tax)]
            action, target = "CREATE", None
            if existing:
                action, target = "UPDATE", int(existing[0])
            elif len(exact_tax) == 1:
                action, target = "ACTIVATE", int(exact_tax[0]["id"])
            elif candidates:
                action = "REVIEW"
            plan.append({
                "row": int(idx), "cif": cif, "name": name, "tax": tax,
                "qlkh_raw": str(row.get(qlkh_col, "")).strip() if qlkh_col else "",
                "contact_name": str(row.get(contact_col, "")).strip() if contact_col else "",
                "contact_phone": str(row.get(phone_col, "")).strip() if phone_col else "",
                "action": action, "target": target, "candidates": candidates,
            })
    if not plan:
        st.warning("Không có dòng CIF hợp lệ để xử lý.")
        return

    import pandas as pd
    preview = []
    decisions = {}
    unresolved = 0
    for item in plan:
        desc = {
            "UPDATE": "Cập nhật CIF đã có",
            "ACTIVATE": "Kích hoạt PROSPECT giữ nguyên ID",
            "CREATE": "Tạo khách hàng CIF mới",
            "REVIEW": "Cần xác nhận",
        }[item["action"]]
        preview.append({
            "CIF": item["cif"], "Tên KH": item["name"], "MST": item["tax"],
            "Xử lý dự kiến": desc, "Customer ID": item["target"] or "",
        })
        if item["action"] == "REVIEW":
            options = [_SKIP, _NEW] + [int(x["id"]) for x in item["candidates"]]
            by_id = {int(x["id"]): x for x in item["candidates"]}

            def _fmt(v, by_id=by_id):
                if v == _SKIP:
                    return "— Chưa chọn / bỏ qua dòng này —"
                if v == _NEW:
                    return "Tạo khách hàng CIF mới"
                candidate = by_id.get(int(v))
                if not candidate:
                    return str(v)
                return "Dùng khách hiện có: " + _customer_label(candidate) + f" · {candidate.get('_reason','')}"

            choice = st.selectbox(
                f"Đối chiếu CIF {item['cif']} · {item['name']}",
                options,
                format_func=_fmt,
                key=f"cif_safe_decision_{item['row']}_{item['cif']}",
            )
            decisions[item["row"]] = choice
            if choice == _SKIP:
                unresolved += 1

    st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)
    if unresolved:
        st.warning(
            f"Có {unresolved} dòng cần chọn cách xử lý. Các dòng đang để 'bỏ qua' sẽ không được nạp."
        )

    if st.button(
        "✅ Thực hiện nạp CIF an toàn",
        key="cif_safe_apply",
        type="primary",
        use_container_width=True,
    ):
        done = {"UPDATED": 0, "ACTIVATED": 0, "CREATED": 0, "SKIPPED": 0}
        try:
            with get_conn() as c:
                c.execute("BEGIN IMMEDIATE")
                for item in plan:
                    target = item["target"]
                    if item["action"] == "REVIEW":
                        choice = decisions.get(item["row"], _SKIP)
                        if choice == _SKIP:
                            done["SKIPPED"] += 1
                            continue
                        target = None if choice == _NEW else int(choice)
                    _, result = apply_cif_row(
                        c,
                        int(u["id"]),
                        cif=item["cif"],
                        name=item["name"],
                        target_id=target,
                        tax_id=item["tax"],
                        contact_name=item["contact_name"],
                        contact_phone=item["contact_phone"],
                        qlkh_raw=item["qlkh_raw"],
                    )
                    done[result] = done.get(result, 0) + 1
                c.commit()
            if logger:
                logger.info(
                    "CUSTOMER_CIF_SAFE_IMPORT actor=%s updated=%s activated=%s created=%s skipped=%s",
                    u["id"], done["UPDATED"], done["ACTIVATED"], done["CREATED"], done["SKIPPED"],
                )
            st.success(
                f"Hoàn tất: {done['ACTIVATED']} khách chưa CIF được kích hoạt giữ nguyên ID; "
                f"{done['UPDATED']} khách được cập nhật; {done['CREATED']} khách mới; "
                f"{done['SKIPPED']} dòng bỏ qua."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Không thể nạp dữ liệu. Toàn bộ giao dịch đã được hoàn tác: {exc}")


def _render_merge(st, u, get_conn, logger=None):
    st.markdown("#### 2) Hợp nhất khách hàng trùng")
    st.caption(
        "Dùng khi trước đây đã lỡ tồn tại 2 Customer ID cho cùng một khách hàng. Lịch sử liên kết sẽ được chuyển về bản ghi giữ lại."
    )
    with get_conn() as c:
        rows = _customer_rows(c)
    if len(rows) < 2:
        st.info("Chưa có đủ dữ liệu để hợp nhất.")
        return
    by_id = {int(r["id"]): r for r in rows}
    ids = list(by_id)
    keep = st.selectbox(
        "Bản ghi GIỮ LẠI",
        [None] + ids,
        format_func=lambda x: "— Chọn —" if x is None else _customer_label(by_id[int(x)]),
        key="cif_merge_keep",
    )
    merge_options = [None] + [x for x in ids if x != keep]
    src = st.selectbox(
        "Bản ghi HỢP NHẤT vào bản giữ lại",
        merge_options,
        format_func=lambda x: "— Chọn —" if x is None else _customer_label(by_id[int(x)]),
        key="cif_merge_src",
    )
    if keep and src:
        with get_conn() as c:
            dep = dependency_counts(c, [keep, src])
        total = sum((dep.get(int(src)) or {}).values())
        st.info(f"Bản ghi #{src} đang có {total} liên kết workflow sẽ được chuyển sang #{keep}.")
        confirm = st.checkbox(
            "Tôi xác nhận đây là cùng một khách hàng và muốn hợp nhất hai bản ghi.",
            key="cif_merge_confirm",
        )
        if st.button(
            "🔗 Hợp nhất khách hàng",
            key="cif_merge_apply",
            disabled=not confirm,
            use_container_width=True,
        ):
            try:
                with get_conn() as c:
                    c.execute("BEGIN IMMEDIATE")
                    merge_customers(c, int(u["id"]), int(keep), int(src))
                    c.commit()
                if logger:
                    logger.info("CUSTOMER_MERGE_DONE actor=%s keep=%s merged=%s", u["id"], keep, src)
                st.success(f"Đã hợp nhất #{src} vào #{keep}. Customer ID #{keep} được giữ nguyên.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _render_bulk_delete(st, u, get_conn, logger=None):
    st.markdown("#### 3) Xóa nhiều khách hàng")
    st.caption(
        "Chỉ xóa cứng các khách hàng chưa có bất kỳ dữ liệu workflow liên kết. Khách đã có Tác nghiệp/Kế hoạch/Công việc khách hàng được khóa để tránh mất lịch sử."
    )
    with get_conn() as c:
        rows = _customer_rows(c)
    if not rows:
        st.info("Danh mục khách hàng đang trống.")
        return
    by_id = {int(r["id"]): r for r in rows}
    selected = st.multiselect(
        "Chọn nhiều khách hàng cần xóa",
        list(by_id),
        format_func=lambda x: _customer_label(by_id[int(x)]),
        key="cif_bulk_delete_ids",
    )
    if not selected:
        return
    with get_conn() as c:
        deps = dependency_counts(c, selected)

    import pandas as pd
    preview = []
    deletable = []
    for cid in selected:
        links = deps.get(int(cid)) or {}
        count = sum(int(v) for v in links.values())
        if count == 0:
            deletable.append(int(cid))
        preview.append({
            "Customer ID": int(cid),
            "CIF": by_id[int(cid)].get("cif") or "",
            "Tên khách hàng": by_id[int(cid)].get("customer_name") or "",
            "Liên kết workflow": count,
            "Kết quả": "Có thể xóa" if count == 0 else "Bị khóa – phải hợp nhất/giữ lịch sử",
        })
    st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)
    blocked_n = len(selected) - len(deletable)
    if blocked_n:
        st.warning(f"{blocked_n} khách hàng có dữ liệu liên kết sẽ KHÔNG bị xóa.")
    if not deletable:
        return
    confirm = st.checkbox(
        f"Tôi xác nhận xóa {len(deletable)} khách hàng không có dữ liệu liên kết.",
        key="cif_bulk_delete_confirm",
    )
    if st.button(
        "🗑️ Xóa các hàng đủ điều kiện",
        key="cif_bulk_delete_apply",
        type="primary",
        disabled=not confirm,
        use_container_width=True,
    ):
        try:
            with get_conn() as c:
                c.execute("BEGIN IMMEDIATE")
                deleted, blocked = delete_customers_safe(c, int(u["id"]), selected)
                c.commit()
            if logger:
                logger.info(
                    "CUSTOMER_BULK_DELETE_DONE actor=%s deleted=%s blocked=%s",
                    u["id"], len(deleted), len(blocked),
                )
            st.success(
                f"Đã xóa {len(deleted)} khách hàng. {len(blocked)} khách hàng có lịch sử được giữ lại an toàn."
            )
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_admin_customer_tools(st, u, get_conn, logger=None):
    if not bool(u.get("is_admin")):
        return
    from khdn_apps import potential_customer_patch as potential
    potential.ensure_customer_master(get_conn, logger)
    st.divider()
    st.subheader("🧩 Đối chiếu CIF & quản trị dữ liệu khách hàng")
    st.caption(
        "Công cụ an toàn dành cho Admin: nạp CIF không tạo trùng Customer ID, hợp nhất bản ghi trùng và xóa nhiều khách hàng chưa có lịch sử."
    )
    tab1, tab2, tab3 = st.tabs(["Nạp CIF an toàn", "Hợp nhất trùng", "Xóa nhiều hàng"])
    with tab1:
        _render_safe_import(st, u, get_conn, logger)
    with tab2:
        _render_merge(st, u, get_conn, logger)
    with tab3:
        _render_bulk_delete(st, u, get_conn, logger)


def install(app_ns, logger=None):
    if app_ns.get(_FLAG) == VERSION:
        return
    original_admin = app_ns.get("admin_page")
    if original_admin is None:
        return

    def admin_page(u, *args, **kwargs):
        result = original_admin(u, *args, **kwargs)
        st = app_ns["st"]
        if (
            bool(u.get("is_admin"))
            and st.session_state.get("main_page") == "admin"
            and str(st.session_state.get("admin_scope", "system")) == "system"
            and st.session_state.get("admin_view") == "customers"
        ):
            render_admin_customer_tools(
                st, u, app_ns["get_conn"], logger or app_ns.get("LOGGER")
            )
        return result

    app_ns["admin_page"] = admin_page
    app_ns[_FLAG] = VERSION
    if logger or app_ns.get("LOGGER"):
        (logger or app_ns.get("LOGGER")).info(
            "CUSTOMER_CIF_ADMIN_PATCH_INSTALLED version=%s safe_import=1 preserve_customer_id=1 merge=1 bulk_delete=1 linked_history_guard=1",
            VERSION,
        )
