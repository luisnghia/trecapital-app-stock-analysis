from __future__ import annotations

from pathlib import Path
from khdn_apps import customer_work_patch as nav


def main():
    support = nav._ops_options("Cán bộ hỗ trợ")
    qlkh = nav._ops_options("Cán bộ QLKH")
    leader = nav._ops_options("Lãnh đạo phòng")
    cb_plan = nav._plan_options("Cán bộ QLKH", False)
    support_plan = nav._plan_options("Cán bộ hỗ trợ", False)
    leader_plan = nav._plan_options("Lãnh đạo phòng", False)
    admin_plan = nav._plan_options("Lãnh đạo phòng", True)

    assert [x[0] for x in support] == ["support", "dashboard"]
    assert [x[0] for x in qlkh] == ["qlkh", "dashboard"]
    assert [x[0] for x in leader] == ["leader", "dashboard"]
    assert [x[0] for x in cb_plan] == ["work_today", "customer_work", "weekly_plan"]
    assert [x[0] for x in support_plan] == ["work_today", "customer_work", "weekly_plan"]
    assert [x[0] for x in leader_plan] == ["work_dashboard", "work_approvals", "customer_work", "weekly_plan", "work_catalogs"]
    assert admin_plan == leader_plan
    assert nav._landing_for("Cán bộ QLKH", False) == "work_today"
    assert nav._landing_for("Cán bộ hỗ trợ", False) == "work_today"
    assert nav._landing_for("Lãnh đạo phòng", False) == "work_dashboard"
    assert nav._landing_for("Lãnh đạo phòng", True) == "work_dashboard"

    src = Path(nav.__file__).read_text(encoding="utf-8")
    assert '"🧾  TÁC NGHIỆP"' in src
    assert '"📅  KẾ HOẠCH"' in src
    assert 'with st.sidebar.expander("⋯  Tiện ích"' in src
    assert 'st.sidebar.selectbox(' in src
    assert 'nav=two-sections' in src
    print("TWO_SECTION_NAV_QA_PASS")


if __name__ == "__main__":
    main()
