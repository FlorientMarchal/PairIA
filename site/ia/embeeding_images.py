import os
import io
import mysql.connector
from PIL import Image
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Import de ta fonction de prétraitement
from image_preprocessing import preprocess_image

# =========================================================
# CONFIGURATION
# =========================================================

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "root",  # Remplace par ton mot de passe si besoin
    "database": "e_commmerce",
    "port": 3306
}

COLLECTION_NAME = "produits_image"

# On utilise Qdrant en local (dossier persistant)
qdrant = QdrantClient(path="./qdrant_db")

qdrant.recreate_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=512, distance=Distance.COSINE)
)

# Chargement du modèle CLIP (512 dimensions)
print("--- Chargement du modèle CLIP (ViT-B-32) ---")
model = SentenceTransformer("clip-ViT-B-32")

# =========================================================
# FONCTION PRINCIPALE D'INDEXATION
# =========================================================

def indexer_images():
    # 1. Connexion MySQL et récupération des données
    print("Connexion MySQL...")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                a.id_shoes, a.nom, a.categorie, a.marque, a.genre, 
                a.Prix, a.description, a.url_image,
                GROUP_CONCAT(DISTINCT sc.taille ORDER BY sc.taille SEPARATOR ', ') AS tailles,
                GROUP_CONCAT(DISTINCT sc.couleur ORDER BY sc.couleur SEPARATOR ', ') AS couleurs
            FROM articles a
            LEFT JOIN size_color sc ON sc.id_shoes = a.id_shoes
            GROUP BY a.id_shoes
        """)
        produits = cursor.fetchall()
        cursor.close()
        conn.close()
        print(f"-> {len(produits)} produits trouvés dans la base SQL.")
    except Exception as e:
        print(f"❌ Erreur connexion MySQL : {e}")
        return

    # 2. Réinitialisation de la collection Qdrant
    print(f"Réinitialisation de la collection '{COLLECTION_NAME}'...")
    qdrant.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

    # 3. Boucle d'indexation
    nb_ok = 0
    nb_err = 0

    for produit in produits:
        nom_produit = produit['nom']
        image_filename = produit.get("url_image")

        if not image_filename:
            print(f"✗ Saut : {nom_produit} (pas d'URL image)")
            nb_err += 1
            continue

        # --- Nettoyage du chemin venant de MySQL ---
        image_filename = image_filename.replace("images/", "").replace("/images/", "")

        # --- Construction du chemin absolu vers l'image ---
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.abspath(os.path.join(BASE_DIR, "..", "images", image_filename))

        if not os.path.exists(image_path):
            print(f"✗ Image introuvable : {image_path}")
            nb_err += 1
            continue

        try:
            # --- ÉTAPE A : Prétraitement (Suppression fond + Redimensionnement) ---
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            image_calculee = preprocess_image(image_bytes)

            # --- ÉTAPE B : Embedding CLIP ---
            embedding = model.encode(image_calculee).tolist()

            # --- ÉTAPE C : Insertion Qdrant ---
            qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=int(produit["id_shoes"]),
                        vector=embedding,
                        payload={
                            "nom": str(produit.get("nom") or ""),
                            "prix": float(produit.get("Prix") or 0),
                            "categorie": str(produit.get("categorie") or ""),
                            "marque": str(produit.get("marque") or ""),
                            "description": str(produit.get("description") or ""),
                            "tailles": str(produit.get("tailles") or ""),
                            "couleurs": str(produit.get("couleurs") or ""),
                            "url_image": image_filename
                        }
                    )
                ]
            )
            print(f"✓ Indexé : {nom_produit}")
            nb_ok += 1

        except Exception as e:
            print(f"❌ Erreur sur {nom_produit} : {e}")
            nb_err += 1

    print("\n" + "="*30)
    print("INDEXATION TERMINÉE")
    print(f"Succès : {nb_ok}")
    print(f"Échecs : {nb_err}")
    print("="*30)

if __name__ == "__main__":
    indexer_images()
