/* ══════════════════════════════════════════════════════════════════
   comment.js — PairIA
   • Placeholder dynamique selon la note ⭐
   • Ghost text (autocomplétion transparente) via IA Groq
   • Accepter avec Tab ou →
══════════════════════════════════════════════════════════════════ */

/* ── Placeholders selon la note ─────────────────────────────────── */
const PLACEHOLDERS = {
  1: "Décrivez votre déception (confort, taille, qualité, livraison...)",
  2: "Qu'est-ce qui pourrait être amélioré sur ces chaussures ?",
  3: "C'était bien mais pas parfait ? Dites-nous ce qui vous a plu et moins plu...",
  4: "Vous avez apprécié ces chaussures ! Qu'est-ce qui vous a convaincu ?",
  5: "Vous avez adoré ! Partagez ce qui vous a séduit : confort, style, qualité...",
};
const PLACEHOLDER_DEFAULT = "Décrivez votre expérience avec ces chaussures...";

/* ══════════════════════════════════════════════════════════════════
   GHOST TEXT — autocomplétion transparente
══════════════════════════════════════════════════════════════════ */

let _ghostTimer = null;
let _ghostSuggestion = ""; // suggestion complète en attente
let _isLoadingGhost = false;

/* Crée la couche ghost superposée au textarea */
function _buildGhostLayer(textarea) {
  // Wrapper positionné
  let wrapper = document.getElementById("review-text-wrapper");
  if (wrapper) return wrapper;

  wrapper = document.createElement("div");
  wrapper.id = "review-text-wrapper";
  wrapper.className = "review-text-wrapper";
  textarea.parentNode.insertBefore(wrapper, textarea);
  wrapper.appendChild(textarea);

  // Calque ghost (affiché sous le texte réel)
  const ghost = document.createElement("div");
  ghost.id = "review-ghost";
  ghost.className = "review-ghost";
  ghost.setAttribute("aria-hidden", "true");
  wrapper.appendChild(ghost);

  return wrapper;
}

/* Met à jour l'affichage ghost */
function _renderGhost(userText, suggestion) {
  const ghost = document.getElementById("review-ghost");
  if (!ghost) return;

  if (!suggestion || !suggestion.startsWith(userText)) {
    ghost.innerHTML = "";
    return;
  }

  const continuation = suggestion.slice(userText.length);
  if (!continuation) {
    ghost.innerHTML = "";
    return;
  }

  // Partie déjà tapée (invisible) + continuation en gris transparent
  ghost.innerHTML =
    '<span class="ghost-typed">' +
    _escapeHtml(userText) +
    "</span>" +
    '<span class="ghost-hint">' +
    _escapeHtml(continuation) +
    "</span>";
}

function _clearGhost() {
  _ghostSuggestion = "";
  const ghost = document.getElementById("review-ghost");
  if (ghost) ghost.innerHTML = "";
}

function _escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br>");
}

/* Appel API Groq pour obtenir une continuation */
async function _fetchGhost(texte) {
  const produit =
    typeof window.PRODUCT_NAME !== "undefined"
      ? window.PRODUCT_NAME
      : (document.querySelector(".product-name")?.textContent?.trim() ?? "");
  const note = window.currentRating ?? 0;

  try {
    const res = await fetch("commentaires/suggest.php", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte, produit, note }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.success || !data.suggestions?.length) return null;
    // On prend la première suggestion et on la préfixe avec le texte tapé
    return texte.trimEnd() + " " + data.suggestions[0];
  } catch {
    return null;
  }
}

/* Handler input : déclenche le ghost après pause */
function _onGhostInput(e) {
  const textarea = e.target;
  const text = textarea.value;

  clearTimeout(_ghostTimer);
  _clearGhost();

  if (text.trim().length < 3) return;

  _ghostTimer = setTimeout(async () => {
    if (_isLoadingGhost) return;
    _isLoadingGhost = true;

    const suggestion = await _fetchGhost(text.trim());
    _isLoadingGhost = false;

    // Vérifie que le texte n'a pas changé pendant la requête
    const current = document.getElementById("review-text");
    if (!current || current.value.trim() !== text.trim()) return;

    if (suggestion) {
      _ghostSuggestion = suggestion;
      _renderGhost(text, suggestion);
    }
  }, 550);
}

