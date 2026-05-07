// js/chat.js
// Gestion du chat — appels vers l'API FastAPI /chat
// et ajout au panier via cart/add.php

const API_URL = 'http://localhost:8000';

// Historique de conversation (max 20 messages = 10 échanges)
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
    const body = {
      question: text,
      history: conversationHistory
    };

    if (typeof PRODUCT_ID !== 'undefined') {
      body.product_id = PRODUCT_ID;
    }

    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    const data = await response.json();
    typing.remove();
    appendBotMessage(data);

    // Mettre à jour l'historique
    conversationHistory.push({ role: 'user',      content: text });
    conversationHistory.push({ role: 'assistant', content: data.message });

    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }

    // Ajout panier déclenché par le LLM — afficher le sélecteur taille/couleur
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
}

/* ══════════════════════════════════════
   SÉLECTEUR TAILLE / COULEUR DANS LE CHAT
══════════════════════════════════════ */
function showCartSelector(produit) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'chat-msg bot';

  const taillesHtml = (produit.tailles || []).map(t =>
    `<button class="chat-sel-btn" onclick="chatSelectOption(this)">${escapeHtml(t)}</button>`
  ).join('');

  const couleursHtml = (produit.couleurs || []).map(c =>
    `<button class="chat-sel-btn" onclick="chatSelectOption(this)">${escapeHtml(c)}</button>`
  ).join('');

  const hasTailles  = (produit.tailles  || []).length > 0;
  const hasCouleurs = (produit.couleurs || []).length > 0;

  div.innerHTML = `
    <div class="chat-bubble">
      Pour ajouter <strong>${escapeHtml(produit.name)}</strong> au panier, choisissez :
      ${hasTailles ? `
        <div class="chat-sel-label">Pointure</div>
        <div class="chat-sel-group" data-type="taille">${taillesHtml}</div>
      ` : ''}
      ${hasCouleurs ? `
        <div class="chat-sel-label">Couleur</div>
        <div class="chat-sel-group" data-type="couleur">${couleursHtml}</div>
      ` : ''}
      <button
        class="chat-sel-confirm"
        onclick="confirmChatCart(${produit.id}, this)"
        ${hasTailles || hasCouleurs ? 'disabled' : ''}
      >Ajouter au panier</button>
      <div class="chat-sel-error"></div>
    </div>
    <div class="chat-time">maintenant</div>
  `;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  // Pas de choix requis : ajouter directement
  if (!hasTailles && !hasCouleurs) {
    confirmChatCart(produit.id, div.querySelector('.chat-sel-confirm'));
  }
}

function chatSelectOption(btn) {

  const group = btn.closest('.chat-option-group');

  group.querySelectorAll('.chat-option-btn')
    .forEach(b => b.classList.remove('active'));

  btn.classList.add('active');

  const card = btn.closest('.chat-product-card');

  const groups = card.querySelectorAll('.chat-option-group');

  const allSelected = [...groups].every(group =>
    group.querySelector('.chat-option-btn.active')
  );

  const cartBtn = card.querySelector('.chat-cart-btn');

  if (cartBtn) {
    cartBtn.disabled = !allSelected;
  }
}

async function confirmChatCart(productId, btn) {

  const card = btn.closest('.chat-product-card');

  const taille =
    card.querySelector('[data-type="taille"] .chat-option-btn.active')
      ?.textContent.trim() || null;

  const couleur =
    card.querySelector('[data-type="couleur"] .chat-option-btn.active')
      ?.textContent.trim() || null;

  btn.disabled = true;
  btn.textContent = 'Ajout...';

  const result = await addToCart(
    productId,
    1,
    taille,
    couleur
  );

  if (result?.success) {

    btn.textContent = '✓ Ajouté';

    btn.style.background = '#4CAF50';

  } else {

    btn.disabled = false;

    btn.textContent = 'Ajouter au panier';
  }
}

/* ══════════════════════════════════════
   CONSTRUCTION DES BULLES
══════════════════════════════════════ */
function appendUserMessage(text) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'chat-msg user';
  div.innerHTML = `
    <div class="chat-bubble">${escapeHtml(text)}</div>
    <div class="chat-time">maintenant</div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendBotMessage(data) {
  const container = document.getElementById('messages');

  const div = document.createElement('div');
  div.className = 'chat-msg bot';

  let html = `
    <div class="chat-bubble">
      ${escapeHtml(data.message)}
    </div>
  `;

  // UNE SEULE RECOMMANDATION
  if (data.products && data.products.length > 0) {

    const p = data.products[0];

    const taillesHtml = (p.tailles || []).map(t =>
      `<button class="chat-option-btn" onclick="chatSelectOption(this)">
        ${escapeHtml(t)}
      </button>`
    ).join('');

    const couleursHtml = (p.couleurs || []).map(c =>
      `<button class="chat-option-btn" onclick="chatSelectOption(this)">
        ${escapeHtml(c)}
      </button>`
    ).join('');

    html += `
      <div class="chat-product-card">

        <div class="chat-product-top">
          <div class="chat-product-img">
            ${
              p.url_image
                ? `<img src="${escapeHtml(p.url_image)}"
                        alt="${escapeHtml(p.name)}">`
                : '👟'
            }
          </div>

          <div class="chat-product-info">
            <div class="chat-product-name">
              ${escapeHtml(p.name)}
            </div>

            <div class="chat-product-price">
              ${p.price} €
            </div>
          </div>
        </div>

        ${
          p.tailles?.length
            ? `
            <div class="chat-option-title">
              Pointure
            </div>

            <div class="chat-option-group"
                 data-type="taille">
              ${taillesHtml}
            </div>
          `
            : ''
        }

        ${
          p.couleurs?.length
            ? `
            <div class="chat-option-title">
              Couleur
            </div>

            <div class="chat-option-group"
                 data-type="couleur">
              ${couleursHtml}
            </div>
          `
            : ''
        }

        <button
          class="chat-cart-btn"
          onclick="confirmChatCart(${p.id}, this)"
          disabled
        >
          Ajouter au panier
        </button>

      </div>
    `;
  }

  html += `<div class="chat-time">maintenant</div>`;

  div.innerHTML = html;

  container.appendChild(div);

  container.scrollTop = container.scrollHeight;
}

function appendBotMessageText(text) {
  const container = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'chat-msg bot';
  div.innerHTML = `
    <div class="chat-bubble">${escapeHtml(text)}</div>
    <div class="chat-time">maintenant</div>
  `;
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
   PANIER
══════════════════════════════════════ */
async function addToCart(productId, quantity = 1, taille = null, couleur = null) {
  try {
    const basePath = window.location.pathname.includes('/site/') ? '/site/' : '/';
    const res = await fetch(basePath + 'cart/add.php', {
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
  } catch (error) {
    console.error('Erreur compteur panier :', error);
  }
}

/* ══════════════════════════════════════
   UTILITAIRES
══════════════════════════════════════ */
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = String(text);
  return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => updateCartCount());