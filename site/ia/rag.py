# ia/rag.py
import sys
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from database import qdrant
from llm_prompt import build_prompt, SYSTEM_PROMPT
from image_search import model
from intention_classifier import classifier_intention
from filters import extraire_filtres, appliquer_filtres, user_wants_cart, DB
from PIL import Image
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue, MatchAny, MinShould


# ══════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════

def _nb_produits_from_history(history: list) -> int:
    nb_echanges = len(history) // 2
    if nb_echanges == 0:
        return 3
    elif nb_echanges <= 2:
        return 2
    else:
        return 1


def _extraire_genre(history: list, question: str) -> str | None:
    from filters import _chercher_genre
    texte_complet = question.lower()
    for msg in history:
        if msg["role"] == "user":
            texte_complet += " " + msg["content"].lower()
    return _chercher_genre(texte_complet)

def _chercher_produit_par_nom(question: str) -> list:
    """
    Détecte si l'utilisateur cite un nom de produit précis dans sa question.
    Cherche dans MySQL par correspondance floue sur le nom.
    Retourne une liste avec le produit trouvé, ou [] si rien.
    """
    from db_mysql import fetch_all
    from rapidfuzz import fuzz

    question_lower = question.lower().strip()

    # Récupère tous les noms de produits
    try:
        rows = fetch_all("SELECT id_shoes, nom, prix, categorie, marque, url_image, description FROM articles")
    except Exception as e:
        print(f"[NOM_EXACT] Erreur DB : {e}")
        return []

    meilleur_score = 0
    meilleur_produit = None

    for row in rows:
        nom = (row.get("nom") or "").lower()
        if not nom:
            continue

        # Score de similarité entre la question et le nom du produit
        score = fuzz.partial_ratio(nom, question_lower)

        # Seuil élevé (88) pour éviter les faux positifs
        if score > meilleur_score and score >= 88:
            meilleur_score = score
            meilleur_produit = row

    if not meilleur_produit:
        return []

    print(f"[NOM_EXACT] '{meilleur_produit['nom']}' détecté (score={meilleur_score})")

    # Récupère tailles et couleurs depuis size_color
    try:
        sc = fetch_all(
            f"SELECT taille, couleur FROM size_color WHERE id_shoes = {meilleur_produit['id_shoes']}"
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
    for msg in reversed(history):
        if msg["role"] == "assistant" and "products" in msg:
            produits = msg["products"]
            if produits:
                print(f"[HISTORIQUE] ✅ {len(produits)} produit(s) : {[p['name'] for p in produits]}")
                return produits
    print(f"[HISTORIQUE] ❌ Aucun produit — {len(history)} msgs, "
          f"clés assistant : {[list(m.keys()) for m in history if m['role'] == 'assistant']}")
    return []


# ══════════════════════════════════════════════
# LLM HELPERS — appels Mistral rapides
# ══════════════════════════════════════════════

def _llm_enrichir_question(question: str, history: list) -> str:
    """
    Demande à Mistral de reformuler la question en mots-clés riches
    pour améliorer la recherche vectorielle Qdrant.
    Ex: "chaussures de soirée" → "talons sandales élégantes habillées soirée chic"
    """
    # Contexte des 2 derniers échanges pour tenir compte de la conversation
    contexte = ""
    msgs_user = [m["content"] for m in history if m["role"] == "user"][-2:]
    if msgs_user:
        contexte = f"Contexte conversation : {' / '.join(msgs_user)}\n"

    prompt = (
        f"{contexte}"
        f"Reformule cette demande en 8 à 12 mots-clés descriptifs pour rechercher des chaussures.\n"
        f"Inclus : style, usage, matière, type de chaussure, occasion si pertinent.\n"
        f"Demande : \"{question}\"\n"
        f"Réponds UNIQUEMENT en français, avec les mots-clés séparés par des espaces, sans ponctuation."
    )
    try:
        resp = ollama.chat(
            model="mistral",
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 40, "temperature": 0},
        )
        enrichie = resp["message"]["content"].strip()
        print(f"[LLM] question enrichie : {enrichie!r}")
        return enrichie
    except Exception as e:
        print(f"[LLM] enrichissement échoué : {e} → fallback question originale")
        return question


