# ia/llm_prompt.py
# Prompt système et construction du prompt final envoyé à Mistral


def get_system_prompt(tutoiement: str = "tu") -> str:
    pronom = "tu" if tutoiement == "tu" else "vous"
    imperatif = "Tutoie" if tutoiement == "tu" else "Vouvoyez"
    return f"""
Tu es un conseiller personnel en chaussures pour PairIA, une boutique en ligne spécialisée.
Tu t'adresses DIRECTEMENT au client à la deuxième personne ("{pronom}"). Jamais de narration ("le client", "l'utilisateur").
{imperatif} le client SYSTÉMATIQUEMENT et de façon cohérente tout au long de la conversation.
Ton naturel, chaleureux, comme un vrai vendeur en magasin. Réponses courtes (1-3 phrases max).

Règles strictes :
- Réponds UNIQUEMENT en français.
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


def build_prompt(question: str, produits: list, product_id: int = None, genre: str = None, is_image_search: bool = False, contexte_filtres: str = ""):
    prompt_parts = []
    if contexte_filtres:
        prompt_parts.append(contexte_filtres + "\n")
    if is_image_search:
        prompt_parts.append(
        "NOTE : L'utilisateur a envoyé une photo de chaussures. "
        "Présente simplement les produits similaires trouvés SANS décrire l'image envoyée "
        "et SANS inventer de caractéristiques visuelles que tu n'as pas vues.\n"
    )
    #Detection du genre pour contextualiser la réponse (si mentionné dans les échanges précédents)
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
        prompt_parts.append("Produits disponibles dans le catalogue :")

        for i, p in enumerate(produits):
            tailles_str = ", ".join(str(taille) for taille in p.get("tailles", [])) or "non précisé"
            couleurs_str = ", ".join(p.get("couleurs", [])) or "non précisé"

            ligne = f"{i+1}. {p['name']} — prix : {p['price']:.2f}€ — marque : {p['marque']}"

            if tailles_str != "non précisé":
                ligne += f"\n   Tailles disponibles : {tailles_str}"
            else:
                ligne += f"\n   Tailles : information non disponible"

            if couleurs_str != "non précisé":
                ligne += f"\n   Couleurs disponibles : {couleurs_str}"
            else:
                ligne += f"\n   Couleurs : information non disponible"

            if p.get("caracteristiques"):
                ligne += f"\n   Caractéristiques : {p['caracteristiques']}"

            prompt_parts.append(ligne)
        prompt_parts.append("")

    prompt_parts.append(f"Question : {question}")
    return "\n".join(prompt_parts)