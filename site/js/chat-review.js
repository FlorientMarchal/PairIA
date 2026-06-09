/* ══════════════════════════════════════════════════════════════════
   js/chat-review.js
══════════════════════════════════════════════════════════════════ */

// ── Mots-clés qui déclenchent le flux d'avis ────────────────────
const _REVIEW_TRIGGERS = [
  // Avis / note
  "laisser un avis",
  "donner un avis",
  "mettre un avis",
  "déposer un avis",
  "écrire un avis",
  "publier un avis",
  "noter",
  "je veux noter",
  "je voudrais noter",
  "donner mon avis",
  "laisser mon avis",
  "mon avis",
  "ma note",
  // Expérience / achat
  "partager mon expérience",
  "partager mon achat",
  "parler de mon achat",
  "parler de mon expérience",
  "raconter mon expérience",
  // Commentaire
  "faire un commentaire",
  "laisser un commentaire",
  "écrire un commentaire",
  "poster un commentaire",
  "ajouter un commentaire",
  // Point de vue / opinion
  "donner mon point de vue",
  "donner mon avis",
  "donner mon opinion",
  "partager mon opinion",
  "mon point de vue",
  "mon opinion",
  // Aider les autres
  "aider les autres",
  "aider d'autres acheteurs",
  "partager pour les autres",
  "conseiller les autres",
  "recommander",
  "je recommande",
  // Satisfaction / retour
  "donner mon retour",
  "faire un retour",
  "partager mon retour",
  "mon retour",
  "donner un feedback",
  "laisser un feedback",
  // Anglais
  "leave a review",
  "write a review",
  "rate this",
  "give a review",
  "share my experience",
  "post a review",
  "give feedback",
  "leave feedback",
  "my review",
];

// ── État du flux avis ────────────────────────────────────────────
window._pendingReview = null;

// ── Détection déclencheur ────────────────────────────────────────
function _isReviewIntent(text) {
  const t = text.toLowerCase().trim();
  return _REVIEW_TRIGGERS.some((kw) => t.includes(kw));
}

// ── Parse la note depuis un message utilisateur ──────────────────
function _parseNote(text) {
  const t = text.trim().toLowerCase();
  const numMap = {
    un: 1,
    une: 1,
    deux: 2,
    trois: 3,
    quatre: 4,
    cinq: 5,
    one: 1,
    two: 2,
    three: 3,
    four: 4,
    five: 5,
  };
  const m = t.match(/\b([1-5])\b/) || t.match(/\b([1-5])\s*[\/⁄]\s*5\b/);
  if (m) return parseInt(m[1]);
  for (const [word, val] of Object.entries(numMap)) {
    if (t.includes(word)) return val;
  }
  return null;
}

