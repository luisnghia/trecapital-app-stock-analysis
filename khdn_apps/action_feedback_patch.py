"""Prominent, dismissible operation results using Streamlit's native toast queue.

The queue survives script reruns and keeps messages isolated per browser session.
Status/guidance success bars remain inline; completed actions also show a popup.
No timers, refresh loops, business writes or additional input components are used.
"""
from __future__ import annotations

from functools import wraps
import re

VERSION = "1.0.0"
SECONDS = 12
TITLE = "Thao tác thành công"
_FLAG = "_KHDN_ACTION_FEEDBACK_VERSION"
_ACTION = re.compile(
    r"^Đã\s+(?:lưu|cập nhật|tạo|thêm|bổ sung|gửi|nộp|duyệt|phê duyệt|chốt|đánh giá|"
    r"kết thúc|đổi|chuyển|hủy|huỷ|xóa|xoá|giao|báo|trả|tiếp nhận|sao chép|"
    r"đồng bộ|hợp nhất|reset|bật|đăng ký|ghi nhớ)\b", re.IGNORECASE)

FEEDBACK_CSS = """<style>
[data-testid="stToastContainer"]{
  position:fixed!important;top:50%!important;left:50%!important;right:auto!important;bottom:auto!important;
  transform:translate(-50%,-50%)!important;width:min(680px,calc(100vw - 32px))!important;
  max-height:calc(100vh - 48px);max-height:calc(100dvh - 48px);
  margin:0!important;z-index:1000020!important;pointer-events:none;
}
[data-testid="stToastContainer"]>ol{width:100%;max-height:inherit;overflow-y:auto;overflow-x:hidden;padding:4px!important}
[data-testid="stToast"]{
  box-sizing:border-box;width:100%!important;max-width:none!important;min-height:120px;
  margin:8px 0!important;padding:24px!important;border:2px solid #087F76!important;
  border-left:8px solid #F4B41A!important;border-radius:18px!important;
  background:#F6FFFC!important;color:#123D35!important;filter:none!important;
  box-shadow:0 18px 64px rgba(0,0,0,.4)!important;pointer-events:auto;
}
[data-testid="stToast"]>div{min-width:0;flex:1}
[data-testid="stToastText"]{
  display:block!important;-webkit-line-clamp:unset!important;-webkit-box-orient:initial!important;
  overflow:visible!important;white-space:normal!important;overflow-wrap:anywhere!important;
}
[data-testid="stToast"] [data-testid="stMarkdownContainer"]{max-width:100%;color:#123D35!important}
[data-testid="stToast"] [data-testid="stMarkdownContainer"] p{
  font-size:20px!important;line-height:1.5!important;color:#123D35!important;overflow-wrap:anywhere;
}
[data-testid="stToast"] [data-testid="stMarkdownContainer"] p:first-child strong{font-size:25px!important}
[data-testid="stToastDynamicIcon"]{font-size:36px!important;min-width:36px!important;width:36px!important;height:36px!important}
[data-testid="stToast"] button[aria-label="Close"]{
  width:44px!important;min-width:44px!important;height:44px!important;margin:0 0 0 12px!important;
  color:#123D35!important;background:#E0F3EB!important;border-radius:10px!important;
}
[data-testid="stToastViewButton"]{display:none!important}
@media(max-width:640px){
  [data-testid="stToastContainer"]{width:calc(100vw - 20px)!important}
  [data-testid="stToast"]{padding:18px 14px!important;min-height:130px}
  [data-testid="stToast"] [data-testid="stMarkdownContainer"] p{font-size:18px!important}
  [data-testid="stToast"] [data-testid="stMarkdownContainer"] p:first-child strong{font-size:22px!important}
  [data-testid="stToast"] button[aria-label="Close"]{margin-left:6px!important}
}
</style>"""


def _completed_action(body):
    text = str(body).lstrip(" \t\r\n*#✅☑️✔")
    return bool(_ACTION.match(text))


def _visible_duration(value):
    if value == "infinite":
        return value
    if value in {"short", "long"}:
        return SECONDS
    if isinstance(value, int) and value > 0:
        return max(SECONDS, value)
    return value  # Keep native validation for unsupported duration values.


def install(app_ns, logger=None):
    st = app_ns["st"]
    # Install once on the Streamlit module. Weekly renderers temporarily proxy
    # st.success; reinstalling during another session's render could wrap that
    # temporary proxy. Its existing capture/restore instead keeps this wrapper.
    if getattr(st, _FLAG, None) != VERSION:
        original_toast = st.toast
        original_success = st.success

        def log(source):
            if logger:
                logger.info("ACTION_FEEDBACK_SHOW source=%s duration=%s centered=1", source, SECONDS)

        @wraps(original_toast)
        def toast(body, *args, **kwargs):
            if _completed_action(body) or kwargs.get("icon") == "✅":
                body = f"**{TITLE}**\n\n{body}"
                kwargs.setdefault("icon", "✅")
                kwargs["duration"] = _visible_duration(kwargs.get("duration", "short"))
                log("toast")
            return original_toast(body, *args, **kwargs)

        @wraps(original_success)
        def success(body, *args, **kwargs):
            if _completed_action(body):
                original_toast(f"**{TITLE}**\n\n{body}", icon=kwargs.get("icon") or "✅", duration=SECONDS)
                log("success")
            return original_success(body, *args, **kwargs)

        st.toast = toast
        st.success = success
        setattr(st, _FLAG, VERSION)
        if logger:
            logger.info("ACTION_FEEDBACK_INSTALLED duration=%s native_queue=1", SECONDS)

    # Emit the style on every page render, after the existing theme CSS. Keep
    # the app's original initialization and configuration order intact.
    if app_ns.get(_FLAG) != VERSION:
        original_css = app_ns["inject_css"]

        @wraps(original_css)
        def inject_css(*args, **kwargs):
            result = original_css(*args, **kwargs)
            st.html(FEEDBACK_CSS)
            return result

        app_ns["inject_css"] = inject_css
        app_ns[_FLAG] = VERSION
