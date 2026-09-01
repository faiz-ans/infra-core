# Frigate first-run

Frigate runs on **periphery**. Config and SQLite are a local HTPC volume (`frigate-config`). Recordings, clips, and exports are NFS `shared/cameras`. `/tmp/cache` is tmpfs. Caddy is `https://cams.<DOMAIN>` (`nvr.` and `frigate.` are aliases).

No Komodo secret. The first start prints an admin user and password in the container logs. Camera RTSP URLs stay in the volume (Frigate’s config editor), not in git. Coral / GPU / `privileged` are not in the catalog.

MQTT is a sidecar (`frigate-mqtt`) on **1883**, anonymous, LAN-only. Caddy does not proxy MQTT, RTSP (8554), or WebRTC (8555).

## 1. Storage

On Core, `shared/cameras` must exist before Deploy (NFS of a missing export path fails). Existing sites:

```text
sudo DATA_ROOT=/srv/dev-disk-by-uuid-… bash bootstrap/data-root-perms.sh
```

Do not re-run `core.sh` only for this directory.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **frigate** → **Deploy**. Redeploy **caddy** and **homepage**.

On the HTPC, allow Windows Firewall from the LAN (Caddy / Home Assistant):

| Port | Why |
|---|---|
| 8971 | UI via Caddy |
| 8554 | RTSP restream (optional) |
| 8555 tcp+udp | WebRTC live view |
| 1883 | MQTT for Home Assistant |

```text
docker ps --filter name=frigate --format "table {{.Names}}\t{{.Status}}"
docker logs frigate 2>&1 | grep -i password
```

If Caddy returns **400** (plain HTTP to HTTPS port), the volume was created with Frigate’s default TLS on. In the config editor (or the volume’s `config.yml`) set `tls.enabled: false` and restart **frigate**. The catalog seed only copies when that file is missing.

## 3. Admin and cameras

Open **`https://cams.<DOMAIN>`**. Log in with the password from the logs. Change it in the UI.

Add cameras in **Settings → Configuration** (or the Add Camera wizard). Use a low detect resolution on the first camera; this site’s detector is CPU (Docker Desktop has no Coral/GPU passthrough). Enable **record** when you want clips in the UI.

Do not put RTSP passwords in the catalog repo.

## 4. Home Assistant

In HA: **Settings → Devices & services → MQTT**. Broker host is the HTPC LAN IP (`HTPC_UPSTREAM`), port **1883**, no username. Then add the **Frigate** integration (MQTT must already work). The Frigate UI URL for the integration is `https://cams.<DOMAIN>` (or `http://<HTPC_UPSTREAM>:8971` on the LAN).

## If it fails

| Symptom | What to do |
|---|---|
| `cams.<DOMAIN>` does not load while `frigate` is Up | Redeploy **caddy**. From Core: `docker exec caddy wget -S -O- --timeout=10 http://<HTPC_UPSTREAM>:8971/ \| head` |
| Caddy 400 | `tls.enabled: false` in `/config/config.yml`, then restart |
| NFS / `cameras` mount error | Directory missing on Core, or `NFS_EXPORT` not `/shared`. Run `data-root-perms.sh`. See `bootstrap/omv-nfs.md` |
| Bus error / Frigate exits | Raise `shm_size` in compose (site edit). 256mb is sized for a couple of 720p detect streams |
| Live view works in LAN :8971 but not through Caddy | MSE/jsmpeg over the HTTPS proxy; WebRTC uses 8555 on the HTPC, not Caddy |
| HA Frigate integration empty | MQTT: from the HA container, broker must be the HTPC host:1883, not `mosquitto` (that name is only inside the Frigate stack) |
| Periphery **Not OK** after Deploy | Docker LAN overlap — `bootstrap/periphery.md` §7, then §1 Engine JSON |

Do **not** delete `shared/cameras` or the `frigate-config` volume on rollback unless you intend to wipe recordings and the admin user.
