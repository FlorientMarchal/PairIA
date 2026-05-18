# ia/main.py
# Serveur FastAPI
# Lancer avec : uvicorn main:app --reload --port 8000
#Lancement kardiatou: uvicorn ia.main:app --reload --port 8000 ou python -m uvicorn ia.main:app --port 8000


import sys
import os
import json
import time
import tempfile
import whisper
import shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from rag import get_response, get_response_stream
from image_search import model as clip_model, rechercher_produits_similaires
from PIL import Image

app = FastAPI(title="API Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# ✅ Charger le modèle Whisper une seule fois au démarrage
print("Chargement du modèle Whisper...")
whisper_model = whisper.load_model("small")
print("Whisper prêt ✓")

# ── Stockage temporaire des vecteurs image par session ──
# { session_id: {"vector": [...], "ts": timestamp} }
_image_vectors: dict = {}

def _clean_old_vectors(max_age_seconds: int = 3600):
    """Supprime les vecteurs de plus d'1h"""
    now = time.time()
    expired = [sid for sid, v in _image_vectors.items()
               if now - v["ts"] > max_age_seconds]
    for sid in expired:
        del _image_vectors[sid]
    if expired:
        print(f"[SESSION] {len(expired)} vecteur(s) expirés supprimés")


# ── Modèles Pydantic ──

class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    product_id: int | None = None
    history: list[HistoryMessage] = []
    session_id: str | None = None

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


# ── Endpoints ──

@app.get("/")
def root():
    return {"status": "PairIA API en ligne"}

@app.get("/health")
def health():
    return {"status": "ok"}

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

    # Récupère le vecteur image de la session si disponible
    entry = _image_vectors.get(request.session_id)
    image_vector = entry["vector"] if entry else None
    if image_vector:
        print(f"[SESSION] vecteur image récupéré pour {request.session_id}")

    def generate():
        generator = get_response_stream(
            question=request.question,
            product_id=request.product_id,
            history=history,
            image_vector=image_vector,
        )
        for chunk in generator:
            if isinstance(chunk, dict):
                yield f"data: {json.dumps(chunk)}\n\n"
            else:
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/chat/stream-image")
async def chat_stream_image(
    file: UploadFile = File(...),
    question: str    = Form(default=""),
    history: str     = Form(default="[]"),
    session_id: str  = Form(default=""),
):
    history_parsed = json.loads(history)

    print(f"[ENDPOINT] question   : {question!r}")
    print(f"[ENDPOINT] session_id : {session_id!r}")
    print(f"[ENDPOINT] history    : {len(history_parsed)} messages")

    # Sauvegarde temporaire de l'image
    suffix = os.path.splitext(file.filename)[-1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Vectorisation + stockage en session
    try:
        image_vec = clip_model.encode(Image.open(tmp_path)).tolist()
        if session_id:
            _clean_old_vectors()
            _image_vectors[session_id] = {
                "vector": image_vec,
                "ts": time.time()
            }
            print(f"[SESSION] vecteur image stocké pour {session_id}")
    except Exception as e:
        print(f"[SESSION] erreur vectorisation : {e}")

    def generate():
        try:
            generator = get_response_stream(
                question=question,
                history=history_parsed,
                image_path=tmp_path,
            )
            for chunk in generator:
                if isinstance(chunk, dict):
                    # Injecte session_id dans le products_final
                    if chunk.get("type") == "products_final":
                        chunk["session_id"] = session_id
                    yield f"data: {json.dumps(chunk)}\n\n"
                else:
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        finally:
            os.unlink(tmp_path)
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/search-image")
async def search_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = rechercher_produits_similaires(image_bytes)
    return {
        "message": "Voici les produits qui ressemblent à votre photo :",
        "products": result.get("products", []),
        "action": "show_products"
    }

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    # ✅ Sauvegarde du fichier webm original
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_webm:
        shutil.copyfileobj(file.file, tmp_webm)
        webm_path = tmp_webm.name

    # ✅ Conversion webm → wav via ffmpeg
    # Whisper est plus fiable avec du WAV qu'avec du WebM
    wav_path = webm_path.replace(".webm", ".wav")

    try:
        import subprocess
        subprocess.run(
            [
                "ffmpeg", "-y",           # -y : écrase sans demander
                "-i", webm_path,          # fichier source webm
                "-ar", "16000",           # 16kHz — fréquence optimale pour Whisper
                "-ac", "1",               # mono — Whisper n'a pas besoin de stéréo
                "-c:a", "pcm_s16le",      # format WAV non compressé
                wav_path
            ],
            check=True,
            capture_output=True
        )
        print(f"[WHISPER] WAV créé : {os.path.getsize(wav_path)} octets")
    except subprocess.CalledProcessError as e:
        print(f"[WHISPER] Erreur ffmpeg : {e.stderr.decode()}")
        # Fallback : utilise le webm directement si ffmpeg échoue
        wav_path = webm_path

    try:
        result = whisper_model.transcribe(
            wav_path,                          # ✅ WAV au lieu de WebM
            language="fr",
            fp16=False,
            condition_on_previous_text=False,
            temperature=0,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
        )
        text = result["text"].strip()
        print(f"[WHISPER] transcrit : {text!r}")

        if len(text) < 2:
            return {"text": "", "success": False, "error": "Aucune parole détectée"}

        return {"text": text, "success": True}

    except Exception as e:
        print(f"[WHISPER] ERREUR : {e}")
        return {"text": "", "success": False, "error": str(e)}

    finally:
        # Supprime les deux fichiers temporaires
        for path in [webm_path, wav_path]:
            try:
                os.unlink(path)
            except OSError:
                pass