const MAX_CHARS = 300;

const PLACEHOLDERS = {
  1: "Décrivez votre déception (confort, taille, qualité, livraison...)",
  2: "Qu'est-ce qui pourrait être amélioré sur ces chaussures ?",
  3: "C'était bien mais pas parfait ? Dites-nous ce qui vous a plu et moins plu...",
  4: "Vous avez apprécié ces chaussures ! Qu'est-ce qui vous a convaincu ?",
  5: "Vous avez adoré ! Partagez ce qui vous a séduit : confort, style, qualité...",
};
const PLACEHOLDER_DEFAULT = "Décrivez votre expérience avec ces chaussures...";

/* ══════════════════════════════════════════════════════════════════
   COMPTEUR DE CARACTÈRES
══════════════════════════════════════════════════════════════════ */

function _updateCounter(textarea) {
  const counter = document.getElementById("review-char-counter");
  if (!counter) return;

  const len = textarea.value.length;
  const left = MAX_CHARS - len;

  counter.textContent = `${len} / ${MAX_CHARS}`;

  // Couleurs progressives
  counter.className = "review-char-counter";
  if (left <= 0) counter.classList.add("review-char-counter--over");
  else if (left <= 30) counter.classList.add("review-char-counter--warn");
  else if (left <= 60) counter.classList.add("review-char-counter--near");

  // Bloque la saisie au-delà de 300
  if (len > MAX_CHARS) {
    textarea.value = textarea.value.slice(0, MAX_CHARS);
    counter.textContent = `${MAX_CHARS} / ${MAX_CHARS}`;
  }
}

/* ══════════════════════════════════════════════════════════════════
   GHOST TEXT
══════════════════════════════════════════════════════════════════ */

let _ghostTimer = null;
let _ghostSuggestion = "";
let _isLoadingGhost = false;

function _clearGhost() {
  _ghostSuggestion = "";
  const g = document.getElementById("review-ghost");
  if (g) g.innerHTML = "";
  const hint = document.querySelector(".review-hint-key");
  if (hint) hint.style.opacity = "0";
}

function _escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}

function _renderGhost(userText, continuation) {
  const g = document.getElementById("review-ghost");
  if (!g || !continuation) {
    _clearGhost();
    return;
  }
  g.innerHTML =
    '<span class="ghost-typed">' +
    _escapeHtml(userText) +
    " </span>" +
    '<span class="ghost-hint">' +
    _escapeHtml(continuation) +
    "</span>";
  const hint = document.querySelector(".review-hint-key");
  if (hint) hint.style.opacity = "1";
  _syncGhostStyle();
}

function _syncGhostStyle() {
  const ta = document.getElementById("review-text");
  const g = document.getElementById("review-ghost");
  if (!ta || !g) return;
  const cs = window.getComputedStyle(ta);
  g.style.fontFamily = cs.fontFamily;
  g.style.fontSize = cs.fontSize;
  g.style.lineHeight = cs.lineHeight;
  g.style.padding = cs.padding;
  g.style.width = ta.offsetWidth + "px";
}

