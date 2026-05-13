# ia/database.py
import os
from qdrant_client import QdrantClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(BASE_DIR, "qdrant_db")

# On initialise le client ici
qdrant = QdrantClient(path=db_path)