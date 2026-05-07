# ia/rag.py
# Pipeline RAG : question → Qdrant → prompt → Ollama → réponse

import ollama
from qdrant_client import QdrantClient
from prompt import build_prompt, SYSTEM_PROMPT

qdrant = QdrantClient(path="./qdrant_db")


def get_response(question: str, product_id: int = None, history: list = None) -> dict:

    if history is None:
        history = []

    # Vectorisation de la question
    embed_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=question
    )
    question_vector = embed_response["embedding"]

    # Recherche dans Qdrant
    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=3
    ).points

    produits_trouves = []
    for r in results:
        # Récupérer tailles et couleurs stockées en payload
        tailles_raw  = r.payload.get("tailles",  "")
        couleurs_raw = r.payload.get("couleurs", "")

        tailles  = [t.strip() for t in tailles_raw.split(",")  if t.strip()] if tailles_raw  else []
        couleurs = [c.strip() for c in couleurs_raw.split(",") if c.strip()] if couleurs_raw else []

        produits_trouves.append({
            "id":          r.id,
            "name":        r.payload.get("nom",         ""),
            "price":       r.payload.get("prix",        0),
            "emoji":       "👟",
            "categorie":   r.payload.get("categorie",   ""),
            "marque":      r.payload.get("marque",      ""),
            "url_image":   r.payload.get("url_image",   ""),
            "description": r.payload.get("description", ""),
            "tailles":     tailles,
            "couleurs":    couleurs,
        })

    # Construction du prompt
    prompt = build_prompt(
        question=question,
        produits=produits_trouves,
        product_id=product_id
    )

    # Messages avec historique
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    MAX_HISTORY = 10
    for msg in history[-MAX_HISTORY:]:
        messages.append({
            "role":    msg["role"],
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": prompt})

    response = ollama.chat(model="mistral", messages=messages)
    message  = response["message"]["content"]

    # Détecter intention ajout panier
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