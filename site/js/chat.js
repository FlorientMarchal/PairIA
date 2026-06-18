// js/chat.js
const API_URL = "http://172.27.30.30:8000";

let conversationHistory = JSON.parse(
  sessionStorage.getItem("chatHistory") || "[]",
);
let sessionId = sessionStorage.getItem("chatSessionId") || ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
sessionStorage.setItem("chatSessionId", sessionId);

// ID de session BDD (null si non connecté ou pas encore créée)
let dbSessionId = sessionStorage.getItem("dbSessionId")
  ? parseInt(sessionStorage.getItem("dbSessionId"))
  : null;

// ══════════════════════════════════════════════
// SYSTÈME DE TRADUCTION UI
// ══════════════════════════════════════════════

// Labels FR — source de vérité. Les valeurs fonctionnelles (couleurs, tailles)
// restent en français en interne pour que Qdrant et les filtres fonctionnent.
const UI_LABELS_FR = {
  suggestions: "Voici quelques suggestions",
  addToCart: "🛒 Ajouter au panier",
  chooseModel: "🛒 Choisir ce modèle",
  confirm: "Confirmer l'ajout",
  added: "✓ Ajouté au panier !",
  cancel: "✗ Annuler",
  fav: "Ajouter aux favoris",
  comparison: "Comparaison",
  size: "Pointure",
  color: "Couleur",
  brand: "Marque",
  category: "Catégorie",
  sizes: "Tailles",
  colors: "Couleurs",
  errorCart: "Erreur lors de l'ajout.",
  errorUnavailable: "Combinaison indisponible.",
  errorNoSize: "Veuillez sélectionner une taille et une couleur.",
  errorLogin: "Vous devez être connecté pour ajouter au panier.",
  errorProduct: "Produit introuvable.",
  errorNetwork: "Erreur réseau",
  analyzing: "Analyse en cours...",
  unavailable:
    "Désolé, je suis temporairement indisponible. Réessayez dans un instant.",
  unavailableImg:
    "Désolé, la recherche par image est temporairement indisponible.",
  welcome:
    "Bonjour ! Je suis votre conseiller PairIA, posez-moi vos questions 👟",
  sizeLabel: "taille",
};

// Cache par langue — évite les appels LLM répétés
const _uiTranslationsCache = { fr: UI_LABELS_FR };

// Langue courante de l'interface
let currentLangue = sessionStorage.getItem("chatLangue") || "fr";

// ── Timestamps localisés ──────────────────────────────────────────────────
// Chaque message reçoit un data-ts (epoch ms). Un ticker toutes les 30s
// met à jour l'affichage : "maintenant" / "il y a 2 min" / "14:32" etc.
// Entièrement géré par l'API Intl — aucune traduction LLM nécessaire.

function _formatTime(tsMs, locale) {
  const lang = locale || currentLangue || "fr";
  const diffSec = Math.round((Date.now() - tsMs) / 1000);
  if (diffSec < 60) {
    // "maintenant" / "just now" / "ahora" … via RelativeTimeFormat
    try {
      return new Intl.RelativeTimeFormat(lang, { numeric: "auto" }).format(
        0,
        "second",
      );
    } catch (_) {
      return "now";
    }
  }
  // Au-delà d'une minute : afficher l'heure HH:MM
  try {
    return new Intl.DateTimeFormat(lang, {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(tsMs));
  } catch (_) {
    const d = new Date(tsMs);
    return (
      String(d.getHours()).padStart(2, "0") +
      ":" +
      String(d.getMinutes()).padStart(2, "0")
    );
  }
}

function _refreshTimestamps() {
  document.querySelectorAll(".chat-time[data-ts]").forEach((el) => {
    el.textContent = _formatTime(parseInt(el.dataset.ts), currentLangue);
  });
}
// Rafraîchir toutes les 30 secondes
setInterval(_refreshTimestamps, 30_000);

let questionFr = null;

// Charge les traductions pour une langue (un seul appel LLM, puis cache)
async function loadUITranslations(langue) {
  if (!langue || langue === "fr") return UI_LABELS_FR;
  if (_uiTranslationsCache[langue]) return _uiTranslationsCache[langue];
  try {
    const res = await fetch(`${API_URL}/translate-ui`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texts: UI_LABELS_FR, langue }),
    });
    const data = await res.json();
    _uiTranslationsCache[langue] = data.translations;
    console.log(`[UI] traductions chargées pour ${langue}`);
    return data.translations;
  } catch (e) {
    console.warn(`[UI] échec traduction ${langue}, fallback FR`);
    return UI_LABELS_FR;
  }
}

// Accès synchrone au cache (utilise toujours ce qui est déjà chargé)
function t(key, langue) {
  const lang = langue || currentLangue;
  const dict = _uiTranslationsCache[lang] || UI_LABELS_FR;
  return dict[key] ?? UI_LABELS_FR[key] ?? key;
}

async function _mettreAjourLangue(langue) {
  if (!langue) return;
  // Ne changer la langue que si c'est une détection fiable
  // (le backend a déjà filtré les textes courts, mais double sécurité)
  if (langue !== currentLangue) {
    currentLangue = langue;
    sessionStorage.setItem("chatLangue", langue);
    if (!_uiTranslationsCache[langue]) {
      await loadUITranslations(langue);
    }
    // Mettre à jour les timestamps déjà affichés dans la nouvelle langue
    _refreshTimestamps();
    // Mettre à jour le texte du message de bienvenue via son id
    const welcomeBubble = document.getElementById("welcome-bubble");
    if (welcomeBubble) {
      welcomeBubble.textContent = t("welcome");
    }
    // Mettre à jour "Analyse en cours..." si le typing indicator est visible
    const typingMsg = document.getElementById("typing-msg");
    if (typingMsg) typingMsg.textContent = t("analyzing");
  }
}

// ── Crée une session BDD au premier message ──
async function ensureDbSession(firstMessage) {
  if (dbSessionId) return dbSessionId;
  try {
    const titre = firstMessage.slice(0, 80);
    const res = await fetch("chat/session_new.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titre }),
    });
    const data = await res.json();
    if (data.success) {
      dbSessionId = data.session_id;
      sessionStorage.setItem("dbSessionId", dbSessionId);
    }
  } catch (e) {}
  return dbSessionId;
}

// ── Sauvegarde un message en base ──
async function saveMessageToDB(
  role,
  content,
  products = [],
  layout = null,
  silent = false,
  internal = false,
) {
  if (!dbSessionId) return;
  try {
    await fetch("chat/history_save.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        role,
        message: content,
        session_id: dbSessionId,
        products,
        layout,
        silent,
        internal,
      }),
    });
  } catch (e) {}
}

// ── Charge la liste des sessions ──
async function loadSessionList() {
  try {
    const res = await fetch("chat/session_list.php");
    const data = await res.json();
    return data.sessions || [];
  } catch (e) {
    return [];
  }
}

// ── Charge les messages d'une session ──
async function loadSessionMessages(sessionId) {
  try {
    const res = await fetch(`chat/session_load.php?session_id=${sessionId}`);
    const data = await res.json();
    return data.history || [];
  } catch (e) {
    return [];
  }
}

// APRÈS — utiliser t() pour les labels traduits, et traduire taille/couleur dynamiquement
async function _messageConfirmationPanier(name, taille, couleur) {
  const langue = sessionStorage.getItem("chatLangue") || "fr";
  let tailleLabel = taille ? `${t("sizeLabel")} ${taille}` : "";

  // Traduire la couleur si elle est en français et qu'on est dans une autre langue
  let couleurLabel = couleur || "";
  if (couleur && langue !== "fr") {
    const cache = await traduireValeursDynamiques([couleur], langue);
    couleurLabel = cache[couleur] || couleur;
  }

  const details = [tailleLabel, couleurLabel].filter(Boolean).join(", ");
  // "added" est déjà traduit via t()
  return `${t("added")} ${name}${details ? ` (${details})` : ""}`;
}

/*
   CHAT TEXTE
*/
// Mots de confirmation pour valider une carte panier par message
// Filtre l'historique pour n'envoyer que les vrais échanges au backend
function _histoirePropre() {
  return conversationHistory.filter(
    (m) =>
      !m.internal && !(m.role === "user" && m.silent) && m.role !== "system",
  );
}

const _CONFIRMATIONS_MSG = [
  "oui",
  "yes",
  "ok",
  "ouais",
  "c'est bon",
  "c bon",
  "parfait",
  "confirme",
  "go",
  "vas y",
  "vas-y",
  "d'accord",
  "exact",
  "correct",
  "oui je confirme",
  "oui c'est ça",
  "oui c'est bon",
  "allez",
  "yep",
  "je confirme",
  "je valide",
  "c'est ça",
  "c'est exact",
  "ajoute",
  "ajoute le",
  "ajoute la",
  "ajoute les",
  "ok c'est bon",
  "nickel",
  "super",
  "top",
  "impeccable",
  "parfait merci",
];

// Détecte le tutoiement depuis le texte de l'utilisateur et le stocke
function _detecterEtStockerTutoiement(text) {
  const q = text.toLowerCase();
  const moisVous = [
    "vous avez",
    "vous êtes",
    "avez-vous",
    "pouvez-vous",
    "faites-vous",
  ];
  const moisTu = [
    "tu as",
    "t'as",
    "tu es",
    "t'es",
    "as-tu",
    "es-tu",
    "peux-tu",
  ];
  if (moisVous.some((m) => q.includes(m))) {
    sessionStorage.setItem("chatTutoiement", "vous");
  } else if (moisTu.some((m) => q.includes(m))) {
    sessionStorage.setItem("chatTutoiement", "tu");
  }
}

let _sendingLock = false;

let _currentAbortController = null;

