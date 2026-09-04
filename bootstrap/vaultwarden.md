# Vaultwarden first-run and import

Vaultwarden runs on **Core**. Caddy is `https://pw.<DOMAIN>` (`pass.` / `vaultwarden.` aliases). Authelia forward-auth is **`/admin` only**; the vault and Bitwarden clients authenticate to Vaultwarden itself.

## 1. First user

After ResourceSync deploys **vaultwarden** and **caddy**, open `https://pw.<DOMAIN>` and create the household owner. Then set Komodo `SIGNUPS_ALLOWED=false` and Redeploy **vaultwarden**.

`VAULTWARDEN_ADMIN_TOKEN` is the `/admin` token (Authelia `admins` still sits in front of that path).

## 2. Site login stubs (future installs)

The catalog Caddyfile is the list of public URLs. Generate a Bitwarden JSON with one Login per site block, every alias as a URI, **match = Host** (not Domain — otherwise every `*.<DOMAIN>` login collides):

```text
DOMAIN=home.lan python3 bootstrap/vaultwarden-import.py -o vw-import.json
```

Dry-run (names and hosts only):

```text
DOMAIN=home.lan python3 bootstrap/vaultwarden-import.py --list
```

Vaultwarden → **Tools** → **Import data** → **Bitwarden (json)** → `vw-import.json`.

Items land in a folder named after `DOMAIN`. Usernames and passwords are empty. Create each service’s native admin (and Authelia users) as usual, then edit the imported logins. Import **once**; a second import duplicates.

Do not commit `vw-import.json`.
