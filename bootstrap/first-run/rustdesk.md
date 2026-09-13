# RustDesk first-run

RustDesk OSS ID (`hbbs`) and relay (`hbbr`) run on **Core** with **host networking**. They are not on the edge Docker network. Caddy does **not** proxy the RustDesk protocol.

Off-LAN remote desktop is **wg-easy first**, then the same ID/relay as on the LAN. The router must keep forwarding **UDP 51820 only**. Do **not** forward TCP/UDP 21115–21119. Do not enable UPnP for those ports.

## 1. Directories

If this site already ran `core.sh` before RustDesk existed, run `data-root-perms.sh` so `system/rustdesk` exists. No Komodo secret.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **rustdesk** → **Deploy**. Redeploy **caddy** and **homepage** if you want `https://desk.<DOMAIN>` (a text hint, not a desktop session).

On Core:

```text
docker ps --filter name=hbb --format "table {{.Names}}\t{{.Status}}"
```

You want `hbbs` and `hbbr` **Up**.

Public key (clients need this):

```text
sudo cat /srv/dev-disk-by-uuid-d6e267fd-109f-4971-bfb1-26b3d99e0d47/system/rustdesk/id_ed25519.pub
```

Use this site’s `DATA_ROOT` if it is not that path.

## 3. Clients

In the RustDesk client, set ID server and relay server to **`desk.<DOMAIN>`** (Pi-hole / WireGuard DNS → Core LAN IP) or to **`NAS_LAN_IP`**. Paste the public key. Leave the API server empty (OSS has no web console).

Test on the LAN first. Then: connect a phone to wg-easy on cellular, confirm `desk.<DOMAIN>` resolves to the Core LAN IP, and connect again. If that works without any new router forwards, the deploy is correct.

`https://desk.<DOMAIN>` only tells you to use the native client.

## If it fails

| Symptom | What to do |
|---|---|
| Client cannot register | Confirm UDP 21116 is not blocked on the LAN; hbbs must be host-net; key matches `id_ed25519.pub` |
| Works on LAN, fails on cellular | Connect wg-easy first. Do not open 21116 on the WAN |
| Relay shows a Docker IP | Catalog must pass `hbbs -r ${NAS_LAN_IP}:21117`. Redeploy **rustdesk** |
