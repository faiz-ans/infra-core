/* ARCHIVED — not loaded. Merge into config/custom.js to re-enable.
 * Flip Glances / Pi-hole between NAS and HTPC; customize Glances metric:info tile.
 */

// Add to ICON_SVG:
// Flip: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M360-120H200q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h160v80H200v560h160v80Zm80 80v-880h80v880h-80Zm160-80v-80h80v80h-80Zm0-640v-80h80v80h-80Zm160 640v-80h80q0 33-23.5 56.5T760-120Zm0-160v-80h80v80h-80Zm0-160v-80h80v80h-80Zm0-160v-80h80v80h-80Zm0-160v-80q33 0 56.5 23.5T840-760h-80Z"/></svg>',

const FLIP_FADE_MS = 400;
const FLIP_SIZE_MS = 300;

const FLIP_GROUPS = [
  {
    id: "glances",
    label: "Glances",
    storageKey: "homepage-flip-glances",
    defaultNode: "nas",
    nodes: [
      { id: "nas", name: "Glances", nodeLabel: "NAS" },
      { id: "htpc", name: "Glances HTPC", nodeLabel: "HTPC" },
    ],
  },
  {
    id: "pihole",
    label: "Pi-hole",
    storageKey: "homepage-flip-pihole",
    defaultNode: "nas",
    nodes: [
      { id: "nas", name: "Pi-hole", nodeLabel: "NAS" },
      { id: "htpc", name: "Pi-hole HTPC", nodeLabel: "HTPC" },
    ],
  },
];

let flipAnimating = false;

function findServiceByName(name) {
  return document.querySelector(`li.service[data-name="${CSS.escape(name)}"]`);
}

function getFlipNodeId(group) {
  const stored = localStorage.getItem(group.storageKey);
  if (group.nodes.some((n) => n.id === stored)) return stored;
  return group.defaultNode;
}

function setFlipNodeId(group, nodeId) {
  localStorage.setItem(group.storageKey, nodeId);
}

function nextFlipNode(group, currentId) {
  const idx = group.nodes.findIndex((n) => n.id === currentId);
  return group.nodes[(idx + 1) % group.nodes.length];
}

function flipDisplayTitle(group, nodeId) {
  const base = group.label.replace(/ \(2\)$/, "");
  return nodeId === group.defaultNode ? base : `${base} (2)`;
}

function setServiceTitle(li, title) {
  const nameEl = li.querySelector(".service-name");
  if (!nameEl) return;

  const desc = nameEl.querySelector(".service-description");
  let titleEl = nameEl.querySelector(".homepage-flip-title");

  if (!titleEl) {
    for (const node of [...nameEl.childNodes]) {
      if (node.nodeType === Node.TEXT_NODE) node.remove();
    }
    titleEl = document.createElement("span");
    titleEl.className = "homepage-flip-title block";
    nameEl.insertBefore(titleEl, desc || null);
  }

  if (titleEl.textContent !== title) titleEl.textContent = title;
}

function setServiceDescription(li, text) {
  const desc = li.querySelector(".service-description");
  if (desc) desc.textContent = text;
}

function getWidgetRoot(li) {
  return li.querySelector(".service-container");
}

function resolveFlipItems(group) {
  return group.nodes
    .map((node) => ({ node, li: findServiceByName(node.name) }))
    .filter((x) => x.li);
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function ensureFlipButton(li, group, currentNode) {
  const tags = li.querySelector(".service-tags");
  if (!tags) return;

  let btn = tags.querySelector(".homepage-flip-btn");
  const next = nextFlipNode(group, currentNode.id);
  const label = `Switch to ${next.nodeLabel}`;

  if (!btn) {
    btn = document.createElement("button");
    btn.type = "button";
    btn.className =
      "homepage-flip-btn shrink-0 flex items-center justify-center cursor-pointer service-tag";
    btn.innerHTML =
      `<div class="homepage-flip-hit hover:bg-theme-500/10 dark:hover:bg-theme-900/20 rounded-b-[3px]">${ICON_SVG.Flip}</div>`;
    btn.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      animateFlip(group);
    });
    const status = tags.querySelector(".service-container-stats");
    if (status) {
      tags.insertBefore(btn, status);
    } else {
      tags.appendChild(btn);
    }
  } else {
    const hit = btn.querySelector(".homepage-flip-hit");
    if (hit) {
      hit.classList.remove("p-4", "flex", "items-center", "justify-center");
    }
  }

  if (btn.getAttribute("data-next") !== next.id) {
    btn.setAttribute("data-next", next.id);
    btn.setAttribute("aria-label", label);
    btn.setAttribute("title", label);
  }
}

function styleGlancesInfoBoxes() {
  document.querySelectorAll(".service-container.chart").forEach((el) => {
    el.classList.add(
      "bg-theme-200/50",
      "dark:bg-theme-900/20",
      "rounded-sm",
      "m-1",
    );
    el.querySelectorAll(".absolute.z-20, .absolute.z-20 div").forEach((node) => {
      node.classList.add("font-thin", "text-xs");
      node.classList.remove(
        "text-sm",
        "text-[0.6rem]",
        "opacity-50",
        "opacity-75",
      );
    });
    el.querySelectorAll('[class*="-top-6"] div').forEach((node) => {
      node.classList.remove("font-thin");
      node.classList.add("font-bold");
    });
    const hash = el.querySelector(".bottom-3.left-2 > div:last-child");
    if (hash) hash.classList.remove("font-thin");
    ensureGlancesCopy(el);
  });
}

