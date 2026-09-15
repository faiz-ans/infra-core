#!/bin/sh
set -eu
# Full DATA_ROOT includes system/vaultwarden and household trees.
restic snapshots >/dev/null 2>&1 || restic init
while true; do
  restic backup /data --host core --exclude-caches --exclude /data/system/restic
  restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
  if [ -n "${UPTIME_KUMA_PUSH_URL:-}" ]; then
    wget -qO- --timeout=15 --no-check-certificate "${UPTIME_KUMA_PUSH_URL}" >/dev/null 2>&1 || echo "uptime-kuma push failed"
  fi
  sleep 86400
done
