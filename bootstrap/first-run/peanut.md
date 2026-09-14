# PeaNUT first-run

PeaNUT is the HTTP front for host NUT (CyberPower ST625U). Homepage’s UPS tile scrapes `http://peanut:8080` on `edge`. Browser: `https://ups.<DOMAIN>` (alias `peanut.`). Authelia forward-auth is on `ups.` and `peanut.` (any logged-in Authelia user). Homepage still scrapes internally (not through Caddy).

PeaNUT’s own login is off (`AUTH_DISABLED`). NUT remote user is **`peanut`**; password is Komodo `NUT_REMOTE_PASSWORD`. Host NUT must have **Remote monitoring** on so `upsd` listens beyond localhost (`bootstrap/omv/omv-nut.sh`).

No LAN publish of PeaNUT. Do not WAN-forward TCP **3493**.

## 1. NUT remote user (existing Core)

NUT is already running. Enable remote monitoring with the Komodo password:

```text
sudo bash bootstrap/komodo/sync-komodo-secrets.sh
# recreate Core so [secrets] reload
cd /etc/komodo/bootstrap && sudo docker compose --env-file compose.env -f compose.yaml up -d
sudo bash bootstrap/omv/omv-nut.sh
```

`omv-nut.sh` reads `NUT_REMOTE_PASSWORD` from `/etc/komodo/core.config.toml` (or generates one into answers). `upsc ups@127.0.0.1` still works. From Docker, NUT is `host.docker.internal:3493`.

```text
sudo mkdir -p "${DATA_ROOT}/system/peanut"
sudo chown 1000:1000 "${DATA_ROOT}/system/peanut"
```

If this site already ran `core.sh` before PeaNUT, `data-root-prep.sh` also creates that dir.

## 2. Deploy

Commit and push. Wait for ResourceSync. Komodo → **Stacks** → **peanut** → **Deploy**. Redeploy **authelia**, **caddy**, and **homepage**.

```text
docker ps --filter name=peanut --format "table {{.Names}}\t{{.Status}}"
```

You want `peanut` **Up**. It must **not** publish 8080 on the LAN.

Open **`https://ups.<DOMAIN>`**. Homepage UPS tile should show charge, load, and status (`OL`).

## If it fails

| Symptom | What to do |
|---|---|
| Widget API error / empty | Redeploy **homepage**. `docker exec homepage wget -S -O- --timeout=5 http://peanut:8080` |
| `ups.<DOMAIN>` 403 | Authelia `default_policy` is deny. Redeploy **authelia** so `ups.` and `peanut.` have a `one_factor` rule. Restart is not enough if the container never re-read `configuration.yml` — use **Redeploy**. Then open `https://ups.<DOMAIN>` again (existing session is fine) |
| `ups.<DOMAIN>` does not load | Redeploy **caddy**. PeaNUT Up on `edge`. `docker exec caddy wget -S -O- --timeout=5 http://peanut:8080` |
| PeaNUT “no devices” / NUT timeout | Remote monitoring off, or password mismatch. Re-run `omv-nut.sh` after sync so OMV `remoteuser=peanut` matches `NUT_REMOTE_PASSWORD`. `grep LISTEN /etc/nut/upsd.conf` should not be localhost-only |
| Click opens `http://peanut:8080` | Redeploy **homepage** (href is `https://ups.<DOMAIN>`) |
| EACCES `/config` | `chown 1000:1000 ${DATA_ROOT}/system/peanut` then Redeploy **peanut** |
