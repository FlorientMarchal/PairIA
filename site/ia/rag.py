# ia/rag.py
import sys
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from database import qdrant
from llm_prompt import build_prompt, get_system_prompt
from language_utils import normaliser_question, traduire_reponse
from image_search import model
from intention_classifier import classifier_intention
from filters import extraire_filtres, user_wants_cart, DB
from PIL import Image
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue, MatchAny, MinShould

LLM_MODEL = "llama3.1"

# ══════════════════════════════════════════════
# LIMITES DE GÉNÉRATION PAR INTENTION
# ══════════════════════════════════════════════
_LIMITES = {
    "hors_sujet":     {"num_predict": 100,   "consigne": "Réponds en 1-2 phrases.", "nb_produits": 0},
    "livraison":      {"num_predict": 180,  "consigne": "Réponds en 2-3 phrases.", "nb_produits": 0},
    "panier":         {"num_predict": 200,  "consigne": "Réponds en 2-3 phrases.", "nb_produits": 1},
    "suivi":          {"num_predict": 220,  "consigne": "Réponds en 2-3 phrases maximum.", "nb_produits": 1},
    "comparaison":    {"num_predict": 120,  "consigne": "Dis juste en une phrase que ci dessous le client trouvera la comparaison du produit 1 et 2", "nb_produits": 2},
    "recommandation": {"num_predict": 220,  "consigne": "Conseille en 2-3 phrases maximum.", "nb_produits": 1},
    "recherche":      {"num_predict": 350,  "consigne": "Parle naturellement comme un vendeur : une phrase par produit, sans liste, sans tirets, sans ':'. Enchaine les produits avec des connecteurs ('aussi', 'et', 'sinon'). Si pas de correspondance exacte, présente-les comme les plus adaptés sans le mentionner explicitement.", "nb_produits": 3},
    "salutation":     {"num_predict": 150,   "consigne": "Réponds en 1 phrase de bienvenue.", "nb_produits": 0},
}


def _calculer_ctx(history: list, base: int = 2048) -> int:
    nb_msgs = len(history)
    if nb_msgs > 10:
        return 4096
    elif nb_msgs > 6:
        return 3072
    return base


# ══════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════

def _nb_produits_from_history(history: list, intention: str = "recherche") -> int:
    # La limite par intention prime sur l'historique
    nb_intention = _LIMITES.get(intention, _LIMITES["recherche"])["nb_produits"]
    if nb_intention > 0:
        return nb_intention

    nb_echanges = len(history) // 2
    if nb_echanges == 0:
        return 3
    elif nb_echanges <= 4:
        return 3
    else:
        return 2


def _extraire_genre(history: list, question: str) -> str | None:
    from filters import _chercher_genre
    texte_complet = question.lower()
    for msg in history:
        if msg["role"] == "user":
            texte_complet += " " + msg["content"].lower()
    return _chercher_genre(texte_complet)


def _detecter_tutoiement(history: list, question: str) -> str:
    """Détecte si l'utilisateur tutoie ou vouvoie, retourne 'tu' ou 'vous'.
    Par défaut 'tu'. Se base sur tous les messages utilisateur."""
    _MOTS_VOUVOIEMENT = [
        "vous avez", "vous êtes", "avez-vous", "avez vous",
        "pouvez-vous", "pouvez vous", "avez-vous", "faites-vous",
    ]
    _MOTS_TUTOIEMENT = [
        "tu as", "t'as", "tu es", "t'es", "as-tu", "es-tu",
        "peux-tu", "peux tu", "fais-tu", "fais tu",
    ]
    messages_user = [question.lower()] + [
        m["content"].lower() for m in history if m.get("role") == "user"
    ]
    texte = " ".join(messages_user)
    nb_vous = sum(1 for mot in _MOTS_VOUVOIEMENT if mot in texte)
    nb_tu   = sum(1 for mot in _MOTS_TUTOIEMENT  if mot in texte)
    if nb_vous > nb_tu:
        return "vous"
    return "tu"  # par défaut



    from db_mysql import fetch_all
    from rapidfuzz import fuzz

    question_lower = question.lower().strip()

    # ── GARDE-FOU : questions trop courtes ou génériques → on ne cherche pas ──
    mots = question_lower.split()

    # Moins de 3 mots → probablement pas un nom de produit
    if len(mots) < 3:
        return []

    # Mots-clés de recherche générique → pas un nom de produit
    mots_generiques = {
        "pour", "je", "cherche", "veux", "voudrais", "besoin",
        "style", "type", "modèle", "chaussure", "chaussures",
        "une", "des", "les", "un", "le", "la", "de", "du",
        "avec", "sans", "pas", "plus", "moins", "très",
        "running", "sport", "ville", "casual", "marche",
    }
    # Si la majorité des mots sont génériques → pas un nom de produit
    mots_non_generiques = [m for m in mots if m not in mots_generiques]
    if len(mots_non_generiques) < 2:
        return []

    try:
        rows = fetch_all("SELECT id_shoes, nom, prix, categorie, marque, url_image, description FROM articles")
    except Exception as e:
        print(f"[NOM_EXACT] Erreur DB : {e}")
        return []

    meilleur_score   = 0
    meilleur_produit = None

    for row in rows:
        nom = (row.get("nom") or "").lower()
        if not nom:
            continue
        score = fuzz.partial_ratio(nom, question_lower)
        if score > meilleur_score and score >= 92:  # seuil remonté de 88 → 92
            meilleur_score   = score
            meilleur_produit = row

    if not meilleur_produit:
        return []

    print(f"[NOM_EXACT] '{meilleur_produit['nom']}' détecté (score={meilleur_score})")

    try:
        sc = fetch_all(
            f"SELECT taille, couleur FROM size_color WHERE id_shoes = {r['id_shoes']}"
        )
        tailles  = list({r["taille"]  for r in sc if r.get("taille")})
        couleurs = list({r["couleur"] for r in sc if r.get("couleur")})
    except Exception:
        tailles, couleurs = [], []

    return [{
        "id":          meilleur_produit["id_shoes"],
        "name":        meilleur_produit["nom"],
        "price":       meilleur_produit["prix"],
        "emoji":       "👟",
        "categorie":   meilleur_produit.get("categorie", ""),
        "marque":      meilleur_produit.get("marque", ""),
        "url_image":   meilleur_produit.get("url_image", ""),
        "description": meilleur_produit.get("description", ""),
        "tailles":     tailles,
        "couleurs":    couleurs,
    }]

def _chercher_produits_cites(question: str) -> list:
    """
    Cherche PLUSIEURS produits cités dans la question.
    Ex: "compare les NeoUrban Street et les CloudStep Lite"
    → retourne les deux produits trouvés.
    """
    from db_mysql import fetch_all
    from rapidfuzz import fuzz

    question_lower = question.lower().strip()

    try:
        rows = fetch_all(
            "SELECT id_shoes, nom, prix, categorie, marque, url_image, description FROM articles"
        )
    except Exception as e:
        print(f"[CITES] Erreur DB : {e}")
        return []

    # Score chaque produit
    scores = []
    for row in rows:
        nom = (row.get("nom") or "").lower()
        if not nom:
            continue
        score = fuzz.partial_ratio(nom, question_lower)
        if score >= 85:
            scores.append((score, row))

    # Trie par score décroissant, garde les 2 meilleurs
    scores.sort(key=lambda x: x[0], reverse=True)
    meilleurs = [row for _, row in scores[:2]]

    if len(meilleurs) < 2:
        return []

    print(f"[CITES] Produits trouvés : {[r['nom'] for r in meilleurs]}")

    # Construit les dicts produits avec tailles/couleurs
    result = []
    for row in meilleurs:
        try:
            from db_mysql import fetch_all as fa
            sc = fa(f"SELECT taille, couleur FROM size_color WHERE id_shoes = {row['id_shoes']}")
            tailles  = list({r["taille"]  for r in sc if r.get("taille")})
            couleurs = list({r["couleur"] for r in sc if r.get("couleur")})
        except Exception:
            tailles, couleurs = [], []

        result.append({
            "id":          row["id_shoes"],
            "name":        row["nom"],
            "price":       row["prix"],
            "emoji":       "👟",
            "categorie":   row.get("categorie", ""),
            "marque":      row.get("marque", ""),
            "url_image":   row.get("url_image", ""),
            "description": row.get("description", ""),
            "tailles":     tailles,
            "couleurs":    couleurs,
        })

    return result

