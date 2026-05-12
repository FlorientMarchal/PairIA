from sentence_transformers import SentenceTransformer
from rag import qdrant
from image_preprocessing import preprocess_image

# chargement modèle une seule fois
model = SentenceTransformer("clip-ViT-B-32")

def rechercher_produits_similaires(
    image_bytes: bytes,
    nb_produits: int = 3
) -> dict:

    # preprocess
    image = preprocess_image(image_bytes)

    # embedding image
    vecteur = model.encode(image).tolist()

    # recherche Qdrant
    results = qdrant.query_points(
        collection_name="produits_image",
        query=vecteur,
        limit=nb_produits
    ).points

    produits = []

    for r in results:

        tailles_raw  = r.payload.get("tailles", "")
        couleurs_raw = r.payload.get("couleurs", "")

        tailles = [
            t.strip()
            for t in tailles_raw.split(",")
            if t.strip()
        ] if tailles_raw else []

        couleurs = [
            c.strip()
            for c in couleurs_raw.split(",")
            if c.strip()
        ] if couleurs_raw else []

        produits.append({
            "id": r.id,
            "name": r.payload.get("nom", ""),
            "price": r.payload.get("prix", 0),
            "emoji": "👟",
            "categorie": r.payload.get("categorie", ""),
            "marque": r.payload.get("marque", ""),
            "url_image": r.payload.get("url_image", ""),
            "description": r.payload.get("description", ""),
            "tailles": tailles,
            "couleurs": couleurs,
        })

    return {
        "products": produits
    }