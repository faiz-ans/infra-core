#!/usr/bin/env bash
# Site secret helpers. Sourced by core.sh. Writes /etc/materia/site.env.
# Requires: prompt, prompt_secret, rand, quote_s (or defines fallbacks).

: "${KOMODO_DIR:=/etc/materia}"
: "${KOMODO_CORE_CONFIG:=${KOMODO_DIR}/site.env}"
: "${ANSWERS:=${KOMODO_DIR}/bootstrap-answers.env}"

_komodo_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_komodo_repo_root="$(cd "${_komodo_lib_dir}/../.." && pwd)"
_komodo_topology="${KOMODO_TOPOLOGY:-${_komodo_repo_root}/MANIFEST.toml}"
_komodo_fragments="${KOMODO_FRAGMENTS:-/dev/null}"
_komodo_site_vars_py="${_komodo_lib_dir}/komodo-site-vars.py"

if ! declare -F prompt >/dev/null 2>&1; then
  prompt() {
    local var="$1" message="$2" default="${3:-}" value
    if [[ -n "${default}" ]]; then
      read -r -p "${message} [${default}]: " value
      value="${value:-${default}}"
    else
      read -r -p "${message}: " value
    fi
    printf -v "${var}" '%s' "${value}"
  }
fi
if ! declare -F prompt_secret >/dev/null 2>&1; then
  prompt_secret() {
    local var="$1" message="$2" value
    read -r -s -p "${message}: " value
    echo
    printf -v "${var}" '%s' "${value}"
  }
fi
if ! declare -F rand >/dev/null 2>&1; then
  rand() { openssl rand -hex 24; }
fi
if ! declare -F quote_s >/dev/null 2>&1; then
  quote_s() { printf "%s" "$1" | sed "s/'/'\\\\''/g"; }
fi

komodo_needed_var_lines() {
  if [[ -f "${_komodo_site_vars_py}" && -f "${_komodo_topology}" && -d "${_komodo_fragments}" ]]; then
    python3 "${_komodo_site_vars_py}" \
      --topology "${_komodo_topology}" \
      --fragments "${_komodo_fragments}"
    return
  fi
  cat <<'EOF'
DOMAIN	prompt	Public/LAN domain (no scheme)
TZ	default	America/Los_Angeles
NAS_LAN_IP	prompt	LAN IP of this host (Core)
SURFACE_UPSTREAM	prompt	LAN IP of surface (Windows TV PC)
DATA_ROOT	fixed	${DATA_ROOT}
PUID	default	1000
PGID	default	1000
WG_HOST	prompt	Public DNS name for WireGuard (WAN)
CORE_SERVER	default	core
AUTHELIA_SESSION_SECRET	generate
AUTHELIA_STORAGE_ENCRYPTION_KEY	generate
AUTHELIA_OIDC_HMAC_SECRET	generate
OIDC_CLIENT_SECRET	generate
PIHOLE_WEBPASSWORD	secret	Pi-hole web password
WG_UI_PASSWORD	generate
VAULTWARDEN_ADMIN_TOKEN	generate
OPENCLOUD_ADMIN_PASSWORD	secret	OpenCloud admin password
NUT_REMOTE_PASSWORD	generate
RESTIC_PASSWORD	secret	Restic repo password
EOF
}

# Ensure one KEY is set in the environment according to MODE/EXTRA.
komodo_ensure_var() {
  local key="$1" mode="$2" extra="${3:-}"
  local cur="${!key-}"
  # Treat unset as empty; allow explicitly empty for empty/fixed.
  if [[ -n "${cur}" ]]; then
    return 0
  fi
  case "${mode}" in
    prompt)
      if [[ "${key}" == "NAS_LAN_IP" && -z "${extra}" ]]; then
        extra="LAN IP of this host (Core)"
      fi
      if [[ "${key}" == "NAS_LAN_IP" ]]; then
        local detected
        detected=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}' || true)
        prompt "${key}" "${extra}" "${detected}"
      else
        prompt "${key}" "${extra}"
      fi
      ;;
    secret)
      prompt_secret "${key}" "${extra}"
      ;;
    generate)
      printf -v "${key}" '%s' "$(rand)"
      echo "Generated ${key}"
      ;;
    default)
      printf -v "${key}" '%s' "${extra}"
      ;;
    empty)
      printf -v "${key}" '%s' ""
      ;;
    fixed)
      if [[ "${extra}" == '${DATA_ROOT}' ]]; then
        printf -v "${key}" '%s' "${DATA_ROOT}"
      else
        printf -v "${key}" '%s' "${extra}"
      fi
      ;;
    *)
      echo "Unknown mode ${mode} for ${key}" >&2
      return 1
      ;;
  esac
}

# Prompt/generate every key required by current topology (skips already set).
komodo_ensure_site_vars() {
  local key mode extra
  while IFS=$'\t' read -r key mode extra; do
    [[ -n "${key}" ]] || continue
    komodo_ensure_var "${key}" "${mode}" "${extra}"
  done < <(komodo_needed_var_lines)
}

# Write only currently needed keys into [secrets], preserving other existing keys.
komodo_write_core_secrets() {
  local tmp existing_keys=()
  tmp="$(mktemp)"
  local key mode extra val

  if [[ -f "${KOMODO_CORE_CONFIG}" ]]; then
    while IFS= read -r line; do
      if [[ "${line}" =~ ^([A-Z0-9_]+)[[:space:]]*=[[:space:]]*\"(.*)\"[[:space:]]*$ ]]; then
        existing_keys+=("${BASH_REMATCH[1]}")
        # shellcheck disable=SC2086
        printf -v "${BASH_REMATCH[1]}" '%s' "${BASH_REMATCH[2]}"
      fi
    done < <(awk '/^\[secrets\]/{p=1;next} /^\[/{p=0} p && /=/{print}' "${KOMODO_CORE_CONFIG}")
  fi

  {
    echo 'title = "infra-core"'
    echo '[secrets]'
    while IFS=$'\t' read -r key mode extra; do
      [[ -n "${key}" ]] || continue
      val="${!key-}"
      # Escape backslash and quotes for TOML basic strings
      val="${val//\\/\\\\}"
      val="${val//\"/\\\"}"
      printf '%s = "%s"\n' "${key}" "${val}"
    done < <(komodo_needed_var_lines)
  } > "${tmp}"

  mkdir -p "$(dirname "${KOMODO_CORE_CONFIG}")"
  mv "${tmp}" "${KOMODO_CORE_CONFIG}"
  chmod 600 "${KOMODO_CORE_CONFIG}"
}

# Persist answers for keys that are set (dynamic).
komodo_save_answers() {
  local old key mode extra val
  old=$(umask)
  umask 077
  {
    echo "# Generated by bootstrap; do not commit."
    while IFS=$'\t' read -r key mode extra; do
      [[ -n "${key}" ]] || continue
      val="${!key-}"
      printf "%s='%s'\n" "${key}" "$(quote_s "${val}")"
    done < <(komodo_needed_var_lines)
    # Always keep DATA_ROOT if set outside the list edge cases
    if [[ -n "${DATA_ROOT:-}" ]]; then
      printf "DATA_ROOT='%s'\n" "$(quote_s "${DATA_ROOT}")"
    fi
  } > "${ANSWERS}"
  umask "${old}"
}
