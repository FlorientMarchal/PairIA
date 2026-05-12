# ia/rag.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from qdrant_client import QdrantClient
from llm_prompt import build_prompt, SYSTEM_PROMPT, _extraire_budget

# Connexion Qdrant locale
qdrant = QdrantClient(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_db"))

#  Liste de mots-clés panier
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


def _extraire_genre(history: list, question: str) -> str | None:
    """
    Détecte si l'utilisateur parle de chaussures homme ou femme.
    Analyse à la fois la question actuelle ET tout l'historique
    pour ne pas perdre l'info si elle a été donnée dans un échange précédent.
    """
    # On concatène question + tout l'historique pour chercher le genre
    # même s'il a été mentionné 3 messages avant
    texte_complet = question.lower()
    for msg in history:
        texte_complet += " " + msg["content"].lower()

    if any(kw in texte_complet for kw in ["femme", "féminin", "dame", "elle"]):
        return "Femme"
    if any(kw in texte_complet for kw in ["homme", "masculin", "monsieur", "il"]):
        return "Homme"
    return None


def get_response(question: str, product_id: int = None, history: list = None) -> dict:

    if history is None:
        history = []

    # ── Étape 1 : vectoriser la question ──

    # Si Ollama est éteint, message clair au lieu d'un crash 500
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
    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=5,
        score_threshold=0.65
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

    # Retour d'un message clair si aucun produit ne passe le seuil de similarité
    if not produits_trouves:
        return {
            "message":    "Je n'ai trouvé aucun produit correspondant à votre recherche. Pouvez-vous reformuler ou préciser votre demande ?",
            "products":   [],
            "action":     None,
            "product_id": None,
            "quantity":   None
        }

    # Filtre en Python, Mistral ne voit que les produits dans le budget
    budget = _extraire_budget(question)
    if budget:
        produits_filtres = [p for p in produits_trouves if p["price"] <= budget]
        if produits_filtres:
            # Des produits passent le filtre → on remplace la liste complète
            produits_trouves = produits_filtres
     

    # Filtre du genre côté Python
    genre = _extraire_genre(history, question)
    if genre:
        produits_filtres_genre = [
            p for p in produits_trouves
            if genre.lower() in p.get("categorie", "").lower()
            or genre.lower() in p.get("marque", "").lower()
        ]
        # On filtre seulement si des résultats passent
        # sinon on garde tous les produits pour ne pas retourner une liste vide
        if produits_filtres_genre:
            produits_trouves = produits_filtres_genre

    # Nombre de produits à afficher selon l'avancement de la conversation
    nb_produits = _nb_produits_from_history(history)

    # ── Étape 3 : construire le prompt ──
    prompt = build_prompt(
        question=question,
        produits=produits_trouves,
        product_id=product_id,
        genre=genre
    )

    # ── Étape 4 : construire les messages avec historique ──
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Injection des échanges précédents (max 10 = 5 échanges user/assistant)
    MAX_HISTORY = 10
    for msg in history[-MAX_HISTORY:]:
        messages.append({
            "role":    msg["role"],
            "content": msg["content"]
        })

    # La question actuelle enrichie avec les produits vient toujours en dernier
    messages.append({"role": "user", "content": prompt})

    # ── Appel Mistral ──

    # ✅ num_predict=300 : limite la longueur de réponse pour aller plus vite
    # Protège aussi contre les timeouts ou erreurs de génération
    try:
        response = ollama.chat(
        model="mistral",
        messages=messages,
        options={
            "num_ctx": 2048,
            "num_predict": 500,
            "num_threads": 8,
            "temperature": 0.7
            }
        )
    except Exception:
        raise RuntimeError(
            "Erreur lors de la génération Mistral. "
            "Vérifie qu'Ollama tourne et que le modèle 'mistral' est installé."
        )

    message = response["message"]["content"]

    # ── Étape 5 : détecter intention ajout panier ──

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

def get_response_stream(question: str, product_id: int = None, history: list = None):
    if history is None:
        history = []

    embed_response = ollama.embeddings(model="nomic-embed-text", prompt=question)
    question_vector = embed_response["embedding"]

    results = qdrant.query_points(
        collection_name="produits",
        query=question_vector,
        limit=5
    ).points

    produits_trouves = []
    for r in results:
        tailles_raw  = r.payload.get("tailles",  "")
        couleurs_raw = r.payload.get("couleurs", "")
        tailles  = [t.strip() for t in tailles_raw.split(",") if t.strip()] if tailles_raw else []
        couleurs = [c.strip() for c in couleurs_raw.split(",") if c.strip()] if couleurs_raw else []
        produits_trouves.append({
            "id":        r.id,
            "name":      r.payload.get("nom", ""),
            "price":     r.payload.get("prix", 0),
            "emoji":     "👟",
            "categorie": r.payload.get("categorie", ""),
            "marque":    r.payload.get("marque", ""),
            "url_image": r.payload.get("url_image", ""),
            "description": r.payload.get("description", ""),
            "tailles":   tailles,
            "couleurs":  couleurs,
        })

    nb_produits = _nb_produits_from_history(history)
    prompt = build_prompt(question=question, produits=produits_trouves, product_id=product_id)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    action            = None
    product_id_action = None
    quantity          = None
    if _user_wants_cart(question) and produits_trouves:
        action            = "add_to_cart"
        product_id_action = produits_trouves[0]["id"]
        quantity          = 1

    metadata = {
        "products":   produits_trouves[:nb_produits],
        "action":     action,
        "product_id": product_id_action,
        "quantity":   quantity
    }

    stream = ollama.chat(
        model="mistral",
        messages=messages,
        stream=True,
        options={"num_ctx": 2048, "num_predict": 150, "num_threads": 8, "temperature": 0.7}
    )

    yield metadata
    for chunk in stream:
        yield chunk["message"]["content"]