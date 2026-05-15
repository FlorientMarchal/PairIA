# ia/rag.py
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from database import qdrant
from llm_prompt import build_prompt, SYSTEM_PROMPT, _extraire_budget
from image_search import model, rechercher_produits_similaires
from PIL import Image
from db_mysql import fetch_all

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
    texte_complet = question.lower()
    for msg in history:
        if msg["role"] == "user":
            texte_complet += " " + msg["content"].lower()

    if any(kw in texte_complet for kw in ["pour femme", "chaussures femme", "féminin", "pour dame", "pour ma femme", "pour elle"]):
        return "Femme"
    if any(kw in texte_complet for kw in ["pour homme", "chaussures homme", "masculin", "pour monsieur", "pour mon mari", "pour lui"]):
        return "Homme"
    return None


def _produits_mentionnes(texte: str, produits: list) -> list:
    texte_lower = texte.lower()
    mentionnes = []
    for p in produits:
        nom = p["name"].lower()
        mots = [m for m in nom.split() if len(m) > 3]
        nom_trouve = nom in texte_lower or (
            len(mots) >= 2 and all(m in texte_lower for m in mots)
        )
        if nom_trouve:
            mentionnes.append(p)

    print(f"[PRODUITS] texte Mistral : {texte[:100]}")
    print(f"[PRODUITS] mentionnés : {[p['name'] for p in mentionnes]}")

    return mentionnes if mentionnes else [produits[0]]


