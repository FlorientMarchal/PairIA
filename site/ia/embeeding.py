# -*- coding: utf-8 -*-
# ia/embeeding.py
# Script d'indexation : lit les produits depuis MySQL et les stocke dans Qdrant
# Commande : py embeeding.py

import ollama
import mysql.connector
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# ── Config MySQL ──
DB_CONFIG = {
    "host":     "127.0.0.1",
    "user":     "root",
    "password": "root",
    "database": "e_commmerce",
    "port":     3306
}

def indexer_produits():
    # ── Connexion MySQL ──
    print("Connexion à MySQL...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # Jointure articles + size_color
    # GROUP_CONCAT regroupe toutes les tailles et couleurs en une seule ligne par produit
    cursor.execute("""
        SELECT
            a.id_shoes,
            a.nom,
            a.categorie,
            a.marque,
            a.genre,
            a.Prix,
            a.description,
            a.mots_cles,
            a.usage,
            a.caracteristiques,
            a.materiaux,
            a.url_image,
            GROUP_CONCAT(DISTINCT sc.taille ORDER BY sc.taille SEPARATOR ', ') AS tailles,
            GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ', ') AS couleurs
        FROM articles a
        LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
        GROUP BY a.id_shoes
        ORDER BY a.id_shoes
    """)
    produits = cursor.fetchall()
    cursor.close()
    conn.close()

    # ── Connexion Qdrant ──
    print("Connexion à Qdrant...")
    client = QdrantClient(path="./qdrant_db")

    try:
        client.delete_collection("produits")
        print("Ancienne collection supprimée.")
    except Exception:
        pass

    client.create_collection(
        collection_name="produits",
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )

    # ── Indexation ──
    print("Indexation en cours...")
    nb_ok  = 0
    nb_err = 0

    for produit in produits:
        # Texte riche à vectoriser — plus il est complet, meilleures sont les recherches
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
            f"Tailles disponibles : {produit.get('tailles', 'non précisé')}. "
            f"Couleurs disponibles : {produit.get('couleurs', 'non précisé')}."
        )

        try:
            embed = ollama.embeddings(
                model="nomic-embed-text",
                prompt=texte
            )

            client.upsert(
                collection_name="produits",
                points=[PointStruct(
                    id=produit["id_shoes"],
                    vector=embed["embedding"],
                    payload={
                        "nom":              produit["nom"],
                        "prix":             float(produit["Prix"]),
                        "categorie":        str(produit["categorie"] or ""),
                        "marque":           str(produit["marque"] or ""),
                        "genre":            str(produit["genre"] or ""),
                        "usage":            str(produit.get("usage") or ""),
                        "tailles":          str(produit.get("tailles") or ""),
                        "couleurs":         str(produit.get("couleurs") or ""),
                        "url_image":        str(produit.get("url_image") or ""),
                        "description":      str(produit.get("description") or ""),
                        "caracteristiques": str(produit.get("caracteristiques") or ""),
                        "materiaux":        str(produit.get("materiaux") or ""),
                        "mots_cles":        str(produit.get("mots_cles") or ""),
                        "stock_total":      int(produit.get("stock_total") or 0)
                    }
                )]
            )

            print(f"  ✓ {produit['nom']} | Tailles : {produit.get('tailles', '?')} | Couleurs : {produit.get('couleurs', '?')}")
            nb_ok += 1

        except Exception as e:
            print(f"  ✗ Erreur sur {produit['nom']} : {e}")
            nb_err += 1

    print(f"\nIndexation terminée — {nb_ok} produits indexés, {nb_err} erreurs.")

if __name__ == "__main__":
    indexer_produits()