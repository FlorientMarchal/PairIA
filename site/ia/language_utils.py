# ia/language_utils.py
# Détection de langue et traduction vers le français pour le pipeline RAG
#
# Stratégie :
#   1. Détection via langdetect (léger, open-source, pas d'API externe)
#   2. Traduction FR via le LLM local (Ollama) — aucun service tiers requis
#
# Installation : pip install langdetect
# (déjà dispo dans la plupart des envs Python 3.8+)

from __future__ import annotations
import ollama

# ── Langues supportées ──────────────────────────────────────────────────────
# Toutes les langues détectables par langdetect (55 langues)
# Codes ISO 639-1 → nom complet pour le prompt LLM
LANGUES_SUPPORTEES: dict[str, str] = {
    "af": "afrikaans",
    "ar": "arabe",
    "bg": "bulgare",
    "bn": "bengali",
    "ca": "catalan",
    "cs": "tchèque",
    "cy": "gallois",
    "da": "danois",
    "de": "allemand",
    "el": "grec",
    "en": "anglais",
    "es": "espagnol",
    "et": "estonien",
    "fa": "persan",
    "fi": "finnois",
    "fr": "français",
    "gu": "gujarati",
    "he": "hébreu",
    "hi": "hindi",
    "hr": "croate",
    "hu": "hongrois",
    "id": "indonésien",
    "it": "italien",
    "ja": "japonais",
    "kn": "kannada",
    "ko": "coréen",
    "lt": "lituanien",
    "lv": "letton",
    "mk": "macédonien",
    "ml": "malayalam",
    "mr": "marathi",
    "ne": "népalais",
    "nl": "néerlandais",
    "no": "norvégien",
    "pa": "pendjabi",
    "pl": "polonais",
    "pt": "portugais",
    "ro": "roumain",
    "ru": "russe",
    "sk": "slovaque",
    "sl": "slovène",
    "so": "somali",
    "sq": "albanais",
    "sv": "suédois",
    "sw": "swahili",
    "ta": "tamoul",
    "te": "télougou",
    "th": "thaï",
    "tl": "tagalog",
    "tr": "turc",
    "uk": "ukrainien",
    "ur": "ourdou",
    "vi": "vietnamien",
    "zh": "chinois",
    "zh-cn": "chinois simplifié",
    "zh-tw": "chinois traditionnel",
}

# Modèle utilisé pour la traduction (même que le chatbot)
_LLM_MODEL = "llama3.1"


# ── Détection de langue ──────────────────────────────────────────────────────

def detecter_langue(texte: str) -> str:
    """
    Retourne le code ISO 639-1 de la langue détectée (ex: 'en', 'es', 'fr').
    Retourne 'fr' par défaut si la détection échoue ou si le texte est trop court.
    """
    if not texte or len(texte.strip()) < 3:
        return "fr"

    try:
        from langdetect import detect, LangDetectException
        code = detect(texte.strip())
        print(f"[LANG] détecté : {code!r} pour : {texte[:60]!r}")
        return code
    except Exception as e:
        print(f"[LANG] langdetect indisponible ou erreur ({e}) → fallback 'fr'")
        return "fr"


# ── Traduction vers le français ──────────────────────────────────────────────

def traduire_en_francais(texte: str, langue_source: str, llm_model: str = _LLM_MODEL) -> str:
    """
    Traduit `texte` depuis `langue_source` vers le français via le LLM local.
    Retourne le texte original en cas d'échec ou si la langue est déjà le français.
    """
    if langue_source == "fr" or not texte.strip():
        return texte

    nom_lang = LANGUES_SUPPORTEES.get(langue_source, langue_source)

    prompt = (
        f"Traduis le texte suivant de l'{nom_lang} vers le français.\n"
        "Réponds UNIQUEMENT avec la traduction, sans explication, sans guillemets.\n\n"
        f"Texte : {texte}"
    )

    try:
        response = ollama.chat(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 300, "temperature": 0.1},
        )
        traduction = response["message"]["content"].strip()
        print(f"[LANG] traduit ({nom_lang}→fr) : {texte[:60]!r} → {traduction[:60]!r}")
        return traduction
    except Exception as e:
        print(f"[LANG] erreur traduction : {e} → texte original conservé")
        return texte


# ── Traduction du français vers une langue cible ─────────────────────────────

