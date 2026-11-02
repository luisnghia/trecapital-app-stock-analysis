"""Regression for one-shot feedback across all KHDN roles and inbox dismissal.

Uses AppTest with fake authenticated profiles. Does not access production
SQLite, alter notification history or require external services.
"""
from __future__ import annotations

from streamlit.testing.v1 import AppTest

from khdn_apps import action_feedback_patch as feedback

SCRIPT = """
import streamlit as st
from khdn_apps import app
from khdn_apps.action_feedback_patch import run_with_feedback, silence_feedback
from khdn_apps.notification_ui_patch import _close_center

st.session_state.setdefault("user", {"id": 22, "role": "Cán bộ QLKH"})
def render():
    app.inject_css()
    # Emulates persistent approved-state guidance on a dashboard. This must
    # never create a popup during navigation or repeated six-second reruns.
    st.success("Đã phê duyệt kế hoạch tuần.")
    if st.button("Duyệt công việc", key="qa_commit_case"):
        st.toast("Đã phê duyệt công việc khách hàng.", icon="✅")
        st.rerun()
    if st.button("Duyệt kế hoạch", key="qa_commit_week"):
        st.toast("Đã phê duyệt kế hoạch tuần.", icon="✅")
        st.rerun()
    if st.button("Hai kết quả trong một lượt", key="qa_two_results"):
        st.toast("Đã gửi kết quả A.", icon="✅")
        st.toast("Đã gửi kết quả B.", icon="✅")
        st.rerun()
    if st.button("Đổi nội dung kết quả", key="qa_handle_update"):
        handle=st.toast("Đã lưu bản nháp cũ.", icon="✅")
        handle.toast("Đã lưu thay đổi cuối cùng.", icon="✅")
        st.rerun()
    if st.button("Mở Trung tâm thông báo", key="qa_open_inbox"):
        silence_feedback(st)
        st.session_state["_khdn_notification_dialog_open"] = True
        st.rerun()
    if st.session_state.get("_khdn_notification_dialog_open"):
        st.info("🔔 Trung tâm thông báo")
        if st.button("Đóng Trung tâm thông báo", key="qa_close_inbox"):
            _close_center(st)
            st.rerun()
    if st.button("Lưu rồi mở Trung tâm", key="qa_commit_open"):
        st.toast("Đã phê duyệt công việc khách hàng.", icon="✅")
        silence_feedback(st)
        st.session_state["_khdn_notification_dialog_open"] = True
        st.rerun()
run_with_feedback(st, render)
"""


def _assert_toast(page, value):
    assert not page.exception, [e.message for e in page.exception]
    toasts = page.get("toast")
    assert len(toasts) == 1, [x.proto.body for x in toasts]
    assert toasts[0].proto.body.endswith(value), toasts[0].proto.body
    assert toasts[0].proto.duration == feedback.SECONDS
    html = [x.proto.body for x in page.get("html")]
    assert any("data-khdn-toast-one-shot" in x and "display:block" in x for x in html)
    assert any("ol>:not(:last-child)" in x for x in html)


def _assert_quiet(page):
    assert not page.exception, [e.message for e in page.exception]
    assert not page.get("toast"), [x.proto.body for x in page.get("toast")]
    styles = [x.proto.body for x in page.get("html")]
    assert any("data-khdn-toast-one-shot" in x and "display:none" in x for x in styles), styles


def qa_all_roles():
    for role in ("Cán bộ hỗ trợ", "Cán bộ QLKH", "Lãnh đạo phòng", "Admin", "Vấn tin"):
        page = AppTest.from_string(SCRIPT, default_timeout=35).run()
        page.session_state["user"] = {"id": 22, "role": role}
        page.run()
        _assert_quiet(page)
        # Two back-to-back completed operations: only their latest event may
        # be delivered, old browser entries are hidden by CSS and the queue is
        # cleared on every page rerun.
        page.button(key="qa_commit_case").click().run()
        _assert_toast(page, "Đã phê duyệt công việc khách hàng.")
        page.button(key="qa_commit_week").click().run()
        _assert_toast(page, "Đã phê duyệt kế hoạch tuần.")
        page.button(key="qa_two_results").click().run()
        _assert_toast(page, "Đã gửi kết quả B.")
        page.button(key="qa_handle_update").click().run()
        _assert_toast(page, "Đã lưu thay đổi cuối cùng.")

        # The notification center must not reveal any old toast behind or after
        # closing the panel, including X/Escape/backdrop (same _close_center).
        page.button(key="qa_open_inbox").click().run()
        _assert_quiet(page)
        assert page.session_state["_khdn_notification_dialog_open"] is True
        assert page.session_state.get(feedback._PENDING) in (None, [])
        page.button(key="qa_close_inbox").click().run()
        _assert_quiet(page)
        assert page.session_state["_khdn_notification_dialog_open"] is False
        page.run()
        _assert_quiet(page)

        # Fresh action after closing the inbox still gets exactly one toast.
        page.button(key="qa_commit_case").click().run()
        _assert_toast(page, "Đã phê duyệt công việc khách hàng.")
        page.button(key="qa_commit_open").click().run()
        _assert_quiet(page)
        assert page.session_state["_khdn_notification_dialog_open"] is True
        page.button(key="qa_close_inbox").click().run()
        _assert_quiet(page)
        assert page.session_state[feedback._CLOSED_THROUGH] >= 1
        page.run()
        _assert_quiet(page)


def qa_pending_expiry_scope_and_nonresurrection():
    class FakeState(dict): pass
    class FakeSt:
        def __init__(self):
            self.session_state = FakeState(user={"id": 12})
    st = FakeSt()
    st.session_state[feedback._SEQUENCE] = 12
    st.session_state[feedback._PENDING] = [
        {"id": 8, "body": "older", "args": (), "kwargs": {}, "user_id": 12},
        {"id": 9, "body": "latest", "args": (), "kwargs": {}, "user_id": 12},
    ]
    item = feedback._latest_pending(st)
    assert item["body"] == "latest"
    assert feedback._PENDING not in st.session_state
    st.session_state[feedback._PENDING] = [dict(item, id=12, user_id=13)]
    assert feedback._latest_pending(st) is None, "Cross-user result leaked"
    st.session_state[feedback._PENDING] = [dict(item, id=12)]
    feedback.silence_feedback(st)
    assert feedback._latest_pending(st) is None, "Already dismissed result returned"
    assert st.session_state[feedback._CLOSED_THROUGH] == 12
    st.session_state[feedback._PENDING] = [
        dict(item, id=13, created_at=feedback.time.monotonic()-feedback.PENDING_MAX_AGE-1)
    ]
    assert feedback._latest_pending(st) is None, "Expired popup resurfaced"
    st.session_state[feedback._PENDING] = [
        dict(item, id=14, created_at=feedback.time.monotonic())
    ]
    assert feedback._latest_pending(st)["id"] == 14


if __name__ == "__main__":
    qa_pending_expiry_scope_and_nonresurrection()
    qa_all_roles()
    print("ACTION_FEEDBACK_ONE_SHOT_QA_PASS five_roles successive_actions latest_only saved_handle native_stack_suppression dialog_open_close native_dismiss user_isolation TTL no_stale_success")
