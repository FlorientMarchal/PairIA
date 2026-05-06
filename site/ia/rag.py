# ia/rag.py
# Pipeline RAG : question → Qdrant → prompt → Ollama → réponse

import ollama
from qdrant_client import QdrantClient
from prompt import build_prompt, SYSTEM_PROMPT

# Connexion à Qdrant (fichier local)
qdrant = QdrantClient(path="./qdrant_db")

def get_response(question: str, product_id: int = None) -> dict:
    """
    Pipeline RAG complet :
    1. Vectorise la question avec nomic-embed-text
    2. Cherche les produits pertinents dans Qdrant
    3. Construit le prompt
    4. Envoie à Mistral via Ollama
    5. Retourne la réponse structurée
    """

    # ── Étape 1 : vectoriser la question ──
    embed_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=question
    )
    question_vector = embed_response["embedding"]

    # ── Étape 2 : chercher dans Qdrant ──
    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=3
    ).points

    produits_trouves = []
    for r in results:
        produits_trouves.append({
            "id":    r.id,
            "name":  r.payload.get("nom", ""),
            "price": r.payload.get("prix", 0),
            "emoji": "👟",
            "categorie": r.payload.get("categorie", ""),
            "marque":    r.payload.get("marque", ""),
            "url_image": r.payload.get("url_image", ""),
            "description": ""
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

    # ── Étape 5 : détecter intention ajout panier ──
    action            = None
    product_id_action = None
    quantity          = None

    message_lower = message.lower()
    if any(kw in message_lower for kw in ["ajouté", "ajouter", "panier"]):
        if produits_trouves:
            action            = "add_to_cart"
            product_id_action = produits_trouves[0]["id"]
            quantity          = 1

    return {
        "message":    message,
        "products":   produits_trouves[:3],
        "action":     action,
        "product_id": product_id_action,
        "quantity":   quantity
    }