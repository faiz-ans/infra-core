/* Copies of components/homepage/images/icons, placed next to this theme at render. */
function icon(name) {
  return "images/icons/" + name;
}

const ICONS = {
  "auth.home.lan": icon("authelia.svg"),
  "authelia.home.lan": icon("authelia.svg"),
  "cloud.home.lan": icon("opencloud.svg"),
  "opencloud.home.lan": icon("opencloud.svg"),
  "oc.home.lan": icon("opencloud.svg"),
  "notes.home.lan": icon("jotty.svg"),
  "jotty.home.lan": icon("jotty.svg"),
  "links.home.lan": icon("linkding.svg"),
  "linkding.home.lan": icon("linkding.svg"),
  "snips.home.lan": icon("bytestash.svg"),
  "snip.home.lan": icon("bytestash.svg"),
  "bytestash.home.lan": icon("bytestash.svg"),
  "pass.home.lan": icon("bitwarden.svg"),
  "vaultwarden.home.lan": icon("bitwarden.svg"),
  "pw.home.lan": icon("bitwarden.svg"),
  "photos.home.lan": icon("immich.svg"),
  "immich.home.lan": icon("immich.svg"),
  "gallery.home.lan": icon("immich.svg"),
  "pdf.home.lan": icon("bentopdf.svg"),
  "bentopdf.home.lan": icon("bentopdf.svg"),
  "it.home.lan": icon("it-tools.svg"),
  "tools.home.lan": icon("it-tools.svg"),
  "ups.home.lan": icon("peanut.svg"),
  "peanut.home.lan": icon("peanut.svg"),
  "sys.home.lan": icon("cockpit.svg"),
  "cockpit.home.lan": icon("cockpit.svg"),
  "users.home.lan": icon("openldap.svg"),
  "ldap.home.lan": icon("openldap.svg"),
  "remote.home.lan": icon("rustdesk.svg"),
  "rustdesk.home.lan": icon("rustdesk.svg"),
  "dns.home.lan": icon("pi-hole.svg"),
  "pihole.home.lan": icon("pi-hole.svg"),
  "dns2.home.lan": icon("pi-hole.svg"),
  "pihole2.home.lan": icon("pi-hole.svg"),
  "ingress.home.lan": icon("caddy.svg"),
  "caddymanager.home.lan": icon("caddy.svg"),
  "caddy.home.lan": icon("caddy.svg"),
  "vpn.home.lan": icon("wireguard.svg"),
  "wireguard.home.lan": icon("wireguard.svg"),
  "wg.home.lan": icon("wireguard.svg"),
  "wifi.home.lan": icon("linksys.svg"),
  "up.home.lan": icon("uptime-kuma.svg"),
  "uptime.home.lan": icon("uptime-kuma.svg"),
  "kuma.home.lan": icon("uptime-kuma.svg"),
  "disks.home.lan": icon("scrutiny.svg"),
  "scrutiny.home.lan": icon("scrutiny.svg"),
};

const src = ICONS[location.hostname];
const logo = document.querySelector(".logo");
if (logo && src) logo.src = src;
else if (logo) logo.remove();
