# Sablier

Sablier is the standalone server `docker.io/sablierapp/sablier:1.18.0`. Caddy stays stock `caddy:2`. There is no xcaddy plugin. `networking.ingress.plugins: [sablier]` means: place that server, then have Caddy call it.

Caddy `forward_auth` hits `/api/strategies/blocking?names=<unit>.service`. Blocking holds the request until the unit is up, or for about a minute. It is not the idle timer. Idle time is the session, default 5 minutes, refreshed by each visit. The other strategies are `dynamic` (a waiting page) and `poke` (start and do not wait). This site does not use them.

The name in that URL is the systemd unit (`linkding.service`), not the Podman container name. Quadlet starts containers with `--rm`. Stopping one deletes it. The Podman provider can only start a container that still exists, so the next visit returns `no such container`. The systemd provider runs `systemctl --user start`, and Quadlet creates the container again.

Opt in from `site.yaml`. A single `.container` uses `container.labels`. A pod uses `pod.spec.containers[].labels` with `sablier.enable: true`. SET writes `[X-Sablier]` / `Enable=true` on the Quadlet file. Quadlet copies that section into the generated unit. The systemd provider will not start a unit without it. A Podman `Label=` does not count.

Sablier reads that unit file from the path systemd returns, `/run/user/<uid>/systemd/generator/<name>.service`. The container must mount that directory as well as the user bus socket. Without the mount, D-Bus answers and `stat` fails with `no such file or directory`. While that fails, Sablier never stops anything, so Homepage keeps showing Running. A container Quadlet already removed shows Not Found.

Homepage dots come from `docker-proxy`, not from Sablier. An open Homepage tab does not refresh the idle session. After a real stop the dot goes away, because the container is gone until the next visit.

Authelia, Caddy, and Sablier itself are not woken. Each Sablier only manages Quadlets of the same host and workload user.
