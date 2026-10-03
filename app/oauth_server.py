import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional


HOST = os.environ.get("OAUTH_HOST", "127.0.0.1")
PORT = int(os.environ.get("OAUTH_PORT", "9000"))
ISSUER = os.environ.get("OAUTH_ISSUER", f"http://{HOST}:{PORT}")
CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "vpn-web-client")
ALLOWED_REDIRECT = os.environ.get("OAUTH_REDIRECT_URI", "http://127.0.0.1:8080/callback")
DEMO_USER = os.environ.get("DEMO_USER", "student")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "vpn-demo")

CODES = {}  # type: Dict[str, dict]
TOKENS = {}  # type: Dict[str, dict]


def login_page(params: dict, error: str = "") -> bytes:
    hidden = "".join(f'<input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}">' for k, v in params.items())
    warning = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>OAuth 2.0 · Авторизация</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(145deg,#0c2946,#155b83);min-height:100vh;display:grid;place-items:center;font:16px Arial;color:#152132}}
.panel{{width:min(440px,calc(100% - 36px));background:white;border-radius:18px;padding:38px;box-shadow:0 24px 70px #001a3380}}
.logo{{color:#087f5b;font-weight:800;letter-spacing:1px}}h1{{font-size:30px;margin:14px 0 8px}}p{{color:#60758a;line-height:1.5}}
label{{display:block;font-weight:700;margin:18px 0 7px}}input{{width:100%;padding:12px;border:1px solid #b8c8d8;border-radius:8px;font-size:16px}}
button{{margin-top:24px;width:100%;padding:13px;border:0;border-radius:8px;background:#087f5b;color:white;font-weight:800;font-size:16px;cursor:pointer}}
.note{{margin-top:20px;padding:12px;background:#eef6ff;border-radius:8px;font-size:13px}}.error{{background:#ffe8e8;color:#a01818;padding:10px;border-radius:8px}}
</style></head><body><main class="panel"><div class="logo">VPN LAB ID</div><h1>Вход в приложение</h1><p>OAuth 2.0 Authorization Server</p>{warning}
<form method="post" action="/authorize">{hidden}<label>Имя пользователя</label><input name="username" value="student" autocomplete="username"><label>Пароль</label><input name="password" type="password" value="vpn-demo" autocomplete="current-password"><button type="submit">Разрешить доступ</button></form>
<div class="note">Учебная учётная запись: <b>student</b> / <b>vpn-demo</b><br>Запрошенные права: openid, profile, email</div></main></body></html>""".encode()


class OAuthHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[oauth] {self.address_string()} {fmt % args}", flush=True)

    def reply(self, status: int, body: bytes, content_type="application/json; charset=utf-8", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def json(self, status: int, value: dict):
        self.reply(status, json.dumps(value).encode())

    def validate_authorize(self, p: dict) -> Optional[str]:
        if p.get("response_type") != "code": return "Поддерживается только response_type=code"
        if p.get("client_id") != CLIENT_ID: return "Неизвестный client_id"
        if p.get("redirect_uri") != ALLOWED_REDIRECT: return "Недопустимый redirect_uri"
        if p.get("code_challenge_method") != "S256" or not p.get("code_challenge"): return "Обязателен PKCE S256"
        return None

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/.well-known/oauth-authorization-server":
            self.json(200, {"issuer": ISSUER, "authorization_endpoint": ISSUER+"/authorize", "token_endpoint": ISSUER+"/token", "userinfo_endpoint": ISSUER+"/userinfo", "response_types_supported": ["code"], "code_challenge_methods_supported": ["S256"]})
        elif url.path == "/authorize":
            p = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            error = self.validate_authorize(p)
            self.reply(400 if error else 200, login_page(p, error or ""), "text/html; charset=utf-8")
        elif url.path == "/userinfo":
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            record = TOKENS.get(token)
            if not record or record["expires"] < time.time():
                self.json(401, {"error": "invalid_token"})
            else:
                self.json(200, {"sub": "user-001", "name": "Студент VPN Lab", "email": "student@example.test"})
        elif url.path == "/health": self.json(200, {"status": "ok"})
        else: self.json(404, {"error": "not_found"})

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0")); raw = self.rfile.read(size).decode()
        p = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
        if self.path == "/authorize":
            error = self.validate_authorize(p)
            if error or not (hmac.compare_digest(p.get("username", ""), DEMO_USER) and hmac.compare_digest(p.get("password", ""), DEMO_PASSWORD)):
                self.reply(400, login_page({k: v for k, v in p.items() if k not in ("username", "password")}, error or "Неверное имя пользователя или пароль"), "text/html; charset=utf-8"); return
            code = secrets.token_urlsafe(32)
            CODES[code] = {"client_id": p["client_id"], "redirect_uri": p["redirect_uri"], "challenge": p["code_challenge"], "expires": time.time()+120}
            sep = "&" if "?" in p["redirect_uri"] else "?"
            location = p["redirect_uri"] + sep + urllib.parse.urlencode({"code": code, "state": p.get("state", "")})
            self.reply(302, b"", headers={"Location": location})
        elif self.path == "/token":
            record = CODES.pop(p.get("code", ""), None)
            verifier = p.get("code_verifier", "")
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
            valid = record and record["expires"] >= time.time() and p.get("grant_type") == "authorization_code" and p.get("client_id") == record["client_id"] and p.get("redirect_uri") == record["redirect_uri"] and hmac.compare_digest(challenge, record["challenge"])
            if not valid: self.json(400, {"error": "invalid_grant"}); return
            token = secrets.token_urlsafe(36); TOKENS[token] = {"expires": time.time()+3600}
            self.json(200, {"access_token": token, "token_type": "Bearer", "expires_in": 3600, "scope": "openid profile email"})
        else: self.json(404, {"error": "not_found"})


if __name__ == "__main__":
    print(f"OAuth server: {ISSUER} (bind {HOST}:{PORT})", flush=True)
    ThreadingHTTPServer((HOST, PORT), OAuthHandler).serve_forever()

