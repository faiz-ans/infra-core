#!/bin/sh
# Always replace configuration.yaml in the container's /config (NFS or local).
# Merge/append left a first http: block without use_x_forwarded_for; HA keeps that one.
# UI automations live in .storage and are not touched.
set -e
cfg="${HA_CONFIG:-/config/configuration.yaml}"
mkdir -p "$(dirname "$cfg")"
cat > "$cfg" <<'EOF'
default_config:

http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 192.168.0.0/16
    - 10.0.0.0/8
    - 172.16.0.0/12
    - 172.24.0.0/16
    - 192.168.65.0/24
    - 169.254.0.0/16
    - 0.0.0.0/0
    - ::/0
EOF
if [ -x /init ]; then
  exec /init "$@"
fi
