#!/usr/bin/env bash
# OPTIONAL. Not called by core.sh. Installs Materia as a git-pull timer that
# runs bootstrap/apply.sh. Future-site GitOps is unspecified; skip this on a
# static site.
#
#   sudo bash bootstrap/core/materia-enable.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

MATERIA_VERSION="${MATERIA_VERSION:-0.7.2}"
PILOT="${PILOT_USER:-pilot}"
REPO="${REPO_ROOT:-/home/${PILOT}/infra-core}"
ARCH=$(uname -m)
case "${ARCH}" in
  aarch64|arm64) MATERIA_ARCH=arm64 ;;
  x86_64|amd64) MATERIA_ARCH=amd64 ;;
  *) echo "Unsupported arch ${ARCH}"; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y curl age git

install -d -m 0755 /etc/materia
if [[ ! -f /etc/materia/age.key ]]; then
  age-keygen -o /etc/materia/age.key
  chmod 600 /etc/materia/age.key
  age-keygen -y /etc/materia/age.key > /etc/materia/age.pubkey
  chmod 644 /etc/materia/age.pubkey
  echo "Wrote /etc/materia/age.key (never commit)."
fi

MATERIA_URL="https://github.com/stryan/materia/releases/download/v${MATERIA_VERSION}/materia-${MATERIA_ARCH}"
tmp=$(mktemp)
curl -fsSL "${MATERIA_URL}" -o "${tmp}" || {
  echo "Download failed: ${MATERIA_URL}"
  echo "Install the v${MATERIA_VERSION} binary for ${MATERIA_ARCH} into /usr/local/bin/materia by hand."
  exit 1
}
install -m 0755 "${tmp}" /usr/local/bin/materia
rm -f "${tmp}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY="${SCRIPT_DIR}/../apply.sh"
if [[ ! -f "${APPLY}" ]]; then
  echo "Missing ${APPLY}"
  exit 1
fi

cat > /etc/systemd/system/infra-apply.service <<EOF
[Unit]
Description=infra-core git pull + apply.sh
After=network-online.target

[Service]
Type=oneshot
User=root
WorkingDirectory=${REPO}
ExecStart=/usr/bin/git -C ${REPO} pull --ff-only
ExecStart=/bin/bash ${APPLY}
EOF

cat > /etc/systemd/system/infra-apply.timer <<'EOF'
[Unit]
Description=Periodic infra-core apply (optional Materia-era poller)

[Timer]
OnBootSec=5min
OnUnitInactiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now infra-apply.timer

echo "Materia binary $(materia version 2>/dev/null || echo "v${MATERIA_VERSION}") is on PATH."
echo "Timer infra-apply.timer runs: git pull && bash bootstrap/apply.sh (no .gotmpl renderer)."
echo "Default stacks do not need this. Disable with: systemctl disable --now infra-apply.timer"
