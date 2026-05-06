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
    cursor.execute("""
        SELECT id_shoes, nom, categorie, marque, genre,
               Prix, description, mots_cles, url_image
        FROM articles
        ORDER BY id_shoes
    """)
    produits = cursor.fetchall()
    cursor.close()
    conn.close()
    print(f"{len(produits)} produits trouvés.")

    # ── Connexion Qdrant (fichier local) ──
    print("Connexion à Qdrant...")
    client = QdrantClient(path="./qdrant_db")

    # Supprimer et recréer la collection
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
    nb_ok = 0
    nb_err = 0

    for produit in produits:
        texte = (
            f"{produit['nom']}. "
            f"Marque : {produit['marque']}. "
            f"Catégorie : {produit['categorie']}. "
            f"Genre : {produit['genre']}. "
            f"{produit.get('description', '')} "
            f"Mots clés : {produit.get('mots_cles', '')}."
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
                        "nom":       produit["nom"],
                        "prix":      float(produit["Prix"]),
                        "categorie": str(produit["categorie"] or ""),
                        "marque":    str(produit["marque"] or ""),
                        "genre":     str(produit["genre"] or ""),
                        "url_image": str(produit.get("url_image") or "")
                    }
                )]
            )

            print(f"  ✓ {produit['nom']} ({produit['Prix']} €)")
            nb_ok += 1

        except Exception as e:
            print(f"  ✗ Erreur sur {produit['nom']} : {e}")
            nb_err += 1

    print(f"\nIndexation terminée — {nb_ok} produits indexés, {nb_err} erreurs.")

if __name__ == "__main__":
    indexer_produits()