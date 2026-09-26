# Transmute first-run

Transmute runs on **mantle**. Uploads, SQLite, and conversion output are a local WSL volume (`transmute-data`). Caddy is `https://convert.<DOMAIN>` (`transmute.` is an alias).

## 1. Secrets (existing Core)

If this site already ran `core.sh` before Transmute existed, add the key in `/etc/infra-core/site.env`. Do not re-run bootstrap only for this.

1. Generate a secret: `openssl rand -hex 24`
2. Set **`TRANSMUTE_AUTH_SECRET_KEY`** in `/etc/infra-core/site.env` (and sops attributes).

New Core installs get the key from `core.sh` into `/etc/infra-core/site.env`.

Without a fixed `AUTH_SECRET_KEY`, every container restart invalidates JWTs.

## 2. Deploy

Re-apply with `apply.sh` **caddy** and **homepage**.

On mantle, allow Windows Firewall TCP **3313** from the LAN (Caddy). See `bootstrap/mantle/README.md`.

```text
podman ps --filter name=transmute --format "table {{.Names}}\t{{.Status}}"
```

You want `transmute` **Up** (healthy after the first minute). The stack reserves surface NVIDIA GPU for FFmpeg NVENC (`bootstrap/mantle/README.md`). A newer Transmute image runs Draw.io Electron `--version` at boot; that crash fills `C:` with WSL dumps. The OIDC entrypoint stubs that probe so the GPU can stay.

## 3. Admin

Open **`https://convert.<DOMAIN>`** (Caddy sends `transmute.` there). Local admin stays as break-glass. Authelia OIDC is on (`Login with Authelia`). First Authelia login as **faiz** or **diana** creates a Transmute user (`OIDC_AUTO_CREATE_USERS`). Elevate **faiz** in Transmute.

## If it fails

| Symptom | What to do |
|---|---|
| `convert.<DOMAIN>` does not load while the container is Up | re-apply (apply.sh / systemd) **caddy**. From Core: `podman exec caddy wget -S -O- --timeout=10 http://<SURFACE_UPSTREAM>:3313/ \| head` |
| `C:` fills and `wsl-crash-*-_opt_drawio_drawio-*.dmp` appears | Stop/rm **transmute**. Delete `%LOCALAPPDATA%\\Temp\\wsl-crashes\\*`. The GPU is not the cause; Draw.io `--version` at boot is. re-apply (apply.sh / systemd) **transmute** after the entrypoint wrapper is on surface. |
| Logged out after re-apply (apply.sh / systemd) | `TRANSMUTE_AUTH_SECRET_KEY` must be set and unchanged |
| Authelia succeeds, then Internal Server Error | Token POST is `401 invalid_client`. Authelia must use `token_endpoint_auth_method: client_secret_basic` (Transmute/Authlib sends Basic, not post). re-apply (apply.sh / systemd) **authelia** only. |
