// admin/js/admin_chat.js
const ADMIN_API_URL    = "http://172.27.30.30:8001";
const ADMIN_SESSION_ID = ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));

let adminHistory  = JSON.parse(localStorage.getItem("adminChatHistory") || "[]");
let adminStreaming = false;
let pendingImageUrl = null;

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".achat-chip").forEach(btn => {
    btn.addEventListener("click", () => {
      const msg = btn.dataset.msg;
      if (msg) {
        document.getElementById("achat-input").value = msg;
        adminChatSend();
        document.getElementById("achat-chips-wrap").style.display = "none";
      }
    });
  });

  if (adminHistory.length > 0) {
    document.getElementById("achat-chips-wrap").style.display = "none";
    adminHistory.forEach(m => _renderAdminMessage(m.role, m.content, false));
  }

  document.getElementById("admin-image-input")?.addEventListener("change", handleAdminImageUpload);
});

// ── Upload image ──────────────────────────────────────────────────────────────
async function handleAdminImageUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const preview = document.getElementById("admin-image-preview");
  const status  = document.getElementById("admin-upload-status");

  const reader = new FileReader();
  reader.onload = ev => {
    if (preview) {
      preview.innerHTML = `<img src="${ev.target.result}" style="max-height:60px;border-radius:6px;margin-right:.5rem">`;
      preview.style.display = "flex";
    }
  };
  reader.readAsDataURL(file);

  if (status) { status.textContent = "Upload…"; status.style.color = "#8a8178"; }

  const form = new FormData();
  form.append("image", file);

  try {
    const resp = await fetch(`/admin/ajax/upload_image.php`, { method: "POST", body: form });
    const data = await resp.json();
    if (data.success) {
      pendingImageUrl = data.url_image;
      if (status) { status.textContent = "✓ Image prête"; status.style.color = "#27ae60"; }
      document.getElementById("achat-input")?.focus();
    } else {
      if (status) { status.textContent = "✗ " + data.message; status.style.color = "#c0392b"; }
      pendingImageUrl = null;
    }
  } catch {
    if (status) { status.textContent = "✗ Erreur réseau"; status.style.color = "#c0392b"; }
    pendingImageUrl = null;
  }

  e.target.value = "";
}

function clearImagePreview() {
  const preview = document.getElementById("admin-image-preview");
  const status  = document.getElementById("admin-upload-status");
  if (preview) { preview.innerHTML = ""; preview.style.display = "none"; }
  if (status)  { status.textContent = ""; }
  pendingImageUrl = null;
}

