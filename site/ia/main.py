# ia/main.py
# Serveur FastAPI — point d'entrée de l'API chatbot
# Lancer avec : uvicorn main:app --reload --port 8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag import get_response

app = FastAPI(title="PairIA — API Chatbot")

# CORS : autorise le frontend PHP à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:80", "http://127.0.0.1"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modèle de la requête entrante
class ChatRequest(BaseModel):
    question: str
    product_id: int | None = None  # si on est sur une fiche produit

# Modèle de la réponse
class Product(BaseModel):
    id: int
    name: str
    price: float
    emoji: str | None = None

class ChatResponse(BaseModel):
    message: str
    products: list[Product] = []
    action: str | None = None       # "add_to_cart" si le LLM veut ajouter au panier
    product_id: int | None = None
    quantity: int | None = None

# ── Routes ──

@app.get("/")
def root():
    return {"status": "PairIA API en ligne"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Reçoit une question, fait le RAG, retourne la réponse du LLM.
    """
    result = get_response(
        question=request.question,
        product_id=request.product_id
    )
    return result

@app.get("/health")
def health():
    return {"status": "ok"}