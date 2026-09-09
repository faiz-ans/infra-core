#!/bin/sh
# Export the tls-internal CA, then run Caddy. No --watch: Komodo config_files
# already requires Redeploy, and --watch on a bind-mount reloads in a loop.
#
# host.docker.internal is extra_hosts (instant). Do not wait 60s per edge
# name: that leaves :443 closed for minutes after Pi-hole :53 is already up.
# core-lan-bind restarts this container once LAN DNS exists; reverse_proxy
# retries backends that are still starting.
wait_name() {
  name=$1
  i=0
  while [ "${i}" -lt 15 ]; do
    if getent hosts "${name}" >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  return 1
}
wait_name host.docker.internal || true

/bin/sh /export-ca.sh &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
