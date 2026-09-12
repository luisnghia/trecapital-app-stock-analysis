"""Streamlit 1.63 ASGI launcher with same-origin HttpOnly cookie exchange."""
import asyncio
import os
from urllib.parse import urlsplit
from starlette.requests import Request
from starlette.responses import JSONResponse
import streamlit.web.server.starlette as streamlit_starlette
from streamlit.web.server.starlette import starlette_server
from streamlit.web.cli import main
from .device_sessions import COOKIE, TTL, redeem, revoke


class DeviceMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'] != '/_khdn/device-session':
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        origin = urlsplit(request.headers.get('origin', ''))
        if (request.method != 'POST' or origin.scheme != 'https'
                or origin.netloc != request.headers.get('host')):
            return await JSONResponse({'ok': False}, status_code=403)(scope, receive, send)
        raw = await request.body()
        if len(raw) > 2048:
            return await JSONResponse({'ok': False}, status_code=413)(scope, receive, send)
        try:
            body = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return await JSONResponse({'ok': False}, status_code=400)(scope, receive, send)
        action = body.get('action')
        if action not in {'set', 'clear'}:
            return await JSONResponse({'ok': False}, status_code=400)(scope, receive, send)
        path = os.environ['KHDN_DB_PATH']
        response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
        if action == 'clear':
            await asyncio.to_thread(revoke, path, request.cookies.get(COOKIE))
            response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='strict')
        else:
            token = await asyncio.to_thread(redeem, path, body.get('grant'))
            if token is None:
                return await JSONResponse({'ok': False}, status_code=401)(scope, receive, send)
            await asyncio.to_thread(revoke, path, request.cookies.get(COOKIE))
            response.set_cookie(COOKIE, token, max_age=TTL, path='/', secure=True,
                                httponly=True, samesite='strict')
        await response(scope, receive, send)


# ``UvicornServer`` keeps its own imported reference in ``starlette_server``;
# the package also re-exports the function. Patch both symbols so the middleware
# is installed on the real Streamlit app across Streamlit's ASGI entry paths.
_create_app = streamlit_starlette.create_starlette_app


def create_app(runtime):
    return DeviceMiddleware(_create_app(runtime))


streamlit_starlette.create_starlette_app = create_app
starlette_server.create_starlette_app = create_app

if __name__ == '__main__':
    main()
