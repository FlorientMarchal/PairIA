// admin/js/admin_chat.js
const ADMIN_API_URL    = "http://172.27.30.30:8001";
function _generateSessionId() {
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
}
let ADMIN_SESSION_ID = _generateSessionId();

let adminHistory  = JSON.parse(localStorage.getItem("adminChatHistory") || "[]");
let _pendingArticleData = null;
let _pendingVariants = null;
let _pendingImageUrl = null;
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
        console.error("[ANALYZE] Erreur:", e);
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
          } else if (event.type === "variant_form") {
            if (!botBubble) botBubble = _createBotBubble();
            botBubble.querySelector(".achat-bubble").innerHTML = "Remplissez les informations de l'article :";
            console.log("[VARIANT_FORM] article reçu:", event.article);
            _showArticleForm(event.article);
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
  ADMIN_SESSION_ID = _generateSessionId();
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
    console.log('[REFRESH] action:', action, 'section:', section);
    if (['modifier_prix','modifier_stock','modifier_prix_batch','modifier_article','ajouter_article','supprimer_article','lister_articles','arrondir_prix'].includes(action) && section === 'catalogue') { console.log('[REFRESH] appel loadCatalogue'); loadCatalogue(); }
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
// ── Widget variantes ──────────────────────────────────────────────────────────
function _showVariantForm(bubble, articleData) {
  _pendingArticleData = articleData;
  const form = document.createElement("div");
  form.className = "variant-form";
  form.innerHTML = `
    <div class="variant-form-title">Variantes pour ${articleData.nom || "l'article"}</div>
    <div class="variant-rows" id="variant-rows">
      <div class="variant-row">
        <input type="number" placeholder="Pointure" class="v-taille" min="30" max="50">
        <select class="v-couleur"><option value="">Couleur</option><option value="Argent">Argent</option><option value="Beige">Beige</option><option value="Beige naturel">Beige naturel</option><option value="Blanc">Blanc</option><option value="Blanc cassé">Blanc cassé</option><option value="Bleu">Bleu</option><option value="Bleu ardoise">Bleu ardoise</option><option value="Bleu ciel">Bleu ciel</option><option value="Bleu gris">Bleu gris</option><option value="Bleu indigo">Bleu indigo</option><option value="Bleu marine">Bleu marine</option><option value="Bleu nuit">Bleu nuit</option><option value="Bleu océan">Bleu océan</option><option value="Bleu pétrole">Bleu pétrole</option><option value="Bordeaux">Bordeaux</option><option value="Camel">Camel</option><option value="Champagne">Champagne</option><option value="Charbon">Charbon</option><option value="Cognac">Cognac</option><option value="Colorblock rouge-blanc">Colorblock rouge-blanc</option><option value="Corail">Corail</option><option value="Crème">Crème</option><option value="Gris">Gris</option><option value="Gris anthracite">Gris anthracite</option><option value="Gris ardoise">Gris ardoise</option><option value="Gris chiné">Gris chiné</option><option value="Gris foncé">Gris foncé</option><option value="Gris taupe">Gris taupe</option><option value="Jaune">Jaune</option><option value="Jaune fluo">Jaune fluo</option><option value="Kaki">Kaki</option><option value="Lilas">Lilas</option><option value="Marine">Marine</option><option value="Marron">Marron</option><option value="Marron foncé">Marron foncé</option><option value="Naturel">Naturel</option><option value="Noir">Noir</option><option value="Noir mat">Noir mat</option><option value="Noir vernis">Noir vernis</option><option value="Nude">Nude</option><option value="Or">Or</option><option value="Orange">Orange</option><option value="Orange sécurité">Orange sécurité</option><option value="Rose">Rose</option><option value="Rose fluo">Rose fluo</option><option value="Rose gold">Rose gold</option><option value="Rose poudré">Rose poudré</option><option value="Rouge">Rouge</option><option value="Rouge bordeaux">Rouge bordeaux</option><option value="Rouge carmin">Rouge carmin</option><option value="Rouge vif">Rouge vif</option><option value="Sable">Sable</option><option value="Terracotta">Terracotta</option><option value="Vert">Vert</option><option value="Vert aqua">Vert aqua</option><option value="Vert fluo">Vert fluo</option><option value="Vert forêt">Vert forêt</option><option value="Vert hunter">Vert hunter</option><option value="Vert kaki">Vert kaki</option><option value="Vert menthe">Vert menthe</option><option value="Vert olive">Vert olive</option><option value="Vert sauge">Vert sauge</option></select>
        <input type="number" placeholder="Stock" class="v-stock" min="0">
        <button class="v-remove" onclick="this.closest('.variant-row').remove()">✕</button>
      </div>
    </div>
    <button class="v-add" onclick="_addVariantRow()">+ Ajouter une ligne</button>
    <div class="variant-actions">
      <button class="v-cancel" onclick="this.closest('.variant-form').remove()">Annuler</button>
      <button class="v-submit" onclick="_submitVariants(this)">Valider</button>
    </div>
  `;
  bubble.querySelector(".achat-bubble").appendChild(form);
  _scrollToBottom();
}

function _addVariantRow() {
  const rows = document.getElementById("variant-rows");
  const row = document.createElement("div");
  row.className = "variant-row";
  row.innerHTML = `
    <input type="number" placeholder="Pointure" class="v-taille" min="30" max="50">
    <select class="v-couleur"><option value="">Couleur</option><option value="Argent">Argent</option><option value="Beige">Beige</option><option value="Beige naturel">Beige naturel</option><option value="Blanc">Blanc</option><option value="Blanc cassé">Blanc cassé</option><option value="Bleu">Bleu</option><option value="Bleu ardoise">Bleu ardoise</option><option value="Bleu ciel">Bleu ciel</option><option value="Bleu gris">Bleu gris</option><option value="Bleu indigo">Bleu indigo</option><option value="Bleu marine">Bleu marine</option><option value="Bleu nuit">Bleu nuit</option><option value="Bleu océan">Bleu océan</option><option value="Bleu pétrole">Bleu pétrole</option><option value="Bordeaux">Bordeaux</option><option value="Camel">Camel</option><option value="Champagne">Champagne</option><option value="Charbon">Charbon</option><option value="Cognac">Cognac</option><option value="Colorblock rouge-blanc">Colorblock rouge-blanc</option><option value="Corail">Corail</option><option value="Crème">Crème</option><option value="Gris">Gris</option><option value="Gris anthracite">Gris anthracite</option><option value="Gris ardoise">Gris ardoise</option><option value="Gris chiné">Gris chiné</option><option value="Gris foncé">Gris foncé</option><option value="Gris taupe">Gris taupe</option><option value="Jaune">Jaune</option><option value="Jaune fluo">Jaune fluo</option><option value="Kaki">Kaki</option><option value="Lilas">Lilas</option><option value="Marine">Marine</option><option value="Marron">Marron</option><option value="Marron foncé">Marron foncé</option><option value="Naturel">Naturel</option><option value="Noir">Noir</option><option value="Noir mat">Noir mat</option><option value="Noir vernis">Noir vernis</option><option value="Nude">Nude</option><option value="Or">Or</option><option value="Orange">Orange</option><option value="Orange sécurité">Orange sécurité</option><option value="Rose">Rose</option><option value="Rose fluo">Rose fluo</option><option value="Rose gold">Rose gold</option><option value="Rose poudré">Rose poudré</option><option value="Rouge">Rouge</option><option value="Rouge bordeaux">Rouge bordeaux</option><option value="Rouge carmin">Rouge carmin</option><option value="Rouge vif">Rouge vif</option><option value="Sable">Sable</option><option value="Terracotta">Terracotta</option><option value="Vert">Vert</option><option value="Vert aqua">Vert aqua</option><option value="Vert fluo">Vert fluo</option><option value="Vert forêt">Vert forêt</option><option value="Vert hunter">Vert hunter</option><option value="Vert kaki">Vert kaki</option><option value="Vert menthe">Vert menthe</option><option value="Vert olive">Vert olive</option><option value="Vert sauge">Vert sauge</option></select>
    <input type="number" placeholder="Stock" class="v-stock" min="0">
    <button class="v-remove" onclick="this.closest('.variant-row').remove()">✕</button>
  `;
  rows.appendChild(row);
  _scrollToBottom();
}

function _submitVariants(btn) {
  const articleData = _pendingArticleData || {};
  const rows = document.querySelectorAll(".variant-row");
  const variants = [];
  let valid = true;

  rows.forEach(row => {
    const taille  = parseInt(row.querySelector(".v-taille").value);
    const couleur = row.querySelector(".v-couleur").value.trim();
    const stock   = parseInt(row.querySelector(".v-stock").value);
    if (!taille || !couleur || isNaN(stock)) { valid = false; return; }
    variants.push({ taille, couleur, stock });
  });

  if (!valid || variants.length === 0) {
    alert("Veuillez remplir tous les champs de chaque variante.");
    return;
  }

  // Supprime le formulaire
  btn.closest(".variant-form").remove();
  // Envoie directement la creation avec toutes les infos deja collectees
  const msg = `Cree l'article avec ces donnees : ${JSON.stringify(articleData)} et ces variantes : ${JSON.stringify(variants)}`;
  document.getElementById("achat-input").value = msg;
  adminChatSend();
}

// ── Widget infos article ──────────────────────────────────────────────────────
function _showArticleDetailsForm(articleData, variants) {
  const msgs = document.getElementById("achat-messages");
  const wrap = document.createElement("div");
  wrap.className = "achat-msg bot";
  wrap.innerHTML = `<div class="achat-bubble">
    <div class="variant-form" id="article-details-form">
      <div class="variant-form-title">Informations complémentaires (optionnel)</div>
      <div style="margin-bottom:.6rem;font-size:.8rem;opacity:.7">Uploadez une image pour remplir automatiquement, ou saisissez manuellement.</div>
      <div style="margin-bottom:.6rem">
        <input type="file" id="ad-image-input" accept="image/*" style="display:none" onchange="_analyzeArticleImage(this)">
        <button class="v-add" onclick="document.getElementById('ad-image-input').click()">📷 Uploader une image</button>
        <div id="ad-image-status" style="font-size:.75rem;opacity:.7;margin-top:.3rem"></div>
      </div>
      <textarea class="ad-field" id="ad-description"    placeholder="Description…"         rows="2"></textarea>
      <textarea class="ad-field" id="ad-caracteristiques" placeholder="Caractéristiques…"  rows="2"></textarea>
      <textarea class="ad-field" id="ad-materiaux"      placeholder="Matériaux…"            rows="1"></textarea>
      <textarea class="ad-field" id="ad-usage"          placeholder="Usage recommandé…"     rows="1"></textarea>
      <textarea class="ad-field" id="ad-mots_cles"      placeholder="Mots-clés (séparés par des virgules)…" rows="1"></textarea>
      <div class="variant-actions" style="margin-top:.6rem">
        <button class="v-cancel" onclick="_skipArticleDetails()">Passer</button>
        <button class="v-submit" onclick="_submitArticleDetails()">Créer l'article</button>
      </div>
    </div>
  </div><div class="achat-time">${_now()}</div>`;
  msgs.appendChild(wrap);
  _scrollToBottom();
}

async function _analyzeArticleImage(input) {
  const file = input.files[0];
  if (!file) return;
  const status = document.getElementById("ad-image-status");
  status.textContent = "Analyse en cours…";

  const reader = new FileReader();
  reader.onload = async ev => {
    const b64 = ev.target.result.split(",")[1];
    try {
      const resp = await fetch(`${ADMIN_API_URL}/admin/analyze-image`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({image_b64: b64})
      });
      const data = await resp.json();
      if (data.success) {
        const d = data.data;
        if (d.description)     document.getElementById("ad-description").value     = d.description;
        if (d.caracteristiques) document.getElementById("ad-caracteristiques").value = d.caracteristiques;
        if (d.materiaux)       document.getElementById("ad-materiaux").value       = d.materiaux;
        if (d.usage)           document.getElementById("ad-usage").value           = d.usage;
        if (d.mots_cles)       document.getElementById("ad-mots_cles").value       = d.mots_cles;
        status.textContent = "✓ Infos extraites automatiquement";
        status.style.color = "#27ae60";

        // Upload l'image pour avoir l'url_image
        const form = new FormData();
        form.append("image", file);
        console.log("[UPLOAD] Tentative upload image...");
        const upResp = await fetch(`/admin/ajax/upload_image.php`, {method:"POST", body:form});
          console.log("[UPLOAD] status:", upResp.status, upResp.ok);
          const upText = await upResp.clone().text(); console.log("[UPLOAD] raw:", upText);
        const upData = await upResp.json();
          console.log("[UPLOAD] response:", upData);
        if (upData.success) {
          _pendingImageUrl = upData.url_image;
          console.log("[IMAGE] url_image:", _pendingImageUrl);
        }
      } else {
        status.textContent = "✗ Erreur analyse : " + data.message;
        status.style.color = "#c0392b";
      }
    } catch(e) {
      status.textContent = "✗ Erreur réseau";
      status.style.color = "#c0392b";
    }
  };
  reader.readAsDataURL(file);
}