function _setGenerating(isGenerating) {
  const stopBtn = document.getElementById("chat-stop-btn");
  const sendBtn = document.getElementById("chat-send-btn");
  const imgBtn = document.querySelector(".chat-image-btn");
  const voiceBtn = document.getElementById("voice-btn");

  if (isGenerating) {
    if (stopBtn) stopBtn.style.display = "flex";
    if (sendBtn) sendBtn.style.display = "none";
    if (imgBtn) {
      imgBtn.disabled = true;
      imgBtn.style.opacity = "0.4";
      imgBtn.title = "Indisponible pendant la génération";
    }
    if (voiceBtn && voiceBtn.style.display !== "none") {
      voiceBtn.disabled = true;
      voiceBtn.style.opacity = "0.4";
    }
  } else {
    if (stopBtn) stopBtn.style.display = "none";
    if (sendBtn) sendBtn.style.display = "";
    if (imgBtn) {
      imgBtn.disabled = false;
      imgBtn.style.opacity = "";
      imgBtn.title = "Rechercher par image";
    }
    if (voiceBtn) {
      voiceBtn.disabled = false;
      voiceBtn.style.opacity = "";
    }
    _currentAbortController = null;
  }
}

function stopGeneration() {
  if (_currentAbortController) {
    _currentAbortController.abort();
  }
}

async function sendMessage(text) {
  if (_sendingLock) return; // bloquer les doubles envois
  _sendingLock = true;
  try {
    await _sendMessageImpl(text);
  } finally {
    _sendingLock = false;
  }
}

async function _sendMessageImpl(text) {
  let questionFr = null;
  let layout = null;
  const container = document.getElementById("messages");
  if (!container || !text.trim()) return;

  // Vérifier si le bot attend une réponse à une question ouverte (panier)
  const pendingFollowUp = sessionStorage.getItem("pendingFollowUp");
  if (pendingFollowUp === "panier") {
    const textLower = text.trim().toLowerCase().replace(/[?!.]/g, "");
    // Réponse négative → effacer et laisser passer normalement
    if (
      [
        "non",
        "non merci",
        "ça va",
        "c'est bon",
        "pas besoin",
        "no",
        "nope",
      ].includes(textLower)
    ) {
      sessionStorage.removeItem("pendingFollowUp");
      // Laisser passer au backend normalement
    }
    // Réponse affirmative courte → transformer en vraie question
    else if (
      [
        "oui",
        "yes",
        "ok",
        "ouais",
        "yep",
        "volontiers",
        "avec plaisir",
      ].includes(textLower)
    ) {
      sessionStorage.removeItem("pendingFollowUp");
      appendUserMessage(text);
      // Envoyer une vraie question au bot
      await sendMessage("je cherche d'autres chaussures, tu peux m'aider ?");
      return;
    }
    // Sinon (vraie phrase) → effacer le pending et laisser passer
    else {
      sessionStorage.removeItem("pendingFollowUp");
    }
  }

  // Vérifier si une confirmation panier est en attente
  const pendingRaw = sessionStorage.getItem("pendingCartConfirm");
  if (
    pendingRaw &&
    _CONFIRMATIONS_MSG.includes(text.trim().toLowerCase().replace(/[?!.]/g, ""))
  ) {
    try {
      const pending = JSON.parse(pendingRaw);
      appendUserMessage(text);
      const result = await addToCart(
        pending.id,
        1,
        pending.taille,
        pending.couleur,
      );
      if (result?.success) {
        sessionStorage.removeItem("pendingCartConfirm");
        // Marquer le bouton de la carte comme confirmé
        const btns = document.querySelectorAll(".chat-cart-btn");
        btns.forEach((btn) => {
          if (btn.textContent.includes("Confirmer")) {
            btn.textContent = t("added");
            btn.style.background = "#2f855a";
            btn.disabled = true;
            btn
              .closest(".chat-product-card")
              ?.querySelector("button[style*='e53e3e']")
              ?.remove();
          }
        });
        // APRÈS
        const msgConfirm = await _messageConfirmationPanier(
          pending.name,
          pending.taille,
          pending.couleur,
        );
        appendBotMessageText(msgConfirm);
      } else {
        appendBotMessageText(
          result?.error || "Erreur lors de l'ajout au panier.",
        );
      }
      return;
    } catch (e) {}
  }

  const input = document.getElementById("chat-input");
  const sendBtn = document.querySelector(".chat-send-btn");
  if (input) input.disabled = true;
  if (sendBtn) sendBtn.disabled = true;

  _detecterEtStockerTutoiement(text);
  appendUserMessage(text);
  const typing = appendTyping();

  // ── DEBUG ──
  console.group("[CHAT TEXTE] Envoi");
  console.log("question :", text);
  console.log("session_id :", sessionId);
  console.log(
    "history (" + conversationHistory.length + " msgs) :",
    JSON.parse(JSON.stringify(conversationHistory)),
  );
  console.groupEnd();

  try {
    // N'envoyer que les vrais échanges — pas les prompts internes ni messages silencieux
    const historyToSend = _histoirePropre();
    const body = {
      question: text,
      history: historyToSend,
      session_id: sessionId,
      langue_session:
        sessionStorage.getItem("chatLangue") || currentLangue || "fr",
    };
    if (typeof PRODUCT_ID !== "undefined") body.product_id = PRODUCT_ID;

    _currentAbortController = new AbortController();
    _setGenerating(true);

    let response;
    try {
      response = await fetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: _currentAbortController.signal,
      });
    } catch (err) {
      if (err.name === "AbortError") {
        typing.remove();
        return;
      }
      throw err;
    }

    let typingRemoved = false;
    let bubbleDiv = null;
    let bubble = null;
    const time = document.createElement("div");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let message = "";
    let products = [];
    let action = null;
    let product_id = null;
    let taille = null;
    let couleur = null;
    let show_products = true;
    let confirm_required = true;
    let langueRecue = null; // ← stocké pendant le parsing, appliqué AVANT l'affichage

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") break;

          try {
            // Remplace le bloc de parsing data dans les deux fonctions
            const data = JSON.parse(raw);

            // Langue en debut de stream -> non bloquant
            if (data.type === "langue_detect") {
              if (data.langue && data.langue !== currentLangue) {
                currentLangue = data.langue;
                sessionStorage.setItem("chatLangue", data.langue);
                const _langue = data.langue;
                (async () => {
                  if (!_uiTranslationsCache[_langue]) {
                    await loadUITranslations(_langue);
                  }
                  _refreshTimestamps();
                  const wb = document.getElementById("welcome-bubble");
                  if (wb) wb.textContent = t("welcome");
                  const tm = document.getElementById("typing-msg");
                  if (tm) tm.textContent = t("analyzing");
                })();
              }
            } else if (data.type === "products_final") {
              products = data.products || [];
              action = data.action;
              product_id = data.product_id;
              layout = data.layout || null;
              taille = data.taille || null;
              couleur = data.couleur || null;
              show_products = data.show_products !== false;
              confirm_required = data.confirm_required !== false;
              if (data.langue) langueRecue = data.langue;
              if (data.tutoiement)
                sessionStorage.setItem("chatTutoiement", data.tutoiement);
              if (data.couleur)
                sessionStorage.setItem("lastNormalizedCouleur", data.couleur);
              if (data.question_fr) questionFr = data.question_fr;
            } // ← accolade fermante du if products_final
            else if (
              data.products !== undefined &&
              data.products.length === 0
            ) {
              // Metadata initiale vide — on ignore
            } else if (data.chunk !== undefined) {
              // Token texte — streaming normal
              if (!typingRemoved) {
                typing.remove();
                typingRemoved = true;
                const bubbleDiv = document.createElement("div");
                bubbleDiv.className = "chat-msg bot";
                bubble = document.createElement("div");
                bubble.className = "chat-bubble";
                const time = document.createElement("div");
                time.className = "chat-time";
                time.dataset.ts = Date.now();
                time.textContent = _formatTime(Date.now());
                bubbleDiv.appendChild(bubble);
                bubbleDiv.appendChild(time);
                container.appendChild(bubbleDiv);
              }
              message += data.chunk;
              bubble.textContent = message;
              container.scrollTop = container.scrollHeight;
            }
          } catch (e) {}
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") throw err;
      // Arrêt propre par l'utilisateur — on garde le texte déjà streamé dans bubble
      if (!typingRemoved) typing.remove();
      return;
    }

    // ✅ Appliquer la langue AVANT d'afficher les cartes — les traductions sont prêtes
    if (langueRecue) await _mettreAjourLangue(langueRecue);

    // Si une couleur a été normalisée (ex: Rouge→Bordeaux), l'intégrer dans le message user
    const normalizedCouleur = sessionStorage.getItem("lastNormalizedCouleur");
    const textToStore =
      normalizedCouleur && couleur && normalizedCouleur !== couleur
        ? text + ` [couleur:${normalizedCouleur}]`
        : text;
    if (normalizedCouleur) sessionStorage.removeItem("lastNormalizedCouleur");

    conversationHistory.push({
      role: "user",
      content: questionFr || textToStore,
    });
    conversationHistory.push({
      role: "assistant",
      content: message,
      products: products,
      layout: layout,
    });
    // Sauvegarde dans la base de données
    await ensureDbSession(text);
    await saveMessageToDB("user", text);
    await saveMessageToDB("assistant", message, products, layout);
    if (conversationHistory.length > 20)
      conversationHistory = conversationHistory.slice(-20);
    sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory)); // ← ajoute

    console.log(
      "[HISTORIQUE MIS À JOUR]",
      JSON.parse(JSON.stringify(conversationHistory)),
    );

    if (show_products) {
      if (layout === "comparison" && products.length >= 2) {
        await showComparisonView(products[0], products[1], container);
      } else if (products.length === 1 && !action) {
        await showCartSelector(products[0], container);
      } else if (products.length > 1 && !action) {
        await showProductPicker(products, container);
      }
    }

    if (action === "add_to_cart" && product_id) {
      const produit = products.find((p) => p.id === product_id) || products[0];
      if (produit) {
        const needsTaille = (produit.tailles || []).length > 0;
        const needsCouleur = (produit.couleurs || []).length > 0;
        const hasTaille = !!taille;
        const hasCouleur = !!couleur;
        const infoComplete =
          (!needsTaille || hasTaille) && (!needsCouleur || hasCouleur);

        if (infoComplete) {
          // Toujours afficher la carte de confirmation
          showCartConfirm(produit, taille, couleur, container);
        } else {
          // Infos manquantes → le bot a déjà demandé, pas de carte
        }
      }
    }

    container.scrollTop = container.scrollHeight;
  } catch (error) {
    typing.remove();
    appendBotMessageText(t("unavailable"));
    console.error("Erreur API chat :", error);
  } finally {
    _setGenerating(false);
    if (input) {
      input.disabled = false;
      input.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
  }
}

