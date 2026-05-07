# ia/rag.py
# Pipeline RAG : question → Qdrant → prompt → Ollama → réponse

import ollama
from qdrant_client import QdrantClient
from prompt import build_prompt, SYSTEM_PROMPT

qdrant = QdrantClient(path="./qdrant_db")


def get_response(question: str, product_id: int = None, history: list = None) -> dict:

    # création d'une nouvelle liste vide à chaque appel si rien n'est passé
    if history is None:
        history = []

    # vectorisation de la question
    embed_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=question
    )
    question_vector = embed_response["embedding"]

    # chercher dans Qdrant
    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=3
    ).points

    produits_trouves = []
    for r in results:
        produits_trouves.append({
            "id":          r.id,
            "name":        r.payload.get("nom", ""),
            "price":       r.payload.get("prix", 0),
            "emoji":       "👟",
            "categorie":   r.payload.get("categorie", ""),
            "marque":      r.payload.get("marque", ""),
            "url_image":   r.payload.get("url_image", ""),
            "description": r.payload.get("description", "")
        })

    # construction du prompt RAG
    prompt = build_prompt(
        question=question,
        produits=produits_trouves,
        product_id=product_id
    )

    # ── Construction des messages ──
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "system",
            "content": "Historique de conversation entre l'utilisateur et l'assistant :"
        }
    ]

    # historique (limité)
    MAX_HISTORY = 10
    for msg in history[-MAX_HISTORY:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # contexte RAG injecté comme system
    messages.append({
        "role": "system",
        "content": prompt
    })

    # vraie question utilisateur
    messages.append({
        "role": "user",
        "content": question
    })

    # appel au modèle
    response = ollama.chat(model="mistral", messages=messages)
    message = response["message"]["content"]

    # ── Détection intention ajout panier ──
    action = None
    product_id_action = None
    quantity = None

    message_lower = message.lower()
    if any(kw in message_lower for kw in ["ajouté", "ajouter", "panier"]):
        if produits_trouves:
            action = "add_to_cart"
            product_id_action = produits_trouves[0]["id"]
            quantity = 1

    return {
        "message": message,
        "products": produits_trouves[:3],
        "action": action,
        "product_id": product_id_action,
        "quantity": quantity
    }