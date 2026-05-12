# ia/rag.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from qdrant_client import QdrantClient
from llm_prompt import build_prompt, SYSTEM_PROMPT

# Connexion Qdrant locale
qdrant = QdrantClient(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db"))


# Couvre plus de formulations naturelles françaises
_CART_KEYWORDS = [
    "ajoute au panier", "ajouter au panier", "mets au panier",
    "mettre au panier", "ajoute-le", "ajoute-la", "je le veux",
    "je la veux", "je veux l'acheter", "commande", "achète",
    "acheter", "je prends", "je veux celui", "je veux celle",
    "je veux commander", "je veux prendre", "ça me convient",
    "je le prends", "je la prends", "mets-le", "mets-la",
    "ajoute ce produit", "je suis intéressé", "comment acheter",
    "je veux celui-ci", "je veux celle-ci", "parfait je le veux"
]


def _user_wants_cart(question: str) -> bool:
    q = question.lower().strip()
    return any(kw in q for kw in _CART_KEYWORDS)


def _nb_produits_from_history(history: list) -> int:
    """
    Adapte le nombre de produits affichés selon l'avancement
    de la conversation :
    - 0 échange  → 3 produits (découverte)
    - 1-2 échanges → 2 produits (affinage)
    - 3+ échanges  → 1 produit  (sélection finale)
    """
    nb_echanges = len(history) // 2
    if nb_echanges == 0:
        return 3
    elif nb_echanges <= 2:
        return 2
    else:
        return 1


def get_response(question: str, product_id: int = None, history: list = None) -> dict:

    if history is None:
        history = []

    # ── Étape 1 : vectoriser la question ──
    # Si Ollama est éteint, on retourne un message clair au lieu d'un crash 500
    try:
        embed_response = ollama.embeddings(
            model="nomic-embed-text",
            prompt=question
        )
    except Exception:
        raise RuntimeError(
            "Le serveur Ollama est inaccessible. "
            "Lance 'ollama serve' dans un terminal."
        )

    question_vector = embed_response["embedding"]

    # ── Étape 2 : chercher dans Qdrant ──

    # Récupère plus de candidats pour mieux filtrer par taille/couleur/prix
    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=5
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

    # Nombre de produits à afficher selon l'avancement de la conversation
    nb_produits = _nb_produits_from_history(history)

    # ── Étape 3 : construire le prompt ──
    prompt = build_prompt(
        question=question,
        produits=produits_trouves,
        product_id=product_id
    )

    # ── Étape 4 : construire les messages avec historique ──
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Injection des échanges précédents (max 10 = 5 échanges user/assistant)
    # Limite la taille du contexte envoyé à Mistral
    MAX_HISTORY = 10
    for msg in history[-MAX_HISTORY:]:
        messages.append({
            "role":    msg["role"],
            "content": msg["content"]
        })

    messages.append({"role": "user", "content": prompt})

    # ── Appel Mistral ──

    # Protège contre les timeouts ou erreurs de génération
    try:
        response = ollama.chat(model="mistral", messages=messages)
    except Exception:
        raise RuntimeError(
            "Erreur lors de la génération Mistral. "
            "Vérifie qu'Ollama tourne et que le modèle 'mistral' est installé."
        )

    # Mistral répond en texte brut depuis la correction de llm_prompt.py
    message = response["message"]["content"]

    # ── Étape 5 : détecter intention ajout panier ──

    # Évite les faux positifs quand Mistral mentionne "panier" dans sa réponse
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