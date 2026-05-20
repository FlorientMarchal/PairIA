# Test direct dans un script Python
from sentence_transformers import SentenceTransformer
from image_preprocessing import preprocess_image
from database import qdrant

model = SentenceTransformer("clip-ViT-B-32")

# Charge exactement le fichier indexé
with open("../images/image1.png", "rb") as f:
    image_bytes = f.read()

img = preprocess_image(image_bytes)
vec = model.encode(img).tolist()

results = qdrant.query_points(
    collection_name="produits_image",
    query=vec,
    limit=3
).points

for r in results:
    print(f"{r.payload.get('nom')} | score={r.score:.4f}")