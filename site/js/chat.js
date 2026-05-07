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
  const group = btn.closest('.chat-sel-group');
  group.querySelectorAll('.chat-sel-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');

  // Vérifier si tout est sélectionné pour activer le bouton
  const bubble    = btn.closest('.chat-bubble');
  const groups    = bubble.querySelectorAll('.chat-sel-group');
  const allOk     = [...groups].every(g => g.querySelector('.chat-sel-btn.active'));
  const confirmBtn = bubble.querySelector('.chat-sel-confirm');
  if (confirmBtn) confirmBtn.disabled = !allOk;
}

async function confirmChatCart(productId, btn) {
  const bubble  = btn.closest('.chat-bubble');
  const errEl   = bubble.querySelector('.chat-sel-error');

  const taille  = bubble.querySelector('.chat-sel-group[data-type="taille"] .chat-sel-btn.active')?.textContent.trim()  || null;
  const couleur = bubble.querySelector('.chat-sel-group[data-type="couleur"] .chat-sel-btn.active')?.textContent.trim() || null;

  btn.disabled    = true;
  btn.textContent = '…';
  if (errEl) errEl.textContent = '';

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent       = '✓ Ajouté !';
    btn.style.background  = '#4CAF50';
    btn.style.borderColor = '#4CAF50';
  } else {
    btn.disabled    = false;
    btn.textContent = 'Ajouter au panier';
    if (errEl) errEl.textContent = result?.error || "Erreur lors de l'ajout.";
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

  let html = `<div class="chat-bubble">${escapeHtml(data.message)}</div>`;

  if (data.products && data.products.length > 0) {
    data.products.forEach(p => {
      // Sérialiser le produit pour le passer à showCartSelector
      const produitJson = escapeHtml(JSON.stringify(p));
      html += `
        <div class="chat-reco" onclick="window.location.href='article.php?id=${p.id}'">
          <div class="chat-reco-img">
            ${p.url_image
              ? `<img src="${escapeHtml(p.url_image)}" alt="${escapeHtml(p.name)}" onerror="this.style.display='none'">`
              : '👟'
            }
          </div>
          <div class="chat-reco-info">
            <div class="chat-reco-name">${escapeHtml(p.name)}</div>
            <div class="chat-reco-price">${p.price} €</div>
            <button class="chat-reco-add" onclick="event.stopPropagation(); showCartSelector(JSON.parse(this.dataset.produit))" data-produit='${produitJson}'>
              + Panier
            </button>
          </div>
        </div>`;
    });
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