# ia/main.py
# Serveur FastAPI
# Lancer avec : py -m uvicorn main:app --reload --port 8000

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag import get_response

app = FastAPI(title="PairIA — API Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    product_id: int | None = None

class Product(BaseModel):
    id: int
    name: str
    price: float
    emoji: str | None = None
    url_image: str | None = None

class ChatResponse(BaseModel):
    message: str
    products: list[Product] = []
    action: str | None = None
    product_id: int | None = None
    quantity: int | None = None

@app.get("/")
def root():
    return {"status": "PairIA API en ligne"}

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result = get_response(
        question=request.question,
        product_id=request.product_id
    )
    return result

@app.get("/health")
def health():
    return {"status": "ok"}