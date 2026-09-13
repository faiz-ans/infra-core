# Uptime Kuma first-run

Uptime Kuma runs on **Core** (edge network) so HTPC downtime is still visible. Caddy is `https://up.<DOMAIN>` (`kuma.` / `uptime.` / `status.` 301 there). Kuma has its own login. `/api/push/*` is **not** behind Authelia (restic and other push monitors need it).

No Komodo secret for the app. Optional `UPTIME_KUMA_PUSH_URL` is for the restic client (empty until you create a Push monitor).

## 1. Directories (existing Core)

If this site already ran `core.sh` before Kuma existed, run `data-root-perms.sh` so `system/uptime-kuma` exists.

## 2. Deploy

Commit and push. Wait for ResourceSync. Komodo → **Stacks** → **uptime-kuma** → **Deploy**. Redeploy **caddy** and **homepage**.

On Core:

```text
docker ps --filter name=uptime-kuma --format "table {{.Names}}\t{{.Status}}"
```

You want `uptime-kuma` **Up**. It must **not** publish 3001 on the LAN.

Open **`https://up.<DOMAIN>`**. Create the admin account.

## 3. Status page (Homepage widget)

The Homepage tile expects a public status page whose slug is **`home`**.

In Kuma: **Status Pages** → add one → slug `home` → add the monitor groups you care about. Until that page exists, the Homepage widget shows an API error; the href still works.

## 4. Monitors

Create what you actually want to watch. A useful first set:

| Type | What | Notes |
|---|---|---|
| HTTP(s) | `https://dash.<DOMAIN>`, `https://cloud.<DOMAIN>`, `https://ops.<DOMAIN>`, … | Through Caddy. Expect the internal CA; Kuma may need “Ignore TLS error” for `tls internal` |
| HTTP(s) | `https://watch.<DOMAIN>` (and other HTPC apps) | Down means HTPC or that stack |
| Push | NAS restic backup | Copy the Push URL. See below |
| Push | Optional HTPC heartbeat | A Windows task `curl`s the URL on a schedule |

Do not point HTTP monitors at Docker-internal names (`http://glances:61208`); Kuma is on `edge` and can reach Core containers by name if you want that, but Caddy URLs match what you click.

## 5. Push URL for restic

1. In Kuma, add a **Push** monitor (heartbeat). Copy the URL.
2. For the NAS restic container, rewrite the host to the edge name, e.g. `http://uptime-kuma:3001/api/push/<token>?status=up&msg=OK&ping=`.
3. Komodo **Settings** → **`UPTIME_KUMA_PUSH_URL`**. Enable **restic** (`deploy = true`) if it is still off, then `sudo bash bootstrap/sync-komodo-secrets.sh` (or set the key in the UI) and Redeploy **restic**.

`backup.sh` pings that URL after a successful `restic backup`. An empty value skips the ping. A failed ping does not fail the backup.

The restic image talks to Kuma over HTTP on `edge` only if you use `http://uptime-kuma:3001/...`. The public `https://up.<DOMAIN>/api/push/...` URL also works (`wget --no-check-certificate`).

## If it fails

| Symptom | What to do |
|---|---|
| `up.<DOMAIN>` does not load while `uptime-kuma` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://uptime-kuma:3001/ \| head` |
| Live UI does not update | Caddy `reverse_proxy` already upgrades WebSockets. Hard-refresh. Confirm you are on `up.` not `status.` (that alias 301s) |
| Homepage widget API error | Status page slug must be exactly `home`. Widget URL is `http://uptime-kuma:3001` (edge), not `https://up.<DOMAIN>` |
| Push monitor goes down | Token/URL mismatch. From Core: `docker exec restic wget -S -O- --timeout=10 --no-check-certificate "$UPTIME_KUMA_PUSH_URL"` after restic has the env |
| HTTP monitor TLS error | `tls internal`. Enable ignore-TLS on that monitor, or install the Caddy root in Kuma (usually not worth it) |
