# ia/prompt.py
# Prompt système et construction du prompt final envoyé à Mistral

SYSTEM_PROMPT = """
Tu es un assistant e-commerce spécialisé en chaussures pour le site PairIA.

Tes règles :
- Tu réponds UNIQUEMENT en français.
- Tu ne parles QUE de chaussures et des produits du catalogue fourni.
- Tu ne dois JAMAIS inventer de produits qui ne sont pas dans le catalogue.
- Si aucun produit ne correspond, dis-le clairement et propose de reformuler.
- Tes réponses sont courtes, claires et utiles (3-5 phrases maximum).
- Tu peux recommander, comparer, conseiller sur la taille ou l'usage.
- Si l'utilisateur veut ajouter un produit au panier, confirme-le.
- Tu ne discutes pas de sujets hors du catalogue de chaussures.
- Ne dis JAMAIS qu'un produit n'est pas dans le catalogue sans en être certain.
- Tu ne dois JAMAIS dire qu'un produit n'existe pas — tu ne connais que les produits fournis.

""".strip()


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

    # Produits trouvés par le RAG
    if produits:
        prompt_parts.append("Produits disponibles dans le catalogue :")
        for p in produits:
            prompt_parts.append(
                f"- {p['name']} ({p['price']}€) — {p['categorie']} — {p['marque']}"
            )
        prompt_parts.append("")

    # Question utilisateur
    prompt_parts.append(f"Question : {question}")

    return "\n".join(prompt_parts)