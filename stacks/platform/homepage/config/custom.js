(() => {
  // Fallback if /images/backgrounds.json is not served yet (needs a container restart).
  const FALLBACK = [
    "/images/o3uxqvbai6gh1.png",
    "/images/mgaoqgmu9pq61.jpg",
    "/images/1o07cxcm3mfh1.png",
  ];

  const pick = (list) => list[Math.floor(Math.random() * list.length)];

  const install = (url) => {
    let tag = document.getElementById("homepage-random-bg");
    if (!tag) {
      tag = document.createElement("style");
      tag.id = "homepage-random-bg";
      document.documentElement.appendChild(tag);
    }
    // !important so React re-renders of #background do not reset settings.yaml's image.
    tag.textContent =
      "#background{background-image:linear-gradient(rgb(var(--bg-color) / 0.5), rgb(var(--bg-color) / 0.5)), url(\"" +
      url +
      "\") !important;background-size:cover !important;background-position:center !important;}";
  };

  fetch("/images/backgrounds.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject()))
    .then((list) => (Array.isArray(list) && list.length ? list : FALLBACK))
    .catch(() => FALLBACK)
    .then((list) => install(pick(list)));
})();