def _produits_mentionnes(texte: str, produits: list) -> list:
    texte_lower = texte.lower()
    mentionnes  = []
    for p in produits:
        nom  = p["name"].lower()
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
    for msg in reversed(history):
        if msg["role"] == "assistant" and "products" in msg:
            produits = msg["products"]
            if produits:
                print(f"[HISTORIQUE] ✅ {len(produits)} produit(s) : {[p['name'] for p in produits]}")
                return produits
    print(f"[HISTORIQUE] ❌ Aucun produit — {len(history)} msgs, "
          f"clés assistant : {[list(m.keys()) for m in history if m['role'] == 'assistant']}")
    return []



def _resumer_description(produit: dict, langue: str = "fr") -> str:
    description = produit.get("description", "").strip()
    if not description:
        return ""
    from language_utils import nom_langue
    langue_label = nom_langue(langue) if langue != "fr" else "français"
    try:
        resp = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": (
                f"Tu es un assistant. Réponds UNIQUEMENT en {langue_label}.\n"
                f"Résume en une phrase de 10 à 15 mots MAXIMUM le point fort principal de cette chaussure.\n"
                f"Description : {description}"
            )}],
            options={"num_predict": 60, "temperature": 0.5},
        )
        return resp["message"]["content"].strip().strip('"').strip("'")
    except Exception as e:
        return description[:120] + "..." if len(description) > 120 else description


def _identifier_produits_a_comparer(question: str, produits: list) -> tuple[dict, dict] | None:
    if len(produits) < 2:
        return None

    n = len(produits)
    liste = "\n".join([f"{i+1}. {p['name']}" for i, p in enumerate(produits)])
    prompt = (
        f"Produits disponibles :\n{liste}\n\n"
        f"L'utilisateur dit : \"{question}\"\n"
        f"Quels sont les numéros des 2 produits à comparer ?\n"
        f"IMPORTANT : si l'utilisateur fait référence aux derniers produits de la liste "
        f"('les deux derniers', 'the last two', 'die letzten beiden', 'los dos últimos', etc.), "
        f"choisis les numéros {n-1} et {n}.\n"
        f"Si référence aux premiers ('les deux premiers', 'the first two', etc.), choisis 1 et 2.\n"
        f"Réponds UNIQUEMENT en JSON : {{\"p1\": 1, \"p2\": 3}}\n"
        f"Si vraiment non précisé, réponds : {{\"p1\": 1, \"p2\": 2}}"
    )
    try:
        resp = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 20, "temperature": 0},
        )
        raw = resp["message"]["content"].strip()
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            i1, i2 = int(data["p1"]) - 1, int(data["p2"]) - 1
            if 0 <= i1 < len(produits) and 0 <= i2 < len(produits) and i1 != i2:
                print(f"[COMPARAISON] {produits[i1]['name']} vs {produits[i2]['name']}")
                return produits[i1], produits[i2]
    except Exception as e:
        print(f"[COMPARAISON] identification échouée : {e} → fallback [0][1]")

    return produits[0], produits[1]

# ══════════════════════════════════════════════
# LLM HELPERS
# ══════════════════════════════════════════════

def _llm_enrichir_question(question: str, history: list) -> str:
    contexte = ""
    msgs_user = [m["content"] for m in history if m["role"] == "user"][-2:]
    if msgs_user:
        contexte = f"Contexte conversation : {' / '.join(msgs_user)}\n"

    prompt = (
        f"{contexte}"
        f"Reformule cette demande en 5 à 8 mots-clés pour rechercher des chaussures.\n"
        f" Utilise UNIQUEMENT des mots présents ou directement liés à la demande. \n "
        f"Inclus : style, usage, matière, type de chaussure, occasion si pertinent.\n"
        f"Demande : \"{question}\"\n"
        f"Réponds UNIQUEMENT en français, avec les mots-clés séparés par des espaces, sans ponctuation."
    )
    try:
        resp = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 100, "temperature": 0},
        )
        enrichie = resp["message"]["content"].strip()
        print(f"[LLM] question enrichie : {enrichie!r}")
        return enrichie
    except Exception as e:
        print(f"[LLM] enrichissement échoué : {e} → fallback question originale")
        return question

def _llm_categories_candidates(question: str, history: list) -> list[str]:
    print(f"[LLM-CAT] ENTRÉE fonction, question={question!r}")
    categories_dispo = DB.get("categories", [])
    if not categories_dispo:
        print("[LLM] Aucune catégorie en DB → pas de filtre")
        return []

    msgs_user = [m["content"] for m in history if m["role"] == "user"][-2:]
    contexte  = f"Contexte : {' / '.join(msgs_user)}\n" if msgs_user else ""

    prompt = (
        f"{contexte}"
        f"Catégories disponibles : {', '.join(categories_dispo)}\n"
        f"Question : \"{question}\"\n"
        f"Liste TOUTES les catégories pertinentes ET similaires avec un score de 1 à 10.\n"
        f"Réponds UNIQUEMENT en JSON : {{\"categories\": [{{\"nom\": \"categorie1\", \"score\": nombre entier 1}}, {{\"nom\": \"categorie2\", \"score\": nombre entier 2}}]}}"
    )
    try:
        resp = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 250, "temperature": 0},
        )
        print(f"[LLM-CAT] resp reçu")
        raw = resp["message"]["content"].strip()
        print(f"[LLM-CAT] raw : {raw!r}")
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())

                # Toutes les catégories valides avec leur score
                cats_raw = [
                    c for c in data.get("categories", [])
                    if c["nom"] in categories_dispo and c.get("score", 0) > 0
                ]
                print(f"[LLM-CAT] catégories brutes : {[(c['nom'], c['score']) for c in cats_raw]}")

                if not cats_raw:
                    print(f"[LLM-CAT] aucune catégorie reconnue → recherche libre")
                    return []

                # Seuil adaptatif selon le meilleur score
                meilleur_score = max(c["score"] for c in cats_raw)
                if meilleur_score >= 9:
                    seuil = 7
                elif meilleur_score >= 7:
                    seuil = 5
                elif meilleur_score >= 5:
                    seuil = 4
                else:
                    seuil = 3
                print(f"[LLM-CAT] meilleur score={meilleur_score} → seuil adaptatif={seuil}")

                cats = [c["nom"] for c in cats_raw if c.get("score", 0) >= seuil]
                print(f"[LLM-CAT] catégories retenues (score >= {seuil}) : {cats}")
                return cats

            except Exception as e:
                print(f"[LLM-CAT] parse échoué : {e}")
    except Exception as e:
        import traceback
        print(f"[LLM-CAT] ERREUR : {traceback.format_exc()}")
    return []
# ══════════════════════════════════════════════
# VECTORISATION + ANALYSE PARALLÈLE
# ══════════════════════════════════════════════

