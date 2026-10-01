"""Open the installed production entrypoint using an isolated temporary database."""
import os
from pathlib import Path
import tempfile


def run():
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="khdn-page-qa-") as folder:
        os.environ["KHDN_DATA_DIR"] = folder
        os.environ["KHDN_DB_PATH"] = str(Path(folder) / "qa.db")
        os.environ["KHDN_REQUIRE_VOLUME"] = "0"
        import secrets
        os.environ["KHDN_ADMIN_PASSWORD"] = secrets.token_urlsafe(24)
        from streamlit.testing.v1 import AppTest
        page = AppTest.from_file(str(root / "online_entry.py"), default_timeout=30).run()
        assert not page.exception, [e.message for e in page.exception]
        page.run()
        assert not page.exception, [e.message for e in page.exception]

        # Regression guard: the final runtime must own Catalog after reruns.
        # The final zero-keystroke layer deliberately rebinds the catalog after
        # older rerun hotfixes. The command-nav restore patch now owns that final
        # renderer so the old cream/teal+gold buttons are preserved without
        # reintroducing native text widgets.
        from khdn_apps import customer_work_ui as customer_work_ui
        catalog_renderer = customer_work_ui.render_catalog_page
        allowed = {
            "khdn_apps.planning_usability_v3_hotfix",
            "khdn_apps.weekly_priority_policy_patch",
            "khdn_apps.mobile_legacy_ui_perf_patch",
            "khdn_apps.catalog_command_nav_restore_patch",
        }
        assert catalog_renderer.__module__ in allowed, (
            "Catalog renderer fell back after rerun",
            catalog_renderer.__module__,
            getattr(catalog_renderer, "__qualname__", ""),
        )
        # On the current release, the final renderer must be the submit-only
        # command-navigation restore layer, not st.tabs or a native Streamlit form.
        assert catalog_renderer.__module__ == "khdn_apps.catalog_command_nav_restore_patch", (
            "Final catalog renderer is not restored command-nav zero-keystroke",
            catalog_renderer.__module__,
            getattr(catalog_renderer, "__qualname__", ""),
        )
        print(
            "KHDN_CATALOG_RERUN_NAV_QA PASS",
            catalog_renderer.__module__,
            getattr(catalog_renderer, "__qualname__", ""),
        )

        # Render the actual generated settings section, then submit its form.
        import ast
        import textwrap
        catalog = ast.parse((root / "catalog_input_fast_patch.py").read_text(encoding="utf-8"))
        block = next(n.value.value for n in ast.walk(catalog)
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "task_type_block" for t in n.targets))
        settings = textwrap.dedent(block.split('if admin_view == "types":', 1)[1].split("# Exact V2.14", 1)[0])
        script = (
            "import khdn_apps.app as m\n"
            "m.init_db()\n"
            "u = dict(m.qdf('SELECT * FROM users ORDER BY id LIMIT 1').iloc[0])\n"
            "exec(" + repr(settings) + ", dict(vars(m), u=u))\n"
        )
        calendar = AppTest.from_string(script, default_timeout=30).run()
        assert not calendar.exception, [e.message for e in calendar.exception]
        assert any(x.label == "Giờ kết thúc ngày làm việc" for x in calendar.time_input)
        assert any(x.label == "Giờ bắt đầu ngày làm việc" for x in calendar.time_input)
        for item in calendar.checkbox:
            if item.label == "Loại trừ thời gian nghỉ ngoài giờ làm việc":
                item.set_value(True)
        next(x for x in calendar.button if x.label == "Lưu giờ làm việc").click()
        calendar.run()
        assert not calendar.exception, [e.message for e in calendar.exception]
        import sqlite3
        with sqlite3.connect(os.environ["KHDN_DB_PATH"]) as c:
            settings_saved = dict(c.execute("SELECT key,value FROM system_settings").fetchall())
        assert settings_saved["workday_enabled"] == "1"
        assert settings_saved["workday_start"] == "07:30"
        assert settings_saved["workday_end"] == "17:30"
        assert settings_saved["lunch_break_start"] == "11:30"
        assert settings_saved["lunch_break_end"] == "13:30"
        print("KHDN_CALENDAR_SETTINGS_UI_QA PASS render save persistence")

        print("KHDN_RUNTIME_PAGE_QA PASS initial_open rerun isolated_database")


if __name__ == "__main__":
    run()
