# ia/embeddings.py
# Script d'indexation : lit les produits depuis MySQL et les stocke dans Chroma DB
# À lancer UNE SEULE FOIS au départ, puis à relancer quand le catalogue change
# Commande : py embeddings.py

import ollama
import chromadb
import mysql.connector

# ── Config MySQL (même que bd.php) ──
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "root",
    "database": "pairia",
    "port":     3306
}

def indexer_produits():
    print("Connexion à MySQL...")
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    # Récupérer tous les produits
    cursor.execute("SELECT id, nom, categorie, description, prix, emoji FROM produits")
    produits = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"{len(produits)} produits trouvés.")

    # ── Connexion à Chroma DB ──
    print("Connexion à Chroma DB...")
    client = chromadb.PersistentClient(path="./chroma_db")

    # Supprimer et recréer la collection pour repartir propre
    try:
        client.delete_collection("produits")
    except:
        pass

    collection = client.create_collection(name="produits")

    # ── Indexation ──
    print("Indexation en cours...")

    for produit in produits:
        # Texte à vectoriser : nom + catégorie + description
        texte = f"{produit['nom']}. Catégorie : {produit['categorie']}. {produit.get('description', '')}"

        # Vectoriser avec nomic-embed-text via Ollama
        embed = ollama.embeddings(
            model="nomic-embed-text",
            prompt=texte
        )

        # Stocker dans Chroma DB
        collection.add(
            ids=[str(produit["id"])],
            embeddings=[embed["embedding"]],
            documents=[texte],
            metadatas={
                "id":    produit["id"],
                "nom":   produit["nom"],
                "prix":  float(produit["prix"]),
                "emoji": produit.get("emoji", "👟"),
                "categorie": produit["categorie"]
            }
        )

        print(f"  ✓ {produit['nom']}")

    print(f"\nIndexation terminée — {len(produits)} produits indexés dans Chroma DB.")

if __name__ == "__main__":
    indexer_produits()