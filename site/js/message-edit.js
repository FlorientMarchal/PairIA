/* ══════════════════════════════════════════════════════════════════
   js/message-edit.js — Modification de message après stop
══════════════════════════════════════════════════════════════════ */

(function () {
  const _originalStop = window.stopGeneration;
  window.stopGeneration = function () {
    if (_originalStop) _originalStop();
    setTimeout(_showEditOnLastUserMessage, 200);
  };

  function _showEditOnLastUserMessage() {
    const container = document.getElementById("messages");
    if (!container) return;
    const userMsgs = container.querySelectorAll(".chat-msg.user");
    if (!userMsgs.length) return;
    const lastUser = userMsgs[userMsgs.length - 1];
    if (lastUser.querySelector(".msg-edit-btn")) return;

    const editBtn = document.createElement("button");
    editBtn.className = "msg-edit-btn";
    editBtn.textContent = "";
    editBtn.title = "Modifier et renvoyer ce message";
    editBtn.addEventListener("click", () => _enterEditMode(lastUser, editBtn));
    lastUser.appendChild(editBtn);
  }

  function _enterEditMode(msgDiv, editBtn) {
    const bubble = msgDiv.querySelector(".chat-bubble");
    if (!bubble) return;
    const originalText = bubble.textContent.trim();

    // Wrapper
    const wrapper = document.createElement("div");
    wrapper.className = "msg-edit-wrapper";

    // Textarea
    const textarea = document.createElement("textarea");
    textarea.className = "msg-edit-textarea";
    textarea.value = originalText;
    // Hauteur auto selon le contenu
    textarea.style.height = "auto";
    setTimeout(() => {
      textarea.style.height = textarea.scrollHeight + "px";
    }, 0);
    textarea.addEventListener("input", () => {
      textarea.style.height = "auto";
      textarea.style.height = textarea.scrollHeight + "px";
    });

    // Ligne d'actions
    const actions = document.createElement("div");
    actions.className = "msg-edit-actions";

    const hint = document.createElement("span");
    hint.className = "msg-edit-hint";
    hint.textContent = "Entrée pour envoyer · Échap pour annuler";

    const confirmBtn = document.createElement("button");
    confirmBtn.className = "msg-edit-confirm";
    confirmBtn.innerHTML = "✓ Envoyer";

    const cancelBtn = document.createElement("button");
    cancelBtn.className = "msg-edit-cancel";
    cancelBtn.innerHTML = "✕";
    cancelBtn.title = "Annuler";

    actions.appendChild(hint);
    actions.appendChild(confirmBtn);
    actions.appendChild(cancelBtn);

    wrapper.appendChild(textarea);
    wrapper.appendChild(actions);

    bubble.style.display = "none";
    editBtn.style.display = "none";
    msgDiv.appendChild(wrapper);

    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    const doConfirm = () => {
      const newText = textarea.value.trim();
      if (!newText) return;
      _applyEdit(msgDiv, wrapper, newText);
    };

    const doCancel = () => {
      wrapper.remove();
      bubble.style.display = "";
      editBtn.style.display = "";
    };

    confirmBtn.addEventListener("click", doConfirm);
    cancelBtn.addEventListener("click", doCancel);
    textarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        doConfirm();
      }
      if (e.key === "Escape") doCancel();
    });
  }

  function _applyEdit(editedMsgDiv, wrapper, newText) {
    const container = document.getElementById("messages");
    if (!container) return;

    // Supprime tous les messages après le message édité
    const allMsgs = Array.from(container.children);
    const idx = allMsgs.indexOf(editedMsgDiv);
    if (idx !== -1) {
      for (let i = allMsgs.length - 1; i > idx; i--) {
        allMsgs[i].remove();
      }
    }
    editedMsgDiv.remove();

    // Nettoie l'historique
    if (typeof conversationHistory !== "undefined") {
      while (
        conversationHistory.length > 0 &&
        conversationHistory[conversationHistory.length - 1].role !== "user"
      ) {
        conversationHistory.pop();
      }
      if (
        conversationHistory.length > 0 &&
        conversationHistory[conversationHistory.length - 1].role === "user"
      ) {
        conversationHistory.pop();
      }
      try {
        sessionStorage.setItem(
          "chatHistory",
          JSON.stringify(conversationHistory),
        );
      } catch (_) {}
    }

    if (typeof sendMessage === "function") sendMessage(newText);
  }
})();
