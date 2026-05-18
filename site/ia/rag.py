# ia/rag.py
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ollama
from database import qdrant
from llm_prompt import build_prompt, SYSTEM_PROMPT
from image_search import model
from intention_classifier import classifier_intention
from filters import extraire_filtres, appliquer_filtres, user_wants_cart, DB
from PIL import Image


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
                print(f"[HISTORIQUE] ✅ {len(produits)} produit(s) récupéré(s) : {[p['name'] for p in produits]}")
                return produits
    print(f"[HISTORIQUE] ❌ Aucun produit trouvé — {len(history)} messages, roles : {[m['role'] for m in history]}")
    print(f"[HISTORIQUE] clés des msgs assistant : {[list(m.keys()) for m in history if m['role'] == 'assistant']}")
    return []


def _vectoriser(
    question: str,
    history: list,
    image_path: str = None,
    image_vector: list = None,
) -> tuple[list, bool, dict]:
    """Retourne (vecteur, is_image_search, filtres)."""
    try:
        if image_path and os.path.exists(image_path):
            print(f"[VECTORISE] mode image_path : {image_path}")
            image_vec = model.encode(Image.open(image_path))
            if question and question.strip():
                vec = ((image_vec * 0.7) + (model.encode(question) * 0.3)).tolist()
            else:
                vec = image_vec.tolist()
            return vec, True, {}

        if image_vector:
            print(f"[VECTORISE] mode image_vector (session)")
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
            return vec, True, {}

        print(f"[VECTORISE] mode texte")
        text_to_encode = question if (question and question.strip()) else "chaussures"
        filtres_actuels = extraire_filtres(question, history)
        if filtres_actuels.get("categorie"):
            text_to_encode = f"{filtres_actuels['categorie']} {text_to_encode}"
            print(f"[VECTORISE] question enrichie : {text_to_encode!r}")
        return model.encode(text_to_encode).tolist(), False, filtres_actuels

    except Exception as e:
        print(f"[VECTORISE] ❌ Erreur : {e}")
        return [0] * 512, False, {}


def _recherche_qdrant(
    question_vector: list,
    question: str,
    history: list,
    filtres: dict = None,
) -> tuple[list, str]:
    try:
        if filtres is None:
            print(f"[QDRANT] filtres non fournis → recalcul")
            filtres = extraire_filtres(question, history)
        limit_qdrant = 15 if filtres.get("categorie") else 5
        print(f"[QDRANT] limit={limit_qdrant} | filtres={filtres}")
        results = qdrant.query_points(
            collection_name="produits_image",
            query=question_vector,
            limit=limit_qdrant,
            score_threshold=0.10,
        ).points
        print(f"[QDRANT] {len(results)} résultats bruts")
        for i, r in enumerate(results):
            print(f"[QDRANT] #{i+1} {r.payload.get('nom')} | cat={r.payload.get('categorie')} | score={r.score:.3f}")
    except Exception as e:
        print(f"[QDRANT] ❌ Erreur : {e}")
        results = []

    produits = []
    for r in results:
        tailles_raw  = r.payload.get("tailles",  "")
        couleurs_raw = r.payload.get("couleurs", "")
        produits.append({
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

    print(f"[QDRANT] {len(produits)} produits avant filtrage")
    produits_filtres, contexte = appliquer_filtres(produits, question, history)
    print(f"[QDRANT] {len(produits_filtres)} produits après filtrage | contexte : {contexte!r}")
    return produits_filtres, contexte


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
    print(f"[RAG] question : {question!r} | history : {len(history)} messages")
    print(f"{'='*50}\n")

    # ── INTENTION ──
    intention, confiance = classifier_intention(question)
    print(f"[INTENTION] {intention!r} (confiance : {confiance:.1%})")

    # ════════════════════════════════════════════
    # CAS 1 — HORS SUJET
    # ════════════════════════════════════════════
    if intention == "hors_sujet":
        print(f"[CAS] 1 — hors_sujet")
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
        print(f"[CAS] 2 — livraison")
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
    if intention == "panier" or user_wants_cart(question):
        print(f"[CAS] 3 — panier (intention={intention}, user_wants_cart={user_wants_cart(question)})")
        produits_historique = _produits_depuis_historique(history)
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}

        if produits_historique:
            contexte_produits = "\n".join([
                f"- {p['name']} ({p['price']}€)" for p in produits_historique
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
                    "Aucun produit n'a encore été présenté. "
                    "Demande-lui ce qu'il recherche."
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
            "type":       "products_final",
            "products":   [],
            "action":     "add_to_cart" if produit_cible else None,
            "product_id": produit_cible["id"] if produit_cible else None,
            "quantity":   1,
        }
        return

    # ════════════════════════════════════════════
    # CAS 4 — SUIVI
    # ════════════════════════════════════════════
    if intention == "suivi":
        print(f"[CAS] 4 — suivi")
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
            yield {
                "type": "products_final", "products": produits_historique,
                "action": None, "product_id": None, "quantity": 1,
            }
            return
        print(f"[CAS] 4 — suivi sans produits → fallback recherche")

    # ════════════════════════════════════════════
    # CAS 5 — COMPARAISON
    # ════════════════════════════════════════════
    if intention == "comparaison":
        print(f"[CAS] 5 — comparaison")
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
                    "Fais une comparaison claire (prix, usage, confort, style) "
                    "et aide le client à choisir."
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
                "type": "products_final", "products": [p1, p2],
                "action": None, "product_id": None, "quantity": 1,
                "layout": "comparison",
            }
            return
        print(f"[CAS] 5 — comparaison sans assez de produits → fallback Qdrant")

    # ════════════════════════════════════════════
    # CAS 6 — RECHERCHE & RECOMMANDATION
    # ════════════════════════════════════════════
    print(f"[CAS] 6 — recherche/recommandation")

    # 1. Vectorisation
    question_vector, is_image_search, filtres_calcules = _vectoriser(question, history, image_path, image_vector)

    # 2. Qdrant + filtres
    produits_trouves, contexte_filtres = _recherche_qdrant(question_vector, question, history, filtres_calcules)

    if not produits_trouves:
        print(f"[CAS] 6 — aucun produit après filtrage → réponse directe Mistral")
        yield {"products": [], "action": None, "product_id": None, "quantity": 1}
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *[{"role": m["role"], "content": m["content"]} for m in history[-10:]],
            {"role": "user", "content": contexte_filtres + f"\nQuestion : {question}"},
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

    # 3. Prompt
    genre       = _extraire_genre(history, question)
    nb_produits = _nb_produits_from_history(history)
    print(f"[CAS] 6 — {len(produits_trouves)} produits | genre={genre} | nb_à_afficher={nb_produits}")

    description_visuelle = ""
    if is_image_search and produits_trouves:
        description_visuelle = f"[L'utilisateur a envoyé une photo de : {produits_trouves[0]['name']}] "

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

    produits_affiches = _produits_mentionnes(texte_complet, produits_trouves[:3])

    action = None
    if user_wants_cart(question) and produits_affiches:
        action = "add_to_cart"

    print(f"[CAS] 6 — produits affichés : {[p['name'] for p in produits_affiches[:nb_produits]]}")
    yield {
        "type":       "products_final",
        "products":   produits_affiches[:nb_produits],
        "action":     action,
        "product_id": produits_affiches[0]["id"] if produits_affiches and action else None,
        "quantity":   1,
    }