function _submitArticleDetails() {
  const articleData = _pendingArticleData || {};
  const variants    = _pendingVariants || [];
  articleData.description     = document.getElementById("ad-description").value.trim();
  articleData.caracteristiques = document.getElementById("ad-caracteristiques").value.trim();
  articleData.materiaux       = document.getElementById("ad-materiaux").value.trim();
  articleData.usage           = document.getElementById("ad-usage").value.trim();
  articleData.mots_cles       = document.getElementById("ad-mots_cles").value.trim();
  console.log("[SUBMIT] _pendingImageUrl:", _pendingImageUrl);
  if (_pendingImageUrl) { articleData.url_image = _pendingImageUrl; _pendingImageUrl = null; }

  document.getElementById("article-details-form").closest(".achat-msg").remove();
  const msg = `Crée l'article avec ces données : ${JSON.stringify(articleData)} et ces variantes : ${JSON.stringify(variants)}`;
  document.getElementById("achat-input").value = msg;
  adminChatSend();
}

function _skipArticleDetails() {
  const articleData = _pendingArticleData || {};
  const variants    = _pendingVariants || [];
  document.getElementById("article-details-form").closest(".achat-msg").remove();
  const msg = `Crée l'article avec ces données : ${JSON.stringify(articleData)} et ces variantes : ${JSON.stringify(variants)}`;
  document.getElementById("achat-input").value = msg;
  adminChatSend();
}

