// js/chat.js
const API_URL = 'http://localhost:8000';

let conversationHistory = [];

/* ══════════════════════════════════════
   CHAT
══════════════════════════════════════ */
async function sendMessage(text) {
  const container = document.getElementById('messages');
  if (!container || !text.trim()) return;

  appendUserMessage(text);
  const typing = appendTyping();

  try {
    const body = { question: text, history: conversationHistory };
    if (typeof PRODUCT_ID !== 'undefined') body.product_id = PRODUCT_ID;

    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    const data = await response.json();
    typing.remove();

    appendBotMessage(data);

    conversationHistory.push({ role: 'user',      content: text });
    conversationHistory.push({ role: 'assistant', content: JSON.stringify({ message: data.message }) });
    if (conversationHistory.length > 20) conversationHistory = conversationHistory.slice(-20);

    // Ajout panier explicite
    if (data.action === 'add_to_cart' && data.product_id) {
      const produit = (data.products || []).find(p => p.id === data.product_id) || data.products?.[0];
      if (produit) showCartSelector(produit);
    }

  } catch (error) {
    typing.remove();
    appendBotMessageText("Désolé, je suis temporairement indisponible. Réessayez dans un instant.");
    console.error('Erreur API chat :', error);
  }
}

function sendFromInput() {
  const input = document.getElementById('chat-input');
  const text  = input?.value.trim();
  if (!text) return;
  input.value = '';
  sendMessage(text);
}

function resetConversation() {
  conversationHistory = [];
  const container = document.getElementById('messages');
  if (container) container.innerHTML = '';
}

