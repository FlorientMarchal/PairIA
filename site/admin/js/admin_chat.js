// admin/js/admin_chat.js
// Chatbot ADMIN — totalement indépendant de js/chat.js (chatbot client)
// Communique avec ia/admin_main.py sur le port 8001

const ADMIN_API_URL = "http://localhost:8001";

let adminHistory   = JSON.parse(sessionStorage.getItem("adminChatHistory") || "[]");
let adminStreaming  = false;

// ── Initialisation ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Chips de suggestion
  document.querySelectorAll(".achat-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      const msg = btn.dataset.msg;
      if (msg) {
        document.getElementById("achat-input").value = msg;
        adminChatSend();
        // Cache les chips après utilisation
        document.getElementById("achat-chips-wrap").style.display = "none";
      }
    });
  });

  // Restaurer l'historique de session
  if (adminHistory.length > 0) {
    document.getElementById("achat-chips-wrap").style.display = "none";
    adminHistory.forEach(m => _renderAdminMessage(m.role, m.content, false));
  }
});

// ── Envoi d'un message ───────────────────────────────────────────────────────
async function adminChatSend() {
  const input = document.getElementById("achat-input");
  const text  = input.value.trim();
  if (!text || adminStreaming) return;

  input.value = "";
  input.style.height = "auto";
  document.getElementById("achat-chips-wrap").style.display = "none";

  _renderAdminMessage("user", text);
  adminHistory.push({ role: "user", content: text });
  _saveHistory();

  const typingEl = _showTyping();
  adminStreaming = true;

  try {
    const resp = await fetch(`${ADMIN_API_URL}/admin/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: text,
        history: adminHistory.slice(-20),
        admin_id: window.ADMIN_ID || null,
      }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    typingEl.remove();

    const botBubble = _createBotBubble();
    let   botText   = "";
    const reader    = resp.body.getReader();
    const decoder   = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const lines = decoder.decode(value).split("\n");
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") break;

        try {
          const event = JSON.parse(raw);

          if (event.type === "action_start") {
            // Affiche un badge "action en cours"
            _appendActionBadge(botBubble, event.action, "running");
          } else if (event.type === "action_result") {
            // Met à jour le badge avec le statut
            _updateActionBadge(botBubble, event.action, event.result);
          } else if (event.chunk) {
            botText += event.chunk;
            botBubble.querySelector(".achat-bubble").innerHTML = _formatBotText(botText);
            _scrollToBottom();
          }
        } catch (_) {}
      }
    }

    // Sauvegarde la réponse finale
    adminHistory.push({ role: "assistant", content: botText });
    _saveHistory();

  } catch (err) {
    typingEl?.remove();
    _renderAdminMessage("bot-error", "Impossible de contacter l'assistant. Vérifiez que le serveur IA admin tourne sur le port 8001.");
    console.error("[AdminChat]", err);
  } finally {
    adminStreaming = false;
  }
}

// ── Réinitialiser la conversation ────────────────────────────────────────────
function adminChatReset() {
  adminHistory = [];
  sessionStorage.removeItem("adminChatHistory");
  const msgs = document.getElementById("achat-messages");
  // Garde seulement le message d'accueil (premier enfant)
  while (msgs.children.length > 1) msgs.removeChild(msgs.lastChild);
  document.getElementById("achat-chips-wrap").style.display = "";
}

// ── Toggle mobile ────────────────────────────────────────────────────────────
function toggleChatMobile() {
  const panel   = document.getElementById("achat-panel");
  const overlay = document.getElementById("chat-overlay");
  const fab     = document.getElementById("chat-fab");
  const open    = panel.classList.toggle("mobile-open");
  overlay.classList.toggle("visible", open);
  fab.classList.toggle("active", open);
  if (open) document.getElementById("achat-input")?.focus();
}
function closeChatMobile() {
  document.getElementById("achat-panel")?.classList.remove("mobile-open");
  document.getElementById("chat-overlay")?.classList.remove("visible");
  document.getElementById("chat-fab")?.classList.remove("active");
}

// ── Helpers d'affichage ──────────────────────────────────────────────────────
function _renderAdminMessage(role, text, scroll = true) {
  const msgs = document.getElementById("achat-messages");
  const wrap = document.createElement("div");

  if (role === "user") {
    wrap.className = "achat-msg user";
    wrap.innerHTML = `<div class="achat-bubble">${_escapeHtml(text)}</div><div class="achat-time">${_now()}</div>`;
  } else if (role === "assistant") {
    wrap.className = "achat-msg bot";
    wrap.innerHTML = `<div class="achat-bubble">${_formatBotText(text)}</div><div class="achat-time">${_now()}</div>`;
  } else {
    wrap.className = "achat-msg bot error";
    wrap.innerHTML = `<div class="achat-bubble achat-error">${_escapeHtml(text)}</div>`;
  }

  msgs.appendChild(wrap);
  if (scroll) _scrollToBottom();
  return wrap;
}

function _createBotBubble() {
  const msgs = document.getElementById("achat-messages");
  const wrap = document.createElement("div");
  wrap.className = "achat-msg bot";
  wrap.innerHTML = `<div class="achat-bubble"></div><div class="achat-time">${_now()}</div>`;
  msgs.appendChild(wrap);
  _scrollToBottom();
  return wrap;
}

function _showTyping() {
  const msgs = document.getElementById("achat-messages");
  const el   = document.createElement("div");
  el.className = "achat-msg bot";
  el.innerHTML = `<div class="achat-bubble achat-typing"><span></span><span></span><span></span></div>`;
  msgs.appendChild(el);
  _scrollToBottom();
  return el;
}

function _appendActionBadge(wrapEl, action, status) {
  const bubble = wrapEl.querySelector(".achat-bubble");
  const badge  = document.createElement("div");
  badge.className = "action-badge action-running";
  badge.dataset.action = action;
  badge.innerHTML = `<span class="action-spinner">⟳</span> ${_actionLabel(action)}…`;
  bubble.appendChild(badge);
  _scrollToBottom();
}

function _updateActionBadge(wrapEl, action, result) {
  const badge = wrapEl.querySelector(`.action-badge[data-action="${action}"]`);
  if (!badge) return;
  badge.classList.remove("action-running");
  if (result?.success) {
    badge.classList.add("action-ok");
    badge.innerHTML = `✓ ${_actionLabel(action)} — ${_escapeHtml(result.message || "OK")}`;
  } else {
    badge.classList.add("action-error");
    badge.innerHTML = `✗ ${_actionLabel(action)} — ${_escapeHtml(result?.message || "Erreur")}`;
  }
}

function _actionLabel(action) {
  const labels = {
    lister_commandes:          "Chargement des commandes",
    detail_commande:           "Récupération commande",
    modifier_statut_commande:  "Mise à jour statut",
    lister_articles:           "Chargement catalogue",
    modifier_prix:             "Modification prix",
    modifier_stock:            "Modification stock",
    rechercher_article:        "Recherche article",
    rechercher_client:         "Recherche client",
    commandes_client:          "Commandes client",
    lister_commentaires:       "Chargement commentaires",
    supprimer_commentaire:     "Suppression commentaire",
    stats_globales:            "Calcul statistiques",
    top_articles:              "Top ventes",
    ca_par_mois:               "CA mensuel",
  };
  return labels[action] || action;
}

function _formatBotText(text) {
  // Conversion simple markdown → HTML (gras, tirets)
  return text
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")
    .replace(/\*(.+?)\*/g,"<em>$1</em>")
    .replace(/^- (.+)$/gm,"<li>$1</li>")
    .replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>")
    .replace(/\n/g,"<br>");
}

function _escapeHtml(str) {
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function _scrollToBottom() {
  const msgs = document.getElementById("achat-messages");
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function _now() {
  return new Date().toLocaleTimeString("fr-FR", { hour:"2-digit", minute:"2-digit" });
}

function _saveHistory() {
  try { sessionStorage.setItem("adminChatHistory", JSON.stringify(adminHistory.slice(-40))); }
  catch (_) {}
}
