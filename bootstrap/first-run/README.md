# First-run notes

Per-app notes after Layer 0. Stacks start with **`sudo bash bootstrap/apply.sh`** (and systemd). Site values live in `/etc/infra-core/site.env`.

Canonical order: [`SITE-DEPLOY.md`](../SITE-DEPLOY.md). Do not restore Authelia sqlite; use `users.yml`.
