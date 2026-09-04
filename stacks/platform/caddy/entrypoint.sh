#!/bin/sh
# Export the tls-internal CA, then run Caddy. No --watch: Komodo config_files
# already requires Redeploy, and --watch on a bind-mount reloads in a loop.
/bin/sh /export-ca.sh &
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
