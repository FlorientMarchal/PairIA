// js/chat.js
const API_URL = "http://localhost:8000";

let conversationHistory = [];
let sessionId = crypto.randomUUID();

/*
   CHAT TEXTE
*/
async function sendMessage(text) {
  const container = document.getElementById("messages");
  if (!container || !text.trim()) return;

  const input = document.getElementById("chat-input");
  const sendBtn = document.querySelector(".chat-send-btn");
  if (input) input.disabled = true;
  if (sendBtn) sendBtn.disabled = true;

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
    const body = {
      question: text,
      history: conversationHistory,
      session_id: sessionId,
    };
    if (typeof PRODUCT_ID !== "undefined") body.product_id = PRODUCT_ID;

    const response = await fetch(`${API_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

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

          if (data.type === "products_final") {
            // Produits filtrés reçus après le texte complet
            products = data.products || [];
            action = data.action;
            product_id = data.product_id;
            layout      = data.layout || null; 
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
              time.textContent = "maintenant";
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

    conversationHistory.push({ role: "user", content: text });
    conversationHistory.push({ role: "assistant", content: message });
    if (conversationHistory.length > 20)
      conversationHistory = conversationHistory.slice(-20);

    console.log(
      "[HISTORIQUE MIS À JOUR]",
      JSON.parse(JSON.stringify(conversationHistory)),
    );

    if (layout === "comparison" && products.length >= 2) {
        showComparisonView(products[0], products[1], container);
    } else if (products.length === 1) {
        showCartSelector(products[0], container);
    } else if (products.length > 1) {
        showProductPicker(products, container);
    }

    if (action === "add_to_cart" && product_id) {
      const produit = products.find((p) => p.id === product_id) || products[0];
      if (produit) showCartSelector(produit);
    }

    container.scrollTop = container.scrollHeight;
  } catch (error) {
    typing.remove();
    appendBotMessageText(
      "Désolé, je suis temporairement indisponible. Réessayez dans un instant.",
    );
    console.error("Erreur API chat :", error);
  } finally {
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

/* ══════════════════════════════════════
   COMPARAISON CÔTE À CÔTE
══════════════════════════════════════ */
function showComparisonView(p1, p2, container) {
    if (!container) container = document.getElementById("messages");

    const div = document.createElement("div");
    div.className = "chat-msg bot";

    function colHtml(p, idx) {
        const tailles  = (p.tailles  || []).join(", ") || "—";
        const couleurs = (p.couleurs || []).join(", ") || "—";
        const resume   = p.resume || "";   // ← résumé LLM
        return `
        <div class="chat-compare-col">
            <div class="chat-compare-img">
                ${p.url_image
                    ? `<img src="${escapeHtml(p.url_image)}"
                            alt="${escapeHtml(p.name)}"
                            onerror="this.style.display='none'">`
                    : "👟"}
            </div>
            <div class="chat-compare-name">${escapeHtml(p.name)}</div>
            <div class="chat-compare-price">${p.price} €</div>
            ${resume ? `<div class="chat-compare-resume">${escapeHtml(resume)}</div>` : ""}
            <table class="chat-compare-table">
                <tr>
                    <td class="chat-compare-label">Marque</td>
                    <td>${escapeHtml(p.marque || "—")}</td>
                </tr>
                <tr>
                    <td class="chat-compare-label">Catégorie</td>
                    <td>${escapeHtml(p.categorie || "—")}</td>
                </tr>
                <tr>
                    <td class="chat-compare-label">Tailles</td>
                    <td>${escapeHtml(tailles)}</td>
                </tr>
                <tr>
                    <td class="chat-compare-label">Couleurs</td>
                    <td>${escapeHtml(couleurs)}</td>
                </tr>
            </table>

            <button class="chat-cart-btn"
                style="margin-top:10px;width:100%"
                onclick="showCartSelector(${JSON.stringify(p).replace(/"/g, '&quot;')}, document.getElementById('messages'))">
                🛒 Choisir ce modèle
            </button>
        </div>`;
    }

    div.innerHTML = `
        <div class="chat-compare-card">
            <div class="chat-compare-title">Comparaison</div>
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

        // Reset d'abord
        cols.forEach(col => col.style.height = "");

        // Prend le max des deux hauteurs naturelles
        const maxH = Math.max(...[...cols].map(col => col.offsetHeight));
        cols.forEach(col => col.style.height = maxH + "px");
    });
    container.scrollTop = container.scrollHeight;
}

