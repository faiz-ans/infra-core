/* Copies of components/homepage/images/icons, placed next to this theme at render. */
function icon(name) {
  return "images/icons/" + name;
}

/* Display names match the Homepage service tiles. Keep in step with portal/login.js. */
const SERVICES = {
  "auth.home.lan": ["authelia.svg", "Authelia"],
  "auto.home.lan": ["home-assistant.svg", "Home Assistant"],
  "backup.home.lan": ["backrest.svg", "Backrest"],
  "cloud.home.lan": ["opencloud.svg", "OpenCloud"],
  "convert.home.lan": ["transmute.svg", "Transmute"],
  "disks.home.lan": ["scrutiny.svg", "Scrutiny"],
  "down.home.lan": ["qbittorrent.svg", "qBittorrent"],
  "dns.home.lan": ["pi-hole.svg", "Pi-hole"],
  "dns2.home.lan": ["pi-hole.svg", "Pi-hole"],
  "flow.home.lan": ["n8n.svg", "n8n"],
  "host.home.lan": ["glances.svg", "Glances"],
  "host2.home.lan": ["glances.svg", "Glances"],
  "indices.home.lan": ["prowlarr.svg", "Prowlarr"],
  "ingress.home.lan": ["caddy.svg", "Caddy"],
  "it.home.lan": ["it-tools.svg", "IT Tools"],
  "links.home.lan": ["linkding.svg", "Linkding"],
  "movies.home.lan": ["radarr.svg", "Radarr"],
  "notes.home.lan": ["jotty.svg", "Jotty"],
  "nvr.home.lan": ["frigate.svg", "Frigate"],
  "pass.home.lan": ["bitwarden.svg", "Vaultwarden"],
  "pdf.home.lan": ["bentopdf.svg", "BentoPDF"],
  "photos.home.lan": ["immich.svg", "Immich"],
  "read.home.lan": ["openreader.webp", "OpenReader"],
  "request.home.lan": ["seerr.svg", "Seerr"],
  "snip.home.lan": ["bytestash.svg", "ByteStash"],
  "sys.home.lan": ["cockpit.svg", "Cockpit"],
  "translate.home.lan": ["libretranslate.svg", "LibreTranslate"],
  "trips.home.lan": ["adventurelog.svg", "AdventureLog"],
  "tv.home.lan": ["sonarr.svg", "Sonarr"],
  "up.home.lan": ["uptime-kuma.svg", "Uptime Kuma"],
  "ups.home.lan": ["peanut.svg", "Peanut"],
  "users.home.lan": ["openldap.svg", "OpenLDAP"],
  "voice.home.lan": ["scriberr.svg", "Scriberr"],
  "vpn.home.lan": ["wireguard.svg", "WireGuard"],
  "watch.home.lan": ["jellyfin.svg", "Jellyfin"],
  "wifi.home.lan": ["linksys.svg", "Linksys EA8300"]
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
