#!/usr/bin/env bash
set -Eeuo pipefail

ROLE="${1:-}"
if [[ "${ROLE}" != "server" && "${ROLE}" != "client" ]]; then
  echo "Использование: bash scripts/status.sh server|client" >&2
  exit 2
fi

echo "=== Узел ==="
printf 'hostname: '; hostname
printf 'user: '; id -un
printf 'wg0 address: '; ip -brief address show wg0 2>/dev/null || echo "интерфейс отсутствует"

echo
echo "=== WireGuard ==="
sudo wg show || true

if [[ "${ROLE}" == "server" ]]; then
  echo
  echo "=== Сервисы ==="
  systemctl --no-pager --full status wg-quick@wg0 nftables oauth-server vpn-web || true
  echo
  echo "=== Слушающие сокеты ==="
  sudo ss -lntup | grep -E ':(22|8080|9000|51820)\b' || true
  echo
  echo "=== Локальная проверка ==="
  curl -fsS http://10.20.0.1:8080/health || true
  echo
else
  echo
  echo "=== Доступ через VPN ==="
  ping -c 2 10.20.0.1 || true
  curl -fsS http://10.20.0.1:8080/health || true
  echo
fi

