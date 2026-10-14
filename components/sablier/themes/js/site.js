/* Copies of components/homepage/images/icons, placed next to this theme at render. */
function icon(name) {
  return "images/icons/" + name;
}

/* Display names match the Homepage service tiles. Keep in step with portal/login.js. */
const SERVICES = {
  "auth.home.lan": ["authelia.svg", "Authelia"],
  "authelia.home.lan": ["authelia.svg", "Authelia"],
  "cloud.home.lan": ["opencloud.svg", "OpenCloud"],
  "opencloud.home.lan": ["opencloud.svg", "OpenCloud"],
  "oc.home.lan": ["opencloud.svg", "OpenCloud"],
  "notes.home.lan": ["jotty.svg", "Jotty"],
  "jotty.home.lan": ["jotty.svg", "Jotty"],
  "links.home.lan": ["linkding.svg", "Linkding"],
  "linkding.home.lan": ["linkding.svg", "Linkding"],
  "snips.home.lan": ["bytestash.svg", "ByteStash"],
  "snip.home.lan": ["bytestash.svg", "ByteStash"],
  "bytestash.home.lan": ["bytestash.svg", "ByteStash"],
  "pass.home.lan": ["bitwarden.svg", "Vaultwarden"],
  "vaultwarden.home.lan": ["bitwarden.svg", "Vaultwarden"],
  "pw.home.lan": ["bitwarden.svg", "Vaultwarden"],
  "photos.home.lan": ["immich.svg", "Immich"],
  "immich.home.lan": ["immich.svg", "Immich"],
  "gallery.home.lan": ["immich.svg", "Immich"],
  "pdf.home.lan": ["bentopdf.svg", "BentoPDF"],
  "bentopdf.home.lan": ["bentopdf.svg", "BentoPDF"],
  "it.home.lan": ["it-tools.svg", "IT Tools"],
  "tools.home.lan": ["it-tools.svg", "IT Tools"],
  "ups.home.lan": ["peanut.svg", "Peanut"],
  "peanut.home.lan": ["peanut.svg", "Peanut"],
  "sys.home.lan": ["cockpit.svg", "Cockpit"],
  "cockpit.home.lan": ["cockpit.svg", "Cockpit"],
  "users.home.lan": ["openldap.svg", "OpenLDAP"],
  "ldap.home.lan": ["openldap.svg", "OpenLDAP"],
  "dns.home.lan": ["pi-hole.svg", "Pi-hole"],
  "pihole.home.lan": ["pi-hole.svg", "Pi-hole"],
  "dns2.home.lan": ["pi-hole.svg", "Pi-hole"],
  "pihole2.home.lan": ["pi-hole.svg", "Pi-hole"],
  "ingress.home.lan": ["caddy.svg", "Caddy"],
  "caddymanager.home.lan": ["caddy.svg", "Caddy"],
  "caddy.home.lan": ["caddy.svg", "Caddy"],
  "vpn.home.lan": ["wireguard.svg", "WireGuard"],
  "wireguard.home.lan": ["wireguard.svg", "WireGuard"],
  "wg.home.lan": ["wireguard.svg", "WireGuard"],
  "wifi.home.lan": ["linksys.svg", "Linksys EA8300"],
  "up.home.lan": ["uptime-kuma.svg", "Uptime Kuma"],
  "uptime.home.lan": ["uptime-kuma.svg", "Uptime Kuma"],
  "kuma.home.lan": ["uptime-kuma.svg", "Uptime Kuma"],
  "disks.home.lan": ["scrutiny.svg", "Scrutiny"],
  "scrutiny.home.lan": ["scrutiny.svg", "Scrutiny"],
};

const row = SERVICES[location.hostname];
const logo = document.querySelector(".logo");
const title = document.querySelector(".service-name");
if (logo && row) {
  logo.src = icon(row[0]);
  if (title) title.textContent = row[1];
} else if (logo) {
  logo.remove();
  if (title) title.remove();
}