/*
   CHAT IMAGE + TEXTE
*/
async function sendImageWithText(file, text) {
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
    <div class="chat-time">maintenant</div>`;
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
    formData.append("history", JSON.stringify(conversationHistory));
    formData.append("session_id", sessionId);

    const response = await fetch(`${API_URL}/chat/stream-image`, {
      method: "POST",
      body: formData,
    });

    let typingRemoved = false;
    let bubble = null;
    let message = "";
    let products = [];
    let action = null;
    let product_id = null;

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

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

          if (data.type === "products_final") {
            // Produits filtrés reçus après le texte complet
            products = data.products || [];
            action = data.action;
            product_id = data.product_id;
            layout      = data.layout || null; 
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
              time.textContent = "maintenant";
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

    // Historique : description textuelle de l'image + produits trouvés
    const productContext =
      products.length > 0
        ? products.map((p) => `${p.name} (${p.price}€)`).join(", ")
        : "aucun produit trouvé";

    const imageContext =
      `[Recherche par image${text ? ` avec message : "${text}"` : ""}] ` +
      `Produits suggérés : ${productContext}`;

    conversationHistory.push({ role: "user", content: imageContext });
    conversationHistory.push({ role: "assistant", content: message });
    if (conversationHistory.length > 20)
      conversationHistory = conversationHistory.slice(-20);

    console.log(
      "[HISTORIQUE MIS À JOUR]",
      JSON.parse(JSON.stringify(conversationHistory)),
    );

    if (layout === "comparison" && products.length >= 2) {
        showComparisonView(products[0], products[1], container);
    } else if (products.length === 1) {
        showCartSelector(products[0], container);
    } else if (products.length > 1) {
        showProductPicker(products, container);
    }

    if (action === "add_to_cart" && product_id) {
      const produit = products.find((p) => p.id === product_id) || products[0];
      if (produit) showCartSelector(produit);
    }

    container.scrollTop = container.scrollHeight;
  } catch (error) {
    typing.remove();
    appendBotMessageText(
      "Désolé, la recherche par image est temporairement indisponible.",
    );
    console.error("Erreur image+texte :", error);
  } finally {
    if (input) {
      input.disabled = false;
      input.focus();
    }
    if (sendBtn) sendBtn.disabled = false;
  }
}

function resetConversation() {
  conversationHistory = [];
  sessionId = crypto.randomUUID();
  const container = document.getElementById("messages");
  if (container) container.innerHTML = "";
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
    <div class="chat-time">maintenant</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendBotMessage(data) {
  const container = document.getElementById("messages");

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "chat-msg bot";
  bubbleDiv.innerHTML = `
    <div class="chat-bubble">${escapeHtml(data.message)}</div>
    <div class="chat-time">maintenant</div>`;
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
    <div class="chat-time">maintenant</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendTyping() {
  const container = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "chat-msg bot";
  div.id = "typing-indicator";

  div.innerHTML = `
    <div class="chat-typing">
      <div class="chat-typing-dot"></div>
      <div class="chat-typing-dot"></div>
      <div class="chat-typing-dot"></div>
    </div>
    <div class="chat-typing-msg"
         id="typing-msg"
         style="font-size:11px;color:#999;margin-top:4px;display:none">
      Analyse en cours...
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
function showProductPicker(produits, container) {
  if (!container) container = document.getElementById("messages");

  const div = document.createElement("div");
  div.className = "chat-msg bot";

  const itemsHtml = produits
    .map((p, i) => {
      const hasTailles = (p.tailles || []).length > 0;
      const hasCouleurs = (p.couleurs || []).length > 0;

      const taillesHtml = (p.tailles || [])
        .map(
          (t) =>
            `<span class="chat-opt" onclick="chatPickOpt(this)" data-group="taille-${i}-${p.id}">${escapeHtml(t)}</span>`,
        )
        .join("");

      const couleursHtml = (p.couleurs || [])
        .map(
          (c) =>
            `<span class="chat-opt" onclick="chatPickOpt(this)" data-group="couleur-${i}-${p.id}">${escapeHtml(c)}</span>`,
        )
        .join("");

      return `
      <div class="chat-pick-item">
        <div class="chat-pick-top">
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
        </div>
        <button class="chat-pick-toggle-btn" onclick="chatToggleSelector(this)">
          🛒 Ajouter au panier
        </button>
        <div class="chat-pick-selector" style="display:none">
          ${
            hasTailles
              ? `
            <div class="chat-option-title">Pointure</div>
            <div class="chat-option-group" data-type="taille">${taillesHtml}</div>
          `
              : ""
          }
          ${
            hasCouleurs
              ? `
            <div class="chat-option-title">Couleur</div>
            <div class="chat-option-group" data-type="couleur">${couleursHtml}</div>
          `
              : ""
          }
          <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>
          <button class="chat-cart-btn"
            onclick="confirmChatCartFromPicker(${p.id}, this)"
            ${hasTailles || hasCouleurs ? "disabled" : ""}>
            Confirmer l'ajout
          </button>
        </div>
      </div>`;
    })
    .join("");

  div.innerHTML = `
    <div class="chat-product-card">
      <div class="chat-pick-title">Voici quelques suggestions</div>
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
  const selector = btn.nextElementSibling;
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
    )?.textContent || null;
  const couleur =
    selector.querySelector(
      '.chat-option-group[data-type="couleur"] .chat-opt.active',
    )?.textContent || null;

  btn.disabled = true;
  btn.textContent = "…";
  if (errEl) errEl.textContent = "";

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent = "✓ Ajouté au panier !";
    btn.style.background = "#2f855a";
  } else {
    btn.disabled = false;
    btn.textContent = "Confirmer l'ajout";
    if (errEl) errEl.textContent = result?.error || "Erreur lors de l'ajout.";
  }
}

/* ══════════════════════════════════════
   CARTE SÉLECTEUR TAILLE / COULEUR
══════════════════════════════════════ */
function showCartSelector(produit, container) {
  if (!container) container = document.getElementById("messages");

  const div = document.createElement("div");
  div.className = "chat-msg bot";

  const hasTailles = (produit.tailles || []).length > 0;
  const hasCouleurs = (produit.couleurs || []).length > 0;

  const taillesHtml = (produit.tailles || [])
    .map(
      (t) =>
        `<button class="chat-option-btn" onclick="chatSelectOption(this)" data-value="${escapeAttr(t)}">${escapeHtml(t)}</button>`,
    )
    .join("");

  const couleursHtml = (produit.couleurs || [])
    .map(
      (c) =>
        `<button class="chat-option-btn" onclick="chatSelectOption(this)" data-value="${escapeAttr(c)}">${escapeHtml(c)}</button>`,
    )
    .join("");

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
          <div class="chat-product-price">${produit.price} €</div>
        </div>
      </div>

      ${
        hasTailles
          ? `
        <div class="chat-option-title">Pointure</div>
        <div class="chat-option-group" data-type="taille">${taillesHtml}</div>
      `
          : ""
      }

      ${
        hasCouleurs
          ? `
        <div class="chat-option-title">Couleur</div>
        <div class="chat-option-group" data-type="couleur">${couleursHtml}</div>
      `
          : ""
      }

      <div class="chat-selector-error" style="font-size:12px;color:#e53e3e;margin-top:6px;min-height:16px;"></div>

      <button class="chat-cart-btn"
        onclick="confirmChatCart(${produit.id}, this)"
        ${hasTailles || hasCouleurs ? "disabled" : ""}>
        Ajouter au panier
      </button>
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
    )?.dataset.value || null;
  const couleur =
    card.querySelector(
      '.chat-option-group[data-type="couleur"] .chat-option-btn.active',
    )?.dataset.value || null;

  btn.disabled = true;
  btn.textContent = "…";
  if (errEl) errEl.textContent = "";

  const result = await addToCart(productId, 1, taille, couleur);

  if (result?.success) {
    btn.textContent = "✓ Ajouté au panier !";
    btn.style.background = "#2f855a";
  } else {
    btn.disabled = false;
    btn.textContent = "Ajouter au panier";
    if (errEl) errEl.textContent = result?.error || "Erreur lors de l'ajout.";
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

document.addEventListener("DOMContentLoaded", () => {
  updateCartCount();

  document.addEventListener("click", (e) => {
    const chip = e.target.closest(".chat-chip");
    if (chip && chip.dataset.msg) {
      sendMessage(chip.dataset.msg);
    }
  });

  //  ACTIVATION MICRO SI SUPPORTÉ
  if (typeof voiceSupported === "function" && voiceSupported()) {
    const mic = document.getElementById("voice-btn");
    if (mic) mic.style.display = "inline-flex";
  }
});
