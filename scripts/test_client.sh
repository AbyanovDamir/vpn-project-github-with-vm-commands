#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
VPN_WEB_URL="${VPN_WEB_URL:-http://10.20.0.1:8080}"
OAUTH_URL="${OAUTH_URL:-http://10.20.0.1:9000}"
SERVER_LAN_URL="${SERVER_LAN_URL:-}"
VPN_WAS_ACTIVE=0

if systemctl is-active --quiet wg-quick@wg0; then
  VPN_WAS_ACTIVE=1
fi

restore_vpn() {
  if [[ ${VPN_WAS_ACTIVE} -eq 1 ]]; then
    sudo systemctl start wg-quick@wg0 >/dev/null 2>&1 || true
  fi
}
trap restore_vpn EXIT

echo "[1/4] Проверка запрета доступа без VPN"
sudo systemctl stop wg-quick@wg0
if curl --connect-timeout 3 --max-time 5 -fsS "${VPN_WEB_URL}/health" >/dev/null 2>&1; then
  echo "ОШИБКА: ${VPN_WEB_URL} доступен при выключенном VPN." >&2
  exit 1
fi
echo "OK: VPN-адрес недоступен без туннеля."

if [[ -n "${SERVER_LAN_URL}" ]]; then
  if curl --connect-timeout 3 --max-time 5 -fsS "${SERVER_LAN_URL}/health" >/dev/null 2>&1; then
    echo "ОШИБКА: LAN-адрес ${SERVER_LAN_URL} доступен без VPN." >&2
    exit 1
  fi
  echo "OK: LAN-адрес веб-приложения закрыт правилами nftables."
fi

echo "[2/4] Включение VPN"
sudo systemctl start wg-quick@wg0
ping -c 2 10.20.0.1

echo "[3/4] Проверка веб-приложения"
curl -fsS "${VPN_WEB_URL}/health"
echo
curl -fsS "${VPN_WEB_URL}/about" >/dev/null

echo "[4/4] Проверка OAuth 2.0 Authorization Code + PKCE"
BASE_URL="${VPN_WEB_URL}" OAUTH_URL="${OAUTH_URL}" \
  python3 "${REPO_ROOT}/scripts/integration_oauth_test.py"

echo "Все клиентские проверки пройдены."

