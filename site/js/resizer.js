//js/resizer.js — PairIA
(function () {
  // Largeurs limites
  const CHAT_MIN = 280; // px minimum du chat
  const CHAT_MAX = 680; // px maximum du chat
  const CHAT_DEFAULT = 420; // largeur par défaut (= --chat-w)
  const STORAGE_KEY = "pairia_chat_width";

  let isDragging = false;
  let startX = 0;
  let startWidth = 0;

  document.addEventListener("DOMContentLoaded", () => {
    const layout = document.querySelector(".page-layout");
    const chatPanel = document.getElementById("chat-panel");
    const content = document.getElementById("main-content");
    if (!layout || !chatPanel || !content) return;

    // ── Crée le séparateur ───────────────────────────────────────
    const resizer = document.createElement("div");
    resizer.className = "chat-resizer";
    resizer.id = "chat-resizer";

    const btn = document.createElement("button");
    btn.className = "chat-resizer-btn";
    btn.id = "chat-resizer-btn";
    btn.title = "Réduire / agrandir le chat";
    btn.innerHTML = "◀";
    btn.setAttribute("aria-label", "Réduire le chat");

    resizer.appendChild(btn);

    // Insère entre .page-content et .chat-panel
    layout.insertBefore(resizer, chatPanel);

    // ── Restaure la largeur sauvegardée ──────────────────────────
    const saved = parseInt(localStorage.getItem(STORAGE_KEY));
    if (saved && saved >= CHAT_MIN && saved <= CHAT_MAX) {
      _applyWidth(saved, chatPanel);
    }

    // ── Drag ─────────────────────────────────────────────────────
    resizer.addEventListener("mousedown", (e) => {
      // Clic sur le bouton → toggle, pas drag
      if (e.target === btn || btn.contains(e.target)) return;

      isDragging = true;
      startX = e.clientX;
      startWidth = chatPanel.offsetWidth;

      resizer.classList.add("dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      // On drag vers la gauche = chat plus large
      const delta = startX - e.clientX;
      const newWidth = Math.min(
        CHAT_MAX,
        Math.max(CHAT_MIN, startWidth + delta),
      );
      _applyWidth(newWidth, chatPanel);
    });

    document.addEventListener("mouseup", () => {
      if (!isDragging) return;
      isDragging = false;
      resizer.classList.remove("dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      // Sauvegarde
      localStorage.setItem(STORAGE_KEY, chatPanel.offsetWidth);
    });

    // ── Toggle bouton ─────────────────────────────────────────────
    btn.addEventListener("click", (e) => {
      e.stopPropagation();

      const isCollapsed = chatPanel.classList.contains("collapsed");

      // Active la transition douce uniquement pour le toggle
      chatPanel.classList.add("transitioning");
      setTimeout(() => chatPanel.classList.remove("transitioning"), 320);

      if (isCollapsed) {
        // Rouvrir
        const w = parseInt(localStorage.getItem(STORAGE_KEY)) || CHAT_DEFAULT;
        chatPanel.classList.remove("collapsed");
        _applyWidth(w, chatPanel);
        btn.innerHTML = "◀";
        btn.setAttribute("aria-label", "Réduire le chat");
      } else {
        // Fermer
        localStorage.setItem(STORAGE_KEY, chatPanel.offsetWidth);
        chatPanel.classList.add("collapsed");
        btn.innerHTML = "▶";
        btn.setAttribute("aria-label", "Ouvrir le chat");
      }
    });

    // ── Double-clic sur la barre → reset à la largeur par défaut ─
    resizer.addEventListener("dblclick", (e) => {
      if (e.target === btn || btn.contains(e.target)) return;
      chatPanel.classList.remove("collapsed");
      chatPanel.classList.add("transitioning");
      setTimeout(() => chatPanel.classList.remove("transitioning"), 320);
      _applyWidth(CHAT_DEFAULT, chatPanel);
      localStorage.setItem(STORAGE_KEY, CHAT_DEFAULT);
      btn.innerHTML = "◀";
    });
  });

  function _applyWidth(width, chatPanel) {
    chatPanel.style.width = width + "px";
  }
})();
