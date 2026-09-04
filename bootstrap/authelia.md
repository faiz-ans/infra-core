# Authelia SSO (existing Core)

Authelia is the household IdP. Two file-backend users: **faiz** (`admins` + `users`) and **diana** (`users`). Sysadmin OIDC clients only accept `admins`. Household OIDC clients and the Caddy forward-auth gates accept `users` (both people).

Caddy uses `tls internal`. App backends that talk to `https://auth.<DOMAIN>` skip TLS verify where the app allows it. Browsers must already trust the Caddy CA.

Do **not** put Authelia forward-auth in front of OIDC apps, Gitea HTTP, Collabora, or Vaultwarden’s vault. That is a second login (or it breaks git/DAV/WOPI/clients).

## 1. Generate users and OIDC material

On Core, from a clone of this repo (or a copy of `bootstrap/`):

```text
sudo DATA_ROOT=/srv/dev-disk-by-uuid-<UUID> DOMAIN=home.lan bash bootstrap/authelia-oidc.sh
```

Use this site’s `DATA_ROOT` and `DOMAIN`. The script writes:

| Path | What |
|---|---|
| `${DATA_ROOT}/system/authelia/users.yml` | `faiz` and `diana` (backs up the old file) |
| `${DATA_ROOT}/system/authelia/oidc.pem` | RSA signing key (keep) |
| `${DATA_ROOT}/system/authelia/client_secret` | Shared confidential-client secret (plaintext) |
| `${DATA_ROOT}/system/authelia/client_secret_digest` | Same secret, hashed for Authelia |

It prints **`AUTHELIA_OIDC_HMAC_SECRET`** and **`OIDC_CLIENT_SECRET`**. Add both in Komodo → **Settings** → **Secrets**. Mark them secrets. Also add them to `/etc/komodo/core.config.toml` if you want `core.sh` re-runs to keep them.

New Core installs get the same files from `core.sh`.

## 2. Komodo Core OIDC (not ResourceSync)

Komodo Core is the bootstrap compose, not a ResourceSync stack. On Core, append to `/etc/komodo/bootstrap/compose.env` (use the live domain and the printed client secret):

```text
DOMAIN=home.lan
NAS_LAN_IP=<NAS_LAN_IP>
KOMODO_OIDC_ENABLED=true
KOMODO_OIDC_PROVIDER=https://auth.home.lan
KOMODO_OIDC_CLIENT_ID=komodo
KOMODO_OIDC_CLIENT_SECRET=<OIDC_CLIENT_SECRET>
KOMODO_ENABLE_NEW_USERS=true
```

`KOMODO_LOCAL_AUTH` stays `true` (break-glass). Then recreate Core so it picks up `extra_hosts` and the new env:

```text
docker compose --env-file /etc/komodo/bootstrap/compose.env \
  -f /etc/komodo/bootstrap/compose.yaml up -d
```

First Authelia login as **faiz**. If Komodo creates the user disabled, enable it with the local admin, then elevate that OIDC user.

## 3. Redeploy catalog stacks

Push this catalog to Gitea. Wait for ResourceSync. Then **Redeploy** in this order:

1. **authelia** (must see `oidc.pem` and `client_secret_digest` or it will not start)
2. **caddy** (forward-auth gates + `--watch` is not enough if you only redeploy other stacks)
3. **opencloud**, **gitea**, **jotty**, **linkding**, **bytestash**, **homepage**
4. On the HTPC sync: **transmute**, **monitoring**

Confirm Authelia is up:

```text
docker logs authelia --tail 80
docker exec caddy wget -S -O- --timeout=10 http://authelia:9091/api/health | head
```

You want HTTP 200 and no JWKS / template errors.

## 4. One-time app clicks