/* Tab ou → : accepte la suggestion ghost */
function _onGhostKeydown(e) {
  if (!_ghostSuggestion) return;

  if (e.key === "Tab" || e.key === "ArrowRight") {
    const textarea = document.getElementById("review-text");
    if (!textarea) return;

    // On n'accepte avec → que si le curseur est à la fin
    if (
      e.key === "ArrowRight" &&
      textarea.selectionStart !== textarea.value.length
    )
      return;

    e.preventDefault();
    const continuation = _ghostSuggestion.slice(
      textarea.value.trimEnd().length,
    );
    textarea.value = textarea.value.trimEnd() + " " + continuation.trimStart();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    _clearGhost();
    _ghostSuggestion = "";
  } else if (e.key === "Escape") {
    _clearGhost();
    _ghostSuggestion = "";
  }
}

/* Synchronise la largeur/hauteur du ghost avec le textarea */
function _syncGhostStyle(textarea) {
  const ghost = document.getElementById("review-ghost");
  if (!ghost) return;
  const cs = window.getComputedStyle(textarea);
  ghost.style.fontFamily = cs.fontFamily;
  ghost.style.fontSize = cs.fontSize;
  ghost.style.lineHeight = cs.lineHeight;
  ghost.style.padding = cs.padding;
  ghost.style.width = textarea.offsetWidth + "px";
}

/* Init au clic sur "Donner mon avis" */
function _initGhost() {
  const textarea = document.getElementById("review-text");
  if (!textarea) return;

  textarea.placeholder = PLACEHOLDER_DEFAULT;

  _buildGhostLayer(textarea);

  textarea.removeEventListener("input", _onGhostInput);
  textarea.removeEventListener("keydown", _onGhostKeydown);
  textarea.addEventListener("input", _onGhostInput);
  textarea.addEventListener("keydown", _onGhostKeydown);

  // Sync style ghost après resize
  new ResizeObserver(() => _syncGhostStyle(textarea)).observe(textarea);
  _syncGhostStyle(textarea);

  _clearGhost();
  console.log("[Ghost text] initialisé ✓");
}

/* ══════════════════════════════════════════════════════════════════
   COMMENTAIRES — fonctions principales
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

window.openReviewModal = function () {
  const modal = document.getElementById("review-modal");
  if (!modal) return;
  modal.style.display = "flex";
  requestAnimationFrame(() => requestAnimationFrame(() => _initGhost()));
};

window.closeReviewModal = function () {
  const modal = document.getElementById("review-modal");
  if (modal) modal.style.display = "none";
  currentRating = 0;
  document
    .querySelectorAll(".rating-input span")
    .forEach((s) => s.classList.remove("active"));
  const textarea = document.getElementById("review-text");
  if (textarea) {
    textarea.placeholder = PLACEHOLDER_DEFAULT;
    textarea.value = "";
  }
  _clearGhost();
  clearTimeout(_ghostTimer);
};

/* ── Clic étoile : note + placeholder dynamique ─────────────────── */
document.addEventListener("click", function (e) {
  const star = e.target.closest(".rating-input span");
  if (!star) return;

  const v = parseInt(star.dataset.value);
  currentRating = v;

  document.querySelectorAll(".rating-input span").forEach((s) => {
    s.classList.toggle("active", parseInt(s.dataset.value) <= v);
  });

  const textarea = document.getElementById("review-text");
  if (textarea) {
    textarea.placeholder = PLACEHOLDERS[v] || PLACEHOLDER_DEFAULT;
    _clearGhost(); // reset ghost quand on change la note
    textarea.focus();
  }
});

window.submitReview = async function () {
  const textarea = document.getElementById("review-text");
  const contenu = textarea ? textarea.value : "";

  if (!currentRating || contenu.trim() === "") {
    alert("Veuillez sélectionner une note et écrire un avis.");
    return;
  }

  const res = await fetch("commentaires/add.php", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: PRODUCT_ID, note: currentRating, contenu }),
  });

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
  } else {
    alert("Erreur : " + (data.error || "inconnue"));
  }
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
