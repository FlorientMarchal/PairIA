# ia/llm_prompt.py
# Prompt système et construction du prompt final envoyé à Mistral


SYSTEM_PROMPT = """
Tu es un assistant e-commerce spécialisé en chaussures pour le site PairIA.

Tes règles ABSOLUES :
- Tu réponds UNIQUEMENT en français.
- Tu ne parles QUE de chaussures et des produits du catalogue fourni.
- Tu ne dois JAMAIS inventer de produits qui ne sont pas dans le catalogue.
- Si aucun produit ne correspond, dis-le clairement et propose le plus proche.
- Tes réponses sont courtes, claires et utiles (3-5 phrases maximum).
- Tu peux recommander, comparer, conseiller sur la taille ou l'usage.
- Si l'utilisateur veut ajouter un produit au panier, confirme-le.
- Tu ne connais que les produits fournis.
- Si l'utilisateur pose une question sur un produit spécifique, concentre-toi dessus.
- Tu utilises TOUJOURS le contexte des échanges précédents pour répondre.
- Tu ne dois JAMAIS inventer de tailles, couleurs ou prix.
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


def build_prompt(question: str, produits: list, product_id: int = None) -> str:
    prompt_parts = []

    # Contexte fiche produit si on est sur article.php
    if product_id and produits:
        produit_actuel = next((p for p in produits if p["id"] == product_id), None)
        if produit_actuel:
            prompt_parts.append(
                f"L'utilisateur consulte actuellement :\n"
                f"- {produit_actuel['name']} à {produit_actuel['price']}€\n"
            )

    if produits:
        #  AJOUT : filtre par budget si détecté dans la question
        budget = _extraire_budget(question)
        if budget:
            produits_filtres = [p for p in produits if p["price"] <= budget]
            # Si aucun produit ne passe le filtre, on garde tous les produits
            # et on laisse Mistral expliquer qu'il n'y a rien dans ce budget
            if not produits_filtres:
                prompt_parts.append(
                    f"⚠️ Aucun produit dans le catalogue ne coûte moins de {budget}€. "
                    f"Voici les produits les plus proches :"
                )
            else:
                produits = produits_filtres
                prompt_parts.append(
                    f"Produits disponibles sous {budget}€ :"
                )
        else:
            prompt_parts.append("Produits disponibles dans le catalogue :")

        for i, p in enumerate(produits):
            tailles_str  = ", ".join(p.get("tailles",  [])) or "non précisé"
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