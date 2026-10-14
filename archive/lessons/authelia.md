# Authelia: a saved page skips the gate

A normal visit can show the app with no Authelia login. A hard refresh then lands on `https://auth.<domain>/`. The saved page is the cause. Caddy, Authelia, and Sablier never see that visit.

The fix is in the Caddy generator (`ansible/lib/generate.py`). Re-run SET. Do not edit the live Caddyfile. After SET, hard-refresh each affected host once. That visit is what drops the copy already stored.

## What the browser is doing

The app was stored while you were signed in. The next ordinary visit replays that copy and does not ask Caddy.

A hard refresh skips the copy for that one load. Authelia then redirects to `auth.<domain>`. The redirect does not delete the stored page. The visit after that shows the app again.

Check the address bar:

- `https://<app>.<domain>/...` before the refresh is the stored app
- `https://auth.<domain>/?rd=...` after the refresh is Authelia

## What SET writes

On every gated site:

- `Cache-Control: private, no-store` on the proxied response, so a new page is not stored
- `Clear-Site-Data: "cache"` on the Authelia redirect, so the redirect drops the page already stored

Homepage is exempt from forward auth, so it does not get these headers. Vaultwarden client paths (`/api`, `/identity`, `/notifications`, `/icons`, `/events`) stay open and do not get them. The web vault does.

## IT Tools

IT Tools is a client-side app and installs a service worker (`/sw.js`). After one signed-in visit the worker serves the app from cache, including in a new tab. A hard refresh is the load that skips the worker.

Caddy answers `/sw.js` before Authelia with a worker that deletes those caches and does not answer fetches. The browser checks that URL on its own. The next visit goes through Authelia, then Sablier.

## CaddyManager

The stored page is `https://ingress.<domain>/login?redirect=/`. That is CaddyManager's own login, not Authelia.

While that page is on screen, its API calls (`/api/v1/...`) reach Authelia and get 401. The app treats 401 as "logged out of CaddyManager" and draws its login form. Those calls do not send the window to Authelia.

A hard refresh of that URL is a page load. Authelia redirects it to `auth.<domain>`.
