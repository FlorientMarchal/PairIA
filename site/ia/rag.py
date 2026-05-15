# ia/rag.py
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from database import qdrant
from llm_prompt import build_prompt, SYSTEM_PROMPT, _extraire_budget
from image_search import model, rechercher_produits_similaires
from intention_classifier import classifier_intention
from PIL import Image
from db_mysql import fetch_all

# ── Liste de mots-clés panier (garde-fou en plus du classifier) ──
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


def _produits_depuis_historique(history: list) -> list:
    """
    Récupère les derniers produits affichés dans la conversation
    en cherchant les métadonnées stockées dans l'historique.
    Le frontend doit stocker les produits dans le message assistant :
    { role: "assistant", content: "...", products: [...] }
    """
    for msg in reversed(history):
        if msg["role"] == "assistant" and "products" in msg:
            produits = msg["products"]
            if produits:
                print(f"[HISTORIQUE] {len(produits)} produit(s) récupéré(s) depuis l'historique")
                return produits
    print("[HISTORIQUE] Aucun produit trouvé dans l'historique")
    return []


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

        couleurs_raw = set()
        for r in fetch_all("SELECT DISTINCT couleur FROM size_color WHERE couleur IS NOT NULL"):
            c = r["couleur"].strip()
            if c:
                couleurs_raw.add(c)

        categories_map = {}
        for cat in categories_raw:
            cat_lower = cat.lower()
            categories_map[cat_lower] = cat
            for mot in cat_lower.split():
                if len(mot) > 3:
                    categories_map[mot] = cat

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
        categories_map.update({k: v for k, v in synonymes_categories.items() if v in categories_raw})

        couleurs_map = {}
        for couleur in couleurs_raw:
            couleurs_map[couleur.lower()] = couleur

        synonymes_couleurs = {
            "noir": "Noir", "noire": "Noir", "noirs": "Noir", "noires": "Noir", "sombre": "Noir",
            "blanc": "Blanc", "blanche": "Blanc", "blancs": "Blanc", "blanches": "Blanc",
            "blanc cassé": "Blanc cassé", "cassé": "Blanc cassé", "ivoire": "Blanc cassé",
            "crème": "Crème", "creme": "Crème", "écru": "Crème",
            "beige": "Beige", "beige naturel": "Beige naturel", "naturel": "Beige naturel",
            "sable": "Beige naturel", "nude": "Beige naturel",
            "bleu": "Bleu", "bleue": "Bleu", "bleu marine": "Bleu marine", "marine": "Bleu marine",
            "bleu foncé": "Bleu marine", "bleu nuit": "Bleu nuit", "nuit": "Bleu nuit",
            "bleu ciel": "Bleu ciel", "ciel": "Bleu ciel", "bleu clair": "Bleu ciel",
            "bleu électrique": "Bleu électrique", "électrique": "Bleu électrique", "bleu vif": "Bleu électrique",
            "bleu indigo": "Bleu indigo", "indigo": "Bleu indigo",
            "bleu océan": "Bleu océan", "océan": "Bleu océan",
            "bleu pétrole": "Bleu pétrole", "pétrole": "Bleu pétrole",
            "bleu ardoise": "Bleu ardoise", "ardoise": "Bleu ardoise", "bleu gris": "Bleu gris",
            "gris": "Gris", "grise": "Gris", "gris clair": "Gris",
            "gris anthracite": "Gris anthracite", "anthracite": "Gris anthracite", "gris foncé": "Gris anthracite",
            "charbon": "Charbon", "gris charbon": "Charbon", "gris très foncé": "Charbon",
            "rouge": "rouge", "rouge vif": "rouge", "colorblock": "rouge",
            "bordeaux": "Bordeaux", "bordeau": "Bordeaux", "rouge sombre": "Bordeaux", "rouge foncé": "Bordeaux",
            "rose": "Rose", "rose clair": "Rose", "corail": "Corail", "orange clair": "Corail", "saumon": "Corail",
            "orange": "Orange", "orange vif": "Orange",
            "marron": "Marron", "brun": "Marron", "chocolat": "Marron",
            "camel": "Camel", "beige foncé": "Camel",
            "cognac": "Cognac", "miel": "Cognac", "cuir": "Cognac",
            "terracotta": "Terracotta", "terre": "Terracotta", "rouille": "Terracotta",
            "vert": "Vert", "verte": "Vert",
            "vert kaki": "Kaki", "kaki": "Kaki", "militaire": "Kaki", "olive": "Kaki", "vert militaire": "Kaki",
            "vert foncé": "Vert hunter", "hunter": "Vert hunter", "vert chasseur": "Vert hunter",
            "vert bouteille": "Vert hunter", "vert forêt": "Vert hunter",
            "vert menthe": "Vert menthe", "menthe": "Vert menthe", "vert clair": "Vert menthe",
            "vert pastel": "Vert menthe", "aqua": "Vert menthe",
            "jaune": "Jaune", "jaune vif": "Jaune",
            "violet": "Violet", "mauve": "Violet", "purple": "Violet", "lilas": "Violet", "lavande": "Violet",
            "argent": "Argent", "argenté": "Argent", "silver": "Argent",
            "champagne": "Champagne", "doré": "Champagne", "or": "Champagne",
            "pêche": "Corail",
        }
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
        return {"marques": [], "categories": [], "categories_map": {}, "couleurs_map": {}, "genres_ids": {}}

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
        matches = re.finditer(r"\b(3[6-9]|4[0-9]|50)\b", texte)
        for match in matches:
            start = match.start()
            end = match.end()
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

    budget = _extraire_budget(question)
    if not budget:
        for msg in reversed(historique_user):
            budget = _extraire_budget(msg)
            if budget:
                break
    if budget:
        filtres["budget"] = budget

    genre = _extraire_genre(history, question)
    if genre:
        filtres["genre"] = genre

    pointure = _chercher_pointure(texte_question)
    if not pointure:
        for msg in reversed(historique_user):
            pointure = _chercher_pointure(msg)
            if pointure:
                break
    if pointure:
        filtres["pointure"] = pointure

    couleur = _chercher_couleur(texte_question)
    if not couleur:
        for msg in reversed(historique_user):
            couleur = _chercher_couleur(msg)
            if couleur:
                break
    if couleur:
        filtres["couleur"] = couleur

    marque = _chercher_avec_fallback(_DB_VALEURS["marques"])
    if marque:
        filtres["marque"] = marque

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