// ── Affiche la carte de saisie dans le chat ──────────────────────
function _showReviewCard(productId, note, suggestion) {
  const container = document.getElementById("messages");
  if (!container) return;

  document.getElementById("chat-review-card")?.remove();

  const stars = "★".repeat(note) + "☆".repeat(5 - note);

  const div = document.createElement("div");
  div.className = "chat-msg bot";
  div.id = "chat-review-card";
  div.innerHTML = `
    <div class="chat-product-card chat-review-form">
      <div class="chat-review-header">
        <span class="ia-badge">✍️ Avis</span>
        <span class="chat-review-stars">${stars}</span>
      </div>

      ${
        suggestion
          ? `
      <div class="chat-review-suggestion">
        <div class="ia-block-header" style="margin-bottom:0.4rem">
          <span class="ia-badge">✨ IA</span>
          <span class="ia-block-title">Suggestion</span>
        </div>
        <div class="ia-suggestion" id="chat-review-suggestion-text"
             style="margin-bottom:0.5rem;cursor:pointer"
             title="Cliquer pour utiliser"
             onclick="_useChatReviewSuggestion()">${escapeHtml(suggestion)}</div>
        <button class="btn-accept" onclick="_useChatReviewSuggestion()" style="margin-bottom:0.75rem">
          ↓ Utiliser cette phrase
        </button>
      </div>`
          : ""
      }

      <div style="position:relative">
        <textarea id="chat-review-text"
          class="review-textarea"
          placeholder="Écrivez votre avis ici... (max 300 caractères)"
          maxlength="300"
          oninput="_updateChatReviewCounter(this)"
          style="min-height:80px;margin-bottom:0.3rem"></textarea>
        <span id="chat-review-counter" class="review-char-counter">0 / 300</span>
      </div>

      <div id="chat-review-error" class="modal-error-msg" style="display:none;margin-bottom:0.5rem"></div>

      <div style="display:flex;gap:0.6rem;margin-top:0.4rem">
        <button class="chat-cart-btn" style="flex:1;background:var(--accent)"
          onclick="_submitChatReview(${productId}, ${note}, this)">
          Publier mon avis
        </button>
        <button class="chat-cart-btn" style="flex:0 0 auto;background:var(--light);color:var(--dark)"
          onclick="_cancelChatReview()">
          Annuler
        </button>
      </div>
    </div>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  setTimeout(() => document.getElementById("chat-review-text")?.focus(), 100);
}

// ── Compteur de caractères ───────────────────────────────────────
window._updateChatReviewCounter = function (ta) {
  const counter = document.getElementById("chat-review-counter");
  if (!counter) return;
  const len = ta.value.length;
  const left = 300 - len;
  counter.textContent = `${len} / 300`;
  counter.className = "review-char-counter";
  if (left <= 0) counter.classList.add("review-char-counter--over");
  else if (left <= 30) counter.classList.add("review-char-counter--warn");
  else if (left <= 60) counter.classList.add("review-char-counter--near");
};

// ── Utilise la suggestion IA ─────────────────────────────────────
window._useChatReviewSuggestion = function () {
  const suggestion =
    document.getElementById("chat-review-suggestion-text")?.textContent ?? "";
  const ta = document.getElementById("chat-review-text");
  if (ta && suggestion) {
    ta.value = suggestion.slice(0, 300);
    _updateChatReviewCounter(ta);
    ta.focus();
    ta.style.borderColor = "#4caf50";
    setTimeout(() => {
      ta.style.borderColor = "";
    }, 600);
  }
};

// ── Annulation ───────────────────────────────────────────────────
window._cancelChatReview = function () {
  window._pendingReview = null;
  document.getElementById("chat-review-card")?.remove();
  appendBotMessageText(
    "D'accord, pas de problème ! Je suis là si tu as d'autres questions. 😊",
  );
};

// ── Soumission ───────────────────────────────────────────────────
window._submitChatReview = async function (productId, note, btn) {
  const ta = document.getElementById("chat-review-text");
  const errEl = document.getElementById("chat-review-error");
  const contenu = ta?.value.trim() ?? "";

  if (!contenu) {
    if (errEl) {
      errEl.textContent = "Veuillez écrire un avis avant de publier.";
      errEl.style.display = "block";
    }
    return;
  }

  btn.disabled = true;
  btn.textContent = "Publication...";
  if (errEl) errEl.style.display = "none";

  try {
    const res = await fetch("commentaires/add.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: productId, note, contenu }),
    });
    const data = await res.json();

    if (data.success) {
      window._pendingReview = null;
      document.getElementById("chat-review-card")?.remove();

      const stars = "★".repeat(note) + "☆".repeat(5 - note);
      appendBotMessageText(
        `Merci pour ton avis ${stars} ! Il a bien été publié. 🎉`,
      );

      // ── Rafraîchit la section commentaires sans recharger la page ──
      if (typeof loadCommentsPremium === "function") {
        loadCommentsPremium();
      }
    } else if (data.error === "not_purchased") {
      document.getElementById("chat-review-card")?.remove();
      window._pendingReview = null;
      appendBotMessageText(
        "🛍️ Tu dois avoir acheté cette chaussure pour laisser un avis.",
      );
    } else if (data.error === "contenu_inapproprie") {
      if (errEl) {
        errEl.textContent =
          data.message ?? "Votre avis contient des termes non autorisés.";
        errEl.style.display = "block";
      }
      btn.disabled = false;
      btn.textContent = "Publier mon avis";
    } else if (data.error === "too_long") {
      if (errEl) {
        errEl.textContent = "L'avis ne peut pas dépasser 300 caractères.";
        errEl.style.display = "block";
      }
      btn.disabled = false;
      btn.textContent = "Publier mon avis";
    } else {
      if (errEl) {
        errEl.textContent = data.message ?? "Erreur lors de la publication.";
        errEl.style.display = "block";
      }
      btn.disabled = false;
      btn.textContent = "Publier mon avis";
    }
  } catch (err) {
    console.error("[ChatReview]", err);
    if (errEl) {
      errEl.textContent = "Erreur réseau. Réessaie.";
      errEl.style.display = "block";
    }
    btn.disabled = false;
    btn.textContent = "Publier mon avis";
  }
};

// ── Récupère l'ID produit courant ────────────────────────────────
function _getCurrentProductId() {
  if (typeof PRODUCT_ID !== "undefined" && PRODUCT_ID) return PRODUCT_ID;
  if (typeof conversationHistory !== "undefined") {
    for (let i = conversationHistory.length - 1; i >= 0; i--) {
      const msg = conversationHistory[i];
      if (msg.products?.length > 0) return msg.products[0].id;
    }
  }
  return null;
}

// ── Génère une suggestion via suggest.php ────────────────────────
async function _generateChatReviewSuggestion(note, productId) {
  try {
    const produit =
      document.querySelector(".product-name")?.textContent?.trim() ?? "";
    const res = await fetch("commentaires/suggest.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        texte:
          note >= 4
            ? "très bien qualité confort"
            : note === 3
              ? "correct moyen"
              : "déçu problème",
        produit,
        note,
        mode: "rewrite",
      }),
    });
    const data = await res.json();
    return data.success && data.rewrite ? data.rewrite : null;
  } catch {
    return null;
  }
}

// ── Patch sendMessage ────────────────────────────────────────────
const _originalSendMessage = window.sendMessage;
window.sendMessage = async function (text) {
  // Étape 2 : on attend la note
  if (window._pendingReview?.step === "note") {
    const note = _parseNote(text);
    if (!note) {
      appendUserMessage(text);
      appendBotMessageText(
        "Je n'ai pas compris la note 😅 Donne-moi un chiffre entre 1 et 5 !",
      );
      return;
    }
    appendUserMessage(text);
    window._pendingReview.note = note;
    window._pendingReview.step = "text";

    const typingEl = appendTyping();
    const suggestion = await _generateChatReviewSuggestion(
      note,
      window._pendingReview.productId,
    );
    typingEl.remove();

    _showReviewCard(window._pendingReview.productId, note, suggestion);
    return;
  }

  // Étape 1 : détection intention avis
  if (_isReviewIntent(text)) {
    const productId = _getCurrentProductId();
    if (!productId) return _originalSendMessage(text);
    appendUserMessage(text);
    window._pendingReview = {
      step: "note",
      productId,
      note: null,
      suggestion: null,
    };
    appendBotMessageText(
      "Bien sûr ! Quelle note tu donnes à cette chaussure ? (1 à 5 étoiles ⭐)",
    );
    return;
  }

  // Comportement normal
  return _originalSendMessage(text);
};
