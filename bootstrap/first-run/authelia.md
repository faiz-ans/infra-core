# Authelia SSO (existing Core)

Authelia is the household IdP. Two file-backend users: **faiz** (`admins` + `users`) and **diana** (`users`). Sysadmin OIDC clients only accept `admins`. Household OIDC clients and the Caddy forward-auth gates accept `users` (both people).

Caddy uses `tls internal`. App backends that talk to `https://auth.<DOMAIN>` skip TLS verify where the app allows it. Browsers must already trust the Caddy CA.

Do **not** put Authelia forward-auth in front of Homepage, OIDC apps, Collabora, or Vaultwarden’s vault. Homepage stays open; the others would be a second login (or would break DAV/WOPI/clients).

## 1. Generate users and OIDC material

New Core installs get these files from `core.sh`. On an existing Core, re-run `core.sh` (it skips files that already exist) or generate by hand:

```text
podman run --rm -v "${DATA_ROOT}/system/authelia:/out" docker.io/authelia/authelia:4 \
  authelia crypto pair rsa generate --directory /out
sudo mv "${DATA_ROOT}/system/authelia/private.pem" "${DATA_ROOT}/system/authelia/oidc.pem"
```

| Path | What |
|---|---|
| `${DATA_ROOT}/system/authelia/users.yml` | `faiz` and `diana` (backs up the old file) |
| `${DATA_ROOT}/system/authelia/oidc.pem` | RSA signing key (keep) |
| `${DATA_ROOT}/system/authelia/client_secret` | Shared confidential-client secret (plaintext) |
| `${DATA_ROOT}/system/authelia/client_secret_digest` | Same secret, hashed for Authelia |
| `${DATA_ROOT}/system/authelia/caddy-root.crt` | Caddy `tls internal` CA (for OIDC discovery from app containers) |
| `${DATA_ROOT}/system/authelia/ca-bundle.crt` | Public CAs + Caddy CA |

Keep **`AUTHELIA_OIDC_HMAC_SECRET`** and **`OIDC_CLIENT_SECRET`** in `/etc/infra-core/site.env` so `core.sh` re-runs do not rotate them.

Do **not** restore Authelia sqlite from a previous storage key. File backend is `users.yml` plus `oidc.pem` / client-secret files. Skip `db.sqlite3`.

## 2. Caddy CA bundle (OIDC discovery)

After **caddy** is up, it writes both cert files (`caddy-ca: exported` in the caddy logs). If they are still empty, dump once:

```text
CA="${DATA_ROOT}/system/authelia"
sudo mkdir -p "${CA}"
sudo rm -rf "${CA}/caddy-root.crt"
sudo podman exec caddy cat /data/caddy/pki/authorities/local/root.crt | sudo tee "${CA}/caddy-root.crt" >/dev/null
sudo cat /etc/ssl/certs/ca-certificates.crt "${CA}/caddy-root.crt" | sudo tee "${CA}/ca-bundle.crt" >/dev/null
sudo chmod 644 "${CA}/caddy-root.crt" "${CA}/ca-bundle.crt"
```

Cockpit on Core (`https://box.<DOMAIN>` or `:9090`) is the host UI. There is no Komodo OIDC client.

## 3. Re-apply catalog stacks

Re-apply with `sudo bash bootstrap/apply.sh` in this order:

1. **authelia** (must see `oidc.pem` and `client_secret_digest` or it will not start)
2. **caddy** (forward-auth gates, Host pins, CA export)
3. **opencloud**, **jotty**, **linkding**, **bytestash**, **homepage**
4. On mantle: **transmute**, **monitoring**, **adventurelog**

Confirm Authelia is up:

```text
podman logs authelia --tail 80
podman exec caddy wget -S -O- --timeout=10 http://127.0.0.1:9091/api/health | head
```

You want HTTP 200 and no JWKS / template errors.

## 4. First Authelia login (not catalog debugging)

`core.sh` registers Authelia users. First login as **faiz** or **diana** creates the app user; elevate **faiz** inside each app. Keep the built-in `admin` (or equivalent) as break-glass.

| App | What is left |
|---|---|
| **Immich** | Immich has no compose OAuth. After the admin wizard, set Admin → OAuth once ([immich.md](immich.md)). |
| **Adventure Log** | Social app is seeded on boot. Use **Login** → **Authelia** (Sign Up stays closed). |
| **OpenCloud / Grafana / Linkding / Jotty / Transmute / ByteStash** | Env is already in the Quadlet. |

