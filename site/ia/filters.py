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

def _normaliser_couleurs(texte: str) -> str:
    mots = texte.split()
    normalises = []
    for mot in mots:
        # Séparer le mot de sa ponctuation finale
        ponctuation = ""
        mot_clean = mot
        while mot_clean and mot_clean[-1] in ".,!?;:":
            ponctuation = mot_clean[-1] + ponctuation
            mot_clean = mot_clean[:-1]
        
        if len(mot_clean) >= 5 and mot_clean.endswith('s') and not mot_clean.endswith('ss'):
            normalises.append(mot_clean[:-1] + ponctuation)
        else:
            normalises.append(mot)
    return " ".join(normalises)


# ══════════════════════════════════════════════
# HELPERS FUZZY — question courante uniquement
# ══════════════════════════════════════════════

def _fuzzy_match(mot: str, candidats: list[str], seuil: int = 80, scorer=None) -> str | None:
    if not candidats:
        return None
    if scorer is None:
        scorer = fuzz.WRatio
    result = process.extractOne(mot, candidats, scorer=scorer, score_cutoff=seuil)
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
    mots = [m.strip(".,!?;:") for m in mots]
    mots = [m for m in mots if m]  # supprimer les mots vides
    candidats = list(mapping.keys())
    for n in (3, 2, 1):
        for i in range(len(mots) - n + 1):
            fragment = " ".join(mots[i:i+n])
            # Exact toujours prioritaire — mais mots courts (<= 3 chars) uniquement
            # s'ils sont des mots entiers (pas dans un mot plus long)
            if fragment in mapping:
                if n > 1 or len(fragment) >= 4:
                    return mapping[fragment]
                # Mot court (2-3 chars) : vérifier que c'est un mot isolé dans le texte original
                import re as _re2
                if _re2.search(r'(?<!\w)' + _re2.escape(fragment) + r'(?!\w)', texte.lower()):
                    return mapping[fragment]
            # 1 mot trop court → skip
            if n == 1 and len(fragment) < 4:
                continue
            if n == 1:
                candidats_valides = [
                    c for c in candidats
                    if abs(len(c) - len(fragment)) <= 1
                ]
            else:
                # Pour n>=2, exclure les candidats beaucoup plus courts que le fragment
                # évite "de sport" (8 chars) de matcher "or" (2 chars) via partial_ratio
                candidats_valides = [
                    c for c in candidats
                    if len(c) >= len(fragment) * 0.6
                ]
            # 1 mot → seuil plus strict + scorer exact (pas WRatio qui matche les sous-chaînes)
            seuil_effectif = 92 if n == 1 else seuil
            scorer = fuzz.ratio if n == 1 else fuzz.WRatio
            match = _fuzzy_match(fragment, candidats_valides, seuil=seuil_effectif, scorer=scorer)
            if match:
                return mapping[match]
    return None


def _chercher_dans_map_exact(texte: str, mapping: dict) -> str | None:
    """Matching EXACT — à utiliser sur l'historique pour éviter les faux positifs."""
    import re as _re
    texte_lower = texte.lower()
    # Du plus long au plus court pour éviter qu'un synonyme court masque un synonyme long
    for synonyme in sorted(mapping.keys(), key=len, reverse=True):
        # Mots courts (<=3 chars) : vérifier word boundary pour éviter "or" dans "sport"
        if len(synonyme) <= 3:
            if _re.search(r'(?<!\w)' + _re.escape(synonyme) + r'(?!\w)', texte_lower):
                return mapping[synonyme]
        else:
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


# Mots de confirmation courts qui ne valent que si le bot vient de parler d'ajout panier
_CONFIRMATIONS_COURTES = {
    "ok vas y", "vas y", "ok go", "go", "oui vas y", "oui confirme",
    "confirme", "c'est bon", "c bon", "parfait", "ok c'est bon",
    "valide", "yes", "ouais vas y", "allez vas y", "ok ajoute",
    "oui ajoute", "ajoute le", "ajoute la", "ok", "oui", "ouais",
}

_MOTS_CONTEXTE_PANIER_BOT = [
    "ajouter au panier", "ajoute au panier", "confirme", "valide",
    "veux-tu que j'ajoute", "je peux ajouter", "dois-je ajouter",
    "c'est bien cela", "c'est bien ça", "voulez-vous que j'ajoute",
    "je vais ajouter", "souhaitez-vous", "est-ce correct",
]

