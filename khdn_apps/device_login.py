"""Streamlit UI bridge. The persistent bearer token never enters JavaScript.

Performance note: normal authenticated reruns do not render the custom component and
do not re-query SQLite. The token is revalidated periodically instead.
"""
from pathlib import Path
import secrets
import time
import streamlit as st
import streamlit.components.v1 as components
from . import device_sessions as sessions

_component = components.declare_component('khdn_device_cookie',
    path=str(Path(__file__).with_name('device_component')))

# A disabled account/password change is still picked up quickly, while bursts of
# typing/button interaction stay entirely client/session-local.
VALIDATE_SECONDS = 30.0


def remember(path, user):
    if user.get('must_change_password'):
        st.info('Hãy đổi mật khẩu bắt buộc trước, sau đó đăng nhập lại và bật ghi nhớ.')
        return
    st.session_state['_device_command'] = {
        'id': secrets.token_hex(12), 'action': 'set', 'grant': sessions.issue(path, user)}


def forget(path, user_id=None):
    # Revoke only this browser's token. Other devices remain signed in; account
    # disablement/password changes invalidate every token through ``resolve``.
    sessions.revoke(path, st.session_state.get('_device_token'))
    st.session_state.pop('_device_token', None)
    st.session_state.pop('_device_last_validated_mono', None)
    st.session_state['_device_command'] = {'id': secrets.token_hex(12), 'action': 'clear'}


def _validate_token_if_due(path):
    token = st.session_state.get('_device_token')
    if not token:
        return
    now = time.monotonic()
    last = float(st.session_state.get('_device_last_validated_mono', 0.0) or 0.0)
    if (now - last) < VALIDATE_SECONDS:
        return
    user = sessions.resolve(path, token)
    if not user:
        st.session_state.pop('user', None)
        st.session_state.pop('_device_token', None)
        st.session_state.pop('_device_last_validated_mono', None)
        return
    st.session_state['_device_last_validated_mono'] = now


def sync(path):
    command = st.session_state.get('_device_command')

    # The component is only needed when browser cookie state must actually change.
    # Rendering an iframe/component on every Streamlit rerun was unnecessary work,
    # especially noticeable on mobile while entering text.
    if command:
        result = _component(command=command, key='khdn_device_cookie', default=None)
        if isinstance(result, dict) and result.get('id') == command['id']:
            st.session_state.pop('_device_command', None)
            if not result.get('ok'):
                st.warning('Không thể ghi nhớ đăng nhập. Bạn vẫn có thể dùng phiên hiện tại; lần sau cần đăng nhập lại.')
            elif command['action'] == 'set':
                st.toast('Đã ghi nhớ đăng nhập trên thiết bị này trong 30 ngày.')
        return

    # st.context.cookies is available without rendering the custom component.
    token = st.context.cookies.get(sessions.COOKIE)
    if 'user' not in st.session_state and token:
        user = sessions.resolve(path, token)
        if user:
            st.session_state.user = user
            st.session_state['_device_token'] = token
            st.session_state['_device_last_validated_mono'] = time.monotonic()

    _validate_token_if_due(path)
