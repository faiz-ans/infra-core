/* Files in components/homepage/images/icons, served at /images/icons. */
function icon(name) {
  return "/images/icons/" + name;
}

/* Host label from the forward-auth redirect, mapped to the Homepage icon. */
/* Display names match the Homepage service tiles. */
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
  "remote.home.lan": ["rustdesk.svg", "RustDesk"],
  "rustdesk.home.lan": ["rustdesk.svg", "RustDesk"],
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

function serviceForRedirect() {
  const rd = new URLSearchParams(location.search).get("rd");
  if (!rd) return null;
  try {
    const row = SERVICES[new URL(rd).hostname];
    return row ? { src: icon(row[0]), name: row[1] } : null;
  } catch (e) {
    return null;
  }
}

function swapLogo(src) {
  const slot = document.querySelector("img[alt='Logo'], img[src*='logo.png'], svg.w-16");
  if (!slot) return null;
  if (slot.dataset.portalIcon === src) return slot;
  const img = document.createElement("img");
  img.src = src;
  img.alt = "Logo";
  img.dataset.portalIcon = src;
  img.className = "mx-auto my-2 w-16";
  img.style.cssText = "display:block;width:4rem;height:4rem;object-fit:contain;margin:0.5rem auto";
  slot.replaceWith(img);
  return img;
}

function placeTitle(img, name) {
  const parent = img.parentElement;
  if (!parent) return;
  let title = parent.querySelector(".portal-service-title");
  if (!title) {
    title = document.createElement("div");
    title.className = "portal-service-title";
    img.insertAdjacentElement("afterend", title);
  }
  title.textContent = name;
}

function placeHome() {
  const stage = document.getElementById("first-factor-stage");
  if (!stage || stage.querySelector("a.home-button")) return false;
  const headerBar = document.createElement("div");
  headerBar.className = "header-bar";
  const footerBar = document.createElement("div");
  footerBar.className = "footer-bar";
  const link = document.createElement("a");
  link.className = "home-button";
  link.href = "https://dash.home.lan/";
  link.setAttribute("aria-label", "Home");
  link.title = "Home";
  link.innerHTML =
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" aria-hidden="true"><path d="M240-200h120v-240h240v240h120v-360L480-740 240-560v360Zm-80 80v-480l320-240 320 240v480H520v-240h-80v240H160Zm320-350Z"/></svg>';
  footerBar.appendChild(link);
  stage.prepend(headerBar);
  stage.appendChild(footerBar);
  return true;
}

if (!placeHome()) {
  const homeObserver = new MutationObserver(() => {
    if (placeHome()) homeObserver.disconnect();
  });
  homeObserver.observe(document.documentElement, { childList: true, subtree: true });
}

const service = serviceForRedirect();
if (service) {
  const pin = () => {
    const img = swapLogo(service.src);
    if (!img) return false;
    placeTitle(img, service.name);
    return true;
  };
  if (!pin()) {
    const observer = new MutationObserver(() => {
      if (pin()) observer.disconnect();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }
}
