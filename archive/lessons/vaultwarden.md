# Vaultwarden: Android login, the web vault, and Sablier

`vaultwarden` is `sso: admin-only` in `components/pack.yaml`. Site-wide forward auth is still on. The Caddy generator in `ansible/lib/generate.py` splits `pass.<domain>` so Bitwarden clients can log in and the web vault stays behind Authelia. Re-run SET after changing that split. Do not edit the live Caddyfile.

## What the phone was hitting

The Android app posts the password to `/identity/connect/token`. A stack trace that only says HTTP 401 does not say who rejected it.

When the whole host was behind Authelia, that POST got `303` to `https://auth.<domain>/` and never reached Vaultwarden. The browser extension still worked because the browser already had an `authelia_session` cookie for the parent domain. The app has no such cookie, so Authelia's refusal showed up as 401.

A curl of that POST tells the two cases apart. JSON (`invalid_grant` or `invalid_client`) is Vaultwarden. An Authelia redirect or HTML page is Caddy.

## What stays open, and what is gated

Open, no Authelia cookie required. Sablier still runs first:

- `/api`
- `/identity`
- `/notifications`
- `/icons`
- `/events`

Gated by Authelia, then Sablier, then Vaultwarden:

- the web vault (`/`)
- `/admin`

The server URL in the app is the primary host, `https://pass.<domain>`, matching `DOMAIN` in `components/vaultwarden/vaultwarden.container`. `pw.` and `vaultwarden.` are redirects. The app's login POST does not survive that redirect.

## Sablier

Sablier runs on every path above, before Authelia on the open client paths and after Authelia on the web vault. See [Sablier](sablier.md). There is no waiting page. A stopped `vaultwarden.service` makes the request wait until the unit is up.
