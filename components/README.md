# Components

Each directory under `components/` is a Materia component: a `MANIFEST.toml` plus Quadlets and data files.

```
components/<name>/
  MANIFEST.toml          # required (empty is valid)
  <name>.kube            # kube-play wrapper, or
  <name>.container       # host-net / single Quadlet
  <name>.yaml            # kube-play Pod(s)
  *.gotmpl               # Go-templated from attributes
  config/                # Caddyfile, Homepage YAML, Authelia, …
```

- **kube-play subset only:** Pod, ConfigMap, Secret, PVC. No Ingress/Service/HPA here (`overlays/k8s/` is the stub for that).
- **Host-netns rootless** (Caddy, Pi-hole, RustDesk, wg-easy UI): `.container` with `Network=host`.
- **Rootful host plumbing** (nft redirects, `wg-quick`, Scrutiny): system Quadlets / units, Core system Materia timer.
- **Site mesh:** `site-network` installs `site.network`. Other Core/mantle app units set `Network=site.network`.
- **Caddy** is host-net and reverse-proxies Core apps at `127.0.0.1:<published>` and mantle at `{$SURFACE_UPSTREAM}`.
- **Placeholders:** `{{.DOMAIN}}`, `{{.DATA_ROOT}}`, `{{.SURFACE_UPSTREAM}}`, … from attributes. No live IPs/domains/secrets in git.
- **Materia:** pin **v0.7.2**. Install from the GitHub release for the host arch. `materia update` on a systemd timer; not `materia server`.

Linuxserver images: `PUID`/`PGID` attributes. Mantle libraries: `hostPath` from WSL NFS (`{{.NFS_SHARED}}`, `{{.NFS_USERS}}`), not a Docker NFS driver. GPU: CDI `nvidia.com/gpu=all` on Immich ML / Jellyfin.