function glancesInfoCopyText(el) {
  const parts = [];
  const device = el.querySelector('[class*="-top-6"]');
  if (device) {
    device.querySelectorAll(":scope > div").forEach((d) => {
      const t = (d.textContent || "").trim();
      if (t) parts.push(t);
    });
  }
  const os = el.querySelector(".bottom-3.left-2");
  if (os) {
    os.querySelectorAll(":scope > div").forEach((d) => {
      const t = (d.textContent || "").trim();
      if (t) parts.push(t);
    });
  }
  return parts.join(" ");
}

function ensureGlancesCopy(el) {
  if (el.dataset.copyBound === "1") return;
  el.dataset.copyBound = "1";
  el.setAttribute("role", "button");
  el.setAttribute("tabindex", "0");
  el.setAttribute("title", "Copy system info");
  el.setAttribute("aria-label", "Copy system info");

  const copy = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const text = glancesInfoCopyText(el);
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      el.setAttribute("title", "Copied");
      el.classList.remove("homepage-glances-copied");
      void el.offsetWidth;
      el.classList.add("homepage-glances-copied");
      const clear = () => {
        el.classList.remove("homepage-glances-copied");
        el.setAttribute("title", "Copy system info");
      };
      el.addEventListener("animationend", clear, { once: true });
      setTimeout(clear, 700);
    } catch (_) {
      el.setAttribute("title", "Copy failed");
      setTimeout(() => el.setAttribute("title", "Copy system info"), 1200);
    }
  };

  el.addEventListener("pointerdown", copy);
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      copy(e);
    }
  });
}

function applyFlipGroup(group, { fadeIn = false } = {}) {
  const items = resolveFlipItems(group);
  if (items.length < 2) return;

  const currentId = getFlipNodeId(group);
  const current = items.find((x) => x.node.id === currentId) || items[0];

  for (const { node, li } of items) {
    const active = node.id === current.node.id;
    li.classList.add("homepage-flip-member");
    li.style.removeProperty("grid-area");
    li.classList.toggle("homepage-flip-hidden", !active);
    li.classList.toggle("homepage-flip-active", active);

    const widget = getWidgetRoot(li);
    if (widget) {
      widget.classList.add("homepage-flip-widget");
      if (!active) {
        widget.style.opacity = "";
      }
    }

    if (!active) continue;

    const displayTitle = flipDisplayTitle(group, current.node.id);
    setServiceTitle(li, displayTitle);
    const descEl = li.querySelector(".service-description");
    if (descEl) {
      const baseDesc = (
        descEl.getAttribute("data-base") ||
        (descEl.textContent || "").replace(/\s*·\s*(NAS|HTPC)\s*$/i, "")
      ).trim();
      if (baseDesc && !descEl.getAttribute("data-base")) {
        descEl.setAttribute("data-base", baseDesc);
      }
      if (baseDesc) setServiceDescription(li, baseDesc);
    }
    ensureFlipButton(li, group, node);

    if (widget && fadeIn) {
      widget.style.opacity = "0";
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          widget.style.opacity = "1";
        });
      });
    }
  }
}

function enhanceFlipGroups() {
  for (const group of FLIP_GROUPS) {
    applyFlipGroup(group);
  }
}

async function animateFlip(group) {
  if (flipAnimating) return;
  const items = resolveFlipItems(group);
  if (items.length < 2) return;

  flipAnimating = true;
  try {
    const currentId = getFlipNodeId(group);
    const current = items.find((x) => x.node.id === currentId) || items[0];
    const nextNode = nextFlipNode(group, current.node.id);
    const next = items.find((x) => x.node.id === nextNode.id) || items[0];
    const curCard = current.li.querySelector(".service-card");
    const fromH = curCard ? curCard.getBoundingClientRect().height : 0;
    const outWidget = getWidgetRoot(current.li);

    if (outWidget) {
      outWidget.classList.add("homepage-flip-widget");
      outWidget.style.opacity = "1";
      void outWidget.offsetHeight;
      outWidget.style.opacity = "0";
      await wait(FLIP_FADE_MS);
    }

    setFlipNodeId(group, nextNode.id);
    applyFlipGroup(group, { fadeIn: true });
    styleGlancesInfoBoxes();

    const nextCard = next.li.querySelector(".service-card");
    if (nextCard && fromH > 0) {
      nextCard.style.transition = "none";
      nextCard.style.height = "auto";
      nextCard.style.overflow = "hidden";
      const toH = nextCard.getBoundingClientRect().height;
      nextCard.style.height = `${fromH}px`;
      void nextCard.offsetHeight;
      nextCard.style.transition = `height ${FLIP_SIZE_MS}ms ease-in-out`;
      nextCard.style.height = `${toH}px`;
      await wait(Math.max(FLIP_FADE_MS, FLIP_SIZE_MS));
      nextCard.style.height = "";
      nextCard.style.overflow = "";
      nextCard.style.transition = "";
    } else {
      await wait(FLIP_FADE_MS);
    }
  } finally {
    flipAnimating = false;
  }
}

// In enhance(): styleGlancesInfoBoxes(); if (!flipAnimating) enhanceFlipGroups();
// In scheduleEnhance(): also gate on flipAnimating
// In MutationObserver ignore: .homepage-flip-btn, .homepage-flip-title
