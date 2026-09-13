#!/bin/sh
set -eu
# Full DATA_ROOT includes system/vaultwarden.
restic snapshots >/dev/null 2>&1 || restic init
while true; do
  restic backup /data --exclude-caches
  if [ -n "${UPTIME_KUMA_PUSH_URL:-}" ]; then
    wget -qO- --timeout=15 --no-check-certificate "${UPTIME_KUMA_PUSH_URL}" >/dev/null 2>&1 || echo "uptime-kuma push failed"
  fi
  sleep 86400
done
