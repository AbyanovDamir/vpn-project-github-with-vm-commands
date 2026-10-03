#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Запустите скрипт через sudo." >&2
  exit 1
fi

ROLE="${1:-}"
case "${ROLE}" in
  server)
    systemctl restart wg-quick@wg0 nftables oauth-server vpn-web
    systemctl --no-pager --full status wg-quick@wg0 nftables oauth-server vpn-web
    ;;
  client)
    systemctl restart wg-quick@wg0
    systemctl --no-pager --full status wg-quick@wg0
    ;;
  *)
    echo "Использование: sudo bash scripts/restart.sh server|client" >&2
    exit 2
    ;;
esac

