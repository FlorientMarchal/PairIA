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

    // Sur la fiche article, envoyer le product_id pour contextualiser
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

    // Limiter à 20 messages pour ne pas surcharger le contexte Mistral
    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }

    // Si le LLM veut ajouter au panier
    if (data.action === 'add_to_cart' && data.product_id) {
      await addToCart(data.product_id, data.quantity || 1);
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

  // Produits recommandés
  if (data.products && data.products.length > 0) {
    data.products.forEach(p => {
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
            <button class="chat-reco-add" onclick="event.stopPropagation(); addToCart(${p.id}, 1)">
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
  }
}

async function updateCartCount(count) {
  if (count !== undefined) {
    const el = document.getElementById('cart-count');
    if (el) el.textContent = count;
    return;
  }
  // Si pas de count fourni, on le récupère
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

// Initialisation — charger le compteur panier
document.addEventListener('DOMContentLoaded', () => updateCartCount());