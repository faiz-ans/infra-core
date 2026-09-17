#!/usr/bin/env bash
# OPTIONAL. Mantle user timer: git pull + apply.sh. Not part of idle WSL setup.
#
#   sudo bash bootstrap/mantle/materia-enable.sh
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo) so linger and the user unit can be installed."
  exit 1
fi

PILOT="${PILOT_USER:-pilot}"
REPO="${REPO_ROOT:-/home/${PILOT}/infra-core}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY="${SCRIPT_DIR}/../apply.sh"

install -d -m 0755 "/home/${PILOT}/.config/systemd/user"
cat > "/home/${PILOT}/.config/systemd/user/infra-apply.service" <<EOF
[Unit]
Description=infra-core git pull + apply.sh (mantle)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${REPO}
ExecStart=/usr/bin/git -C ${REPO} pull --ff-only
ExecStart=/usr/bin/sudo /bin/bash ${APPLY} --host mantle
EOF
cat > "/home/${PILOT}/.config/systemd/user/infra-apply.timer" <<'EOF'
[Unit]
Description=Periodic mantle apply (optional)

[Timer]
OnBootSec=5min
OnUnitInactiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
EOF
chown -R "${PILOT}:${PILOT}" "/home/${PILOT}/.config/systemd/user"
loginctl enable-linger "${PILOT}"
systemctl --machine="${PILOT}@" --user daemon-reload
systemctl --machine="${PILOT}@" --user enable --now infra-apply.timer
echo "Enabled user infra-apply.timer for ${PILOT}. Not required for a static site."
