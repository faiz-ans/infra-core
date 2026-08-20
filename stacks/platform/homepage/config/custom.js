(() => {
  const apply = (url) => {
    const el = document.getElementById("background");
    if (!el || !url) return false;
    const current = el.style.backgroundImage;
    if (current && current.includes("url(")) {
      el.style.backgroundImage = current.replace(
        /url\((['"]?)[^'")]+(['"]?)\)/,
        `url("${url}")`,
      );
    } else {
      el.style.backgroundImage = `url("${url}")`;
    }
    el.style.backgroundSize = "cover";
    el.style.backgroundPosition = "center";
    return true;
  };

  const run = async () => {
    let list;
    try {
      const res = await fetch("/images/backgrounds.json", { cache: "no-store" });
      list = await res.json();
    } catch {
      return;
    }
    if (!Array.isArray(list) || list.length === 0) return;
    const url = list[Math.floor(Math.random() * list.length)];
    if (apply(url)) return;
    const obs = new MutationObserver(() => {
      if (apply(url)) obs.disconnect();
    });
    obs.observe(document.documentElement, { childList: true, subtree: true });
  };

  run();
})();
