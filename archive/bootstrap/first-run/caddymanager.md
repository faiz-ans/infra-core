# CaddyManager first-run (experiment)

CaddyManager is a web UI for this site’s Caddy admin API. The component ships **Stopped** until you opt in (`Stopped = true` in `components/caddymanager/MANIFEST.toml`). GitOps still owns [`components/caddy/Caddyfile`](../../components/caddy/Caddyfile). A Caddy re-apply reloads that file and **drops** UI-only config.

Caddy is `https://traffic.<DOMAIN>` (`caddymanager.` 301 there). Authelia forward-auth is on the vhost (`admins` / **faiz** only), then CaddyManager’s own login.

The admin API listens on `0.0.0.0:2019` in Caddy’s host netns. CaddyManager reaches it at `http://127.0.0.1:2019` (same pod network namespace as the UI backend when Caddy is host-net).

## 1. Opt in

1. Set `CADDYMANAGER_JWT_SECRET` in `attributes/core.age`.
2. Clear `Stopped` / `Disabled` on the caddymanager component (host override or edit the component MANIFEST).
3. `mkdir -p ${DATA_ROOT}/system/caddymanager` and `apply.sh`.

## 2. Check

```text
podman ps --filter name=caddymanager --format "table {{.Names}}\t{{.Status}}"
```

You want frontend and backend **Up**. They must **not** publish 80 or 3000 on the LAN (localhost 8086 only).
