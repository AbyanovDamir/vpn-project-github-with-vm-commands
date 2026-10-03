import hashlib
import html
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional

from common import b64url, cookie_header, get_cookie, random_urlsafe, read_signed_payload, sign_payload


HOST = os.environ.get("APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("APP_PORT", "8080"))
BASE_URL = os.environ.get("APP_BASE_URL", f"http://{HOST}:{PORT}")
OAUTH_URL = os.environ.get("OAUTH_URL", "http://127.0.0.1:9000")
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "vpn-web-client")


def page(title: str, body: str, user: Optional[dict] = None) -> bytes:
    auth = (
        f'<span class="user">{html.escape(user.get("name", ""))}</span> '
        '<a class="ghost" href="/logout">Выйти</a>'
        if user
        else '<a class="primary" href="/login">Войти через OAuth 2.0</a>'
    )
    document = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{html.escape(title)} · VPN Lab</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#eef3f8;color:#152132;font:16px/1.55 Arial,sans-serif}}
header{{background:#102a43;color:white;padding:18px 0;box-shadow:0 3px 12px #102a4330}}
.bar,main{{width:min(920px,calc(100% - 40px));margin:auto}} .bar{{display:flex;align-items:center;gap:28px}}
.brand{{font-weight:700;font-size:20px;letter-spacing:.3px}} nav{{display:flex;gap:20px;flex:1}}
a{{color:#0b6bcb;text-decoration:none}} header a{{color:#d7e9fb}} .primary,.ghost{{padding:9px 14px;border-radius:8px}}
.primary{{background:#22a06b!important;color:white!important;font-weight:700}} .ghost{{border:1px solid #7594b3}}
main{{padding:54px 0}} .card{{background:white;border-radius:16px;padding:38px;box-shadow:0 12px 36px #102a4317;border:1px solid #dbe5ef}}
.eyebrow{{color:#087f5b;text-transform:uppercase;font-weight:700;font-size:13px;letter-spacing:1.6px}}
h1{{font-size:38px;line-height:1.15;margin:10px 0 18px}} h2{{margin-top:28px}} code{{background:#eaf1f8;padding:3px 7px;border-radius:5px}}
.status{{display:inline-flex;gap:9px;align-items:center;background:#e8f7f0;color:#126544;padding:8px 12px;border-radius:999px;font-weight:700}}
.dot{{width:9px;height:9px;border-radius:50%;background:#22a06b}} .user{{color:#fff;font-weight:700}}
footer{{color:#63788d;text-align:center;padding:24px}}
</style></head><body>
<header><div class="bar"><div class="brand">🔐 VPN Lab</div><nav><a href="/">Главная</a><a href="/about">О проекте</a><a href="/private">Личный кабинет</a></nav>{auth}</div></header>
<main><section class="card">{body}</section></main><footer>Учебный стенд · WireGuard + OAuth 2.0 PKCE</footer>
</body></html>"""
    return document.encode()


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} {fmt % args}", flush=True)

    def send(self, status: int, body: bytes, headers: Optional[dict] = None):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location: str, cookie: Optional[str] = None):
        headers = {"Location": location}
        if cookie:
            headers["Set-Cookie"] = cookie
        self.send(302, b"", headers)

    def session(self) -> dict:
        return read_signed_payload(get_cookie(self.headers, "vpn_session"), max_age=8 * 3600)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        session = self.session()
        user = session.get("user")

        if url.path == "/health":
            data = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if url.path == "/":
            body = '<div class="eyebrow">Страница 1</div><h1>Веб-приложение доступно через защищённый VPN</h1><p>Это главная страница учебного стенда. Сетевой доступ ограничен интерфейсом <code>wg0</code>, а вход реализован по OAuth 2.0 Authorization Code с PKCE.</p><p><span class="status"><span class="dot"></span> Веб-сервис работает</span></p>'
            self.send(200, page("Главная", body, user))
        elif url.path == "/about":
            body = '<div class="eyebrow">Страница 2</div><h1>О проекте</h1><p>Стенд состоит из двух независимых HTTP-служб: клиентского веб-приложения и сервера авторизации. WireGuard создаёт приватную сеть <code>10.20.0.0/24</code>.</p><h2>Цель</h2><p>Показать совместную работу прикладной авторизации и сетевого ограничения доступа.</p>'
            self.send(200, page("О проекте", body, user))
        elif url.path == "/private":
            if not user:
                self.redirect("/login")
                return
            body = f'<div class="eyebrow">Защищённая страница</div><h1>Личный кабинет</h1><p>OAuth 2.0 авторизация успешно завершена.</p><p><b>Пользователь:</b> {html.escape(user.get("name", ""))}<br><b>Email:</b> {html.escape(user.get("email", ""))}<br><b>Subject:</b> <code>{html.escape(user.get("sub", ""))}</code></p><p><span class="status"><span class="dot"></span> Доступ разрешён</span></p>'
            self.send(200, page("Личный кабинет", body, user))
        elif url.path == "/login":
            state = random_urlsafe(24)
            verifier = random_urlsafe(48)
            challenge = b64url(hashlib.sha256(verifier.encode()).digest())
            pending = sign_payload({"iat": int(time.time()), "state": state, "verifier": verifier})
            params = urllib.parse.urlencode({
                "response_type": "code", "client_id": CLIENT_ID,
                "redirect_uri": f"{BASE_URL}/callback", "scope": "openid profile email",
                "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
            })
            self.redirect(f"{OAUTH_URL}/authorize?{params}", cookie_header("oauth_pending", pending, 600))
        elif url.path == "/callback":
            query = urllib.parse.parse_qs(url.query)
            pending = read_signed_payload(get_cookie(self.headers, "oauth_pending"), max_age=600)
            if not pending or query.get("state", [""])[0] != pending.get("state"):
                self.send(400, page("Ошибка", "<h1>Ошибка OAuth</h1><p>Проверка параметра state не пройдена.</p>"))
                return
            form = urllib.parse.urlencode({
                "grant_type": "authorization_code", "code": query.get("code", [""])[0],
                "client_id": CLIENT_ID, "redirect_uri": f"{BASE_URL}/callback",
                "code_verifier": pending["verifier"],
            }).encode()
            try:
                request = urllib.request.Request(f"{OAUTH_URL}/token", data=form, headers={"Content-Type": "application/x-www-form-urlencoded"})
                token = json.loads(urllib.request.urlopen(request, timeout=5).read())
                profile_request = urllib.request.Request(f"{OAUTH_URL}/userinfo", headers={"Authorization": f"Bearer {token['access_token']}"})
                profile = json.loads(urllib.request.urlopen(profile_request, timeout=5).read())
            except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
                self.send(502, page("Ошибка", f"<h1>Ошибка обмена токена</h1><p>{html.escape(str(exc))}</p>"))
                return
            session_cookie = cookie_header("vpn_session", sign_payload({"iat": int(time.time()), "user": profile}), 8 * 3600)
            self.redirect("/private", session_cookie)
        elif url.path == "/logout":
            self.redirect("/", cookie_header("vpn_session", "", 0))
        else:
            self.send(404, page("404", "<h1>Страница не найдена</h1>"))


if __name__ == "__main__":
    print(f"Web app: {BASE_URL} (bind {HOST}:{PORT})", flush=True)
    ThreadingHTTPServer((HOST, PORT), AppHandler).serve_forever()

