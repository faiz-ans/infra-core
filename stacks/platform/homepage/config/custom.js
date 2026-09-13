/* Move Apps/System tabs into the header (after weather) as Material icon buttons.
 * Also normalize glances uptime "1 day" → "1d" (Homepage only rewrites plural "days").
 * Footer: glances visibility toggle + scroll-to-top (before refresh).
 * Service tiles: flip Glances / Pi-hole between NAS and HTPC instances.
 */
(function () {
  const ICON_SVG = {
    Apps:
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M4 8h4V4H4v4zm6 12h4v-4h-4v4zm-6 0h4v-4H4v4zm0-6h4v-4H4v4zm6 0h4v-4h-4v4zm6-10v4h4V4h-4zm-6 4h4V4h-4v4zm6 6h4v-4h-4v4zm0 6h4v-4h-4v4z"/></svg>',
    System:
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32a.5.5 0 0 0-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.5.5 0 0 0-.48-.41h-3.84a.5.5 0 0 0-.48.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.5.5 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.07.63-.07.94s.02.63.06.94l-2.03 1.58a.5.5 0 0 0-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4a3.6 3.6 0 0 1 0 7.2z"/></svg>',
    BarChart:
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" fill="currentColor" class="text-theme-800 dark:text-theme-200 w-6 h-6 cursor-pointer" aria-hidden="true"><path d="M640-160v-280h160v280H640Zm-240 0v-640h160v640H400Zm-240 0v-440h160v440H160Z"/></svg>',
    BarChartOff:
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" fill="currentColor" class="text-theme-800 dark:text-theme-200 w-6 h-6 cursor-pointer" aria-hidden="true"><path d="M160-160v-440h160v440H160Zm240 0v-400l160 160v240H400Zm160-354L400-674v-126h160v286Zm240 240L640-434v-6h160v166Zm-9 219L55-791l57-57 736 736-57 57Z"/></svg>',
    ArrowUpward:
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="text-theme-800 dark:text-theme-200 w-6 h-6 cursor-pointer" aria-hidden="true"><path d="M4 12l1.41 1.41L11 7.83V20h2V7.83l5.58 5.59L20 12l-8-8z"/></svg>',
    // Material Symbols Outlined "flip"
    Flip:
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M360-120H200q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h160v80H200v560h160v80Zm80 80v-880h80v880h-80Zm160-80v-80h80v80h-80Zm0-640v-80h80v80h-80Zm160 640v-80h80q0 33-23.5 56.5T760-120Zm0-160v-80h80v80h-80Zm0-160v-80h80v80h-80Zm0-160v-80h80v80h-80Zm0-160v-80q33 0 56.5 23.5T840-760h-80Z"/></svg>',
  };

  const FLIP_FADE_MS = 400;
  // Match Homepage service-stats: transition-all duration-300 ease-in-out
  const FLIP_SIZE_MS = 300;

  const TAB_BY_ID = {
    "Apps-tab": "Apps",
    "System-tab": "System",
  };

  const GLANCES_VISIBLE_KEY = "homepage-glances-visible";

  // Paired service tiles: one visible at a time; flip cycles NAS ↔ HTPC.
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

  let scheduled = false;
  let flipAnimating = false;

  function glancesVisible() {
    // Default off for first visit; persist once the user toggles.
    return localStorage.getItem(GLANCES_VISIBLE_KEY) === "true";
  }

  function applyGlancesVisibility() {
    const visible = glancesVisible();
    document.documentElement.classList.toggle("glances-visible", visible);

    const btn = document.getElementById("glances-toggle");
    if (!btn) return;

    // Avoid rewriting DOM every tick — that cancels clicks (esp. Firefox).
    if (btn.getAttribute("data-visible") === String(visible)) return;

    btn.setAttribute("data-visible", String(visible));
    btn.setAttribute("aria-pressed", visible ? "true" : "false");
    btn.setAttribute("aria-label", visible ? "Hide stats" : "Show stats");
    btn.setAttribute("title", visible ? "Hide stats" : "Show stats");
    btn.innerHTML = visible ? ICON_SVG.BarChartOff : ICON_SVG.BarChart;
  }

  function toggleGlancesVisible() {
    localStorage.setItem(
      GLANCES_VISIBLE_KEY,
      glancesVisible() ? "false" : "true",
    );
    applyGlancesVisibility();
  }

  function getScrollRoot() {
    return (
      document.getElementById("inner_wrapper") ||
      document.scrollingElement ||
      document.documentElement
    );
  }

  function scrollToTop() {
    getScrollRoot().scrollTo({ top: 0, behavior: "smooth" });
  }

  function createFooterControl(id, { svg, label, onClick }) {
    const wrap = document.createElement("div");
    wrap.id = id;
    wrap.className =
      "rounded-full flex align-middle self-center mr-3 homepage-footer-control";
    wrap.setAttribute("role", "button");
    wrap.setAttribute("tabindex", "0");
    wrap.setAttribute("aria-label", label);
    wrap.setAttribute("title", label);
    wrap.innerHTML = svg;
    // pointerdown is more reliable than click when observers rewrite nearby DOM
    wrap.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      onClick();
    });
    wrap.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onClick();
      }
    });
    return wrap;
  }

  function ensureFooterControls() {
    const revalidate = document.getElementById("revalidate");
    if (!revalidate || !revalidate.parentElement) return;

    let glancesBtn = document.getElementById("glances-toggle");
    if (!glancesBtn) {
      const visible = glancesVisible();
      glancesBtn = createFooterControl("glances-toggle", {
        svg: visible ? ICON_SVG.BarChartOff : ICON_SVG.BarChart,
        label: visible ? "Hide stats" : "Show stats",
        onClick: toggleGlancesVisible,
      });
      glancesBtn.setAttribute("data-visible", String(visible));
      glancesBtn.setAttribute("aria-pressed", visible ? "true" : "false");
      revalidate.parentElement.insertBefore(glancesBtn, revalidate);
    }

    let scrollBtn = document.getElementById("scroll-top");
    if (!scrollBtn) {
      scrollBtn = createFooterControl("scroll-top", {
        svg: ICON_SVG.ArrowUpward,
        label: "Back to top",
        onClick: scrollToTop,
      });
      revalidate.parentElement.insertBefore(scrollBtn, revalidate);
    }

    applyGlancesVisibility();
  }

  function iconifyButton(btn) {
    if (!btn || btn.querySelector("svg")) return;

    const name =
      TAB_BY_ID[btn.id] ||
      (btn.getAttribute("aria-label") || btn.textContent || "").trim();
    const svg = ICON_SVG[name];
    if (!svg) return;

    btn.setAttribute("aria-label", name);
    btn.setAttribute("title", name);
    btn.innerHTML = svg;
  }

  function enhanceTabs() {
    const tabs = document.getElementById("tabs");
    const right = document.getElementById("information-widgets-right");
    if (!tabs || !right) return;

    if (tabs.parentElement !== right) {
      right.appendChild(tabs);
    }

    tabs.querySelectorAll('button[role="tab"]').forEach(iconifyButton);
  }

  // Homepage: uptime.replace(" days,", "d") — misses singular "1 day,"
  function normalizeGlancesUptime() {
    document
      .querySelectorAll(
        "#widgets-wrap .information-widget-glances .information-widget-resource .pl-0\\.5",
      )
      .forEach((el) => {
        const text = el.textContent;
        if (!text || !/day/i.test(text)) return;
        const next = text.replace(/\s*days?,?\s*/i, "d ");
        if (next !== text) el.textContent = next;
      });
  }

  function syncGlancesStacked() {
    const wrap = document.getElementById("widgets-wrap");
    if (!wrap) return;
    const widgets = wrap.querySelectorAll(":scope > .information-widget-glances");
    const stacked =
      widgets.length >= 2 && widgets[0].offsetTop !== widgets[1].offsetTop;
    wrap.classList.toggle("glances-stacked", stacked);
  }

  // When datetime wraps to two lines, drop the comma between date and time.
  function syncDatetimeWrapComma() {
    const span = document.querySelector(
      ".information-widget-datetime span.tabular-nums",
    );
    if (!span) return;

    const text = span.textContent;
    if (!text) return;

    const styles = getComputedStyle(span);
    const lineHeight = parseFloat(styles.lineHeight);
    if (!lineHeight) return;

    const wrapped = span.getBoundingClientRect().height > lineHeight * 1.5;
    if (!wrapped) return;

    const next = text.replace(/,\s+(?=\d{1,2}:\d{2}\b)/, " ");
    if (next !== text) span.textContent = next;
  }

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

  function setServiceTitle(li, title) {
    const nameEl = li.querySelector(".service-name");
    if (!nameEl) return;
    for (const node of nameEl.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        const leading = (node.textContent.match(/^\s*/) || [""])[0];
        node.textContent = leading + title;
        return;
      }
    }
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
      // Match container-status button; hit target mirrors Status dot box size.
      btn.className =
        "homepage-flip-btn shrink-0 flex items-center justify-center cursor-pointer service-tag";
      btn.innerHTML =
        `<div class="homepage-flip-hit hover:bg-theme-500/10 dark:hover:bg-theme-900/20 rounded-b-[3px]">${ICON_SVG.Flip}</div>`;
      btn.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        animateFlip(group);
      });
      // Left of the container status indicator.
      const status = tags.querySelector(".service-container-stats");
      if (status) {
        tags.insertBefore(btn, status);
      } else {
        tags.appendChild(btn);
      }
    } else {
      // Migrate older markup that used p-4 (taller than the status square).
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
      // Same dark box as service-block widgets
      el.classList.add(
        "bg-theme-200/50",
        "dark:bg-theme-900/20",
        "rounded-sm",
        "m-1",
      );
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
        setTimeout(() => el.setAttribute("title", "Copy system info"), 1200);
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

      setServiceTitle(li, group.label);
      const descEl = li.querySelector(".service-description");
      const raw = (descEl?.textContent || "").trim();
      const baseDesc = (
        descEl?.getAttribute("data-base") ||
        raw.replace(/\s*·\s*(NAS|HTPC)\s*$/i, "")
      ).trim();
      if (descEl && !descEl.getAttribute("data-base") && baseDesc) {
        descEl.setAttribute("data-base", baseDesc);
      }
      setServiceDescription(
        li,
        baseDesc ? `${baseDesc} · ${node.nodeLabel}` : node.nodeLabel,
      );
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
        // Measure natural height, then animate from previous tile size
        // (same timing curve as status → service-stats expand).
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

  function enhance() {
    enhanceTabs();
    normalizeGlancesUptime();
    syncGlancesStacked();
    syncDatetimeWrapComma();
    ensureFooterControls();
    styleGlancesInfoBoxes();
    // Don't clobber mid-flip widget opacity / active card.
    if (!flipAnimating) enhanceFlipGroups();
  }

  function scheduleEnhance() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      enhance();
    });
  }

  // Apply persisted glances visibility before paint when possible
  applyGlancesVisibility();
  // Enable toggle animations only after the initial visibility is applied
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.documentElement.classList.add("glances-anim");
    });
  });

  const observer = new MutationObserver((mutations) => {
    // Ignore churn from our own footer / flip icon updates
    for (const m of mutations) {
      const t = m.target;
      if (
        t &&
        (t.id === "glances-toggle" ||
          t.id === "scroll-top" ||
          (t.closest &&
            t.closest("#glances-toggle, #scroll-top, .homepage-flip-btn")))
      ) {
        continue;
      }
      scheduleEnhance();
      return;
    }
  });
  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
  });

  window.addEventListener("resize", scheduleEnhance);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scheduleEnhance);
  } else {
    scheduleEnhance();
  }
})();
