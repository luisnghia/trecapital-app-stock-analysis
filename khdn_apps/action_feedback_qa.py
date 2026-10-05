"""Verify action results without turning static guidance into repeated popups."""
from __future__ import annotations


def run_feedback_qa():
    from khdn_apps import action_feedback_patch as feedback

    class UI:
        def __init__(self):
            self.toasts = []
            self.bars = []
            self.styles = []
        def toast(self, body, **kwargs):
            self.toasts.append((body, kwargs))
            return self.toasts[-1]
        def success(self, body, **kwargs):
            self.bars.append((body, kwargs))
            return self.bars[-1]
        def html(self, body):
            self.styles.append(body)

    ui = UI()
    ns = {"st": ui, "inject_css": lambda: "original-theme"}
    feedback.install(ns)
    toast, success, css = ui.toast, ui.success, ns["inject_css"]
    feedback.install(ns)
    assert (ui.toast, ui.success, ns["inject_css"]) == (toast, success, css)
    for _ in range(2):
        assert ns["inject_css"]() == "original-theme"
    assert len(ui.styles) == 2
    for message in [
        "Đã thêm công việc vào kế hoạch.", "Đã lưu sửa công việc.",
        "Đã nộp kế hoạch cho Trưởng phòng.", "Đã gửi kế hoạch chờ phê duyệt.",
        "Đã phê duyệt kế hoạch.", "Đã chốt tuần.",
        "Đã tạo công việc.", "Đã cập nhật tiến độ.",
        "Đã giao hồ sơ cho Cán bộ hỗ trợ.", "Đã tiếp nhận hồ sơ.",
        "Đã báo hoàn thành.", "Đã lưu đánh giá và kết thúc tác nghiệp.",
        "Đã lưu toàn bộ thay đổi và ghi audit.", "Đã cập nhật thông tin liên hệ.",
    ]:
        returned = ui.toast(message, icon="✅")
        assert returned == ui.toasts[-1]
        body, settings = returned
        assert feedback.TITLE in body and body.endswith(message)
        assert settings["duration"] == 12 and settings["icon"] == "✅"
    before = len(ui.toasts)
    for message in [
        "Không có công việc đang chờ đánh giá.",
        "Kế hoạch đã duyệt. Cập nhật tiến độ tại đây.",
        "→ Tự động phân loại: Q2 · Trọng tâm.",
        "Đã tự động nạp 2 thông tin liên hệ đã lưu của khách hàng.",
        "Đã chọn: Khách hàng hiện có.",
    ]:
        assert ui.success(message) == ui.bars[-1]
    assert len(ui.toasts) == before
    message = "Đã lưu đánh giá và kết thúc tác nghiệp."
    assert ui.success(message) == ui.bars[-1]
    assert len(ui.toasts) == before + 1
    assert ui.toasts[-1][0].endswith(message) and ui.toasts[-1][1]["duration"] == 12
    ui.toast("Đã lưu.", duration="infinite")
    assert ui.toasts[-1][1]["duration"] == "infinite"
    ui.toast("Đã lưu.", duration=30)
    assert ui.toasts[-1][1]["duration"] == 30
    ui.toast("Ghi chú không thay đổi.", icon="ℹ️")
    assert ui.toasts[-1] == ("Ghi chú không thay đổi.", {"icon": "ℹ️"})
    print("ACTION_FEEDBACK_QA_PASS create edit submit approve close contact native_queue inline_status_no_popup original_return idempotent theme_each_rerun duration dismissible")


def installed_feedback_ui():
    from streamlit.testing.v1 import AppTest
    from khdn_apps import app
    from khdn_apps import action_feedback_patch as feedback

    assert app.st._KHDN_ACTION_FEEDBACK_VERSION == feedback.VERSION
    script = '''
import streamlit as st
from khdn_apps import app
app.inject_css()
st.success("Kế hoạch đã duyệt. Cập nhật tiến độ tại đây.")
if st.button("QA lưu thay đổi"):
    st.success("Đã lưu thay đổi và ghi lịch sử.")
if st.button("QA gửi duyệt"):
    st.toast("Đã gửi kế hoạch chờ Lãnh đạo phê duyệt.", icon="✅")
'''
    page = AppTest.from_string(script, default_timeout=30).run()
    assert not page.exception, [e.message for e in page.exception]
    assert len(page.get("toast")) == 0
    assert any(feedback.FEEDBACK_CSS == x.proto.body for x in page.get("html"))
    for button, message in [("QA lưu thay đổi", "Đã lưu thay đổi và ghi lịch sử."),
                            ("QA gửi duyệt", "Đã gửi kế hoạch chờ Lãnh đạo phê duyệt.")]:
        next(x for x in page.button if x.label == button).click().run()
        assert not page.exception, [e.message for e in page.exception]
        toasts = page.get("toast")
        assert len(toasts) == 1
        assert toasts[0].proto.body.endswith(message) and feedback.TITLE in toasts[0].proto.body
        assert toasts[0].proto.duration == 12
        page.run()
        assert not page.exception and len(page.get("toast")) == 0
    print("ACTION_FEEDBACK_INSTALLED_UI_QA_PASS native_toast centered_CSS save submit exact_outcome 12_seconds status_not_replayed no_extra_rerun")


if __name__ == "__main__":
    run_feedback_qa()
