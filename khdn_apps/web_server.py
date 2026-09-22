"""Streamlit 1.63 ASGI launcher with same-origin device and Web Push endpoints."""
import asyncio
import html
import json
import os
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
import streamlit.web.server.starlette as streamlit_starlette
from streamlit.web.server.starlette import starlette_server
from streamlit.web.cli import main

from .device_sessions import COOKIE, TTL, redeem, revoke
from . import notifications as notify


SERVICE_WORKER = r"""
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) {
    data = {title: 'KHDN Ops', body: event.data ? event.data.text() : ''};
  }
  const title = data.title || 'KHDN Ops';
  const options = {
    body: data.body || '',
    icon: '/app/static/bidv-icon-192.png?v=push-1',
    badge: '/app/static/bidv-icon-192.png?v=push-1',
    tag: data.tag || 'khdn-notification',
    renotify: true,
    data: {url: data.url || '/'},
  };
  const jobs = [self.registration.showNotification(title, options)];
  if (typeof self.registration.setAppBadge === 'function' && Number.isFinite(Number(data.badgeCount))) {
    jobs.push(self.registration.setAppBadge(Number(data.badgeCount)));
  }
  event.waitUntil(Promise.all(jobs));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const target = new URL((event.notification.data || {}).url || '/', self.location.origin).href;
  event.waitUntil((async () => {
    const windows = await clients.matchAll({type: 'window', includeUncontrolled: true});
    for (const client of windows) {
      try {
        if ('navigate' in client) await client.navigate(target);
        if ('focus' in client) return client.focus();
      } catch (_) {}
    }
    if (clients.openWindow) return clients.openWindow(target);
  })());
});
"""


def _same_origin_post(request: Request) -> bool:
    origin = urlsplit(request.headers.get('origin', ''))
    return request.method == 'POST' and origin.scheme == 'https' and origin.netloc == request.headers.get('host')


def _push_setup_html(ticket: str, public_key: str) -> str:
    ticket_js = json.dumps(ticket)
    key_js = json.dumps(public_key)
    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>KHDN Apps - Push Notification</title>