async function _fetchGhostSuggestion(texte) {
  const produit =
    document.querySelector(".product-name")?.textContent?.trim() ?? "";
  const note = window.currentRating ?? 0;
  try {
    const res = await fetch("commentaires/suggest.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte, produit, note, mode: "ghost" }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.success || !data.suggestions?.length) return null;
    return data.suggestions[0];
  } catch {
    return null;
  }
}

function _onGhostInput(e) {
  const ta = e.target;
  const text = ta.value;

  _updateCounter(ta);
  clearTimeout(_ghostTimer);
  _clearGhost();

  if (text.trim().length < 3 || text.length >= MAX_CHARS) return;

  _ghostTimer = setTimeout(async () => {
    if (_isLoadingGhost) return;
    _isLoadingGhost = true;
    const cont = await _fetchGhostSuggestion(text.trim());
    _isLoadingGhost = false;
    const current = document.getElementById("review-text");
    if (!current || current.value.trim() !== text.trim()) return;
    if (cont) {
      _ghostSuggestion = text.trimEnd() + " " + cont.trimStart();
      _renderGhost(text, cont);
    }
  }, 550);
}

function _onGhostKeydown(e) {
  if (!_ghostSuggestion) return;
  if (e.key === "Tab" || e.key === "ArrowRight") {
    const ta = document.getElementById("review-text");
    if (!ta) return;
    if (e.key === "ArrowRight" && ta.selectionStart !== ta.value.length) return;
    e.preventDefault();
    // Respecte la limite de 300 lors de l'acceptation
    const full = _ghostSuggestion.slice(0, MAX_CHARS);
    ta.value = full;
    ta.setSelectionRange(ta.value.length, ta.value.length);
    _updateCounter(ta);
    _clearGhost();
    _ghostSuggestion = "";
  } else if (e.key === "Escape") {
    _clearGhost();
    _ghostSuggestion = "";
  }
}

function _initGhost() {
  const ta = document.getElementById("review-text");
  if (!ta) return;
  ta.removeEventListener("input", _onGhostInput);
  ta.removeEventListener("keydown", _onGhostKeydown);
  ta.addEventListener("input", _onGhostInput);
  ta.addEventListener("keydown", _onGhostKeydown);
  new ResizeObserver(_syncGhostStyle).observe(ta);
  _clearGhost();
  _updateCounter(ta);
}

/* ══════════════════════════════════════════════════════════════════
   GÉNÉRATION IA depuis mots-clés
══════════════════════════════════════════════════════════════════ */

async function generateIA() {
  const keywords =
    document.getElementById("review-keywords")?.value.trim() ?? "";
  const note = window.currentRating ?? 0;

  if (keywords.length < 2) {
    alert("Écris au moins quelques mots-clés avant de générer.");
    return;
  }

  const btnIcon = document.getElementById("btn-ia-icon");
  const btnText = document.getElementById("btn-ia-text");
  const btn = document.getElementById("btn-generate-ia");

  btn.disabled = true;
  btnIcon.textContent = "⏳";
  btnText.textContent = "Génération en cours...";

  const produit =
    document.querySelector(".product-name")?.textContent?.trim() ?? "";

  try {
    const res = await fetch("commentaires/suggest.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte: keywords, produit, note, mode: "rewrite" }),
    });
    const data = await res.json();

    if (data.success && data.rewrite) {
      document.getElementById("ia-suggestion-text").textContent = data.rewrite;
      document.getElementById("ia-suggestion-block").style.display = "block";
      document
        .getElementById("ia-suggestion-block")
        .scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      alert("Impossible de générer une phrase. Ajoute plus de mots-clés.");
    }
  } catch (err) {
    console.error("[IA rewrite]", err);
    alert("Erreur lors de la génération.");
  } finally {
    btn.disabled = false;
    btnIcon.textContent = "✨";
    btnText.textContent = "Générer un avis avec l'IA";
  }
}

function acceptIA() {
  const suggestion =
    document.getElementById("ia-suggestion-text")?.textContent ?? "";
  const ta = document.getElementById("review-text");
  if (!ta || !suggestion) return;
  ta.value = suggestion.slice(0, MAX_CHARS);
  ta.focus();
  _updateCounter(ta);
  _clearGhost();
  ta.classList.add("review-textarea--accepted");
  setTimeout(() => ta.classList.remove("review-textarea--accepted"), 600);
}

/* ══════════════════════════════════════════════════════════════════
   MODAL
══════════════════════════════════════════════════════════════════ */

window.openReviewModal = function () {
  const modal = document.getElementById("review-modal");
  if (!modal) return;
  modal.style.display = "flex";

  const kw = document.getElementById("review-keywords");
  const ta = document.getElementById("review-text");
  if (kw) kw.value = "";
  if (ta) {
    ta.value = "";
    ta.placeholder = PLACEHOLDER_DEFAULT;
  }
  document.getElementById("ia-suggestion-block").style.display = "none";
  window.currentRating = 0;
  document
    .querySelectorAll(".rating-input span")
    .forEach((s) => s.classList.remove("active"));

  document.getElementById("btn-generate-ia").onclick = generateIA;
  document.getElementById("btn-accept-ia").onclick = acceptIA;

  requestAnimationFrame(() => requestAnimationFrame(() => _initGhost()));
};

window.closeReviewModal = function () {
  const modal = document.getElementById("review-modal");
  if (modal) modal.style.display = "none";
  window.currentRating = 0;
  document
    .querySelectorAll(".rating-input span")
    .forEach((s) => s.classList.remove("active"));
  _clearGhost();
  clearTimeout(_ghostTimer);
};

/* ── Étoiles ────────────────────────────────────────────────────── */
document.addEventListener("click", function (e) {
  const star = e.target.closest(".rating-input span");
  if (!star) return;
  const v = parseInt(star.dataset.value);
  window.currentRating = v;
  document.querySelectorAll(".rating-input span").forEach((s) => {
    s.classList.toggle("active", parseInt(s.dataset.value) <= v);
  });
  const ta = document.getElementById("review-text");
  if (ta) {
    ta.placeholder = PLACEHOLDERS[v] || PLACEHOLDER_DEFAULT;
    _clearGhost();
    ta.focus();
  }
});