| App | What to do |
|---|---|
| **Gitea** | See [gitea.md](gitea.md) § OIDC. `gitea admin auth add-oauth` once. Name must be `authelia`. |
| **Immich** | See [immich.md](immich.md) § OIDC. Admin → OAuth. Issuer `https://auth.<DOMAIN>`. Client `immich`. Secret is `OIDC_CLIENT_SECRET`. Auto-register on. |
| **Adventure Log** | See [adventurelog.md](adventurelog.md) § OIDC. Django admin social app named `authelia`. |
| **OpenCloud / Grafana / Linkding / Jotty / Transmute / ByteStash** | Env is already in compose. First Authelia login creates a normal user. Elevate **faiz** inside each app. Keep the built-in `admin` (or equivalent) as break-glass. |

DAV/mobile that cannot do OIDC: OpenCloud **App Token**; Immich mobile uses the Immich OAuth redirect `app.immich:///oauth-callback`.

## 5. Who can open what

**Forward-auth (Authelia is the only login)**

- Household (`users`): Homepage, BentoPDF, IT Tools, LibreTranslate
- Sysadmin (`admins`): Prometheus, Glances, Glances (periphery), Vaultwarden `/admin`

**OIDC (app session after Authelia)**

- Household: OpenCloud, Immich, Linkding, Jotty, Transmute, ByteStash, Adventure Log
- Sysadmin: Grafana, Gitea (browser only), Komodo

## 6. Excluded from Authelia (create matching native accounts)

These either have no OIDC / trusted-header support, or putting Authelia in front would be a second login (or would break clients). Use the same usernames/passwords as Authelia if you want it to feel close to SSO.

| App | Why |
|---|---|
| Pi-hole (Core and HTPC) | Own admin password; no OIDC |
| OpenMediaVault | Own login; no OIDC |
| WireGuard (wg-easy) | Host-network + Caddy internal TLS; OIDC needs a cert the UI will trust |
| Vaultwarden vault | Official clients + lockout risk; Authelia stays on `/admin` only |
| Jellyfin | No first-class OIDC in this catalog (plugin not shipped) |
| Seerr | OIDC is still preview / not on `:latest` |
| Home Assistant | No official OIDC |
| Frigate | Own login |
| Scriberr | No OIDC |
| OpenReader | Own login; no OIDC |
| n8n | Community SSO is license-gated / unreliable to declare in compose |
| qBittorrent, Sonarr, Radarr, Prowlarr | Own login; no OIDC |
| Collabora | WOPI machine traffic; must not be gated |
| RustDesk | Not HTTP |
| Router, printer | Device logins |

Homepage widgets keep using internal URLs, so they do not hit Authelia.

## If it fails

| Symptom | What to do |
|---|---|
| Authelia Restarting / template error / JWKS | `${DATA_ROOT}/system/authelia/oidc.pem` must be a PEM private key. Re-run `authelia-oidc.sh` or generate with `docker run --rm -v "${DATA_ROOT}/system/authelia:/out" authelia/authelia:4 authelia crypto pair rsa generate --directory /out` and copy `private.pem` to `oidc.pem`. Confirm `client_secret_digest` exists. Then Redeploy **authelia**. |
| Authelia: client_secret | `${DATA_ROOT}/system/authelia/client_secret_digest` must be a pbkdf2 digest, not the plaintext. |
| `dash.<DOMAIN>` login loop | Redeploy **caddy** after the Authelia gate was added. Cookie domain is `DOMAIN`. |
| Diana can open Grafana/Komodo/Gitea login but Authelia denies | Expected. Those clients are `admins` only. |
| OpenCloud CSP / blank login | `IDP_DOMAIN=auth.<DOMAIN>` and Redeploy **opencloud**. Confirm `csp.yaml` lists `https://auth.<DOMAIN>/`. |
| Gitea OIDC TLS error | The add-oauth command uses `--skip-tls-verify` (internal CA). |
| Immich OAuth token fail | Immich on the HTPC must reach `https://auth.<DOMAIN>`. Trust the Caddy CA on Docker Desktop or the issuer fetch will fail. |
| Komodo OIDC button missing | `compose.env` OIDC lines + recreate Core. `KOMODO_HOST` must be `https://ops.<DOMAIN>`. |
