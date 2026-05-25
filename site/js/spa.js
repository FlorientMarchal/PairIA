// js/spa.js — navigation SPA

const SPA_PAGES = ["index.php", "article.php", "panier.php", "compte.php"];

function scrollToCatalogue() {
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      const pageLayout = document.querySelector(".page-layout");
      if (!pageLayout) return;
      const top = pageLayout.getBoundingClientRect().top + window.scrollY;
      window.scrollTo({ top, behavior: "instant" });
    }),
  );
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "instant" });
  const mc = document.getElementById("main-content");
  if (mc) mc.scrollTop = 0;
}

async function navigateTo(url, pushState = true) {
  const separator = url.includes("?") ? "&" : "?";
  const ajaxUrl = url + separator + "ajax=1";
  const targetPage = url.split("?")[0].split("/").pop() || "index.php";
  const goToIndex = targetPage === "index.php";

  try {
    const res = await fetch(ajaxUrl);
    if (!res.ok) throw new Error("Erreur réseau");
    const html = await res.text();

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    // Contenu
    const content = doc.getElementById("ajax-content");
    if (content)
      document.getElementById("spa-content").innerHTML = content.innerHTML;

    // Hero
    const hero = doc.getElementById("ajax-hero");
    document.getElementById("spa-hero").innerHTML = hero ? hero.innerHTML : "";

    // Titre
    const title = doc.querySelector("title");
    if (title) document.title = title.textContent;

    // Lien actif navbar
    document
      .querySelectorAll("nav a")
      .forEach((a) => a.classList.remove("active"));
    const activeLink = document.querySelector(`nav a[href="${targetPage}"]`);
    if (activeLink) activeLink.classList.add("active");

    // Scripts externes : chargés une seule fois
    const scriptPromises = [];
    doc.querySelectorAll("script[src]").forEach((oldScript) => {
      const alreadyLoaded = document.querySelector(
        `script[src="${oldScript.src}"]`,
      );
      if (!alreadyLoaded) {
        const p = new Promise((resolve) => {
          const s = document.createElement("script");
          s.src = oldScript.src;
          s.onload = resolve;
          s.onerror = resolve;
          document.body.appendChild(s);
        });
        scriptPromises.push(p);
      }
    });
    await Promise.all(scriptPromises);

    // Scripts inline : combinés en un seul bloc pour que les variables
    // soient partagées entre scripts, et window.* reste accessible globalement
    const inlineScripts = [...doc.querySelectorAll("script:not([src])")];
    const combined = inlineScripts.map((s) => s.textContent).join("\n");
    const s = document.createElement("script");
    s.textContent = combined;
    document.body.appendChild(s);
    // Ne pas supprimer : les fonctions window.* doivent rester disponibles

    if (pushState) history.pushState({ url }, "", url);

    goToIndex ? scrollToCatalogue() : scrollToTop();
  } catch (e) {
    console.error("[SPA]", e);
    window.location.href = url;
  }
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("a[href]");
  if (!link) return;
  const href = link.getAttribute("href");
  if (!href) return;
  if (
    href.startsWith("http") ||
    href.startsWith("#") ||
    href.startsWith("cart/") ||
    href.startsWith("chat/") ||
    href.startsWith("mailto:") ||
    href.startsWith("tel:") ||
    href === "deconnexion.php"
  )
    return;
  const pageName = href.replace(/(\?.*)$/, "");
  if (!SPA_PAGES.includes(pageName)) return;
  e.preventDefault();
  navigateTo(href);
});

window.addEventListener("popstate", (e) => {
  const url = e.state?.url || window.location.pathname + window.location.search;
  navigateTo(url, false);
});

document.addEventListener("DOMContentLoaded", () => {
  const initialUrl = window.location.pathname + window.location.search;
  const pageName = initialUrl.split("/").pop().split("?")[0];

  if (pageName === "shell.php" || pageName === "") {
    navigateTo("index.php", true);
    history.replaceState({ url: "index.php" }, "", "index.php");
  } else if (SPA_PAGES.includes(pageName)) {
    navigateTo(initialUrl, false);
    history.replaceState({ url: initialUrl }, "", initialUrl);
  }
});
