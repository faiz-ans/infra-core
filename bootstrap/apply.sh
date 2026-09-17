#!/usr/bin/env bash
# Install catalog Quadlets for this host. No Materia required.
#
#   sudo bash bootstrap/apply.sh --role core-bootstrap
#   sudo bash bootstrap/apply.sh                 # all roles in [Hosts.<hostname>]
#   sudo bash bootstrap/apply.sh --role core-full
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

SITE_ENV="${SITE_ENV:-/etc/infra-core/site.env}"
PILOT="${PILOT_USER:-pilot}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
MANIFEST="${MANIFEST:-${REPO_ROOT}/MANIFEST.toml}"
HOST="$(hostname -s)"
ROLE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --role)
      ROLE="${2:-}"
      shift 2
      ;;
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      echo "Usage: sudo bash bootstrap/apply.sh [--role NAME] [--host NAME]"
      exit 1
      ;;
  esac
done

if [[ ! -f "${SITE_ENV}" ]]; then
  echo "Missing ${SITE_ENV}. Run bootstrap/core.sh first."
  exit 1
fi
if [[ ! -f "${MANIFEST}" ]]; then
  echo "Missing ${MANIFEST}."
  exit 1
fi
if ! command -v envsubst >/dev/null 2>&1; then
  echo "envsubst not found (package gettext-base)."
  exit 1
fi

# shellcheck disable=SC1090
set -a
source "${SITE_ENV}"
set +a
# Homepage v1+ exact-matches Host. Caddy https_port 8443 and leftover
# Alt-Svc clients send dash.${DOMAIN}:8443; :443 lan-bind sends no port.
# Always set this at apply — a non-empty site.env missing :8443 still 400s.
if [[ -n "${DOMAIN:-}" ]]; then
  HOMEPAGE_ALLOWED_HOSTS="dash.${DOMAIN},dash.${DOMAIN}:443,dash.${DOMAIN}:8443,homepage.${DOMAIN}"
  export HOMEPAGE_ALLOWED_HOSTS
fi

# Site-network gateway (Homepage scrape of host-net PeaNUT). Netavark default
# is 10.89.0.1 when inspect cannot run yet (first apply, before site exists).
SITE_NET_GATEWAY="$(python3 - "${PILOT}" <<'PY'
import json, os, subprocess, sys
pilot = sys.argv[1]
uid = subprocess.check_output(["id", "-u", pilot], text=True).strip()
env = os.environ.copy()
env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
r = subprocess.run(
    ["sudo", "-u", pilot, "--preserve-env=XDG_RUNTIME_DIR", "podman", "network", "inspect", "site"],
    capture_output=True, text=True, env=env,
)
if r.returncode != 0:
    sys.exit(0)
try:
    data = json.loads(r.stdout)
except json.JSONDecodeError:
    sys.exit(0)
nets = data if isinstance(data, list) else [data]
for n in nets:
    for key in ("subnets", "Subnets"):
        for s in n.get(key) or []:
            gw = s.get("gateway") or s.get("Gateway")
            if gw:
                print(gw)
                sys.exit(0)
PY
)"
if [[ -z "${SITE_NET_GATEWAY}" ]]; then
  SITE_NET_GATEWAY="10.89.0.1"
fi
export SITE_NET_GATEWAY

