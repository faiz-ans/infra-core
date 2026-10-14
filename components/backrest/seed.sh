#!/bin/sh
set -eu
# First start only. Later edits belong to the Backrest UI.
if [ ! -s /config/config.json ]; then
  escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
  password=$(escape "${RESTIC_PASSWORD}")
  rest_password=$(escape "${RESTIC_REST_PASSWORD}")
  if [ -s /sources.list ]; then
    plan_paths=$(awk 'BEGIN { sep = "" } NF { printf "%s\"%s\"", sep, $0; sep = "," }' /sources.list)
  else
    plan_paths='"/data/appdata","/data/groups","/data/users"'
  fi
  cat > /config/config.json <<EOF
{
  "modno": 1,
  "version": 6,
  "instance": "${BACKUP_HOST}",
  "auth": { "disabled": true },
  "repos": [
    {
      "id": "site",
      "uri": "${RESTIC_REPOSITORY}",
      "password": "${password}",
      "autoInitialize": true,
      "env": [
        "RESTIC_REST_USERNAME=restic",
        "RESTIC_REST_PASSWORD=${rest_password}"
      ],
      "prunePolicy": {
        "schedule": { "cron": "30 3 * * 0", "clock": "CLOCK_LOCAL" },
        "maxUnusedPercent": 10
      }
    }
  ],
  "plans": [
    {
      "id": "site-data",
      "repo": "site",
      "paths": [${plan_paths}],
      "excludes": ["/data/appdata/restic", "/data/appdata/backrest"],
      "schedule": { "cron": "0 3 * * *", "clock": "CLOCK_LOCAL" },
      "retention": {
        "policyTimeBucketed": { "daily": 7, "weekly": 4, "monthly": 12 }
      }
    }
  ]
}
EOF
fi
exec /docker-entrypoint /backrest
