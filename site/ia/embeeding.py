# ia/embeeding.py
# Script d'indexation : lit les produits depuis MySQL et les stocke dans Qdrant
# Commande : py embeeding.py
#
# CHANGEMENTS vs version précédente :
#   - tailles et couleurs stockées en LISTES (filtres natifs Qdrant)
#   - prix, genre, categorie, marque indexés pour filtrage natif
#   - création des index payload pour accélérer les filtres

import ollama
import mysql.connector
from database import qdrant as client
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    PayloadSchemaType
)

DB_CONFIG = {
    "host":     "127.0.0.1",
    "user":     "root",
    "password": "root",
    "database": "e_commmerce",
    "port":     3306
}

def indexer_produits():
    print("Connexion à MySQL...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

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
    print(f"{len(produits)} produits trouvés.")

    print("Connexion à Qdrant...")
    # client = QdrantClient(path="./qdrant_db")

    # Recrée la collection proprement
    for collection in ["produits", "produits_image"]:
        try:
            client.delete_collection(collection)
            print(f"Ancienne collection '{collection}' supprimée.")
        except Exception:
            pass

    # Collection texte (nomic-embed-text, 768 dims)
    client.create_collection(
        collection_name="produits",
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )

    # Collection image (CLIP, 512 dims)
    client.create_collection(
        collection_name="produits_image",
        vectors_config=VectorParams(size=512, distance=Distance.COSINE)
    )

    # ── Index payload pour filtres natifs rapides ──
    # Sans ces index, Qdrant fait un scan complet à chaque filtre
    for collection in ["produits", "produits_image"]:
        client.create_payload_index(collection, "prix",      PayloadSchemaType.FLOAT)
        client.create_payload_index(collection, "categorie", PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection, "marque",    PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection, "genre",     PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection, "couleurs",  PayloadSchemaType.KEYWORD)
        client.create_payload_index(collection, "tailles",   PayloadSchemaType.KEYWORD)
    print("Index payload créés.")

    print("Indexation en cours...")
    nb_ok = nb_err = 0

    for produit in produits:
        # Découpe les strings MySQL en vraies listes Python
        def split_list(val: str) -> list[str]:
            if not val:
                return []
            return [v.strip() for v in val.split(",") if v.strip()]

        tailles_list  = split_list(produit.get("tailles",  ""))
        couleurs_list = split_list(produit.get("couleurs", ""))

        # Payload unifié — tailles et couleurs en LISTES pour filtrage natif
        payload = {
            "nom":              str(produit["nom"] or ""),
            "prix":             float(produit["Prix"] or 0),
            "categorie":        str(produit["categorie"] or ""),
            "marque":           str(produit["marque"] or ""),
            "genre":            str(produit["genre"] or ""),
            "usage":            str(produit.get("usage") or ""),
            "tailles":          tailles_list,   # ← liste, pas string
            "couleurs":         couleurs_list,  # ← liste, pas string
            "url_image":        str(produit.get("url_image") or ""),
            "description":      str(produit.get("description") or ""),
            "caracteristiques": str(produit.get("caracteristiques") or ""),
            "materiaux":        str(produit.get("materiaux") or ""),
            "mots_cles":        str(produit.get("mots_cles") or ""),
        }

        # Texte riche pour l'embedding nomic
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
            # Embedding texte (nomic) → collection produits
            embed_texte = ollama.embeddings(model="nomic-embed-text", prompt=texte)
            client.upsert(
                collection_name="produits",
                points=[PointStruct(
                    id=produit["id_shoes"],
                    vector=embed_texte["embedding"],
                    payload=payload
                )]
            )

            # Embedding image (CLIP) → collection produits_image
            # Importe le modèle CLIP local
            from image_search import model as clip_model
            from PIL import Image
            import os

            image_path = os.path.join("../images", produit.get("url_image", ""))
            if os.path.exists(image_path):
                clip_vec = clip_model.encode(Image.open(image_path)).tolist()
            else:
                # Fallback : encode le texte avec CLIP si pas d'image
                clip_vec = clip_model.encode(texte).tolist()

            client.upsert(
                collection_name="produits_image",
                points=[PointStruct(
                    id=produit["id_shoes"],
                    vector=clip_vec,
                    payload=payload
                )]
            )

            print(f"  ✓ {produit['nom']} | {len(tailles_list)} tailles | {len(couleurs_list)} couleurs")
            nb_ok += 1

        except Exception as e:
            print(f"  ✗ Erreur sur {produit['nom']} : {e}")
            nb_err += 1

    print(f"\nIndexation terminée — {nb_ok} produits indexés, {nb_err} erreurs.")
    print("\nIndex payload disponibles pour filtres natifs :")
    print("  prix (float) — ex: Range(lte=80)")
    print("  categorie (keyword) — ex: MatchAny(['Talons', 'Sandales'])")
    print("  marque (keyword) — ex: MatchValue('Nike')")
    print("  genre (keyword) — ex: MatchValue('Femme')")
    print("  couleurs (keyword) — ex: MatchAny(['Rouge', 'Bleu'])")
    print("  tailles (keyword) — ex: MatchValue('42')")

if __name__ == "__main__":
    indexer_produits()