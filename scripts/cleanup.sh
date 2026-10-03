#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Запустите скрипт через sudo." >&2
  exit 1
fi

ROLE="${1:-}"
CONFIRM="${2:-}"
if [[ "${ROLE}" != "server" && "${ROLE}" != "client" ]] || [[ "${CONFIRM}" != "--yes" ]]; then
  echo "Использование: sudo bash scripts/cleanup.sh server|client --yes" >&2
  echo "Команда удаляет конфигурацию лабораторной работы, но не удаляет пакеты." >&2
  exit 2
fi

if [[ "${ROLE}" == "server" ]]; then
  systemctl disable --now vpn-web oauth-server wg-quick@wg0 2>/dev/null || true
  rm -f /etc/systemd/system/vpn-web.service /etc/systemd/system/oauth-server.service
  rm -f /etc/wireguard/wg0.conf /etc/vpn-lab.env
  rm -rf /opt/vpn-lab /etc/vpn-lab-keys
  nft flush ruleset 2>/dev/null || true
  if [[ -f /etc/nftables.conf.vpn-lab.bak ]]; then
    mv /etc/nftables.conf.vpn-lab.bak /etc/nftables.conf
    systemctl restart nftables || true
  else
    systemctl disable --now nftables 2>/dev/null || true
  fi
  systemctl daemon-reload
  echo "Серверная конфигурация лабораторной работы удалена."
else
  systemctl disable --now wg-quick@wg0 2>/dev/null || true
  rm -f /etc/wireguard/wg0.conf
  rm -rf /etc/vpn-lab-keys
  echo "Клиентская конфигурация лабораторной работы удалена."
fi

