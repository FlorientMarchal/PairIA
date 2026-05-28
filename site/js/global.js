// js/global.js
// Burger menu + chat mobile

// ✅ Fonction globale toast (accessible partout)
window.showToast = function (msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);

  setTimeout(() => t.remove(), 2000);
};

document.addEventListener("DOMContentLoaded", () => {
  /* ── Burger menu ── */
  const burger = document.getElementById("burger");
  const navLinks = document.getElementById("nav-links");

  burger?.addEventListener("click", () => {
    navLinks?.classList.toggle("open");
  });

  /* ── Chat mobile ── */
  const chatPanel = document.getElementById("chat-panel");
  const chatOverlay = document.getElementById("chat-overlay");

  window.openChatMobile = () => {
    chatPanel?.classList.add("open");
    chatOverlay?.classList.add("open");
    document.getElementById("chat-fab")?.classList.add("hidden");
  };

  window.closeChatMobile = () => {
    chatPanel?.classList.remove("open");
    chatOverlay?.classList.remove("open");
    document.getElementById("chat-fab")?.classList.remove("hidden");
  };

  window.toggleChatMobile = () => {
    chatPanel?.classList.contains("open")
      ? closeChatMobile()
      : openChatMobile();
  };
});
