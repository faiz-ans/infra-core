#!/usr/bin/env bash
# After editing topology.inc (and regenerating ResourceSync TOML), ingest any
# newly required Komodo [secrets] into /etc/komodo/core.config.toml without
# using the Komodo UI.
#
#   sudo bash bootstrap/sync-komodo-secrets.sh
#   # or from a clone:
#   sudo KOMODO_TOPOLOGY=/path/to/topology.inc bash bootstrap/sync-komodo-secrets.sh
#
# Existing secrets are kept. Only missing keys for enabled stacks are prompted
# or auto-generated. Then recreate Core so Komodo reloads [secrets]:
#   cd /etc/komodo/bootstrap && docker compose --env-file compose.env -f compose.yaml up -d
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOMODO_DIR="${KOMODO_DIR:-/etc/komodo}"
ANSWERS="${KOMODO_DIR}/bootstrap-answers.env"
KOMODO_CORE_CONFIG="${KOMODO_DIR}/core.config.toml"

# shellcheck source=komodo-secrets.sh
source "${SCRIPT_DIR}/komodo-secrets.sh"

if [[ -f "${ANSWERS}" ]]; then
  # shellcheck disable=SC1090
  source "${ANSWERS}"
  echo "Loaded ${ANSWERS}"
fi

# Prefill from current core.config.toml so we do not re-prompt known keys.
if [[ -f "${KOMODO_CORE_CONFIG}" ]]; then
  while IFS= read -r line; do
    if [[ "${line}" =~ ^([A-Z0-9_]+)[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$ ]]; then
      k="${BASH_REMATCH[1]}"
      v="${BASH_REMATCH[2]}"
      v="${v//\\\"/\"}"
      v="${v//\\\\/\\}"
      if [[ -z "${!k-}" ]]; then
        printf -v "${k}" '%s' "${v}"
      fi
    fi
  done < <(awk '/^\[secrets\]/{p=1;next} /^\[/{p=0} p && /=/{print}' "${KOMODO_CORE_CONFIG}")
fi

echo "Ensuring secrets for topology: ${_komodo_topology}"
komodo_ensure_site_vars
komodo_save_answers
komodo_write_core_secrets

echo
echo "Updated ${KOMODO_CORE_CONFIG}"
echo "Reload Komodo Core to pick up [secrets]:"
echo "  docker compose --env-file ${KOMODO_DIR}/bootstrap/compose.env -f ${KOMODO_DIR}/bootstrap/compose.yaml up -d"
echo "Then Redeploy stacks that use the new keys."