mapfile -t COMPONENTS < <(python3 - "${MANIFEST}" "${HOST}" "${ROLE}" <<'PY'
import re, sys
path, host, role = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(path, encoding="utf-8").read()

def parse_lists(prefix):
    found = {}
    for m in re.finditer(r'\[%s\.([^\]]+)\]' % prefix, text):
        name = m.group(1).strip()
        rest = text[m.end():]
        nxt = re.search(r'\n\[', rest)
        block = rest[: nxt.start()] if nxt else rest
        cm = re.search(r'Components\s*=\s*\[(.*?)\]', block, re.S)
        rm = re.search(r'Roles\s*=\s*\[(.*?)\]', block, re.S)
        def items(blob):
            if not blob:
                return []
            return re.findall(r'"([^"]+)"', blob)
        found[name] = {"components": items(cm.group(1) if cm else ""), "roles": items(rm.group(1) if rm else "")}
    return found

roles = parse_lists("Roles")
hosts = parse_lists("Hosts")
wanted = []
if role:
    if role not in roles:
        sys.stderr.write("Unknown role %s\n" % role)
        sys.exit(1)
    wanted = roles[role]["components"]
else:
    if host not in hosts:
        sys.stderr.write("No [Hosts.%s] in MANIFEST.toml (hostname is %s).\n" % (host, host))
        sys.exit(1)
    for r in hosts[host]["roles"]:
        wanted.extend(roles.get(r, {}).get("components", []))
seen = set()
out = []
for c in wanted:
    if c not in seen:
        seen.add(c)
        out.append(c)
print("\n".join(out))
PY
)