function sendFromInput() {
  const input = document.getElementById("chat-input");
  const text = input?.value || "";

  if (pendingImageFile) {
    input.value = "";
    input.placeholder = "Posez votre question...";
    const file = pendingImageFile;
    pendingImageFile = null;
    const preview = document.getElementById("image-preview-bar");
    if (preview) preview.style.display = "none";
    sendImageWithText(file, text);
  } else {
    if (!text.trim()) return;
    input.value = "";
    sendMessage(text);
  }
}

/*
   CHAT IMAGE + TEXTE
*/
async function sendImageWithText(file, text) {
  let taille = null;
  let couleur = null;
  let show_products = true;
  let confirm_required = true;
  let layout = null;
  const container = document.getElementById("messages");
  if (!container) return;

  const input = document.getElementById("chat-input");
  const sendBtn = document.querySelector(".chat-send-btn");
  if (input) input.disabled = true;
  if (sendBtn) sendBtn.disabled = true;

  // Bulle utilisateur : image + texte éventuel
  const imageUrl = URL.createObjectURL(file);
  const userDiv = document.createElement("div");
  userDiv.className = "chat-msg user";
  userDiv.innerHTML = `
    <div class="chat-bubble chat-bubble-image">
      <img src="${imageUrl}" alt="Image recherche"
           style="max-width:200px;max-height:200px;border-radius:8px;display:block;">
      ${text ? `<div style="margin-top:6px">${escapeHtml(text)}</div>` : ""}
    </div>
    <div class="chat-time" data-ts="${Date.now()}">${_formatTime(Date.now())}</div>`;
  container.appendChild(userDiv);
  container.scrollTop = container.scrollHeight;

  const typing = appendTyping();

  // ── DEBUG ──
  console.group("[CHAT IMAGE] Envoi");
  console.log("question :", text);
  console.log("session_id :", sessionId);
  console.log(
    "history (" + conversationHistory.length + " msgs) :",
    JSON.parse(JSON.stringify(conversationHistory)),
  );
  console.groupEnd();

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("question", text || "");
    const historyToSendImg = _histoirePropre();
    formData.append("history", JSON.stringify(historyToSendImg));
    formData.append("session_id", sessionId);
    formData.append(
      "langue_session",
      sessionStorage.getItem("chatLangue") || currentLangue || "fr",
    );

    _currentAbortController = new AbortController();
    _setGenerating(true);

    let response;
    try {
      response = await fetch(`${API_URL}/chat/stream-image`, {
        method: "POST",
        body: formData,
        signal: _currentAbortController.signal,
      });
    } catch (err) {
      if (err.name === "AbortError") {
        typing.remove();
        return;
      }
      throw err;
    }

    let typingRemoved = false;
    let bubble = null;
    let message = "";
    let products = [];
    let action = null;
    let product_id = null;
    let langueRecue = null; // ← stocké pendant le parsing

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (raw === "[DONE]") break;

          try {
            // Remplace le bloc de parsing data dans les deux fonctions
            const data = JSON.parse(raw);

            // Langue en debut de stream -> non bloquant
            if (data.type === "langue_detect") {
              if (data.langue && data.langue !== currentLangue) {
                currentLangue = data.langue;
                sessionStorage.setItem("chatLangue", data.langue);
                const _langue = data.langue;
                (async () => {
                  if (!_uiTranslationsCache[_langue]) {
                    await loadUITranslations(_langue);
                  }
                  _refreshTimestamps();
                  const wb = document.getElementById("welcome-bubble");
                  if (wb) wb.textContent = t("welcome");
                  const tm = document.getElementById("typing-msg");
                  if (tm) tm.textContent = t("analyzing");
                })();
              }
            } else if (data.type === "products_final") {
              products = data.products || [];
              action = data.action;
              product_id = data.product_id;
              layout = data.layout || null;
              taille = data.taille || null;
              couleur = data.couleur || null;
              show_products = data.show_products !== false;
              confirm_required = data.confirm_required !== false;
              if (data.langue) langueRecue = data.langue; // ← AJOUTER cette ligne
              if (data.tutoiement)
                sessionStorage.setItem("chatTutoiement", data.tutoiement);
              if (data.couleur)
                sessionStorage.setItem("lastNormalizedCouleur", data.couleur);
              if (data.question_fr) questionFr = data.question_fr;
            } else if (
              data.products !== undefined &&
              data.products.length === 0
            ) {
              // Metadata initiale vide — on ignore
            } else if (data.chunk !== undefined) {
              // Token texte — streaming normal
              if (!typingRemoved) {
                typing.remove();
                typingRemoved = true;
                const bubbleDiv = document.createElement("div");
                bubbleDiv.className = "chat-msg bot";
                bubble = document.createElement("div");
                bubble.className = "chat-bubble";
                const time = document.createElement("div");
                time.className = "chat-time";
                time.dataset.ts = Date.now();
                time.textContent = _formatTime(Date.now());
                bubbleDiv.appendChild(bubble);
                bubbleDiv.appendChild(time);
                container.appendChild(bubbleDiv);
              }
              message += data.chunk;
              bubble.textContent = message;
              container.scrollTop = container.scrollHeight;
            }
          } catch (e) {}
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") throw err;
      // Arrêt propre par l'utilisateur — on garde le texte déjà streamé dans bubble
      if (!typingRemoved) typing.remove();
      return;
    }

    // ✅ Appliquer la langue AVANT d'afficher les cartes
    if (langueRecue) await _mettreAjourLangue(langueRecue);

    // Historique : description textuelle de l'image + produits trouvés
    const productContext =
      products.length > 0
        ? products.map((p) => `${p.name} (${p.price.toFixed(2)}€)`).join(", ")
        : "aucun produit trouvé";

    const imageContext =
      `[Recherche par image${text ? ` avec message : "${text}"` : ""}] ` +
      `Produits suggérés : ${productContext}`;

    conversationHistory.push({ role: "user", content: imageContext });
    conversationHistory.push({
      role: "assistant",
      content: message,
      products: products,
    });

    await ensureDbSession(imageContext);
    await saveMessageToDB("user", imageContext);
    await saveMessageToDB("assistant", message, products);

    if (conversationHistory.length > 20)
      conversationHistory = conversationHistory.slice(-20);
    sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory)); // ← ajoute

    console.log(
      "[HISTORIQUE MIS À JOUR]",
      JSON.parse(JSON.stringify(conversationHistory)),
    );

    if (layout === "comparison" && products.length >= 2) {
      await showComparisonView(products[0], products[1], container);
    } else if (products.length === 1) {
      await showCartSelector(products[0], container);
    } else if (products.length > 1) {
      await showProductPicker(products, container);
    }

    if (action === "add_to_cart" && product_id) {
      const produit = products.find((p) => p.id === product_id) || products[0];
      if (produit) showCartSelector(produit);
    }

    container.scrollTop = container.scrollHeight;
  } catch (error) {
    typing.remove();
    appendBotMessageText(t("unavailableImg"));
    console.error("Erreur image+texte :", error);
  } finally {
    _setGenerating(false);
    if (input) {
      input.disabled = false;
      input.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
  }
}

function resetConversation() {
  conversationHistory = [];
  sessionId = ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  dbSessionId = null;
  currentLangue = "fr";
  sessionStorage.removeItem("chatHistory");
  sessionStorage.removeItem("dbSessionId");
  sessionStorage.removeItem("chatLangue");
  sessionStorage.setItem("chatSessionId", sessionId);

  const container = document.getElementById("messages");
  if (container) container.innerHTML = "";
  closeHistoryPanel();
}