// ── Formulaire article complet ────────────────────────────────────────────────
const CATEGORIES = ["Baskets lifestyle","Baskets sport","Bottines","Danse","Espadrilles","Imperméables","Indoor","Marche","Minimalistes","Mocassins","Montantes légères","Randonnée","Running","Sabots","Sandales","Sécurité","Slip-on","Talons","Training","Vegan"];
const GENRES = ["Mixte","Homme","Femme"];

function _showArticleForm(articleData) {
  _pendingArticleData = articleData || {};
  const msgs = document.getElementById("achat-messages");
  const wrap = document.createElement("div");
  wrap.className = "achat-msg bot";
  const catOptions = CATEGORIES.map(c => `<option value="${c}" ${c === articleData.categorie ? 'selected' : ''}>${c}</option>`).join('');
  const genreOptions = GENRES.map(g => `<option value="${g}" ${g === articleData.genre ? 'selected' : ''}>${g}</option>`).join('');
  wrap.innerHTML = `<div class="achat-bubble">
    <div class="variant-form" id="article-main-form">
      <div class="variant-form-title">Informations de l'article</div>
      <div class="article-form-grid">
        <div class="af-field"><label>Nom *</label><input type="text" id="af-nom" value="${articleData.nom || ''}" placeholder="Nom"></div>
        <div class="af-field"><label>Marque *</label><input type="text" id="af-marque" value="${articleData.marque || ''}" placeholder="Marque"></div>
        <div class="af-field"><label>Catégorie *</label><select id="af-categorie"><option value="">Choisir...</option>${catOptions}</select></div>
        <div class="af-field"><label>Genre *</label><select id="af-genre"><option value="">Choisir...</option>${genreOptions}</select></div>
        <div class="af-field"><label>Prix (€) *</label><input type="number" id="af-prix" value="${articleData.prix || ''}" placeholder="Prix" step="0.01"></div>
        <div class="af-field af-full"><label>Image</label>
          <input type="file" id="af-image-input" accept="image/*" style="display:none" onchange="_analyzeAndPreviewImage(this)">
          <button class="v-add" onclick="document.getElementById('af-image-input').click()">📷 Uploader une image</button>
          <div id="af-image-status" style="font-size:.75rem;margin-top:.3rem;opacity:.7"></div>
          <div id="af-image-preview" style="margin-top:.4rem"></div>
        </div>
        <div class="af-field af-full"><label>Description</label><textarea id="af-description" rows="3" placeholder="Description commerciale…">${articleData.description || ''}</textarea></div>
        <div class="af-field af-full"><label>Caractéristiques</label><textarea id="af-caracteristiques" rows="2" placeholder="Ex: Ultra légères, Respirantes…">${articleData.caracteristiques || ''}</textarea></div>
        <div class="af-field"><label>Matériaux</label><input type="text" id="af-materiaux" value="${articleData.materiaux || ''}" placeholder="Ex: Cuir, mesh…"></div>
        <div class="af-field"><label>Usage</label><input type="text" id="af-usage" value="${articleData.usage || ''}" placeholder="Ex: Running, ville…"></div>
        <div class="af-field af-full"><label>Mots-clés</label><input type="text" id="af-mots_cles" value="${articleData.mots_cles || ''}" placeholder="Ex: sport, confort…"></div>
      </div>
      <div class="variant-actions" style="margin-top:.8rem">
        <button class="v-cancel" onclick="this.closest('.achat-msg').remove()">Annuler</button>
        <button class="v-submit" onclick="_validateArticleForm()">Suivant → Variantes</button>
      </div>
    </div>
  </div><div class="achat-time">${_now()}</div>`;
  msgs.appendChild(wrap);
  _scrollToBottom();
}

