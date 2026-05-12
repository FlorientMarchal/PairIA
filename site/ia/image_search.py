# ia/image_search.py
# Recherche de produits similaires à partir d'une image

import ollama
from rag import qdrant
import io
from PIL import Image

SYSTEM_PROMPT_IMAGE = """
Tu es un assistant spécialisé en chaussures.
On te montre une photo de chaussure.
Décris-la en français en quelques mots clés séparés par des virgules :
type, couleur, style, usage, matière si visible.
Réponds UNIQUEMENT avec les mots clés, sans phrase, sans ponctuation finale.
Exemple : baskets, blanc, casual, lifestyle, cuir
""".strip()


def analyser_image(image_bytes: bytes) -> str:
    """
    Envoie l'image à LLaVA et retourne une description textuelle.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.format != 'JPEG':
        buffer = io.BytesIO()
        img.convert('RGB').save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()

    response = ollama.chat(
        model="llava",
        messages=[
            {
                "role": "user",
                "content": SYSTEM_PROMPT_IMAGE,
                "images": [image_bytes]
            }
        ],
        options={"num_predict": 50, "temperature": 0.1}
    )

    return response["message"]["content"]


def rechercher_produits_similaires(image_bytes: bytes, nb_produits: int = 3) -> dict:
    """
    Analyse l'image puis cherche les produits les plus similaires dans Qdrant.
    """
    # Étape 1 : décrire l'image avec LLaVA
    description = analyser_image(image_bytes)
    print(f"Description image : {description}")

    # Étape 2 : vectoriser la description
    embed_response = ollama.embeddings(
        model="nomic-embed-text",
        prompt=description
    )
    vecteur = embed_response["embedding"]

    # Étape 3 : chercher dans Qdrant
    results = qdrant.query_points(
        collection_name="produits",
        query=vecteur,
        limit=nb_produits
    ).points

    produits = []
    for r in results:
        tailles_raw  = r.payload.get("tailles",  "")
        couleurs_raw = r.payload.get("couleurs", "")
        tailles  = [t.strip() for t in tailles_raw.split(",") if t.strip()] if tailles_raw else []
        couleurs = [c.strip() for c in couleurs_raw.split(",") if c.strip()] if couleurs_raw else []

        produits.append({
            "id":          r.id,
            "name":        r.payload.get("nom",         ""),
            "price":       r.payload.get("prix",        0),
            "emoji":       "👟",
            "categorie":   r.payload.get("categorie",   ""),
            "marque":      r.payload.get("marque",      ""),
            "url_image":   r.payload.get("url_image",   ""),
            "description": r.payload.get("description", ""),
            "tailles":     tailles,
            "couleurs":    couleurs,
        })

    return {
        "description": description,
        "products":    produits
    }