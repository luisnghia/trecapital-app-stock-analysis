"""Make device-login persistence automatic after a successful sign-in.

The legacy login form already supports a 30-day device cookie through
``device_login.remember`` but exposes it behind an opt-in checkbox.  This patch
keeps the tested login flow and cookie implementation, while making the checkbox
implicitly true and replacing its old opt-in guidance with explicit automatic
persistence guidance.  Logout continues to revoke this browser's token.
"""
from __future__ import annotations

VERSION = "1.0.0"
_REMEMBER_LABEL = "Ghi nhớ đăng nhập trên thiết bị này trong 30 ngày"
_OLD_CAPTION = "Chỉ bật trên điện thoại cá nhân có khóa màn hình. Không bật trên thiết bị dùng chung."
_NEW_CAPTION = "Đăng nhập sẽ được tự động ghi nhớ trên thiết bị này trong 30 ngày. Bấm Đăng xuất để thu hồi phiên ghi nhớ trên thiết bị này."


def install(ns):
    if ns.get("_AUTO_REMEMBER_LOGIN_INSTALLED"):
        return
    st = ns["st"]
    original_login = ns["login_ui"]

    def login_ui():
        original_checkbox = st.checkbox
        original_caption = st.caption

        def checkbox(label, *args, **kwargs):
            if str(label) == _REMEMBER_LABEL:
                # Do not render an unnecessary option: successful login always
                # follows the existing remember-device path.
                return True
            return original_checkbox(label, *args, **kwargs)

        def caption(body, *args, **kwargs):
            if str(body) == _OLD_CAPTION:
                body = _NEW_CAPTION
            return original_caption(body, *args, **kwargs)

        st.checkbox = checkbox
        st.caption = caption
        try:
            return original_login()
        finally:
            st.checkbox = original_checkbox
            st.caption = original_caption

    ns["login_ui"] = login_ui
    ns["_AUTO_REMEMBER_LOGIN_INSTALLED"] = True
    logger = ns.get("LOGGER")
    if logger:
        logger.info("AUTO_REMEMBER_LOGIN_INSTALLED version=%s", VERSION)
