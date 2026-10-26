"""Streamlit UI bridge. The persistent bearer token never enters JavaScript.

Normal interactions use a fresh indexed identity check. Typing remains in the
browser and does not trigger server reruns. Cookie UI renders only when changed.
"""
from pathlib import Path
import secrets
import sqlite3
import time
import streamlit as st
import streamlit.components.v1 as components
from . import device_sessions as sessions

_component = components.declare_component('khdn_device_cookie',
    path=str(Path(__file__).with_name('device_component')))


def begin_session(user):
    st.session_state['_auth_password_stamp'] = sessions.digest(user['password_hash'])
    st.session_state['_auth_session_expires'] = time.time() + sessions.TTL


def password_changed(path, user):
    remembered = bool(st.session_state.get('_auth_remember_device') or st.session_state.get('_device_token'))
    sessions.revoke_user(path, int(user['id']))
    st.session_state.pop('_device_token', None)
    begin_session(user)
    if remembered:
        remember(path, user)
    else:
        forget(path)


def _end_session(path):
    forget(path)
    for key in list(st.session_state):
        if str(key) != '_device_command':
            st.session_state.pop(key, None)


def _fresh_session_user(path):
    current = st.session_state.get('user')
    if not current:
        return True
    stamp = st.session_state.get('_auth_password_stamp') or sessions.digest(current.get('password_hash', ''))
    expires = st.session_state.get('_auth_session_expires') or time.time() + sessions.TTL
    with sqlite3.connect(str(path), timeout=15) as c:
        c.row_factory = sqlite3.Row
        row = c.execute('SELECT * FROM users WHERE id=?', (int(current['id']),)).fetchone()
    fresh = dict(row) if row else {}
    valid = bool(fresh.get('active') and not fresh.get('deleted_at') and
                 sessions.digest(fresh.get('password_hash', '')) == stamp and time.time() < expires)
    token = st.session_state.get('_device_token')
    if valid and token:
        valid = bool(sessions.resolve(path, token))
    if not valid:
        _end_session(path)
        return False
    st.session_state['user'] = fresh
    st.session_state['_auth_password_stamp'] = stamp
    st.session_state['_auth_session_expires'] = expires
    return True


def remember(path, user):
    if user.get('must_change_password'):
        st.info('Hãy đổi mật khẩu bắt buộc trước, sau đó đăng nhập lại và bật ghi nhớ.')
        return
    st.session_state['_auth_remember_device'] = True
    st.session_state['_device_command'] = {
        'id': secrets.token_hex(12), 'action': 'set', 'grant': sessions.issue(path, user)}


def forget(path, user_id=None):
    # Revoke only this browser's token. Other devices remain signed in; account
    # disablement/password changes invalidate every token through ``resolve``.
    sessions.revoke(path, st.session_state.get('_device_token'))
    st.session_state.pop('_device_token', None)
    st.session_state.pop('_device_last_validated_mono', None)
    st.session_state.pop('_auth_remember_device', None)
    st.session_state['_device_command'] = {'id': secrets.token_hex(12), 'action': 'clear'}



def sync(path):
    # An indexed identity lookup per explicit interaction; typing stays local.
    # Validate even when the WebSocket lacks the newly issued browser cookie.
    if not _fresh_session_user(path):
        return
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
            st.session_state['_auth_remember_device'] = True
            st.session_state['_device_last_validated_mono'] = time.monotonic()
            begin_session(user)
            st.session_state['_auth_session_expires'] = user['expires']
