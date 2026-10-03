import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from http import cookies


SESSION_SECRET = os.environ.get("SESSION_SECRET", "development-only-change-me").encode()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def sign_payload(payload: dict) -> str:
    raw = b64url(json.dumps(payload, separators=(",", ":")).encode())
    signature = b64url(hmac.new(SESSION_SECRET, raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{signature}"


def read_signed_payload(value: str, max_age: int = 3600) -> dict:
    try:
        raw, signature = value.split(".", 1)
        expected = b64url(hmac.new(SESSION_SECRET, raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return {}
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if int(time.time()) - int(payload.get("iat", 0)) > max_age:
            return {}
        return payload
    except (ValueError, TypeError, json.JSONDecodeError):
        return {}


def get_cookie(headers, name: str) -> str:
    jar = cookies.SimpleCookie(headers.get("Cookie", ""))
    morsel = jar.get(name)
    return morsel.value if morsel else ""


def cookie_header(name: str, value: str, max_age: int = 3600) -> str:
    jar = cookies.SimpleCookie()
    jar[name] = value
    jar[name]["path"] = "/"
    jar[name]["httponly"] = True
    jar[name]["samesite"] = "Lax"
    jar[name]["max-age"] = max_age
    return jar.output(header="").strip()


def random_urlsafe(length: int = 32) -> str:
    return secrets.token_urlsafe(length)

