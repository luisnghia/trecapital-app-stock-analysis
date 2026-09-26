from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from khdn_apps import planning_usability_v2_patch as p
from khdn_apps import potential_customer_patch as prospects


def run():
    src = Path(__file__).with_name("planning_usability_v2_patch.py").read_text(encoding="utf-8")
    ast.parse(src)
    entry = Path(__file__).with_name("online_entry.py").read_text(encoding="utf-8")

    required = {
        "system_type_admin": '("types", "🧩 Loại công việc")' in src and "system_admin_view_v2" in src,
        "ops_type_removed": 'allowed = {"reasons", "audit", "backup"}' in src,
        "blank_customer": 'placeholder="— Chọn khách hàng —"' in src and 'index=preferred_index' in src,
        "blank_type": 'placeholder="— Chọn loại công việc —"' in src and 'index=None' in src,
        "blank_role": 'placeholder="— Chọn chức vụ —"' in src,
        "blank_stage": 'placeholder="— Chọn mục công việc —"' in src,
        "priority_required": '"Ưu tiên góc phần tư *"' in src and 'priority_quadrant' in src,
        "leader_priority_edit": 'Mức ưu tiên khi duyệt' in src and 'ap_case_priority_v2_' in src,
        "processing_default": 'st.session_state["cw_view"] = "processing"' in src,
        "button_subnav_customer": 'subnav_customer_work_v2' in src,
        "button_subnav_catalog": 'subnav_catalog_v2' in src,
        "button_subnav_weekly": 'subnav_weekly_v2' in src,
        "yellow_detail": '#F4B41A' in src and '🔎 Chi tiết' in src and '[5.5, 1.5, 3.0]' in src,
        "prospect_highlight": 'prospect_quick_' in src and 'KHÁCH HÀNG MỚI / CHƯA CÓ CIF' in src,
        "phone_dedupe": 'trùng SĐT' in src and '_phone_key' in src,
        "name_containment": 'tên chứa cùng cụm từ chính' in src,
        "hard_duplicate_block": 'Hệ thống không cho tạo bản ghi mới' in src,
        "installed_last": '_install_planning_usability_v2(' in entry,
    }
    assert all(required.values()), required

    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE customers(
        id INTEGER PRIMARY KEY, cif TEXT, customer_name TEXT, qlkh_user_id INTEGER,
        active INTEGER, customer_status TEXT, tax_id TEXT, contact_name TEXT, contact_phone TEXT
    )""")
    c.execute("INSERT INTO customers VALUES(1,'001','Công ty Quang Đại Việt',NULL,1,'ACTIVE_CIF','0400123456','Lan','0905123456')")
    c.execute("INSERT INTO customers VALUES(2,'002','Công ty Minh Phát',NULL,1,'ACTIVE_CIF','0400999999','Hà','0905999999')")

    a = p._enhanced_find_similar(prospects, c, "Đại Việt", None, None, None, 8)
    assert a and int(a[0]["id"]) == 1 and "cụm từ chính" in a[0]["match_reason"], a
    b = p._enhanced_find_similar(prospects, c, "Khách hàng hoàn toàn khác", None, None, "0905 123 456", 8)
    assert b and int(b[0]["id"]) == 1 and b[0]["hard_duplicate"], b
    d = p._enhanced_find_similar(prospects, c, "Tên khác", "0400123456", None, None, 8)
    assert d and int(d[0]["id"]) == 1 and d[0]["hard_duplicate"], d
    c.close()

    print("PLANNING_USABILITY_V2_QA_PASS", required)


if __name__ == "__main__":
    run()
