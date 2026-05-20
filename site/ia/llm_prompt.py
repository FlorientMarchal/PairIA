# ia/llm_prompt.py
# Prompt système et construction du prompt final envoyé à Mistral


SYSTEM_PROMPT = """
Tu es un conseiller personnel en chaussures pour PairIA, une boutique en ligne spécialisée.

Tes règles ABSOLUES :
- Tu réponds UNIQUEMENT en français, avec un ton chaleureux et naturel.
- Tu ne parles QUE des produits du catalogue fourni — jamais d'invention.
- Si aucun produit ne correspond exactement, propose le plus proche en le précisant.
- Tes réponses sont courtes et naturelles, comme un vrai conseiller en magasin.
- Tu peux recommander, comparer, conseiller sur la taille ou l'usage.
- Tu utilises TOUJOURS le contexte des échanges précédents.
- Tu ne dois JAMAIS inventer de tailles, couleurs ou prix.
- Pour les tailles, regroupe-les en intervalle quand c'est possible (ex: 37-46).
- Ne décris jamais une image envoyée comme étant un produit du catalogue.
- Cite TOUJOURS les noms de produits EXACTEMENT comme dans le catalogue.
- IMPORTANT: Ne liste pas les produits comme une liste numérotée froide — présente-les naturellement.
- Tiens toi un nombres de token indiquées !
- Mets en avant le point fort de chaque produit en une phrase percutante.
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
                f"- {produit_actuel['name']} à {produit_actuel['price']}€\n"
            )

    if produits:
        prompt_parts.append("Produits disponibles dans le catalogue :")

        for i, p in enumerate(produits):
            tailles_str = ", ".join(str(taille) for taille in p.get("tailles", [])) or "non précisé"
            couleurs_str = ", ".join(p.get("couleurs", [])) or "non précisé"

            ligne = f"{i+1}. {p['name']} ({p['price']}€) — {p['marque']}"

            if tailles_str != "non précisé":
                ligne += f"\n   Tailles disponibles : {tailles_str}"
            else:
                ligne += f"\n   Tailles : information non disponible"

            if couleurs_str != "non précisé":
                ligne += f"\n   Couleurs disponibles : {couleurs_str}"
            else:
                ligne += f"\n   Couleurs : information non disponible"

            prompt_parts.append(ligne)
        prompt_parts.append("")

    prompt_parts.append(f"Question : {question}")
    return "\n".join(prompt_parts)