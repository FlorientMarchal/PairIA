/* ══════════════════════════════════════════════════════════════════
   js/resizer.js — Séparateur draggable chat / catalogue
══════════════════════════════════════════════════════════════════ */

(function () {
  const CHAT_MIN = 280;
  const CHAT_MAX = 680;
  const CHAT_DEFAULT = 420;
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

    // Poignée visuelle centrale (3 points)
    const handle = document.createElement("div");
    handle.className = "chat-resizer-handle";
    handle.innerHTML = "⋮";
    resizer.appendChild(handle);

    layout.insertBefore(resizer, chatPanel);

    // ── Restaure la largeur sauvegardée ──────────────────────────
    const saved = parseInt(localStorage.getItem(STORAGE_KEY));
    if (saved && saved >= CHAT_MIN && saved <= CHAT_MAX) {
      chatPanel.style.width = saved + "px";
    }

    // ── Drag ─────────────────────────────────────────────────────
    resizer.addEventListener("mousedown", (e) => {
      isDragging = true;
      startX = e.clientX;
      startWidth = chatPanel.offsetWidth;

      resizer.classList.add("dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const delta = startX - e.clientX;
      const newWidth = Math.min(
        CHAT_MAX,
        Math.max(CHAT_MIN, startWidth + delta),
      );
      chatPanel.style.width = newWidth + "px";
    });

    document.addEventListener("mouseup", () => {
      if (!isDragging) return;
      isDragging = false;
      resizer.classList.remove("dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      localStorage.setItem(STORAGE_KEY, chatPanel.offsetWidth);
    });

    // ── Double-clic → reset largeur par défaut ───────────────────
    resizer.addEventListener("dblclick", () => {
      chatPanel.classList.add("transitioning");
      setTimeout(() => chatPanel.classList.remove("transitioning"), 320);
      chatPanel.style.width = CHAT_DEFAULT + "px";
      localStorage.setItem(STORAGE_KEY, CHAT_DEFAULT);
    });
  });
})();