def _llm_categories_candidates(question: str, history: list) -> list[str]:
    """
    Demande à Mistral quelles catégories sont pertinentes pour la question.
    Retourne une liste de 0 à 3 catégories (garde-fou souple).
    [] = pas de filtre catégorie (question trop vague)
    """
    categories_dispo = DB.get("categories", [])
    if not categories_dispo:
        print("[LLM] Aucune catégorie en DB → pas de filtre")
        return []

    # Contexte conversation
    msgs_user = [m["content"] for m in history if m["role"] == "user"][-2:]
    contexte = f"Contexte : {' / '.join(msgs_user)}\n" if msgs_user else ""

    prompt = (
        f"{contexte}"
        f"Catégories de chaussures disponibles : {', '.join(categories_dispo)}\n"
        f"Question client : \"{question}\"\n"
        f"Quelles catégories sont pertinentes ? (0, 1 ou plusieurs)\n"
        f"Réponds UNIQUEMENT en JSON valide, exemple : {{\"categories\": [\"Talons\", \"Sandales\"]}}\n"
        f"Si la question est trop vague ou générale, réponds : {{\"categories\": []}}"
    )
    try:
        resp = ollama.chat(
            model="mistral",
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 60, "temperature": 0},
        )
        raw = resp["message"]["content"].strip()
        # Nettoyage robuste du JSON
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            cats = [c for c in data.get("categories", []) if c in categories_dispo]
            print(f"[LLM] catégories candidates : {cats}")
            return cats
    except Exception as e:
        print(f"[LLM] catégories échoué : {e} → pas de filtre catégorie")
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
    """
    Retourne (vecteur, is_image_search, filtres_explicites, categories_candidates).

    Pour les recherches texte :
      - Lance en PARALLÈLE :
          1. Enrichissement question via LLM  → meilleur vecteur Qdrant
          2. Extraction filtres explicites    → couleur, marque, budget, genre, pointure
          3. Détection catégories candidates  → garde-fou souple multi-catégories
      - Vectorise la question enrichie
    """
    # ── Mode image : pas de LLM, vectorisation directe ──
    try:
        if image_path and os.path.exists(image_path):
            print(f"[VECTORISE] mode image_path")
            image_vec = model.encode(Image.open(image_path))
            vec = ((image_vec * 0.7) + (model.encode(question) * 0.3)).tolist() \
                  if question and question.strip() else image_vec.tolist()
            return vec, True, {}, []

        if image_vector:
            print(f"[VECTORISE] mode image_vector (session)")
            import numpy as np
            image_vec = np.array(image_vector)

            # Analyse texte même avec image
            filtres_explicites = extraire_filtres(question, history)
            categories_candidates = _llm_categories_candidates(question, history)

            if question and question.strip():
                contexte_produit = ""
                for msg in reversed(history):
                    if msg["role"] == "user" and "Produits suggérés" in msg["content"]:
                        m = re.search(r"Produits suggérés : ([^,\(]+)", msg["content"])
                        if m:
                            contexte_produit = m.group(1).strip()
                        break

                q_enrichie = (
                    f"{contexte_produit} {question}".strip()
                    if contexte_produit else question
                )

                text_vec = model.encode(q_enrichie)

                # fusion image + texte
                vec = ((image_vec * 0.5) + (text_vec * 0.5)).tolist()
            else:
                vec = image_vector

            print(f"[VECTORISE] filtres explicites : {filtres_explicites}")
            print(f"[VECTORISE] catégories candidates : {categories_candidates}")

            return (
                vec,
                True,
                filtres_explicites,
                categories_candidates
            )

        # ── Mode texte : 3 tâches en parallèle ──
        print(f"[VECTORISE] mode texte — analyse parallèle")
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_enrichi    = executor.submit(_llm_enrichir_question,     question, history)
            fut_filtres    = executor.submit(extraire_filtres,            question, history)
            fut_categories = executor.submit(_llm_categories_candidates, question, history)

            question_enrichie     = fut_enrichi.result()
            filtres_explicites    = fut_filtres.result()
            categories_candidates = fut_categories.result()

        # Si l'enrichissement n'a rien apporté (retour identique ou vide), on garde l'original
        if not question_enrichie or question_enrichie.lower().strip() == question.lower().strip():
            question_enrichie = question
            print(f"[VECTORISE] enrichissement sans apport → question originale")

        # Retire la catégorie des filtres explicites — gérée séparément
        filtres_explicites.pop("categorie", None)

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
    """
    Construit un filtre Qdrant natif depuis les filtres explicites et les catégories candidates.
    Les filtres sont appliqués DANS Qdrant avant le scoring — bien plus efficace.
    """
    conditions = []

    # Budget → filtre sur le prix
    if "budget" in filtres:
        conditions.append(FieldCondition(key="prix", range=Range(lte=filtres["budget"])))
        print(f"[QDRANT-FILTER] prix <= {filtres['budget']}")

    # Genre
    if "genre" in filtres:
        # Inclut toujours Mixte en plus du genre demandé
        conditions.append(FieldCondition(key="genre",
                                         match=MatchAny(any=[filtres["genre"], "Mixte"])))
        print(f"[QDRANT-FILTER] genre = {filtres['genre']} ou Mixte")

    # Marque
    if "marque" in filtres:
        conditions.append(FieldCondition(key="marque",
                                         match=MatchValue(value=filtres["marque"])))
        print(f"[QDRANT-FILTER] marque = {filtres['marque']}")

    # Couleur — filtre sur la liste de couleurs (keyword array)
    if "couleur" in filtres:
        conditions.append(FieldCondition(key="couleurs",
                                         match=MatchValue(value=filtres["couleur"])))
        print(f"[QDRANT-FILTER] couleur = {filtres['couleur']}")

    # Pointure — filtre sur la liste de tailles (keyword array)
    if "pointure" in filtres:
        conditions.append(FieldCondition(key="tailles",
                                         match=MatchValue(value=filtres["pointure"])))
        print(f"[QDRANT-FILTER] taille = {filtres['pointure']}")

    # Catégories candidates — garde-fou souple (should = OR)
    # On utilise should au lieu de must pour ne pas bloquer si vide
    cat_conditions = []
    if categories_candidates:
        cat_conditions = [
            FieldCondition(key="categorie", match=MatchValue(value=cat))
            for cat in categories_candidates
        ]
        print(f"[QDRANT-FILTER] catégories (OR) = {categories_candidates}")

    if not conditions and not cat_conditions:
        return None

    # must = ET obligatoire (budget, genre, marque, couleur, pointure)
    # should = OU souple (catégories candidates)
    return Filter(
        must=conditions if conditions else None,
        should=cat_conditions if cat_conditions else None,
        min_should=MinShould(
            conditions=cat_conditions,
            min_count=1
        ) if cat_conditions else None,
    )


