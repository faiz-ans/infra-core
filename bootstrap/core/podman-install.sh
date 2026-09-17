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
# Wait out a leftover apt-get from a previous failed run / unattended-upgrades.
for _i in $(seq 1 60); do
  if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
     && ! fuser /var/cache/apt/archives/lock >/dev/null 2>&1; then
    break
  fi
  echo "Waiting for apt lock (pid $(fuser /var/cache/apt/archives/lock 2>/dev/null || true))..."
  sleep 2
done
apt-get update
apt-get install -y podman uidmap slirp4netns fuse-overlayfs catatonit netavark aardvark-dns passt \
  dbus-user-session cockpit cockpit-podman curl git gettext-base

# Debian netavark is /usr/lib/podman/netavark, not /usr/libexec/podman.
# Rootless Podman reads ~/.config/containers/containers.conf and that key
# replaces the system drop-in — write both.
HELPERS_CONF='[engine]
helper_binaries_dir = [
  "/usr/lib/podman",
  "/usr/libexec/podman",
  "/usr/libexec/catatonit",
  "/usr/bin",
]
'
install -d -m 0755 /etc/containers/containers.conf.d
printf '%s' "${HELPERS_CONF}" > /etc/containers/containers.conf.d/99-infra-core.conf
chmod 644 /etc/containers/containers.conf.d/99-infra-core.conf
rm -f /etc/containers/containers.conf.d/99-infra-core-helpers.conf
install -d -m 0755 "/home/${PILOT}/.config/containers"
printf '%s' "${HELPERS_CONF}" > "/home/${PILOT}/.config/containers/containers.conf"
chown "${PILOT}:${PILOT}" "/home/${PILOT}/.config/containers/containers.conf"
chmod 644 "/home/${PILOT}/.config/containers/containers.conf"

loginctl enable-linger "${PILOT}"

systemctl enable --now podman.socket
systemctl enable --now cockpit.socket

systemctl daemon-reload
systemctl --machine="${PILOT}@" --user daemon-reload 2>/dev/null || true

echo "Podman $(podman version --format '{{.Client.Version}}' 2>/dev/null || echo installed), linger ${PILOT}, Cockpit socket on."
echo "Cockpit: https://<NAS_LAN_IP>:9090 (or https://box.<DOMAIN> through Caddy)"
