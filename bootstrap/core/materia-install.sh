#!/usr/bin/env bash
# Install Podman (system + user lingering for pilot), Cockpit, Materia v0.7.2,
# age, and systemd timers. Does not run materia server.
#
#   sudo bash bootstrap/core/materia-install.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

MATERIA_VERSION="${MATERIA_VERSION:-0.7.2}"
PILOT="${PILOT_USER:-pilot}"
ARCH=$(uname -m)
case "${ARCH}" in
  aarch64|arm64) MATERIA_ARCH=arm64 ;;
  x86_64|amd64) MATERIA_ARCH=amd64 ;;
  *) echo "Unsupported arch ${ARCH}"; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y podman uidmap slirp4netns fuse-overlayfs dbus-user-session cockpit cockpit-podman curl age git

loginctl enable-linger "${PILOT}"

install -d -m 0755 /etc/materia /var/lib/materia
if [[ ! -f /etc/materia/age.key ]]; then
  age-keygen -o /etc/materia/age.key
  chmod 600 /etc/materia/age.key
  age-keygen -y /etc/materia/age.key > /etc/materia/age.pubkey
  chmod 644 /etc/materia/age.pubkey
  echo "Wrote /etc/materia/age.key (never commit)."
fi

MATERIA_URL="https://github.com/stryan/materia/releases/download/v${MATERIA_VERSION}/materia_Linux_${MATERIA_ARCH}.tar.gz"
tmp=$(mktemp -d)
curl -fsSL "${MATERIA_URL}" -o "${tmp}/materia.tgz" || {
  echo "Download failed: ${MATERIA_URL}"
  echo "Install the v${MATERIA_VERSION} binary for ${MATERIA_ARCH} into /usr/local/bin/materia by hand."
  exit 1
}
tar -xzf "${tmp}/materia.tgz" -C "${tmp}"
install -m 0755 "${tmp}/materia" /usr/local/bin/materia
rm -rf "${tmp}"

install -m 644 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/materia-system.service" /etc/systemd/system/materia-system.service
install -m 644 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/materia-system.timer" /etc/systemd/system/materia-system.timer
install -d -m 0755 "/home/${PILOT}/.config/systemd/user"
install -m 644 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/materia-user.service" "/home/${PILOT}/.config/systemd/user/materia-user.service"
install -m 644 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/materia-user.timer" "/home/${PILOT}/.config/systemd/user/materia-user.timer"
chown -R "${PILOT}:${PILOT}" "/home/${PILOT}/.config/systemd/user"

systemctl daemon-reload
systemctl enable --now cockpit.socket materia-system.timer
systemctl --machine="${PILOT}@" --user daemon-reload || true
systemctl --machine="${PILOT}@" --user enable --now materia-user.timer || true

echo "Materia $(materia version 2>/dev/null || echo "v${MATERIA_VERSION}")"
echo "Cockpit: https://<NAS_LAN_IP>:9090 (or https://box.<DOMAIN> through Caddy)"
echo "Encrypt attributes with: age -r \"\$(cat /etc/materia/age.pubkey)\" -o attributes/vault.age attributes/vault.example.toml"
