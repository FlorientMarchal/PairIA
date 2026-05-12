// js/image_search.js
// Recherche de produits par image

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
    await sendImageMessage(file);
  });
}

async function sendImageMessage(file) {
  const container = document.getElementById("messages");
  if (!container) return;

  // Affiche l'image dans le chat comme message utilisateur
  const reader = new FileReader();
  reader.onload = async (e) => {
    const imageUrl = e.target.result;

    const userDiv = document.createElement("div");
    userDiv.className = "chat-msg user";
    userDiv.innerHTML = `
      <div class="chat-bubble chat-bubble-image">
        <img src="${imageUrl}" alt="Image recherche" style="max-width:200px;max-height:200px;border-radius:8px;">
      </div>
      <div class="chat-time">maintenant</div>`;
    container.appendChild(userDiv);
    container.scrollTop = container.scrollHeight;

    // Indicateur de chargement
    const typing = appendTyping();

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/search-image`, {
        method: "POST",
        body: formData
      });

      const data = await response.json();
      typing.remove();

      // Bulle réponse bot
      const botDiv = document.createElement("div");
      botDiv.className = "chat-msg bot";
      botDiv.innerHTML = `
        <div class="chat-bubble">J'ai trouvé des chaussures similaires à votre photo :</div>
        <div class="chat-time">maintenant</div>`;
      container.appendChild(botDiv);

      // Affiche les produits
      const products = data.products || [];
      if (products.length === 1) {
        showCartSelector(products[0], container);
      } else if (products.length > 1) {
        showProductPicker(products, container);
      } else {
        appendBotMessageText("Aucun produit similaire trouvé. Essayez avec une autre photo.");
      }

      container.scrollTop = container.scrollHeight;

    } catch (error) {
      typing.remove();
      appendBotMessageText("Désolé, la recherche par image est temporairement indisponible.");
      console.error("Erreur recherche image :", error);
    }
  };

  reader.readAsDataURL(file);
}

function openImageSearch() {
  document.getElementById("image-search-input")?.click();
}

document.addEventListener("DOMContentLoaded", () => initImageSearch());