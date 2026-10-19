/* Files in components/homepage/images/icons, served at /images/icons. */
function icon(name) {
  return "/images/icons/" + name;
}

/* Host label from the forward-auth redirect, mapped to the Homepage icon. */
/* Display names match the Homepage service tiles. */
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

function serviceForHost(hostname) {
  const row = SERVICES[hostname];
  return row ? { src: icon(row[0]), name: row[1] } : null;
}

function serviceForRedirect() {
  const rd = new URLSearchParams(location.search).get("rd");
  if (rd) {
    try {
      const fromRedirect = serviceForHost(new URL(rd).hostname);
      if (fromRedirect) return fromRedirect;
    } catch (e) {
      /* fall through to this host */
    }
  }
  return serviceForHost(location.hostname);
}

function swapLogo(src) {
  const stage = document.getElementById("first-factor-stage");
  const slot = stage && stage.querySelector("img[alt='Logo'], img[src*='logo.png'], svg.w-16");
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
  encloseContent(stage);
  return true;
}

function encloseContent(stage) {
  let content = stage.querySelector(":scope > .portal-content");
  if (!content) {
    content = document.createElement("div");
    content.className = "portal-content";
    const footer = stage.querySelector(":scope > .footer-bar");
    stage.insertBefore(content, footer);
  }
  for (const el of [...stage.children]) {
    if (
      el === content ||
      el.classList.contains("header-bar") ||
      el.classList.contains("footer-bar")
    ) {
      continue;
    }
    content.appendChild(el);
  }
}

function pinService() {
  const stage = document.getElementById("first-factor-stage");
  if (!stage || !stage.querySelector("#username-textfield")) return;
  if (stage.querySelector("[data-portal-icon]")) return;
  const service = serviceForRedirect();
  if (!service) return;
  const img = swapLogo(service.src);
  if (!img) return;
  placeTitle(img, service.name);
}

const homeObserver = new MutationObserver(() => {
  const stage = document.getElementById("first-factor-stage");
  if (!stage) return;
  if (!stage.querySelector("a.home-button")) placeHome();
  else encloseContent(stage);
  pinService();
});
homeObserver.observe(document.documentElement, { childList: true, subtree: true });
placeHome();
pinService();
