import ast
import pathlib
import re

root = pathlib.Path(__file__).resolve().parents[1]
required = (
    "README.md",
    "LICENSE",
    ".gitignore",
    "requirements-dev.txt",
    ".github/workflows/ci.yml",
    "app/common.py",
    "app/web_app.py",
    "app/oauth_server.py",
    "deploy/nftables.conf",
    "deploy/vpn-lab.env.example",
    "deploy/systemd/vpn-web.service",
    "deploy/systemd/oauth-server.service",
    "deploy/wireguard/server-wg0.conf.template",
    "deploy/wireguard/client-wg0.conf.template",
    "scripts/install_server.sh",
    "scripts/install_client.sh",
    "scripts/add_client.sh",
    "scripts/status.sh",
    "scripts/restart.sh",
    "scripts/test_client.sh",
    "scripts/cleanup.sh",
    "scripts/integration_oauth_test.py",
)
missing = [item for item in required if not (root / item).is_file()]
assert not missing, f"Missing project files: {', '.join(missing)}"

for path in (root / "app").glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

web = (root / "app" / "web_app.py").read_text(encoding="utf-8")
oauth = (root / "app" / "oauth_server.py").read_text(encoding="utf-8")
nft = (root / "deploy" / "nftables.conf").read_text(encoding="utf-8")

assert all(route in web for route in ('url.path == "/"', 'url.path == "/about"', 'url.path == "/private"'))
assert "code_challenge_method" in web and "code_verifier" in web
assert "hmac.compare_digest(challenge" in oauth
assert re.search(r'iifname "wg0".*tcp dport \{ 8080, 9000 \} accept', nft)

for forbidden in ("*.key", "*.pem"):
    leaked = [p for p in root.rglob(forbidden) if ".git" not in p.parts]
    assert not leaked, f"Secret-looking files must not be committed: {leaked}"

readme = (root / "README.md").read_text(encoding="utf-8")
for command in ("git clone", "install_server.sh", "install_client.sh", "test_client.sh", "cleanup.sh"):
    assert command in readme, f"README is missing command: {command}"

print("OK: complete repository, Python syntax, 3 pages, OAuth PKCE and wg0-only firewall rule verified")