def user_wants_cart(question: str, history: list = None) -> bool:
    """Détecte une intention panier — matching exact uniquement, pas de fuzzy.
    Les confirmations courtes (ok, vas y...) ne valent que si le bot vient
    de proposer un ajout panier dans le message précédent.
    """
    q = question.lower().strip()

    # Mots panier explicites → toujours vrai
    if any(kw in q for kw in _MOTS_PANIER):
        return True

    # Confirmation courte → vrai seulement si le dernier message bot parlait de panier
    if q in _CONFIRMATIONS_COURTES and history:
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                bot_text = msg.get("content", "").lower()
                if any(kw in bot_text for kw in _MOTS_CONTEXTE_PANIER_BOT):
                    return True
                break

    return False


# ══════════════════════════════════════════════
# EXTRACTION DES FILTRES
# ══════════════════════════════════════════════

def extraire_filtres(question: str, history: list) -> dict:
    """
    Extrait tous les filtres depuis la question et l'historique.

    Règles de fallback :
      Genre / pointure / budget  → persistants, exact sur TOUT l'historique
                                   (l'utilisateur ne répète pas "je chausse du 42" à chaque message)
      Couleur / marque / catégorie → persistants sur TOUT l'historique
                                   Une nouvelle valeur dans la question courante remplace l'ancienne.
                                   Si la question n'en mentionne pas, on garde celle de l'historique.
    """
    import re as _re

    texte_question = question.lower()

    historique_user = [
        msg["content"].lower()
        for msg in history
        if msg["role"] == "user"
    ]
    # ── Couleur ──
    texte_normalise = _normaliser_couleurs(texte_question)
    print(f"[DEBUG] texte_question={texte_question!r}")
    print(f"[DEBUG] texte_normalise={texte_normalise!r}")
    # Pour les filtres ponctuels : 1 seul tour en arrière maximum (le plus récent)
    dernier_msg = [historique_user[-1]] if historique_user else []

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

    # Pour la persistance couleur/catégorie/marque : limiter aux 6 derniers messages
    # Inverser pour prendre la valeur la plus RÉCENTE en premier
    historique_recent = list(reversed(historique_user[-6:])) if historique_user else []

    # ── Couleur (persistante sur l'historique récent) ──
    # Chercher d'abord un tag explicite [couleur:X] injecté par le JS lors de normalisations
    import re as _re
    couleur = _chercher_dans_map_fuzzy(texte_normalise, DB["couleurs_map"])
    print(f"[DEBUG] couleur trouvée={couleur!r}")
    # Chercher tag [couleur:X] dans la question courante — sur le texte ORIGINAL
    # pour conserver la casse (ex: 'Rouge' et non 'rouge')
    _tag_match = _re.search(r'\[couleur:([^\]]+)\]', question)
    if _tag_match:
        couleur = _tag_match.group(1)  # conserve 'Rouge' avec majuscule
    if not couleur:
        for msg in historique_recent:
            # Chercher tag [couleur:X] en priorité — capitalize() pour restaurer la casse
            # car historique_user est stocké en lowercase
            _tag = _re.search(r'\[couleur:([^\]]+)\]', msg)
            if _tag:
                couleur = _tag.group(1).capitalize()  # 'rouge' → 'Rouge'
                break
            couleur = _chercher_dans_map_exact(msg, DB["couleurs_map"])
            if couleur:
                break
    if couleur:
        filtres["couleur"] = couleur

    # ── Marque (persistante sur l'historique récent) ──
    marque = _chercher_marque_fuzzy(texte_question)
    if not marque:
        for msg in historique_recent:  # déjà inversé
            marque = _chercher_marque_exact(msg)
            if marque:
                break
    if marque:
        filtres["marque"] = marque

    # ── Catégorie (persistante sur l'historique récent) ──
    categorie = _chercher_dans_map_fuzzy(texte_question, DB["categories_map"])
    if not categorie:
        for msg in historique_recent:  # déjà inversé
            categorie = _chercher_dans_map_exact(msg, DB["categories_map"])
            if categorie:
                break
    if categorie:
        filtres["categorie"] = categorie

    print(f"[FILTERS] détectés : {filtres}")
    return filtres


def appliquer_filtres(produits: list, question: str, history: list, filtres: dict = None) -> tuple[list, str]:
    """
    Applique les filtres sur la liste de produits.
    Si filtres est fourni (pré-calculé), on l'utilise directement.
    Retourne (produits_filtrés, contexte_pour_mistral).
    """
    if filtres is None:
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