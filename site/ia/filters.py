# ia/filters.py
# Extraction des filtres avec correspondance floue (RapidFuzz)
# Gère les fautes de frappe : "tallons" → "Talons", "adidass" → "adidas"
#
# RÈGLE FONDAMENTALE :
#   - Question courante  → fuzzy match autorisé (tolérant aux fautes)
#   - Historique passé   → matching EXACT uniquement (évite les faux positifs)
#   - Genre / pointure / budget → persistants (tout l'historique)
#   - Couleur / marque / catégorie → ponctuels (1 tour en arrière max)

import json
import os
import re
from rapidfuzz import process, fuzz
from db_mysql import fetch_all
from llm_prompt import _extraire_budget

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dictionnaires")

def _charger_json(nom: str) -> dict | list:
    path = os.path.join(_CONFIG_DIR, nom)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

_SYNONYMES_CATEGORIES: dict = _charger_json("synonymes_categories.json")
_SYNONYMES_COULEURS:   dict = _charger_json("synonymes_couleurs.json")
_SYNONYMES_GENRE:      dict = _charger_json("synonymes_genre.json")
_MOTS_PANIER:          list = _charger_json("mots_panier.json")


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

        categories_map = dict(_SYNONYMES_CATEGORIES)
        for cat in categories_raw:
            categories_map[cat.lower()] = cat

        couleurs_map = dict(_SYNONYMES_COULEURS)
        for couleur in couleurs_raw:
            couleurs_map[couleur.lower()] = couleur

        print(f"[FILTERS] {len(marques)} marques | {len(categories_raw)} catégories | {len(couleurs_raw)} couleurs")

        genres_ids = {}
        for genre in ["Homme", "Femme", "Mixte"]:
            ids = [
                r["id_shoes"]
                for r in fetch_all(f"SELECT id_shoes FROM articles WHERE genre = '{genre}'")
            ]
            genres_ids[genre] = set(ids)

        return {
            "marques":        marques,
            "categories":     categories_raw,
            "categories_map": categories_map,
            "couleurs_map":   couleurs_map,
            "genres_ids":     genres_ids,
        }
    except Exception as e:
        print(f"[FILTERS] Erreur chargement DB : {e}")
        return {
            "marques": [], "categories": [],
            "categories_map": dict(_SYNONYMES_CATEGORIES),
            "couleurs_map":   dict(_SYNONYMES_COULEURS),
            "genres_ids":     {},
        }

DB = _charger_valeurs_db()


# ══════════════════════════════════════════════
# HELPERS FUZZY — question courante uniquement
# ══════════════════════════════════════════════

def _fuzzy_match(mot: str, candidats: list[str], seuil: int = 80) -> str | None:
    if not candidats:
        return None
    result = process.extractOne(mot, candidats, scorer=fuzz.WRatio, score_cutoff=seuil)
    return result[0] if result else None


def _chercher_dans_map_fuzzy(texte: str, mapping: dict, seuil: int = 88) -> str | None:
    """Fuzzy match — à utiliser sur la question courante uniquement.

    Règles anti-faux-positifs :
    - Seuil relevé à 88 (était 80)
    - Fragment d'1 mot < 4 chars ignoré (évite "une", "des", "le"...)
    - Fragment d'1 mot : seuil encore plus strict à 92
    - Correspondance exacte toujours prioritaire (sans longueur minimale)
    """
    mots = texte.lower().split()
    candidats = list(mapping.keys())
    for n in (3, 2, 1):
        for i in range(len(mots) - n + 1):
            fragment = " ".join(mots[i:i+n])
            # Exact toujours prioritaire
            if fragment in mapping:
                return mapping[fragment]
            # 1 mot trop court → skip
            if n == 1 and len(fragment) < 4:
                continue
            # 1 mot → seuil plus strict
            seuil_effectif = 92 if n == 1 else seuil
            match = _fuzzy_match(fragment, candidats, seuil=seuil_effectif)
            if match:
                return mapping[match]
    return None


def _chercher_dans_map_exact(texte: str, mapping: dict) -> str | None:
    """Matching EXACT — à utiliser sur l'historique pour éviter les faux positifs."""
    texte_lower = texte.lower()
    # Du plus long au plus court pour éviter qu'un synonyme court masque un synonyme long
    for synonyme in sorted(mapping.keys(), key=len, reverse=True):
        if synonyme in texte_lower:
            return mapping[synonyme]
    return None


def _chercher_marque_fuzzy(texte: str, seuil: int = 90) -> str | None:
    """Fuzzy match marque — question courante uniquement.
    Seuil strict à 90 : une marque mal orthographiée doit rester très proche.
    Fragment d'1 mot < 4 chars ignoré.
    """
    mots = texte.lower().split()
    marques = DB["marques"]
    for n in (2, 1):
        for i in range(len(mots) - n + 1):
            fragment = " ".join(mots[i:i+n])
            if fragment in marques:
                return fragment
            if n == 1 and len(fragment) < 4:
                continue
            match = _fuzzy_match(fragment, marques, seuil=seuil)
            if match:
                return match
    return None


