// js/image_search.js
function initImageSearch() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/*";
  input.style.display = "none";
  input.id = "image-search-input";
  document.body.appendChild(input);

  input.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    input.value = "";
    // Avant : await sendImageMessage(file)  ← déclenchait immédiatement
    // Après : on stocke juste et on ouvre le prompt
    pendingImageFile = file;
    openImageTextPrompt(file);
  });
}

// Fichier image en attente d'envoi
let pendingImageFile = null;

function openImageTextPrompt(file) {
  // Affiche la preview + input texte dans la zone de saisie
  const preview = document.getElementById("image-preview-bar");
  if (preview) {
    const url = URL.createObjectURL(file);
    preview.innerHTML = `
      <div class="image-preview-inner">
        <img src="${url}" alt="preview" style="height:48px;border-radius:6px;">
        <span class="image-preview-name">${escapeHtml(file.name)}</span>
        <button onclick="cancelPendingImage()" title="Annuler">✕</button>
      </div>`;
    preview.style.display = "flex";
  }
  // Focus sur l'input texte pour que l'utilisateur puisse ajouter un message
  const input = document.getElementById("chat-input");
  if (input) {
    input.placeholder = "Décrivez ce que vous cherchez (optionnel)...";
    input.focus();
  }
}

function cancelPendingImage() {
  pendingImageFile = null;
  const preview = document.getElementById("image-preview-bar");
  if (preview) preview.style.display = "none";
  const input = document.getElementById("chat-input");
  if (input) input.placeholder = "Posez votre question...";
}

function openImageSearch() {
  document.getElementById("image-search-input")?.click();
}

document.addEventListener("DOMContentLoaded", () => initImageSearch());