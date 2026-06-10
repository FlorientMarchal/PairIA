import os
import sys
import mysql.connector
from PIL import Image
from sentence_transformers import SentenceTransformer
from qdrant_client.models import Distance, VectorParams, PointStruct

from image_preprocessing import preprocess_image
from database import qdrant

DB_CONFIG = {
    "host":     os.environ.get("MYSQL_HOST",     "localhost"),
    "user":     os.environ.get("MYSQL_USER",     "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "root"),
    "database": os.environ.get("MYSQL_DATABASE", "e_commmerce"),
    "port":     3306
}

COLLECTION_NAME = "produits_image"

# Chargement du modèle CLIP une seule fois au démarrage du module
print("--- Chargement du modèle CLIP (ViT-B-32) ---")
model = SentenceTransformer("clip-ViT-B-32")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _assure_collection():
    """Crée la collection si elle n'existe pas — sans jamais la détruire."""
    collections = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION_NAME not in collections:
        qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=512, distance=Distance.COSINE)
        )
        print(f"[CLIP] Collection '{COLLECTION_NAME}' créée.")


def indexer_images(article_id: int = None):
    """
    Vectorise les images avec CLIP et les insère dans Qdrant via upsert.

    article_id : si fourni, ne traite que cet article.
                 si None, traite tous les articles (ré-indexation complète).
    """
    _assure_collection()

    try:
        conn   = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        if article_id:
            cursor.execute("""
                SELECT a.id_shoes, a.nom, a.categorie, a.marque, a.genre,
                       a.Prix, a.description, a.url_image,
                       GROUP_CONCAT(DISTINCT sc.taille  ORDER BY sc.taille  SEPARATOR ', ') AS tailles,
                       GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ', ') AS couleurs
                FROM articles a
                LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
                WHERE a.id_shoes = %s
                GROUP BY a.id_shoes
            """, (article_id,))
        else:
            cursor.execute("""
                SELECT a.id_shoes, a.nom, a.categorie, a.marque, a.genre,
                       a.Prix, a.description, a.url_image,
                       GROUP_CONCAT(DISTINCT sc.taille  ORDER BY sc.taille  SEPARATOR ', ') AS tailles,
                       GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ', ') AS couleurs
                FROM articles a
                LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
                GROUP BY a.id_shoes
            """)

        produits = cursor.fetchall()
        cursor.close()
        conn.close()
        print(f"[CLIP] {len(produits)} produit(s) à indexer.")

    except Exception as e:
        print(f"[CLIP] ❌ Erreur MySQL : {e}")
        return

    nb_ok = nb_err = 0

    for produit in produits:
        nom           = produit['nom']
        image_raw_url = produit.get("url_image", "")

        if not image_raw_url:
            print(f"[CLIP] ✗ Saut {nom} : pas d'image.")
            nb_err += 1
            continue

        # Normalise le nom de fichier (supprime le préfixe "images/" s'il est présent)
        filename  = image_raw_url.replace("images/", "").replace("/images/", "").lstrip("/")
        image_path = os.path.join(BASE_DIR, "images", filename)

        if not os.path.exists(image_path):
            print(f"[CLIP] ✗ Image introuvable : {image_path}")
            nb_err += 1
            continue

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            image_calculee = preprocess_image(image_bytes)
            embedding      = model.encode(image_calculee).tolist()

            # upsert — ajoute ou met à jour sans toucher aux autres points
            qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=[PointStruct(
                    id=int(produit["id_shoes"]),
                    vector=embedding,
                    payload={
                        "nom":        str(produit.get("nom")         or ""),
                        "prix":       float(produit.get("Prix")      or 0),
                        "categorie":  str(produit.get("categorie")   or ""),
                        "marque":     str(produit.get("marque")      or ""),
                        "description":str(produit.get("description") or ""),
                        "tailles":    str(produit.get("tailles")     or ""),
                        "couleurs":   [c.strip() for c in str(produit.get("couleurs") or "").split(",") if c.strip()],
                        "url_image":  "images/" + filename,
                    }
                )]
            )
            print(f"[CLIP] ✓ {nom}")
            nb_ok += 1

        except Exception as e:
            print(f"[CLIP] ❌ Erreur sur {nom} : {e}")
            nb_err += 1

    print(f"[CLIP] Terminé — {nb_ok} OK, {nb_err} erreurs.")


if __name__ == "__main__":
    # Utilisation : python embeeding_images.py [article_id]
    aid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    indexer_images(article_id=aid)