def _analyser_question(
    question: str,
    history: list,
    image_path: str = None,
    image_vector: list = None,
) -> tuple[list, bool, dict, list]:
    try:
        if image_path and os.path.exists(image_path):
            print("[VECTORISE] mode image_path")
            image_vec = model.encode(Image.open(image_path))
            vec = ((image_vec * 0.7) + (model.encode(question) * 0.3)).tolist() \
                  if question and question.strip() else image_vec.tolist()
            return vec, True, {}, []

        if image_vector:
            print("[VECTORISE] mode image_vector (session)")
            import numpy as np
            image_vec = np.array(image_vector)

            filtres_explicites    = extraire_filtres(question, history)
            categories_candidates = _llm_categories_candidates(question, history)

            if question and question.strip():
                contexte_produit = ""
                for msg in reversed(history):
                    if msg["role"] == "user" and "Produits suggérés" in msg["content"]:
                        m = re.search(r"Produits suggérés : ([^,\(]+)", msg["content"])
                        if m:
                            contexte_produit = m.group(1).strip()
                        break
                q_enrichie = f"{contexte_produit} {question}".strip() if contexte_produit else question
                text_vec   = model.encode(q_enrichie)
                vec        = ((image_vec * 0.5) + (text_vec * 0.5)).tolist()
            else:
                vec = image_vector

            print(f"[VECTORISE] filtres explicites : {filtres_explicites}")
            print(f"[VECTORISE] catégories candidates : {categories_candidates}")
            return vec, True, filtres_explicites, categories_candidates

        # Mode texte : 3 tâches en parallèle
        print("[VECTORISE] mode texte — analyse parallèle")
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_enrichi    = executor.submit(_llm_enrichir_question,     question, history)
            history_recent = [m for m in history[-4:]]  # seulement les 2 derniers échanges
            fut_filtres = executor.submit(extraire_filtres, question, history_recent)
            fut_categories = executor.submit(_llm_categories_candidates, question, history)

            question_enrichie     = fut_enrichi.result()
            filtres_explicites    = fut_filtres.result()
            categories_candidates = fut_categories.result()

        if not question_enrichie or question_enrichie.lower().strip() == question.lower().strip():
            question_enrichie = question
            print("[VECTORISE] enrichissement sans apport → question originale")

        if "categorie" in filtres_explicites:
            # extraire_filtres a trouvé une catégorie explicite → elle prime
            cat_explicite = filtres_explicites.pop("categorie")
            cats_llm_valides = [c for c in categories_candidates if c != cat_explicite]
            categories_candidates = [cat_explicite] + cats_llm_valides[:2]  # max 2 similaires
            print(f"[VECTORISE] catégorie explicite prioritaire : {cat_explicite} + similaires LLM : {cats_llm_valides[:2]}")
        else:
            filtres_explicites.pop("categorie", None)

            # ✅ Si l'utilisateur demande une couleur ou une marque SANS catégorie explicite,
            # on ignore les catégories suggérées par le LLM — elles restreignent trop la recherche
            # et peuvent mener à 0 résultat alors que des produits de la bonne couleur existent ailleurs.
            if filtres_explicites.get("couleur") or filtres_explicites.get("marque"):
                categories_candidates = []
                print("[VECTORISE] couleur/marque sans catégorie explicite → recherche libre (catégories LLM ignorées)")
            elif not categories_candidates:
                print("[VECTORISE] aucune catégorie détectée → recherche libre")

        vec = model.encode(question_enrichie).tolist()
        print(f"[VECTORISE] filtres explicites : {filtres_explicites}")
        print(f"[VECTORISE] catégories candidates : {categories_candidates}")
        return vec, False, filtres_explicites, categories_candidates

    except Exception as e:
        print(f"[VECTORISE] ❌ Erreur : {e}")
        return [0] * 512, False, {}, []

# ══════════════════════════════════════════════
# RECHERCHE QDRANT
# ══════════════════════════════════════════════

def _construire_filtre_qdrant(filtres: dict, categories_candidates: list) -> Filter | None:
    conditions    = []
    cat_conditions = []

    if "budget" in filtres:
        conditions.append(FieldCondition(key="prix", range=Range(lte=filtres["budget"])))
        print(f"[QDRANT-FILTER] prix <= {filtres['budget']}")

    if "genre" in filtres:
        conditions.append(FieldCondition(key="genre",
                                         match=MatchAny(any=[filtres["genre"], "Mixte"])))
        print(f"[QDRANT-FILTER] genre = {filtres['genre']} ou Mixte")

    if "marque" in filtres:
        conditions.append(FieldCondition(key="marque",
                                         match=MatchValue(value=filtres["marque"])))
        print(f"[QDRANT-FILTER] marque = {filtres['marque']}")

    if "couleur" in filtres:
        conditions.append(FieldCondition(key="couleurs",
                                         match=MatchValue(value=filtres["couleur"])))
        print(f"[QDRANT-FILTER] couleur = {filtres['couleur']}")

    if "pointure" in filtres:
        conditions.append(FieldCondition(key="tailles",
                                         match=MatchValue(value=filtres["pointure"])))
        print(f"[QDRANT-FILTER] taille = {filtres['pointure']}")

    if categories_candidates:
        cat_conditions = [
            FieldCondition(key="categorie", match=MatchValue(value=cat))
            for cat in categories_candidates
        ]
        print(f"[QDRANT-FILTER] catégories (OR) = {categories_candidates}")

    if not conditions and not cat_conditions:
        return None

    return Filter(
        must=conditions if conditions else None,
        should=cat_conditions if cat_conditions else None,
        min_should=MinShould(conditions=cat_conditions, min_count=1) if cat_conditions else None,
    )


def _recherche_qdrant(
    question_vector: list,
    question: str,
    history: list,
    filtres: dict,
    categories_candidates: list,
) -> tuple[list, str]:
    limit_qdrant  = 20 if categories_candidates else 8
    qdrant_filter = _construire_filtre_qdrant(filtres, categories_candidates)
    print(f"[QDRANT] limit={limit_qdrant} | filtre natif={'oui' if qdrant_filter else 'non'}")

    try:
        results = qdrant.query_points(
            collection_name="produits_image",
            query=question_vector,
            query_filter=qdrant_filter,
            limit=limit_qdrant,
            score_threshold=0.10,
        ).points
        print(f"[QDRANT] {len(results)} résultats")
        for i, r in enumerate(results):
            print(f"[QDRANT] #{i+1} {r.payload.get('nom')} | cat={r.payload.get('categorie')} | score={r.score:.3f}")
    except Exception as e:
        print(f"[QDRANT] ❌ Erreur : {e}")
        results = []

    def _construire_produit(r) -> dict:
        tailles  = r.payload.get("tailles",  [])
        couleurs = r.payload.get("couleurs", [])
        if isinstance(tailles, str):
            tailles  = [t.strip() for t in tailles.split(",") if t.strip()]
        if isinstance(couleurs, str):
            couleurs = [c.strip() for c in couleurs.split(",") if c.strip()]
        return {
            "id":          r.id,
            "name":        r.payload.get("nom",         ""),
            "price":       r.payload.get("prix",        0),
            "emoji":       "👟",
            "categorie":   r.payload.get("categorie",   ""),
            "marque":      r.payload.get("marque",      ""),
            "url_image":   r.payload.get("url_image",   ""),
            "description":      r.payload.get("description",      ""),
            "caracteristiques": r.payload.get("caracteristiques", ""),
            "tailles":          tailles,
            "couleurs":         couleurs,
        }

    produits = [_construire_produit(r) for r in results]

    # Réordonner : catégorie principale en tête, similaires ensuite
    if categories_candidates:
        cat_principale = categories_candidates[0]
        produits_principaux = [p for p in produits if p["categorie"] == cat_principale]
        produits_similaires = [p for p in produits if p["categorie"] != cat_principale]
        produits = produits_principaux + produits_similaires
        print(f"[QDRANT] réordonné : {len(produits_principaux)} '{cat_principale}' + {len(produits_similaires)} similaires")

    # Complétion si peu de résultats avec filtre catégorie strict
    if len(produits) < 3 and categories_candidates:
        print(f"[QDRANT] seulement {len(produits)} résultat(s) → complétion sans filtre catégorie")
        filtre_souple = _construire_filtre_qdrant(filtres, [])
        try:
            results_extra = qdrant.query_points(
                collection_name="produits_image",
                query=question_vector,
                query_filter=filtre_souple,
                limit=8,
                score_threshold=0.68,
            ).points
            ids_deja = {p["id"] for p in produits}
            nb_ajoutes = 0
            for r in results_extra:
                if r.id in ids_deja:
                    continue
                produits.append(_construire_produit(r))
                nb_ajoutes += 1
                if len(produits) >= 5:
                    break
            print(f"[QDRANT] après complétion : {len(produits)} produits ({nb_ajoutes} ajoutés)")
        except Exception as e:
            print(f"[QDRANT] ❌ complétion échouée : {e}")

    if not produits:
        filtres_ko = []
        if "budget"   in filtres: filtres_ko.append(f"sous {filtres['budget']}€")
        if "genre"    in filtres: filtres_ko.append(f"pour {filtres['genre']}")
        if "marque"   in filtres: filtres_ko.append(f"marque {filtres['marque']}")
        if "couleur"  in filtres: filtres_ko.append(f"couleur {filtres['couleur']}")
        if "pointure" in filtres: filtres_ko.append(f"taille {filtres['pointure']}")
        if categories_candidates: filtres_ko.append(f"catégorie {'/'.join(categories_candidates)}")
        contexte = (
            f"ATTENTION : aucun produit trouvé pour [{', '.join(filtres_ko)}]. "
            if filtres_ko else "ATTENTION : aucun produit trouvé. "
        ) + (
            "Ne propose AUCUN produit inventé. "
            "Explique ce qui n'est pas disponible et demande à l'utilisateur "
            "s'il veut modifier ses critères."
        )
        print(f"[QDRANT] 0 résultats | contexte : {contexte!r}")
        return [], contexte

    filtres_ok = []
    if "budget"   in filtres: filtres_ok.append(f"sous {filtres['budget']}€")
    if "genre"    in filtres: filtres_ok.append(f"pour {filtres['genre']}")
    if "marque"   in filtres: filtres_ok.append(f"marque {filtres['marque']}")
    if "couleur"  in filtres: filtres_ok.append(f"couleur {filtres['couleur']}")
    if "pointure" in filtres: filtres_ok.append(f"taille {filtres['pointure']}")
    if categories_candidates: filtres_ok.append(f"catégorie {'/'.join(categories_candidates)}")

    nb_cat = len([p for p in produits if p["categorie"] == categories_candidates[0]]) if categories_candidates else 0
    nb_alt = len(produits) - nb_cat
    if nb_alt > 0 and categories_candidates:
        contexte = f"Produits filtrés ({', '.join(filtres_ok)}) + {nb_alt} alternative(s) similaire(s) :"
    else:
        contexte = f"Produits filtrés ({', '.join(filtres_ok)}) :" if filtres_ok else ""

    print(f"[QDRANT] {len(produits)} produits | contexte : {contexte!r}")
    return produits, contexte


