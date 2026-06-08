# ia/main.py
import sys
import os
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
import ollama as _ollama_lib
_ollama_lib.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))

import json
import time
import tempfile
import whisper
import shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decimal import Decimal

from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks, Request
from typing import Optional
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rag import get_response_stream
from image_search import model as clip_model, rechercher_produits_similaires
from PIL import Image
from typing import Optional

app = FastAPI(title="API Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Chargement du modèle Whisper...")
whisper_model = whisper.load_model("small")
print("Whisper prêt ✓")

_VEC_PREFIX = "pairia_vec_"
_VEC_TTL    = 3600

def _vec_path(session_id: str) -> str:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return os.path.join(tempfile.gettempdir(), f"{_VEC_PREFIX}{safe}.json")

def _save_vector(session_id: str, vector: list) -> None:
    try:
        data = {"vector": vector, "ts": time.time()}
        with open(_vec_path(session_id), "w") as f:
            json.dump(data, f)
        print(f"[SESSION] vecteur image stocké pour {session_id}")
    except Exception as e:
        print(f"[SESSION] erreur sauvegarde vecteur : {e}")

def _load_vector(session_id: str) -> list | None:
    if not session_id:
        return None
    path = _vec_path(session_id)
    try:
        with open(path) as f:
            data = json.load(f)
        if time.time() - data["ts"] > _VEC_TTL:
            os.unlink(path)
            return None
        print(f"[SESSION] vecteur image récupéré pour {session_id}")
        return data["vector"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None

def _clean_old_vectors() -> None:
    tmp = tempfile.gettempdir()
    now = time.time()
    try:
        for fname in os.listdir(tmp):
            if not fname.startswith(_VEC_PREFIX):
                continue
            fpath = os.path.join(tmp, fname)
            try:
                with open(fpath) as f:
                    data = json.load(f)
                if now - data.get("ts", 0) > _VEC_TTL:
                    os.unlink(fpath)
                    print(f"[SESSION] vecteur expiré supprimé : {fname}")
            except Exception:
                pass
    except Exception:
        pass


class HistoryMessage(BaseModel):
    role: str
    content: str
    products: list[dict] = []
    internal: bool = False

class ChatRequest(BaseModel):
    question: str
    product_id: int | None = None
    history: list[HistoryMessage] = []
    session_id: str | None = None
    langue_session: str = "fr"

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

class TranslateUIRequest(BaseModel):
    texts: dict[str, str]
    langue: str


@app.get("/")
def root():
    return {"status": "PairIA API en ligne"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/translate-ui")
def translate_ui(request: TranslateUIRequest):
    from language_utils import nom_langue
    import ollama

    if request.langue == "fr":
        return {"translations": request.texts}

    keys     = list(request.texts.keys())
    values   = list(request.texts.values())
    combined = " |SEP| ".join(values)
    nom_lang = nom_langue(request.langue)

    prompt = (
        f"Translate each French label to {nom_lang}. "
        f"Labels are separated by |SEP|. "
        f"Reply with ONLY the translated labels in the same order, separated by |SEP|. "
        f"Do not write anything before or after. Do not number them. "
        f"Input: {combined}\n"
        f"Output:"
    )

    try:
        response = ollama.chat(
            model="llama3.1",
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": 400, "temperature": 0.1},
        )
        raw = response["message"]["content"].strip()

        if "|SEP|" in raw:
            lines = raw.splitlines()
            for line in lines:
                if "|SEP|" in line:
                    raw = line.strip()
                    break

        parts = [p.strip() for p in raw.split("|SEP|")]

        if len(parts) == len(keys):
            translations = dict(zip(keys, parts))
            print(f"[TRANSLATE-UI] {nom_lang} : {len(translations)} labels traduits")
        else:
            print(f"[TRANSLATE-UI] segments inattendus ({len(parts)} vs {len(keys)}) → fallback FR")
            translations = request.texts

    except Exception as e:
        print(f"[TRANSLATE-UI] erreur : {e} → fallback FR")
        translations = request.texts

    return {"translations": translations}

@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    history = [
        {"role": m.role, "content": m.content, "products": m.products}
        for m in request.history
        if not m.internal
    ]

    image_vector = _load_vector(request.session_id) if request.session_id else None

    def generate():
        try:
            generator = get_response_stream(
                question=request.question,
                product_id=request.product_id,
                history=history,
                image_vector=image_vector,
                langue_session=request.langue_session,
            )
            for chunk in generator:
                if isinstance(chunk, dict):
                    yield f"data: {json.dumps(chunk, default=lambda o: float(o) if isinstance(o, Decimal) else str(o))}\n\n"
                else:
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"[STREAM] erreur : {e}")
            yield f"data: {json.dumps({'chunk': 'Erreur temporaire.'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/chat/stream-image")
