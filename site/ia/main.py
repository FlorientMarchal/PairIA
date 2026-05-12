# ia/main.py
# Serveur FastAPI
# Lancer avec : uvicorn main:app --reload --port 8000

import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from rag import get_response, get_response_stream
from fastapi import File, UploadFile
from image_search import rechercher_produits_similaires

app = FastAPI(title="API Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    product_id: int | None = None
    history: list[HistoryMessage] = []

class Product(BaseModel):
    id: int
    name: str
    price: float
    emoji: str | None = None
    url_image: str | None = None
    tailles: list[str] = []
    couleurs: list[str] = []

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
        product_id=request.product_id,
        history=[{"role": m.role, "content": m.content} for m in request.history]
    )
    return result

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    history = [{"role": m.role, "content": m.content} for m in request.history]

    def generate():
        generator = get_response_stream(
            question=request.question,
            product_id=request.product_id,
            history=history
        )
        metadata = next(generator)
        yield f"data: {json.dumps(metadata)}\n\n"
        for chunk in generator:
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/search-image")
async def search_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = rechercher_produits_similaires(image_bytes)
    return result