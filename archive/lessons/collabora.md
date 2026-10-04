# Collabora: office editing in OpenCloud

Working state when both `opencloud` and `collabora` are placed. SET wires them in `ansible/lib/integrate.py`. Do not SSH a fix onto the host.

`ansible/lib/diff.py` hashes both placements into each service fingerprint, so adding or moving one re-renders the other on the next SET.

## Wiring

OpenCloud, only while Collabora is placed:

- `OC_ADD_RUN_SERVICES=collaboration`
- `COLLABORA_DOMAIN` is the office host, no scheme. CSP `frame-src` and `img-src` substitute it (`components/opencloud/csp.yaml`).
- `COLLABORATION_APP_ADDR=https://<office>`
- `COLLABORATION_WOPI_SRC=https://<cloud>`
- `COLLABORATION_APP_PROOF_DISABLE=true`, plus the two insecure flags

Collabora, only while OpenCloud is placed:

- `aliasgroup1=https://<cloud>`
- `extra_params` adds `--o:net.frame_ancestors=<cloud>` and `--o:net.lok_allow.host[14]=<cloud>`

Caddy proxies the office name to that host's `:9980` with no Authelia gate, `X-Forwarded-Proto https`, and long read/write timeouts.

A container on the ingress host cannot hairpin to that host's LAN `:443`. Its `AddHost` for `cloud.`, `auth.`, and `office.` is `169.254.1.2` (pasta loopback; lan-bind sends it to Caddy). A container on another host uses the ingress LAN address.

## A docx never offers Collabora

The collaboration service polls `https://<office>/hosting/discovery`. HTTP 502 every 30 seconds means it never registers an office app. The file stays a normal download.

On this site Collabora is on Mantle (WSL, mirrored networking) and OpenCloud is on Core. Collabora answers discovery with 200 on the Mantle host. From Core, `:9980` times out. Glances `61208`, Immich `2283`, and Pi-hole web `8088` are already reachable. Mirrored networking drops a LAN TCP port into WSL unless a Hyper-V firewall rule allows it. `9980` has to be in that list (`windows/wsl-pihole.md`). SET cannot create the rule. An elevated PowerShell on the Windows host does.

## The editor frame never appears

Discovery `urlsrc` is `http://<office>/browser/.../cool.html`. OpenCloud is HTTPS. The browser blocks that frame as mixed content, so the iframe never shows.

Caddy already sends `X-Forwarded-Proto: https`. Collabora ignores it unless `ssl.termination` is true. The unit used `--o:ssl.ssl_termination=true`. Startup lists that key as a loaded non-default value, then logs `SSL support: termination is disabled`. The flag it reads is `--o:ssl.termination=true` (`ssl.enable=false` stays). After the next SET, discovery `urlsrc` is `https://<office>/...`.