# ── Application de tous les filtres ──
def _appliquer_filtres(produits: list, question: str, history: list) -> tuple[list, str]:
    filtres = _extraire_filtres(question, history)

    if not filtres:
        return produits, ""

    produits_courants = produits
    filtres_appliques = []
    filtres_echoues   = []

    if "budget" in filtres:
        budget = filtres["budget"]
        f = [p for p in produits_courants if p["price"] <= budget]
        if f:
            produits_courants = f
            filtres_appliques.append(f"sous {budget}€")
        else:
            filtres_echoues.append(f"sous {budget}€")

    if "genre" in filtres:
        genre = filtres["genre"]
        ids_genre = _DB_VALEURS["genres_ids"].get(genre, set())
        ids_mixte = _DB_VALEURS["genres_ids"].get("Mixte", set())
        f = [p for p in produits_courants if p["id"] in ids_genre or p["id"] in ids_mixte]
        if f:
            produits_courants = f
            filtres_appliques.append(f"pour {genre}")
        else:
            filtres_echoues.append(f"pour {genre}")

    if "categorie" in filtres:
        cat = filtres["categorie"]
        f = [p for p in produits_courants if cat.lower() in p.get("categorie", "").lower()]
        if f:
            produits_courants = f
            filtres_appliques.append(f"catégorie {cat}")
        else:
            filtres_echoues.append(f"catégorie {cat}")

    if "marque" in filtres:
        marque = filtres["marque"]
        f = [p for p in produits_courants if marque.lower() in p.get("marque", "").lower()]
        if f:
            produits_courants = f
            filtres_appliques.append(f"marque {marque}")
        else:
            filtres_echoues.append(f"marque {marque}")

    if "couleur" in filtres:
        couleur = filtres["couleur"]
        f = [p for p in produits_courants if any(couleur.lower() in c.lower() for c in p.get("couleurs", []))]
        if f:
            produits_courants = f
            filtres_appliques.append(f"couleur {couleur}")
        else:
            filtres_echoues.append(f"couleur {couleur}")

    if "pointure" in filtres:
        pointure = filtres["pointure"]
        f = [
            p for p in produits_courants
            if pointure in p.get("tailles", []) or pointure in p.get("tailles", "")
        ]
        if f:
            produits_courants = f
            filtres_appliques.append(f"taille {pointure}")
        else:
            filtres_echoues.append(f"taille {pointure}")

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


