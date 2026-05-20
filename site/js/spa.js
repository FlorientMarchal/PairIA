// js/spa.js — navigation SPA

const SPA_PAGES = ['index.php', 'article.php', 'panier.php'];

// Le hero est HORS de main-content (frère au-dessus de page-layout).
// Pour "aller sous le hero", on scrolle WINDOW jusqu'à page-layout.
function scrollToCatalogue() {
    requestAnimationFrame(() => requestAnimationFrame(() => {
        const pageLayout = document.querySelector('.page-layout');
        if (!pageLayout) return;
        const top = pageLayout.getBoundingClientRect().top + window.scrollY;
        window.scrollTo({ top, behavior: 'instant' });
    }));
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'instant' });
    const mc = document.getElementById('main-content');
    if (mc) mc.scrollTop = 0;
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

        // Contenu
        const content = doc.getElementById('ajax-content');
        if (content) document.getElementById('spa-content').innerHTML = content.innerHTML;

        // Hero (full-width, hors split)
        const hero = doc.getElementById('ajax-hero');
        document.getElementById('spa-hero').innerHTML = hero ? hero.innerHTML : '';

        // Titre
        const title = doc.querySelector('title');
        if (title) document.title = title.textContent;

        // Lien actif navbar
        document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
        const activeLink = document.querySelector(`nav a[href="${targetPage}"]`);
        if (activeLink) activeLink.classList.add('active');

        // Scripts inline
        doc.querySelectorAll('script').forEach(oldScript => {
            const s = document.createElement('script');
            if (oldScript.src) { s.src = oldScript.src; }
            else { s.textContent = oldScript.textContent; }
            document.body.appendChild(s);
            document.body.removeChild(s);
        });

        if (pushState) history.pushState({ url }, '', url);

        if (goToIndex) {
            scrollToCatalogue();
        } else {
            scrollToTop();
        }

    } catch (e) {
        console.error('[SPA]', e);
        window.location.href = url;
    }
}

document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href) return;
    if (href.startsWith('http') || href.startsWith('#') ||
        href.startsWith('cart/') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
    const pageName = href.split('?')[0];
    if (!SPA_PAGES.includes(pageName)) return;
    e.preventDefault();
    navigateTo(href);
});

window.addEventListener('popstate', (e) => {
    const url = e.state?.url || (window.location.pathname + window.location.search);
    navigateTo(url, false);
});

document.addEventListener('DOMContentLoaded', () => {
    const initialUrl = window.location.pathname + window.location.search;
    const pageName   = initialUrl.split('/').pop().split('?')[0];

    if (pageName === 'shell.php' || pageName === '') {
        navigateTo('index.php', true);
        history.replaceState({ url: 'index.php' }, '', 'index.php');
    } else if (SPA_PAGES.includes(pageName)) {
        navigateTo(initialUrl, false);
        history.replaceState({ url: initialUrl }, '', initialUrl);
    }
});