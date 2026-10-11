#!/bin/sh
# Drop a web overlay built for a different binary. Sablier recreates the
# container, so a pulled image would keep serving the previous chunk names
# and the browser would show the splash error.
set -eu
digest=$(sha256sum /usr/bin/opencloud | awk '{print $1}')
assets=/var/lib/opencloud/web/assets
overlay=$assets/core
stamp=$assets/.image
if [ -d "$overlay" ]; then
  current=$(cat "$stamp" 2>/dev/null || true)
  if [ "$current" != "$digest" ]; then
    rm -rf "$overlay"
    mkdir -p "$assets"
    printf '%s\n' "$digest" > "$stamp"
  fi
fi
opencloud init || true
exec opencloud server
