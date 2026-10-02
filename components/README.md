# Components

Each directory under `components/` is an official Quadlet: kube-play Pod YAML and/or `.container` / `.kube` / `.network`. Placement is `site.yaml` (`hosts[].operations.workload.services`), not a host-role manifest.

```
components/<name>/
  <name>.kube            # kube-play wrapper, or
  <name>.container       # host-net / single process
  pod.yaml               # kube-play Pod
```

`components/pack.yaml` is the official service pack (ports, OIDC vs forward-auth, host-net vs site, rootful vs rootless). A generated site uses the service name as its host label (`authelia.example.lan`). `hosts[].operations.workload.services[].subdomain` in `site.yaml` replaces that. With `generate-upstream: false`, SET installs `components/caddy/Caddyfile` and `components/authelia/configuration.yml` instead of generating them. Homepage uses `components/homepage/config/services.yaml` when that file is present, and the My First Group example when it is not. Comment-only engines in the example topology are vocabulary, not implementations.

SET (`ansible/site.py set`) resolves `${site.*}`, `${host.*}`, and `${component.dir}` on the runner. `${secrets.site.<service>.<name>}`, `${secrets.<service>.<name>}`, and `${secrets.<name>}` read a site secret (`<name>` uses the service being rendered). `${secrets.hosts.<hostname>.<service>.<name>}`, `${secrets.host.<service>.<name>}`, and `${secrets.host.<name>}` read a host secret (`host` is the instance's host; `<name>` uses the service being rendered). The Podman secret for a service's own secret is `<service>_<name>` (`pi-hole_web_password`). The service key is exact: `pi-hole` does not match `pihole`. Another unit reading that host secret uses `<unit>_<service>_<name>` (`homepage_pi-hole_web_password`). Another host's secret also includes the host name (`homepage_mantle_pi-hole_web_password`). Each host receives site secrets, its own host secrets, and the cross-references its units name. kube-play `secretKeyRef` and Quadlet `Secret=` read the value at runtime. Kubernetes-only kinds (Ingress, Service, HPA) are stripped. Units install into the system tree (rootful) or the workload-user tree (rootless).

Lessons encoded in the pack and generators:

- Caddy / Authelia: `UserNS=keep-id` and PKI/oidc.pem ownership
- lan-bind: ingress host PREROUTING 53/80/443 plus OUTPUT `:443` on loopback and the ingress LAN IP — never OUTPUT `:53`; bare-metal secondary Pi-hole uses Linux `site-dns-proxy` (socat). A WSL Pi-hole stays on `:15353`; the operator publishes `:53` with Windows dnsproxy (`windows/wsl-pihole.md`).
- OpenCloud: `PROXY_OIDC_ACCESS_TOKEN_VERIFY_METHOD=none`, autoprovision, `auth.` → pasta `169.254.1.2`
- Homepage: `HOMEPAGE_ALLOWED_HOSTS` includes `:8443`; host scrapes via `169.254.1.2`; Pi-hole widget key is the web password
- PeaNUT: host-net `:8092`, NUT `127.0.0.1`, no `AUTH_URL`
- WireGuard MTU 1280
- Do not recreate OpenCloud spaces when xattrs already exist
