# ia/language_utils.py
# Détection de langue et traduction vers le français pour le pipeline RAG

from __future__ import annotations
import os
import ollama
client = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
#75 langues
LANGUES_SUPPORTEES: dict[str, str] = {
    "af": "afrikaans",
    "ar": "arabe",
    "az": "azerbaïdjanais",
    "be": "biélorusse",
    "bg": "bulgare",
    "bn": "bengali",
    "bs": "bosnien",
    "ca": "catalan",
    "cs": "tchèque",
    "cy": "gallois",
    "da": "danois",
    "de": "allemand",
    "el": "grec",
    "en": "anglais",
    "eo": "espéranto",
    "es": "espagnol",
    "et": "estonien",
    "eu": "basque",
    "fa": "persan",
    "fi": "finnois",
    "fr": "français",
    "ga": "irlandais",
    "gu": "gujarati",
    "he": "hébreu",
    "hi": "hindi",
    "hr": "croate",
    "hu": "hongrois",
    "hy": "arménien",
    "id": "indonésien",
    "is": "islandais",
    "it": "italien",
    "ja": "japonais",
    "ka": "géorgien",
    "kk": "kazakh",
    "ko": "coréen",
    "la": "latin",
    "lg": "ganda",
    "lt": "lituanien",
    "lv": "letton",
    "mi": "maori",
    "mk": "macédonien",
    "mn": "mongol",
    "mr": "marathi",
    "ms": "malais",
    "nb": "norvégien bokmål",
    "nl": "néerlandais",
    "nn": "norvégien nynorsk",
    "pa": "pendjabi",
    "pl": "polonais",
    "pt": "portugais",
    "ro": "roumain",
    "ru": "russe",
    "sk": "slovaque",
    "sl": "slovène",
    "sn": "shona",
    "so": "somali",
    "sq": "albanais",
    "sr": "serbe",
    "st": "sotho",
    "sv": "suédois",
    "sw": "swahili",
    "ta": "tamoul",
    "te": "télougou",
    "th": "thaï",
    "tl": "tagalog",
    "tn": "tswana",
    "tr": "turc",
    "ts": "tsonga",
    "uk": "ukrainien",
    "ur": "ourdou",
    "vi": "vietnamien",
    "xh": "xhosa",
    "yo": "yoruba",
    "zh": "chinois",
    "zu": "zoulou",
}

_LLM_MODEL = "llama3.1"

# ── Initialisation du détecteur lingua ──────────────────────────────────────
# Chargé une seule fois au démarrage
try:
    from lingua import Language, LanguageDetectorBuilder
    _detector = LanguageDetectorBuilder.from_all_languages().with_minimum_relative_distance(0.02).build()
    print("[LANG] lingua chargé ✓")
except Exception as e:
    _detector = None
    print(f"[LANG] lingua indisponible ({e}) → fallback langdetect")


def detecter_langue(texte: str) -> str:
    if not texte or len(texte.strip()) < 3:
        return "fr"

    if _detector is not None:
        try:
            langue = _detector.detect_language_of(texte.strip())
            if langue is None:
                return "fr"
            code = langue.iso_code_639_1.name.lower()  # "EN" → "en"
            print(f"[LANG] détecté : {code!r} pour : {texte[:60]!r}")
            return code
        except Exception as e:
            print(f"[LANG] lingua erreur ({e}) → fallback langdetect")

    try:
        from langdetect import detect
        code = detect(texte.strip())
        print(f"[LANG] détecté (langdetect) : {code!r} pour : {texte[:60]!r}")
        return code
    except Exception as e:
        print(f"[LANG] langdetect erreur ({e}) → fallback 'fr'")
        return "fr"