/* ══════════════════════════════════════
   BULLES
══════════════════════════════════════ */
function appendUserMessage(text) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'chat-msg user';
  div.innerHTML = `
    <div class="chat-bubble">${escapeHtml(text)}</div>
    <div class="chat-time">maintenant</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendBotMessage(data) {
  const container = document.getElementById('messages');

  // Bulle texte
  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = 'chat-msg bot';
  bubbleDiv.innerHTML = `
    <div class="chat-bubble">${escapeHtml(data.message)}</div>
    <div class="chat-time">maintenant</div>`;
  container.appendChild(bubbleDiv);

  const products = data.products || [];

  if (products.length === 1) {
    // Carte directe avec pointure/couleur
    showCartSelector(products[0], container);
  } else if (products.length > 1) {
    // Carte multi-produits : on choisit d'abord le produit
    showProductPicker(products, container);
  }

  container.scrollTop = container.scrollHeight;
}

function appendBotMessageText(text) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'chat-msg bot';
  div.innerHTML = `
    <div class="chat-bubble">${escapeHtml(text)}</div>
    <div class="chat-time">maintenant</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendTyping() {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'chat-msg bot';
  div.id = 'typing-indicator';
  div.innerHTML = `
    <div class="chat-typing">
      <div class="chat-typing-dot"></div>
      <div class="chat-typing-dot"></div>
      <div class="chat-typing-dot"></div>
    </div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}
/* ══════════════════════════════════════
   CARTE MULTI-PRODUITS (picker)
══════════════════════════════════════ */
function showProductPicker(produits, container) {
  if (!container) container = document.getElementById('messages');

  const div = document.createElement('div');
  div.className = 'chat-msg bot';

  const itemsHtml = produits.map((p, i) => {
    const hasTailles  = (p.tailles  || []).length > 0;
    const hasCouleurs = (p.couleurs || []).length > 0;

    const taillesHtml = (p.tailles || []).map(t =>
      `<span class="chat-opt" onclick="chatPickOpt(this)" data-group="taille-${i}-${p.id}">${escapeHtml(t)}</span>`
    ).join('');

    const couleursHtml = (p.couleurs || []).map(c =>
      `<span class="chat-opt" onclick="chatPickOpt(this)" data-group="couleur-${i}-${p.id}">${escapeHtml(c)}</span>`
    ).join('');

    return `
      <div class="chat-pick-item">
        <div class="chat-pick-top">
          <div class="chat-product-pick-img">
            ${p.url_image
              ? `<img src="${escapeHtml(p.url_image)}" alt="${escapeHtml(p.name)}" onerror="this.style.display='none'">`
              : '👟'
            }
          </div>
          <div class="chat-product-pick-info">
            <div class="chat-product-name">${escapeHtml(p.name)}</div>
            <div class="chat-product-price">${p.price} €</div>
          </div>
        </div>
        <button class="chat-pick-toggle-btn" onclick="chatToggleSelector(this)">
          🛒 Ajouter au panier
        </button>
        <div class="chat-pick-selector" style="display:none">
          ${hasTailles ? `
            <div class="chat-option-title">Pointure</div>
            <div class="chat-option-group" data-type="taille">${taillesHtml}</div>
          ` : ''}
          ${hasCouleurs ? `
            <div class="chat-option-title">Couleur</div>
            <div class="chat-option-group" data-type="couleur">${couleursHtml}</div>
          ` : ''}
          <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>
          <button class="chat-cart-btn"
            onclick="confirmChatCartFromPicker(${p.id}, this)"
            ${hasTailles || hasCouleurs ? 'disabled' : ''}>
            Confirmer l'ajout
          </button>
        </div>
      </div>`;
  }).join('');

  div.innerHTML = `
    <div class="chat-product-card">
      <div class="chat-pick-title">Voici quelques suggestions</div>
      <div class="chat-product-pick-list">${itemsHtml}</div>
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function selectProductFromPicker(btn) {
  const card     = btn.closest('.chat-product-card');
  const produits = JSON.parse(card.dataset.products);
  const id       = parseInt(btn.dataset.id);
  const produit  = produits.find(p => p.id === id);
  if (!produit) return;

  const msgDiv    = card.closest('.chat-msg');
  const container = msgDiv.parentElement;
  msgDiv.remove();

  showCartSelector(produit, container);
  container.scrollTop = container.scrollHeight;
}

function chatToggleSelector(btn) {
  const selector = btn.nextElementSibling;
  const isOpen   = selector.style.display !== 'none';
  selector.style.display = isOpen ? 'none' : 'block';
  btn.style.opacity = isOpen ? '1' : '0.6';
}

function chatPickOpt(el) {
  el.closest('.chat-option-group').querySelectorAll('.chat-opt').forEach(o => o.classList.remove('active'));
  el.classList.add('active');

  const selector = el.closest('.chat-pick-selector');
  const groups   = [...selector.querySelectorAll('.chat-option-group')];
  const allDone  = groups.every(g => g.querySelector('.chat-opt.active'));
  selector.querySelector('.chat-cart-btn').disabled = !allDone;
}

async function confirmChatCartFromPicker(productId, btn) {
  const selector = btn.closest('.chat-pick-selector');
  const errEl    = selector.querySelector('.chat-selector-error');
  const taille   = selector.querySelector('.chat-option-group[data-type="taille"] .chat-opt.active')?.textContent || null;
  const couleur  = selector.querySelector('.chat-option-group[data-type="couleur"] .chat-opt.active')?.textContent || null;

  btn.disabled    = true;
  btn.textContent = '…';
  if (errEl) errEl.textContent = '';

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent      = '✓ Ajouté au panier !';
    btn.style.background = '#2f855a';
  } else {
    btn.disabled    = false;
    btn.textContent = 'Confirmer l\'ajout';
    if (errEl) errEl.textContent = result?.error || "Erreur lors de l'ajout.";
  }
}
/* ══════════════════════════════════════
   CARTE SÉLECTEUR TAILLE / COULEUR
══════════════════════════════════════ */
function showCartSelector(produit, container) {
  if (!container) container = document.getElementById('messages');

  const div = document.createElement('div');
  div.className = 'chat-msg bot';

  const hasTailles  = (produit.tailles  || []).length > 0;
  const hasCouleurs = (produit.couleurs || []).length > 0;

  const taillesHtml = (produit.tailles || []).map(t =>
    `<button class="chat-option-btn" onclick="chatSelectOption(this)" data-value="${escapeAttr(t)}">${escapeHtml(t)}</button>`
  ).join('');

  const couleursHtml = (produit.couleurs || []).map(c =>
    `<button class="chat-option-btn" onclick="chatSelectOption(this)" data-value="${escapeAttr(c)}">${escapeHtml(c)}</button>`
  ).join('');

  div.innerHTML = `
    <div class="chat-product-card">
      <div class="chat-product-top">
        <div class="chat-product-img">
          ${produit.url_image
            ? `<img src="${escapeHtml(produit.url_image)}" alt="${escapeHtml(produit.name)}" onerror="this.style.display='none'">`
            : '👟'
          }
        </div>
        <div>
          <div class="chat-product-name">${escapeHtml(produit.name)}</div>
          <div class="chat-product-price">${produit.price} €</div>
        </div>
      </div>

      ${hasTailles ? `
        <div class="chat-option-title">Pointure</div>
        <div class="chat-option-group" data-type="taille">${taillesHtml}</div>
      ` : ''}

      ${hasCouleurs ? `
        <div class="chat-option-title">Couleur</div>
        <div class="chat-option-group" data-type="couleur">${couleursHtml}</div>
      ` : ''}

      <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>

      <button class="chat-cart-btn"
        onclick="confirmChatCart(${produit.id}, this)"
        ${hasTailles || hasCouleurs ? 'disabled' : ''}>
        Ajouter au panier
      </button>
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  if (!hasTailles && !hasCouleurs) {
    confirmChatCart(produit.id, div.querySelector('.chat-cart-btn'));
  }
}

function chatSelectOption(btn) {
  const group = btn.closest('.chat-option-group');
  group.querySelectorAll('.chat-option-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  const card    = btn.closest('.chat-product-card');
  const groups  = card.querySelectorAll('.chat-option-group');
  const allDone = [...groups].every(g => g.querySelector('.chat-option-btn.active'));
  const confirm = card.querySelector('.chat-cart-btn');
  if (confirm) confirm.disabled = !allDone;
}

async function confirmChatCart(productId, btn) {
  const card    = btn.closest('.chat-product-card');
  const errEl   = card.querySelector('.chat-selector-error');
  const taille  = card.querySelector('.chat-option-group[data-type="taille"] .chat-option-btn.active')?.dataset.value  || null;
  const couleur = card.querySelector('.chat-option-group[data-type="couleur"] .chat-option-btn.active')?.dataset.value || null;

  btn.disabled    = true;
  btn.textContent = '…';
  if (errEl) errEl.textContent = '';

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent      = '✓ Ajouté au panier !';
    btn.style.background = '#2f855a';
  } else {
    btn.disabled    = false;
    btn.textContent = 'Ajouter au panier';
    if (errEl) errEl.textContent = result?.error || "Erreur lors de l'ajout.";
  }
}

/* ══════════════════════════════════════
   PANIER
══════════════════════════════════════ */
async function addToCart(productId, quantity = 1, taille = null, couleur = null) {
  try {
    const basePath = window.location.pathname.includes('/site/') ? '/site/' : '/';
    const res  = await fetch(basePath + 'cart/add.php', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ product_id: productId, quantity, taille, couleur })
    });
    const data = await res.json();
    if (data.success) updateCartCount(data.count);
    return data;
  } catch (error) {
    console.error('Erreur ajout panier :', error);
    return { success: false, error: 'Erreur réseau' };
  }
}

async function updateCartCount(count) {
  if (count !== undefined) {
    const el = document.getElementById('cart-count');
    if (el) el.textContent = count;
    return;
  }
  try {
    const res  = await fetch('cart/count.php');
    const data = await res.json();
    const el   = document.getElementById('cart-count');
    if (el) el.textContent = data.count;
  } catch (error) { console.error('Erreur compteur panier :', error); }
}

/* ══════════════════════════════════════
   UTILITAIRES
══════════════════════════════════════ */
function escapeHtml(text) {
  if (!text) return '';
  const d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function escapeAttr(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', () => updateCartCount());