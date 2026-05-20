// js/spa.js — navigation SPA

const SPA_PAGES = ['index.php', 'article.php', 'panier.php'];

// Scrolle main-content jusqu'au début du contenu (sous le hero)
function scrollToCatalogue() {
    // Double rAF : le premier laisse le navigateur appliquer le DOM,
    // le second attend que le layout soit calculé (offsetHeight valide)
    requestAnimationFrame(() => requestAnimationFrame(() => {
        const mainContent = document.getElementById('main-content');
        const spaHero     = document.getElementById('spa-hero');
        if (!mainContent) return;
        const heroHeight = spaHero ? spaHero.offsetHeight : 0;
        mainContent.scrollTop = heroHeight;
    }));
}

function scrollToTop() {
    const mainContent = document.getElementById('main-content');
    if (mainContent) mainContent.scrollTop = 0;
}

async function navigateTo(url, pushState = true) {
    const separator = url.includes('?') ? '&' : '?';
    const ajaxUrl   = url + separator + 'ajax=1';

    const targetPage = url.split('?')[0].split('/').pop() || 'index.php';
    const goToIndex  = targetPage === 'index.php';

    try {
        const res = await fetch(ajaxUrl);
        if (!res.ok) throw new Error('Erreur réseau');
        const html = await res.text();

        const parser = new DOMParser();
        const doc    = parser.parseFromString(html, 'text/html');

        // Met à jour le contenu
        const content = doc.getElementById('ajax-content');
        if (content) {
            document.getElementById('spa-content').innerHTML = content.innerHTML;
        }

        // Met à jour le hero
        const hero = doc.getElementById('ajax-hero');
        document.getElementById('spa-hero').innerHTML = hero ? hero.innerHTML : '';

        // Met à jour le titre
        const title = doc.querySelector('title');
        if (title) document.title = title.textContent;

        // Met à jour le lien actif dans la navbar
        document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
        const activeLink = document.querySelector(`nav a[href="${targetPage}"]`);
        if (activeLink) activeLink.classList.add('active');

        // Exécute les scripts inline du fragment
        doc.querySelectorAll('script').forEach(oldScript => {
            const newScript = document.createElement('script');
            if (oldScript.src) {
                newScript.src = oldScript.src;
            } else {
                newScript.textContent = oldScript.textContent;
            }
            document.body.appendChild(newScript);
            document.body.removeChild(newScript);
        });

        if (pushState) {
            history.pushState({ url }, '', url);
        }

        // Scroll : index → sous le hero, tout le reste → haut
        if (goToIndex) {
            scrollToCatalogue();
        } else {
            scrollToTop();
        }

    } catch (e) {
        console.error('[SPA] Erreur navigation :', e);
        window.location.href = url;
    }
}

// Intercepte les clics sur les liens internes
document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href]');
    if (!link) return;

    const href = link.getAttribute('href');
    if (!href) return;

    if (href.startsWith('http') || href.startsWith('#') ||
        href.startsWith('cart/') || href.startsWith('mailto:') ||
        href.startsWith('tel:')) return;

    const pageName = href.split('?')[0];
    if (!SPA_PAGES.includes(pageName)) return;

    e.preventDefault();
    navigateTo(href);
});

// Gestion du bouton retour/avant du navigateur
window.addEventListener('popstate', (e) => {
    if (e.state && e.state.url) {
        navigateTo(e.state.url, false);
    } else {
        navigateTo(window.location.pathname + window.location.search, false);
    }
});

// Charge la page initiale au démarrage
document.addEventListener('DOMContentLoaded', () => {
    const initialUrl = window.location.pathname + window.location.search;
    const pageName   = initialUrl.split('/').pop().split('?')[0];

    if (pageName === 'shell.php' || pageName === '') {
        // Arrivée directe sur shell.php → charge index.php sous le hero
        navigateTo('index.php', true);
        history.replaceState({ url: 'index.php' }, '', 'index.php');
    } else if (SPA_PAGES.includes(pageName)) {
        navigateTo(initialUrl, false);
        history.replaceState({ url: initialUrl }, '', initialUrl);
    }
});