# Components

Each directory under `components/` is a Quadlet app: kube-play YAML and/or `.container` / `.kube` / `.network`, plus config files.

```
components/<name>/
  MANIFEST.toml          # optional service list
  <name>.kube            # kube-play wrapper, or
  <name>.container       # host-net / single Quadlet
  pod.yaml               # kube-play Pod(s)
  config/                # Caddyfile, Homepage YAML, Authelia, …
```

`bootstrap/apply.sh` copies these into `/etc/containers/systemd/<name>/` (rootful: Scrutiny) or `/home/pilot/.config/containers/systemd/<name>/` (rootless), substituting `${VAR}` from `/etc/infra-core/site.env`. `Yaml=pod.yaml` is beside the unit after install.

- **kube-play subset only:** Pod, ConfigMap, Secret, PVC. No Ingress/Service/HPA here (`overlays/k8s/` is the stub).
- **Host-netns rootless** (Caddy, Pi-hole, PeaNUT, RustDesk, wg-easy UI): `.container` with `Network=host`. PeaNUT stays host-net so it can reach `upsd` on `127.0.0.1:3493`; Homepage on `site` scrapes it at `169.254.1.2:8092` (`bootstrap/first-run/peanut.md`).
- **Rootful host plumbing** (`wg-quick`, Scrutiny): system Quadlets / units.
- **Site mesh:** `site-network` installs `site.network`. Other Core/mantle app units set `Network=site.network`.
- **Placeholders:** `${DOMAIN}`, `${DATA_ROOT}`, `${SURFACE_UPSTREAM}`, … from `site.env`. No live IPs/domains/secrets in git.
- **Materia:** optional. `bootstrap/core/materia-enable.sh` polls git and runs `apply.sh`. Not required.

Linuxserver images: `PUID`/`PGID`. Mantle libraries: `hostPath` from WSL NFS (`${NFS_SHARED}`, `${NFS_USERS}`). GPU: CDI `nvidia.com/gpu=all` on Immich ML / Jellyfin.
