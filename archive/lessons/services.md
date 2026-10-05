# Uptime Kuma, Scrutiny, PeaNUT, and CaddyManager

Working state when those keys are listed on a workload host in `site.yaml`. SET installs them. Do not SSH a fix onto the host.

Homepage widgets that use a container hostname fail before HTTP. Node resolves AAAA, gets `ENODATA`, and the tile shows an API error. `NODE_OPTIONS=--dns-result-order=ipv4first` does not stop that lookup. Use an IPv4 the site network can open. `169.254.1.2` reaches ports bound on the host's LAN address or on `0.0.0.0`. It does not reach a port bound only on `127.0.0.1`.

Caddy's HTTP port is `8080`. A service published on host `8080` is proxied to Caddy itself. The browser reports that the page is not redirecting properly.

## Uptime Kuma

The widget URL is `http://{{HOMEPAGE_VAR_NAS_LAN_IP}}:3004` with slug `home`. The unit publishes `${site.networking.ingress.host.ip}:3004:3001`, not `127.0.0.1:3004`.

`http://uptime-kuma:3001` answers from `wget` inside Homepage and still fails in the widget. An empty `heartbeatList` for slug `home` is a status page with no monitors, not a connection error.

## Scrutiny

Listing `scrutiny` also places `scrutiny-collector` on that host (`ansible/lib/topology.py`). The UI stays rootless and is published on host `8087` (container `8080`). Caddy proxies `127.0.0.1:8087`. The collector is rootful, host netns, `--privileged`, with `/dev` and `/run/udev`. It posts to `http://127.0.0.1:8087`. It has no web port, so Caddy does not publish it.

Rootless `smartctl` can open `/dev/sda` and still cannot send ATA pass-through (`Operation not permitted`). It reports the disk as SCSI with no SMART data. Scrutiny stores that as a failed device (`device_status` 1) even when `smartctl` on the host says `PASSED`. The web container's collector and cron are replaced with stubs that exit (`components/scrutiny/collector-once.run`, `cron.run`).

A later successful ATA collect does not update that row. The UUID includes the protocol, so the same WWN appears twice: failed SCSI and passed ATA. Delete the SCSI registration (`DELETE /api/device/<scrutiny_uuid>` on the web port). The rootless collector must stay disabled or it will register the SCSI copy again.

## PeaNUT

The image has no `/config/settings.yml`. Bind-mounting the catalog file there makes crun exit 127: `open .../merged/config/settings.yml: No such file or directory` and `OCI runtime attempted to invoke a command that was not found`. Host, port, username, and password come from the unit environment. The data volume is `${appdata}/peanut:/config` only.

The UI listens on `0.0.0.0:8092` (`WEB_HOST=0.0.0.0`). `WEB_HOST=127.0.0.1` hangs the HTML renderer. Do not use port `8080`. Homepage uses `http://{{HOMEPAGE_VAR_HOST_LOOPBACK}}:8092` and `key: ups`. That key is the NUT section name. `/api/v1/devices` returns 500 when nothing is listening on `127.0.0.1:3493`.

`nut-server` and `nut-client` are not enough. SET writes `MODE=netserver`, `LISTEN 127.0.0.1 3493`, a `usbhid-ups` section named `ups` from `resources.usb` where `type: ups` (`vendorid` / `productid` from `id`), and user `peanut` with `secrets.peanut.nut_remote_password`. CyberPower `0764` also sets `override.battery.charge.low = 30`. Then it starts `nut-driver@ups` and `nut-server`. Ansible's systemd result has no `ActiveState`; the driver can be active while that field is empty. Check `systemctl is-active nut-driver@ups`. The driver takes a few seconds to claim the USB device and still succeeds.

## CaddyManager

The backend runs as uid 1000 (`node`) in a rootless pod. Without `UserNS=keep-id`, that uid is not the workload user, `/app/data` is not writable, and SQLite fails with `unable to open database file`. The pod never creates the first user.

The admin API is Caddy on the host, port `2019`. `127.0.0.1:2019` inside the pod is not that listener. `CADDY_SANDBOX_URL` is `http://169.254.1.2:2019`. The generated Caddyfile already allows that origin.

The image creates `admin` / `caddyrocks` when the users table is empty. Change that password after login. The vhost is `https://ingress.<domain>`, behind Authelia, then this login.