# ── Chargement dynamique des marques et catégories depuis MySQL ──
def _charger_valeurs_db() -> dict:
    try:
        marques = [
            r["marque"].lower()
            for r in fetch_all("SELECT DISTINCT marque FROM articles WHERE marque IS NOT NULL")
        ]
        categories_raw = [
            r["categorie"]
            for r in fetch_all("SELECT DISTINCT categorie FROM articles WHERE categorie IS NOT NULL")
        ]

        # Couleurs distinctes depuis le champ texte séparé par virgules
        couleurs_raw = set()
        for r in fetch_all("SELECT DISTINCT couleur FROM size_color WHERE couleur IS NOT NULL"):
            c = r["couleur"].strip()
            if c:
                couleurs_raw.add(c)

        # Mapping catégorie : synonymes → valeur exacte DB
        # Généré automatiquement : chaque catégorie génère ses propres synonymes
        categories_map = {}
        for cat in categories_raw:
            cat_lower = cat.lower()
            # La catégorie elle-même
            categories_map[cat_lower] = cat
            # Mots individuels significatifs (>3 chars)
            for mot in cat_lower.split():
                if len(mot) > 3:
                    categories_map[mot] = cat

        # Synonymes manuels pour les cas ambigus — à compléter si besoin
        synonymes_categories = {
            "basket":        "Baskets sport",
            "baskets":       "Baskets sport",
            "sport":         "Baskets sport",
            "lifestyle":     "Baskets lifestyle",
            "casual":        "Baskets lifestyle",
            "ville":         "Baskets lifestyle",
            "running":       "Running",
            "course":        "Running",
            "courir":        "Running",
            "trail":         "Running",
            "rando":         "Randonnée",
            "randonnée":     "Randonnée",
            "montagne":      "Randonnée",
            "imperméable":   "Imperméables",
            "imperméables":  "Imperméables",
            "waterproof":    "Imperméables",
            "pluie":         "Imperméables",
            "botte":         "Imperméables",
            "bottine":       "Bottines",
            "talon":         "Talons",
            "talons":        "Talons",
            "sandale":       "Sandales",
            "sandales":      "Sandales",
            "mocassin":      "Mocassins",
            "mocassins":     "Mocassins",
            "training":      "Training",
            "fitness":       "Training",
            "salle":         "Training",
            "sécurité":      "Sécurité",
            "travail":       "Sécurité",
            "vegan":         "Vegan",
            "écologique":    "Vegan",
            "danse":         "Danse",
            "indoor":        "Indoor",
            "marche":        "Marche",
            "slip":          "Slip-on",
            "sabot":         "Sabots",
            "espadrille":    "Espadrilles",
            "minimaliste":   "Minimalistes",
            "montante":      "Montantes légères",
        }
        # Les synonymes manuels écrasent la génération automatique
        categories_map.update({k: v for k, v in synonymes_categories.items() if v in categories_raw})

        # Mapping couleur : synonymes → valeur exacte DB
        couleurs_map = {}
        for couleur in couleurs_raw:
            couleurs_map[couleur.lower()] = couleur

        # Synonymes couleurs — regroupe les variantes vers la couleur DB la plus proche
        synonymes_couleurs = {
            # Noir
            "noir":              "Noir",
            "noire":             "Noir",
            "noirs":             "Noir",
            "noires":            "Noir",
            "sombre":            "Noir",

            # Blanc
            "blanc":             "Blanc",
            "blanche":           "Blanc",
            "blancs":            "Blanc",
            "blanches":          "Blanc",
            "blanc cassé":       "Blanc cassé",
            "cassé":             "Blanc cassé",
            "ivoire":            "Blanc cassé",
            "crème":             "Crème",
            "creme":             "Crème",
            "écru":              "Crème",

            # Beige / Naturel
            "beige":             "Beige",
            "beige naturel":     "Beige naturel",
            "naturel":           "Beige naturel",
            "sable":             "Beige naturel",
            "nude":              "Beige naturel",

            # Bleu
            "bleu":              "Bleu",
            "bleue":             "Bleu",
            "bleu marine":       "Bleu marine",
            "marine":            "Bleu marine",
            "bleu foncé":        "Bleu marine",
            "bleu nuit":         "Bleu nuit",
            "nuit":              "Bleu nuit",
            "bleu ciel":         "Bleu ciel",
            "ciel":              "Bleu ciel",
            "bleu clair":        "Bleu ciel",
            "bleu électrique":   "Bleu électrique",
            "électrique":        "Bleu électrique",
            "bleu vif":          "Bleu électrique",
            "bleu indigo":       "Bleu indigo",
            "indigo":            "Bleu indigo",
            "bleu océan":        "Bleu océan",
            "océan":             "Bleu océan",
            "bleu pétrole":      "Bleu pétrole",
            "pétrole":           "Bleu pétrole",
            "bleu ardoise":      "Bleu ardoise",
            "ardoise":           "Bleu ardoise",
            "bleu gris":         "Bleu gris",

            # Gris
            "gris":              "Gris",
            "grise":             "Gris",
            "gris clair":        "Gris",
            "gris anthracite":   "Gris anthracite",
            "anthracite":        "Gris anthracite",
            "gris foncé":        "Gris anthracite",
            "charbon":           "Charbon",
            "gris charbon":      "Charbon",
            "gris très foncé":   "Charbon",

            # Rouge
            "rouge":             "rouge",
            "rouge vif":         "rouge",
            "colorblock":        "rouge",

            # Bordeaux / Rose / Corail
            "bordeaux":          "Bordeaux",
            "bordeau":           "Bordeaux",
            "rouge sombre":      "Bordeaux",
            "rouge foncé":       "Bordeaux",
            "rose":              "Rose",
            "rose clair":        "Rose",
            "corail":            "Corail",
            "orange clair":      "Corail",
            "saumon":            "Corail",

            # Orange
            "orange":            "Orange",
            "orange vif":        "Orange",

            # Marron / Camel / Cognac
            "marron":            "Marron",
            "brun":              "Marron",
            "chocolat":          "Marron",
            "camel":             "Camel",
            "beige foncé":       "Camel",
            "cognac":            "Cognac",
            "miel":              "Cognac",
            "cuir":              "Cognac",
            "terracotta":        "Terracotta",
            "terre":             "Terracotta",
            "rouille":           "Terracotta",

            # Vert
            "vert":              "Vert",
            "verte":             "Vert",
            "vert kaki":         "Kaki",
            "kaki":              "Kaki",
            "militaire":         "Kaki",
            "olive":             "Kaki",
            "vert militaire":    "Kaki",
            "vert foncé":        "Vert hunter",
            "hunter":            "Vert hunter",
            "vert chasseur":     "Vert hunter",
            "vert bouteille":    "Vert hunter",
            "vert forêt":        "Vert hunter",
            "vert menthe":       "Vert menthe",
            "menthe":            "Vert menthe",
            "vert clair":        "Vert menthe",
            "vert pastel":       "Vert menthe",
            "aqua":              "Vert menthe",

            # Jaune / Violet / Argent / Champagne
            "jaune":             "Jaune",
            "jaune vif":         "Jaune",
            "violet":            "Violet",
            "mauve":             "Violet",
            "purple":            "Violet",
            "lilas":             "Violet",
            "argent":            "Argent",
            "argenté":           "Argent",
            "silver":            "Argent",
            "champagne":         "Champagne",
            "doré":              "Champagne",
            "or":                "Champagne",
            "lavande":           "Violet",
            "pêche":             "Corail",
        }
        # Filtre : garde uniquement les synonymes qui pointent vers une couleur existante en DB
        couleurs_map.update(synonymes_couleurs)


        print(f"[DB] {len(marques)} marques, {len(categories_raw)} catégories, {len(couleurs_raw)} couleurs chargées")
        genres_ids = {}
        for genre in ["Homme", "Femme", "Mixte"]:
            ids = [
                r["id_shoes"]
                for r in fetch_all(f"SELECT id_shoes FROM articles WHERE genre = '{genre}'")
            ]
            genres_ids[genre] = set(ids)
            print(f"[DB] {len(ids)} articles genre {genre}")

        return {
            "marques":        marques,
            "categories":     categories_raw,
            "categories_map": categories_map,
            "couleurs_map":   couleurs_map,
            "genres_ids":     genres_ids,
        }
    except Exception as e:
        print(f"[DB] Erreur chargement valeurs : {e}")
        return {"marques": [], "categories": [], "categories_map": {}, "couleurs_map": {}}

