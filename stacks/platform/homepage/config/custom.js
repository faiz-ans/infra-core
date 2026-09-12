/* Move Apps/System tabs into the header (after weather) as Material icon buttons.
 * Also normalize glances uptime "1 day" → "1d" (Homepage only rewrites plural "days").
 * Footer: glances visibility toggle + scroll-to-top (before refresh).
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
  };

  const TAB_BY_ID = {
    "Apps-tab": "Apps",
    "System-tab": "System",
  };

  const GLANCES_VISIBLE_KEY = "homepage-glances-visible";

  let scheduled = false;

  function glancesVisible() {
    // Default off for first visit; persist once the user toggles.
    return localStorage.getItem(GLANCES_VISIBLE_KEY) === "true";
  }

  function applyGlancesVisibility() {
    const visible = glancesVisible();
    document.documentElement.classList.toggle("glances-hidden", !visible);

    const btn = document.getElementById("glances-toggle");
    if (!btn) return;

    // Avoid rewriting DOM every tick — that cancels clicks (esp. Firefox).
    if (btn.getAttribute("data-visible") === String(visible)) return;

    btn.setAttribute("data-visible", String(visible));
    btn.setAttribute("aria-pressed", visible ? "true" : "false");
    btn.setAttribute("aria-label", visible ? "Hide glances" : "Show glances");
    btn.setAttribute("title", visible ? "Hide glances" : "Show glances");
    btn.innerHTML = visible ? ICON_SVG.BarChart : ICON_SVG.BarChartOff;
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
        svg: visible ? ICON_SVG.BarChart : ICON_SVG.BarChartOff,
        label: visible ? "Hide glances" : "Show glances",
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
        label: "Scroll to top",
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

  function enhance() {
    enhanceTabs();
    normalizeGlancesUptime();
    syncGlancesStacked();
    syncDatetimeWrapComma();
    ensureFooterControls();
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

  const observer = new MutationObserver((mutations) => {
    // Ignore churn from our own footer icon updates
    for (const m of mutations) {
      const t = m.target;
      if (
        t &&
        (t.id === "glances-toggle" ||
          t.id === "scroll-top" ||
          (t.closest && t.closest("#glances-toggle, #scroll-top")))
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
