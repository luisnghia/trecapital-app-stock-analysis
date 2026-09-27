from __future__ import annotations

from khdn_apps import planning_usability_v3_hotfix as hotfix


def run():
    fake_st = object()
    calls = []
    original = hotfix.ui_hotfix._local_command_tabs

    def fake_local(st, state_key, options, default=None, prefix="subnav"):
        calls.append((st, state_key, list(options), default, prefix))
        return default

    hotfix.ui_hotfix._local_command_tabs = fake_local
    try:
        nav = hotfix._bound_child_nav(fake_st)
        result = nav(
            "cw_catalog_view_v2",
            [("stages", "Mục công việc / SLA"), ("important", "Danh mục công việc quan trọng")],
            default="stages",
            prefix="subnav_catalog_v2",
        )
    finally:
        hotfix.ui_hotfix._local_command_tabs = original

    assert result == "stages"
    assert len(calls) == 1
    st_arg, state_key, options, default, prefix = calls[0]
    assert st_arg is fake_st
    assert state_key == "cw_catalog_view_v2"
    assert options[0][1] == "Mục công việc / SLA"
    assert options[1][1] == "Danh mục công việc quan trọng"
    assert default == "stages"
    assert prefix == "subnav_catalog_v2"
    print("PLANNING_USABILITY_V3_HOTFIX_QA_PASS")


if __name__ == "__main__":
    run()
