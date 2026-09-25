from __future__ import annotations

from pathlib import Path
from khdn_apps import customer_work_patch as nav


def main():
    support = nav._ops_options("Cán bộ hỗ trợ", False)
    qlkh = nav._ops_options("Cán bộ QLKH", False)
    leader = nav._ops_options("Lãnh đạo phòng", False)
    admin_ops = nav._ops_options("Admin", True)
    cb_plan = nav._plan_options("Cán bộ QLKH", False)
    support_plan = nav._plan_options("Cán bộ hỗ trợ", False)
    leader_plan = nav._plan_options("Lãnh đạo phòng", False)
    admin_plan = nav._plan_options("Admin", True)

    assert [x[0] for x in support] == ["support", "dashboard"]
    assert [x[0] for x in qlkh] == ["qlkh", "dashboard"]
    assert [x[0] for x in leader] == ["leader", "dashboard"]
    assert [x[0] for x in admin_ops] == ["leader", "dashboard"]
    assert [x[0] for x in cb_plan] == ["work_today", "customer_work", "weekly_plan"]
    assert [x[0] for x in support_plan] == ["work_today", "customer_work", "weekly_plan"]
    assert [x[0] for x in leader_plan] == ["work_dashboard", "work_approvals", "customer_work", "weekly_plan", "work_catalogs"]
    assert [x[0] for x in admin_plan] == ["work_dashboard", "work_approvals", "customer_work", "weekly_plan", "work_catalogs"]
    assert nav._landing_for("Cán bộ QLKH", False) == "work_today"
    assert nav._landing_for("Cán bộ hỗ trợ", False) == "work_today"
    assert nav._landing_for("Lãnh đạo phòng", False) == "work_dashboard"
    assert nav._landing_for("Admin", True) == "work_dashboard"

    src = Path(nav.__file__).read_text(encoding="utf-8")
    assert '"🧾  TÁC NGHIỆP"' in src
    assert '"📅  KẾ HOẠCH"' in src
    assert 'with st.sidebar.expander("⋯  Tiện ích"' in src
    assert 'st.sidebar.selectbox(' not in src
    assert 'def _render_command_tabs(' in src
    assert 'st.columns(widths,gap="small")' in src
    assert 'khdn_subnav_bar' in src
    assert 'stBaseButton-primary' in src
    assert 'stBaseButton-secondary' in src
    assert 'nav=two-sections-top-tabs' in src
    print("TWO_SECTION_NAV_QA_PASS")


if __name__ == "__main__":
    main()
