# ia/admin_main.py
# Chatbot ADMIN — utilise le function calling natif d'Ollama

import os
import json
import re
import httpx
import ollama
import subprocess

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

OLLAMA_HOST        = os.environ.get("OLLAMA_HOST",        "http://localhost:11434")
OLLAMA_MODEL       = os.environ.get("ADMIN_OLLAMA_MODEL", "llama3.1")
PHP_ACTIONS_URL    = os.environ.get("ADMIN_ACTIONS_URL",  "http://localhost/admin/includes/admin_actions.php")
ADMIN_ACTION_TOKEN = os.environ.get("ADMIN_ACTION_TOKEN", "")

ollama_client = ollama.Client(host=OLLAMA_HOST)

app = FastAPI(title="PairIA Admin Chatbot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

TOOLS = [
    {"type":"function","function":{"name":"lister_commandes","description":"Lister les commandes","parameters":{"type":"object","properties":{"statut":{"type":"string"},"limit":{"type":"integer"},"depuis":{"type":"string"}}}}},
    {"type":"function","function":{"name":"detail_commande","description":"Détail d'une commande","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"}},"required":["id_commande"]}}},
    {"type":"function","function":{"name":"modifier_statut_commande","description":"Modifier le statut d'une commande","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"},"nouveau_statut":{"type":"string"}},"required":["id_commande","nouveau_statut"]}}},
    {"type":"function","function":{"name":"lister_articles","description":"Lister les articles","parameters":{"type":"object","properties":{"categorie":{"type":"string"}}}}},
    {"type":"function","function":{"name":"modifier_prix","description":"Modifier le prix d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_prix":{"type":"number"}},"required":["id_shoes","nouveau_prix"]}}},
    {"type":"function","function":{"name":"modifier_stock","description":"Modifier le stock d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_stock":{"type":"integer"}},"required":["id_shoes","nouveau_stock"]}}},
    {"type":"function","function":{"name":"rechercher_article","description":"Rechercher un article","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"rechercher_client","description":"Rechercher un client","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"commandes_client","description":"Commandes d'un client","parameters":{"type":"object","properties":{"id_client":{"type":"integer"}},"required":["id_client"]}}},
    {"type":"function","function":{"name":"lister_commentaires","description":"Lister les commentaires","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"supprimer_commentaire","description":"Supprimer un commentaire","parameters":{"type":"object","properties":{"id_commentaire":{"type":"integer"}},"required":["id_commentaire"]}}},
    {"type":"function","function":{"name":"stats_globales","description":"Statistiques globales de la boutique","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"top_articles","description":"Top articles les plus vendus","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"ca_par_mois","description":"CA par mois sur 12 mois","parameters":{"type":"object","properties":{}}}},
]

SYSTEM_PROMPT = """Tu es l'assistant IA de l'administrateur de PairIA, une boutique en ligne de chaussures.
Tu aides l'admin à gérer la boutique : commandes, catalogue, clients, commentaires, statistiques.

RÈGLES :
- Réponds TOUJOURS en français, de manière concise et professionnelle.
- N'invente JAMAIS de données. Utilise TOUJOURS les outils pour obtenir des données réelles.
- Agis directement sans demander confirmation, sauf pour les suppressions.
- Si l'admin demande de modifier plusieurs éléments, appelle les outils nécessaires en séquence.
- Texte brut, sans markdown excessif.""".strip()

class Message(BaseModel):
    role: str
    content: str

class AdminChatRequest(BaseModel):
    question: str
    history: List[Message] = []
    admin_id: Optional[int] = None

class ReindexRequest(BaseModel):
    article_id: Optional[int] = None

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

def run_reindex(article_id: int = None):
    api_url = os.environ.get("CLIENT_API_URL", "http://api:8000")
    token   = os.environ.get("ADMIN_ACTION_TOKEN", "")
    try:
        httpx.post(f"{api_url}/reindex", json={"article_id": article_id},
                   headers={"X-Admin-Token": token}, timeout=5.0)
        print(f"[REINDEX] Demande envoyée (article_id={article_id}).")
    except Exception as e:
        print(f"[REINDEX] Erreur : {e}")

@app.post("/admin/reindex")
async def reindex(request: ReindexRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_reindex, request.article_id)
    return {"status": "started", "article_id": request.article_id}

@app.post("/admin/chat/stream")
async def admin_chat_stream(request: AdminChatRequest):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in request.history[-20:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": request.question})

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

            max_iterations = 10
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                response = ollama_client.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    stream=False,
                    options={"temperature": 0.1, "num_predict": 2048},
                )

                msg = response["message"]

                if not msg.get("tool_calls"):
                    content = msg.get("content", "")
                    for char in content:
                        yield f"data: {json.dumps({'chunk': char})}\n\n"
                    break

                tool_calls = msg["tool_calls"]

                for tool_call in tool_calls:
                    fn_name = tool_call["function"]["name"]
                    fn_args = tool_call["function"].get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except Exception:
                            fn_args = {}

                    yield f"data: {json.dumps({'type': 'action_start', 'action': fn_name})}\n\n"

                    result    = await call_php_action(fn_name, fn_args)
                    formatted = format_result_for_llm(fn_name, result)

                    yield f"data: {json.dumps({'type': 'action_result', 'action': fn_name, 'result': result})}\n\n"

                    messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})
                    messages.append({"role": "tool", "content": formatted, "name": fn_name})

        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'Erreur : {str(e)}'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/admin/health")
def health():
    return {"status": "ok", "service": "admin-chatbot"}