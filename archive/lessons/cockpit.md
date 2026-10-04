# Cockpit: start, stop, and restart Quadlets

Working state when `hosts[].admin-gui` is enabled. SET installs it. Do not SSH a fix onto the host.

## The ⋮ menu only offers Commit

Workloads are Quadlets. Debian 13's `cockpit-podman` (108) lists them and keeps Commit. It withholds start, stop, and restart because stopping a Quadlet removes the container; systemd owns the unit. A running row may also show Pause.

Version 116 and later put Start, Stop, and Restart on that menu and run them with `systemctl`, including `systemctl --user` for the logged-in workload user. Debian 13 gets this from `trixie-backports` (131). Ubuntu 24.04 gets it from `noble-backports` (124). Log in as the workload user. Those containers are rootless and belong to that session.

Stopping a Quadlet stops its unit. The row stays, so Start is still there.

## Apt rejects `trixie-backports` as the default release

The source file can already be on disk. Apt still errors `The value 'trixie-backports' is invalid for APT::Default-Release as such a release is not available in the sources` when the install task sets that release and updates the cache together. The cache does not contain the release until a plain `apt update` has read the new source.

SET writes `/etc/apt/sources.list.d/site-cockpit-backports.sources`, updates the cache with no default release, then installs `cockpit-podman` from `<release>-backports`. `cockpit-storaged` is installed in the same role so the Storage page is present.

`ansible/lib/diff.py` hashes `ansible/roles/cockpit/tasks/main.yml` into the `admin_gui` fingerprint. A role edit re-runs that section on the next SET.

## "Inconsistent filesystem mount" on the data disk

Storage warns that the filesystem is mounted on `/appdata` but will not be mounted after the next boot. Cockpit reads UDisks `Configuration`, which is `/etc/fstab` only. The disk is an enabled systemd unit, `mnt-site-<id>.mount` at `/mnt/site/<id>`, plus bind units for `/appdata`, `/groups`, and `/users`. Those do mount on boot. With no fstab line, UDisks lists the bind `/appdata` first and Cockpit reports that path.

Do not use the warning's "Mount automatically on `/appdata` on boot" action. That writes the whole filesystem at `/appdata`.

SET writes a matching `UUID=` line for `/mnt/site/<id>` (`defaults,nofail`). The systemd unit still performs the mount. The fstab line clears the warning. `ansible/lib/diff.py` hashes `ansible/roles/storage/tasks/main.yml` into the `storage` fingerprint, so a role edit re-runs that section on the next SET.

## Services shows "Failed to start" for `sssd-nss.socket` and `sssd-pam.socket`

`sssd.service` is running. Its config lists `services = nss, pam`, so those responders are already children of that service. Debian also enables the matching sockets and starts them with `sssd.service` (`WantedBy=sssd.service`). Each socket then exits 17: socket activation and the `services` line cannot both apply. Cockpit lists that failed result.

Stopping the sockets does not clear `ActiveState=failed`. `systemctl reset-failed` does. After a stop, the units may already be unloaded, and `reset-failed` then exits 1 with "not loaded". That is success.

SET disables and stops both sockets, then resets the failed result and ignores "not loaded". `ansible/lib/diff.py` hashes `ansible/roles/identity/tasks/sssd.yml` and `ansible/roles/directory/tasks/access.yml` into the `users` fingerprint.
