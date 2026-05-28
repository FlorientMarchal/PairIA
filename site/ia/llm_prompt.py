# ia/llm_prompt.py
# Prompt système et construction du prompt final envoyé au LLM


def get_system_prompt(tutoiement: str = "tu", langue: str = "fr") -> str:
    """
    Construit le prompt système.

    Paramètres :
        tutoiement : "tu" ou "vous"
        langue     : code ISO 639-1 de la langue du client (ex: "en", "es", "fr")
                     → force explicitement la langue de réponse dans le prompt
    """
    from language_utils import nom_langue

    pronom = "tu" if tutoiement == "tu" else "vous"
    imperatif = "Tutoie" if tutoiement == "tu" else "Vouvoyez"

    # Instruction de langue : explicite si différent du français
    if langue and langue != "fr":
        instruction_langue = (
            f"IMPORTANT : le client te parle en {nom_langue(langue)}. "
            f"Tu DOIS répondre UNIQUEMENT en {nom_langue(langue)}, sans exception. "
            "N'utilise jamais le français dans ta réponse."
        )
    else:
        instruction_langue = "Réponds en français."

    return f"""
Tu es un conseiller personnel en chaussures pour PairIA, une boutique en ligne spécialisée.
Tu t'adresses DIRECTEMENT au client à la deuxième personne ("{pronom}"). Jamais de narration ("le client", "l'utilisateur").
{imperatif} le client SYSTÉMATIQUEMENT et de façon cohérente tout au long de la conversation.
Ton naturel, chaleureux, comme un vrai vendeur en magasin. Réponses courtes (1-3 phrases max).

{instruction_langue}

Règles strictes :
- Ne parle QUE des produits du catalogue fourni. Si rien ne correspond exactement, propose le plus proche en le précisant.
- Cite les noms de produits EXACTEMENT comme dans le catalogue. N'invente jamais tailles, couleurs ou prix.
- Pour décrire un produit, utilise UNIQUEMENT les caractéristiques présentes dans le catalogue. N'ajoute AUCUN détail inventé — par exemple n'invente jamais de matériaux ("ammonium", "néoprène"...) si ce n'est pas écrit explicitement.
- Regroupe les tailles en intervalle quand possible (ex : 37-46).
- Présente les produits naturellement, JAMAIS en liste numérotée.
- Si le prompt contient "Ne commence pas par Bonjour", ne commence JAMAIS par une salutation.
- Ne décris jamais une image envoyée comme un produit du catalogue.
- N'utilise JAMAIS de markdown : pas de **, *, #, listes à tirets ou numérotées. Texte brut uniquement.
- N'utilise jamais de formules génériques comme "En tant que conseiller", "Bien sûr !", "Je te recommande donc", "voici les alternatives". Va droit au but.
- Ne répète JAMAIS la question du client dans ta réponse. Réponds directement.
""".strip()



def _extraire_budget(question: str):
    """
    Détecte un budget maximum dans la question.
    Exemples : "moins de 40 euros", "max 50€", "pas plus de 60€"
    Retourne un float ou None si pas de budget détecté.
    """
    import re
    # Cherche des patterns comme "moins de 40", "max 50", "pas plus de 60"
    patterns = [
        r"moins de\s+(\d+)",
        r"max(?:imum)?\s+(\d+)",
        r"pas plus de\s+(\d+)",
        r"jusqu['\s]à\s+(\d+)",
        r"budget\s+(\d+)",
        r"(\d+)\s*€?\s*max",
        r"sous\s+(\d+)",
    ]
    q = question.lower()
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            return float(match.group(1))
    return None


def build_prompt(
    question: str,
    produits: list,
    product_id: int = None,
    genre: str = None,
    is_image_search: bool = False,
    contexte_filtres: str = "",
    langue: str = "fr",
):
    """
    Construit le prompt utilisateur final.

    Le paramètre `langue` est utilisé pour indiquer au LLM dans quelle langue
    répondre lorsque la question originale n'était pas en français
    (elle a été traduite en FR pour la recherche, mais la réponse doit être
    dans la langue du client).
    """
    from language_utils import nom_langue

    prompt_parts = []
    if contexte_filtres:
        prompt_parts.append(contexte_filtres + "\n")
    if is_image_search:
        prompt_parts.append(
        "NOTE : L'utilisateur a envoyé une photo de chaussures. "
        "Présente simplement les produits similaires trouvés SANS décrire l'image envoyée "
        "et SANS inventer de caractéristiques visuelles que tu n'as pas vues.\n"
    )
    # Détection du genre pour contextualiser la réponse
    if genre:
        prompt_parts.append(f"Contexte : l'utilisateur recherche des chaussures pour {genre}.\n")

    # Contexte fiche produit si on est sur article.php
    if product_id and produits:
        produit_actuel = next((p for p in produits if p["id"] == product_id), None)
        if produit_actuel:
            prompt_parts.append(
                f"L'utilisateur consulte actuellement :\n"
                f"- {produit_actuel['name']} à {produit_actuel['price']:.2f}€\n"
            )

    if produits:
        # Pré-traduire les caractéristiques si la langue n'est pas le français.
        # Un seul appel LLM pour tous les produits.
        if langue and langue != "fr":
            from language_utils import traduire_catalogue
            produits = traduire_catalogue(produits, langue)

        # ✅ CORRIGÉ — labels traduits selon la langue du client
        if langue and langue != "fr":
            lbl_prix     = "price"
            lbl_marque   = "brand"
            lbl_tailles  = "Available sizes"
            lbl_couleurs = "Available colors"
            lbl_caract   = "Features"
            lbl_na       = "not specified"
        else:
            lbl_prix     = "prix"
            lbl_marque   = "marque"
            lbl_tailles  = "Tailles disponibles"
            lbl_couleurs = "Couleurs disponibles"
            lbl_caract   = "Caractéristiques"
            lbl_na       = "non précisé"

        prompt_parts.append("Produits disponibles dans le catalogue :")

        for i, p in enumerate(produits):
            tailles_str = ", ".join(str(taille) for taille in p.get("tailles", [])) or lbl_na
            couleurs_str = ", ".join(p.get("couleurs", [])) or lbl_na

            ligne = f"{i+1}. {p['name']} — {lbl_prix} : {p['price']:.2f}€ — {lbl_marque} : {p['marque']}"

            if tailles_str != lbl_na:
                ligne += f"\n   {lbl_tailles} : {tailles_str}"
            else:
                ligne += f"\n   {lbl_tailles} : {lbl_na}"

            if couleurs_str != lbl_na:
                ligne += f"\n   {lbl_couleurs} : {couleurs_str}"
            else:
                ligne += f"\n   {lbl_couleurs} : {lbl_na}"

            if p.get("caracteristiques"):
                ligne += f"\n   {lbl_caract} : {p['caracteristiques']}"

            prompt_parts.append(ligne)
        prompt_parts.append("")

    # Rappel de langue dans le prompt utilisateur (renforcement)
    if langue and langue != "fr":
        prompt_parts.append(
            f"[RAPPEL : réponds en {nom_langue(langue)}, pas en français]\n"
        )

    prompt_parts.append(f"Le client cherche : {question}\nRéponds directement sans répéter cette phrase :")
    return "\n".join(prompt_parts)