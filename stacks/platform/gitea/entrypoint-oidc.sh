#!/bin/bash
# Seed Authelia after the official entrypoint brings up :3000. Same container
# (no second Gitea on the SQLite file — that crash-loops the server).
set +e
(
  for _ in $(seq 1 60); do
    if wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/ >/dev/null 2>&1; then
      bash /seed-oidc.sh
      exit 0
    fi
    sleep 5
  done
  echo "gitea-oidc: server never became ready; skip"
) &
exec /usr/bin/entrypoint "$@"