async function _analyzeAndPreviewImage(input) {
  const file = input.files[0];
  if (!file) return;
  const status = document.getElementById("af-image-status");
  const preview = document.getElementById("af-image-preview");
  status.textContent = "Analyse en cours…";
  const reader = new FileReader();
  reader.onload = async ev => {
    preview.innerHTML = `<img src="${ev.target.result}" style="max-height:80px;border-radius:6px">`;
    const b64 = ev.target.result.split(",")[1];
    // Affiche "Chargement..." dans les champs
    ["af-description","af-caracteristiques","af-materiaux","af-usage","af-mots_cles"].forEach(id => {
      const el = document.getElementById(id);
      if (el && !el.value) { el.value = "Chargement..."; el.style.opacity = "0.4"; }
    });
    try {
      const resp = await fetch(`${ADMIN_API_URL}/admin/analyze-image`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({image_b64: b64})
      });
      const data = await resp.json();
      if (data.success) {
        const d = data.data;
        const _isEmpty = v => !v || v === "Chargement...";
        if (d.description && _isEmpty(document.getElementById("af-description").value)) document.getElementById("af-description").value = d.description;
        if (d.caracteristiques && _isEmpty(document.getElementById("af-caracteristiques").value)) document.getElementById("af-caracteristiques").value = d.caracteristiques;
        if (d.materiaux && _isEmpty(document.getElementById("af-materiaux").value)) document.getElementById("af-materiaux").value = d.materiaux;
        if (d.usage && _isEmpty(document.getElementById("af-usage").value)) document.getElementById("af-usage").value = d.usage;
        if (d.mots_cles && _isEmpty(document.getElementById("af-mots_cles").value)) document.getElementById("af-mots_cles").value = d.mots_cles;
        status.textContent = "✓ Infos extraites"; status.style.color = "#27ae60";
        ["af-description","af-caracteristiques","af-materiaux","af-usage","af-mots_cles"].forEach(id => {
          const el = document.getElementById(id);
          if (el) el.style.opacity = "1";
        });
      }
    } catch(e) {
      status.textContent = "✗ Analyse échouée"; status.style.color = "#c0392b";
      ["af-description","af-caracteristiques","af-materiaux","af-usage","af-mots_cles"].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.value === "Chargement...") { el.value = ""; el.style.opacity = "1"; }
      });
    }
    const form = new FormData();
    form.append("image", file);
    try {
      const upResp = await fetch(`/admin/ajax/upload_image.php`, {method:"POST", body:form});
      const upData = await upResp.json();
      if (upData.success) _pendingImageUrl = upData.url_image;
    } catch(e) {}
  };
  reader.readAsDataURL(file);
}