/* ══════════════════════════════════════════════════════════════════
   ENVOI
══════════════════════════════════════════════════════════════════ */

window.submitReview = async function () {
  const ta = document.getElementById("review-text");
  const contenu = ta ? ta.value.trim() : "";

  if (!window.currentRating || contenu === "") {
    alert("Veuillez sélectionner une note et écrire un avis.");
    return;
  }
  if (contenu.length > MAX_CHARS) {
    alert(`Votre avis dépasse ${MAX_CHARS} caractères.`);
    return;
  }

  // Désactive le bouton pendant l'envoi
  const btnSubmit = document.querySelector(".btn-submit");
  if (btnSubmit) {
    btnSubmit.disabled = true;
    btnSubmit.textContent = "Publication...";
  }

  const res = await fetch("commentaires/add.php", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      id: PRODUCT_ID,
      note: window.currentRating,
      contenu,
    }),
  });

  if (btnSubmit) {
    btnSubmit.disabled = false;
    btnSubmit.textContent = "Publier";
  }

  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    console.error("Réponse invalide :", text);
    alert("Erreur serveur.");
    return;
  }

  if (data.success) {
    closeReviewModal();
    loadCommentsPremium();
  } else if (data.error === "not_logged") {
    alert("Connecte-toi pour laisser un avis.");
  } else if (data.error === "not_purchased") {
    closeReviewModal();
    showReviewMessage(
      "🛍️ Tu dois avoir acheté cette chaussure pour laisser un avis.",
      "info",
    );
  } else if (data.error === "contenu_inapproprie") {
    // Message personnalisé du filtre
    showModalError(
      data.message ?? "Votre avis contient des termes non autorisés.",
    );
  } else if (data.error === "too_long") {
    showModalError(`L'avis ne peut pas dépasser ${MAX_CHARS} caractères.`);
  } else {
    alert("Erreur : " + (data.error || "inconnue"));
  }
};

/* Affiche une erreur dans la modal (sans la fermer) */
function showModalError(message) {
  let err = document.getElementById("modal-error-msg");
  if (!err) {
    err = document.createElement("div");
    err.id = "modal-error-msg";
    err.className = "modal-error-msg";
    const actions = document.querySelector(".modal-actions");
    if (actions) actions.insertAdjacentElement("beforebegin", err);
  }
  err.textContent = message;
  err.style.display = "block";
  setTimeout(() => {
    if (err) err.style.display = "none";
  }, 4000);
}

/* ══════════════════════════════════════════════════════════════════
   LISTE COMMENTAIRES
══════════════════════════════════════════════════════════════════ */

window.currentRating = 0;
window.currentSort = "recent";

window.loadCommentsPremium = async function () {
  const res = await fetch(
    `commentaires/list.php?id=${PRODUCT_ID}&sort=${currentSort}`,
  );
  const data = await res.json();

  const section = document.getElementById("comments-premium");
  const right = document.querySelector(".comments-right");
  const filters = document.querySelector(".comments-filters");

  if (data.empty) {
    document.getElementById("comments-list").innerHTML = "";
    document.getElementById("comments-summary").innerHTML = "";
    document.getElementById("comments-histogram").innerHTML = "";
    if (filters) filters.style.display = "none";
    if (right) right.style.display = data.is_logged ? "" : "none";
    section.style.display = data.is_logged ? "" : "none";
    return;
  }

  section.style.display = "";
  if (filters) filters.style.display = "";
  document.getElementById("comments-list").innerHTML = data.list_html;
  document.getElementById("comments-summary").innerHTML = data.summary_html;
  document.getElementById("comments-histogram").innerHTML = data.histogram_html;
  if (right) right.style.display = data.is_logged ? "" : "none";
};

window.filterComments = function () {
  currentSort = document.getElementById("comments-sort").value;
  loadCommentsPremium();
};

window.markUseful = async function (id, value) {
  await fetch(`commentaires/useful.php?id=${id}&value=${value}`);
  loadCommentsPremium();
};

window.deleteComment = async function (id) {
  if (!confirm("Supprimer cet avis ?")) return;
  await fetch(`commentaires/delete.php?id=${id}`);
  loadCommentsPremium();
};

function showReviewMessage(text, type = "info") {
  const existing = document.getElementById("review-message");
  if (existing) existing.remove();
  const msg = document.createElement("div");
  msg.id = "review-message";
  msg.className = `review-message review-message--${type}`;
  msg.textContent = text;
  const btn = document.querySelector(".btn-review");
  if (btn) btn.insertAdjacentElement("afterend", msg);
  setTimeout(() => msg.remove(), 5000);
}
