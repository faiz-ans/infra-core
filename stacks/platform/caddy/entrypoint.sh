#!/bin/sh
# Export the tls-internal CA, then run Caddy. No --watch: Komodo config_files
# already requires Redeploy, and --watch on a bind-mount reloads in a loop.
#
# After reboot, USB/PCIe NICs can get DHCP after Docker has already started
# Caddy. First lookups of edge names / host.docker.internal fail and stay
# cached until `docker restart caddy`. Wait until Docker DNS answers.
wait_name() {
  name=$1
  i=0
  while [ "${i}" -lt 60 ]; do
    if getent hosts "${name}" >/dev/null 2>&1; then
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done
  return 1
}
wait_name host.docker.internal || true
wait_name pihole || true
wait_name authelia || true
wait_name homepage || true

/bin/sh /export-ca.sh &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
