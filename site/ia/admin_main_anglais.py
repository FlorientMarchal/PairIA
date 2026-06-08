# ia/admin_main.py
import os
import json
import uuid
import httpx
import ollama

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

OLLAMA_HOST        = os.environ.get("OLLAMA_HOST",        "http://localhost:11434")
OLLAMA_MODEL       = os.environ.get("ADMIN_OLLAMA_MODEL", "qwen2.5:14b")
PHP_ACTIONS_URL    = os.environ.get("ADMIN_ACTIONS_URL",  "http://localhost/admin/includes/admin_actions.php")
ADMIN_ACTION_TOKEN = os.environ.get("ADMIN_ACTION_TOKEN", "")

ollama_client = ollama.Client(host=OLLAMA_HOST)

app = FastAPI(title="PairIA Admin Chatbot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_session_messages: dict = {}

# Messages contextuels affichés dans les badges pendant les actions
ACTION_STATUS_TEXTS = {
    "lister_commandes":               "Je recherche les commandes…",
    "detail_commande":                "Je récupère le détail de la commande…",
    "modifier_statut_commande":       "Je mets à jour le statut…",
    "modifier_statut_batch":          "Je mets à jour les statuts en lot…",
    "lister_articles":                "Je charge le catalogue…",
    "lister_articles_stock_faible":   "Je vérifie les stocks…",
    "rechercher_article":             "Je recherche l'article…",
    "modifier_prix":                  "Je modifie le prix…",
    "modifier_stock":                 "Je modifie le stock…",
    "modifier_prix_batch":            "Je mets à jour les prix…",
    "modifier_article":               "Je modifie l'article…",
    "ajouter_article":                "J'ajoute l'article au catalogue…",
    "supprimer_article":              "Je supprime l'article…",
    "lister_clients":                 "Je charge les clients…",
    "rechercher_client":              "Je recherche le client…",
    "commandes_client":               "Je récupère les commandes du client…",
    "clients_top":                    "Je calcule le top clients…",
    "lister_commentaires":            "Je charge les commentaires…",
    "supprimer_commentaire":          "Je supprime le commentaire…",
    "supprimer_commentaires_article": "Je supprime les commentaires…",
    "stats_globales":                 "Je calcule les statistiques…",
    "stats_par_categorie":            "Je calcule les stats par catégorie…",
    "top_articles":                   "Je calcule le top ventes…",
    "ca_par_mois":                    "Je calcule le chiffre d'affaires…",
    "arrondir_prix": "J'arrondis les prix…",
}

TOOLS = [
    {"type":"function","function":{"name":"lister_commandes","description":"List orders. Use statut filter if specified.","parameters":{"type":"object","properties":{"statut":{"type":"string","description":"en_attente, payée, expédiée, livrée, annulée"},"limit":{"type":"integer"},"depuis":{"type":"string"}}}}},
    {"type":"function","function":{"name":"detail_commande","description":"Get full order details with lines","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"}},"required":["id_commande"]}}},
    {"type":"function","function":{"name":"modifier_statut_commande","description":"Update status of ONE order","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"},"nouveau_statut":{"type":"string"}},"required":["id_commande","nouveau_statut"]}}},
    {"type":"function","function":{"name":"modifier_statut_batch","description":"Update status of MULTIPLE orders at once","parameters":{"type":"object","properties":{"ids":{"type":"array","items":{"type":"integer"},"description":"List of order IDs"},"nouveau_statut":{"type":"string"}},"required":["ids","nouveau_statut"]}}},
    {"type":"function","function":{"name":"lister_articles","description":"List catalog articles","parameters":{"type":"object","properties":{"categorie":{"type":"string"}}}}},
    {"type":"function","function":{"name":"lister_articles_stock_faible","description":"List articles with low stock","parameters":{"type":"object","properties":{"seuil":{"type":"integer","description":"Stock threshold, default 20"}}}}},
    {"type":"function","function":{"name":"rechercher_article","description":"Search article by name, brand or category","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"modifier_prix","description":"Update price of ONE article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_prix":{"type":"number"}},"required":["id_shoes","nouveau_prix"]}}},
    {"type":"function","function":{"name":"modifier_stock","description":"Update stock of ONE article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_stock":{"type":"integer"}},"required":["id_shoes","nouveau_stock"]}}},
    {"type":"function","function":{"name":"modifier_prix_batch","description":"Update prices for a group of articles (by category, brand, genre or all)","parameters":{"type":"object","properties":{"filtre_type":{"type":"string","description":"categorie, marque, genre, or tous"},"filtre_valeur":{"type":"string","description":"Filter value (ignored if tous)"},"type_modif":{"type":"string","description":"pourcentage, fixe, or nouveau_prix"},"valeur":{"type":"number","description":"Value: percentage (+10 = +10%), fixed amount (+5 = +5€), or new price"}},"required":["filtre_type","type_modif","valeur"]}}},
    {"type":"function","function":{"name":"modifier_article","description":"Update one or more fields of an article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nom":{"type":"string"},"categorie":{"type":"string"},"marque":{"type":"string"},"genre":{"type":"string"},"Prix":{"type":"number"},"description":{"type":"string"},"caracteristiques":{"type":"string"},"materiaux":{"type":"string"},"usage":{"type":"string"},"mots_cles":{"type":"string"},"url_image":{"type":"string"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"ajouter_article","description":"Add a new article to the catalog","parameters":{"type":"object","properties":{"nom":{"type":"string"},"categorie":{"type":"string"},"marque":{"type":"string"},"genre":{"type":"string","description":"Mixte, Homme, or Femme"},"prix":{"type":"number"},"description":{"type":"string"},"caracteristiques":{"type":"string"},"materiaux":{"type":"string"},"usage":{"type":"string"},"mots_cles":{"type":"string"},"url_image":{"type":"string"},"variants":{"type":"array","items":{"type":"object","properties":{"taille":{"type":"integer"},"couleur":{"type":"string"},"stock":{"type":"integer"}}}}},"required":["nom","categorie","marque","prix"]}}},
    {"type":"function","function":{"name":"supprimer_article","description":"Delete an article from the catalog","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"lister_clients","description":"List all clients sorted by revenue","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"rechercher_client","description":"Search client by name or email","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"commandes_client","description":"Get orders for a specific client","parameters":{"type":"object","properties":{"id_client":{"type":"integer"}},"required":["id_client"]}}},
    {"type":"function","function":{"name":"clients_top","description":"Top clients by revenue","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"lister_commentaires","description":"List recent comments","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"supprimer_commentaire","description":"Delete a single comment","parameters":{"type":"object","properties":{"id_commentaire":{"type":"integer"}},"required":["id_commentaire"]}}},
    {"type":"function","function":{"name":"supprimer_commentaires_article","description":"Delete ALL comments for an article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"stats_globales","description":"Global store statistics","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"stats_par_categorie","description":"Sales and revenue by category","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"top_articles","description":"Top selling articles","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"ca_par_mois","description":"Monthly revenue for last 12 months","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"arrondir_prix","description":"Round article prices (nearest euro, ceiling, floor, .50 or .99)","parameters":{"type":"object","properties":{"methode":{"type":"string","description":"nearest (round), up (ceiling), down (floor), half (x.50), nine (x.99)"},"filtre_type":{"type":"string","description":"categorie, marque, genre, or tous"},"filtre_valeur":{"type":"string","description":"Filter value"}},"required":["methode"]}}},
]

SYSTEM_PROMPT = """You are the AI assistant for the administrator of PairIA, an online shoe store.
You help manage the store: orders, catalog, clients, comments, statistics.

ABSOLUTE RULES:
- NEVER invent data, IDs, names or statuses. NEVER.
- ALWAYS use tools to get real data before answering.
- Act directly without asking for confirmation, EXCEPT for deletions and batch price updates.
- Always respond in French.
- NEVER show JSON or technical parameters !


AVAILABLE CATEGORIES (use EXACTLY one of these):
Baskets lifestyle, Baskets sport, Bottines, Danse, Espadrilles, Imperméables, Indoor, Marche, Minimalistes, Mocassins, Montantes légères, Randonnée, Running, Sabots, Sandales, Sécurité, Slip-on, Talons, Training, Vegan

DELETION RULES:
- When admin says "delete/remove [article name]", ALWAYS call rechercher_article first to get the real ID.
- Show the result, ask ONE confirmation, then call supprimer_article with the real ID.
- NEVER call supprimer_article with an invented ID.
- For modifier_statut_batch with many orders: summarize what will be done and ask confirmation first.

ORDER STATUS: en_attente → payée → expédiée → livrée. NEVER downgrade.
For multiple orders use modifier_statut_batch.

PRICE UPDATES — ALWAYS ask confirmation first:
- Before any modifier_prix_batch, tell admin exactly what will happen:
  "Je vais [augmenter/baisser] tous les prix [filtre] de [valeur]. Confirmer ?"
- Wait for confirmation, then execute.
- "reduce all prices by 5€" → modifier_prix_batch(filtre_type=tous, type_modif=fixe, valeur=-5), but confirm first
- "increase all prices by 5€" → modifier_prix_batch(filtre_type=tous, type_modif=fixe, valeur=5), but vonfirm first
- For reductions, valeur MUST be negative (e.g. -0.41, not 0.41)
- "reduce price of article X by Y€" → ALWAYS call rechercher_article first to get the REAL current price, then call modifier_prix with nouveau_prix = real_current_price - Y
- NEVER calculate nouveau_prix without first fetching the real current price via rechercher_article
- "set price of article X to Y€" → modifier_prix with nouveau_prix = Y directly

ARTICLE CREATION:
- Ask for: nom, catégorie (from list above), marque, genre, prix, description, caractéristiques, matériaux, usage, mots-clés, variants (couleurs+pointures+stock)
- ALWAYS include url_image if an image was provided in session context
- Call ajouter_article once you have nom, categorie, marque, prix and variants""".strip()

class Message(BaseModel):
    role: str
    content: str

class AdminChatRequest(BaseModel):
    question: str
    history: List[Message] = []
    admin_id: Optional[int] = None
    session_id: Optional[str] = None
    image_url: Optional[str] = None

class ReindexRequest(BaseModel):
    article_id: Optional[int] = None

async def call_php_action(action: str, params: dict) -> dict:
    print(f"[PHP] action={action} | params={params}")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                PHP_ACTIONS_URL,
                json={"action": action, "params": params},
                headers={"X-Admin-Token": ADMIN_ACTION_TOKEN},
            )
            print(f"[PHP] status={resp.status_code} | body={resp.text[:200]!r}")
            # Strip les warnings PHP avant le JSON
            text = resp.text.strip()
            if '{' in text:
                text = text[text.index('{'):]
            return json.loads(text)
    except Exception as e:
        return {"success": False, "message": f"Erreur appel PHP : {e}", "data": None}

def format_result_for_llm(action: str, result: dict) -> str:
    if not result.get("success"):
        return f"ERROR: {result.get('message', 'unknown')}"
    data = result.get("data")
    msg  = result.get("message", "")
    if data is None:
        return msg
    if isinstance(data, list):
        if not data:
            return "No results."
        lines = [f"{msg} ({len(data)} items):"]
        for item in data[:30]:
            lines.append("- " + " | ".join(f"{k}: {v}" for k, v in item.items()))
        return "\n".join(lines)
    if isinstance(data, dict):
        lines = [msg]
        for k, v in data.items():
            if isinstance(v, list):
                lines.append(f"{k} ({len(v)}):")
                for item in v[:15]:
                    if isinstance(item, dict):
                        lines.append("  - " + " | ".join(f"{ik}: {iv}" for ik, iv in item.items()))
                    else:
                        lines.append(f"  - {item}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)
    return f"{msg}\n{json.dumps(data, ensure_ascii=False)[:800]}"

def translate_to_english(text: str) -> str:
    text = text.strip()
    if len(text.split()) <= 3:
        return text
    try:
        resp = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content":
                f"Translate this French e-commerce admin request to English. "
                f"'commandes' means 'orders' (not commands). "
                f"Reply ONLY with the translation, nothing else:\n{text}"}],
            stream=False,
            options={"temperature": 0, "num_predict": 200},
        )
        return resp["message"]["content"].strip()
    except:
        return text

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
    session_id = request.session_id or str(uuid.uuid4())

    if session_id not in _session_messages:
        _session_messages[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    messages = _session_messages[session_id]
    print(f"[ADMIN] session={session_id[:8]} | nb_messages={len(messages)}")

    # Injecte l'image dans le contexte si présente
    if request.image_url:
        if not any("image_url" in str(m.get("content", "")) for m in messages):
            messages.insert(1, {
                "role": "system",
                "content": f"[CONTEXT] Admin uploaded an image. URL: {request.image_url} — use as url_image when calling ajouter_article."
            })

    # Traduit la question FR → EN
    question_en = translate_to_english(request.question)
    if request.image_url:
        question_en = f"[Image: {request.image_url}] {question_en}"
    print(f"[ADMIN] session={session_id[:8]} | question_en: {question_en!r}")

    messages.append({"role": "user", "content": question_en})

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

            max_iterations = 15
            iteration = 0
            had_tool_calls = False

            while iteration < max_iterations:
                iteration += 1

                response = ollama_client.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=TOOLS,
                    stream=False,
                    options={"temperature": 0.1, "num_predict": 4096},
                )

                msg = response["message"]
                print(f"[ADMIN] iter={iteration} | tool_calls={bool(msg.get('tool_calls'))} | content={msg.get('content','')[:80]!r}")

                if not msg.get("tool_calls"):
                    content = msg.get("content", "").strip()
                    # Si pas de contenu après des tool_calls, génère une confirmation
                    if not content and had_tool_calls:
                        content = "C'est fait ✓"
                    messages.append({"role": "assistant", "content": content})
                    for char in content:
                        yield f"data: {json.dumps({'chunk': char})}\n\n"
                    break

                had_tool_calls = True
                tool_calls = msg["tool_calls"]
                messages.append({"role": "assistant", "content": "", "tool_calls": tool_calls})

                for tool_call in tool_calls:
                    fn_name = tool_call["function"]["name"]
                    fn_args = tool_call["function"].get("arguments", {})
                    if isinstance(fn_args, str):
                        try:
                            fn_args = json.loads(fn_args)
                        except:
                            fn_args = {}

                    # Cast des types
                    int_params   = ["id_commande","id_shoes","id_client","id_commentaire","limit","nouveau_stock","seuil"]
                    float_params = ["nouveau_prix","valeur","prix"]
                    for k, v in fn_args.items():
                        if k in int_params:   fn_args[k] = int(v)
                        if k in float_params: fn_args[k] = float(v)

                    # Status text contextuel pour la bulle
                    status_text = ACTION_STATUS_TEXTS.get(fn_name, "Je traite la demande…")
                    yield f"data: {json.dumps({'type': 'action_start', 'action': fn_name, 'status_text': status_text})}\n\n"

                    result    = await call_php_action(fn_name, fn_args)
                    formatted = format_result_for_llm(fn_name, result)
                    yield f"data: {json.dumps({'type': 'action_result', 'action': fn_name, 'result': result})}\n\n"

                    messages.append({"role": "tool", "content": formatted, "name": fn_name})

                    # Reindex si article modifié
                    if fn_name in ['ajouter_article', 'modifier_article', 'supprimer_article']:
                        article_id = result.get('data', {}).get('id_shoes') if result.get('data') else None
                        run_reindex(article_id)

            # Nettoyage sessions
            if len(_session_messages) > 100:
                oldest = list(_session_messages.keys())[0]
                del _session_messages[oldest]

            # Ignore les tool calls écrits en texte par le LLM
            if content.startswith("CallCheck") or '"name"' in content[:50]:
                content = ""
                had_tool_calls = True  # Force le fallback "C'est fait ✓"

        except Exception as e:
            yield f"data: {json.dumps({'chunk': f'Erreur : {str(e)}'})}\n\n"
        except Exception:
            pass
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/admin/health")
def health():
    return {"status": "ok", "service": "admin-chatbot"}