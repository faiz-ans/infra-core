#!/bin/sh
set -eu
# Full DATA_ROOT includes system/vaultwarden.
restic snapshots >/dev/null 2>&1 || restic init
while true; do
  restic backup /data --exclude-caches
  sleep 86400
done