def _filtres_depuis_produit(produit: dict) -> dict:
    filtres = {}
    if produit.get("categorie"):
        filtres["categorie"] = produit["categorie"]
    couleurs = produit.get("couleurs", [])
    if couleurs:
        filtres["couleur"] = couleurs[0]
    return filtres


# ══════════════════════════════════════════════
# STREAMING PRINCIPAL
# ══════════════════════════════════════════════

# Familles de couleurs : si une couleur exacte n'est pas disponible,
# on propose les couleurs de la même famille
_FAMILLES_COULEURS = {
    "Rouge":   ["Rouge", "Bordeaux", "Corail", "Terracotta", "Rose", "Orange"],
    "Bordeaux":["Bordeaux", "Rouge"],
    "Bleu":    ["Bleu", "Bleu marine", "Bleu nuit", "Bleu ciel", "Bleu électrique", "Bleu indigo", "Bleu océan"],
    "Vert":    ["Vert", "Kaki", "Vert hunter", "Vert menthe"],
    "Marron":  ["Marron", "Camel", "Cognac", "Terracotta"],
    "Gris":    ["Gris", "Gris anthracite", "Charbon"],
    "Blanc":   ["Blanc", "Blanc cassé", "Crème", "Beige"],
    "Beige":   ["Beige", "Beige naturel", "Crème", "Blanc cassé", "Camel"],
}

def _couleurs_famille(couleur: str) -> list:
    """Retourne les couleurs de la même famille, couleur demandée en premier."""
    for famille, couleurs in _FAMILLES_COULEURS.items():
        if couleur in couleurs:
            return couleurs
    return [couleur]

def _stream_and_translate(ollama_stream, langue_client: str):
    """
    Accumule le texte du stream Ollama, le traduit si nécessaire,
    puis le yield en un seul bloc.
    Retourne aussi le texte complet pour usage ultérieur.
    """
    texte = ""
    for chunk in ollama_stream:
        texte += chunk["message"]["content"]
    # Nettoyer le markdown
    texte = texte.replace("**", "").replace("*", "").strip()
    # Traduction post-génération : une seule fois, texte complet
    if langue_client != "fr" and texte:
        texte = traduire_reponse(texte, langue_client)
        print(f"[RAG] réponse traduite → {langue_client}")
    return texte


