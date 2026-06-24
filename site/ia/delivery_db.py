# ia/delivery_db.py
"""
Gestion des données livraison pour le chatbot PairIA.

Deux cas :
  A) Question générique (délais, retours, zones)  → constante statique
  B) Question sur UNE commande précise du client  → tables commandes + lignes_commande
"""

from db_mysql import fetch_all


# ══════════════════════════════════════════════
# A) INFOS GÉNÉRIQUES — PROMPT STATIQUE
# ══════════════════════════════════════════════

_LIVRAISON_STATIQUE = """Informations livraison & retours PairIA :

Modes de livraison :
- Livraison standard : 3 à 5 jours ouvrés | 4,90 € (gratuite dès 60 €)
- Livraison express : 24 h ouvrées | 9,90 €
- Livraison point relais : 3 à 4 jours ouvrés | 3,90 € (gratuite dès 60 €)
- Livraison gratuite dès 60 € d'achat (standard et relais)

Zones desservies :
- France métropolitaine, Belgique, Suisse, Luxembourg
- Délai +2 jours ouvrés hors France métropolitaine

Suivi de commande :
- Un e-mail avec lien de suivi est envoyé dès l'expédition

Retours :
- Délai : 30 jours après réception
- Conditions : articles non portés, emballage d'origine, étiquettes attachées
- Remboursement : 5 à 7 jours ouvrés sur le moyen de paiement initial
- Procédure : contacter support@pairia.fr pour recevoir une étiquette retour prépayée"""


def get_delivery_info() -> str:
    return _LIVRAISON_STATIQUE


def format_delivery_context(info: str) -> str:
    return info if isinstance(info, str) else _LIVRAISON_STATIQUE


# ══════════════════════════════════════════════
# B) COMMANDES PERSONNALISÉES DU CLIENT
# ══════════════════════════════════════════════

_STATUT_LABELS = {
    "en_attente": "en attente de traitement",
    "payée":      "payée et en cours de préparation",
    "expédiée":   "expédiée et en cours de livraison",
    "livrée":     "livrée",
    "annulée":    "annulée",
}


def get_client_orders(id_client: int) -> list[dict]:
    """Récupère les 10 dernières commandes d'un client avec leurs lignes."""
    if not id_client:
        return []

    try:
        commandes = fetch_all(f"""
            SELECT id_commande, date_commande, statut,
                   sous_total, frais_livraison, total,
                   adresse_livraison
            FROM commandes
            WHERE id_client = {int(id_client)}
            ORDER BY date_commande DESC
            LIMIT 10
        """)
    except Exception as e:
        print(f"[DELIVERY] Erreur récupération commandes client {id_client} : {e}")
        return []

    if not commandes:
        return []

    result = []
    for idx, cmd in enumerate(commandes):
        id_cmd = cmd["id_commande"]

        try:
            lignes = fetch_all(f"""
                SELECT nom_article, taille, couleur, quantite, prix_unitaire
                FROM lignes_commande
                WHERE id_commande = {int(id_cmd)}
            """)
        except Exception as e:
            print(f"[DELIVERY] Erreur lignes commande #{id_cmd} : {e}")
            lignes = []

        result.append({
            "id_commande":       id_cmd,
            "position":          idx + 1,   # 1 = la plus récente
            "date":              str(cmd["date_commande"])[:10],
            "statut_raw":        cmd["statut"],
            "statut_label":      _STATUT_LABELS.get(cmd["statut"], cmd["statut"]),
            "total":             float(cmd["total"]),
            "frais_livraison":   float(cmd["frais_livraison"]),
            "adresse_livraison": cmd.get("adresse_livraison", ""),
            "articles": [
                {
                    "nom":      l["nom_article"],
                    "taille":   l["taille"],
                    "couleur":  l["couleur"],
                    "quantite": l["quantite"],
                    "prix":     float(l["prix_unitaire"]),
                }
                for l in lignes
            ],
        })

    return result


def format_orders_context(commandes: list[dict]) -> str:
    """
    Formate les commandes en contexte pour le LLM.
    Inclut la position (1ère = plus récente, dernière = la plus ancienne)
    pour que le LLM comprenne "ma première commande", "ma dernière commande", etc.
    """
    if not commandes:
        return "Le client n'a aucune commande enregistrée."

    nb = len(commandes)
    lignes = [
        f"Le client a {nb} commande(s) au total.",
        f"La commande n°1 est la PLUS RÉCENTE, la commande n°{nb} est la PLUS ANCIENNE.",
        ""
    ]

    for cmd in commandes:
        articles_str = ", ".join(
            f"{a['nom']} (T{a['taille']}, {a['couleur']}, x{a['quantite']})"
            for a in cmd["articles"]
        ) or "—"

        lignes.append(
            f"• Commande n°{cmd['position']} | ID #{cmd['id_commande']} | Date : {cmd['date']}"
            f" | Statut : {cmd['statut_label'].upper()}"
            f" | Total : {cmd['total']:.2f} euros"
            f" | Articles : {articles_str}"
        )
        if cmd["adresse_livraison"]:
            lignes.append(f"  Adresse : {cmd['adresse_livraison']}")

    lignes.append("")
    lignes.append(
        "INSTRUCTIONS pour répondre :"
        "\n- Si le client dit 'ma dernière commande' → il parle de la commande n°1 (la plus récente)."
        "\n- Si le client dit 'ma première commande' → il parle de la commande avec la date la plus ancienne."
        "\n- Si le client cite un numéro (#X) → cherche l'ID correspondant."
        "\n- Si le client dit 'deuxième commande' → commande n°2 dans la liste ci-dessus."
        "\n- Si la commande demandée n'existe pas → dis-le clairement."
        "\n- Cite toujours le numéro de commande (#ID) dans ta réponse."
    )

    return "\n".join(lignes)


# ══════════════════════════════════════════════
# C) DÉTECTION DU TYPE DE QUESTION LIVRAISON
# ══════════════════════════════════════════════

_MOTS_COMMANDE_PERSONNELLE = [
    # Français
    "ma commande", "mon colis", "ma livraison", "mon achat",
    "j'ai commandé", "j'ai acheté", "que j'ai passé",
    "où est", "où en est", "statut de", "suivi de",
    "quand vais-je recevoir", "quand arrivera", "quand est-ce que",
    "été livré", "été expédié", "pas encore reçu", "toujours pas reçu",
    "commande #", "commande n°", "première commande", "dernière commande",
    "deuxième commande", "troisième commande", "mes commandes",
    # Anglais
    "my order", "my package", "my delivery",
    "where is my", "when will i receive", "order #",
    "my last order", "my first order",
]

_MOTS_GENERIQUES = [
    "délai", "combien de jours", "retourner", "retour", "remboursement",
    "livrez-vous", "vous livrez", "livraison gratuite", "frais de port",
    "express", "relais", "point relais", "belgique", "suisse",
    "politique", "conditions", "how long", "return", "shipping",
]


def detecter_type_question_livraison(question: str) -> str:
    """
    Retourne :
      'personnelle' -> question sur la commande du client
      'generique'   -> question sur la politique de livraison
      'mixte'       -> les deux
    """
    q = question.lower()
    a_perso   = any(mot in q for mot in _MOTS_COMMANDE_PERSONNELLE)
    a_generiq = any(mot in q for mot in _MOTS_GENERIQUES)

    if a_perso and a_generiq:
        return "mixte"
    if a_perso:
        return "personnelle"
    return "generique"