_DB_VALEURS = _charger_valeurs_db()

# ── Extraction de tous les filtres ──
def _extraire_filtres(question: str, history: list) -> dict:
    texte_question = question.lower()

    historique_user = [
        msg["content"].lower()
        for msg in history
        if msg["role"] == "user"
    ]

    def _chercher_dans(texte: str, valeurs: list) -> str | None:
        for v in valeurs:
            if v in texte:
                return v
        return None

    def _chercher_avec_fallback(valeurs: list) -> str | None:
        trouve = _chercher_dans(texte_question, valeurs)
        if trouve:
            return trouve
        for msg in reversed(historique_user):
            trouve = _chercher_dans(msg, valeurs)
            if trouve:
                return trouve
        return None

    def _chercher_categorie(texte: str) -> str | None:
        for synonyme, cat in _DB_VALEURS["categories_map"].items():
            if synonyme in texte:
                return cat
        return None

    def _chercher_couleur(texte: str) -> str | None:
        for synonyme, couleur in _DB_VALEURS["couleurs_map"].items():
            if synonyme in texte:
                return couleur
        return None

    def _chercher_pointure(texte: str) -> str | None:
        # Exclut les nombres qui font partie d'un prix (suivis de € ou précédés de contexte budget)
        # Cherche une pointure isolée, pas précédée/suivie de € ou de contexte monétaire
        matches = re.finditer(r"\b(3[6-9]|4[0-9]|50)\b", texte)
        for match in matches:
            start = match.start()
            end = match.end()
            # Vérifie que ce n'est pas un prix : pas de € après, pas "moins de/max/budget" avant
            apres = texte[end:end+2].strip()
            avant = texte[max(0, start-15):start].strip()
            mots_budget = ["€", "euro", "moins de", "max", "budget", "sous", "jusqu"]
            if apres.startswith("€"):
                continue
            if any(kw in avant for kw in mots_budget):
                continue
            return match.group(1)
        return None

    filtres = {}

    # Budget — question actuelle uniquement, pas de fallback
    budget = _extraire_budget(question)
    if not budget:
        for msg in reversed(historique_user):
            budget = _extraire_budget(msg)
            if budget:
                break
    if budget:
        filtres["budget"] = budget

    # Genre — historique user uniquement
    genre = _extraire_genre(history, question)
    if genre:
        filtres["genre"] = genre

    # Pointure — question actuelle en priorité, fallback historique
    pointure = _chercher_pointure(texte_question)
    if not pointure:
        for msg in reversed(historique_user):
            pointure = _chercher_pointure(msg)
            if pointure:
                break
    if pointure:
        filtres["pointure"] = pointure

    # Couleur — question actuelle en priorité, fallback historique
    couleur = _chercher_couleur(texte_question)
    if not couleur:
        for msg in reversed(historique_user):
            couleur = _chercher_couleur(msg)
            if couleur:
                break
    if couleur:
        filtres["couleur"] = couleur

    # Marque — question actuelle en priorité, fallback historique
    marque = _chercher_avec_fallback(_DB_VALEURS["marques"])
    if marque:
        filtres["marque"] = marque

    # Catégorie — question actuelle en priorité, fallback historique
    categorie = _chercher_categorie(texte_question)
    if not categorie:
        for msg in reversed(historique_user):
            categorie = _chercher_categorie(msg)
            if categorie:
                break
    if categorie:
        filtres["categorie"] = categorie

    print(f"[FILTRES] détectés : {filtres}")
    return filtres

