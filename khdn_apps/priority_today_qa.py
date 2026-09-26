from __future__ import annotations

import inspect
from pathlib import Path

import khdn_apps.customer_work as customer_work
import khdn_apps.priority_today_patch as patch
import khdn_apps.weekly_plan as weekly_plan


def main():
    src = Path(patch.__file__).read_text(encoding="utf-8")
    assert 'st.tabs(["Đang xử lý", "Tạo công việc mới"])' in src
    assert '"🔥 Góc phần tư ưu tiên"' in src
    assert 'for q in range(1, 5)' in src
    assert '0 if x.get("is_overdue") else 1' in src
    assert '0 if x.get("is_stage_delayed") else 1' in src
    assert '("work_today", "Công việc hôm nay")' in src
    assert '_HEAT = {' in src and '#D92D20' in src and '#F79009' in src and '#FEC84B' in src and '#12B76A' in src

    # Both planning layers must read the one System administration customer master.
    cw_src = inspect.getsource(customer_work.customers)
    wp_src = inspect.getsource(weekly_plan.customers)
    for fn_src in (cw_src, wp_src):
        assert "FROM customers WHERE active=1" in fn_src
        assert "ORDER BY CASE WHEN qlkh_user_id=? THEN 0 ELSE 1 END,customer_name" in fn_src

    # No second customer-master table is introduced by the Today patch.
    assert "CREATE TABLE" not in src
    print("PRIORITY_TODAY_QA_PASS")


if __name__ == "__main__":
    main()
