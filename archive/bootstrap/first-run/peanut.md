# PeaNUT first-run

PeaNUT is the HTTP front for host NUT (CyberPower ST625U). `core-bootstrap` apply must produce this layout with no extra steps:

| Path | Value |
|---|---|
| Unit | Quadlet `.container`, **host netns**, `UserNS=keep-id` |
| NUT | `127.0.0.1:3493` (env + `settings.yml`). User `peanut` / `NUT_REMOTE_PASSWORD` |
| Listen | `WEB_HOST=0.0.0.0` `WEB_PORT=8092` (not `127.0.0.1`, not `8080`) |
| Auth | `AUTH_DISABLED=true` `AUTH_TRUST_HOST=true` `AUTH_SECRET` set. Do **not** set `AUTH_URL` / `NEXTAUTH_URL` |
| Browser | `https://ups.<DOMAIN>` (alias `peanut.`). Caddy `reverse_proxy 127.0.0.1:8092` with `Host` / `X-Forwarded-Host` **`ups.<DOMAIN>`** (no `:8443`) |
| Homepage tile | `http://{{HOMEPAGE_VAR_HOST_LOOPBACK}}:8092` (`169.254.1.2`) `key: ups`. Not `peanut`, `127.0.0.1`, LAN IP, or `host.containers.internal` |

`apply.sh` chowns `${DATA_ROOT}/system/peanut`, envsubst-copies `settings.yml`, and removes leftover kube `peanut-peanut` / pod `peanut` so a second container cannot steal Caddy `:8080`.

Do not WAN-forward **3493** or **8092**. Authelia forward-auth is on `ups.` and `peanut.` (any logged-in user).

## Layer 0 (already in `core.sh` / prep)

```text
sudo mkdir -p "${DATA_ROOT}/system/peanut"
sudo chown 1000:1000 "${DATA_ROOT}/system/peanut"
```

`data-root-prep.sh` creates that dir. Host NUT: `sudo bash bootstrap/omv/omv-nut.sh` (`NUT_REMOTE_PASSWORD` in `/etc/infra-core/site.env`). `upsc ups@127.0.0.1` must work.

## Deploy

```text
sudo bash bootstrap/apply.sh --role core-bootstrap
```

Want `peanut` **Up**, `ss` showing `*:8092` (and Caddy `*:8080`). Open `https://ups.<DOMAIN>`. Homepage UPS tile: charge, load, **OL**.

## Do not

- `Network=site` or a second `Network=slirp4netns` / `pasta` (this Podman rejects those modes; Homepage still cannot hairpin to `192.168.x.x`)
- `WEB_HOST=127.0.0.1` (Next.js HTML hangs; API still answers)
- `WEB_PORT=8080` on host netns (takes Caddy down)
- `AUTH_URL` / `NEXTAUTH_URL` (HTML 500 / proxy loop)
- Caddy extra listener on `10.89.0.1:8093` (can fail the whole Caddy process)
- Widget `http://peanut:8080`, `http://127.0.0.1:8092`, or `http://<NAS_LAN_IP>:8092` (Homepage is on `site`; those are connection-refused or NXDOMAIN)
- Widget `http://host.containers.internal:8092` (works, but Node AAAA stalls the tile)

## If it fails

| Symptom | Cause / fix |
|---|---|
| Widget API error | Live `services.yaml` URL must be `http://169.254.1.2:8092`. From Homepage: `wget http://169.254.1.2:8092/api/ping` → `pong` |
| Widget slow, then fills | URL is the name `host.containers.internal` (AAAA wait). Use `169.254.1.2` |
| `ups.<DOMAIN>` Internal Server Error / hang | `WEB_HOST` is not `0.0.0.0`, or `AUTH_URL` is set. Direct `curl -m 15 http://127.0.0.1:8092/` must be **200** |
| `ups.<DOMAIN>` 403 | Authelia ACL, not PeaNUT. See below |
| No devices in UI | `upsc ups@127.0.0.1`. `settings.yml` HOST must be `127.0.0.1`. Re-run `omv-nut.sh` if `upsc` fails |
| Everything down / Caddy dead | Two peanuts or PeaNUT on host `:8080`. `podman rm -f peanut-peanut peanut`; `podman pod rm -f peanut`; re-apply **peanut** then **caddy** |
| EACCES `/config` | `chown 1000:1000 ${DATA_ROOT}/system/peanut` then re-apply **peanut** |
| Click opens `http://peanut:8080` | Stale Homepage href. re-apply **homepage** |

## 403 diagnosis

PeaNUT v6 skips its own login when `AUTH_DISABLED=true`. A browser **403** is Authelia (logged in, ACL deny) or a stale Caddy/Authelia file.

```text
DOMAIN=home.lan

sudo podman exec authelia cat /config/configuration.yml | sed -n '/access_control:/,/session:/p' | grep -E 'ups\.|peanut\.'

# Same host netns as Caddy. Expect 200 pong
curl -sS --max-time 5 http://127.0.0.1:8092/api/ping

podman inspect peanut --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^(AUTH_|WEB_|NUT_)'

podman logs authelia --since 2m 2>&1 | tail -30
```

| Result | Meaning |
|---|---|
| `/api/ping` → 200 `pong`, browser 403 | Authelia/Caddy. re-apply **authelia** + **caddy**. Log in at `https://auth.<DOMAIN>` first |
| `/api/ping` → 403 | PeaNUT. re-apply **peanut**; `AUTH_DISABLED=true` in inspect |
| Authelia `Access denied` for `ups.` | Live ACL missing `ups.` — re-apply **authelia** |