/* ══════════════════════════════════════
   BULLES
══════════════════════════════════════ */
function appendUserMessage(text) {
  const container = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "chat-msg user";
  div.innerHTML = `
    <div class="chat-bubble">${escapeHtml(text)}</div>
    <div class="chat-time" data-ts="${Date.now()}">${_formatTime(Date.now())}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendBotMessage(data) {
  const container = document.getElementById("messages");

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "chat-msg bot";
  bubbleDiv.innerHTML = `
    <div class="chat-bubble">${escapeHtml(data.message)}</div>
    <div class="chat-time" data-ts="${Date.now()}">${_formatTime(Date.now())}</div>`;
  container.appendChild(bubbleDiv);

  const products = data.products || [];

  if (products.length === 1) {
    showCartSelector(products[0], container);
  } else if (products.length > 1) {
    showProductPicker(products, container);
  }

  container.scrollTop = container.scrollHeight;
}

function appendBotMessageText(text) {
  const container = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "chat-msg bot";
  div.innerHTML = `
    <div class="chat-bubble">${escapeHtml(text)}</div>
    <div class="chat-time" data-ts="${Date.now()}">${_formatTime(Date.now())}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendTyping() {
  const container = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "chat-msg bot";
  div.id = "typing-indicator";

  div.innerHTML = `
    <div class="chat-bubble" style="opacity:0.7;font-size:0.9em">
      <span class="chat-shoe-steps"><span>👟</span><span>👟</span><span>👟</span></span>
    </div>
    <div class="chat-typing-msg"
         id="typing-msg"
         style="font-size:11px;color:#999;margin-top:4px;display:none">
      ${t("analyzing")}
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  setTimeout(() => {
    const msg = document.getElementById("typing-msg");
    if (msg) msg.style.display = "block";
  }, 5000);

  return div;
}

/* ══════════════════════════════════════
   CARTE MULTI-PRODUITS (picker)
══════════════════════════════════════ */

// ── Favoris depuis le chat ──
async function toggleFavChat(productId, btn) {
  try {
    const currentDir = window.location.pathname.substring(
      0,
      window.location.pathname.lastIndexOf("/") + 1,
    );
    const res = await fetch(currentDir + "favorites/toggle.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId }),
    });
    const data = await res.json();
    if (data.success) {
      btn.classList.toggle("active", data.action === "added");
      btn.textContent = data.action === "added" ? "❤️" : "🤍";
    } else if (data.error === "not_logged") {
      btn.title = "Connectez-vous pour ajouter aux favoris";
    }
  } catch (e) {}
}

// ── Skeleton loader pour les cartes produites pendant la traduction ──────────
function _appendCardsSkeleton(container, n = 3, layout = "list") {
  const div = document.createElement("div");
  div.className = "chat-msg bot";
  div.id = "cards-skeleton";

  if (layout === "comparison") {
    // Deux colonnes côte à côte comme la vraie comparaison
    div.innerHTML = `
      <div class="chat-compare-card">
        <div class="skel" style="height:12px;width:80px;margin-bottom:12px"></div>
        <div class="chat-compare-grid">
          <div class="chat-compare-col">
            <div class="skel" style="width:100%;aspect-ratio:1;border-radius:8px;margin-bottom:8px"></div>
            <div class="skel" style="height:12px;width:80%;margin-bottom:6px"></div>
            <div class="skel" style="height:11px;width:50%;margin-bottom:10px"></div>
            <div class="skel" style="height:9px;width:100%;margin-bottom:4px"></div>
            <div class="skel" style="height:9px;width:100%;margin-bottom:4px"></div>
            <div class="skel" style="height:9px;width:100%;margin-bottom:4px"></div>
            <div class="skel" style="height:9px;width:100%"></div>
          </div>
          <div style="flex-shrink:0;width:24px"></div>
          <div class="chat-compare-col">
            <div class="skel" style="width:100%;aspect-ratio:1;border-radius:8px;margin-bottom:8px"></div>
            <div class="skel" style="height:12px;width:80%;margin-bottom:6px"></div>
            <div class="skel" style="height:11px;width:50%;margin-bottom:10px"></div>
            <div class="skel" style="height:9px;width:100%;margin-bottom:4px"></div>
            <div class="skel" style="height:9px;width:100%;margin-bottom:4px"></div>
            <div class="skel" style="height:9px;width:100%;margin-bottom:4px"></div>
            <div class="skel" style="height:9px;width:100%"></div>
          </div>
        </div>
      </div>`;
  } else {
    // Cartes produits normales
    div.innerHTML = Array.from(
      { length: n },
      () => `
      <div class="chat-product-card" style="pointer-events:none">
        <div class="chat-product-top">
          <div class="skel" style="width:72px;height:72px;border-radius:14px;flex-shrink:0"></div>
          <div style="flex:1;display:flex;flex-direction:column;gap:8px;padding:4px 0">
            <div class="skel" style="height:13px;width:70%"></div>
            <div class="skel" style="height:12px;width:35%"></div>
            <div class="skel" style="height:11px;width:55%"></div>
          </div>
        </div>
        <div class="skel" style="height:32px;border-radius:8px;margin-top:4px"></div>
      </div>`,
    ).join("");
  }

  if (container) {
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }
  return div;
}

function _removeCardsSkeleton() {
  document.getElementById("cards-skeleton")?.remove();
}

// Traduit les messages d'erreur retournés par cart/add.php
function _cartErrorMsg(phpError) {
  if (!phpError) return t("errorCart");
  const e = phpError.toLowerCase();
  if (
    e.includes("combinaison") ||
    e.includes("unavailable") ||
    e.includes("indisponible")
  )
    return t("errorUnavailable");
  if (
    e.includes("taille") ||
    e.includes("couleur") ||
    e.includes("sélectionner") ||
    e.includes("select")
  )
    return t("errorNoSize");
  if (e.includes("connecté") || e.includes("connected") || e.includes("login"))
    return t("errorLogin");
  if (e.includes("introuvable") || e.includes("not found"))
    return t("errorProduct");
  return t("errorCart");
}

async function showProductPicker(produits, container) {
  if (!container) container = document.getElementById("messages");
  if (currentLangue !== "fr") {
    _appendCardsSkeleton(container, produits.length);
    const toutesValeurs = produits.flatMap((p) => [
      ...(p.tailles || []).map(String),
      ...(p.couleurs || []),
    ]);
    const cache = await traduireValeursDynamiques(toutesValeurs, currentLangue);
    _removeCardsSkeleton();
    produits = produits.map((p) => ({
      ...p,
      tailles_fr: (p.tailles || []).map(String), // originaux FR pour cart/add.php
      couleurs_fr: p.couleurs || [],
      tailles: (p.tailles || []).map((v) => cache[String(v)] || v),
      couleurs: (p.couleurs || []).map((v) => cache[v] || v),
    }));
  } else {
    // En FR les valeurs sont déjà les bonnes
    produits = produits.map((p) => ({
      ...p,
      tailles_fr: (p.tailles || []).map(String),
      couleurs_fr: p.couleurs || [],
    }));
  }

  const div = document.createElement("div");
  div.className = "chat-msg bot";

  const itemsHtml = produits
    .map((p, i) => {
      const hasTailles = (p.tailles || []).length > 0;
      const hasCouleurs = (p.couleurs || []).length > 0;

      const taillesHtml = (p.tailles || [])
        .map((t, ti) => {
          const fr = (p.tailles_fr || [])[ti] || t;
          return `<span class="chat-opt" onclick="chatPickOpt(this)" data-group="taille-${i}-${p.id}" data-value-fr="${escapeAttr(fr)}">${escapeHtml(t)}</span>`;
        })
        .join("");

      const couleursHtml = (p.couleurs || [])
        .map((c, ci) => {
          const fr = (p.couleurs_fr || [])[ci] || c;
          return `<span class="chat-opt" onclick="chatPickOpt(this)" data-group="couleur-${i}-${p.id}" data-value-fr="${escapeAttr(fr)}">${escapeHtml(c)}</span>`;
        })
        .join("");

      return `
      <div class="chat-pick-item">
        <a href="article.php?id=${p.id}" class="chat-pick-top" title="Voir ${escapeHtml(p.name)}">
          <div class="chat-product-pick-img">
            ${
              p.url_image
                ? `<img src="${escapeHtml(p.url_image)}" alt="${escapeHtml(p.name)}" onerror="this.style.display='none'">`
                : "👟"
            }
          </div>
          <div class="chat-product-pick-info">
            <div class="chat-product-name">${escapeHtml(p.name)}</div>
            <div class="chat-product-price">${p.price} €</div>
          </div>
        </a>
        <div style="display:flex;gap:6px;padding:0 10px 6px">
          <button class="chat-pick-toggle-btn" style="flex:1" onclick="chatToggleSelector(this)">
            ${t("addToCart")}
          </button>
          <button class="chat-fav-btn" title="Ajouter aux favoris"
            onclick="toggleFavChat(${p.id}, this)">
            🤍
          </button>
        </div>
        <div class="chat-pick-selector" style="display:none">
          ${
            hasTailles
              ? `
            <div class="chat-option-title">${t("size")}</div>
            <div class="chat-option-group" data-type="taille">${taillesHtml}</div>
          `
              : ""
          }
          ${
            hasCouleurs
              ? `
            <div class="chat-option-title">${t("color")}</div>
            <div class="chat-option-group" data-type="couleur">${couleursHtml}</div>
          `
              : ""
          }
          <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>
          <button class="chat-cart-btn"
            onclick="confirmChatCartFromPicker(${p.id}, this)"
            ${hasTailles || hasCouleurs ? "disabled" : ""}>
            ${t("confirm")}
          </button>
        </div>
      </div>`;
    })
    .join("");

  div.innerHTML = `
    <div class="chat-product-card">
      <div class="chat-pick-title">${t("suggestions")}</div>
      <div class="chat-product-pick-list">${itemsHtml}</div>
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function selectProductFromPicker(btn) {
  const card = btn.closest(".chat-product-card");
  const produits = JSON.parse(card.dataset.products);
  const id = parseInt(btn.dataset.id);
  const produit = produits.find((p) => p.id === id);
  if (!produit) return;

  const msgDiv = card.closest(".chat-msg");
  const container = msgDiv.parentElement;
  msgDiv.remove();

  showCartSelector(produit, container);
  container.scrollTop = container.scrollHeight;
}

function chatToggleSelector(btn) {
  const selector = btn
    .closest(".chat-pick-item")
    .querySelector(".chat-pick-selector");
  const isOpen = selector.style.display !== "none";
  selector.style.display = isOpen ? "none" : "block";
  btn.style.opacity = isOpen ? "1" : "0.6";
}

function chatPickOpt(el) {
  el.closest(".chat-option-group")
    .querySelectorAll(".chat-opt")
    .forEach((o) => o.classList.remove("active"));
  el.classList.add("active");

  const selector = el.closest(".chat-pick-selector");
  const groups = [...selector.querySelectorAll(".chat-option-group")];
  const allDone = groups.every((g) => g.querySelector(".chat-opt.active"));
  selector.querySelector(".chat-cart-btn").disabled = !allDone;
}

async function confirmChatCartFromPicker(productId, btn) {
  const selector = btn.closest(".chat-pick-selector");
  const errEl = selector.querySelector(".chat-selector-error");
  const taille =
    selector.querySelector(
      '.chat-option-group[data-type="taille"] .chat-opt.active',
    )?.dataset.valueFr ||
    selector.querySelector(
      '.chat-option-group[data-type="taille"] .chat-opt.active',
    )?.textContent ||
    null;
  const couleur =
    selector.querySelector(
      '.chat-option-group[data-type="couleur"] .chat-opt.active',
    )?.dataset.valueFr ||
    selector.querySelector(
      '.chat-option-group[data-type="couleur"] .chat-opt.active',
    )?.textContent ||
    null;

  btn.disabled = true;
  btn.textContent = "…";
  if (errEl) errEl.textContent = "";

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent = t("added");
    btn.style.background = "#2f855a";
  } else {
    btn.disabled = false;
    btn.textContent = t("confirm");
    if (errEl) errEl.textContent = _cartErrorMsg(result?.error);
  }
}

/* ══════════════════════════════════════
   CARTE SÉLECTEUR TAILLE / COULEUR
══════════════════════════════════════ */
async function showCartConfirm(produit, taille, couleur, container) {
  if (!container) container = document.getElementById("messages");

  // Mémoriser l'état en attente de confirmation
  sessionStorage.setItem(
    "pendingCartConfirm",
    JSON.stringify({
      id: produit.id,
      name: produit.name,
      price: produit.price,
      taille: taille || null,
      couleur: couleur || null,
    }),
  );

  const div = document.createElement("div");
  div.className = "chat-msg bot";

  // Traduire le label "taille" et la valeur couleur via le cache UI
  const tailleStr = taille ? `${t("sizeLabel")} ${taille}` : "";
  let couleurStr = couleur || "";
  if (couleur && currentLangue !== "fr") {
    const cache = await traduireValeursDynamiques([couleur], currentLangue);
    couleurStr = cache[couleur] || couleur;
  }
  const details = [tailleStr, couleurStr].filter(Boolean).join(", ");

  div.innerHTML = `
    <div class="chat-product-card">
      <div class="chat-product-top">
        <div class="chat-product-img">
          ${
            produit.url_image
              ? `<img src="${escapeHtml(produit.url_image)}" alt="${escapeHtml(produit.name)}" onerror="this.style.display='none'">`
              : "👟"
          }
        </div>
        <div>
          <div class="chat-product-name">${escapeHtml(produit.name)}</div>
          <div class="chat-product-price">${produit.price.toFixed(2)} €</div>
          ${details ? `<div style="font-size:12px;color:#666;margin-top:2px">${escapeHtml(details)}</div>` : ""}
        </div>
      </div>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="chat-cart-btn" style="flex:1"
          onclick="confirmCartDirect(${produit.id}, '${escapeAttr(taille || "")}', '${escapeAttr(couleur || "")}', this)">
          ✓ ${t("confirm")}
        </button>
        <button class="chat-cart-btn" style="flex:1;background:#e53e3e"
          onclick="sessionStorage.removeItem('pendingCartConfirm'); this.closest('.chat-msg').remove()">
          ${t("cancel")}
        </button>
      </div>
      <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

async function confirmCartDirect(productId, taille, couleur, btn) {
  const card = btn.closest(".chat-product-card");
  const errEl = card.querySelector(".chat-selector-error");
  btn.disabled = true;
  btn.textContent = t("added");

  const result = await addToCart(productId, 1, taille || null, couleur || null);

  if (result?.success) {
    sessionStorage.removeItem("pendingCartConfirm");
    btn.textContent = t("added");
    btn.style.background = "#2f855a";
    card.querySelector("button[style*='e53e3e']")?.remove();
  } else {
    btn.disabled = false;
    btn.textContent = "✓ " + t("confirm");
    if (errEl) errEl.textContent = _cartErrorMsg(result?.error);
  }
}

// Wrapper pour le bouton "Choisir ce modèle" — feedback immédiat pendant le chargement
async function _choisirModele(produit, btn) {
  // Désactiver le bouton et afficher un état de chargement
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.innerHTML = `<span class="chat-shoe-steps"><span>👟</span><span>👟</span><span>👟</span></span>`;
  // Désactiver aussi l'autre bouton "Choisir ce modèle" dans la comparaison
  btn
    .closest(".chat-msg")
    ?.querySelectorAll(".chat-cart-btn")
    .forEach((b) => (b.disabled = true));

  const container = document.getElementById("messages");
  await showCartSelector(produit, container);

  // Rétablir au cas où showCartSelector n'aurait pas retiré la carte
  btn.disabled = false;
  btn.textContent = originalText;
}

async function showCartSelector(produit, container) {
  if (!container) container = document.getElementById("messages");
  if (currentLangue !== "fr") {
    // Si couleurs_fr est déjà présent (produit venant de showComparisonView),
    // les valeurs sont déjà traduites — pas besoin de retraduire
    if (!produit.couleurs_fr) {
      _appendCardsSkeleton(container, 1);
      const vals = [
        ...(produit.tailles || []).map(String),
        ...(produit.couleurs || []),
      ];
      const cache = await traduireValeursDynamiques(vals, currentLangue);
      _removeCardsSkeleton();
      produit = {
        ...produit,
        tailles_fr: (produit.tailles || []).map(String),
        couleurs_fr: produit.couleurs || [],
        tailles: (produit.tailles || []).map((v) => cache[String(v)] || v),
        couleurs: (produit.couleurs || []).map((v) => cache[v] || v),
      };
    }
  } else {
    produit = {
      ...produit,
      tailles_fr: (produit.tailles || []).map(String),
      couleurs_fr: produit.couleurs || [],
    };
  }

  const div = document.createElement("div");
  div.className = "chat-msg bot";

  const hasTailles = (produit.tailles || []).length > 0;
  const hasCouleurs = (produit.couleurs || []).length > 0;

  const taillesHtml = (produit.tailles || [])
    .map((t, i) => {
      const fr = (produit.tailles_fr || [])[i] || t;
      return `<button class="chat-option-btn" onclick="chatSelectOption(this)" data-value="${escapeAttr(t)}" data-value-fr="${escapeAttr(fr)}">${escapeHtml(t)}</button>`;
    })
    .join("");

  const couleursHtml = (produit.couleurs || [])
    .map((c, i) => {
      const fr = (produit.couleurs_fr || [])[i] || c;
      return `<button class="chat-option-btn" onclick="chatSelectOption(this)" data-value="${escapeAttr(c)}" data-value-fr="${escapeAttr(fr)}">${escapeHtml(c)}</button>`;
    })
    .join("");

  div.innerHTML = `
    <div class="chat-product-card">
      <a href="article.php?id=${produit.id}" class="chat-pick-top" title="Voir ${escapeHtml(produit.name)}">
        <div class="chat-product-img">
          ${
            produit.url_image
              ? `<img src="${escapeHtml(produit.url_image)}" alt="${escapeHtml(produit.name)}" onerror="this.style.display='none'">`
              : "👟"
          }
        </div>
        <div>
          <div class="chat-product-name">${escapeHtml(produit.name)}</div>
          <div class="chat-product-price">${produit.price} €</div>
        </div>
      </a>

      ${
        hasTailles
          ? `
        <div class="chat-option-title">${t("size")}</div>
        <div class="chat-option-group" data-type="taille">${taillesHtml}</div>
      `
          : ""
      }

      ${
        hasCouleurs
          ? `
        <div class="chat-option-title">${t("color")}</div>
        <div class="chat-option-group" data-type="couleur">${couleursHtml}</div>
      `
          : ""
      }

      <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>

      <div style="display:flex;gap:6px">
        <button class="chat-cart-btn" style="flex:1"
          onclick="confirmChatCart(${produit.id}, this)"
          ${hasTailles || hasCouleurs ? "disabled" : ""}>
          ${t("addToCart")}
        </button>
        <button class="chat-fav-btn" title="Ajouter aux favoris"
          onclick="toggleFavChat(${produit.id}, this)">
          🤍
        </button>
      </div>
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;

  if (!hasTailles && !hasCouleurs) {
    confirmChatCart(produit.id, div.querySelector(".chat-cart-btn"));
  }
}

function chatSelectOption(btn) {
  const group = btn.closest(".chat-option-group");
  group
    .querySelectorAll(".chat-option-btn")
    .forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");

  const card = btn.closest(".chat-product-card");
  const groups = card.querySelectorAll(".chat-option-group");
  const allDone = [...groups].every((g) =>
    g.querySelector(".chat-option-btn.active"),
  );
  const confirm = card.querySelector(".chat-cart-btn");
  if (confirm) confirm.disabled = !allDone;
}

async function confirmChatCart(productId, btn) {
  const card = btn.closest(".chat-product-card");
  const errEl = card.querySelector(".chat-selector-error");
  const taille =
    card.querySelector(
      '.chat-option-group[data-type="taille"] .chat-option-btn.active',
    )?.dataset.valueFr ||
    card.querySelector(
      '.chat-option-group[data-type="taille"] .chat-option-btn.active',
    )?.dataset.value ||
    null;
  const couleur =
    card.querySelector(
      '.chat-option-group[data-type="couleur"] .chat-option-btn.active',
    )?.dataset.valueFr ||
    card.querySelector(
      '.chat-option-group[data-type="couleur"] .chat-option-btn.active',
    )?.dataset.value ||
    null;

  btn.disabled = true;
  btn.textContent = t("added");
  if (errEl) errEl.textContent = "";

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent = t("added");
    btn.style.background = "#2f855a";
  } else {
    btn.disabled = false;
    btn.textContent = t("addToCart");
    if (errEl) errEl.textContent = _cartErrorMsg(result?.error);
  }
}

