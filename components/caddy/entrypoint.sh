#!/bin/sh
# Export the tls-internal CA, then run Caddy. No --watch: Materia
# already requires Redeploy, and --watch on a bind-mount reloads in a loop.
# 127.0.0.1 is in extra_hosts; reverse_proxy retries backends.
/bin/sh /export-ca.sh &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