def traduire_en_francais(texte: str, langue_source: str, llm_model: str = _LLM_MODEL) -> str:
    if langue_source == "fr" or not texte.strip():
        return texte

    nom_lang = LANGUES_SUPPORTEES.get(langue_source, langue_source)
    prompt = (
        f"Traduis le texte suivant de l'{nom_lang} vers le français.\n"
        "Réponds UNIQUEMENT avec la traduction, sans explication, sans guillemets.\n"
        "Conserve exactement les noms propres, marques et noms de produits.\n\n"
        f"Texte : {texte}"
    )
    try:
        response = client.chat(
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


def traduire_reponse(texte: str, langue_cible: str, llm_model: str = _LLM_MODEL) -> str:
    if langue_cible == "fr" or not texte.strip():
        return texte

    nom_lang = LANGUES_SUPPORTEES.get(langue_cible, langue_cible)
    prompt = (
        f"You are a translator. Output ONLY the {nom_lang} translation of the text below.\n"
        "Rules:\n"
        "- Output the translation immediately, no preamble, no explanation, no quotes.\n"
        "- Do NOT add 'Translation:', 'Übersetzung:', or any label before the text.\n"
        "- Do NOT repeat the original text.\n"
        "- Do NOT add lines like 'ProductName: ProductName' at the end.\n"
        "- Keep product names, brand names, prices and numbers exactly as-is.\n\n"
        f"Text to translate:\n{texte}"
    )
    try:
        response = client.chat(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 500, "temperature": 0.1},
        )
        traduction = response["message"]["content"].strip()

        # Nettoyage 1 : supprimer les préfixes parasites en début de réponse.
        # Llama génère parfois "Here is the translation:\n\n..." ou équivalent
        # dans n'importe quelle langue. On détecte structurellement :
        # - La 1ère ligne est courte (< 60 chars) ET se termine par ":"
        # - Elle est suivie d'une ligne vide
        # → c'est un préfixe introductif, pas le contenu traduit.
        lignes_brutes = traduction.splitlines()
        if (
            len(lignes_brutes) >= 3
            and lignes_brutes[0].strip().endswith(":")
            and len(lignes_brutes[0].strip()) < 60
            and lignes_brutes[1].strip() == ""
        ):
            traduction = "\n".join(lignes_brutes[2:]).strip()

        # Cas 2 : préfixe sur la 1ère ligne SANS ligne vide (ex: "Translation: Of course...")
        # On vérifie que la clé est un mot court (≤ 6 mots) et la valeur est substantielle
        elif lignes_brutes and ":" in lignes_brutes[0]:
            premiere = lignes_brutes[0].strip()
            idx_colon = premiere.index(":")
            cle = premiere[:idx_colon].strip()
            val_suite = premiere[idx_colon+1:].strip()
            if len(cle.split()) <= 6 and val_suite:
                # La vraie traduction commence après le ":"
                traduction = val_suite + ("\n" + "\n".join(lignes_brutes[1:]) if len(lignes_brutes) > 1 else "")
                traduction = traduction.strip()

        # Nettoyage 2 ligne par ligne : artefacts "Nom: Nom" en fin de réponse
        lignes = traduction.splitlines()
        lignes_nettes = []
        for ligne in lignes:
            stripped = ligne.strip()
            if ":" in stripped:
                parties = stripped.split(":", 1)
                cle = parties[0].strip()
                val = parties[1].strip()
                # Si clé == valeur (ou très proches) → artefact à ignorer
                if cle.lower() == val.lower() or cle.lower() in val.lower().split():
                    continue
            lignes_nettes.append(ligne)

        traduction = "\n".join(lignes_nettes).strip()
        print(f"[LANG] traduit (fr→{nom_lang}) : {texte[:60]!r} → {traduction[:60]!r}")
        return traduction
    except Exception as e:
        print(f"[LANG] erreur traduction réponse : {e} → texte original conservé")
        return texte