/* ══════════════════════════════════════
   PANIER
══════════════════════════════════════ */

async function addToCart(
  productId,
  quantity = 1,
  taille = null,
  couleur = null,
) {
  try {
    // On calcule le dossier de la page courante
    const currentDir = window.location.pathname.substring(
      0,
      window.location.pathname.lastIndexOf("/") + 1,
    );
    const res = await fetch(currentDir + "cart/add.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        product_id: productId,
        quantity,
        taille,
        couleur,
      }),
    });
    const data = await res.json();
    if (data.success) updateCartCount(data.count);
    return data;
  } catch (error) {
    console.error("Erreur ajout panier :", error);
    return { success: false, error: "Erreur réseau" };
  }
}

async function updateCartCount(count) {
  if (count !== undefined) {
    const el = document.getElementById("cart-count");
    if (el) el.textContent = count;
    return;
  }
  try {
    const res = await fetch("cart/count.php");
    const data = await res.json();
    const el = document.getElementById("cart-count");
    if (el) el.textContent = data.count;
  } catch (error) {
    console.error("Erreur compteur panier :", error);
  }
}

/* ══════════════════════════════════════
   UTILITAIRES
══════════════════════════════════════ */
function escapeHtml(text) {
  if (!text) return "";
  const d = document.createElement("div");
  d.textContent = String(text);
  return d.innerHTML;
}

