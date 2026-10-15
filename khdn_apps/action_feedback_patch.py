"""Prominent, dismissible operation results using Streamlit's native toast queue.

Results are held per session across reruns and emitted after the page is rendered.
This avoids style-only st.html elements overwriting a toast's event-container slot.
Status/guidance success bars remain inline; completed actions also show a popup.
No timers, refresh loops, business writes or additional input components are used.
"""
from __future__ import annotations

from functools import wraps
from contextvars import ContextVar
import re

VERSION = "1.1.0"
SECONDS = 12
TITLE = "Thao tác thành công"
_FLAG = "_KHDN_ACTION_FEEDBACK_VERSION"
_PENDING = "_khdn_action_feedback_pending"
_SEQUENCE = "_khdn_action_feedback_sequence"
_NATIVE = "_KHDN_ACTION_FEEDBACK_NATIVE_TOAST"
_DEFER = ContextVar("khdn_action_feedback_defer", default=False)
_ACTION = re.compile(
    r"^Đã\s+(?:lưu|cập nhật|tạo|thêm|bổ sung|gửi|nộp|duyệt|phê duyệt|chốt|đánh giá|"
    r"kết thúc|đổi|chuyển|hủy|huỷ|xóa|xoá|giao|báo|trả|tiếp nhận|sao chép|"
    r"đồng bộ|hợp nhất|reset|bật|đăng ký|ghi nhớ|xác nhận|từ chối|mở khóa|"
    r"bỏ|ngưng|ngừng|nạp|khôi phục|liên kết)\b", re.IGNORECASE)

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


def _user_id(st):
    user = st.session_state.get("user")
    return user.get("id") if hasattr(user, "get") else None


def run_with_feedback(st, render, *args, **kwargs):
    """Flush results once, after the final render, without requesting a rerun.

    A save followed by st.rerun leaves its message for the next completed render.
    A normal return or st.stop flushes it immediately. ContextVars isolate the
    render scope across Streamlit sessions/threads; session_state holds only data.
    """
    from streamlit.runtime.scriptrunner import RerunException

    if _DEFER.get():
        return render(*args, **kwargs)
    token = _DEFER.set(True)
    rerunning = False
    try:
        return render(*args, **kwargs)
    except RerunException:
        rerunning = True
        raise
    finally:
        _DEFER.reset(token)
        if not rerunning:
            pending = st.session_state.pop(_PENDING, [])
            native = getattr(st, _NATIVE, st.toast)
            current_user = _user_id(st)
            for entry in pending:
                if entry["user_id"] == current_user:
                    native(entry["body"], *entry["args"], **entry["kwargs"])
                    logger = getattr(st, "_KHDN_ACTION_FEEDBACK_LOGGER", None)
                    if logger:
                        logger.info("ACTION_FEEDBACK_SHOW source=deferred duration=%s centered=1", entry["kwargs"].get("duration", "short"))


class _QueuedToast:
    """Preserve the documented handle.toast(...) update while a result is queued."""
    def __init__(self, update, message_id):
        self._update = update
        self._message_id = message_id

    def toast(self, body, *args, **kwargs):
        return self._update(body, args, kwargs, self._message_id)


def install(app_ns, logger=None):
    st = app_ns["st"]
    # Install once on the Streamlit module. Weekly renderers temporarily proxy
    # st.success; reinstalling during another session's render could wrap that
    # temporary proxy. Its existing capture/restore instead keeps this wrapper.
    if getattr(st, _FLAG, None) != VERSION:
        original_toast = st.toast
        original_success = st.success
        setattr(st, _NATIVE, original_toast)
        setattr(st, "_KHDN_ACTION_FEEDBACK_LOGGER", logger)

        def log(source):
            if logger:
                logger.info("ACTION_FEEDBACK_%s source=%s duration=%s centered=1", "QUEUED" if _DEFER.get() else "SHOW", source, SECONDS)

        def deliver(body, args, kwargs, message_id=None):
            if _completed_action(body) or kwargs.get("icon") == "✅":
                body = f"**{TITLE}**\n\n{body}"
                kwargs.setdefault("icon", "✅")
                kwargs["duration"] = _visible_duration(kwargs.get("duration", "short"))
                log("toast")
            if _DEFER.get():
                pending = list(st.session_state.get(_PENDING, []))
                if message_id is None:
                    message_id = int(st.session_state.get(_SEQUENCE, 0)) + 1
                    st.session_state[_SEQUENCE] = message_id
                entry = dict(id=message_id, body=body, args=args, kwargs=kwargs, user_id=_user_id(st))
                previous = next((i for i, item in enumerate(pending) if item["id"] == message_id), None)
                if previous is None:
                    pending.append(entry)
                else:
                    pending[previous] = entry
                st.session_state[_PENDING] = pending
                return _QueuedToast(deliver, message_id)
            return original_toast(body, *args, **kwargs)

        @wraps(original_toast)
        def toast(body, *args, **kwargs):
            return deliver(body, args, kwargs)

        @wraps(original_success)
        def success(body, *args, **kwargs):
            if _completed_action(body):
                deliver(body, (), dict(icon=kwargs.get("icon") or "✅", duration=SECONDS))
            return original_success(body, *args, **kwargs)

        st.toast = toast
        st.success = success
        original_dialog = getattr(st, "dialog", None)
        if callable(original_dialog):
            @wraps(original_dialog)
            def dialog(title, *args, **kwargs):
                decorate = original_dialog(title, *args, **kwargs)

                def wrap(render):
                    @wraps(render)
                    def body(*args, **kwargs):
                        return run_with_feedback(st, render, *args, **kwargs)
                    return decorate(body)

                return wrap

            st.dialog = dialog
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

    # Install last, around the real entrypoint, so every role and nested dialog
    # finishes its HTML/CSS output before the native toast event is emitted.
    app_key = _FLAG + "_APP"
    if callable(app_ns.get("app")) and app_ns.get(app_key) != VERSION:
        original_app = app_ns["app"]

        @wraps(original_app)
        def app(*args, **kwargs):
            return run_with_feedback(st, original_app, *args, **kwargs)

        app_ns["app"] = app
        app_ns[app_key] = VERSION
