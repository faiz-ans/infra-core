#!/bin/sh
# Export the tls-internal CA, then run Caddy. No --watch: Komodo config_files
# already requires Redeploy, and --watch on a bind-mount reloads in a loop.
#
# extra_hosts: host.docker.internal is always in /etc/hosts. Do not delay
# :443 for getent of edge names; reverse_proxy retries backends.
/bin/sh /export-ca.sh &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