# ── Recherche Qdrant + construction des produits ──
def _recherche_qdrant(question_vector: list, question: str, history: list) -> tuple[list, str]:
    """
    Lance la recherche Qdrant, construit la liste produits et applique les filtres.
    Retourne (produits_filtres, contexte_filtres).
    """
    try:
        filtres_preview = _extraire_filtres(question, history)
        limit_qdrant = 15 if filtres_preview.get("categorie") else 5
        results_qdrant = qdrant.query_points(
            collection_name="produits_image",
            query=question_vector,
            limit=limit_qdrant,
            score_threshold=0.10
        ).points
        print(f"[QDRANT] {len(results_qdrant)} résultats")
        if results_qdrant:
            print("[PAYLOAD EXEMPLE]", dict(results_qdrant[0].payload))
    except Exception as e:
        print(f"Erreur Qdrant : {e}")
        results_qdrant = []

    produits_trouves = []
    for r in results_qdrant:
        tailles_raw  = r.payload.get("tailles",  "")
        couleurs_raw = r.payload.get("couleurs", "")
        produits_trouves.append({
            "id":          r.id,
            "name":        r.payload.get("nom",         ""),
            "price":       r.payload.get("prix",        0),
            "emoji":       "👟",
            "categorie":   r.payload.get("categorie",   ""),
            "marque":      r.payload.get("marque",      ""),
            "url_image":   r.payload.get("url_image",   ""),
            "description": r.payload.get("description", ""),
            "tailles":     [t.strip() for t in tailles_raw.split(",")  if t.strip()] if tailles_raw  else [],
            "couleurs":    [c.strip() for c in couleurs_raw.split(",") if c.strip()] if couleurs_raw else [],
        })

    return _appliquer_filtres(produits_trouves, question, history)


# ── Vectorisation de la question ──
def _vectoriser(question: str, history: list, image_path: str = None, image_vector: list = None) -> tuple[list, bool]:
    """
    Retourne (vecteur, is_image_search).
    """
    try:
        if image_path and os.path.exists(image_path):
            image_vec = model.encode(Image.open(image_path))
            if question and question.strip():
                vec = ((image_vec * 0.7) + (model.encode(question) * 0.3)).tolist()
            else:
                vec = image_vec.tolist()
            return vec, True

        if image_vector:
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
                text_vec = model.encode(question_enrichie)
                vec = ((image_vec * 0.5) + (text_vec * 0.5)).tolist()
            else:
                vec = image_vector
            return vec, True

        text_to_encode = question if (question and question.strip()) else "chaussures"
        filtres_actuels = _extraire_filtres(question, history)
        if filtres_actuels.get("categorie"):
            text_to_encode = f"{filtres_actuels['categorie']} {text_to_encode}"
            print(f"[RAG] question enrichie pour Qdrant : {text_to_encode!r}")
        return model.encode(text_to_encode).tolist(), False

    except Exception as e:
        print(f"Erreur vectorisation : {e}")
        return [0] * 512, False


