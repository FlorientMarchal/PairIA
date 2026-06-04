# -*- coding: utf-8 -*-
# ia/embeeding.py
# Indexation texte (nomic-embed-text) → collection "produits"
# Supporte un article_id optionnel pour un upsert ciblé (pas de recreate)

import os
import sys
import mysql.connector
import ollama

from database import qdrant as client
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, PayloadSchemaType
)

ollama_client = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))

DB_CONFIG = {
    "host":     os.environ.get("MYSQL_HOST",     "localhost"),
    "user":     os.environ.get("MYSQL_USER",     "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "root"),
    "database": os.environ.get("MYSQL_DATABASE", "e_commmerce"),
    "port":     3306
}


def _assure_collection():
    """Crée la collection 'produits' si elle n'existe pas — sans jamais la détruire."""
    collections = [c.name for c in client.get_collections().collections]
    if "produits" not in collections:
        client.create_collection(
            collection_name="produits",
            vectors_config=VectorParams(size=768, distance=Distance.COSINE)
        )
        # Index payload pour filtres natifs
        for field, ftype in [
            ("prix",      PayloadSchemaType.FLOAT),
            ("categorie", PayloadSchemaType.KEYWORD),
            ("marque",    PayloadSchemaType.KEYWORD),
            ("genre",     PayloadSchemaType.KEYWORD),
            ("couleurs",  PayloadSchemaType.KEYWORD),
            ("tailles",   PayloadSchemaType.KEYWORD),
        ]:
            client.create_payload_index("produits", field, ftype)
        print("[EMBED] Collection 'produits' créée avec index payload.")


def indexer_produits(article_id: int = None):
    """
    Vectorise les produits avec nomic-embed-text et les insère via upsert.

    article_id : si fourni, ne traite que cet article.
                 si None, traite tous les articles.
    """
    _assure_collection()

    print("[EMBED] Connexion à MySQL...")
    conn   = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    if article_id:
        cursor.execute("""
            SELECT
                a.id_shoes, a.nom, a.categorie, a.marque, a.genre, a.Prix,
                a.description, a.mots_cles, a.usage, a.caracteristiques,
                a.materiaux, a.url_image,
                GROUP_CONCAT(DISTINCT sc.taille  ORDER BY sc.taille  SEPARATOR ', ') AS tailles,
                GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ', ') AS couleurs
            FROM articles a
            LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
            WHERE a.id_shoes = %s
            GROUP BY a.id_shoes
        """, (article_id,))
    else:
        cursor.execute("""
            SELECT
                a.id_shoes, a.nom, a.categorie, a.marque, a.genre, a.Prix,
                a.description, a.mots_cles, a.usage, a.caracteristiques,
                a.materiaux, a.url_image,
                GROUP_CONCAT(DISTINCT sc.taille  ORDER BY sc.taille  SEPARATOR ', ') AS tailles,
                GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ', ') AS couleurs
            FROM articles a
            LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
            GROUP BY a.id_shoes
            ORDER BY a.id_shoes
        """)

    produits = cursor.fetchall()
    cursor.close()
    conn.close()
    print(f"[EMBED] {len(produits)} produit(s) à indexer.")

    def split_list(val):
        if not val:
            return []
        return [v.strip() for v in val.split(",") if v.strip()]

    nb_ok = nb_err = 0

    for produit in produits:
        tailles_list  = split_list(produit.get("tailles",  ""))
        couleurs_list = split_list(produit.get("couleurs", ""))

        payload = {
            "nom":              str(produit["nom"]             or ""),
            "prix":             float(produit["Prix"]          or 0),
            "categorie":        str(produit["categorie"]       or ""),
            "marque":           str(produit["marque"]          or ""),
            "genre":            str(produit["genre"]           or ""),
            "usage":            str(produit.get("usage")       or ""),
            "tailles":          tailles_list,
            "couleurs":         couleurs_list,
            "url_image":        str(produit.get("url_image")   or ""),
            "description":      str(produit.get("description") or ""),
            "caracteristiques": str(produit.get("caracteristiques") or ""),
            "materiaux":        str(produit.get("materiaux")   or ""),
            "mots_cles":        str(produit.get("mots_cles")   or ""),
        }

        texte = (
            f"{produit['nom']}. "
            f"Marque : {produit['marque']}. "
            f"Catégorie : {produit['categorie']}. "
            f"Genre : {produit['genre']}. "
            f"Usage : {produit.get('usage', '')}. "
            f"Caractéristiques : {produit.get('caracteristiques', '')}. "
            f"Matériaux : {produit.get('materiaux', '')}. "
            f"{produit.get('description', '')} "
            f"Mots clés : {produit.get('mots_cles', '')}. "
            f"Tailles disponibles : {', '.join(tailles_list) or 'non précisé'}. "
            f"Couleurs disponibles : {', '.join(couleurs_list) or 'non précisé'}."
        )

        try:
            embed = ollama_client.embeddings(model="nomic-embed-text", prompt=texte)
            client.upsert(
                collection_name="produits",
                points=[PointStruct(
                    id=produit["id_shoes"],
                    vector=embed["embedding"],
                    payload=payload
                )]
            )
            print(f"[EMBED] ✓ {produit['nom']} | {len(tailles_list)} tailles | {len(couleurs_list)} couleurs")
            nb_ok += 1

        except Exception as e:
            print(f"[EMBED] ✗ Erreur sur {produit['nom']} : {e}")
            nb_err += 1

    print(f"[EMBED] Terminé — {nb_ok} OK, {nb_err} erreurs.")


if __name__ == "__main__":
    # Utilisation : python embeeding.py [article_id]
    aid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    indexer_produits(article_id=aid)