def _chercher_marque_exact(texte: str) -> str | None:
    """Matching exact marque — historique uniquement."""
    texte_lower = texte.lower()
    for marque in sorted(DB["marques"], key=len, reverse=True):
        if marque in texte_lower:
            return marque
    return None


def _chercher_genre(texte: str) -> str | None:
    texte_lower = texte.lower()
    for genre, mots_cles in _SYNONYMES_GENRE.items():
        for mot in mots_cles:
            if mot in texte_lower:
                return genre
    return None


def _chercher_pointure(texte: str) -> str | None:
    matches = re.finditer(r"\b(3[6-9]|4[0-9]|50)\b", texte)
    for match in matches:
        start, end = match.start(), match.end()
        apres = texte[end:end+2].strip()
        avant = texte[max(0, start-15):start].strip()
        mots_budget = ["€", "euro", "moins de", "max", "budget", "sous", "jusqu"]
        if apres.startswith("€"):
            continue
        if any(kw in avant for kw in mots_budget):
            continue
        return match.group(1)
    return None


def user_wants_cart(question: str) -> bool:
    """Détecte une intention panier — matching exact uniquement, pas de fuzzy.
    Le fuzzy causait trop de faux positifs ("running" → "prendre" etc.)
    """
    q = question.lower().strip()
    return any(kw in q for kw in _MOTS_PANIER)


# ══════════════════════════════════════════════
# EXTRACTION DES FILTRES
# ══════════════════════════════════════════════

def extraire_filtres(question: str, history: list) -> dict:
    """
    Extrait tous les filtres depuis la question et l'historique.

    Règles de fallback :
      Genre / pointure / budget  → persistants, exact sur TOUT l'historique
                                   (l'utilisateur ne répète pas "je chausse du 42" à chaque message)
      Couleur / marque / catégorie → ponctuels :
        - question courante : fuzzy (tolérant aux fautes)
        - historique        : exact uniquement, 1 seul tour en arrière
                              → empêche "jaune bellemode" de contaminer les requêtes suivantes
    """
    texte_question = question.lower()

    historique_user = [
        msg["content"].lower()
        for msg in history
        if msg["role"] == "user"
    ]

    # Pour les filtres ponctuels : 1 seul tour en arrière maximum
    dernier_msg = [historique_user[0]] if historique_user else []

    filtres = {}

    # ── Budget (persistant) ──
    budget = _extraire_budget(question)
    if not budget:
        for msg in historique_user:
            budget = _extraire_budget(msg)
            if budget:
                break
    if budget:
        filtres["budget"] = budget

    # ── Genre (persistant) ──
    genre = _chercher_genre(texte_question)
    if not genre:
        for msg in historique_user:
            genre = _chercher_genre(msg)
            if genre:
                break
    if genre:
        filtres["genre"] = genre

    # ── Pointure (persistante) ──
    pointure = _chercher_pointure(texte_question)
    if not pointure:
        for msg in historique_user:
            pointure = _chercher_pointure(msg)
            if pointure:
                break
    if pointure:
        filtres["pointure"] = pointure

    # ── Couleur (ponctuelle) ──
    couleur = _chercher_dans_map_fuzzy(texte_question, DB["couleurs_map"])
    if not couleur:
        for msg in dernier_msg:                              # 1 tour max, exact
            couleur = _chercher_dans_map_exact(msg, DB["couleurs_map"])
            if couleur:
                break
    if couleur:
        filtres["couleur"] = couleur

    # ── Marque (ponctuelle) ──
    marque = _chercher_marque_fuzzy(texte_question)
    if not marque:
        for msg in dernier_msg:                              # 1 tour max, exact
            marque = _chercher_marque_exact(msg)
            if marque:
                break
    if marque:
        filtres["marque"] = marque

    # ── Catégorie (ponctuelle) ──
    categorie = _chercher_dans_map_fuzzy(texte_question, DB["categories_map"])
    if not categorie:
        for msg in dernier_msg:                              # 1 tour max, exact
            categorie = _chercher_dans_map_exact(msg, DB["categories_map"])
            if categorie:
                break
    if categorie:
        filtres["categorie"] = categorie

    print(f"[FILTERS] détectés : {filtres}")
    return filtres


def appliquer_filtres(produits: list, question: str, history: list) -> tuple[list, str]:
    """
    Applique les filtres extraits sur la liste de produits.
    Retourne (produits_filtrés, contexte_pour_mistral).
    """
    filtres = extraire_filtres(question, history)

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
        ids_genre = DB["genres_ids"].get(genre, set())
        ids_mixte = DB["genres_ids"].get("Mixte", set())
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

    contexte = f"Produits filtrés ({' + '.join(filtres_appliques)}) :" if filtres_appliques else ""
    return produits_courants, contexte