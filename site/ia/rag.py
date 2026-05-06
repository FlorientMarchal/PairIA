# ia/rag.py
# Pipeline RAG : question → Chroma DB → prompt → Ollama → réponse

import ollama
import chromadb
from prompt import build_prompt, SYSTEM_PROMPT

# Connexion à Chroma DB (fichier local dans le dossier ia/)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="produits")

def get_response(question: str, product_id: int = None) -> dict:
    """
    Pipeline RAG complet :
    1. Vectorise la question avec nomic-embed-text
    2. Cherche les produits pertinents dans Chroma DB
    3. Construit le prompt avec les résultats
    4. Envoie à Mistral via Ollama
    5. Retourne la réponse structurée
    """

    # ── Étape 1 : vectoriser la question ──
    embed_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=question
    )
    question_vector = embed_response["embedding"]

    # ── Étape 2 : chercher dans Chroma DB ──
    results = collection.query(
        query_embeddings=[question_vector],
        n_results=3,  # top 3 produits les plus pertinents
        include=["documents", "metadatas"]
    )

    produits_trouves = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            produits_trouves.append({
                "id":    meta.get("id", 0),
                "name":  meta.get("nom", ""),
                "price": meta.get("prix", 0),
                "emoji": meta.get("emoji", "👟"),
                "description": doc
            })

    # ── Étape 3 : construire le prompt ──
    prompt = build_prompt(
        question=question,
        produits=produits_trouves,
        product_id=product_id
    )

    # ── Étape 4 : appel à Mistral via Ollama ──
    response = ollama.chat(
        model="mistral",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt}
        ]
    )

    message = response["message"]["content"]

    # ── Étape 5 : détecter une intention d'ajout au panier ──
    action     = None
    product_id_action = None
    quantity   = None

    message_lower = message.lower()
    if any(kw in message_lower for kw in ["ajouté", "ajouter", "panier"]):
        if produits_trouves:
            action = "add_to_cart"
            product_id_action = produits_trouves[0]["id"]
            quantity = 1

    # ── Réponse finale ──
    return {
        "message":    message,
        "products":   produits_trouves[:3],
        "action":     action,
        "product_id": product_id_action,
        "quantity":   quantity
    }