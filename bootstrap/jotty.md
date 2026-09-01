# Jotty first-run

Jotty runs on **Core** (edge network). Notes and checklists are files under `${DATA_ROOT}/system/jotty`. Caddy is `https://notes.<DOMAIN>` (`jotty.` is an alias).

## 1. Directories

If this site already ran `core.sh` before Jotty existed, run `data-root-perms.sh` so `${PUID}` owns `system/jotty/{data,config,cache}`. Do not re-run bootstrap only for this app.

## 2. Deploy

Commit and push to the catalog origin (Gitea). Wait for ResourceSync. Komodo → **Stacks** → **jotty** → **Deploy**. Redeploy **caddy** and **homepage** so the vhost and tile exist.

On Core:

```text
docker ps --filter name=jotty --format "table {{.Names}}\t{{.Status}}"
```

You want `jotty` **Up**. It must **not** publish 3000 on the LAN.

## 3. Admin

Open **`https://notes.<DOMAIN>`**. First visit sends you to `/auth/setup`. Create the household admin there. There is no Komodo secret for Jotty.

## If it fails

| Symptom | What to do |
|---|---|
| `notes.<DOMAIN>` does not load while `jotty` is Up | Redeploy **caddy**. Then `docker exec caddy wget -S -O- --timeout=10 http://jotty:3000/ \| head` |
| Permission denied on `/app/data` | Stop the container, `chown -R ${PUID}:${PGID}` `system/jotty`, Redeploy |
