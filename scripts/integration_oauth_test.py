import re
import requests
import os
from urllib.parse import urljoin


session = requests.Session()
base = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
oauth = os.environ.get("OAUTH_URL", "http://127.0.0.1:9000")
demo_user = os.environ.get("DEMO_USER", "student")
demo_password = os.environ.get("DEMO_PASSWORD", "vpn-demo")

home = session.get(base + "/")
assert home.status_code == 200 and "Страница 1" in home.text
about = session.get(base + "/about")
assert about.status_code == 200 and "Страница 2" in about.text

login = session.get(base + "/private")
assert login.url.startswith(oauth + "/authorize")

fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', login.text))
fields.update({"username": demo_user, "password": demo_password})
authorized = session.post(oauth + "/authorize", data=fields, allow_redirects=True)
assert authorized.url == base + "/private"
assert authorized.status_code == 200
assert "OAuth 2.0 авторизация успешно завершена" in authorized.text
assert f"{demo_user}@example.test" in authorized.text

print("OK: home, about, Authorization Code + PKCE, token exchange and private page")

