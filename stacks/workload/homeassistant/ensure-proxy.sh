#!/bin/sh
# Runs before HA. Writes trusted_proxies into the persistent configuration.yaml.
# Do not bind-mount that file over an NFS volume — the overlay is dropped.
set -e
cfg=/config/configuration.yaml
mkdir -p /config
if [ ! -f "$cfg" ]; then
  printf '%s\n' 'default_config:' > "$cfg"
fi
if ! grep -q trusted_proxies "$cfg"; then
  if grep -q '^http:[[:space:]]*$' "$cfg"; then
    awk '
      { print }
      /^http:[[:space:]]*$/ && !done {
        print "  use_x_forwarded_for: true"
        print "  trusted_proxies:"
        print "    - 192.168.0.0/16"
        print "    - 10.0.0.0/8"
        print "    - 172.16.0.0/12"
        print "    - 192.168.65.0/24"
        print "    - 169.254.0.0/16"
        print "    - 0.0.0.0/0"
        print "    - ::/0"
        done = 1
      }
    ' "$cfg" > "${cfg}.tmp" && mv "${cfg}.tmp" "$cfg"
  else
    cat >> "$cfg" <<'EOF'

http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 192.168.0.0/16
    - 10.0.0.0/8
    - 172.16.0.0/12
    - 192.168.65.0/24
    - 169.254.0.0/16
    - 0.0.0.0/0
    - ::/0
EOF
  fi
fi
exec /init "$@"