async def chat_stream_image(
    file: UploadFile = File(...),
    question: str    = Form(default=""),
    history: str     = Form(default="[]"),
    session_id: str  = Form(default=""),
    langue_session: str = Form(default="fr"),
):
    history_parsed = json.loads(history)

    print(f"[ENDPOINT] question   : {question!r}")
    print(f"[ENDPOINT] session_id : {session_id!r}")
    print(f"[ENDPOINT] history    : {len(history_parsed)} messages")

    suffix = os.path.splitext(file.filename)[-1] or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        image_vec = clip_model.encode(Image.open(tmp_path)).tolist()
        if session_id:
            _clean_old_vectors()
            _save_vector(session_id, image_vec)
    except Exception as e:
        print(f"[SESSION] erreur vectorisation : {e}")

    def generate():
        try:
            generator = get_response_stream(
                question=question,
                history=history_parsed,
                image_path=tmp_path,
                langue_session=langue_session,
            )
            for chunk in generator:
                if isinstance(chunk, dict):
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
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_webm:
        shutil.copyfileobj(file.file, tmp_webm)
        webm_path = tmp_webm.name

    wav_path = webm_path.replace(".webm", ".wav")

    try:
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", "-af", "loudnorm", wav_path],
            check=True, capture_output=True
        )
        print(f"[WHISPER] WAV créé : {os.path.getsize(wav_path)} octets")
    except subprocess.CalledProcessError as e:
        print(f"[WHISPER] Erreur ffmpeg : {e.stderr.decode()}")
        wav_path = webm_path

    try:
        result = whisper_model.transcribe(
            wav_path, language=None, fp16=False, temperature=0,
            condition_on_previous_text=False, no_speech_threshold=0.6,
            compression_ratio_threshold=1.4, logprob_threshold=-1.0,
        )
        text = result["text"].strip()
        detected_lang = result.get("language", "unknown")
        print(f"[WHISPER] langue détectée : {detected_lang}")
        print(f"[WHISPER] transcrit : {text!r}")
        if len(text) < 2:
            return {"text": "", "success": False, "error": "Aucune parole détectée"}
        return {"text": text,"language": detected_lang, "success": True}
    except Exception as e:
        print(f"[WHISPER] ERREUR : {e}")
        return {"text": "", "success": False, "error": str(e)}
    finally:
        for path in [webm_path, wav_path]:
            try:
                os.unlink(path)
            except OSError:
                pass


class ReindexRequest(BaseModel):
    article_id: Optional[int] = None

@app.post("/reindex")
async def reindex(request_body: ReindexRequest, background_tasks: BackgroundTasks, request: Request):
    token = request.headers.get("X-Admin-Token", "")
    if token != os.environ.get("ADMIN_ACTION_TOKEN", ""):
        return JSONResponse(status_code=403, content={"error": "Non autorisé"})
    background_tasks.add_task(run_reindex_task, request_body.article_id)
    return {"status": "started", "article_id": request_body.article_id}

def run_reindex_task(article_id: int = None):
    import subprocess
    cmd_text = ["python", "/app/embeeding.py"]
    if article_id:
        cmd_text.append(str(article_id))
    cmd_img = ["python", "/app/embeeding_images.py"]
    if article_id:
        cmd_img.append(str(article_id))

    for cmd, name in [(cmd_text, "embeeding.py"), (cmd_img, "embeeding_images.py")]:
        try:
            print(f"[REINDEX] {name} article_id={article_id}...")
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            print(f"[REINDEX] ✓ {name}" if r.returncode == 0 else f"[REINDEX] ✗ {name}: {r.stderr[:300]}")
        except Exception as e:
            print(f"[REINDEX] Exception {name}: {e}")


class DeleteIndexRequest(BaseModel):
    article_id: int

@app.post("/reindex/delete")
async def reindex_delete(request_body: DeleteIndexRequest, request: Request):
    token = request.headers.get("X-Admin-Token", "")
    if token != os.environ.get("ADMIN_ACTION_TOKEN", ""):
        return JSONResponse(status_code=403, content={"error": "Non autorisé"})
    try:
        from qdrant_client.models import PointIdsList
        from database import qdrant
        for collection in ["produits", "produits_image"]:
            qdrant.delete(
                collection_name=collection,
                points_selector=PointIdsList(points=[request_body.article_id])
            )
        print(f"[REINDEX] ✓ Article #{request_body.article_id} supprimé de Qdrant.")
        return {"status": "deleted", "article_id": request_body.article_id}
    except Exception as e:
        print(f"[REINDEX] ✗ Erreur suppression Qdrant : {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ── RAG Admin — recherche sémantique dans le catalogue ────────────────────────

class AdminSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5

@app.post("/admin/search-article")
async def admin_search_article(request_body: AdminSearchRequest, request: Request):
    """Recherche sémantique d'articles via Qdrant — utilisé par le chatbot admin."""
    token = request.headers.get("X-Admin-Token", "")
    if token != os.environ.get("ADMIN_ACTION_TOKEN", ""):
        return JSONResponse(status_code=403, content={"error": "Non autorisé"})

    try:
        import ollama as _ol
        from database import qdrant
        from db_mysql import fetch_all

        ollama_client = _ol.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))

        # Vectorise la query avec nomic-embed-text
        embed = ollama_client.embeddings(model="nomic-embed-text", prompt=request_body.query)
        vector = embed["embedding"]

        # Recherche dans Qdrant collection produits
        results = qdrant.query_points(
            collection_name="produits",
            query=vector,
            limit=request_body.limit,
            score_threshold=0.2,
        ).points

        if not results:
            return {"success": True, "message": "0 résultat(s).", "data": []}

        # Enrichit avec le prix réel depuis MySQL (plus fiable que Qdrant)
        articles = []
        for r in results:
            p = r.payload
            # Récupère le prix MySQL à jour
            rows = fetch_all(f"SELECT Prix, stock_total FROM articles WHERE id_shoes = {int(r.id)}")
            prix = float(rows[0]["Prix"]) if rows else float(p.get("prix", 0))
            stock = int(rows[0]["stock_total"]) if rows else 0
            articles.append({
                "id_shoes":    int(r.id),
                "nom":         p.get("nom", ""),
                "categorie":   p.get("categorie", ""),
                "marque":      p.get("marque", ""),
                "Prix":        prix,
                "stock_total": stock,
                "score":       round(r.score, 3),
            })

        print(f"[ADMIN-RAG] query={request_body.query!r} → {len(articles)} résultat(s)")
        return {"success": True, "message": f"{len(articles)} résultat(s).", "data": articles}

    except Exception as e:
        print(f"[ADMIN-RAG] Erreur : {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})