if [[ ${#COMPONENTS[@]} -eq 0 ]]; then
  echo "No components to apply."
  exit 1
fi

SYSTEM_COMPONENTS="scrutiny wireguard-data"
USER_QUADLET="/home/${PILOT}/.config/containers/systemd"
SYS_QUADLET="/etc/containers/systemd"
install -d -m 0755 "${SYS_QUADLET}"
install -d -m 0755 "${USER_QUADLET}"
chown -R "${PILOT}:${PILOT}" "/home/${PILOT}/.config/containers"

is_system() {
  case " ${SYSTEM_COMPONENTS} " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

# Files Authelia/Homepage/Caddy template themselves — copy, do not envsubst.
skip_subst() {
  local base="$1"
  case "${base}" in
    Caddyfile|configuration.yml|*.yml.template) return 0 ;;
  esac
  case "${base}" in
    services.yaml|widgets.yaml|bookmarks.yaml|settings.yaml|custom.css|custom.js) return 0 ;;
  esac
  return 1
}

subst_keys() {
  local k keys=()
  while IFS= read -r k; do
    [[ -n "${k}" ]] && keys+=("\$${k}")
  done < <(awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print $1}' "${SITE_ENV}")
  keys+=("\$COMPONENT_DIR")
  keys+=("\$SITE_NET_GATEWAY")
  printf '%s' "${keys[*]}"
}

ENVSUBST_KEYS="$(subst_keys)"

install_component() {
  local name="$1"
  local src="${REPO_ROOT}/components/${name}"
  local dest
  if [[ ! -d "${src}" ]]; then
    echo "skip ${name}: no components/${name}"
    return 0
  fi
  if is_system "${name}"; then
    dest="${SYS_QUADLET}/${name}"
  else
    dest="${USER_QUADLET}/${name}"
  fi
  install -d -m 0755 "${dest}"
  export COMPONENT_DIR="${dest}"
  # Catalog moved kube→container: drop leftover Quadlet files so start_unit
  # does not keep using the old .kube unit.
  if [[ -f "${src}/${name}.container" && ! -f "${src}/${name}.kube" ]]; then
    rm -f "${dest}/${name}.kube" "${dest}/pod.yaml"
  fi
  local f rel out
  while IFS= read -r -d '' f; do
    rel="${f#${src}/}"
    case "${rel}" in
      MANIFEST.toml|README.md) continue ;;
    esac
    out="${dest}/${rel}"
    mkdir -p "$(dirname "${out}")"
    if skip_subst "$(basename "${f}")" || [[ "${rel}" == config/* ]] || [[ "${rel}" == images/* ]]; then
      cp -a "${f}" "${out}"
    elif grep -q '\${' "${f}" 2>/dev/null; then
      # shellcheck disable=SC2086
      envsubst "${ENVSUBST_KEYS}" <"${f}" >"${out}"
    else
      cp -a "${f}" "${out}"
    fi
  done < <(find "${src}" -type f -print0)
  if is_system "${name}"; then
    chown -R root:root "${dest}"
  else
    chown -R "${PILOT}:${PILOT}" "${dest}"
  fi
  echo "installed ${name} -> ${dest}"
}

for c in "${COMPONENTS[@]}"; do
  install_component "${c}"
done

# Rootless keep-id units must own their DATA_ROOT binds (Authelia JWKS,
# OpenCloud posix/config). Remounted Docker trees are root-owned.
if [[ -n "${DATA_ROOT:-}" ]]; then
  for _c in "${COMPONENTS[@]}"; do
    case "${_c}" in
      authelia)
        if [[ -d "${DATA_ROOT}/system/authelia" ]]; then
          chown -R "${PUID:-1000}:${PGID:-1000}" "${DATA_ROOT}/system/authelia"
        fi
        ;;
      opencloud)
        chown "${PUID:-1000}:${PGID:-1000}" "${DATA_ROOT}/system/opencloud" \
          "${DATA_ROOT}/system/opencloud/projects" 2>/dev/null || true
        chown -R "${PUID:-1000}:${PGID:-1000}" \
          "${DATA_ROOT}/system/opencloud/config" \
          "${DATA_ROOT}/system/opencloud/data" \
          "${DATA_ROOT}/system/opencloud/posix" \
          "${DATA_ROOT}/system/opencloud/radicale" 2>/dev/null || true
        ;;
      peanut)
        if [[ -d "${DATA_ROOT}/system/peanut" && -f "${USER_QUADLET}/peanut/settings.yml" ]]; then
          chown "${PUID:-1000}:${PGID:-1000}" "${DATA_ROOT}/system/peanut"
          install -m 600 -o "${PUID:-1000}" -g "${PGID:-1000}" \
            "${USER_QUADLET}/peanut/settings.yml" \
            "${DATA_ROOT}/system/peanut/settings.yml"
        fi
        # Drop the previous kube pod so it cannot keep :8092 or leave a
        # second PeaNUT on host :8080 (Caddy's port).
        XDG_RUNTIME_DIR="/run/user/$(id -u "${PILOT}")" \
          sudo -u "${PILOT}" --preserve-env=XDG_RUNTIME_DIR \
          podman rm -f peanut-peanut 2>/dev/null || true
        XDG_RUNTIME_DIR="/run/user/$(id -u "${PILOT}")" \
          sudo -u "${PILOT}" --preserve-env=XDG_RUNTIME_DIR \
          podman pod rm -f peanut 2>/dev/null || true
        ;;
    esac
  done
fi

systemctl daemon-reload
if systemctl --machine="${PILOT}@" --user daemon-reload; then
  :
else
  echo "user daemon-reload failed (linger ${PILOT}?); system units still reloaded."
fi

start_unit() {
  local name="$1" unit=""
  local dest
  if is_system "${name}"; then
    dest="${SYS_QUADLET}/${name}"
  else
    dest="${USER_QUADLET}/${name}"
  fi
  if [[ "${name}" == "wireguard-data" ]]; then
    echo "${name}: host wg-quick@wg0 (see components/wireguard-data/README.md); not started here."
    return 0
  fi
  if [[ "${name}" == "site-network" ]]; then
    unit="site-network.service"
  elif [[ -f "${dest}/${name}.kube" ]]; then
    unit="${name}.service"
  elif [[ -f "${dest}/${name}.container" ]]; then
    unit="${name}.service"
  elif [[ -f "${dest}/site.network" ]]; then
    unit="site-network.service"
  else
    echo "${name}: no Quadlet unit to start"
    return 0
  fi
  # Generated Quadlet units cannot be `enable`d. Linger + WantedBy=default.target
  # is what survives reboot; restart picks up a rewritten Quadlet.
  if is_system "${name}"; then
    systemctl restart "${unit}" || echo "warn: systemctl restart ${unit} failed"
  else
    systemctl --machine="${PILOT}@" --user restart "${unit}" || echo "warn: user restart ${unit} failed"
  fi
}

for c in "${COMPONENTS[@]}"; do
  start_unit "${c}"
done

echo "apply.sh done: ${COMPONENTS[*]}"
echo "Next (Core bootstrap): wait until :15353 :8080 :8443 listen, then sudo bash bootstrap/core/core-lan-bind.sh --enable"
