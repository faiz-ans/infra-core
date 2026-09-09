#!/bin/sh
# Export the tls-internal CA, then run Caddy. No --watch: Komodo config_files
# already requires Redeploy, and --watch on a bind-mount reloads in a loop.
# host.docker.internal is in extra_hosts; reverse_proxy retries backends.
/bin/sh /export-ca.sh &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
