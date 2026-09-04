# Gitea (catalog git)

Gitea is the primary origin for `faiz-ans/infra-core`. GitHub stays as a **push mirror** (backup). Komodo polls Gitea over the Docker `edge` network (`gitea:3000`, HTTP). Do not put Authelia **forward-auth** in front of Gitea (git HTTP and Komodo would hit a login wall). Browser login is Authelia OIDC (sysadmin / `faiz` only). Do not put the live domain in ResourceSync TOML.

## 1. Data dir and deploy

On Core:

```text
sudo mkdir -p "${DATA_ROOT}/system/gitea"
```

Apply ResourceSync so the **gitea** and **caddy** stacks update. The web installer is **off** (`INSTALL_LOCK`); it hangs behind Caddy and can leave a broken data dir (Homepage then shows a white/unknown Docker dot).

If you already opened the installer and closed it, wipe and recreate **on Core**:

```text
docker stop gitea
sudo rm -rf "${DATA_ROOT}/system/gitea/"*
docker start gitea
```

Wait until `docker ps` shows `gitea` up **and** `docker inspect -f '{{.State.Health.Status}}' gitea` is `healthy` (not `starting`). Then create the admin:

```text
docker exec -u git gitea gitea admin user create --admin \
  --username admin \
  --password 'YOUR_PASSWORD' \
  --email admin@localhost \
  --must-change-password=false
```

Then log in at `https://git.<DOMAIN>`.

## OIDC (Authelia)

After Authelia OIDC material exists (`bootstrap/authelia.md`) and **gitea** has the current catalog:

```text
docker exec -u git gitea gitea admin auth add-oauth \
  --name=authelia \
  --provider=openidConnect \
  --key=gitea \
  --secret='OIDC_CLIENT_SECRET' \
  --auto-discover-url='https://auth.<DOMAIN>/.well-known/openid-configuration' \
  --skip-tls-verify \
  --scopes='openid email profile groups'
```

The authentication name **must** be `authelia` (that is the callback path Authelia allows). If the source already exists, Gitea will say so — do not add a second one. Local `admin` stays as break-glass. First Authelia login as **faiz** creates a normal Gitea user; elevate that user to admin in Gitea.

Connect Komodo Core to `edge` if it is not already (needed later for `gitea:3000`):

```text
docker network connect edge "$(docker ps -qf ancestor=ghcr.io/moghtech/komodo-core)"
```

If that matches more than one container, pass the Core container name explicitly. New bootstrap compose attaches Core to `edge` on recreate.

## 2. Transfer GitHub → Gitea

In Gitea: **New Migration** → GitHub → `https://github.com/faiz-ans/infra-core.git`.

- Owner: `faiz-ans` (create the org/user if needed)
- Repository name: `infra-core`
- Mirror: **off** for the migration (this is a one-time copy, not a pull mirror)

Or from a laptop that already has the repo:

```text
git remote add gitea https://git.<DOMAIN>/faiz-ans/infra-core.git
git push -u gitea main
```

Trust the Caddy internal CA for HTTPS git:

```text
git remote add gitea https://git.<DOMAIN>/faiz-ans/infra-core.git
```

## 3. Push mirror to GitHub (backup)

In the Gitea repo: **Settings → Mirror Settings → Add Push Mirror**.

- Sync URL: `https://github.com/faiz-ans/infra-core.git`
- Auth: a GitHub PAT with `repo` (classic) or repository **contents** write
- Interval: 10m (compose default `GITEA__mirror__INTERVAL`)

Store the PAT only in Gitea, not in this catalog. After this, `git push` to Gitea; Gitea updates GitHub.

## 4. Laptop origin

```text
git remote set-url origin https://git.<DOMAIN>/faiz-ans/infra-core.git
git remote add github https://github.com/faiz-ans/infra-core.git
```

Keep `github` only for emergencies. Day-to-day `git push` is `origin` (Gitea).

## 5. Komodo polls Gitea

Settings → Providers → add a git provider:

| Field | Value |
|---|---|
| Domain | `gitea:3000` |
| HTTPS | off |
| Account | Gitea username |
| Token | Gitea access token (repo read) |

On **every** stack in `stacks/komodo/stacks-core.toml` and `stacks-periphery.toml`, under `[stack.config]`, add:

```toml
git_provider = "gitea:3000"
```

Also set that provider on the ResourceSync resource in the Komodo UI (the sync that reads those TOML files). Commit and push that TOML change to **Gitea**. Then execute the sync.

`repo` stays `faiz-ans/infra-core`. Do not write `git.home.lan` (or any live domain) in git.

Until those `git_provider` lines exist, stacks keep cloning from GitHub. Apply this catalog from GitHub first so Gitea itself can start.