// ── Envoi d'un message ────────────────────────────────────────────────────────
async function adminChatSend() {
  const input = document.getElementById("achat-input");
  const text  = input.value.trim();
  if ((!text && !pendingImageUrl) || adminStreaming) return;

  input.value = "";
  input.style.height = "auto";
  document.getElementById("achat-chips-wrap").style.display = "none";

  // Affiche le message utilisateur
  const msgs = document.getElementById("achat-messages");
  const userWrap = document.createElement("div");
  userWrap.className = "achat-msg user";
  let userContent = "";
  if (pendingImageUrl) {
    userContent += `<img src="../../${pendingImageUrl}" style="max-height:100px;border-radius:8px;display:block;margin-bottom:.4rem">`;
  }
  if (text) userContent += `<span>${_escapeHtml(text)}</span>`;
  userWrap.innerHTML = `<div class="achat-bubble">${userContent}</div><div class="achat-time">${_now()}</div>`;
  msgs.appendChild(userWrap);
  _scrollToBottom();

  const displayText = text || "📷 Image envoyée";
  adminHistory.push({ role: "user", content: displayText });
  _saveHistory();

  const imageUrlToSend = pendingImageUrl;
  clearImagePreview();

  const typingEl = _showTyping();
  adminStreaming  = true;

  try {
    const resp = await fetch(`${ADMIN_API_URL}/admin/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question:   text || "J'ai envoyé une photo pour un nouvel article.",
        session_id: ADMIN_SESSION_ID,
        admin_id:   window.ADMIN_ID || null,
        image_url:  imageUrlToSend || null,
      }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    typingEl.remove();

    // La bulle est créée au premier événement reçu (action ou chunk)
    let botBubble = null;
    let botText   = "";
    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();

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
          if (event.type === "thinking") {
            if (!botBubble) botBubble = _createBotBubble();
            botBubble.querySelector(".achat-bubble").innerHTML = 
                `<span style="color:rgba(255,255,255,.4);font-size:.82rem">Je réfléchis…</span>`;
          } else if (event.type === "action_start") {
            if (!botBubble) botBubble = _createBotBubble();
            _appendActionBadge(botBubble, event.action, "running", event.status_text);
          } else if (event.type === "action_result") {
            if (!botBubble) botBubble = _createBotBubble();
            _updateActionBadge(botBubble, event.action, event.result);
          } else if (event.chunk) {
            if (!botBubble) botBubble = _createBotBubble();
            botText += event.chunk;
            botBubble.querySelector(".achat-bubble").innerHTML = _formatBotText(botText);
            _scrollToBottom();
          }
        } catch (_) {}
      }
    }

    // Si aucune bulle créée (cas rare), on en crée une vide
    if (!botBubble && botText) botBubble = _createBotBubble();

    adminHistory.push({ role: "assistant", content: botText || "✓" });
    _saveHistory();

  } catch (err) {
    typingEl?.remove();
    _renderAdminMessage("bot-error", "Impossible de contacter l'assistant.");
    console.error("[AdminChat]", err);
  } finally {
    adminStreaming = false;
  }
}

function adminChatReset() {
  adminHistory = [];
localStorage.removeItem("adminChatHistory");
  const msgs = document.getElementById("achat-messages");
  while (msgs.children.length > 1) msgs.removeChild(msgs.lastChild);
  document.getElementById("achat-chips-wrap").style.display = "";
  clearImagePreview();
}

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

// ── Helpers d'affichage ───────────────────────────────────────────────────────
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

function _appendActionBadge(wrapEl, action, status, statusText) {
  const bubble = wrapEl.querySelector(".achat-bubble");
  const badge  = document.createElement("div");
  badge.className = "action-badge action-running";
  badge.dataset.action = action;
  // Utilise le status_text envoyé par Python si disponible, sinon label générique
  const label = statusText || _actionLabel(action) + "…";
  badge.innerHTML = `<span class="action-spinner">⟳</span> ${label}`;
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
    const section = window.location.hash.replace('#', '') || 'dashboard';
    if (['modifier_statut_commande','modifier_statut_batch','lister_commandes'].includes(action) && section === 'commandes') loadCommandes();
    if (['modifier_prix','modifier_stock','modifier_prix_batch','modifier_article','ajouter_article','supprimer_article','lister_articles'].includes(action) && section === 'catalogue') loadCatalogue();
    if (['rechercher_client','commandes_client','lister_clients'].includes(action) && section === 'clients') loadClients();
    if (['supprimer_commentaire','supprimer_commentaires_article','lister_commentaires'].includes(action) && section === 'commentaires') loadCommentaires();
  } else {
    badge.classList.add("action-error");
    badge.innerHTML = `✗ ${_actionLabel(action)} — ${_escapeHtml(result?.message || "Erreur")}`;
  }
}

function _actionLabel(action) {
  const labels = {
    lister_commandes:               "Chargement des commandes",
    detail_commande:                "Récupération commande",
    modifier_statut_commande:       "Mise à jour statut",
    modifier_statut_batch:          "Mise à jour statuts",
    lister_articles:                "Chargement catalogue",
    lister_articles_stock_faible:   "Articles stock faible",
    modifier_prix:                  "Modification prix",
    modifier_stock:                 "Modification stock",
    modifier_prix_batch:            "Mise à jour prix en lot",
    modifier_article:               "Modification article",
    ajouter_article:                "Ajout article",
    supprimer_article:              "Suppression article",
    rechercher_article:             "Recherche article",
    lister_clients:                 "Chargement clients",
    rechercher_client:              "Recherche client",
    commandes_client:               "Commandes client",
    clients_top:                    "Top clients",
    lister_commentaires:            "Chargement commentaires",
    supprimer_commentaire:          "Suppression commentaire",
    supprimer_commentaires_article: "Suppression commentaires",
    stats_globales:                 "Calcul statistiques",
    stats_par_categorie:            "Stats par catégorie",
    top_articles:                   "Top ventes",
    ca_par_mois:                    "CA mensuel",
  };
  return labels[action] || action;
}

function _formatBotText(text) {
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
   try { localStorage.setItem("adminChatHistory", JSON.stringify(adminHistory.slice(-40))); }
  catch (_) {}
}