def traduire_reponse(texte: str, langue_cible: str, llm_model: str = _LLM_MODEL) -> str:
    """
    Traduit une réponse du français vers la langue cible via le LLM local.
    Utilisée dans rag.py pour traduire la réponse finale si besoin.
    Retourne le texte original en cas d'échec ou si la langue cible est le français.
    """
    if langue_cible == "fr" or not texte.strip():
        return texte

    nom_lang = LANGUES_SUPPORTEES.get(langue_cible, langue_cible)

    prompt = (
        f"Translate the following text to {nom_lang}.\n"
        "Translate ALL content including labels and descriptions.\n"
        "Keep product names, brand names, prices and numbers exactly as-is.\n"
        "Reply ONLY with the translation, no explanation, no quotes.\n\n"
        f"Text: {texte}"
    )

    try:
        response = ollama.chat(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 500, "temperature": 0.1},
        )
        traduction = response["message"]["content"].strip()
        print(f"[LANG] traduit (fr→{nom_lang}) : {texte[:60]!r} → {traduction[:60]!r}")
        return traduction
    except Exception as e:
        print(f"[LANG] erreur traduction réponse : {e} → texte original conservé")
        return texte


# ── Fonction principale (détection + traduction en un appel) ─────────────────

def normaliser_question(question: str, llm_model: str = _LLM_MODEL) -> tuple[str, str]:
    """
    Détecte la langue de la question et la traduit en français si nécessaire.

    Retourne :
        (question_en_francais, code_langue_originale)

    Exemple :
        normaliser_question("I'm looking for red sneakers")
        → ("Je cherche des baskets rouges", "en")

        normaliser_question("Je cherche des baskets")
        → ("Je cherche des baskets", "fr")
    """
    langue = detecter_langue(question)
    question_fr = traduire_en_francais(question, langue, llm_model)
    return question_fr, langue


# ── Nom complet de la langue pour le prompt LLM ──────────────────────────────

def nom_langue(code: str) -> str:
    """Retourne le nom complet d'une langue à partir de son code ISO."""
    return LANGUES_SUPPORTEES.get(code, code)


# ── Traduction du catalogue produits ────────────────────────────────────────

def traduire_catalogue(produits: list, langue: str, llm_model: str = _LLM_MODEL) -> list:
    """
    Traduit uniquement les caracteristiques de chaque produit en langue cible.
    Les couleurs sont intentionnellement conservees en francais pour ne pas
    casser le filtrage Qdrant qui compare les couleurs en francais.
    Un appel LLM par produit (texte court) pour eviter les erreurs JSON.
    """
    if not produits or langue == "fr":
        return produits

    import copy
    nom_lang = nom_langue(langue)
    produits_trad = copy.deepcopy(produits)

    # Collecter tous les textes a traduire (caracteristiques uniquement)
    textes = [p.get("caracteristiques", "") or "" for p in produits_trad]
    textes_non_vides = [(i, t) for i, t in enumerate(textes) if t.strip()]

    if not textes_non_vides:
        return produits_trad

    # Un seul appel : on envoie toutes les caracteristiques separees par |SEP|
    combined = " |SEP| ".join(t for _, t in textes_non_vides)

    # ✅ CORRIGÉ — \n échappés correctement (plus de saut de ligne littéral)
    prompt = (
        "Translate the following French shoe characteristics to " + nom_lang + ".\n"
        "Each characteristic is separated by |SEP|.\n"
        "Reply ONLY with the translated texts separated by |SEP|, same order, nothing else.\n\n"
        + combined
    )

    try:
        response = ollama.chat(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 600, "temperature": 0.1},
        )
        raw = response["message"]["content"].strip()
        parts = [p.strip() for p in raw.split("|SEP|")]

        if len(parts) == len(textes_non_vides):
            for (i, _), trad in zip(textes_non_vides, parts):
                produits_trad[i]["caracteristiques"] = trad
            print("[LANG] catalogue traduit (" + nom_lang + ") : " + str(len(produits_trad)) + " produits")
        else:
            print("[LANG] catalogue : nombre de segments inattendu (" + str(len(parts)) + " vs " + str(len(textes_non_vides)) + ") -> original conserve")

    except Exception as e:
        print("[LANG] erreur traduction catalogue : " + str(e) + " -> catalogue original conserve")

    return produits_trad