# ── Application de tous les filtres avec messages cohérents ──
def _appliquer_filtres(produits: list, question: str, history: list) -> tuple[list, str]:
    filtres = _extraire_filtres(question, history)

    if not filtres:
        return produits, ""

    produits_courants = produits
    filtres_appliques = []
    filtres_echoues   = []

    # Budget
    if "budget" in filtres:
        budget = filtres["budget"]
        f = [p for p in produits_courants if p["price"] <= budget]
        if f:
            produits_courants = f
            filtres_appliques.append(f"sous {budget}€")
        else:
            filtres_echoues.append(f"sous {budget}€")

    # Genre
    if "genre" in filtres:
        genre = filtres["genre"]
        ids_genre = _DB_VALEURS["genres_ids"].get(genre, set())
        ids_mixte = _DB_VALEURS["genres_ids"].get("Mixte", set())
        f = [
            p for p in produits_courants
            if p["id"] in ids_genre or p["id"] in ids_mixte
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"pour {genre}")
        else:
            filtres_echoues.append(f"pour {genre}")

    # Catégorie
    if "categorie" in filtres:
        cat = filtres["categorie"]
        f = [
            p for p in produits_courants
            if cat.lower() in p.get("categorie", "").lower()
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"catégorie {cat}")
        else:
            filtres_echoues.append(f"catégorie {cat}")

    # Marque
    if "marque" in filtres:
        marque = filtres["marque"]
        f = [
            p for p in produits_courants
            if marque.lower() in p.get("marque", "").lower()
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"marque {marque}")
        else:
            filtres_echoues.append(f"marque {marque}")
    if "genre" in filtres:
        genre = filtres["genre"]
        ids_genre = _DB_VALEURS["genres_ids"].get(genre, set())
        ids_mixte = _DB_VALEURS["genres_ids"].get("Mixte", set())
        f = [
            p for p in produits_courants
            if p["id"] in ids_genre or p["id"] in ids_mixte
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"pour {genre}")
        else:
            filtres_echoues.append(f"pour {genre}")
            
    # Couleur
    if "couleur" in filtres:
        couleur = filtres["couleur"]
        f = [
            p for p in produits_courants
            if any(couleur.lower() in c.lower() for c in p.get("couleurs", []))
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"couleur {couleur}")
        else:
            filtres_echoues.append(f"couleur {couleur}")

    # Pointure
    if "pointure" in filtres:
        pointure = filtres["pointure"]
        f = [
            p for p in produits_courants
            if pointure in p.get("tailles", [])
            or pointure in p.get("tailles", "")
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"taille {pointure}")
        else:
            filtres_echoues.append(f"taille {pointure}")

    # Résultat
    if filtres_echoues:
        criteres_ok = " + ".join(filtres_appliques) if filtres_appliques else ""
        criteres_ko = " + ".join(filtres_echoues)
        contexte = (
            f"ATTENTION : aucun produit trouvé pour les critères [{criteres_ko}]"
            + (f" (avec {criteres_ok})" if criteres_ok else "")
            + ". Ne propose AUCUN produit. "
            + "Explique clairement ce qui n'est pas disponible et demande "
            + "si l'utilisateur veut élargir sa recherche."
        )
        return [], contexte

    contexte = ""
    if filtres_appliques:
        contexte = f"Produits filtrés ({' + '.join(filtres_appliques)}) :"

    return produits_courants, contexte


