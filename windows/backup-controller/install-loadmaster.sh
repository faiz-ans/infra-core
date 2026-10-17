#!/bin/sh
# Install the backup controller for the loadmaster user on Core.
# This is not part of GET/SET. Run it as loadmaster:
#   sh windows/backup-controller/install-loadmaster.sh
set -eu

src=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
dest="${HOME}/.local/lib/backup-controller"
unit_dir="${HOME}/.config/systemd/user"
key="${HOME}/.ssh/backup_mantle"

mkdir -p "$dest" "$unit_dir" "${HOME}/.ssh"
install -m 755 "$src/backup_controller.py" "$dest/backup_controller.py"
install -m 755 "$src/backup-remote" "$dest/backup-remote"
install -m 644 "$src/backup-disk.ps1" "$dest/backup-disk.ps1"
install -m 644 "$src/backup-disk.vbs" "$dest/backup-disk.vbs"
install -m 644 "$src/install-surface.ps1" "$dest/install-surface.ps1"
install -m 644 "$src/backup-controller.service" "$unit_dir/backup-controller.service"

if [ ! -f "$key" ]; then
  ssh-keygen -t ed25519 -f "$key" -N "" -C loadmaster-backup
fi
chmod 700 "${HOME}/.ssh"
chmod 600 "$key"

systemctl --user daemon-reload

pub=$(cat "${key}.pub")
printf '\nFiles are installed. Finish Surface and Mantle before starting the service.\n'
printf 'Starting it takes 127.0.0.1:9898, which is where Caddy sends backup.home.lan.\n\n'
printf 'On Surface, elevated, with D: online, from a copy of this directory:\n'
printf '  powershell -ExecutionPolicy Bypass -File install-surface.ps1\n\n'
printf 'On Mantle, as root, install the forced command:\n'
printf '  install -m 755 -o root -g root %s/backup-remote /usr/local/sbin/backup-remote\n\n' "$dest"
printf 'Pin Loadmaster'\''s key in ~pilot/.ssh/authorized_keys on Mantle:\n'
printf '  restrict,command="/usr/local/sbin/backup-remote" %s\n\n' "$pub"
printf 'Record Mantle'\''s host key:\n'
printf '  ssh-keyscan -H 192.168.1.111 >> %s/.ssh/backup_mantle_known_hosts\n\n' "$HOME"
printf 'Linger, so the 02:55 wake runs without a login (needs root):\n'
printf '  sudo loginctl enable-linger loadmaster\n\n'
printf 'Then start it:\n'
printf '  systemctl --user enable --now backup-controller.service\n'
