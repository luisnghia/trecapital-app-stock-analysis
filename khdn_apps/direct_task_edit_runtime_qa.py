"""Runtime semantic QA for V2.31.5 direct inline task edit.

Simulates the actual button click in one Streamlit script run and proves that the
exact selected task editor renders immediately without leader/admin navigation.
"""
from types import SimpleNamespace

import khdn_apps.direct_task_edit_button_patch as patch


class _Ctx:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


class FakeSt:
    def __init__(self):
        self.session_state = {
            "user": {"id": 7, "role": "Lãnh đạo phòng", "is_admin": True},
            "leader_view": "active",
        }
        self.open_clicks = 1
        self.rerun_called = False

    def markdown(self, *args, **kwargs):
        return None
    def caption(self, *args, **kwargs):
        return None
    def divider(self):
        return None
    def columns(self, spec, **kwargs):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(n)]
    def button(self, label, **kwargs):
        key = kwargs.get("key", "")
        if key.startswith("direct_full_edit_task_") and self.open_clicks:
            self.open_clicks -= 1
            return True
        return False
    def rerun(self):
        self.rerun_called = True
        raise AssertionError("Open action must not rerun before rendering inline editor")


st = FakeSt()
history_calls = []
editor_calls = []


def original_history(task_id):
    history_calls.append(int(task_id))
    return "history-ok"


def render_task_form(ns, user, task_id):
    editor_calls.append((int(user["id"]), int(task_id), user["role"]))


ns = {"st": st, "task_history": original_history, "APP_VERSION": "old"}
full_edit_module = SimpleNamespace(_render_task_form=render_task_form)
patch.install(ns, full_edit_module)

result = ns["task_history"](123)

checks = {
    "history_preserved": result == "history-ok" and history_calls == [123],
    "clicked_task_targeted": st.session_state.get("direct_inline_full_edit_task_id") == 123,
    "editor_rendered_same_run": editor_calls == [(7, 123, "Lãnh đạo phòng")],
    "no_open_rerun": not st.rerun_called,
    "leader_view_unchanged": st.session_state.get("leader_view") == "active",
    "admin_view_not_created": "admin_view" not in st.session_state,
    "version_updated": ns.get("APP_VERSION") == "2.31.5",
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit(f"KHDN_DIRECT_TASK_EDIT_RUNTIME_QA FAIL {failed} {checks}")
print("KHDN_DIRECT_TASK_EDIT_RUNTIME_QA PASS", checks)
