# ia/rag.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from database import qdrant
from llm_prompt import build_prompt, SYSTEM_PROMPT, _extraire_budget
from image_search import model, rechercher_produits_similaires
from PIL import Image

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

def _produits_mentionnes(texte: str, produits: list) -> list:
    texte_lower = texte.lower()
    mentionnes = []
    for p in produits:
        nom = p["name"].lower()
        # Cherche le nom complet OU les mots significatifs du nom (>3 chars)
        mots = [m for m in nom.split() if len(m) > 3]
        nom_trouve = nom in texte_lower or (
            len(mots) >= 2 and all(m in texte_lower for m in mots)
        )
        if nom_trouve:
            mentionnes.append(p)
    
    print(f"[PRODUITS] texte Mistral : {texte[:100]}")
    print(f"[PRODUITS] mentionnés : {[p['name'] for p in mentionnes]}")
    
    return mentionnes if mentionnes else [produits[0]]

def get_response(question: str, product_id: int = None, history: list = None, image_path: str = None) -> dict:
    if history is None:
        history = []

    # REMPLACE l'étape 1 (vectorisation) par ceci :
        try:
            is_image_search = False
            if image_path and os.path.exists(image_path):
                is_image_search = True
                image_vec = model.encode(Image.open(image_path))
                if question and _user_wants_cart(question) and produits_trouves:
                    # Fusion Image (70%) + Texte (30%)
                    question_vector = ((image_vec * 0.7) + (model.encode(question) * 0.3)).tolist()
                else:
                    question_vector = image_vec.tolist()
            else:
                question_vector = model.encode(question).tolist()
        except Exception as e:
            print(f"Erreur CLIP : {e}")
            question_vector = [0] * 512

    # MODIFIE l'étape 2 (La collection Qdrant) :
    results = qdrant.query_points(
        collection_name="produits_image", # Vérifie bien le nom de ta collection CLIP
        query=question_vector,
        limit=5,
        score_threshold=0.10 # Seuil plus bas pour CLIP (les distances sont différentes)
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
        genre=genre,
        is_image_search=is_image_search
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
            "num_predict": 150,
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

def get_response_stream(question: str, product_id: int = None, history: list = None, image_path: str = None, image_vector: list = None):
    if history is None:
        history = []
    # ── DEBUG ──
    print(f"\n{'='*50}")
    print(f"[RAG] question    : {question!r}")
    print(f"[RAG] image_path  : {image_path}")
    print(f"[RAG] history     : {len(history)} messages")
    for i, msg in enumerate(history):
        print(f"  [{i}] {msg['role']}: {msg['content'][:80]}...")
    print(f"{'='*50}\n")
    # 1. Vectorisation (CLIP)
    try:
        is_image_search = False

        if image_path and os.path.exists(image_path):
            # Tour image direct
            is_image_search = True
            image_vec = model.encode(Image.open(image_path))
            if question and question.strip():
                question_vector = ((image_vec * 0.7) + (model.encode(question) * 0.3)).tolist()
            else:
                question_vector = image_vec.tolist()
                
        elif image_vector:
            is_image_search = True
            import numpy as np
            image_vec = np.array(image_vector)

            if question and question.strip():
                # Enrichit la question avec le contexte du dernier produit mentionné
                # pour que CLIP encode quelque chose de plus précis
                contexte_produit = ""
                for msg in reversed(history):
                    if msg["role"] == "user" and "Produits suggérés" in msg["content"]:
                        # Extrait le premier produit mentionné dans l'historique
                        import re
                        match = re.search(r"Produits suggérés : ([^,\(]+)", msg["content"])
                        if match:
                            contexte_produit = match.group(1).strip()
                        break

                # Question enrichie : "basket Nike en noir" plutôt que juste "en noir"
                question_enrichie = f"{contexte_produit} {question}".strip() if contexte_produit else question
                print(f"[RAG] question enrichie pour CLIP : {question_enrichie!r}")

                text_vec = model.encode(question_enrichie)
                question_vector = ((image_vec * 0.5) + (text_vec * 0.5)).tolist()
            else:
                question_vector = image_vector
        else:
            # Tour texte pur
            text_to_encode = question if (question and question.strip()) else "chaussures"
            question_vector = model.encode(text_to_encode).tolist()

    except Exception as e:
        print(f"Erreur vectorisation : {e}")
        question_vector = [0] * 512

    # 2. Recherche Qdrant
    try:
        results_qdrant = qdrant.query_points(
            collection_name="produits_image",
            query=question_vector,
            limit=5,
            score_threshold=0.10
        ).points
    except Exception as e:
        print(f"Erreur Qdrant : {e}")
        results_qdrant = []

    # 3. Traitement des résultats
    produits_trouves = []
    for r in results_qdrant:
        tailles_raw = r.payload.get("tailles", "")
        couleurs_raw = r.payload.get("couleurs", "")
        produits_trouves.append({
            "id": r.id,
            "name": r.payload.get("nom", ""),
            "price": r.payload.get("prix", 0),
            "emoji": "👟",
            "categorie": r.payload.get("categorie", ""),
            "marque": r.payload.get("marque", ""),
            "url_image": r.payload.get("url_image", ""),
            "description": r.payload.get("description", ""),
            "tailles": [t.strip() for t in tailles_raw.split(",") if t.strip()] if tailles_raw else [],
            "couleurs": [c.strip() for c in couleurs_raw.split(",") if c.strip()] if couleurs_raw else [],
        })

    # 4. Préparation du prompt et métadonnées
    genre = _extraire_genre(history, question)
    nb_produits = _nb_produits_from_history(history)
    
    description_visuelle = ""
    if is_image_search and produits_trouves:
        # On prend le nom du premier produit trouvé pour donner un "contexte" à Mistral
        top_p = produits_trouves[0]
        description_visuelle = f"[L'utilisateur a envoyé une photo de : {top_p['name']}] "

    # On combine la description de l'image avec la question textuelle
    question_complete = f"{description_visuelle}{question if question else ''}"

    prompt = build_prompt(
        question=question_complete, 
        produits=produits_trouves, 
        product_id=product_id, 
        genre=genre, 
        is_image_search=is_image_search
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    # Détection panier
    action = None
    if _user_wants_cart(question) and produits_trouves:
        action = "add_to_cart"

   
    # Yield metadata VIDE au début (pas de produits encore)
    yield {
        "products": [],
        "action": None,
        "product_id": None,
        "quantity": 1
    }

    # Streaming Mistral — accumule le texte complet
    texte_complet = ""
    try:
        stream = ollama.chat(
            model="mistral",
            messages=messages,
            stream=True,
            options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.7}
        )
        for chunk in stream:
            token = chunk["message"]["content"]
            texte_complet += token
            yield token
    except Exception as e:
        yield f"Erreur Mistral : {str(e)}"
        return

    # Après streaming : filtre les produits selon ce que Mistral a mentionné
    produits_affiches = _produits_mentionnes(texte_complet, produits_trouves[:3])

    action = None
    if _user_wants_cart(question) and produits_affiches:
        action = "add_to_cart"

    # Yield final avec les vrais produits filtrés
    yield {
        "type": "products_final",
        "products": produits_affiches,
        "action": action,
        "product_id": produits_affiches[0]["id"],
        "quantity": 1
    }