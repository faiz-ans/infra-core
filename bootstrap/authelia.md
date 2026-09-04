# Authelia SSO (existing Core)

Authelia is the household IdP. Two file-backend users: **faiz** (`admins` + `users`) and **diana** (`users`). Sysadmin OIDC clients only accept `admins`. Household OIDC clients and the Caddy forward-auth gates accept `users` (both people).

Caddy uses `tls internal`. App backends that talk to `https://auth.<DOMAIN>` skip TLS verify where the app allows it. Browsers must already trust the Caddy CA.

Do **not** put Authelia forward-auth in front of Homepage, OIDC apps, Gitea HTTP, Collabora, or Vaultwarden’s vault. Homepage stays open; the others would be a second login (or would break git/DAV/WOPI/clients).

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
| `${DATA_ROOT}/system/authelia/caddy-root.crt` | Caddy `tls internal` CA (for Gitea OIDC discovery) |
| `${DATA_ROOT}/system/authelia/ca-bundle.crt` | Public CAs + Caddy CA (Komodo Core `SSL_CERT_FILE`) |

It prints **`AUTHELIA_OIDC_HMAC_SECRET`** and **`OIDC_CLIENT_SECRET`**. Add both in Komodo → **Settings** → **Secrets**. Mark them secrets. Also add them to `/etc/komodo/core.config.toml` if you want `core.sh` re-runs to keep them.

New Core installs get the same files from `core.sh`.

## 2. Komodo Core OIDC (not ResourceSync)

Komodo Core is the bootstrap compose, not a ResourceSync stack. On Core, append to `/etc/komodo/bootstrap/compose.env` (use the live domain and the printed client secret):

```text
DOMAIN=home.lan
NAS_LAN_IP=<NAS_LAN_IP>
DATA_ROOT=/srv/dev-disk-by-uuid-<UUID>
KOMODO_OIDC_ENABLED=true
KOMODO_OIDC_PROVIDER=https://auth.home.lan
KOMODO_OIDC_CLIENT_ID=komodo
KOMODO_OIDC_CLIENT_SECRET=<OIDC_CLIENT_SECRET>
KOMODO_ENABLE_NEW_USERS=true
```

`KOMODO_LOCAL_AUTH` stays `true` (break-glass). Copy the current `bootstrap/komodo/compose.yaml` to `/etc/komodo/bootstrap/compose.yaml` (it mounts `ca-bundle.crt`). The bundle must be a **file** before recreate:

```text
CA="${DATA_ROOT}/system/authelia"
sudo docker exec caddy cat /data/caddy/pki/authorities/local/root.crt | sudo tee "${CA}/caddy-root.crt" >/dev/null
sudo cat /etc/ssl/certs/ca-certificates.crt "${CA}/caddy-root.crt" | sudo tee "${CA}/ca-bundle.crt" >/dev/null
sudo chmod 644 "${CA}/caddy-root.crt" "${CA}/ca-bundle.crt"
```

Then recreate Core:

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

- Household (`users`): BentoPDF, IT Tools, LibreTranslate
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

Homepage (`dash.` / `homepage.`) has no Authelia gate. Widgets scrape internal URLs, so they do not hit Authelia either.

## If it fails

| Symptom | What to do |
|---|---|
| Authelia Restarting / template error / JWKS | `${DATA_ROOT}/system/authelia/oidc.pem` must be a PEM private key. Re-run `authelia-oidc.sh` or generate with `docker run --rm -v "${DATA_ROOT}/system/authelia:/out" authelia/authelia:4 authelia crypto pair rsa generate --directory /out` and copy `private.pem` to `oidc.pem`. Confirm `client_secret_digest` exists. Then Redeploy **authelia**. |
| Authelia: client_secret | `${DATA_ROOT}/system/authelia/client_secret_digest` must be a pbkdf2 digest, not the plaintext. |
| `pdf.<DOMAIN>` / `metrics.<DOMAIN>` open with no Authelia login | The live Caddyfile is stale. Komodo `config_files` for Caddy **requires Redeploy** (`--watch` does not copy git updates). Redeploy **caddy**, then open `https://pdf.<DOMAIN>` / `https://metrics.<DOMAIN>` (not a host port). Homepage itself is ungated on purpose. |
| Forward-auth site returns 401 instead of the login page | Redeploy **caddy** so `authelia_url` is on the `forward_auth` URI. |
| Diana can open Grafana/Komodo/Gitea login but Authelia denies | Expected. Those clients are `admins` only. |
| OpenCloud CSP / blank login | `IDP_DOMAIN=auth.<DOMAIN>` and Redeploy **opencloud**. Confirm `csp.yaml` lists `https://auth.<DOMAIN>/`. |
| Gitea `flag provided but not defined: -skip-tls-verify` | That flag is not on `gitea admin auth add-oauth`. Dump the Caddy CA and Redeploy **gitea**, then run the command in [gitea.md](gitea.md) (no skip-tls flag). |
| Immich OAuth “can’t reach the server” | Redeploy **immich** after `extra_hosts` + `NODE_TLS_REJECT_UNAUTHORIZED`. The image has no `wget` — use `docker exec -e NODE_TLS_REJECT_UNAUTHORIZED=0 immich node -e "fetch('https://auth.<DOMAIN>/.well-known/openid-configuration').then(async r=>{console.log(r.status);console.log(await r.text())}).catch(e=>{console.error(e);process.exit(1)})"`. `ENOTFOUND` means the stack was not recreated with `extra_hosts`. Timeout to the NAS IP means Docker LAN overlap ([periphery.md](periphery.md) §7). |
| Firefox “can’t find” `*.home.lan`, Edge works | AAAA NXDOMAIN from Pi-hole (`address=/` IPv4-only). Firefox will not try A. See [periphery.md](periphery.md) §3. |
| Komodo OIDC “Provider not available” | Core cannot verify Caddy TLS. Write `ca-bundle.crt` (see §2), copy `bootstrap/komodo/compose.yaml` onto the box, set `DATA_ROOT` in `compose.env`, recreate Core. |