function _validateArticleForm() {
  const nom = document.getElementById("af-nom").value.trim();
  const marque = document.getElementById("af-marque").value.trim();
  const categorie = document.getElementById("af-categorie").value;
  const genre = document.getElementById("af-genre").value;
  const prix = parseFloat(document.getElementById("af-prix").value);
  if (!nom || !marque || !categorie || !genre || !prix) {
    alert("Veuillez remplir tous les champs obligatoires (*)");
    return;
  }
  const articleData = {
    nom, marque, categorie, genre, prix,
    description: document.getElementById("af-description").value.trim(),
    caracteristiques: document.getElementById("af-caracteristiques").value.trim(),
    materiaux: document.getElementById("af-materiaux").value.trim(),
    usage: document.getElementById("af-usage").value.trim(),
    mots_cles: document.getElementById("af-mots_cles").value.trim(),
  };
  if (_pendingImageUrl) { articleData.url_image = _pendingImageUrl; _pendingImageUrl = null; }
  _pendingArticleData = articleData;
  document.getElementById("article-main-form").closest(".achat-msg").remove();
  const varBubble = _createBotBubble();
  varBubble.querySelector(".achat-bubble").innerHTML = "Ajoutez les variantes (taille, couleur, stock) :";
  _showVariantForm(varBubble, articleData);
}
