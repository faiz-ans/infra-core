#!/usr/bin/env bash
# Layer 0: Podman (system + user linger for pilot), Cockpit, podman.socket.
# Does not install Materia.
#
#   sudo bash bootstrap/core/podman-install.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

PILOT="${PILOT_USER:-pilot}"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y podman uidmap slirp4netns fuse-overlayfs dbus-user-session cockpit cockpit-podman curl git gettext-base

loginctl enable-linger "${PILOT}"

systemctl enable --now podman.socket
systemctl enable --now cockpit.socket

systemctl daemon-reload
systemctl --machine="${PILOT}@" --user daemon-reload 2>/dev/null || true

echo "Podman $(podman version --format '{{.Client.Version}}' 2>/dev/null || echo installed), linger ${PILOT}, Cockpit socket on."
echo "Cockpit: https://<NAS_LAN_IP>:9090 (or https://box.<DOMAIN> through Caddy)"
