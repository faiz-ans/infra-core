#!/bin/sh
set -eu
# Homepage's widget calls /api/status-page/home. Kuma 1.23 never answers
# when that slug is missing, so the tile stays on its pulsing skeleton.
# Create the empty page once. Monitors are still added in the Kuma UI.
db=/app/data/kuma.db
if [ -f "$db" ]; then
  count=$(sqlite3 "$db" "SELECT count(*) FROM status_page WHERE slug='home';")
  if [ "$count" = "0" ]; then
    sqlite3 "$db" "INSERT INTO status_page (slug, title, icon, theme) VALUES ('home', 'Home', '/icon.svg', 'light');"
  fi
fi
cd /app
exec /usr/bin/dumb-init -- extra/entrypoint.sh node server/server.js
