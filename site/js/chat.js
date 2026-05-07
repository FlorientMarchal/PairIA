//  tableau qui stocke tout l'historique de la conversation

let conversationHistory = [];

async function sendMessage(question, productId = null) {
  try {
    const response = await fetch("http://localhost:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        product_id: productId,
        history: conversationHistory,
      }),
    });

    const data = await response.json();

    conversationHistory.push({ role: "user", content: question });
    conversationHistory.push({ role: "assistant", content: data.message });

    // Limite à 20 messages pour ne pas surcharger le contexte Mistral
    if (conversationHistory.length > 20) {
      conversationHistory = conversationHistory.slice(-20);
    }

    afficherMessage(data.message);

    if (data.action === "add_to_cart") {
      ajouterAuPanier(data.product_id, data.quantity);
    }
  } catch (error) {
    console.error("Erreur chatbot :", error);
  }
}

function resetConversation() {
  conversationHistory = [];
}
