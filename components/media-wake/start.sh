#!/bin/sh
# The 2:55 and 4:55 windows are local time. This image does not ship zoneinfo,
# so the container file mounts the host's. Install it only if that mount is absent.
zone="${TZ:-America/Los_Angeles}"
if [ ! -e "/usr/share/zoneinfo/$zone" ]; then
  if ! apk add --no-cache tzdata >/dev/null; then
    echo "media-wake: tzdata install failed" >&2
    exit 1
  fi
fi
exec python3 -u /media-wake.py