def get_response_stream(
    question: str = "",
    product_id: int = None,
    history: list = None,
    context_messages: list = None,
    image_path: str = None,
    image_vector: list = None,
):
    question = question or ""
    if history is None:
        history = []
    if context_messages is None:
        context_messages = []

    # Détecter dès le début pour cohérence dans tous les CAS
     # Détecter dès le début pour cohérence dans tous les CAS
    tutoiement = _detecter_tutoiement(history, question)
 
    # ── Détection de langue + traduction en français pour la recherche ──
    # Les prompts internes (générés par le JS) sont toujours en français → on
    # ne les traduit pas pour éviter une double traduction inutile.
    # La langue originale est conservée pour que le LLM réponde dans celle-ci.
    est_prompt_interne_rapide = any(
        m in question for m in ["Génère un message", "accueille le client", "En une seule phrase"]
    )
    if est_prompt_interne_rapide:
        langue_client = "fr"
        question_fr   = question
    else:
        question_fr, langue_client = normaliser_question(question)
 
    print(f"\n{'='*50}")
    print(f"[RAG] question : {question!r} | langue : {langue_client} | history : {len(history)} messages")
    print(f"{'='*50}\n")
 
    # On travaille avec la version française pour toute la recherche/filtres
    question = question_fr
    # ══════════════════════════════════════════════
    # DÉTECTION PROMPTS INTERNES (pages produit/panier)
    # Ces prompts sont générés automatiquement par le JS,
    # ils ne doivent JAMAIS passer dans le classifier.
    # ══════════════════════════════════════════════
    _MARQUEURS_INTERNES = [
        "accueille le client sur la fiche",
        "mets en avant le point fort de",
        "revient sur",
        "revient encore sur",
        "parle directement au client de son panier",
        "dis directement au client que tu as vu",
        "invite le client à découvrir le catalogue",
        "crée un sentiment d'urgence",
        "encourage-le chaleureusement à passer à l'achat",
        "En une à deux phrases (max",   # ← couvre tous les prompts auto
        "En une seule phrase courte (max",  # ← panier
        "En une phrase (max",            # ← variantes panier
        "encourage le client à valider",
        "fais un commentaire positif sur le choix",
        "dis au client que son panier",
        "félicite le client pour son choix",
        "rappelle au client qu'il regardait",
        "encourage le client à craquer",
        "invite le client à",
        "propose au client de l'aider",
        "encourage le client à explorer",
        "Le client a",                   # ← nouvelles variantes panier
        "dans son panier. En une phrase",
        "tutoie le client",
        "tutoie-le",
    ]
    est_prompt_interne = any(marqueur in question for marqueur in _MARQUEURS_INTERNES)

    mots_accueil = [
        "Génère un message d'accueil",
        "En une seule phrase courte",
        "accueille le client",
        "cite son point fort",
    ]
    if any(mot in question for mot in mots_accueil) or est_prompt_interne:
        intention, confiance = "salutation", 1.0
    else:
        intention, confiance = classifier_intention(question) if question.strip() else ("recherche", 1.0)
        if intention not in ("salutation", "hors_sujet", "livraison", "comparaison") and question.strip():
            try:
                from db_mysql import fetch_all
                from rapidfuzz import fuzz
                rows = fetch_all("SELECT id_shoes, nom, prix, categorie, marque, url_image, description FROM articles")
                question_lower = question.lower()
                for row in rows:
                    nom = (row.get("nom") or "").lower()
                    if nom and fuzz.partial_ratio(nom, question_lower) >= 90:
                        # Charger le produit complet et l'injecter dans l'historique
                        sc = fetch_all(f"SELECT taille, couleur FROM size_color WHERE id_shoes = {row['id_shoes']}")
                        produit_detecte = {
                            "id":          row["id_shoes"],
                            "name":        row["nom"],
                            "price":       row["prix"],
                            "categorie":   row.get("categorie", ""),
                            "marque":      row.get("marque", ""),
                            "url_image":   row.get("url_image", ""),
                            "description": row.get("description", ""),
                            "tailles":     list({x["taille"] for x in sc if x.get("taille")}),
                            "couleurs":    list({x["couleur"] for x in sc if x.get("couleur")}),
                        }
                        # Injecter comme si l'assistant avait déjà présenté ce produit
                        history = history + [{"role": "assistant", "content": "", "products": [produit_detecte]}]
                        # Ne pas override en suivi si l'utilisateur veut ajouter au panier
                        if not user_wants_cart(question, history):
                            intention = "suivi"
                            confiance = 1.0
                            print(f"[INTENTION] override → suivi (nom exact détecté : {row['nom']})")
                        else:
                            print(f"[INTENTION] nom exact détecté ({row['nom']}) mais intention panier conservée")
                        break
            except Exception as e:
                print(f"[INTENTION] override nom exact échoué : {e}")
    """
    _MOTS_COMPARAISON = [
    "comparatif", "comparer", "compare", "comparaison",
    "différence", "différences", "versus", "vs", "côte à côte"
    ]
    if any(mot in question.lower() for mot in _MOTS_COMPARAISON):
        intention = "comparaison"
        confiance = 1.0
        print(f"[INTENTION] override → comparaison (mot-clé détecté)")
    """
    # Si image sans texte → recherche directe
    if (image_path or image_vector) and not question.strip():
        intention = "recherche"
        confiance = 1.0
        print("[INTENTION] image seule → recherche")
    # Si image avec texte → on garde l'intention détectée SAUF hors_sujet/livraison
    elif (image_path or image_vector) and intention in ("hors_sujet", "livraison", "panier"):
        intention = "recherche"
        confiance = 1.0
        print(f"[INTENTION] image + texte → intention {intention} ignorée → recherche")


    # ── Garde-fou : si le classifier dit hors_sujet mais que la question
    # contient des mots clairement liés aux chaussures → on force recherche
    _MOTS_CHAUSSURES = [
        "chaussure", "basket", "sandale", "botte", "bottine", "mocassin",
        "espadrille", "talon", "running", "trail", "randonn\u00e9e", "sneaker",
        "slip-on", "indoor", "paire", "pointure", "taille", "semelle",
        "plage", "\u00e9t\u00e9", "hiver", "sport", "confort", "marche", "travail",
        "soir\u00e9e", "mariage", "festival", "gym", "danse", "cuir", "vegan",
        "imperm\u00e9able", "l\u00e9g\u00e8re", "l\u00e9g\u00e8res", "respirant",
    ]
    if intention == "hors_sujet" and any(mot in question.lower() for mot in _MOTS_CHAUSSURES):
        intention = "recherche"
        confiance = 1.0
        print(f"[INTENTION] override hors_sujet \u2192 recherche (mot-cl\u00e9 chaussures d\u00e9tect\u00e9)")

    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    # CAS 1 \u2014 HORS SUJET
    # \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
    if intention == "hors_sujet":
        print("[CAS] 1 — hors_sujet")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": get_system_prompt(tutoiement)},
            *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
            {"role": "user", "content": (
                f"L'utilisateur dit : « {question} »\n"
                "C'est hors sujet pour une boutique de chaussures. "
                f"Réponds poliment que tu es spécialisé chaussures et recentre. "
                f"{_LIMITES['hors_sujet']['consigne']}"
            )},
        ]
        try:
            stream = ollama.chat(
                model=LLM_MODEL, messages=messages, stream=True,
                options={
                    "num_ctx":     _calculer_ctx(history, 1024),
                    "num_predict": _LIMITES["hors_sujet"]["num_predict"],
                    "temperature": 0.7,
                },
            )
            yield _stream_and_translate(stream, langue_client)
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1, "langue": langue_client}
        return

    # ════════════════════════════════════════════
    # ── Override PRIORITAIRE : si le dernier message bot posait une question taille/couleur
    # s'applique AVANT tous les CAS, même salutation
    _MOTS_QUESTION_TAILLE_COULEUR = [
        "quelle taille", "quelle pointure", "quelle couleur",
        "taille souhaitée", "couleur souhaitée", "taille préférée",
        "quelle est ta taille", "quelle est votre taille",
        "tu chausses du", "vous chaussez du",
        "tu préfères quelle couleur", "tu veux quelle couleur",
        "tu veux quelle taille", "tu veux quelle pointure",
        "ta pointure", "votre pointure",
        "pointure (disponibles", "couleur (disponibles",
        "quelle est ta pointure", "quelle est votre pointure",
    ]
    if history:
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                bot_text = msg.get("content", "").lower()
                if any(kw in bot_text for kw in _MOTS_QUESTION_TAILLE_COULEUR):
                    intention = "suivi"
                    confiance = 1.0
                    print(f"[INTENTION] override → suivi (bot posait une question taille/couleur)")
                break

    # CAS 1b — SALUTATION
    # ════════════════════════════════════════════
    # CAS 1b — SALUTATION
    # CAS 1b — SALUTATION / PROMPT INTERNE
    if intention == "salutation":
        print("[CAS] 1b — salutation")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        has_prior_exchange = any(m["role"] == "assistant" for m in history)
        if has_prior_exchange and "Ne commence pas par Bonjour" not in question:
            question_llm = question + " (Ne commence pas par Bonjour, tu as déjà salué le client.)"
        else:
            question_llm = question

        # Si c'est un prompt interne, on passe directement la consigne au LLM
        # sans polluer avec l'historique de produits
        if est_prompt_interne:
            messages = [
                {"role": "system", "content": get_system_prompt(tutoiement)},
                {"role": "user", "content": question_llm},
            ]
        else:
            messages = [
                {"role": "system", "content": get_system_prompt(tutoiement)},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:] if m["role"] in ("user", "assistant")],
                {"role": "user", "content": question_llm},
            ]

        # Les prompts internes (accueil page produit/panier) ont un format très contraint.
        # On réduit la température et le nombre de tokens pour éviter les hallucinations.
        gen_options = (
            {"num_ctx": 2048, "num_predict": 120, "temperature": 0.6}
            if est_prompt_interne
            else {"num_ctx": 2048, "num_predict": 120, "temperature": 0.8}
        )

        try:
            stream = ollama.chat(
                model=LLM_MODEL, messages=messages, stream=True,
                options=gen_options,
            )
            yield _stream_and_translate(stream, langue_client)
        except Exception as e:
            yield "Je suis votre conseiller PairIA, posez-moi vos questions 👟"

        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1, "langue": langue_client}
        return
        
    # ════════════════════════════════════════════
    # CAS 2 — LIVRAISON
    # ════════════════════════════════════════════
    if intention == "livraison":
        print("[CAS] 2 — livraison")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": get_system_prompt(tutoiement)},
            *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
            {"role": "user", "content": (
                f"L'utilisateur demande : « {question} »\n"
                "Tu n'as pas accès aux infos livraison/retours/stock. "
                f"Dis-le honnêtement et propose de l'aider à trouver des chaussures. "
                f"{_LIMITES['livraison']['consigne']}"
            )},
        ]
        try:
            stream = ollama.chat(
                model=LLM_MODEL, messages=messages, stream=True,
                options={
                    "num_ctx":     _calculer_ctx(history, 1024),
                    "num_predict": _LIMITES["livraison"]["num_predict"],
                    "temperature": 0.5,
                },
            )
            yield _stream_and_translate(stream, langue_client)
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1, "langue": langue_client}
        return

    # ════════════════════════════════════════════
    # CAS 3 — PANIER
    # ════════════════════════════════════════════
    if (intention == "panier" or user_wants_cart(question, history)) and \
       (user_wants_cart(question, history) or (intention == "panier" and confiance >= 0.75)):
        print(f"[CAS] 3 — panier (intention={intention}, user_wants_cart={user_wants_cart(question, history)})")
        produits_historique = _produits_depuis_historique(history)
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        # Extraire taille et couleur dès maintenant pour adapter la consigne
        filtres_panier = extraire_filtres(question, history)
        taille_panier  = filtres_panier.get("pointure")
        couleur_panier = filtres_panier.get("couleur")

        if produits_historique:
            contexte_produits = "\n".join([
                f"- {p['name']} ({p['price']}€) | tailles: {', '.join(str(t) for t in p.get('tailles', []))} | couleurs: {', '.join(p.get('couleurs', []))}"
                for p in produits_historique
            ])
            # Construire la consigne selon ce qu'on sait déjà
            manque = []
            if not taille_panier and any(p.get("tailles") for p in produits_historique):
                manque.append("la pointure")
            if not couleur_panier and any(p.get("couleurs") for p in produits_historique):
                manque.append("la couleur")

            if manque:
                consigne_panier = (
                    f"Identifie le produit voulu, confirme-le et demande {' et '.join(manque)} en une seule question courte. "
                    f"{_LIMITES['panier']['consigne']}"
                )
            else:
                consigne_panier = (
                    f"Identifie lequel il veut, confirme chaleureusement et cite son nom exact. "
                    f"{_LIMITES['panier']['consigne']}"
                )

            messages = [
                {"role": "system", "content": get_system_prompt(tutoiement)},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"Produits disponibles :\n{contexte_produits}\n\n"
                    f"L'utilisateur dit : « {question} »\n"
                    f"{consigne_panier}"
                )},
            ]
        else:
            messages = [
                {"role": "system", "content": get_system_prompt(tutoiement)},
                {"role": "user", "content": (
                    f"L'utilisateur dit : « {question} »\n"
                    f"Aucun produit présenté. Demande ce qu'il recherche. "
                    f"{_LIMITES['panier']['consigne']}"
                )},
            ]

        texte_complet = ""
        try:
            stream = ollama.chat(
                model=LLM_MODEL, messages=messages, stream=True,
                options={
                    "num_ctx":     _calculer_ctx(history, 1024),
                    "num_predict": _LIMITES["panier"]["num_predict"],
                    "temperature": 0.5,
                },
            )
            # Accumuler en français pour détecter les produits mentionnés
            for chunk in stream:
                texte_complet += chunk["message"]["content"]
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"

        produit_cible = None
        if produits_historique:
            mentionnes    = _produits_mentionnes(texte_complet, produits_historique)
            produit_cible = mentionnes[0] if mentionnes else produits_historique[0]

        # Traduire après détection des produits (la détection se fait sur le texte FR)
        texte_traduit = texte_complet
        if langue_client != "fr" and texte_complet.strip():
            texte_traduit = traduire_reponse(texte_complet, langue_client)
        yield texte_traduit

        produit_cible = None
        if produits_historique:
            mentionnes    = _produits_mentionnes(texte_complet, produits_historique)
            produit_cible = mentionnes[0] if mentionnes else produits_historique[0]

        # Normaliser la couleur contre les couleurs réelles du produit
        if couleur_panier and produit_cible:
            couleurs_produit = produit_cible.get("couleurs", [])
            famille = _couleurs_famille(couleur_panier)
            # Chercher d'abord une correspondance exacte
            match_exact = next((c for c in couleurs_produit if couleur_panier.lower() in c.lower() or c.lower().startswith(couleur_panier.lower())), None)
            # Sinon chercher dans la famille de couleurs
            match_famille = next((c for c in couleurs_produit if c in famille), None)
            if match_exact:
                couleur_panier = match_exact
            elif match_famille:
                print(f"[CAS] 3 — couleur normalisée via famille : {couleur_panier} → {match_famille}")
                couleur_panier = match_famille

        print(f"[CAS] 3 — taille={taille_panier} | couleur={couleur_panier}")

        yield {
            "type":            "products_final",
            "products":        [produit_cible] if produit_cible else [],
            "action":          "add_to_cart" if produit_cible else None,
            "product_id":      produit_cible["id"] if produit_cible else None,
            "quantity":        1,
            "taille":          taille_panier,
            "couleur":         couleur_panier,
            # Confirmation nécessaire seulement si une info manque encore
            "confirm_required": not (taille_panier and couleur_panier),
            "langue":           langue_client,
        }
        return

    # CAS 4 — SUIVI
    if intention == "suivi":
        print("[CAS] 4 — suivi")
        produit_suivi = None
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("products"):
                produit_suivi = msg["products"][0]
                break
        if not produit_suivi:
            for msg in context_messages:
                if msg.get("role") == "system" and "consulte actuellement" in msg.get("content", ""):
                    import re
                    match = re.search(r'consulte actuellement\s*:\s*"([^"]+)"', msg["content"])
                    if match:
                        nom_produit = match.group(1)
                        print(f"[CAS] 4 — produit trouvé via contexte system : {nom_produit}")
                        try:                          # ← AJOUT
                            from db_mysql import fetch_all
                            rows = fetch_all(
                                f"SELECT id_shoes, nom, prix, categorie, marque, url_image, description FROM articles "
                                f"WHERE nom = '{nom_produit.replace(chr(39), chr(39)*2)}' LIMIT 1"
                            )
                            print(f"[CAS] 4 — rows DB : {rows}")   # ← AJOUT
                            if rows:
                                r = rows[0]
                                sc = fetch_all(
                                    f"SELECT taille, couleur FROM size_color WHERE id_shoes = {r['id_shoes']}"
                                )
                                produit_suivi = {
                                    "id":          r["id_shoes"],
                                    "name":        r["nom"],
                                    "price":       r["prix"],
                                    "categorie":   r.get("categorie", ""),
                                    "marque":      r.get("marque", ""),
                                    "url_image":   r.get("url_image", ""),
                                    "description": r.get("description", ""),
                                    "tailles":     list({x["taille"] for x in sc if x.get("taille")}),
                                    "couleurs":    list({x["couleur"] for x in sc if x.get("couleur")}),
                                }
                                print(f"[CAS] 4 — produit_suivi construit : {produit_suivi['name']}")  # ← AJOUT
                        except Exception as e:        # ← AJOUT
                            import traceback          # ← AJOUT
                            print(f"[CAS] 4 — ERREUR DB : {traceback.format_exc()}")  # ← AJOUT
                    break

        # Utiliser tous les produits du dernier message assistant
        # (pas seulement produit_suivi qui ne prend que le premier)
        produits_depuis_hist = _produits_depuis_historique(history)
        produits_a_utiliser = produits_depuis_hist if produits_depuis_hist else ([produit_suivi] if produit_suivi else [])

        # Filtrer par couleur si demandée dans la question
        filtres_suivi  = extraire_filtres(question, history)
        couleur_suivi  = filtres_suivi.get("couleur")
        couleur_originale = couleur_suivi  # sauvegarder avant normalisation
        taille_suivi   = filtres_suivi.get("pointure")

        # Normaliser la couleur contre les couleurs réelles des produits AVANT le filtrage
        if couleur_suivi and produits_a_utiliser:
            for p in produits_a_utiliser:
                for c in p.get("couleurs", []):
                    if couleur_suivi.lower() in c.lower() or c.lower().startswith(couleur_suivi.lower()):
                        couleur_suivi = c
                        break
                else:
                    continue
                break

        if couleur_suivi:
            # Normaliser via famille de couleurs : "Rouge" peut matcher "Bordeaux"
            famille = _couleurs_famille(couleur_suivi)
            produits_couleur = [
                p for p in produits_a_utiliser
                if any(c in famille for c in p.get("couleurs", []))
            ]
            # Normaliser couleur_suivi vers la valeur exacte du produit si possible
            if produits_couleur:
                for p in produits_couleur:
                    for c in p.get("couleurs", []):
                        if c in famille and c != couleur_suivi:
                            print(f"[CAS] 4 — couleur normalisée : {couleur_suivi} → {c}")
                            couleur_suivi = c
                            break
                    break
            print(f"[CAS] 4 — filtre couleur={couleur_suivi} : {len(produits_couleur)}/{len(produits_a_utiliser)} produits")

            if not produits_couleur:
                # Aucun des produits présentés n'a cette couleur → nouvelle recherche Qdrant
                print(f"[CAS] 4 — 0 résultat en {couleur_suivi} → fallback recherche Qdrant")
                cat_hist = extraire_filtres("", history).get("categorie")

                # 1er essai : avec couleur + catégorie
                filtres_nouveaux = {"couleur": couleur_suivi}
                if cat_hist:
                    filtres_nouveaux["categorie"] = cat_hist
                vec_fallback = model.encode(question).tolist()
                produits_fallback, contexte_fallback = _recherche_qdrant(
                    question_vector=vec_fallback,
                    question=question,
                    filtres=filtres_nouveaux,
                    categories_candidates=[cat_hist] if cat_hist else [],
                    history=history,
                )

                # 2ème essai : sans filtre couleur (montrer ce qui est dispo dans la catégorie)
                if not produits_fallback and cat_hist:
                    print(f"[CAS] 4→6 — 0 résultat en {couleur_suivi}, recherche sans couleur")
                    produits_fallback, contexte_fallback = _recherche_qdrant(
                        question_vector=vec_fallback,
                        question=question,
                        filtres={"categorie": cat_hist},
                        categories_candidates=[cat_hist],
                        history=history,
                    )
                    if produits_fallback:
                        contexte_fallback = (
                            f"IMPORTANT : aucun modèle disponible en {couleur_suivi}. "
                            f"Voici les modèles disponibles dans cette catégorie avec leurs couleurs. "
                            f"Dis-le clairement au client et propose les couleurs disponibles :"
                        )

                if produits_fallback:
                    print(f"[CAS] 4→6 — {len(produits_fallback)} produits trouvés en {couleur_suivi}")
                    # Rediriger vers CAS 6 directement
                    yield {"products": [], "action": None, "product_id": None, "quantity": 1}
                    nb_a = min(3, len(produits_fallback))
                    if cat_hist:
                        p_cat = [p for p in produits_fallback if p["categorie"] == cat_hist]
                        p_autres = [p for p in produits_fallback if p["categorie"] != cat_hist]
                        produits_fallback = (p_cat + p_autres)[:nb_a]
                    else:
                        produits_fallback = produits_fallback[:nb_a]
                    # ✅ CORRIGÉ — langue_client ajouté
                    prompt_fb = build_prompt(
                        question=question,
                        produits=produits_fallback,
                        genre=_extraire_genre(history, question),
                        contexte_filtres=contexte_fallback,
                        langue=langue_client,
                    )
                    msgs_fb = [
                        {"role": "system", "content": get_system_prompt(tutoiement)},
                        *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                        {"role": "user", "content": prompt_fb},
                    ]
                    texte_fb = ""
                    try:
                        stream_fb = ollama.chat(model=LLM_MODEL, messages=msgs_fb, stream=True,
                            options={"num_ctx": _calculer_ctx(history), "num_predict": 350, "temperature": 0.7})
                        for chunk in stream_fb:
                            texte_fb += chunk["message"]["content"]
                    except Exception as e:
                        yield f"Erreur : {e}"
                    produits_mentionnes_fb = _produits_mentionnes(texte_fb, produits_fallback)
                    # Traduire après détection des produits
                    if langue_client != "fr" and texte_fb.strip():
                        texte_fb = traduire_reponse(texte_fb, langue_client)
                    yield texte_fb
                    produits_finaux_fb = produits_mentionnes_fb or produits_fallback
                    yield {
                        "type":          "products_final",
                        "products":      produits_finaux_fb,
                        "action":        None,
                        "product_id":    None,
                        "quantity":      1,
                        "tutoiement":    tutoiement,
                        "show_products": True,
                        "langue":        langue_client,
                    }
                    return
                else:
                    # Vraiment rien → laisser le LLM expliquer
                    produits_avec = []
                    produits_sans = produits_a_utiliser
            else:
                produits_avec = produits_couleur
                produits_sans = [p for p in produits_a_utiliser if couleur_suivi not in p.get("couleurs", [])]
        else:
            produits_avec = produits_a_utiliser
            produits_sans = []

        # Si intention panier avec info manquante → demander directement
        if produits_a_utiliser and user_wants_cart(question, history):
            produit_cible_panier = (produits_avec[0] if produits_avec else produits_a_utiliser[0])
            manque = []
            if not taille_suivi and produit_cible_panier.get("tailles"):
                tailles_dispo = ", ".join(str(t) for t in produit_cible_panier["tailles"])
                manque.append(f"pointure (disponibles : {tailles_dispo})")
            if not couleur_suivi and produit_cible_panier.get("couleurs"):
                couleurs_dispo = ", ".join(produit_cible_panier["couleurs"])
                manque.append(f"couleur (disponibles : {couleurs_dispo})")

            if manque:
                yield {"products": [], "action": None, "product_id": None, "quantity": 1}
                question_manque = (
                    f"Le client veut ajouter {produit_cible_panier['name']} au panier. "
                    f"Il manque : {' et '.join(manque)}. "
                    f"Demande-lui {'ces informations' if len(manque) > 1 else 'cette information'} "
                    f"en une seule question courte et naturelle. {_LIMITES['panier']['consigne']}"
                )
                messages_manque = [
                    {"role": "system", "content": get_system_prompt(tutoiement)},
                    *[{"role": m["role"], "content": m["content"]} for m in history[-4:]],
                    {"role": "user", "content": question_manque},
                ]
                texte_manque = ""
                try:
                    stream = ollama.chat(
                        model=LLM_MODEL, messages=messages_manque, stream=True,
                        options={"num_ctx": 1024, "num_predict": 80, "temperature": 0.4},
                    )
                    for chunk in stream:
                        texte_manque += chunk["message"]["content"]
                    if langue_client != "fr" and texte_manque.strip():
                        texte_manque = traduire_reponse(texte_manque, langue_client)
                    yield texte_manque
                except Exception as e:
                    info = " et ".join(m.split(" (")[0] for m in manque)
                    yield f"Quelle {info} souhaites-tu pour les {produit_cible_panier['name']} ?"
                yield {
                    "type": "products_final", "products": [], "action": None,
                    "product_id": None, "quantity": 1, "show_products": False,
                    "langue": langue_client,
                }
                return

        if produits_a_utiliser:
            yield {"products": [], "action": None, "product_id": None, "quantity": 1}

            def _fmt_produit(p):
                return (
                    f"- {p['name']} ({p.get('marque', '')}, {p['price']}€)"
                    f" | Tailles : {', '.join(str(t) for t in p.get('tailles', []))}"
                    f" | Couleurs : {', '.join(p.get('couleurs', []))}"
                )

            if couleur_suivi and (produits_avec or produits_sans):
                lignes = []
                if produits_avec:
                    lignes.append(f"Disponibles en {couleur_suivi} :")
                    lignes += [_fmt_produit(p) for p in produits_avec]
                if produits_sans:
                    lignes.append(f"Non disponibles en {couleur_suivi} :")
                    lignes += [_fmt_produit(p) for p in produits_sans]
                contexte_produits = "\n".join(lignes)
            else:
                contexte_produits = "\n".join([_fmt_produit(p) for p in produits_a_utiliser])

            # Construire une note explicative si la couleur a été normalisée
            note_couleur = ""
            if couleur_suivi and couleur_originale and couleur_suivi != couleur_originale:
                note_couleur = (
                    f"Note : le client demande '{couleur_originale}'. "
                    f"'{couleur_suivi}' est la nuance disponible la plus proche. "
                    f"Présente-la comme telle.\n"
                )

            messages = [
                {"role": "system", "content": get_system_prompt(tutoiement)},
                *[{"role": m["role"], "content": m["content"]} for m in history[-4:]],
                {"role": "user", "content": (
                    f"{note_couleur}"
                    f"Produits présentés :\n{contexte_produits}\n\n"
                    f"Question : {question}\n"
                    f"Réponds en 1-2 phrases naturelles en te basant UNIQUEMENT sur les informations ci-dessus. "
                    f"Ne mentionne AUCUN autre produit. "
                    f"{_LIMITES['suivi']['consigne']}"
                )},
            ]
            try:
                stream = ollama.chat(
                    model=LLM_MODEL, messages=messages, stream=True,
                    options={
                        "num_ctx":     _calculer_ctx(history),
                        "num_predict": _LIMITES["suivi"]["num_predict"],
                        "temperature": 0.5,
                    },
                )
                yield _stream_and_translate(stream, langue_client)
            except Exception as e:
                yield f"Erreur Mistral : {str(e)}"
            # Si bot posait une question taille/couleur → déclencher ajout panier
            dernier_bot = next((m.get("content","") for m in reversed(history) if m.get("role")=="assistant"), "")
            # Déclencher add_to_cart seulement si le bot posait une question explicite
            # sur la taille/couleur DANS LE CADRE d'un ajout panier (pas juste informatif)
            _MOTS_QUESTION_AJOUT = [
                "quelle taille", "quelle pointure", "quelle couleur",
                "ta pointure", "ta taille", "ta couleur",
                "tu veux quelle", "choisis", "pointure (disponibles",
                "couleur (disponibles", "quelle est ta pointure",
            ]
            action_suivi = "add_to_cart" if (taille_suivi or couleur_suivi) and any(
                kw in dernier_bot.lower() for kw in _MOTS_QUESTION_AJOUT
            ) else None
            produits_finaux = produits_avec if (couleur_suivi and produits_avec) else produits_a_utiliser
            produit_cible_suivi = produits_finaux[0] if produits_finaux else None
            # Afficher les cartes si on a filtré par couleur (pour que l'utilisateur voie ce qui est dispo)
            afficher_cartes = bool(couleur_suivi and produits_avec)
            print(f"[CAS] 4 — taille={taille_suivi} | couleur={couleur_suivi} | action={action_suivi}")

            # Vérifier si toutes les infos nécessaires sont présentes pour l'ajout
            infos_completes = bool(action_suivi) and (
                not produit_cible_suivi or (
                    (taille_suivi or not produit_cible_suivi.get("tailles")) and
                    (couleur_suivi or not produit_cible_suivi.get("couleurs"))
                )
            )

            yield {
                "type":             "products_final",
                "products":         produits_finaux,
                "action":           action_suivi,
                "product_id":       produit_cible_suivi["id"] if produit_cible_suivi and action_suivi else None,
                "quantity":         1,
                "taille":           taille_suivi,
                "couleur":          couleur_suivi,
                "show_products":    afficher_cartes,
                "confirm_required": True,
            }
            return
        print("[CAS] 4 — suivi sans produits → fallback recherche")
    # ════════════════════════════════════════════
    # CAS 5 — COMPARAISON
    # ════════════════════════════════════════════
    if intention == "comparaison":
        print("[CAS] 5 — comparaison")
        produits_historique = _produits_depuis_historique(history)

        # Fallback si pas assez de produits en historique
        if len(produits_historique) < 2:
            produits_cites = _chercher_produits_cites(question)
            if len(produits_cites) >= 2:
                produits_historique = produits_cites
                print(f"[CAS] 5 — produits cités trouvés : {[p['name'] for p in produits_cites]}")

        if len(produits_historique) >= 2:
            resultat = _identifier_produits_a_comparer(question, produits_historique)
            if resultat is None:
                print("[CAS] 5 — pas assez de produits → fallback Qdrant")
            else:
                p1, p2 = resultat

                # Résumés courts en parallèle (max 15 mots)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    fut_r1 = executor.submit(_resumer_description, p1, langue_client)
                    fut_r2 = executor.submit(_resumer_description, p2, langue_client)
                    p1["resume"] = fut_r1.result()
                    p2["resume"] = fut_r2.result()

                yield {"products": [], "action": None, "product_id": None, "quantity": 1}
                intro = f"Bien sûr, voici le comparatif {p1['name']} vs {p2['name']} :"
                if langue_client != "fr":
                    intro = traduire_reponse(intro, langue_client)
                yield intro
                yield {
                    "type":       "products_final",
                    "products":   [p1, p2],
                    "action":     None,
                    "product_id": None,
                    "quantity":   1,
                    "layout":     "comparison",
                    "langue":     langue_client,
                }
                return

        print("[CAS] 5 — pas assez de produits → fallback Qdrant")

    # ════════════════════════════════════════════
    # CAS 6 — RECHERCHE & RECOMMANDATION
    # ════════════════════════════════════════════
    print("[CAS] 6 — recherche/recommandation")

    # 1. Analyse parallèle
    question_vector, is_image_search, filtres, categories_candidates = \
        _analyser_question(question, history, image_path, image_vector)

    # 2. Qdrant
    produits_trouves, contexte_filtres = _recherche_qdrant(
        question_vector, question, history, filtres, categories_candidates
    )

    # Aucun produit
    if not produits_trouves:
        print("[CAS] 6 — aucun produit → réponse Mistral directe")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        # ✅ Traduire le contexte_filtres pour éviter les noms de catégories en français dans la réponse
        if langue_client != "fr" and contexte_filtres:
            contexte_filtres = traduire_reponse(contexte_filtres, langue_client)

        messages = [
            {"role": "system", "content": get_system_prompt(tutoiement)},
            *[{"role": m["role"], "content": m["content"]} for m in history[-10:]],
            {"role": "user", "content": (
                f"{contexte_filtres}\n"
                "IMPORTANT : tu ne dois proposer AUCUN produit inventé. "
                "Ne cite aucun nom de produit, aucun prix, aucune marque. "
                "Explique simplement ce qui n'est pas disponible et demande à l'utilisateur "
                f"s'il veut modifier ses critères.\nQuestion : {question}\n"
                f"{_LIMITES['recherche']['consigne']}"
            )},
        ]
        try:
            stream = ollama.chat(
                model=LLM_MODEL, messages=messages, stream=True,
                options={
                    "num_ctx":     _calculer_ctx(history),
                    "num_predict": _LIMITES["recherche"]["num_predict"],
                    "temperature": 0.7,
                },
            )
            yield _stream_and_translate(stream, langue_client)
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1, "langue": langue_client}
        return

    # 3. Prompt Mistral
    genre       = _extraire_genre(history, question)
    tutoiement  = _detecter_tutoiement(history, question)
    nb_produits = _nb_produits_from_history(history,intention)
    limite      = _LIMITES.get(intention, _LIMITES["recherche"])

    # ✅ Traduire le contexte_filtres pour éviter les noms de catégories en français dans la réponse
    if langue_client != "fr" and contexte_filtres:
        contexte_filtres = traduire_reponse(contexte_filtres, langue_client)
    print(f"[CAS] 6 — {len(produits_trouves)} produits | genre={genre} | nb_à_afficher={nb_produits}")
    if is_image_search:
        produits_trouves = produits_trouves[:3]
        nb_a_presenter   = 3
        print(f"[CAS] 6 — recherche image → top 3 Qdrant forcé")
    else:
        nb_a_presenter = min(nb_produits, len(produits_trouves))
        # Si on a assez de produits dans la catégorie principale, on ne donne
        # que ceux-là au LLM — il ne peut pas "déborder" sur les similaires.
        if categories_candidates:
            cat_principale = categories_candidates[0]
            produits_cat = [p for p in produits_trouves if p["categorie"] == cat_principale]
            if len(produits_cat) >= nb_a_presenter:
                produits_trouves = produits_cat
                print(f"[CAS] 6 — LLM limité aux {len(produits_trouves)} produits '{cat_principale}'")
            else:
                # Pas assez dans la catégorie principale : on complète avec les similaires
                # mais on tronque à nb_a_presenter pour que le LLM n'ait pas le choix
                produits_autres = [p for p in produits_trouves if p["categorie"] != cat_principale]
                produits_trouves = (produits_cat + produits_autres)[:nb_a_presenter]
                print(f"[CAS] 6 — LLM forcé : {len(produits_cat)} '{cat_principale}' + {len(produits_trouves) - len(produits_cat)} similaires")
    description_visuelle = ""
    if is_image_search and produits_trouves:
       description_visuelle = (
        "[Photo reçue] Présente ces 3 produits visuellement similaires à la photo. "
        "Sois naturel et enthousiaste, comme un vendeur qui conseille un ami. "
        "1 phrase par produit, pas de liste à puces, pas de 'Voici'."
    )
    suffixe_recommandation = ""
    if intention == "recommandation":
        suffixe_recommandation = (
            "\nL'utilisateur demande un conseil personnalisé. "
            "Donne ton avis clair sur le meilleur choix et explique pourquoi."
        )

    nb_produits = _nb_produits_from_history(history, intention)
    nb_a_presenter = min(nb_produits, len(produits_trouves))
    consigne_nb = (
        f"Les produits ci-dessus sont les plus adaptés disponibles — présente-les, "
        f"ne dis JAMAIS qu'il n'y a pas de stock ou que le catalogue est vide. "
        f"Présente exactement {nb_a_presenter} produit(s) du catalogue ci-dessus. "
        f"Ne mentionne aucun autre produit."
    ) if nb_a_presenter > 0 else ""

    question_complete = (
        f"{description_visuelle}{question or ''}"
        f"{suffixe_recommandation}\n{limite['consigne']} {consigne_nb}"
    )

    # ✅ langue_client déjà bien passé ici (inchangé)
    prompt = build_prompt(
        question=question_complete,
        produits=produits_trouves,
        product_id=product_id,
        genre=genre,
        is_image_search=is_image_search,
        contexte_filtres=contexte_filtres,
        langue=langue_client,
    )

    messages = [{"role": "system", "content": get_system_prompt(tutoiement)}]
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})

    yield {"products": [], "action": None, "product_id": None, "quantity": 1}

    texte_complet = ""
    try:
        stream = ollama.chat(
            model=LLM_MODEL, messages=messages, stream=True,
            options={
                "num_ctx":     _calculer_ctx(history),
                "num_predict": limite["num_predict"],
                "temperature": 0.4 if is_image_search else 0.7,
            },
        )
        buffer = ""
        for chunk in stream:
            token = chunk["message"]["content"]
            buffer += token
            # Supprimer le markdown au fil du stream
            while len(buffer) >= 2:
                if buffer[:2] == "**":
                    buffer = buffer[2:]
                elif buffer[0] == "*" and buffer[1] != "*":
                    buffer = buffer[1:]
                else:
                    texte_complet += buffer[0]
                    buffer = buffer[1:]
        # Vider le buffer restant
        clean = buffer.replace("**", "").replace("*", "")
        texte_complet += clean

    except Exception as e:
        yield f"Erreur Mistral : {str(e)}"
        return

    # ✅ Traduction post-génération : une seule fois, texte complet, zéro fuite
    if langue_client != "fr" and texte_complet.strip():
        texte_complet = traduire_reponse(texte_complet, langue_client)
        print(f"[RAG] réponse traduite → {langue_client}")

    # Yield du texte final (en un seul bloc — le frontend streame déjà le typing indicator)
    yield texte_complet

    produits_affiches = _produits_mentionnes(texte_complet, produits_trouves)
    action = "add_to_cart" if user_wants_cart(question, history) and produits_affiches else None

    print(f"[CAS] 6 — affichés : {[p['name'] for p in produits_affiches[:nb_produits]]}")
    yield {
        "type":        "products_final",
        "products":    produits_affiches[:nb_a_presenter],
        "action":      action,
        "product_id":  produits_affiches[0]["id"] if produits_affiches and action else None,
        "quantity":    1,
        "tutoiement":  tutoiement,
    }