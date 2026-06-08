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
OLLAMA_MODEL       = os.environ.get("ADMIN_OLLAMA_MODEL", "qwen2.5:7b")
PHP_ACTIONS_URL    = os.environ.get("ADMIN_ACTIONS_URL",  "http://localhost/admin/includes/admin_actions.php")
ADMIN_ACTION_TOKEN = os.environ.get("ADMIN_ACTION_TOKEN", "")

ollama_client = ollama.Client(host=OLLAMA_HOST)

app = FastAPI(title="PairIA Admin Chatbot API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_session_messages: dict = {}

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
    "arrondir_prix":                  "J'arrondis les prix…",
}

TOOLS = [
    {"type":"function","function":{"name":"lister_commandes","description":"Lister les commandes avec filtre optionnel sur le statut","parameters":{"type":"object","properties":{"statut":{"type":"string","description":"en_attente, payée, expédiée, livrée, annulée"},"limit":{"type":"integer"},"depuis":{"type":"string"}}}}},
    {"type":"function","function":{"name":"detail_commande","description":"Obtenir le détail complet d'une commande","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"}},"required":["id_commande"]}}},
    {"type":"function","function":{"name":"modifier_statut_commande","description":"Modifier le statut d'UNE commande","parameters":{"type":"object","properties":{"id_commande":{"type":"integer"},"nouveau_statut":{"type":"string","description":"en_attente, payée, expédiée, livrée, annulée"}},"required":["id_commande","nouveau_statut"]}}},
    {"type":"function","function":{"name":"modifier_statut_batch","description":"Modifier le statut de PLUSIEURS commandes en une fois","parameters":{"type":"object","properties":{"ids":{"type":"array","items":{"type":"integer"},"description":"Liste des IDs de commandes"},"nouveau_statut":{"type":"string"}},"required":["ids","nouveau_statut"]}}},
    {"type":"function","function":{"name":"lister_articles","description":"Lister les articles du catalogue","parameters":{"type":"object","properties":{"categorie":{"type":"string"}}}}},
    {"type":"function","function":{"name":"lister_articles_stock_faible","description":"Lister les articles avec stock faible","parameters":{"type":"object","properties":{"seuil":{"type":"integer","description":"Seuil de stock, défaut 20"}}}}},
    {"type":"function","function":{"name":"rechercher_article","description":"Rechercher un article par nom, marque ou catégorie","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"modifier_prix","description":"Modifier le prix d'UN article. nouveau_prix est le NOUVEAU prix final, pas une différence.","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_prix":{"type":"number","description":"Le nouveau prix final de l'article en euros"}},"required":["id_shoes","nouveau_prix"]}}},
    {"type":"function","function":{"name":"modifier_stock","description":"Modifier le stock d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nouveau_stock":{"type":"integer"}},"required":["id_shoes","nouveau_stock"]}}},
    {"type":"function","function":{"name":"modifier_prix_batch","description":"Modifier les prix d'un groupe d'articles","parameters":{"type":"object","properties":{"filtre_type":{"type":"string","description":"categorie, marque, genre, ou tous"},"filtre_valeur":{"type":"string","description":"Valeur du filtre (ignoré si tous)"},"type_modif":{"type":"string","description":"pourcentage, fixe, ou nouveau_prix"},"valeur":{"type":"number","description":"Valeur: pourcentage (+10 = +10%), montant fixe (+5 = +5€, -5 = -5€), ou nouveau prix"}},"required":["filtre_type","type_modif","valeur"]}}},
    {"type":"function","function":{"name":"modifier_article","description":"Modifier un ou plusieurs champs d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"},"nom":{"type":"string"},"categorie":{"type":"string"},"marque":{"type":"string"},"genre":{"type":"string"},"Prix":{"type":"number"},"description":{"type":"string"},"caracteristiques":{"type":"string"},"materiaux":{"type":"string"},"usage":{"type":"string"},"mots_cles":{"type":"string"},"url_image":{"type":"string"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"ajouter_article","description":"Ajouter un nouvel article au catalogue","parameters":{"type":"object","properties":{"nom":{"type":"string"},"categorie":{"type":"string"},"marque":{"type":"string"},"genre":{"type":"string","description":"Mixte, Homme, ou Femme"},"prix":{"type":"number"},"description":{"type":"string"},"caracteristiques":{"type":"string"},"materiaux":{"type":"string"},"usage":{"type":"string"},"mots_cles":{"type":"string"},"url_image":{"type":"string"},"variants":{"type":"array","items":{"type":"object","properties":{"taille":{"type":"integer"},"couleur":{"type":"string"},"stock":{"type":"integer"}}}}},"required":["nom","categorie","marque","prix"]}}},
    {"type":"function","function":{"name":"supprimer_article","description":"Supprimer un article du catalogue","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"lister_clients","description":"Lister tous les clients triés par CA","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"rechercher_client","description":"Rechercher un client par nom ou email","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}},
    {"type":"function","function":{"name":"commandes_client","description":"Voir les commandes d'un client","parameters":{"type":"object","properties":{"id_client":{"type":"integer"}},"required":["id_client"]}}},
    {"type":"function","function":{"name":"clients_top","description":"Top clients par CA","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"lister_commentaires","description":"Lister les commentaires récents","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"supprimer_commentaire","description":"Supprimer un commentaire","parameters":{"type":"object","properties":{"id_commentaire":{"type":"integer"}},"required":["id_commentaire"]}}},
    {"type":"function","function":{"name":"supprimer_commentaires_article","description":"Supprimer TOUS les commentaires d'un article","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
    {"type":"function","function":{"name":"stats_globales","description":"Statistiques globales de la boutique","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"stats_par_categorie","description":"CA et ventes par catégorie","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"top_articles","description":"Top articles les plus vendus","parameters":{"type":"object","properties":{"limit":{"type":"integer"}}}}},
    {"type":"function","function":{"name":"ca_par_mois","description":"CA par mois sur 12 mois","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"arrondir_prix","description":"Arrondir les prix des articles","parameters":{"type":"object","properties":{"methode":{"type":"string","description":"nearest (arrondi), up (plafond), down (plancher), half (x.50), nine (x.99)"},"filtre_type":{"type":"string","description":"categorie, marque, genre, ou tous"},"filtre_valeur":{"type":"string","description":"Valeur du filtre"}},"required":["methode"]}}},
    {"type":"function","function":{"name":"detail_article","description":"Obtenir le détail d'un article par son ID exact","parameters":{"type":"object","properties":{"id_shoes":{"type":"integer"}},"required":["id_shoes"]}}},
]

SYSTEM_PROMPT = """Tu es l'assistant IA de l'administrateur de PairIA, une boutique en ligne de chaussures.
Tu aides à gérer la boutique : commandes, catalogue, clients, commentaires, statistiques.

RÈGLES ABSOLUES :
- N'invente JAMAIS de données, d'IDs, de noms ou de prix. JAMAIS.
- Utilise TOUJOURS les outils pour obtenir des données réelles avant de répondre.
- Agis directement sans demander confirmation, SAUF pour les suppressions et les modifications de prix en lot.
- Réponds TOUJOURS en français.
- N'affiche JAMAIS de JSON ou de paramètres techniques dans tes réponses.

CATÉGORIES DISPONIBLES (utilise EXACTEMENT l'une de ces valeurs) :
Baskets lifestyle, Baskets sport, Bottines, Danse, Espadrilles, Imperméables, Indoor, Marche, Minimalistes, Mocassins, Montantes légères, Randonnée, Running, Sabots, Sandales, Sécurité, Slip-on, Talons, Training, Vegan

RÈGLES SUPPRESSION :
- Pour supprimer un article, appelle TOUJOURS rechercher_article d'abord pour obtenir l'ID réel.
- Montre le résultat, demande UNE confirmation, puis appelle supprimer_article avec l'ID réel.
- N'appelle JAMAIS supprimer_article avec un ID inventé.

STATUTS COMMANDES : en_attente → payée → expédiée → livrée. Ne rétrograde JAMAIS.
Pour plusieurs commandes, utilise modifier_statut_batch.

MODIFICATIONS DE PRIX — demande TOUJOURS confirmation avant :
- Avant tout modifier_prix_batch, dis exactement ce qui va se passer :
  "Je vais [augmenter/baisser] tous les prix [filtre] de [valeur]. Confirmer ?"
- Attends la confirmation, puis exécute.
- Pour une BAISSE, la valeur doit être NÉGATIVE : valeur=-5 pour baisser de 5€
- Pour une HAUSSE, la valeur doit être POSITIVE : valeur=5 pour augmenter de 5€
- "baisser le prix de l'article X de Y€" → appelle rechercher_article pour obtenir le prix actuel réel, puis appelle modifier_prix avec nouveau_prix = prix_actuel_réel - Y
- "mettre le prix de l'article X à Y€" → modifier_prix avec nouveau_prix = Y directement
- N'INVENTE JAMAIS le prix actuel — récupère-le TOUJOURS via rechercher_article
- Avant chaque appel à modifier_prix, appelle TOUJOURS detail_article ou rechercher_article pour obtenir le prix actuel réel au moment de l'action — même si tu penses déjà le connaître. Ne jamais utiliser un prix récupéré lors d'un tour précédent.

RECHERCHE ARTILCE/
- Si l'admin donne un ID numérique (ex: "article 3", "l'article numéro 61") → utilise detail_article avec cet ID exact
- Si l'admin donne un nom ou une description (ex: "les Dunk", "les Nike running") → utilise rechercher_article qui fait une recherche sémantique


CRÉATION D'ARTICLE :
- Demande : nom, catégorie (dans la liste), marque, genre, prix, description, caractéristiques, matériaux, usage, mots-clés, variantes (couleurs+pointures+stock)
- Inclus TOUJOURS url_image si une image a été fournie dans le contexte de session
- Appelle ajouter_article dès que tu as nom, catégorie, marque, prix et variantes""".strip()

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
                "content": f"[CONTEXTE] L'admin a uploadé une image. URL : {request.image_url} — utilise-la comme url_image lors de l'appel à ajouter_article."
            })
        question = f"[Image: {request.image_url}] {request.question}"
    else:
        question = request.question

    print(f"[ADMIN] session={session_id[:8]} | question: {question!r}")
    messages.append({"role": "user", "content": question})

    async def generate():
        content = ""
        had_tool_calls = False
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"

            max_iterations = 15
            iteration = 0

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

                    # Ignore les tool calls écrits en texte par le LLM
                    if '"name"' in content[:100] and '"arguments"' in content[:200]:
                        content = ""

                    # Fallback si pas de contenu après des tool_calls
                    if not content and had_tool_calls:
                        content = "C'est fait ✓"

                    messages.append({"role": "assistant", "content": content})
                    try:
                        for char in content:
                            yield f"data: {json.dumps({'chunk': char})}\n\n"
                    except Exception:
                        pass
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
                        except Exception:
                            fn_args = {}

                    # Cast des types
                    int_params   = ["id_commande","id_shoes","id_client","id_commentaire","limit","nouveau_stock","seuil"]
                    float_params = ["nouveau_prix","valeur","prix"]
                    for k, v in fn_args.items():
                        if k in int_params:   fn_args[k] = int(v)
                        if k in float_params: fn_args[k] = float(v)

                    status_text = ACTION_STATUS_TEXTS.get(fn_name, "Je traite la demande…")
                    try:
                        yield f"data: {json.dumps({'type': 'action_start', 'action': fn_name, 'status_text': status_text})}\n\n"
                    except Exception:
                        pass

                    result    = await call_php_action(fn_name, fn_args)
                    formatted = format_result_for_llm(fn_name, result)

                    try:
                        yield f"data: {json.dumps({'type': 'action_result', 'action': fn_name, 'result': result})}\n\n"
                    except Exception:
                        pass

                    messages.append({"role": "tool", "content": formatted, "name": fn_name})

                    # Reindex si article modifié
                    if fn_name in ['ajouter_article', 'modifier_article', 'supprimer_article']:
                        article_id = result.get('data', {}).get('id_shoes') if result.get('data') else None
                        run_reindex(article_id)

            # Nettoyage sessions
            if len(_session_messages) > 100:
                oldest = list(_session_messages.keys())[0]
                del _session_messages[oldest]

        except Exception as e:
            try:
                yield f"data: {json.dumps({'chunk': f'Erreur : {str(e)}'})}\n\n"
            except Exception:
                pass
        finally:
            try:
                yield "data: [DONE]\n\n"
            except Exception:
                pass

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/admin/health")
def health():
    return {"status": "ok", "service": "admin-chatbot"}