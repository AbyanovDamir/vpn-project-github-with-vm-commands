#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo ... bash scripts/install_client.sh" >&2
  exit 1
fi

: "${SERVER_PUBLIC_KEY:?Укажите SERVER_PUBLIC_KEY — публичный ключ WireGuard-сервера}"
: "${SERVER_ENDPOINT:?Укажите SERVER_ENDPOINT, например 192.168.100.10:51820}"

CLIENT_ADDRESS="${CLIENT_ADDRESS:-10.20.0.2/24}"
VPN_NETWORK="${VPN_NETWORK:-10.20.0.0/24}"
KEY_DIR=/etc/vpn-lab-keys

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wireguard curl git python3 python3-requests

install -d -m 700 "${KEY_DIR}"
if [[ ! -s "${KEY_DIR}/client.key" ]]; then
  umask 077
  wg genkey | tee "${KEY_DIR}/client.key" | wg pubkey > "${KEY_DIR}/client.pub"
fi

CLIENT_PRIVATE_KEY=$(<"${KEY_DIR}/client.key")
install -d -m 700 /etc/wireguard
cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = ${CLIENT_ADDRESS}
PrivateKey = ${CLIENT_PRIVATE_KEY}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${SERVER_ENDPOINT}
AllowedIPs = ${VPN_NETWORK}
PersistentKeepalive = 25
EOF
chmod 600 /etc/wireguard/wg0.conf

systemctl enable --now wg-quick@wg0

echo
echo "Клиент WireGuard установлен. Публичный ключ клиента:"
cat "${KEY_DIR}/client.pub"
echo
echo "Скопируйте ключ на сервер и выполните:"
echo "  sudo CLIENT_PUBLIC_KEY='<ключ>' bash scripts/add_client.sh"

