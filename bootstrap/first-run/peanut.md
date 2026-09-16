# PeaNUT first-run

PeaNUT is the HTTP front for host NUT (CyberPower ST625U). Homepage’s UPS tile scrapes `http://peanut:8080` on `edge`. Browser: `https://ups.<DOMAIN>` (alias `peanut.`). Authelia forward-auth is on `ups.` and `peanut.` (any logged-in Authelia user). Homepage still scrapes internally (not through Caddy).

PeaNUT’s own login is off (`AUTH_DISABLED`). NUT remote user is **`peanut`**; password is attribute `NUT_REMOTE_PASSWORD`. Host NUT must have **Remote monitoring** on so `upsd` listens beyond localhost (`bootstrap/omv/omv-nut.sh`).

No LAN publish of PeaNUT. Do not WAN-forward TCP **3493**.

## 1. NUT remote user (existing Core)

NUT is already running. Enable remote monitoring with the site password:

```text
# NUT_REMOTE_PASSWORD is in /etc/materia/site.env (set by core.sh)
sudo bash bootstrap/omv/omv-nut.sh
```

`omv-nut.sh` reads `NUT_REMOTE_PASSWORD` from `/etc/materia/site.env` (or generates one into answers). `upsc ups@127.0.0.1` still works. From Podman, NUT is `host.containers.internal:3493`.

```text
sudo mkdir -p "${DATA_ROOT}/system/peanut"
sudo chown 1000:1000 "${DATA_ROOT}/system/peanut"
```

If this site already ran `core.sh` before PeaNUT, `data-root-prep.sh` also creates that dir.

## 2. Deploy

Commit and push. Wait for Materia, then re-apply **authelia**, **caddy**, and **homepage**.

```text
podman ps --filter name=peanut --format "table {{.Names}}\t{{.Status}}"
```

You want `peanut` **Up**. It must **not** publish 8080 on the LAN.

Open **`https://ups.<DOMAIN>`**. Homepage UPS tile should show charge, load, and status (`OL`).

## If it fails

| Symptom | What to do |
|---|---|
| Widget API error / empty | re-apply (Materia / systemd) **homepage**. `podman exec homepage wget -S -O- --timeout=5 http://peanut:8080` |
| `ups.<DOMAIN>` 403 | See **403 diagnosis** below. re-apply (Materia / systemd) **authelia** and **caddy** (not just Restart). `ups.` must appear in the household `group:users` rule in the live Authelia config |
| `ups.<DOMAIN>` does not load | re-apply (Materia / systemd) **caddy**. PeaNUT Up on `edge`. `podman exec caddy wget -S -O- --timeout=5 http://peanut:8080/api/ping` |
| PeaNUT “no devices” / NUT timeout | Remote monitoring off, or password mismatch. Re-run `omv-nut.sh` after sync so OMV `remoteuser=peanut` matches `NUT_REMOTE_PASSWORD`. `grep LISTEN /etc/nut/upsd.conf` should not be localhost-only |
| Click opens `http://peanut:8080` | re-apply (Materia / systemd) **homepage** (href is `https://ups.<DOMAIN>`) |
| EACCES `/config` | `chown 1000:1000 ${DATA_ROOT}/system/peanut` then re-apply (Materia / systemd) **peanut** |

## 403 diagnosis

PeaNUT v6 has `trustHost: true` baked in and skips auth when `AUTH_DISABLED=true`, so a browser **403** is usually **Authelia forward-auth** (logged in, but ACL deny) or a **stale Caddyfile/Authelia config** (Restart does not reload ConfigMaps — use **re-apply (Materia / systemd)**).

On Core (replace `home.lan` if your `DOMAIN` differs):

```text
DOMAIN=home.lan

# Live Authelia ACL — ups./peanut. must be on the pdf/it/translate household rule
sudo podman exec authelia cat /config/configuration.yml | sed -n '/access_control:/,/session:/p' | grep -E 'ups\.|peanut\.|pdf\.'

# PeaNUT direct on edge (bypasses Authelia) — expect HTTP 200 and body "pong"
sudo podman exec caddy wget -S -O- --timeout=5 http://peanut:8080/api/ping 2>&1 | head -15

# PeaNUT env (image has no printenv)
sudo podman inspect peanut --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^(AUTH_|WEB_|NUT_)'

# Reload https://ups.<DOMAIN> in the browser, then:
sudo podman logs authelia --since 2m 2>&1 | tail -30
```

| Result | Meaning |
|---|---|
| `/api/ping` → 200 `pong`, browser still 403 | Authelia or Caddy gate. Confirm live config (first command). re-apply (Materia / systemd) **authelia** + **caddy**. Log in at `https://auth.<DOMAIN>` first, then retry `ups.` |
| `/api/ping` → 403 | PeaNUT itself. re-apply (Materia / systemd) **peanut**; confirm `AUTH_DISABLED=true` in inspect output |
| Authelia log `Access denied` for `ups.` | Live `configuration.yml` is stale or missing `ups.` — re-apply (Materia / systemd) **authelia** |
| `grep ups` shows nothing | Authelia never picked up the catalog — re-apply (Materia / systemd) **authelia** after Materia |
