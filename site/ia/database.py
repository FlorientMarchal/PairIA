# ia/database.py
import os
from qdrant_client import QdrantClient

_QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")   # "qdrant" en Docker
_QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))

def _create_client() -> QdrantClient:
    try:
        client = QdrantClient(host=_QDRANT_HOST, port=_QDRANT_PORT, timeout=3)
        client.get_collections()
        print(f"[QDRANT] connecté au serveur {_QDRANT_HOST}:{_QDRANT_PORT} ✓")
        return client
    except Exception as e:
        print(f"[QDRANT] serveur indisponible ({e}) → fallback mode fichier")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path  = os.path.join(BASE_DIR, "qdrant_db")
    print(f"[QDRANT] mode fichier : {db_path}")
    return QdrantClient(path=db_path)

qdrant = _create_client()
