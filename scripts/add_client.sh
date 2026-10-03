#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo CLIENT_PUBLIC_KEY=... bash scripts/add_client.sh" >&2
  exit 1
fi

: "${CLIENT_PUBLIC_KEY:?Укажите CLIENT_PUBLIC_KEY — публичный ключ WireGuard-клиента}"

SERVER_ADDRESS="${SERVER_ADDRESS:-10.20.0.1/24}"
CLIENT_VPN_IP="${CLIENT_VPN_IP:-10.20.0.2/32}"
LISTEN_PORT="${LISTEN_PORT:-51820}"
KEY_DIR=/etc/vpn-lab-keys

if [[ ! -s "${KEY_DIR}/server.key" ]]; then
  echo "Не найден ${KEY_DIR}/server.key. Сначала выполните install_server.sh." >&2
  exit 1
fi

SERVER_PRIVATE_KEY=$(<"${KEY_DIR}/server.key")
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = ${SERVER_ADDRESS}
ListenPort = ${LISTEN_PORT}
PrivateKey = ${SERVER_PRIVATE_KEY}

[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
AllowedIPs = ${CLIENT_VPN_IP}
EOF
chmod 600 /etc/wireguard/wg0.conf

systemctl restart wg-quick@wg0
systemctl restart oauth-server vpn-web

echo "Клиент добавлен. Текущее состояние WireGuard:"
wg show