def normaliser_question(question: str, langue_session: str = "fr", llm_model: str = _LLM_MODEL) -> tuple[str, str]:
    """
    Détecte la langue et traduit en français si nécessaire.
    Avec lingua, la détection est fiable même sur les phrases courtes —
    on garde donc une logique simple sans cas particuliers.
    """
    mots = question.strip().split()

    # Texte court (≤ 5 mots) + session établie → garder la langue de session
    # Lingua est peu fiable sur les phrases courtes et ambiguës (ex: "i take it"
    # détecté comme maori au lieu d'anglais).
    # Seuil remonté de 2 → 5 mots pour couvrir les confirmations typiques.
    # Exception : si la langue détectée est clairement différente ET le texte
    # est assez long (> 5 mots), on fait confiance au détecteur.
    if langue_session and langue_session != "fr" and len(mots) <= 5:
        print(f"[LANG] texte court ({len(mots)} mot(s)) → langue session conservée : {langue_session}")
        question_fr = traduire_en_francais(question, langue_session, llm_model)
        return question_fr, langue_session

    langue_detectee = detecter_langue(question)

    # Verrouillage de session : si une langue est établie, on ne bascule que
    # si la détection est confiante (langue différente ET phrase de > 8 mots).
    # Cela évite les faux changements de langue en mid-conversation.
    if langue_session and langue_session != "fr" and langue_detectee != langue_session:
        if len(mots) <= 8:
            print(f"[LANG] langue session {langue_session!r} maintenue malgré détection {langue_detectee!r} ({len(mots)} mots)")
            question_fr = traduire_en_francais(question, langue_session, llm_model)
            return question_fr, langue_session

    question_fr = traduire_en_francais(question, langue_detectee, llm_model)
    return question_fr, langue_detectee


def nom_langue(code: str) -> str:
    return LANGUES_SUPPORTEES.get(code, code)


def traduire_catalogue(produits: list, langue: str, llm_model: str = _LLM_MODEL) -> list:
    """
    Traduit pour affichage dans le prompt LLM :
      - caracteristiques (texte libre)
      - couleurs uniques (FR → langue cible)

    Les données originales ne sont PAS modifiées — copie locale uniquement.
    Un seul appel LLM pour tous les produits.
    """
    if not produits or langue == "fr":
        return produits

    import copy
    nom_lang = nom_langue(langue)
    produits_trad = copy.deepcopy(produits)

    segments = []
    valeurs  = []

    for i, p in enumerate(produits_trad):
        caract = (p.get("caracteristiques") or "").strip()
        if caract:
            segments.append(("caract", i))
            valeurs.append(caract)

    couleurs_uniques = list(dict.fromkeys(
        c for p in produits_trad for c in p.get("couleurs", []) if c
    ))
    for c in couleurs_uniques:
        segments.append(("couleur", c))
        valeurs.append(c)

    if not valeurs:
        return produits_trad

    combined = " |SEP| ".join(valeurs)
    prompt = (
        f"Translate each French term to {nom_lang}. "
        f"Terms are separated by |SEP|. "
        f"Reply with ONLY the translated terms in the same order, separated by |SEP|. "
        f"Keep product names, brand names, numbers and sizes exactly as-is. "
        f"Input: {combined}\n"
        f"Output:"
    )

    try:
        response = client.chat(
            model=llm_model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 800, "temperature": 0.1},
        )
        raw = response["message"]["content"].strip()

        if "|SEP|" in raw:
            lines = raw.splitlines()
            for line in lines:
                if "|SEP|" in line:
                    raw = line.strip()
                    break

        parts = [p.strip() for p in raw.split("|SEP|")]

        if len(parts) != len(valeurs):
            print(f"[LANG] catalogue : {len(parts)} segments vs {len(valeurs)} attendus → original conservé")
            return produits_trad

        mapping_couleurs = {}
        for (type_, val), trad in zip(segments, parts):
            if type_ == "caract":
                produits_trad[val]["caracteristiques"] = trad
            elif type_ == "couleur":
                mapping_couleurs[val] = trad

        for p in produits_trad:
            p["couleurs"] = [mapping_couleurs.get(c, c) for c in p.get("couleurs", [])]

        print(f"[LANG] catalogue traduit ({nom_lang}) : {len(produits_trad)} produits, "
              f"{len(mapping_couleurs)} couleurs")

    except Exception as e:
        print(f"[LANG] erreur traduction catalogue : {e} → catalogue original conservé")

    return produits_trad