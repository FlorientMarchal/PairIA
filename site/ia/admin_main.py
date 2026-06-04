# ia/admin_main.py
# Chatbot ADMIN + endpoint de re-vectorisation

import os
import json
import re
import httpx
import ollama
import asyncio
import subprocess

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_HOST        = os.environ.get("OLLAMA_HOST",        "http://localhost:11434")
OLLAMA_MODEL       = os.environ.get("ADMIN_OLLAMA_MODEL", "llama3.1")
PHP_ACTIONS_URL    = os.environ.get("ADMIN_ACTIONS_URL",  "http://localhost/admin/includes/admin_actions.php")
ADMIN_ACTION_TOKEN = os.environ.get("ADMIN_ACTION_TOKEN", "")

ollama_client = ollama.Client(host=OLLAMA_HOST)

app = FastAPI(title="PairIA Admin Chatbot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prompt système ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu es l'assistant IA de l'administrateur de PairIA, une boutique en ligne de chaussures.
Tu aides l'admin à gérer la boutique : commandes, catalogue, clients, commentaires, statistiques.

RÈGLES STRICTES :
- Réponds TOUJOURS en français, de manière concise et professionnelle.
- N'INVENTE JAMAIS de données. Tu dois appeler une fonction pour obtenir des données réelles.
- Si tu as besoin de données, appelle la fonction IMMÉDIATEMENT sans rien écrire d'autre avant le tag <ACTION>.
- Avant toute MODIFICATION (statut, prix, stock, suppression), explique ce que tu vas faire et demande confirmation.
- Texte brut uniquement. Tu peux utiliser des tirets pour les listes.

POUR RÉCUPÉRER DES DONNÉES : réponds UNIQUEMENT avec le bloc ACTION, sans texte avant ni après :
<ACTION>{"action": "nom_action", "params": {...}}</ACTION>

POUR RÉPONDRE sans données : écris ta réponse directement, sans bloc ACTION.

Actions disponibles :
- lister_commandes         params: {"statut": "en_attente"|"payée"|"expédiée"|"livrée"|"annulée" (optionnel), "limit": N}
- detail_commande          params: {"id_commande": N}
- modifier_statut_commande params: {"id_commande": N, "nouveau_statut": "..."}
- lister_articles          params: {"categorie": "..." (optionnel)}
- modifier_prix            params: {"id_shoes": N, "nouveau_prix": X.XX}
- modifier_stock           params: {"id_shoes": N, "nouveau_stock": N}
- rechercher_article       params: {"query": "..."}
- rechercher_client        params: {"query": "..."}
- commandes_client         params: {"id_client": N}
- lister_commentaires      params: {"limit": N}
- supprimer_commentaire    params: {"id_commentaire": N}
- stats_globales           params: {}
- top_articles             params: {"limit": N}
- ca_par_mois              params: {}
""".strip()

# ── Modèles Pydantic ──────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    content: str

class AdminChatRequest(BaseModel):
    question: str
    history: List[Message] = []
    admin_id: Optional[int] = None

class ReindexRequest(BaseModel):
    article_id: Optional[int] = None  # None = réindexation complète

# ── Appel PHP ─────────────────────────────────────────────────────────────────
async def call_php_action(action: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                PHP_ACTIONS_URL,
                json={"action": action, "params": params},
                headers={"X-Admin-Token": ADMIN_ACTION_TOKEN},
            )
            return resp.json()
    except Exception as e:
        return {"success": False, "message": f"Erreur appel PHP : {e}", "data": None}

def format_result_for_llm(action: str, result: dict) -> str:
    if not result.get("success"):
        return f"ERREUR : {result.get('message', 'inconnue')}"
    data = result.get("data")
    msg  = result.get("message", "")
    if data is None:
        return msg
    if isinstance(data, list):
        if not data:
            return "Aucun résultat."
        lines = [f"{msg} ({len(data)} éléments) :"]
        for item in data[:30]:
            lines.append("- " + " | ".join(f"{k}: {v}" for k, v in item.items()))
        return "\n".join(lines)
    if isinstance(data, dict):
        lines = [msg]
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k} ({len(v)}) :")
                for item in v[:15]:
                    if isinstance(item, dict):
                        lines.append("  - " + " | ".join(f"{ik}: {iv}" for ik, iv in item.items()))
                    else:
                        lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    return f"{msg}\n{json.dumps(data, ensure_ascii=False)[:800]}"

def extract_action(text: str):
    match = re.search(r"<ACTION>(.*?)</ACTION>", text, re.DOTALL)
    if not match:
        return None
    pre  = text[:match.start()].strip()
    post = text[match.end():].strip()
    try:
        action_dict = json.loads(match.group(1).strip())
        return pre, action_dict, post
    except json.JSONDecodeError:
        return None

def llm_call(messages: list) -> str:
    response = ollama_client.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        stream=False,
        options={"temperature": 0.2, "num_predict": 1024},
    )
    return response["message"]["content"]

# ── Re-vectorisation ──────────────────────────────────────────────────────────
def run_reindex(article_id: int = None):
    """Demande au conteneur api de re-vectoriser."""
    api_url = os.environ.get("CLIENT_API_URL", "http://api:8000")
    token   = os.environ.get("ADMIN_ACTION_TOKEN", "")
    try:
        httpx.post(
            f"{api_url}/reindex",
            json={"article_id": article_id},
            headers={"X-Admin-Token": token},
            timeout=5.0
        )
        print(f"[REINDEX] Demande envoyée au conteneur api (article_id={article_id}).")
    except Exception as e:
        print(f"[REINDEX] Erreur : {e}")

@app.post("/admin/reindex")
async def reindex(request: ReindexRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_reindex, request.article_id)
    return {"status": "started", "article_id": request.article_id}

# ── Endpoint chat ─────────────────────────────────────────────────────────────
@app.post("/admin/chat/stream")
async def admin_chat_stream(request: AdminChatRequest):

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in request.history[-20:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": request.question})

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

            first_response = llm_call(messages)
            parsed = extract_action(first_response)

            if parsed is None:
                for char in first_response:
                    yield f"data: {json.dumps({'chunk': char})}\n\n"
                yield "data: [DONE]\n\n"
                return

            pre_text, action_dict, _ = parsed
            action_name   = action_dict.get("action", "")
            action_params = action_dict.get("params", {})

            if pre_text:
                for char in pre_text:
                    yield f"data: {json.dumps({'chunk': char})}\n\n"

            yield f"data: {json.dumps({'type': 'action_start', 'action': action_name})}\n\n"

            result    = await call_php_action(action_name, action_params)
            formatted = format_result_for_llm(action_name, result)

            yield f"data: {json.dumps({'type': 'action_result', 'action': action_name, 'result': result})}\n\n"

            messages_with_data = messages + [
                {"role": "assistant", "content": pre_text or ""},
                {"role": "user",      "content": f"Voici les données réelles de la base :\n{formatted}\n\nFormule une réponse claire et concise pour l'admin."},
            ]
            final_response = llm_call(messages_with_data)

            for char in final_response:
                yield f"data: {json.dumps({'chunk': char})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'Erreur : {str(e)}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/admin/health")
def health():
    return {"status": "ok", "service": "admin-chatbot"}