function escapeAttr(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

document.addEventListener("DOMContentLoaded", async () => {
  updateCartCount();

  // Initialiser les timestamps dès le chargement (message de bienvenue inclus)
  _refreshTimestamps();

  // Restaurer la langue de la session précédente
  const savedLangue = sessionStorage.getItem("chatLangue");
  if (savedLangue && savedLangue !== "fr") {
    currentLangue = savedLangue;
    await loadUITranslations(savedLangue);
    _refreshTimestamps(); // re-formater dans la bonne langue
  }
  const container = document.getElementById("messages");

  // NOUVEAU : recharge depuis MySQL si session active
  if (dbSessionId) {
    const history = await loadSessionMessages(dbSessionId);
    if (history.length > 0) {
      conversationHistory = history;
      sessionStorage.setItem(
        "chatHistory",
        JSON.stringify(conversationHistory),
      );
    }
  }

  // Détecter le tutoiement depuis l'historique existant
  if (!sessionStorage.getItem("chatTutoiement")) {
    for (const msg of conversationHistory) {
      if (msg.role === "user" && msg.content) {
        _detecterEtStockerTutoiement(msg.content);
        if (sessionStorage.getItem("chatTutoiement")) break;
      }
    }
  }

  // Rejoue l'historique visuel
  if (container && conversationHistory.length > 0) {
    container.innerHTML = "";
    for (const msg of conversationHistory) {
      if (msg.content.startsWith("[Page produit")) continue;
      if (msg.role === "system") continue;
      if (msg.role === "user") {
        if (msg.silent) continue;
        appendUserMessage(msg.content);
      } else if (msg.role === "assistant" && msg.content) {
        appendBotMessageText(msg.content);
        if (msg.products && msg.products.length > 0) {
          if (msg.products.length === 1) {
            await showCartSelector(msg.products[0], container);
          } else if (msg.layout === "comparison" && msg.products.length >= 2) {
            await showComparisonView(
              msg.products[0],
              msg.products[1],
              container,
            );
          } else if (msg.products.length > 1) {
            await showProductPicker(msg.products, container);
          }
        }
      }
    }
    container.scrollTop = container.scrollHeight;
  }

  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".chat-chip");
    if (chip && chip.dataset.msg) {
      sendMessage(chip.dataset.msg);
    }
  });

  if (typeof voiceSupported === "function" && voiceSupported()) {
    const mic = document.getElementById("voice-btn");
    if (mic) mic.style.display = "inline-flex";
  }
});

/* ══════════════════════════════════════
   COMPARAISON CÔTE À CÔTE
══════════════════════════════════════ */
async function showComparisonView(p1, p2, container) {
  if (!container) container = document.getElementById("messages");
  if (currentLangue !== "fr") {
    _appendCardsSkeleton(container, 2, "comparison");
    const toutesValeurs = [
      ...(p1.tailles || []).map(String),
      ...(p2.tailles || []).map(String),
      ...(p1.couleurs || []),
      ...(p2.couleurs || []),
    ];
    const cache = await traduireValeursDynamiques(toutesValeurs, currentLangue);
    _removeCardsSkeleton();
    const traduire = (arr) => arr.map((v) => cache[v] || v);
    p1 = {
      ...p1,
      tailles_fr: (p1.tailles || []).map(String),
      couleurs_fr: p1.couleurs || [],
      tailles: traduire(p1.tailles || []),
      couleurs: traduire(p1.couleurs || []),
    };
    p2 = {
      ...p2,
      tailles_fr: (p2.tailles || []).map(String),
      couleurs_fr: p2.couleurs || [],
      tailles: traduire(p2.tailles || []),
      couleurs: traduire(p2.couleurs || []),
    };
  } else {
    p1 = {
      ...p1,
      tailles_fr: (p1.tailles || []).map(String),
      couleurs_fr: p1.couleurs || [],
    };
    p2 = {
      ...p2,
      tailles_fr: (p2.tailles || []).map(String),
      couleurs_fr: p2.couleurs || [],
    };
  }

  const div = document.createElement("div");
  div.className = "chat-msg bot";

  function colHtml(p, idx) {
    const tailles = (p.tailles || []).join(", ") || "—";
    const couleurs = (p.couleurs || []).join(", ") || "—";
    const resume = p.resume || ""; // ← résumé LLM
    return `
        <div class="chat-compare-col">
            <div class="chat-compare-img">
                ${
                  p.url_image
                    ? `<img src="${escapeHtml(p.url_image)}"
                            alt="${escapeHtml(p.name)}"
                            onerror="this.style.display='none'">`
                    : "👟"
                }
            </div>
            <div class="chat-compare-name">${escapeHtml(p.name)}</div>
            <div class="chat-compare-price">${p.price} €</div>
            ${resume ? `<div class="chat-compare-resume">${escapeHtml(resume)}</div>` : ""}
            <table class="chat-compare-table">
                <tr>
                    <td class="chat-compare-label">${t("brand")}</td>
                    <td>${escapeHtml(p.marque || "—")}</td>
                </tr>
                <tr>
                    <td class="chat-compare-label">${t("category")}</td>
                    <td>${escapeHtml(p.categorie || "—")}</td>
                </tr>
                <tr>
                    <td class="chat-compare-label">${t("sizes")}</td>
                    <td>${escapeHtml(tailles)}</td>
                </tr>
                <tr>
                    <td class="chat-compare-label">${t("colors")}</td>
                    <td>${escapeHtml(couleurs)}</td>
                </tr>
            </table>

            <button class="chat-cart-btn"
                style="margin-top:10px;width:100%"
                onclick="_choisirModele(${JSON.stringify(p).replace(/"/g, "&quot;")}, this)">
                ${t("chooseModel")}
            </button>
        </div>`;
  }

  div.innerHTML = `
        <div class="chat-compare-card">
            <div class="chat-compare-title">${t("comparison")}</div>
            <div class="chat-compare-grid">
                ${colHtml(p1, 0)}
                <div class="chat-compare-vs">VS</div>
                ${colHtml(p2, 1)}
            </div>
        </div>`;

  container.appendChild(div);
  requestAnimationFrame(() => {
    const cols = div.querySelectorAll(".chat-compare-col");
    if (cols.length < 2) return;

    const imgs = div.querySelectorAll("img");
    const loaded = Array.from(imgs).map((img) =>
      img.complete
        ? Promise.resolve()
        : new Promise((r) => {
            img.onload = r;
            img.onerror = r;
          }),
    );

    Promise.all(loaded).then(() => {
      cols.forEach((col) => (col.style.height = ""));
      const maxH = Math.max(...[...cols].map((col) => col.scrollHeight));
      cols.forEach((col) => (col.style.height = maxH + "px"));
    });
  });
  container.scrollTop = container.scrollHeight;
}

