"""Allowlisted Push origins, public-IP pinning, verified TLS, no redirects."""
import base64
import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from requests import Response
from requests.structures import CaseInsensitiveDict

HOSTS = {'fcm.googleapis.com', 'android.googleapis.com',
         'updates.push.services.mozilla.com', 'web.push.apple.com'}


def endpoint_parts(endpoint):
    if not isinstance(endpoint, str) or len(endpoint) > 4096 or any(x.isspace() for x in endpoint):
        raise ValueError('Địa chỉ dịch vụ Push không hợp lệ.')
    try:
        url = urlsplit(endpoint)
        host = url.hostname or ''
        approved = host in HOSTS or bool(re.fullmatch(r'wns[0-9]+-[a-z0-9-]+\.notify\.windows\.com', host))
        if (url.scheme != 'https' or not approved or url.username is not None or
                url.password is not None or url.port not in (None,443) or url.fragment or
                not url.path.startswith('/') or '\\' in endpoint or host.endswith('.')):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('Chỉ chấp nhận địa chỉ HTTPS của dịch vụ Push trình duyệt được hỗ trợ.') from None
    return url


def validate_subscription(subscription):
    endpoint = str(subscription.get('endpoint') or '').strip()
    endpoint_parts(endpoint)
    keys = subscription.get('keys')
    if not isinstance(keys, dict):
        raise ValueError('Khóa đăng ký Push không hợp lệ.')
    try:
        def decode(value):
            value = str(value or '')
            if len(value) > 128 or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', value):
                raise ValueError
            return base64.urlsafe_b64decode(value + '=' * (-len(value)%4))
        public = decode(keys.get('p256dh'))
        auth = decode(keys.get('auth'))
        if len(public) != 65 or len(auth) != 16:
            raise ValueError
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
    except (ValueError, TypeError):
        raise ValueError('Khóa đăng ký Push không hợp lệ.') from None
    return endpoint, str(keys['p256dh']).strip(), str(keys['auth']).strip()


def public_addresses(host):
    addresses = list(dict.fromkeys(row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses:
        raise ValueError('Không phân giải được dịch vụ Push.')
    for value in addresses:
        ip = ipaddress.ip_address(value)
        mapped = getattr(ip, 'ipv4_mapped', None)
        if not ip.is_global or (mapped and not mapped.is_global):
            raise ValueError('Dịch vụ Push không được trỏ tới địa chỉ nội bộ.')
    return addresses


class _PinnedTLS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class SafePushSession:
    def post(self, endpoint, *, data=None, headers=None, timeout=10, **kwargs):
        url = endpoint_parts(endpoint)
        addresses = public_addresses(url.hostname)
        connection = _PinnedTLS(url.hostname, addresses[0], min(float(timeout), 15))
        try:
            path = url.path + ('?' + url.query if url.query else '')
            connection.request('POST', path, body=data, headers=dict(headers or {}))
            incoming = connection.getresponse()
            response = Response()
            response.status_code = incoming.status
            response.headers = CaseInsensitiveDict(incoming.getheaders())
            response._content = incoming.read(4096)
            response.url = endpoint
            if 300 <= incoming.status < 400:
                raise ValueError('Dịch vụ Push chuyển hướng; yêu cầu đã bị chặn.')
            return response
        finally:
            connection.close()
