## 1. Compose sidecar

- [x] 1.1 Add PostgreSQL service and local `nextcloud-postgres` volume to `compose.nfs.yaml` (no host port; Nextcloud `depends_on` healthy)
- [x] 1.2 Mirror the same sidecar on `compose.yaml`

## 2. Komodo and bootstrap

- [x] 2.1 Document `NEXTCLOUD_DB_PASSWORD` in `VARIABLES.md` and interpolate it in `stacks-periphery.toml`
- [x] 2.2 Prompt and write `NEXTCLOUD_DB_PASSWORD` in `bootstrap/core.sh` (answers + `[secrets]`; generate if missing on re-run)

## 3. Operator docs

- [x] 3.1 Add `bootstrap/nextcloud.md` with Komodo secret, volume wipe, and installer fields (`postgres` / `nextcloud`)
