# ia/rag.py
# Pipeline RAG : question → Qdrant → prompt → Ollama → réponse

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from qdrant_client import QdrantClient
from llm_prompt import build_prompt, SYSTEM_PROMPT

qdrant = QdrantClient(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db"))

_CART_KEYWORDS = [
    "ajoute au panier", "ajouter au panier", "mets au panier",
    "mettre au panier", "ajoute-le", "ajoute-la", "je le veux",
    "je la veux", "je veux l'acheter", "commande", "achète",
    "acheter", "je prends", "je veux celui", "je veux celle"
]


def _user_wants_cart(question: str) -> bool:
    q = question.lower().strip()
    return any(kw in q for kw in _CART_KEYWORDS)


def _nb_produits_from_history(history: list) -> int:
    """
    Décide combien de produits afficher selon l'avancement de la conversation.
    - 0 échange  → 3 produits (découverte)
    - 1-2 échanges → 2 produits (affinage)
    - 3+ échanges  → 1 produit  (sélection)
    """
    nb_echanges = len(history) // 2  # 1 échange = 1 user + 1 assistant
    if nb_echanges == 0:
        return 3
    elif nb_echanges <= 2:
        return 2
    else:
        return 1


def get_response(question: str, product_id: int = None, history: list = None) -> dict:

    if history is None:
        history = []
    
    # Vectorisation de la question
    embed_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=question
    )
    question_vector = embed_response["embedding"]

    # Qdrant récupère toujours 3 candidats
    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=3
    ).points

    produits_trouves = []
    for r in results:
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

    # Nombre de produits à afficher selon l'historique
    nb_produits = _nb_produits_from_history(history)

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
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": prompt})
    print("\n=== MESSAGES ENVOYÉS À MISTRAL ===")
    for msg in messages:
        print(f"[{msg['role']}] {msg['content']}")
    print("==================================\n")

    response = ollama.chat(model="mistral", messages=messages)

    # Appel Mistral + parsing JSON
    response = ollama.chat(model="mistral", messages=messages)
    raw      = response["message"]["content"]

    try:
        parsed  = json.loads(raw)
        message = parsed.get("message", raw)
        # nb_produits reste celui de _nb_produits_from_history — Mistral n'est pas fiable là-dessus
    except (json.JSONDecodeError, KeyError):
        message = raw

    # Détection intention panier UNIQUEMENT sur la question utilisateur
    action            = None
    product_id_action = None
    quantity          = None

    if _user_wants_cart(question) and produits_trouves:
        action            = "add_to_cart"
        product_id_action = produits_trouves[0]["id"]
        quantity          = 1

    return {
        "message":    message,
        "products":   produits_trouves[:nb_produits],
        "action":     action,
        "product_id": product_id_action,
        "quantity":   quantity
    }