function initProductContext(produit) {
  const tutoiement = sessionStorage.getItem("chatTutoiement") || "tu";
  const pronom = tutoiement === "vous" ? "Vouvoyez" : "Tutoie";
  const pronLe = tutoiement === "vous" ? "Vouvoyez-le" : "Tutoie-le";
  const langue = sessionStorage.getItem("chatLangue") || "fr";
  // Tracker les produits visités
  let visited = JSON.parse(
    sessionStorage.getItem("visitedProducts_" + sessionId) || "[]",
  );
  const indexExistant = visited.findIndex((p) => p.id === produit.id);
  let nbVisites = 1;

  if (indexExistant === -1) {
    // Première visite de ce produit
    visited.push({
      id: produit.id,
      name: produit.name,
      price: produit.price,
      categorie: produit.categorie,
      marque: produit.marque,
      visits: 1,
    });
  } else {
    // Déjà visité → on incrémente
    visited[indexExistant].visits = (visited[indexExistant].visits || 1) + 1;
    nbVisites = visited[indexExistant].visits;
  }
  if (visited.length > 10) visited = visited.slice(-10);
  sessionStorage.setItem(
    "visitedProducts_" + sessionId,
    JSON.stringify(visited),
  );

  // Détecter si c'est la toute première interaction de la session
  const estPremiereVisite =
    conversationHistory.filter((m) => m.role === "assistant").length === 0;
  const sansBonjour = estPremiereVisite ? "" : " Ne commence pas par Bonjour.";

  // Injection du contexte produit dans l'historique (remplace l'ancien)
  conversationHistory = conversationHistory.filter(
    (msg) =>
      !(
        msg.role === "system" &&
        msg.content.startsWith("L'utilisateur consulte actuellement")
      ),
  );
  conversationHistory.push({
    role: "system",
    internal: true,
    content:
      `L'utilisateur consulte actuellement : "${produit.name}" ` +
      `(${produit.categorie}, ${produit.marque}, ${produit.price.toFixed(2)}€). ` +
      (produit.description ? `Description : ${produit.description}. ` : "") +
      (produit.couleurs?.length
        ? `Couleurs dispo : ${produit.couleurs.join(", ")}. `
        : "") +
      (produit.tailles?.length
        ? `Tailles dispo : ${produit.tailles.join(", ")}.`
        : ""),
  });
  sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory));

  // Prompt adapté selon le nombre de visites sur ce produit
  let question;
  const variantesPremiere = [
    `En une à deux phrases , accueille le client sur la fiche "${produit.name}" en citant son point fort principal. Utilise "tu" et parle comme un vendeur enthousiaste.`,
    `En une à deux phrases , présente le point fort des ${produit.name} (${produit.price.toFixed(2)}€) de façon percutante. ${pronom} le client.`,
    `En une à deux phrases , accroche le client avec ce qui rend les ${produit.name} uniques. ${pronLe}, sois naturel.`,
  ];
  const variantesRetour = [
    `En une à deux phrases , mets en avant le point fort des "${produit.name}" (${produit.price.toFixed(2)}€) et propose ton aide pour choisir la taille ou la couleur. ${pronom} le client.`,
    `En une à deux phrases, rappelle ce qui fait le charme des ${produit.name} et demande au client ce qui l'intéresse. ${pronLe}.`,
    `En une à deux phrases , souligne la qualité des ${produit.name} (${produit.price.toFixed(2)}€) et propose de répondre à ses questions. ${pronom} le client.`,
  ];
  if (nbVisites >= 3) {
    question = `En une à deux phrases percutantes (max 25 mots), tu remarques que le client revient encore sur "${produit.name}" (${produit.price.toFixed(2)}€). Crée un sentiment d'urgence ou mets en avant une raison décisive d'acheter maintenant. ${pronom} le client.${sansBonjour}`;
  } else if (nbVisites === 2) {
    question = `En une à deux phrases (max 25 mots), tu remarques que le client revient sur "${produit.name}" (${produit.price.toFixed(2)}€). Encourage-le chaleureusement à passer à l'achat en soulignant ce qui le séduisait. ${pronLe}.${sansBonjour}`;
  } else if (estPremiereVisite) {
    question =
      variantesPremiere[Math.floor(Math.random() * variantesPremiere.length)];
  } else {
    question =
      variantesRetour[Math.floor(Math.random() * variantesRetour.length)] +
      sansBonjour;
  }

  _genererMessageAccueil(question, produit.id);
}

async function initFavorisContext(favorisItems) {
  const tutoiement = sessionStorage.getItem("chatTutoiement") || "tu";
  const pronom = tutoiement === "vous" ? "Vouvoyez" : "Tutoie";
  const pronLe = tutoiement === "vous" ? "Vouvoyez-le" : "Tutoie-le";
  const langue = sessionStorage.getItem("chatLangue") || "fr";
  const estPremiereVisite =
    conversationHistory.filter((m) => m.role === "assistant").length === 0;
  const sansBonjour = estPremiereVisite ? "" : " Ne commence pas par Bonjour.";

  let contexte, question;

  if (favorisItems && favorisItems.length > 0) {
    const resumeFav = favorisItems.map((f) => f.nom).join(", ");
    const nbFav = favorisItems.length;
    contexte = `L'utilisateur consulte ses favoris (${nbFav} article(s)) : ${resumeFav}.`;

    const variantes = [
      `Le client a ${nbFav} favori(s) : ${resumeFav}. En 2 phrases : félicite-le pour ses choix, puis propose de l'aider à décider lequel prendre. Ne cite AUCUN autre produit. ${pronLe}.`,
      `Le client regarde ses favoris (${resumeFav}). En 2 phrases : commente positivement ces choix, puis demande s'il veut qu'on l'aide à choisir ou à trouver autre chose. Ne cite AUCUN autre produit. ${pronLe}.`,
      `Le client a sauvegardé ${resumeFav} dans ses favoris. En 2 phrases : valorise ces sélections, puis propose ton aide pour finaliser un achat. Ne cite AUCUN autre produit. ${pronLe}.`,
    ];
    question =
      variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
  } else {
    contexte = `L'utilisateur est sur sa page favoris mais elle est vide.`;
    const variantes = [
      `En une phrase, dis au client que sa liste de favoris est vide et propose de l'aider à trouver des chaussures qui lui plairont. ${pronLe}.`,
      `En une phrase, invite le client à explorer le catalogue pour ajouter ses coups de cœur en favoris. ${pronLe}.`,
    ];
    question =
      variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
  }

  conversationHistory = conversationHistory.filter(
    (msg) =>
      !(msg.role === "system" && msg.content.startsWith("L'utilisateur")),
  );
  conversationHistory.push({
    role: "system",
    internal: true,
    content: contexte,
  });
  sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory));

  _genererMessageAccueil(question, null, []);
}

async function initPanierContext(panierItems) {
  const tutoiement = sessionStorage.getItem("chatTutoiement") || "tu";
  const pronom = tutoiement === "vous" ? "Vouvoyez" : "Tutoie";
  const pronLe = tutoiement === "vous" ? "Vouvoyez-le" : "Tutoie-le";
  const langue = sessionStorage.getItem("chatLangue") || "fr";
  const visited = JSON.parse(
    sessionStorage.getItem("visitedProducts_" + sessionId) || "[]",
  );
  const derniersProduitsChat = [];
  for (let i = conversationHistory.length - 1; i >= 0; i--) {
    const msg = conversationHistory[i];
    if (msg.role === "assistant" && msg.products && msg.products.length > 0) {
      derniersProduitsChat.push(...msg.products);
      break;
    }
  }
  const estPremiereVisite =
    conversationHistory.filter((m) => m.role === "assistant").length === 0;
  const sansBonjour = estPremiereVisite ? "" : " Ne commence pas par Bonjour.";

  let contexte, question;

  if (panierItems && panierItems.length > 0) {
    const resume = panierItems
      .map((it) => `${it.nom} ×${it.quantity} à ${it.prix}€`)
      .join(", ");
    contexte = `L'utilisateur est sur sa page panier. Contenu : ${resume}.`;
    const resumeNoms = panierItems.map((it) => it.nom).join(", ");
    const interdiction =
      "Ne cite AUCUN autre produit que tu n'as pas dans le catalogue fourni.";
    const variantes = [
      `Le client a ${resumeNoms} dans son panier. En 2 phrases : félicite-le pour ce choix, puis demande-lui s'il cherche autre chose ou si tu peux l'aider. ${interdiction} ${pronLe}.`,
      `Le client a ${resumeNoms} dans son panier. En 2 phrases : rassure-le sur son excellent choix, puis propose ton aide s'il a besoin d'une autre paire. ${interdiction} ${pronLe}.`,
      `Le client a ${resumeNoms} dans son panier. En 2 phrases : dis-lui que c'est un super choix, puis demande s'il cherche quelque chose pour compléter. ${interdiction} ${pronLe}.`,
      `Le client a ${resumeNoms} dans son panier. En 2 phrases : valorise son choix, puis demande s'il a trouvé tout ce qu'il cherchait ou s'il veut explorer d'autres modèles. ${interdiction} ${pronLe}.`,
      `Le client a ${resumeNoms} dans son panier. En 2 phrases : félicite-le pour ce choix et rappelle une qualité clé, puis demande si tu peux l'aider pour autre chose. ${interdiction} ${pronLe}.`,
    ];
    question =
      variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
  } else if (derniersProduitsChat.length > 0) {
    const resumeChat = derniersProduitsChat
      .map((p) => `${p.name} (${p.price.toFixed(2)}€)`)
      .join(", ");
    contexte = `L'utilisateur a un panier vide. Il vient de consulter dans le chat : ${resumeChat}.`;
    const variantes = [
      `En 1-2 phrases, rappelle au client qu'il regardait ${resumeChat} et propose de l'aider à choisir.`,
      `En 1-2 phrases, dis au client que ${resumeChat} l'attend et qu'il peut les ajouter facilement.`,
      `En 1-2 phrases, encourage le client à craquer pour ${resumeChat} qu'il vient de consulter.`,
    ];
    question =
      variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
  } else if (visited.length > 0) {
    const resumeVisites = visited
      .slice(-3)
      .map((p) => `${p.name} (${p.price.toFixed(2)}€)`)
      .join(", ");
    contexte = `L'utilisateur a un panier vide. Il a récemment consulté : ${resumeVisites}.`;
    const variantes = [
      `En une phrase , dis au client que tu as vu qu'il regardait ${resumeVisites} et propose de l'aider.`,
      `En une phrase , rappelle au client ses consultations récentes (${resumeVisites}) et invite-le à se décider.`,
      `En une phrase , interpelle le client sur ${resumeVisites} qu'il a consulté et propose ton aide.`,
    ];
    question =
      variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
  } else {
    // Panier vide, aucun historique → vérifier les favoris
    contexte = `L'utilisateur arrive sur sa page panier vide.`;
    let favorisNoms = "";
    try {
      const currentDir = window.location.pathname.substring(
        0,
        window.location.pathname.lastIndexOf("/") + 1,
      );
      const resFav = await fetch(currentDir + "favorites/list.php");
      const dataFav = await resFav.json();
      if (dataFav.success && dataFav.favoris.length > 0) {
        favorisNoms = dataFav.favoris.map((f) => f.nom).join(", ");
        contexte = `L'utilisateur a un panier vide. Ses favoris : ${favorisNoms}.`;
      }
    } catch (e) {}

    if (favorisNoms) {
      const variantes = [
        `Le client a ${favorisNoms} dans ses favoris. En une phrase, rappelle-lui et propose de l'aider à choisir. ${pronLe}.`,
        `Le client a des favoris (${favorisNoms}). En une phrase, invite-le à les ajouter au panier ou à explorer d'autres modèles. ${pronLe}.`,
      ];
      question =
        variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
    } else {
      const variantes = [
        `En une phrase, invite le client à découvrir le catalogue pour trouver sa prochaine paire. ${pronLe}.`,
        `En une phrase , propose au client de l'aider à trouver la chaussure parfaite dans le catalogue. ${pronLe}.`,
        `En une phrase, encourage le client à explorer le catalogue et à se faire plaisir. ${pronLe}.`,
      ];
      question =
        variantes[Math.floor(Math.random() * variantes.length)] + sansBonjour;
    }
  }

  conversationHistory = conversationHistory.filter(
    (msg) =>
      !(msg.role === "system" && msg.content.startsWith("L'utilisateur")),
  );
  conversationHistory.push({
    role: "system",
    internal: true,
    content: contexte,
  });
  sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory));

  _genererMessageAccueil(
    question,
    null,
    derniersProduitsChat,
    panierItems && panierItems.length > 0,
  );
}