def get_response(question: str, product_id: int = None, history: list = None, image_path: str = None) -> dict:
    if history is None:
        history = []

    # REMPLACE l'étape 1 (vectorisation) par ceci :
    try:
        is_image_search = False
        if image_path and os.path.exists(image_path):
            is_image_search = True
            image_vec = model.encode(Image.open(image_path))

            if question and _user_wants_cart(question):
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
        collection_name="produits_image",
        query=question_vector,
        limit=5,
        score_threshold=0.10
    ).points

    produits_trouves = []
    for r in results:
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

    if not produits_trouves:
        return {
            "message":    "Je n'ai trouvé aucun produit correspondant à votre recherche. Pouvez-vous reformuler ou préciser votre demande ?",
            "products":   [],
            "action":     None,
            "product_id": None,
            "quantity":   None
        }

    # Filtres généralisés
    produits_trouves, contexte_filtres = _appliquer_filtres(produits_trouves, question, history)

    if not produits_trouves:
        return {
            "message":    contexte_filtres,
            "products":   [],
            "action":     None,
            "product_id": None,
            "quantity":   None
        }

    genre = _extraire_genre(history, question)
    nb_produits = _nb_produits_from_history(history)

    prompt = build_prompt(
        question=question,
        produits=produits_trouves,
        product_id=product_id,
        genre=genre,
        is_image_search=False,
        contexte_filtres=contexte_filtres,
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    MAX_HISTORY = 10
    for msg in history[-MAX_HISTORY:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

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
                contexte_produit = ""
                for msg in reversed(history):
                    if msg["role"] == "user" and "Produits suggérés" in msg["content"]:
                        match = re.search(r"Produits suggérés : ([^,\(]+)", msg["content"])
                        if match:
                            contexte_produit = match.group(1).strip()
                        break

                question_enrichie = f"{contexte_produit} {question}".strip() if contexte_produit else question
                print(f"[RAG] question enrichie pour CLIP : {question_enrichie!r}")

                text_vec = model.encode(question_enrichie)
                question_vector = ((image_vec * 0.5) + (text_vec * 0.5)).tolist()
            else:
                question_vector = image_vector
        else:
            text_to_encode = question if (question and question.strip()) else "chaussures"
            # Enrichit avec la catégorie détectée pour améliorer la recherche Qdrant
            filtres_actuels = _extraire_filtres(question, history)
            if filtres_actuels.get("categorie"):
                text_to_encode = f"{filtres_actuels['categorie']} {text_to_encode}"
                print(f"[RAG] question enrichie pour Qdrant : {text_to_encode!r}")
            
            question_vector = model.encode(text_to_encode).tolist()

    except Exception as e:
        print(f"Erreur vectorisation : {e}")
        question_vector = [0] * 512

    # 2. Recherche Qdrant
    try:
        filtres_preview = _extraire_filtres(question, history)
        limit_qdrant = 15 if filtres_preview.get("categorie") else 5
        results_qdrant = qdrant.query_points(
            collection_name="produits_image",
            query=question_vector,
            limit=limit_qdrant,
            score_threshold=0.10
        ).points
        print("[NB RESULTATS]", len(results_qdrant))
        if results_qdrant:
            print("[PAYLOAD EXEMPLE]", dict(results_qdrant[0].payload))
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
    if produits_trouves:
        print("[PAYLOAD COMPLET]", dict(results_qdrant[0].payload))
    # 4. Filtres généralisés
    produits_trouves, contexte_filtres = _appliquer_filtres(produits_trouves, question, history)

    # Si aucun produit après filtres → réponse directe sans produits
    if not produits_trouves:
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": contexte_filtres + f"\nQuestion : {question}"})

        texte_complet = ""
        try:
            stream = ollama.chat(
                model="mistral", messages=messages, stream=True,
                options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.7}
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                texte_complet += token
                yield token
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"

        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1}
        return

    # 5. Préparation du prompt
    genre = _extraire_genre(history, question)
    nb_produits = _nb_produits_from_history(history)

    description_visuelle = ""
    if is_image_search and produits_trouves:
        top_p = produits_trouves[0]
        description_visuelle = f"[L'utilisateur a envoyé une photo de : {top_p['name']}] "

    question_complete = f"{description_visuelle}{question if question else ''}"

    prompt = build_prompt(
        question=question_complete,
        produits=produits_trouves,
        product_id=product_id,
        genre=genre,
        is_image_search=is_image_search,
        contexte_filtres=contexte_filtres,
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    action = None
    if _user_wants_cart(question) and produits_trouves:
        action = "add_to_cart"

    # Yield metadata vide au début
    yield {
        "products": [],
        "action": None,
        "product_id": None,
        "quantity": 1
    }

    # Streaming Mistral
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

    # Filtre les produits selon ce que Mistral a mentionné
    produits_affiches = _produits_mentionnes(texte_complet, produits_trouves[:3])

    action = None
    if _user_wants_cart(question) and produits_affiches:
        action = "add_to_cart"

    yield {
        "type": "products_final",
        "products": produits_affiches,
        "action": action,
        "product_id": produits_affiches[0]["id"] if produits_affiches else None,
        "quantity": 1
    }