<link rel="manifest" href="/app/static/manifest.json?v=push-1">
<link rel="apple-touch-icon" href="/app/static/bidv-icon-180.png?v=push-1">
<meta name="theme-color" content="#006B68">
<style>
:root{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark}}
body{{margin:0;background:#0E1F1E;color:#F4FFFC;display:flex;justify-content:center;min-height:100vh}}
.card{{width:min(620px,calc(100% - 28px));margin:24px 14px;padding:22px;border:1px solid rgba(164,232,219,.35);border-radius:18px;background:#17312F;box-shadow:0 14px 38px rgba(0,0,0,.28)}}
h1{{font-size:1.35rem;margin:0 0 8px}}p{{line-height:1.48;color:#D7ECE8}}.hint{{font-size:.92rem;color:#B7D5D0}}
button,a.btn{{display:block;width:100%;box-sizing:border-box;border:0;border-radius:12px;padding:14px 16px;margin:10px 0;font-size:1rem;font-weight:800;text-align:center;text-decoration:none;cursor:pointer}}
.primary{{background:#F4B41A;color:#2B2410}}.secondary{{background:#24504A;color:#fff;border:1px solid rgba(164,232,219,.4)!important}}
.danger{{background:#442327;color:#FFD9DE;border:1px solid #F06A77!important}}#status{{padding:12px;border-radius:10px;background:#122624;margin:14px 0;white-space:pre-wrap}}
</style></head><body><main class="card">
<h1>🔔 Push Notification - KHDN Apps</h1>
<p>Nhận thông báo công việc trên màn hình khóa/Notification Center ngay cả khi KHDN Apps không mở.</p>
<div id="status">Đang kiểm tra thiết bị…</div>
<button id="enable" class="primary">📲 Bật thông báo trên thiết bị này</button>
<button id="disable" class="danger">Tắt thông báo trên thiết bị này</button>
<a class="btn secondary" href="/">← Quay lại KHDN Apps</a>
<p class="hint"><b>iPhone/iPad:</b> Web Push hoạt động khi KHDN Apps đã được <b>Thêm vào Màn hình chính</b> và mở từ icon KHDN. Sau đó bấm nút Bật thông báo ở trang này.</p>
<script>
const ticket={ticket_js}; const vapidKey={key_js};
const statusEl=document.getElementById('status'); const enable=document.getElementById('enable'); const disable=document.getElementById('disable');
function ios(){{return /iphone|ipad|ipod/i.test(navigator.userAgent)}}
function standalone(){{return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone===true}}
function b64ToUint8Array(base64String){{const padding='='.repeat((4-base64String.length%4)%4);const base64=(base64String+padding).replace(/-/g,'+').replace(/_/g,'/');const raw=atob(base64);return Uint8Array.from([...raw].map(c=>c.charCodeAt(0)));}}
async function reg(){{if(!('serviceWorker' in navigator))throw new Error('Trình duyệt không hỗ trợ Service Worker');return navigator.serviceWorker.register('/khdn-sw.js',{{scope:'/'}});}}
async function current(){{const r=await reg();await navigator.serviceWorker.ready;return r.pushManager.getSubscription();}}
async function send(action,sub){{const resp=await fetch('/_khdn/push-subscription',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticket,action,subscription:sub?sub.toJSON():null}})}});if(!resp.ok)throw new Error('Máy chủ từ chối đăng ký ('+resp.status+')');return resp.json();}}
async function refresh(){{
  if(!('Notification' in window)||!('PushManager' in window)||!('serviceWorker' in navigator)){{statusEl.textContent='Thiết bị/trình duyệt này chưa hỗ trợ Web Push.';enable.disabled=true;return;}}
  if(ios()&&!standalone()){{statusEl.textContent='Trên iPhone/iPad: hãy dùng Share → Add to Home Screen / Thêm vào Màn hình chính, mở KHDN Apps từ icon vừa tạo, rồi vào lại mục 🔔 Thông báo để bật Push.';enable.disabled=true;return;}}
  const sub=await current();statusEl.textContent=sub?'✅ Thiết bị này đã đăng ký Push Notification.':'Thông báo hiện: '+Notification.permission+'. Bấm Bật để đăng ký.';
}}
enable.addEventListener('click',async()=>{{try{{enable.disabled=true;statusEl.textContent='Đang xin quyền thông báo…';if(Notification.permission!=='granted'){{const p=await Notification.requestPermission();if(p!=='granted')throw new Error('Bạn chưa cho phép thông báo.')}}const r=await reg();await navigator.serviceWorker.ready;let sub=await r.pushManager.getSubscription();if(!sub)sub=await r.pushManager.subscribe({{userVisibleOnly:true,applicationServerKey:b64ToUint8Array(vapidKey)}});await send('set',sub);statusEl.textContent='✅ Đã bật Push Notification cho thiết bị này.';}}catch(e){{statusEl.textContent='❌ '+(e.message||e);}}finally{{enable.disabled=false;}}}});
disable.addEventListener('click',async()=>{{try{{disable.disabled=true;const sub=await current();if(sub){{await send('clear',sub);await sub.unsubscribe();}}statusEl.textContent='Đã tắt Push Notification trên thiết bị này.';}}catch(e){{statusEl.textContent='❌ '+(e.message||e);}}finally{{disable.disabled=false;}}}});
refresh().catch(e=>{{statusEl.textContent='❌ '+(e.message||e)}});
</script></main></body></html>"""


class KHDNMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope.get('path', '')
        request = Request(scope, receive)

        if path == '/khdn-sw.js':
            response = Response(
                SERVICE_WORKER,
                media_type='application/javascript',
                headers={'Cache-Control': 'no-cache, no-store, must-revalidate', 'Service-Worker-Allowed': '/'},
            )
            return await response(scope, receive, send)

        if path == '/_khdn/push-setup':
            if request.method != 'GET':
                return await JSONResponse({'ok': False}, status_code=405)(scope, receive, send)
            ticket = request.query_params.get('ticket', '')
            uid = notify.verify_setup_ticket(ticket)
            public_key = os.getenv('KHDN_VAPID_PUBLIC_KEY', '').strip()
            if not uid or not public_key:
                return await HTMLResponse(
                    '<h3>Liên kết cài đặt Push không hợp lệ hoặc đã hết hạn.</h3><p>Quay lại KHDN Apps → 🔔 Thông báo và mở lại trang cài đặt.</p>',
                    status_code=401,
                )(scope, receive, send)
            response = HTMLResponse(_push_setup_html(ticket, public_key), headers={'Cache-Control': 'no-store'})
            return await response(scope, receive, send)

        if path == '/_khdn/push-subscription':
            if not _same_origin_post(request):
                return await JSONResponse({'ok': False}, status_code=403)(scope, receive, send)
            raw = await request.body()
            if len(raw) > 16384:
                return await JSONResponse({'ok': False}, status_code=413)(scope, receive, send)
            try:
                body = json.loads(raw.decode('utf-8'))
            except Exception:
                body = None
            if not isinstance(body, dict):
                return await JSONResponse({'ok': False}, status_code=400)(scope, receive, send)
            uid = notify.verify_setup_ticket(body.get('ticket', ''))
            if not uid:
                return await JSONResponse({'ok': False}, status_code=401)(scope, receive, send)
            db_path = os.environ['KHDN_DB_PATH']
            try:
                with notify._connect(db_path) as c:
                    user = c.execute('SELECT id,active,deleted_at FROM users WHERE id=?', (int(uid),)).fetchone()
                if not user or not user['active'] or user['deleted_at']:
                    return await JSONResponse({'ok': False}, status_code=403)(scope, receive, send)
                action = body.get('action')
                sub = body.get('subscription') or {}
                if action == 'set':
                    await asyncio.to_thread(notify.save_subscription, db_path, uid, sub, request.headers.get('user-agent', ''))
                elif action == 'clear':
                    endpoint = str(sub.get('endpoint') or '')
                    await asyncio.to_thread(notify.deactivate_subscription, db_path, uid, endpoint)
                else:
                    return await JSONResponse({'ok': False}, status_code=400)(scope, receive, send)
            except ValueError as exc:
                return await JSONResponse({'ok': False, 'error': str(exc)}, status_code=400)(scope, receive, send)
            except Exception:
                return await JSONResponse({'ok': False}, status_code=500)(scope, receive, send)
            return await JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})(scope, receive, send)

        if path == '/_khdn/device-session':
            if not _same_origin_post(request):
                return await JSONResponse({'ok': False}, status_code=403)(scope, receive, send)
            raw = await request.body()
            if len(raw) > 2048:
                return await JSONResponse({'ok': False}, status_code=413)(scope, receive, send)
            try:
                body = json.loads(raw.decode('utf-8'))
            except Exception:
                body = None
            if not isinstance(body, dict):
                return await JSONResponse({'ok': False}, status_code=400)(scope, receive, send)
            action = body.get('action')
            if action not in {'set', 'clear'}:
                return await JSONResponse({'ok': False}, status_code=400)(scope, receive, send)
            db_path = os.environ['KHDN_DB_PATH']
            response = JSONResponse({'ok': True}, headers={'Cache-Control': 'no-store'})
            if action == 'clear':
                await asyncio.to_thread(revoke, db_path, request.cookies.get(COOKIE))
                response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='strict')
            else:
                token = await asyncio.to_thread(redeem, db_path, body.get('grant'))
                if token is None:
                    return await JSONResponse({'ok': False}, status_code=401)(scope, receive, send)
                await asyncio.to_thread(revoke, db_path, request.cookies.get(COOKIE))
                response.set_cookie(COOKIE, token, max_age=TTL, path='/', secure=True,
                                    httponly=True, samesite='strict')
            return await response(scope, receive, send)

        return await self.app(scope, receive, send)


# ``UvicornServer`` keeps its own imported reference in ``starlette_server``;
# patch both symbols so middleware is installed on the real Streamlit app.
_create_app = streamlit_starlette.create_starlette_app


def create_app(runtime):
    return KHDNMiddleware(_create_app(runtime))


streamlit_starlette.create_starlette_app = create_app
starlette_server.create_starlette_app = create_app

if __name__ == '__main__':
    main()