# ═══════════════════════════════════════════════════════════════
# STREAMING PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def get_response_stream(
    question: str,
    product_id: int = None,
    history: list = None,
    image_path: str = None,
    image_vector: list = None,
):
    if history is None:
        history = []

    print(f"\n{'='*50}")
    print(f"[RAG] question   : {question!r}")
    print(f"[RAG] image_path : {image_path}")
    print(f"[RAG] history    : {len(history)} messages")
    print(f"{'='*50}\n")

    # ── INTENTION ──
    intention, confiance = classifier_intention(question)

    # ════════════════════════════════════════════
    # CAS 1 — HORS SUJET
    # ════════════════════════════════════════════
    if intention == "hors_sujet":
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
            {"role": "user", "content": (
                f"L'utilisateur dit : « {question} »\n"
                "C'est hors sujet pour une boutique de chaussures. "
                "Réponds poliment que tu es spécialisé chaussures et recentre la conversation."
            )},
        ]
        try:
            stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                 options={"num_ctx": 1024, "num_predict": 80, "temperature": 0.7})
            for chunk in stream:
                yield chunk["message"]["content"]
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1}
        return

    # ════════════════════════════════════════════
    # CAS 2 — LIVRAISON
    # ════════════════════════════════════════════
    if intention == "livraison":
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
            {"role": "user", "content": (
                f"L'utilisateur demande : « {question} »\n"
                "Tu n'as pas accès aux informations de livraison, de retours ou de stock. "
                "Dis-le honnêtement, invite l'utilisateur à contacter directement le magasin "
                "pour ces informations, et propose-lui de l'aider à trouver des chaussures."
            )},
        ]
        try:
            stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                 options={"num_ctx": 1024, "num_predict": 100, "temperature": 0.5})
            for chunk in stream:
                yield chunk["message"]["content"]
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1}
        return

    # ════════════════════════════════════════════
    # CAS 3 — PANIER
    # ════════════════════════════════════════════
    if intention == "panier" or _user_wants_cart(question):
        produits_historique = _produits_depuis_historique(history)
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        if produits_historique:
            contexte_produits = "\n".join([
                f"- {p['name']} ({p['price']}€)"
                for p in produits_historique
            ])
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"Produits disponibles dans la conversation :\n{contexte_produits}\n\n"
                    f"L'utilisateur dit : « {question} »\n"
                    "Identifie lequel il veut ajouter au panier, confirme chaleureusement "
                    "et cite son nom exact dans ta réponse."
                )},
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"L'utilisateur dit : « {question} »\n"
                    "Aucun produit n'a encore été présenté dans cette conversation. "
                    "Demande-lui ce qu'il recherche pour pouvoir l'aider."
                )},
            ]

        texte_complet = ""
        try:
            stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                 options={"num_ctx": 1024, "num_predict": 100, "temperature": 0.5})
            for chunk in stream:
                token = chunk["message"]["content"]
                texte_complet += token
                yield token
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"

        # Détecte le produit cité par Mistral dans sa réponse
        produit_cible = None
        if produits_historique:
            mentionnes = _produits_mentionnes(texte_complet, produits_historique)
            produit_cible = mentionnes[0] if mentionnes else produits_historique[0]

        yield {
            "type":       "products_final",
            "products":   [],
            "action":     "add_to_cart" if produit_cible else None,
            "product_id": produit_cible["id"] if produit_cible else None,
            "quantity":   1,
        }
        return

    # ════════════════════════════════════════════
    # CAS 4 — SUIVI (question sur produit déjà vu)
    # ════════════════════════════════════════════
    if intention == "suivi":
        produits_historique = _produits_depuis_historique(history)

        if produits_historique:
            yield {"products": [], "action": None, "product_id": None, "quantity": 1}

            contexte_produits = "\n".join([
                f"- {p['name']} ({p['marque']}, {p['price']}€) : {p['description']}\n"
                f"  Tailles : {', '.join(p.get('tailles', []))}\n"
                f"  Couleurs : {', '.join(p.get('couleurs', []))}"
                for p in produits_historique
            ])
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"Produits déjà présentés au client :\n{contexte_produits}\n\n"
                    f"Question du client : {question}\n"
                    "Réponds précisément à sa question en te basant uniquement "
                    "sur ces informations. Sois concis et utile."
                )},
            ]
            try:
                stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                     options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.5})
                for chunk in stream:
                    yield chunk["message"]["content"]
            except Exception as e:
                yield f"Erreur Mistral : {str(e)}"

            yield {
                "type":       "products_final",
                "products":   produits_historique,
                "action":     None,
                "product_id": None,
                "quantity":   1,
            }
            return
        # Pas de produits connus → on laisse tomber vers recherche normale

    # ════════════════════════════════════════════
    # CAS 5 — COMPARAISON
    # ════════════════════════════════════════════
    if intention == "comparaison":
        produits_historique = _produits_depuis_historique(history)

        if len(produits_historique) >= 2:
            yield {"products": [], "action": None, "product_id": None, "quantity": 1}

            p1, p2 = produits_historique[0], produits_historique[1]
            contexte = (
                f"Produit 1 — {p1['name']} ({p1['marque']}, {p1['price']}€)\n"
                f"Description : {p1['description']}\n"
                f"Tailles dispo : {', '.join(p1.get('tailles', []))}\n"
                f"Couleurs dispo : {', '.join(p1.get('couleurs', []))}\n\n"
                f"Produit 2 — {p2['name']} ({p2['marque']}, {p2['price']}€)\n"
                f"Description : {p2['description']}\n"
                f"Tailles dispo : {', '.join(p2.get('tailles', []))}\n"
                f"Couleurs dispo : {', '.join(p2.get('couleurs', []))}"
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"{contexte}\n\n"
                    f"Question du client : {question}\n"
                    "Fais une comparaison claire entre ces deux produits. "
                    "Mets en avant les différences clés (prix, usage, confort, style) "
                    "et aide le client à choisir selon son besoin."
                )},
            ]
            try:
                stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                     options={"num_ctx": 2048, "num_predict": 200, "temperature": 0.6})
                for chunk in stream:
                    yield chunk["message"]["content"]
            except Exception as e:
                yield f"Erreur Mistral : {str(e)}"

            yield {
                "type":       "products_final",
                "products":   [p1, p2],   # le front affiche les 2 côte à côte
                "action":     None,
                "product_id": None,
                "quantity":   1,
                "layout":     "comparison",  # signal pour le frontend
            }
            return

        # Moins de 2 produits connus → nouvelle recherche Qdrant (fall-through)
        print("[COMPARAISON] Pas assez de produits en historique → fallback Qdrant")

    # ════════════════════════════════════════════
    # CAS 6 — RECHERCHE & RECOMMANDATION
    # (+ fallback suivi/comparaison sans historique)
    # ════════════════════════════════════════════

    # 1. Vectorisation
    question_vector, is_image_search = _vectoriser(question, history, image_path, image_vector)

    # 2. Recherche Qdrant + filtres
    produits_trouves, contexte_filtres = _recherche_qdrant(question_vector, question, history)

    # Aucun produit après filtres → réponse directe
    if not produits_trouves:
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-10:]],
            {"role": "user", "content": contexte_filtres + f"\nQuestion : {question}"},
        ]
        texte_complet = ""
        try:
            stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                 options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.7})
            for chunk in stream:
                token = chunk["message"]["content"]
                texte_complet += token
                yield token
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1}
        return

    # 3. Préparation du prompt
    genre       = _extraire_genre(history, question)
    nb_produits = _nb_produits_from_history(history)

    description_visuelle = ""
    if is_image_search and produits_trouves:
        description_visuelle = f"[L'utilisateur a envoyé une photo de : {produits_trouves[0]['name']}] "

    # Pour la recommandation, on oriente le discours de Mistral
    suffixe_recommandation = ""
    if intention == "recommandation":
        suffixe_recommandation = (
            "\nL'utilisateur demande un conseil personnalisé. "
            "Donne ton avis clair sur le meilleur choix selon son besoin "
            "et explique pourquoi tu le recommandes."
        )

    question_complete = f"{description_visuelle}{question if question else ''}{suffixe_recommandation}"

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

    # 4. Yield metadata vide au début
    yield {"products": [], "action": None, "product_id": None, "quantity": 1}

    # 5. Streaming Mistral
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

    # 6. Filtre les produits selon ce que Mistral a mentionné
    produits_affiches = _produits_mentionnes(texte_complet, produits_trouves[:3])

    action = None
    if _user_wants_cart(question) and produits_affiches:
        action = "add_to_cart"

    yield {
        "type":       "products_final",
        "products":   produits_affiches[:nb_produits],
        "action":     action,
        "product_id": produits_affiches[0]["id"] if produits_affiches and action else None,
        "quantity":   1,
    }


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

