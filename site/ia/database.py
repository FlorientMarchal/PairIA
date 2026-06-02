# ia/database.py
import os
from qdrant_client import QdrantClient

# ── Connexion Qdrant ──────────────────────────────────────────────────────────
# Mode serveur (recommandé pour multi-workers) : Qdrant tourne en processus
# séparé sur le port 6333, tous les workers s'y connectent via HTTP.
#
# Pour lancer Qdrant server :
#   Windows : qdrant.exe  (dans le dossier site/ia/qdrant-server/)
#   Linux   : ./qdrant
#
# Fallback automatique en mode fichier si le serveur est indisponible
# (utile pour les scripts d'embedding qui tournent seuls).

_QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
_QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

def _create_client() -> QdrantClient:
    # Essayer le mode serveur en premier
    try:
        client = QdrantClient(host=_QDRANT_HOST, port=_QDRANT_PORT, timeout=3)
        # Vérifier que le serveur répond
        client.get_collections()
        print(f"[QDRANT] connecté au serveur {_QDRANT_HOST}:{_QDRANT_PORT} ✓")
        return client
    except Exception as e:
        print(f"[QDRANT] serveur indisponible ({e}) → fallback mode fichier")

    # Fallback mode fichier (scripts d'embedding, etc.)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path  = os.path.join(BASE_DIR, "qdrant_db")
    print(f"[QDRANT] mode fichier : {db_path}")
    return QdrantClient(path=db_path)

qdrant = _create_client()