async function _genererMessageAccueil(
  question,
  productId,
  produitsAafficher = [],
  produitsDejaAuPanier = false,
) {
  const container = document.getElementById("messages");
  const langueEffective =
    sessionStorage.getItem("chatLangue") || currentLangue || "fr";
  if (!container) return;
  if (langueEffective !== currentLangue) {
    currentLangue = langueEffective;
    if (!_uiTranslationsCache[langueEffective]) {
      await loadUITranslations(langueEffective);
    }
  }

  const msgDiv = document.createElement("div");
  msgDiv.className = "chat-msg bot";
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble";
  bubble.innerHTML = `<span class="chat-shoe-steps" style="opacity:0.7"><span>👟</span><span>👟</span><span>👟</span></span>`;
  const time = document.createElement("div");
  time.className = "chat-time";
  time.dataset.ts = Date.now();
  time.textContent = _formatTime(Date.now());
  msgDiv.appendChild(bubble);
  msgDiv.appendChild(time);
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;

  try {
    const body = {
      question: question,
      history: _histoirePropre(),
      session_id: sessionId,
      langue_session: langueEffective,
    };
    if (productId) body.product_id = productId;

    const response = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let text = "",
      started = false,
      products = [];

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of decoder.decode(value).split("\n")) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (raw === "[DONE]") break;
        try {
          const data = JSON.parse(raw);
          if (data.type === "products_final") {
            products = data.products || [];
          } else if (data.chunk !== undefined) {
            if (!started) {
              bubble.innerHTML = "";
              started = true;
            }
            text += data.chunk;
            bubble.textContent = text;
          }
        } catch (e) {}
      }
    }

    // ← NOUVEAU : utiliser les produits passés en paramètre si le backend n'en retourne pas
    const produitsFinaux = products.length > 0 ? products : produitsAafficher;

    conversationHistory.push({
      role: "user",
      content: question,
      silent: true,
      internal: true,
    });
    conversationHistory.push({
      role: "assistant",
      content: text,
      products: produitsFinaux,
      internal: true,
    });

    await saveMessageToDB("user", question, [], null, true, true);
    await saveMessageToDB("assistant", text, produitsFinaux, null, false, true);

    if (conversationHistory.length > 20)
      conversationHistory = conversationHistory.slice(-20);
    sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory));

    // Afficher les cartes seulement si les produits ne sont pas déjà au panier
    if (!produitsDejaAuPanier) {
      if (produitsFinaux.length === 1) {
        await showCartSelector(produitsFinaux[0], container);
      } else if (produitsFinaux.length > 1) {
        await showProductPicker(produitsFinaux, container);
      }
    }

    // Si le message bot pose une question ouverte (panier avec items), stocker le contexte
    // pour que "oui" / "non" seuls soient bien traités
    if (produitsDejaAuPanier && text) {
      const questionOuverte = text.match(/\?/) !== null;
      if (questionOuverte) {
        sessionStorage.setItem("pendingFollowUp", "panier");
      }
    }
  } catch (e) {
    bubble.textContent =
      "Bonjour ! Je suis votre conseiller PairIA, posez-moi vos questions 👟";
  }
}

// ── Panneau historique ──
async function openHistoryPanel() {
  const panel = document.getElementById("history-panel");
  if (!panel) return;
  panel.classList.add("open");

  const list = document.getElementById("history-list");
  list.innerHTML = '<div class="history-loading">Chargement…</div>';

  const sessions = await loadSessionList();
  if (sessions.length === 0) {
    list.innerHTML =
      '<div class="history-empty">Aucune conversation sauvegardée.</div>';
    return;
  }

  // Grouper par date comme
  const groups = {};
  const now = new Date();
  sessions.forEach((s) => {
    const d = new Date(s.updated_at);
    const diff = Math.floor((now - d) / 86400000);
    let label;
    if (diff === 0) label = "Aujourd'hui";
    else if (diff === 1) label = "Hier";
    else if (diff <= 7) label = "Cette semaine";
    else if (diff <= 30) label = "Ce mois-ci";
    else label = "Plus ancien";
    if (!groups[label]) groups[label] = [];
    groups[label].push(s);
  });

  list.innerHTML = Object.entries(groups)
    .map(
      ([label, items]) => `
        <div class="history-group">
            <div class="history-group-label">${label}</div>
            ${items
              .map(
                (s) => `
                <div class="history-item ${s.id === dbSessionId ? "active" : ""}"
                     onclick="loadSession(${s.id})">
                    <span class="history-item-title">${escapeHtml(s.titre)}</span>
                    <button class="history-item-del" onclick="deleteSession(event, ${s.id})" title="Supprimer">
                        <i class="ti ti-trash" aria-hidden="true"></i>
                    </button>
                </div>
            `,
              )
              .join("")}
        </div>
    `,
    )
    .join("");
}

function closeHistoryPanel() {
  document.getElementById("history-panel")?.classList.remove("open");
}

async function loadSession(sessionDbId) {
  const history = await loadSessionMessages(sessionDbId);
  dbSessionId = sessionDbId;
  sessionStorage.setItem("dbSessionId", dbSessionId);
  conversationHistory = history;
  sessionStorage.setItem("chatHistory", JSON.stringify(conversationHistory));

  const container = document.getElementById("messages");
  container.innerHTML = "";
  for (const msg of conversationHistory) {
    if (msg.role === "system" || (msg.role === "user" && msg.silent)) continue;
    if (msg.role === "user") appendUserMessage(msg.content);
    else if (msg.role === "assistant" && msg.content) {
      appendBotMessageText(msg.content);
      if (msg.products?.length > 0) {
        if (msg.products.length === 1)
          await showCartSelector(msg.products[0], container);
        else if (msg.layout === "comparison" && msg.products.length >= 2)
          await showComparisonView(msg.products[0], msg.products[1], container);
        else await showProductPicker(msg.products, container);
      }
    }
  }
  container.scrollTop = container.scrollHeight;
  closeHistoryPanel();
}

async function deleteSession(e, sessionDbId) {
  e.stopPropagation();
  await fetch("chat/history_clear.php", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionDbId }),
  });
  if (sessionDbId === dbSessionId) {
    dbSessionId = null;
    sessionStorage.removeItem("dbSessionId");
    conversationHistory = [];
    sessionStorage.removeItem("chatHistory");
    document.getElementById("messages").innerHTML = "";
  }
  openHistoryPanel(); // Rafraîchit la liste
}

function newConversation() {
  dbSessionId = null;
  currentLangue = "fr";
  sessionStorage.removeItem("chatLangue");
  sessionStorage.removeItem("dbSessionId");
  conversationHistory = [];
  sessionId = ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
  sessionStorage.removeItem("chatHistory");
  sessionStorage.setItem("chatSessionId", sessionId);
  document.getElementById("messages").innerHTML = "";
  closeHistoryPanel();
}

// Traduit des valeurs dynamiques (couleurs, catégories) via le même endpoint /translate-ui
// Réutilise le cache existant _uiTranslationsCache[langue]
async function traduireValeursDynamiques(valeurs, langue) {
  if (!langue || langue === "fr" || !valeurs.length) return {};

  const cache = _uiTranslationsCache[langue] || {};
  const aTraduire = [...new Set(valeurs)].filter((v) => v && !(v in cache));

  if (aTraduire.length > 0) {
    const texts = Object.fromEntries(aTraduire.map((v) => [v, v]));
    try {
      const res = await fetch(`${API_URL}/translate-ui`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texts, langue }),
      });
      const data = await res.json();
      // Fusionne dans le cache existant de la langue
      _uiTranslationsCache[langue] = { ...cache, ...data.translations };
    } catch (e) {
      // Fallback : valeur originale
      aTraduire.forEach((v) => {
        if (!_uiTranslationsCache[langue]) _uiTranslationsCache[langue] = {};
        _uiTranslationsCache[langue][v] = v;
      });
    }
  }

  return _uiTranslationsCache[langue] || {};
}