DAV/mobile that cannot do OIDC: OpenCloud **App Token**; Immich mobile uses the Immich OAuth redirect `app.immich:///oauth-callback`.

## 5. Who can open what

**Forward-auth (Authelia is the only login)**

- Household (`users`): BentoPDF, IT Tools, LibreTranslate, PeaNUT (`ups.` / `peanut.`)
- Sysadmin (`admins`): Prometheus, Glances, Glances (mantle), Scrutiny, Caddy Manager, Vaultwarden `/admin`

**OIDC (app session after Authelia)**

- Household: OpenCloud, Immich, Linkding, Jotty, Transmute, ByteStash, Adventure Log
- Sysadmin: Grafana

## 6. Excluded from Authelia (create matching native accounts)

These either have no OIDC / trusted-header support, or putting Authelia in front would be a second login (or would break clients). Use the same usernames/passwords as Authelia if you want it to feel close to SSO.

| App | Why |
|---|---|
| Pi-hole (Core and mantle) | Own admin password; no OIDC |
| OpenMediaVault | Own login; no OIDC |
| WireGuard (wg-easy) | Host-network + Caddy internal TLS; OIDC needs a cert the UI will trust |
| Vaultwarden vault | Official clients + lockout risk; Authelia stays on `/admin` only |
| Jellyfin | No first-class OIDC in this catalog (plugin not shipped) |
| Seerr | OIDC is still preview / not on `:latest` |
| Home Assistant | No official OIDC |
| Frigate | Own login |
| Scriberr | No OIDC |
| OpenReader | Own login; no OIDC |
| n8n | Community SSO is license-gated / unreliable to declare in the Quadlet |
| qBittorrent, Sonarr, Radarr, Prowlarr | Own login; no OIDC |
| Collabora | WOPI machine traffic; must not be gated |
| RustDesk | Not HTTP |
| Router, printer | Device logins |
| Cockpit | Host PAM; no Authelia gate |

Homepage (`dash.` / `homepage.`) has no Authelia gate. Widgets scrape internal URLs, so they do not hit Authelia either.

## If it fails

| Symptom | What to do |
|---|---|
| Authelia Restarting / template error / JWKS | `${DATA_ROOT}/system/authelia/oidc.pem` must be a PEM private key. Generate with `podman run --rm -v "${DATA_ROOT}/system/authelia:/out" authelia/authelia:4 authelia crypto pair rsa generate --directory /out` and copy `private.pem` to `oidc.pem`. Confirm `client_secret_digest` exists. Then re-apply **authelia**. |
| Authelia: client_secret | `${DATA_ROOT}/system/authelia/client_secret_digest` must be a pbkdf2 digest, not the plaintext. |
| `pdf.<DOMAIN>` / `metrics.<DOMAIN>` open with no Authelia login | The live Caddyfile is stale. Re-apply **caddy**, then open `https://pdf.<DOMAIN>` / `https://metrics.<DOMAIN>` (not a host port). Homepage itself is ungated on purpose. |
| Forward-auth site returns 401 instead of the login page | Re-apply **caddy** so `authelia_url` is on the `forward_auth` URI. |
| Diana can open Grafana login but Authelia denies | Expected. Those clients are `admins` only. |
| OpenCloud CSP / blank login | `IDP_DOMAIN=auth.<DOMAIN>` and re-apply **opencloud**. Confirm `csp.yaml` lists `https://auth.<DOMAIN>/`. |
| OpenCloud: Consent Request every login | Authelia must prompt for every `offline_access` (refresh token) request; remembered consent does not apply. Catalog drops that scope on the **web** client. Re-apply **authelia** and **opencloud**. Confirm `podman exec opencloud printenv WEB_OIDC_SCOPE` has no `offline_access`. |
| Immich OAuth “can’t reach the server” | Re-apply **immich** after `extra_hosts` + `NODE_TLS_REJECT_UNAUTHORIZED`. The image has no `wget` — use `podman exec -e NODE_TLS_REJECT_UNAUTHORIZED=0 immich node -e "fetch('https://auth.<DOMAIN>/.well-known/openid-configuration').then(async r=>{console.log(r.status);console.log(await r.text())}).catch(e=>{console.error(e);process.exit(1)})"`. `ENOTFOUND` means the stack was not recreated with `extra_hosts`. Timeout to the NAS IP: see [`bootstrap/mantle/README.md`](../mantle/README.md). |
| Firefox “can’t find” `*.home.lan`, Edge works | AAAA NXDOMAIN from Pi-hole (`address=/` IPv4-only). Firefox will not try A. See [`bootstrap/mantle/README.md`](../mantle/README.md). |
