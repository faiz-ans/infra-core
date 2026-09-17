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
# catatonit: kube-play pause. netavark+aardvark-dns: the `site` bridge.
# Debian ships netavark in /usr/lib/podman, which Podman's default helper
# search path does not include.
apt-get install -y podman uidmap slirp4netns fuse-overlayfs catatonit netavark aardvark-dns \
  dbus-user-session cockpit cockpit-podman curl git gettext-base

install -d -m 0755 /etc/containers/containers.conf.d
cat > /etc/containers/containers.conf.d/99-infra-core.conf <<'EOF'
[engine]
helper_binaries_dir = [
  "/usr/lib/podman",
  "/usr/libexec/podman",
  "/usr/bin",
]
EOF
chmod 644 /etc/containers/containers.conf.d/99-infra-core.conf
# A user containers.conf helper_binaries_dir replaces this drop-in. Do not write one.
rm -f /etc/containers/containers.conf.d/99-infra-core-helpers.conf

loginctl enable-linger "${PILOT}"

systemctl enable --now podman.socket
systemctl enable --now cockpit.socket

systemctl daemon-reload
systemctl --machine="${PILOT}@" --user daemon-reload 2>/dev/null || true

echo "Podman $(podman version --format '{{.Client.Version}}' 2>/dev/null || echo installed), linger ${PILOT}, Cockpit socket on."
echo "Cockpit: https://<NAS_LAN_IP>:9090 (or https://box.<DOMAIN> through Caddy)"
