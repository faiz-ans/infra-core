#!/bin/bash
# Nextcloud extra config (*.config.php). Git-bind, not an NFS overlay.
# overwrite* so Caddy https://nextcloud.${DOMAIN} is the public URL.
set -e
dest=/config/www/nextcloud/config
mkdir -p "${dest}"
host="nextcloud.${DOMAIN:-home.lan}"
cat > "${dest}/zzz-infra.config.php" <<EOF
<?php
\$CONFIG = array (
  'trusted_proxies' => array (
    '192.168.0.0/16',
    '10.0.0.0/8',
    '172.16.0.0/12',
    '192.168.65.0/24',
    '127.0.0.1',
  ),
  'overwriteprotocol' => 'https',
  'overwritehost' => '${host}',
  'overwrite.cli.url' => 'https://${host}',
);
EOF
