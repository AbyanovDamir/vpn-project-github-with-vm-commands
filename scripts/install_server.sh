#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VPN_USER=${VPN_USER:-vpnlab}
VPN_SERVER_ADDRESS=${VPN_SERVER_ADDRESS:-10.20.0.1/24}
DEMO_USER=${DEMO_USER:-student}
DEMO_PASSWORD=${DEMO_PASSWORD:-vpn-demo}

if [ "$(id -u)" -ne 0 ]; then
  echo "Запустите: sudo bash scripts/install_server.sh" >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard nftables python3 curl openssl

id "$VPN_USER" >/dev/null 2>&1 || useradd --system --home /opt/vpn-lab --shell /usr/sbin/nologin "$VPN_USER"
install -d -m 0755 -o "$VPN_USER" -g "$VPN_USER" /opt/vpn-lab/app
install -m 0644 -o "$VPN_USER" -g "$VPN_USER" "$ROOT_DIR"/app/*.py /opt/vpn-lab/app/

install -d -m 0700 /etc/wireguard /etc/vpn-lab-keys
umask 077
if [ ! -f /etc/vpn-lab-keys/server.key ]; then
  wg genkey | tee /etc/vpn-lab-keys/server.key | wg pubkey > /etc/vpn-lab-keys/server.pub
fi
chmod 0600 /etc/vpn-lab-keys/server.key /etc/vpn-lab-keys/server.pub

if [ ! -f /etc/wireguard/wg0.conf ]; then
  server_private=$(cat /etc/vpn-lab-keys/server.key)
  cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = ${VPN_SERVER_ADDRESS}
ListenPort = 51820
PrivateKey = ${server_private}
SaveConfig = false
EOF
  chmod 0600 /etc/wireguard/wg0.conf
fi

if [ ! -f /etc/vpn-lab.env ]; then
  session_secret=$(openssl rand -hex 32)
  sed \
    -e "s|REPLACE_WITH_RANDOM_VALUE|${session_secret}|" \
    -e "s|REPLACE_WITH_STRONG_PASSWORD|${DEMO_PASSWORD}|" \
    -e "s|DEMO_USER=student|DEMO_USER=${DEMO_USER}|" \
    "$ROOT_DIR/deploy/vpn-lab.env.example" > /etc/vpn-lab.env
  chown root:"$VPN_USER" /etc/vpn-lab.env
  chmod 0640 /etc/vpn-lab.env
fi

install -m 0644 "$ROOT_DIR"/deploy/systemd/*.service /etc/systemd/system/

if [ -f /etc/nftables.conf ] && [ ! -f /etc/nftables.conf.vpn-lab.bak ]; then
  cp -a /etc/nftables.conf /etc/nftables.conf.vpn-lab.bak
fi
nft -c -f "$ROOT_DIR/deploy/nftables.conf"
install -m 0644 "$ROOT_DIR/deploy/nftables.conf" /etc/nftables.conf

systemctl daemon-reload
systemctl enable --now wg-quick@wg0.service nftables.service
systemctl enable --now oauth-server.service vpn-web.service

echo
echo "Сервер установлен. Публичный ключ сервера:"
cat /etc/vpn-lab-keys/server.pub
echo
echo "Следующий шаг: настройте клиент этим ключом, затем выполните на сервере:"
echo "sudo CLIENT_PUBLIC_KEY='<ключ-клиента>' bash scripts/add_client.sh"