def _recherche_qdrant(
    question_vector: list,
    question: str,
    history: list,
    filtres: dict,
    categories_candidates: list,
) -> tuple[list, str]:
    """
    Recherche Qdrant avec filtres NATIFS (prix, genre, marque, couleur, taille, catégorie).
    Bien plus efficace que le filtrage Python post-hoc.
    """
    limit_qdrant = 20 if categories_candidates else 8
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

    # Construction des produits — tailles/couleurs déjà en listes dans le payload
    produits = []
    for r in results:
        tailles  = r.payload.get("tailles",  [])
        couleurs = r.payload.get("couleurs", [])
        # Compatibilité si encore en string (avant réindexation)
        if isinstance(tailles, str):
            tailles  = [t.strip() for t in tailles.split(",")  if t.strip()]
        if isinstance(couleurs, str):
            couleurs = [c.strip() for c in couleurs.split(",") if c.strip()]
        produits.append({
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

    if not produits:
        # Construire le contexte d'erreur pour Mistral
        filtres_ko = []
        if "budget"   in filtres: filtres_ko.append(f"sous {filtres['budget']}€")
        if "genre"    in filtres: filtres_ko.append(f"pour {filtres['genre']}")
        if "marque"   in filtres: filtres_ko.append(f"marque {filtres['marque']}")
        if "couleur"  in filtres: filtres_ko.append(f"couleur {filtres['couleur']}")
        if "pointure" in filtres: filtres_ko.append(f"taille {filtres['pointure']}")
        if categories_candidates: filtres_ko.append(f"catégorie {'/'.join(categories_candidates)}")
        contexte = (
            f"ATTENTION : aucun produit trouvé pour [{', '.join(filtres_ko)}]. "
            if filtres_ko else
            "ATTENTION : aucun produit trouvé. "
        ) + (
            "Ne propose AUCUN produit inventé. "
            "Explique ce qui n'est pas disponible et demande à l'utilisateur "
            "s'il veut modifier ses critères."
        )
        print(f"[QDRANT] 0 résultats | contexte : {contexte!r}")
        return [], contexte

    # Contexte positif pour Mistral
    filtres_ok = []
    if "budget"   in filtres: filtres_ok.append(f"sous {filtres['budget']}€")
    if "genre"    in filtres: filtres_ok.append(f"pour {filtres['genre']}")
    if "marque"   in filtres: filtres_ok.append(f"marque {filtres['marque']}")
    if "couleur"  in filtres: filtres_ok.append(f"couleur {filtres['couleur']}")
    if "pointure" in filtres: filtres_ok.append(f"taille {filtres['pointure']}")
    if categories_candidates: filtres_ok.append(f"catégorie {'/'.join(categories_candidates)}")
    contexte = f"Produits filtrés ({', '.join(filtres_ok)}) :" if filtres_ok else ""

    print(f"[QDRANT] {len(produits)} produits | contexte : {contexte!r}")
    return produits, contexte

# ══════════════════════════════════════════════
# VECTORISATION + ANALYSE PARALLÈLE
# ══════════════════════════════════════════════
def _filtres_depuis_produit(produit: dict) -> dict:
    """
    Extrait des filtres implicites depuis un produit similaire à l'image.
    """
    filtres = {}

    if produit.get("categorie"):
        filtres["categorie"] = produit["categorie"]

    # On prend UNE couleur principale si dispo
    couleurs = produit.get("couleurs", [])
    if couleurs:
        filtres["couleur"] = couleurs[0]

    return filtres




# ══════════════════════════════════════════════
# STREAMING PRINCIPAL
# ══════════════════════════════════════════════

def get_response_stream(
    question: str = "",
    product_id: int = None,
    history: list = None,
    image_path: str = None,
    image_vector: list = None,
):
    question = question or ""
    if history is None:
        history = []

    print(f"\n{'='*50}")
    print(f"[RAG] question : {question!r} | history : {len(history)} messages")
    print(f"{'='*50}\n")

    # Une image implique automatiquement une recherche produit
    if image_path or image_vector:
        intention = "recherche"
        confiance = 1.0
        print("[INTENTION] image détectée → recherche")
    else:
        intention, confiance = classifier_intention(question)
        print(f"[INTENTION] {intention!r} ({confiance:.1%})")
    # ════════════════════════════════════════════
    # CAS 1 — HORS SUJET
    # ════════════════════════════════════════════
    if intention == "hors_sujet":
        print("[CAS] 1 — hors_sujet")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
            {"role": "user", "content": (
                f"L'utilisateur dit : « {question} »\n"
                "C'est hors sujet pour une boutique de chaussures. "
                "Réponds poliment que tu es spécialisé chaussures et recentre."
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
        print("[CAS] 2 — livraison")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
            {"role": "user", "content": (
                f"L'utilisateur demande : « {question} »\n"
                "Tu n'as pas accès aux infos livraison/retours/stock. "
                "Dis-le honnêtement et propose de l'aider à trouver des chaussures."
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
    if (intention == "panier" or user_wants_cart(question))             and (user_wants_cart(question) or confiance >= 0.95):
        print(f"[CAS] 3 — panier (intention={intention}, user_wants_cart={user_wants_cart(question)})")
        produits_historique = _produits_depuis_historique(history)
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        if produits_historique:
            contexte_produits = "\n".join([f"- {p['name']} ({p['price']}€)" for p in produits_historique])
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"Produits disponibles :\n{contexte_produits}\n\n"
                    f"L'utilisateur dit : « {question} »\n"
                    "Identifie lequel il veut, confirme chaleureusement et cite son nom exact."
                )},
            ]
        else:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"L'utilisateur dit : « {question} »\n"
                    "Aucun produit présenté. Demande ce qu'il recherche."
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

        produit_cible = None
        if produits_historique:
            mentionnes = _produits_mentionnes(texte_complet, produits_historique)
            produit_cible = mentionnes[0] if mentionnes else produits_historique[0]

        yield {
            "type": "products_final", "products": [],
            "action": "add_to_cart" if produit_cible else None,
            "product_id": produit_cible["id"] if produit_cible else None,
            "quantity": 1,
        }
        return

    # ════════════════════════════════════════════
    # CAS 4 — SUIVI
    # ════════════════════════════════════════════
    if intention == "suivi":
        print("[CAS] 4 — suivi")
        produits_historique = _produits_depuis_historique(history)
        if produits_historique:
            yield {"products": [], "action": None, "product_id": None, "quantity": 1}
            contexte_produits = "\n".join([
                f"- {p['name']} ({p['marque']}, {p['price']}€) : {p['description']}\n"
                f"  Tailles : {', '.join(str(t) for t in p.get('tailles', []))}\n"
                f"  Couleurs : {', '.join(p.get('couleurs', []))}"
                for p in produits_historique
            ])
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"Produits déjà présentés :\n{contexte_produits}\n\n"
                    f"Question : {question}\n"
                    "Réponds précisément en te basant uniquement sur ces informations."
                )},
            ]
            try:
                stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                     options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.5})
                for chunk in stream:
                    yield chunk["message"]["content"]
            except Exception as e:
                yield f"Erreur Mistral : {str(e)}"
            yield {"type": "products_final", "products": produits_historique,
                   "action": None, "product_id": None, "quantity": 1}
            return
        print("[CAS] 4 — suivi sans produits → fallback recherche")

    # ════════════════════════════════════════════
    # CAS 5 — COMPARAISON
    # ════════════════════════════════════════════
    if intention == "comparaison":
        print("[CAS] 5 — comparaison")
        produits_historique = _produits_depuis_historique(history)
        if len(produits_historique) >= 2:
            yield {"products": [], "action": None, "product_id": None, "quantity": 1}
            p1, p2 = produits_historique[0], produits_historique[1]
            contexte = (
                f"Produit 1 — {p1['name']} ({p1['marque']}, {p1['price']}€)\n"
                f"Description : {p1['description']}\n"
                f"Tailles : {', '.join(p1.get('tailles', []))}\n"
                f"Couleurs : {', '.join(p1.get('couleurs', []))}\n\n"
                f"Produit 2 — {p2['name']} ({p2['marque']}, {p2['price']}€)\n"
                f"Description : {p2['description']}\n"
                f"Tailles : {', '.join(p2.get('tailles', []))}\n"
                f"Couleurs : {', '.join(p2.get('couleurs', []))}"
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *[{"role": m["role"], "content": m["content"]} for m in history[-6:]],
                {"role": "user", "content": (
                    f"{contexte}\n\nQuestion : {question}\n"
                    "Fais une comparaison claire (prix, usage, confort, style) et aide à choisir."
                )},
            ]
            try:
                stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                     options={"num_ctx": 2048, "num_predict": 200, "temperature": 0.6})
                for chunk in stream:
                    yield chunk["message"]["content"]
            except Exception as e:
                yield f"Erreur Mistral : {str(e)}"
            yield {"type": "products_final", "products": [p1, p2],
                   "action": None, "product_id": None, "quantity": 1, "layout": "comparison"}
            return
        print("[CAS] 5 — pas assez de produits → fallback Qdrant")

    # ════════════════════════════════════════════
    # CAS 6 — RECHERCHE & RECOMMANDATION
    # ════════════════════════════════════════════
    print("[CAS] 6 — recherche/recommandation")

    # 0. Détection nom exact — court-circuite tout si l'utilisateur cite un produit précis
    produits_nom_exact = _chercher_produit_par_nom(question)
    if produits_nom_exact:
        print(f"[CAS] 6 — nom exact détecté → réponse directe")
        genre       = _extraire_genre(history, question)
        nb_produits = _nb_produits_from_history(history)
        prompt = build_prompt(
            question=question,
            produits=produits_nom_exact,
            product_id=product_id,
            genre=genre,
            is_image_search=False,
            contexte_filtres="",
        )
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        texte_complet = ""
        try:
            stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                 options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.5})
            for chunk in stream:
                token = chunk["message"]["content"]
                texte_complet += token
                yield token
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {
            "type": "products_final",
            "products": produits_nom_exact[:nb_produits],
            "action": None, "product_id": None, "quantity": 1,
        }
        return

    # 1. Analyse parallèle (enrichissement + filtres + catégories)
    question_vector, is_image_search, filtres, categories_candidates = \
        _analyser_question(question, history, image_path, image_vector)

    # 2. Qdrant + garde-fou catégorie + filtres explicites
    produits_trouves, contexte_filtres = _recherche_qdrant(
        question_vector, question, history, filtres, categories_candidates
    )

    if not produits_trouves:
        print("[CAS] 6 — aucun produit → réponse Mistral directe")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-10:]],
            {"role": "user", "content": (
                f"{contexte_filtres}\n"
                "IMPORTANT : tu ne dois proposer AUCUN produit inventé. "
                "Ne cite aucun nom de produit, aucun prix, aucune marque que tu n'as pas dans le catalogue ci-dessus. "
                "Explique simplement ce qui n'est pas disponible et demande à l'utilisateur "
                "s'il veut modifier ses critères de recherche.\n"
                f"Question : {question}"
            )},
        ]
        try:
            stream = ollama.chat(model="mistral", messages=messages, stream=True,
                                 options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.7})
            for chunk in stream:
                yield chunk["message"]["content"]
        except Exception as e:
            yield f"Erreur Mistral : {str(e)}"
        yield {"type": "products_final", "products": [], "action": None, "product_id": None, "quantity": 1}
        return

    # 3. Prompt Mistral
    genre       = _extraire_genre(history, question)
    nb_produits = _nb_produits_from_history(history)
    print(f"[CAS] 6 — {len(produits_trouves)} produits | genre={genre} | nb_à_afficher={nb_produits}")

    description_visuelle = ""
    if is_image_search and produits_trouves:
        description_visuelle = f"[Photo reçue, produit similaire : {produits_trouves[0]['name']}] "

    suffixe_recommandation = ""
    if intention == "recommandation":
        suffixe_recommandation = (
            "\nL'utilisateur demande un conseil personnalisé. "
            "Donne ton avis clair sur le meilleur choix et explique pourquoi."
        )

    question_complete = f"{description_visuelle}{question or ''}{suffixe_recommandation}"
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

    yield {"products": [], "action": None, "product_id": None, "quantity": 1}

    texte_complet = ""
    try:
        stream = ollama.chat(
            model="mistral", messages=messages, stream=True,
            options={"num_ctx": 2048, "num_predict": 150, "temperature": 0.7},
        )
        for chunk in stream:
            token = chunk["message"]["content"]
            texte_complet += token
            yield token
    except Exception as e:
        yield f"Erreur Mistral : {str(e)}"
        return

    produits_affiches = _produits_mentionnes(texte_complet, produits_trouves)
    action = "add_to_cart" if user_wants_cart(question) and produits_affiches else None

    print(f"[CAS] 6 — affichés : {[p['name'] for p in produits_affiches[:nb_produits]]}")
    yield {
        "type":       "products_final",
        "products":   produits_affiches[:nb_produits],
        "action":     action,
        "product_id": produits_affiches[0]["id"] if produits_affiches and action else None,
        "quantity":   1,
    }